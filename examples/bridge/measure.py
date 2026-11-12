"""The demonstration's numbers (PIL and numpy; run by demo.py):
measure.py clip.json set.png composite-middle.png opaque-middle.png geometry-box.json out.json"""
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

record_path, still, composed, opaque, box_path, out = map(Path, sys.argv[1:7])
spec = importlib.util.spec_from_file_location("clip_record", Path(__file__).resolve().parents[2] / "clip_record.py")
clip_record = importlib.util.module_from_spec(spec)
sys.modules["clip_record"] = clip_record
spec.loader.exec_module(clip_record)                       # by its path, with nothing of `characters` imported
record = clip_record.load(record_path)
folder = record_path.parent
BACKDROP = np.array([0xFD, 0xEC, 0xD9], float)             # the low-poly finish's backdrop, which a cutout must not carry
SOLID = 250                                                # alpha from which a pixel is the figure, not its shadow's edge

facts = {"frames": record.frame_count, "size": [record.frame.width, record.frame.height], "fps": record.fps,
         "bytes_a_frame": {"mean": round(sum(f.bytes for f in record.frames) / record.frame_count),
                           "min": min(f.bytes for f in record.frames), "max": max(f.bytes for f in record.frames)},
         "bytes_all_frames": sum(f.bytes for f in record.frames)}

# where the feet land: the lowest solid row of every frame and the middle of the solid pixels in the 12 rows above it
lows, mids, modes = [], [], set()
for frame in record.frames:
    image = Image.open(folder / frame.file)
    modes.add(image.mode)
    alpha = np.asarray(image)[..., 3]
    ys, xs = np.nonzero(alpha >= SOLID)
    low = int(ys.max())
    near = xs[ys >= low - 12]
    lows.append(low)
    mids.append((int(near.min()) + int(near.max())) / 2)
feet = [f.figures[0].feet_px for f in record.frames]
facts["modes"] = sorted(modes)
facts["feet"] = {
    "record_feet_px_first": list(feet[0]), "record_feet_px_spread": [max(p[0] for p in feet) - min(p[0] for p in feet),
                                                                     max(p[1] for p in feet) - min(p[1] for p in feet)],
    "lowest_solid_row": {"min": min(lows), "max": max(lows), "mean": round(float(np.mean(lows)), 2)},
    "middle_column_of_the_shoes": {"min": min(mids), "max": max(mids), "mean": round(float(np.mean(mids)), 2)},
    "row_below_feet_px": {"min": round(min(l - p[1] for l, p in zip(lows, feet)), 2),
                          "max": round(max(l - p[1] for l, p in zip(lows, feet)), 2)},
    "column_off_feet_px": {"min": round(min(m - p[0] for m, p in zip(mids, feet)), 2),
                           "max": round(max(m - p[0] for m, p in zip(mids, feet)), 2)},
    "pixels_per_metre": record.frames[0].figures[0].pixels_per_metre}

# the middle frame: its solid pixels against the box round the exported geometry, as the record's camera projects it
k = record.frame_count // 2
rgba = np.asarray(Image.open(folder / record.frames[k].file)).astype(float)
alpha, colour = rgba[..., 3], rgba[..., :3]
ys, xs = np.nonzero(alpha >= SOLID)
drawn = [int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1]      # pixel edges, as a projection gives them
box = json.loads(box_path.read_text())["box_px"]
facts["middle_frame"] = {"frame": k, "solid_box_px": drawn, "geometry_box_px": [round(v, 2) for v in box],
                         "solid_minus_geometry_px": [round(d - b, 2) for d, b in zip(drawn, box)],
                         "note": "left, right, top, bottom; the finish redraws parts with few facets, so its outline "
                                 "lies a little inside or outside the exported surface"}

# the alpha's edge: a pixel partly clear that touches the figure has a colour of the figure beside it, not the
# backdrop's. For each such pixel: how far its colour is from the nearest colour among the solid pixels within two
# pixels of it, and whether it is nearer the backdrop's colour than any of them (a fringe).
solid = alpha >= SOLID
part = (alpha >= 32) & (alpha < SOLID)
nearest, fringe, pale = [], 0, 0
h, w = alpha.shape
for y, x in zip(*np.nonzero(part)):
    y0, y1, x0, x1 = max(0, y - 2), min(h, y + 3), max(0, x - 2), min(w, x + 3)
    near = solid[y0:y1, x0:x1]
    if near.sum() < 3:
        continue                                           # the shadow's own soft edge: black, by itself
    beside = np.abs(colour[y0:y1, x0:x1][near] - colour[y, x]).mean(axis=1).min()
    to_backdrop = float(np.abs(colour[y, x] - BACKDROP).mean())
    nearest.append(float(beside))
    fringe += to_backdrop < beside
    pale += to_backdrop < 40
facts["edge"] = {"edge_pixels": len(nearest),
                 "levels_from_the_nearest_figure_colour_beside": {"median": round(float(np.median(nearest)), 2),
                                                                  "p95": round(float(np.percentile(nearest, 95)), 2),
                                                                  "max": round(float(np.max(nearest)), 2)},
                 "nearer_the_backdrop_colour_than_the_figure": int(fringe),
                 "within_40_levels_of_the_backdrop_colour": int(pale),
                 "colour_where_alpha_is_0": int(rgba[alpha == 0][:, :3].max()) if (alpha == 0).any() else None,
                 "alpha": {"clear": round(float((alpha == 0).mean()), 5), "solid": round(float((alpha == 255).mean()), 5),
                           "between": round(float(((alpha > 0) & (alpha < 255)).mean()), 5),
                           "from_1_to_3": int(((alpha > 0) & (alpha <= 3)).sum()),
                           "shadow_strongest": int(alpha[(colour.max(axis=2) <= 2) & (alpha > 0)].max())}}

# the same frame drawn the old way (opaque, over the backdrop): where the cutout is solid the two are one picture
old = np.asarray(Image.open(opaque).convert("RGB")).astype(float)
inside = alpha == 255
laid = colour * (alpha[..., None] / 255) + BACKDROP * (1 - alpha[..., None] / 255)
facts["against_the_opaque_render"] = {
    "solid_pixels": int(inside.sum()),
    "levels_apart_where_solid": {"mean": round(float(np.abs(old - colour)[inside].mean()), 3),
                                 "max": int(np.abs(old - colour)[inside].max())},
    "levels_apart_cutout_laid_over_the_backdrop": {"mean": round(float(np.abs(old - laid).mean()), 4),
                                                   "max": int(np.abs(old - laid).max()),
                                                   "pixels_over_8": int((np.abs(old - laid).max(axis=2) > 8).sum())},
    "note": "the opaque render dithers (one level) and lays the backdrop under before the display curve, the "
            "comparison after it: soft shadow and edge pixels differ by that"}

# the engine's composite of the middle frame against the same two pictures laid together here, with the cutout
# moved by a few pixels each way: the engine put it where the frames have it if no move fits better than none
ground = np.asarray(Image.open(still).convert("RGB")).astype(float)
theirs = np.asarray(Image.open(composed).convert("RGB")).astype(float)
x0, x1, y0, y1 = drawn[0] - 24, drawn[1] + 24, drawn[2] - 24, drawn[3] + 24      # round the figure
errors = {}
for dy in range(-3, 4):
    for dx in range(-3, 4):
        moved = np.roll(rgba, (dy, dx), axis=(0, 1))
        laid_here = moved[..., :3] * (moved[..., 3:] / 255) + ground * (1 - moved[..., 3:] / 255)
        errors[(dx, dy)] = float(((laid_here - theirs)[y0:y1, x0:x1] ** 2).mean())
best = min(errors, key=errors.get)
whole = colour * (alpha[..., None] / 255) + ground * (1 - alpha[..., None] / 255)
psnr = lambda e: round(float(10 * np.log10(255 ** 2 / e)), 2)       # noqa: E731
facts["composite"] = {"psnr_db_whole_frame_against_set_plus_cutout": psnr(((whole - theirs) ** 2).mean()),
                      "best_move_of_the_cutout_px": list(best),
                      "psnr_db_round_the_figure": {"as_laid": psnr(errors[(0, 0)]), "one_px_right": psnr(errors[(1, 0)]),
                                                   "one_px_left": psnr(errors[(-1, 0)]), "one_px_down": psnr(errors[(0, 1)]),
                                                   "one_px_up": psnr(errors[(0, -1)])},
                      "record_feet_px": list(record.frames[k].figures[0].feet_px)}
out.write_text(json.dumps(facts, indent=1) + "\n")
