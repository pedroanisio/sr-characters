"""How close a rendered figure is to a reference sheet's, view by view.

    python sheet_match.py <sheet.png> <front.png> <profile.png> <back.png> [out.png]
                          [--widths] [--surface] [--brief] [--json report.json] [--debug prefix] [--sheet NAME]

Always prints the silhouette overlap (IoU, 0 to 1). The sheet's three figures are found by their colour against
the background (the three largest shapes, left to right: front, profile, back). Each outline is scaled to the
same height and centred before comparing. `out.png` shows them overlaid: sheet only in red, render only in blue,
both in grey.

--widths   where the outlines differ and by how much, front and profile, on the same scaled and centred
           outlines the IoU uses, in metres on a figure 1.0 m tall: a table of 40 heights from the feet (0.0) to
           the top of the cap (1.0), then a summary by body band (mean signed difference in centimetres,
           positive = ours wider / further out than the sheet).
--surface  how faceted the navy cloth reads, front and back: spread of lightness, share of edge pixels and
           typical facet size, sheet against ours, and one line of ours/sheet ratios.
--brief    with --widths only the band summary, with --surface only the ratio line.
--json     also write everything measured to this file.
--debug    with --surface: write pictures of the cloth measured, edges in red, to <this prefix>-<view>-<ref|ours>.png
--sheet    which sheet this is (SHEETS: officer, anchor): its body bands and what its colours need. Without it the
           sheet's file name says (anchor-sheet.png is the anchor's), and any other is measured as the officer's.

A piece that white cloth cuts off a figure (a head over a white collar, a hand past a white cuff) is found and
joined to it, in the sheet and in our pictures alike (`joined`).

Needs numpy, scipy and PIL.
"""
import json
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

SIZE = 512          # the square the outlines are compared in: SIZE px = the figure's height = 1.0 m
FINE = 768          # px per metre for the surface measures (close to the sheet's own resolution)
ROWS = 40           # heights in the width table

# body bands by share of the height (feet 0.0, top of the cap 1.0)
BANDS = [("cap", 0.90, 1.00), ("face", 0.79, 0.90), ("neck", 0.765, 0.79), ("shoulders", 0.72, 0.765),
         ("chest", 0.60, 0.72), ("midriff", 0.55, 0.60), ("waist/belt", 0.47, 0.55), ("hips", 0.41, 0.47),
         ("thigh", 0.30, 0.41), ("knee", 0.20, 0.30), ("shin", 0.12, 0.20), ("hem", 0.07, 0.12),
         ("boot", 0.00, 0.07)]
LEGS_BELOW = 0.55   # the legs can only part below this height
LEG_GAP = 0.03      # the gap between the legs lies within this distance of the centre line, metres
ARMS = (0.20, 0.72)  # in the front view an arm or hand apart from the body is looked for between these heights
BARE = (0.25, 0.66)  # in the profile bare arm and hand (skin below the sleeve) are looked for between these
NECK = (0.74, 0.84)  # the narrowest place between the head and the shoulders is looked for between these heights
ARM_BANDS = (("sleeve", 0.60, 0.72), ("forearm", 0.47, 0.60))  # where the arm's outer edge is compared, front view
HAND_TOP = 0.45     # and the hand's: from just over its lowest point up to here
CHEST = (0.60, 0.70)  # the heights over which the front outline's middle is checked against the centre line
SHANK = (0.12, 0.30)  # and the lower leg, whose middle says how far back a profile stands
DARK = 0.45         # a pixel this much darker than the background (share of its brightness) is figure, whatever its hue
ENCLOSED = False    # what the outline encloses counts as figure for the IoU too (see SHEETS)
SHOULDER_AT = (0.05, 0.08, 0.11, 0.14, 0.17)  # distances from the centre line where the shoulder line is read
CLOTH = (0.02, 0.775)  # heights of the navy cloth measured for the surface (above the soles, below the collar)
EDGE = 4.0          # a cloth pixel is an edge when lightness (L*, 0 to 100) changes faster than this per cm
BLUR = 0.002        # blur before taking that change, metres (hides render noise and compression blocks)
RIM = 0.008         # cloth this close to its own border is left out, metres
# a piece apart from a figure belongs to it (a head over a white collar, a hand past a white cuff: `joined`) when it
# is at least JOIN_SIZE of the figure's area and no further from it than JOIN_GAP of its height; the cloth between
# them is what a disc of JOIN_DISC of that height (or wider than the gap) cannot enter
JOIN_SIZE, JOIN_GAP, JOIN_DISC = 0.01, 0.03, 0.012
ENCLOSE_DISC, ENCLOSE_OPEN = 0.02, 0.2  # see `enclosed`

# The measures above are the officer's sheet's: a figure in a cap whose head with it is 0.225 of the height. Another
# sheet says here what differs: its own bands and heights (a bare-headed adult's chin is at 0.85, not 0.79), and
# what its colours need. `--sheet NAME` picks one; without it, the one whose name the sheet's file name starts with
# (anchor-sheet.png: "anchor"), else the officer's.
SHEETS = {
    "officer": {},
    # a news anchor in a suit, bare-headed, drawn with the arms held out in the front and the back views: a white
    # shirt (ENCLOSED: it shows between the lapels and at the collar) and grey hair at the temples (DARK: grey is
    # the background's hue, only darker)
    "anchor": dict(
        BANDS=[("hair", 0.93, 1.00), ("face", 0.85, 0.93), ("neck", 0.81, 0.85), ("shoulders", 0.70, 0.81),
               ("chest", 0.62, 0.70), ("waist", 0.54, 0.62), ("hips", 0.46, 0.54), ("thigh", 0.32, 0.46),
               ("knee", 0.22, 0.32), ("shin", 0.12, 0.22), ("hem", 0.06, 0.12), ("shoe", 0.00, 0.06)],
        ARMS=(0.38, 0.70), BARE=(0.40, 0.58), NECK=(0.80, 0.87), ARM_BANDS=(("sleeve", 0.62, 0.70), ("forearm", 0.54, 0.62)),
        HAND_TOP=0.52, CHEST=(0.60, 0.69), SHANK=(0.10, 0.28), CLOTH=(0.07, 0.80), DARK=0.6, ENCLOSED=True),
}


def use(sheet):
    """Measure as the sheet named needs (SHEETS)."""
    globals().update(SHEETS[sheet])


def sheet_of(path):
    """The sheet a file is, by its name: the one of SHEETS its name starts with, else the officer's."""
    name = path.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return next((k for k in SHEETS if name.startswith(k)), "officer")


def mask_of(im, tol=None):
    """What is figure and not background: a shadow on the ground only dims the background evenly, so a pixel
    counts when its colour differs from the background's in hue (the channels dim unevenly) or it is far darker."""
    a = np.asarray(im.convert("RGB")).astype(np.float64)
    bg = np.median(np.concatenate([a[:8].reshape(-1, 3), a[-8:].reshape(-1, 3), a[:, :8].reshape(-1, 3), a[:, -8:].reshape(-1, 3)]), axis=0)
    r = a / np.maximum(bg, 1.0)
    return (r.max(axis=2) - r.min(axis=2) > 0.12) | (r.mean(axis=2) < DARK)


def figures(mask, count):
    """The `count` largest shapes, left to right, each with what belongs to it across a strip of white cloth."""
    lab, n = ndimage.label(ndimage.binary_opening(mask, iterations=2))
    sizes = ndimage.sum(mask, lab, range(1, n + 1))
    keep = sorted(np.argsort(sizes)[-count:] + 1, key=lambda k: ndimage.center_of_mass(lab == k)[1])
    return joined([lab == k for k in keep], lab, sizes, keep)


def disc(r):
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r


def joined(shapes, lab, sizes, keep):
    """White cloth is the background's colour, so a white collar cuts the head off a figure and a white cuff a
    hand: a piece that is no speck (JOIN_SIZE of the figure's area) and lies within JOIN_GAP of the figure's height
    from it is part of that figure, and so is what lies between the two (the collar, the cuff): the strip a disc
    wider than it cannot enter. A sheet with no such piece is left exactly as it was found."""
    tall = [np.ptp(np.nonzero(s.any(axis=1))[0]) + 1 for s in shapes]
    far = [ndimage.distance_transform_edt(~s) for s in shapes]
    out = [s.copy() for s in shapes]
    for k in np.argsort(sizes)[::-1] + 1:
        if k in keep:
            continue
        piece = lab == k
        gaps = [f[piece].min() for f in far]
        i = int(np.argmin(gaps))
        gap = float(gaps[i])
        if sizes[k - 1] < JOIN_SIZE * min(sizes[j - 1] for j in keep):
            break                                   # (the pieces come largest first: the rest are specks)
        if sizes[k - 1] < JOIN_SIZE * sizes[keep[i] - 1] or gap > JOIN_GAP * tall[i]:
            continue
        r = int(np.ceil(max(gap + 2, JOIN_DISC * tall[i])))
        ys, xs = np.nonzero(piece)
        pad = 3 * r + int(gap) + 4
        box = (slice(max(0, ys.min() - pad), ys.max() + pad + 1), slice(max(0, xs.min() - pad), xs.max() + pad + 1))
        both = shapes[i][box] | piece[box]
        closed = ndimage.binary_closing(np.pad(both, r), structure=disc(r))[r:-r, r:-r]
        reach = gap + r
        between = closed & (far[i][box] <= reach) & (ndimage.distance_transform_edt(~piece[box]) <= reach)
        out[i][box] |= piece[box] | between
    return out


def squared(m, size=SIZE):
    ys, xs = np.nonzero(m)
    crop = Image.fromarray((m[ys.min():ys.max() + 1, xs.min():xs.max() + 1] * 255).astype(np.uint8))
    w = max(1, round(crop.width * size / crop.height))
    crop = crop.resize((w, size))
    out = Image.new("L", (size, size))
    out.paste(crop, ((size - w) // 2, 0))
    return np.asarray(out) > 127


def squared_colour(im, m, size=SIZE):
    """The picture's colours in the same square as `squared` puts the outline (the canvas may be wider)."""
    ys, xs = np.nonzero(m)
    crop = im.convert("RGB").crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    w = max(1, round(crop.width * size / crop.height))
    crop = crop.resize((w, size), Image.LANCZOS)
    side = max(size, w)
    out = Image.new("RGB", (side, size))
    out.paste(crop, ((side - w) // 2, 0))
    return np.asarray(out).astype(np.float64)


def hue_sat_val(a):
    a = a / 255.0
    hi, lo = a.max(axis=2), a.min(axis=2)
    d = np.where(hi > lo, hi - lo, 1.0)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    hue = np.where(hi == r, ((g - b) / d) % 6, np.where(hi == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    return np.where(hi > lo, hue, 0.0), np.where(hi > 0, (hi - lo) / np.maximum(hi, 1e-9), 0.0), hi


def is_skin(a):
    hue, sat, val = hue_sat_val(a)
    return (hue > 8) & (hue < 34) & (sat > 0.3) & (val > 0.4)


def is_navy(a):
    hue, sat, val = hue_sat_val(a)
    return (hue > 225) & (hue < 290) & (sat > 0.2)


# ---------------------------------------------------------------------------------------------- widths

def height_of(row, size=SIZE):
    return 1.0 - (row + 0.5) / size


def rows_of(lo, hi, size=SIZE):
    """The pixel rows whose centres lie between two heights."""
    h = height_of(np.arange(size), size)
    return np.nonzero((h >= lo) & (h < hi))[0]


def tidy(m):
    """Small holes closed (buckle, buttons, eyes: parts whose colour is the background's), so that a row's
    runs are body parts. A large enclosed gap, such as between an arm and the torso, is left open."""
    lab, n = ndimage.label(ndimage.binary_fill_holes(m) & ~m)
    small = np.nonzero(ndimage.sum(np.ones_like(lab), lab, range(1, n + 1)) < 0.003 * m.shape[0] ** 2)[0] + 1
    return m | np.isin(lab, small)


def enclosed(m):
    """White cloth inside a figure: what its outline encloses is figure, also where the white reaches the outline
    through a gap that a disc of ENCLOSE_DISC of the height cannot enter (a shirt's front shows between the lapels
    and comes out at the collar). Such a place has the figure nearly all round it (ENCLOSE_OPEN: the most of its
    edge that may be open); a concave corner that the disc only rounds off has not. Nor is it the gap between
    the legs or between an arm and the trunk: it is under 1% of the square, and above where the legs can part."""
    r = int(round(ENCLOSE_DISC * m.shape[0]))
    closed = ndimage.binary_closing(np.pad(m, r), structure=disc(r))[r:-r, r:-r]
    lab, n = ndimage.label(ndimage.binary_fill_holes(closed) & ~m)
    out = m.copy()
    for k, box in enumerate(ndimage.find_objects(lab), 1):
        box = tuple(slice(max(0, s.start - 1), s.stop + 1) for s in box)
        piece = lab[box] == k
        if piece.sum() >= 0.01 * m.shape[0] ** 2:
            continue
        rim = ndimage.binary_dilation(piece, structure=np.ones((3, 3), bool)) & ~piece
        gap = (rim & ~m[box]).sum()
        # (between the legs the outline is open by rights: there only a hole it closes all round counts)
        if gap <= ENCLOSE_OPEN * rim.sum() and (not gap or height_of(box[0].stop - 1, m.shape[0]) > LEGS_BELOW):
            out[box] |= piece
    return out


def runs_of(line):
    d = np.diff(np.concatenate([[0], line.astype(np.int8), [0]]))
    return [(int(a), int(b)) for a, b in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]) if b - a >= 2]


def front_rows(m):
    """Row by row of a front (or back) outline, in metres from the centre line (left of the picture negative):
    out = the outline's outermost edges; body = the run on the centre line (torso, head), or below the crotch
    the two legs' outer edges; inner = the legs' inner edges; arm = outer edge of a run lying outside the body
    (arm or hand apart from the torso or the legs), arm_in its inner edge. NaN where there is none."""
    size = m.shape[0]
    c = m.shape[1] / 2.0
    keys = ("out_l", "out_r", "body_l", "body_r", "inner_l", "inner_r", "arm_l", "arm_r", "arm_in_l", "arm_in_r")
    t = {k: np.full(size, np.nan) for k in keys}
    for y in range(size):
        h = height_of(y, size)
        runs = runs_of(m[y])
        if not runs:
            continue
        t["out_l"][y], t["out_r"][y] = runs[0][0], runs[-1][1]
        gaps = [(runs[i][1], runs[i + 1][0], i) for i in range(len(runs) - 1)]
        near = [g for g in gaps if g[0] - LEG_GAP * size <= c <= g[1] + LEG_GAP * size]
        if h < LEGS_BELOW and near:
            i = min(near, key=lambda g: abs((g[0] + g[1]) / 2 - c))[2]
            first, last = i, i + 1
            t["inner_l"][y], t["inner_r"][y] = runs[i][1], runs[i + 1][0]
        else:
            first = last = min(range(len(runs)), key=lambda i: 0 if runs[i][0] <= c <= runs[i][1] else min(abs(runs[i][0] - c), abs(runs[i][1] - c)))
        t["body_l"][y], t["body_r"][y] = runs[first][0], runs[last][1]
        if ARMS[0] < h < ARMS[1]:
            if first > 0:
                t["arm_l"][y], t["arm_in_l"][y] = runs[0][0], runs[first - 1][1]
            if last < len(runs) - 1:
                t["arm_r"][y], t["arm_in_r"][y] = runs[-1][1], runs[last + 1][0]
    return {k: (v - c) / size for k, v in t.items()}


def neck_of(t):
    """The narrowest place between head and shoulders: (height, width in metres, pixel row)."""
    rows = rows_of(*NECK, len(t["body_l"]))
    w = (t["body_r"] - t["body_l"])[rows]
    i = int(np.nanargmin(w))
    return float(height_of(rows[i], len(t["body_l"]))), float(w[i]), int(rows[i])


def shoulder_line(m, neck_row):
    """Height of the top of the shoulder at set distances from the centre line, each side: the first figure
    pixel going down from the figure's own neck. NaN where the column is inside the neck."""
    size = m.shape[0]
    c = m.shape[1] / 2.0
    out = {}
    for d in SHOULDER_AT:
        for side, sign in (("l", -1), ("r", 1)):
            col = m[neck_row:, int(round(c + sign * d * size - 0.5))]
            hit = np.nonzero(col)[0]
            out[(d, side)] = np.nan if col[0] or not len(hit) else 1.0 - (neck_row + hit[0]) / size
    return out


def hand_low(t, side):
    """The hand's lowest point on one side: (height, distance from the centre line of the hand's middle there),
    from the lowest rows where a piece stands apart from the body."""
    rows = np.nonzero(~np.isnan(t["arm_" + side]))[0]
    if not len(rows):
        return None
    low = rows[rows > rows.max() - 4]
    return float(1.0 - (rows.max() + 1) / len(t["arm_" + side])), float(np.mean(np.abs(t["arm_" + side][low] + t["arm_in_" + side][low]) / 2))


def profile_rows(m, rgb):
    """Row by row of a profile outline facing left, in metres from the centre line, both counted outwards:
    front = how far forward the outline reaches, back = how far back. skin_f / skin_b say whether bare skin
    (arm, hand) is what reaches furthest there, below the sleeve. arm_f / arm_b = how far forward and back
    the bare arm and hand themselves reach in that row (NaN where there is none)."""
    size = m.shape[0]
    c = m.shape[1] / 2.0
    off = (rgb.shape[1] - m.shape[1]) // 2
    skin = ndimage.binary_opening(is_skin(rgb)[:, off:off + m.shape[1]] & m, iterations=1)
    t = {k: np.full(size, np.nan) for k in ("front", "back", "arm_f", "arm_b")}
    t["skin_f"], t["skin_b"] = np.zeros(size, bool), np.zeros(size, bool)
    for y in range(size):
        xs = np.nonzero(m[y])[0]
        if not len(xs):
            continue
        a, b = xs[0], xs[-1] + 1
        t["front"][y], t["back"][y] = (c - a) / size, (b - c) / size
        if BARE[0] < height_of(y, size) < BARE[1] and b - a > 8:
            t["skin_f"][y] = skin[y, a + 2:a + 7].mean() > 0.5
            t["skin_b"][y] = skin[y, b - 7:b - 2].mean() > 0.5
            xs = np.nonzero(skin[y])[0]
            if len(xs):
                t["arm_f"][y], t["arm_b"][y] = (c - xs[0]) / size, (xs[-1] + 1 - c) / size
    return t


def faces_left(m):
    """The toes are in front: the boots reach further from the ankle's middle on the side the figure faces."""
    foot, ankle = m[rows_of(0.0, 0.05)], m[rows_of(0.10, 0.16)]
    xs, mid = np.nonzero(foot.any(axis=0))[0], np.nonzero(ankle.any(axis=0))[0]
    mid = (mid[0] + mid[-1]) / 2
    return mid - xs[0] > xs[-1] - mid


def best_shift(a, b):
    """How many pixels to slide b sideways for the best overlap with a, and that overlap."""
    best = (0, 0.0)
    for s in range(-40, 41):
        r = np.roll(b, s, axis=1)
        score = (a & r).sum() / (a | r).sum()
        if score > best[1]:
            best = (s, score)
    return best


def paired(ref, ours, rows, ok=None):
    """Means of a measure over the rows where both figures have it (and `ok` allows): ref, ours, rows used."""
    use = ~np.isnan(ref[rows]) & ~np.isnan(ours[rows])
    if ok is not None:
        use &= ok[rows]
    if not use.any():
        return float("nan"), float("nan"), 0
    return float(ref[rows][use].mean()), float(ours[rows][use].mean()), int(use.sum())


def fmt(v, spec="%+.3f", blank=None):
    text = spec % 0.0
    return (blank or "n/a").rjust(len(text)) if v is None or np.isnan(v) else spec % v


def cm(ref, ours):
    return float("nan") if np.isnan(ref) or np.isnan(ours) else (ours - ref) * 100


def sample_rows():
    return [int(round((1 - (i + 0.5) / ROWS) * SIZE - 0.5)) for i in range(ROWS)]


def row_record(y, ref, ours):
    cell = lambda v: bool(v) if isinstance(v, (bool, np.bool_)) else (None if np.isnan(v) else round(float(v), 4))
    return {"h": round(float(height_of(y)), 4), "ref": {k: cell(v[y]) for k, v in ref.items()}, "ours": {k: cell(v[y]) for k, v in ours.items()}}


def torso_alone(t):
    """Rows where the body run is the torso or the legs on their own, each side: at the shoulders and above,
    where an arm or hand stands apart, and below the hand. In between the arm is joined to the torso."""
    h = height_of(np.arange(SIZE))
    ok = np.ones(SIZE, bool)
    for s in "lr":
        has = ~np.isnan(t["arm_" + s])
        below = np.arange(SIZE) > (np.nonzero(has)[0].max() if has.any() else SIZE * (1 - ARMS[0]))
        ok &= (h >= ARMS[1]) | has | below
    return ok


def front_report(a, b, brief, say):
    a, b = tidy(a), tidy(b)
    ra, rb = front_rows(a), front_rows(b)
    alone = torso_alone(ra) & torso_alone(rb)
    sample = sample_rows()
    data = {"rows": [row_record(y, ra, rb) for y in sample], "bands": []}
    if not brief:
        say("")
        say("front, metres from the centre line (ref  ours  ours further out):")
        say("  body = the piece on the centre line (head, torso), below the crotch the two legs' outer edges.")
        say("  pieces: 1 = one piece (between %.2f and %.2f that means the arms are joined to the torso), A = an arm or hand stands apart, L = legs apart" % ARMS)
        say("    h   |      body L          |      body R          |    body width        | pieces ref ours")
        for y in sample:
            la, lb, r_a, r_b = -ra["body_l"][y], -rb["body_l"][y], ra["body_r"][y], rb["body_r"][y]
            pieces = ["".join(("A" if not (np.isnan(t["arm_l"][y]) and np.isnan(t["arm_r"][y])) else "", "L" if not np.isnan(t["inner_l"][y]) else "")) or "1" for t in (ra, rb)]
            say("  %.3f | %s %s %s | %s %s %s | %s %s %s |        %-3s %s" % (
                height_of(y), fmt(-la, "%6.3f"), fmt(-lb, "%6.3f"), fmt(lb - la), fmt(r_a, "%6.3f"), fmt(r_b, "%6.3f"), fmt(r_b - r_a),
                fmt(la + r_a, "%6.3f"), fmt(lb + r_b, "%6.3f"), fmt(lb + r_b - la - r_a), pieces[0], pieces[1]))
        say("")
        say("  legs' inner edges, and the edges of an arm or hand standing apart from the body (outer = outermost, inner = towards the body):")
        say("    h   |    leg inner L       |    leg inner R       |    arm outer L       |    arm outer R       |    arm inner L       |    arm inner R")
        for y in sample:
            cells = []
            for k, sign in (("inner_l", -1), ("inner_r", 1), ("arm_l", -1), ("arm_r", 1), ("arm_in_l", -1), ("arm_in_r", 1)):
                va, vb = ra[k][y], rb[k][y]
                cells.append("%s %s %s" % (fmt(va, "%6.3f"), fmt(vb, "%6.3f"), fmt(sign * (vb - va))))
            say("  %.3f | %s" % (height_of(y), " | ".join(cells)))

    say("")
    say("front by band, cm, + = ours wider / further out than the reference:")
    say("  torso/legs = the piece on the centre line without the arms (legs: outer edges); outline = outermost edge, arms and hands included;")
    say("  legs inner = inner edge further from the centre line; leg width = outer to inner edge")
    say("  band        heights     | torso/legs L     R  both | outline L     R  both | legs inner L     R | leg width L     R | note")
    for name, lo, hi in BANDS:
        rows = rows_of(lo, hi)
        bl = paired(-ra["body_l"], -rb["body_l"], rows, alone)
        br = paired(ra["body_r"], rb["body_r"], rows, alone)
        ol = paired(-ra["out_l"], -rb["out_l"], rows)
        orr = paired(ra["out_r"], rb["out_r"], rows)
        il = paired(-ra["inner_l"], -rb["inner_l"], rows)
        ir = paired(ra["inner_r"], rb["inner_r"], rows)
        wl = paired(ra["inner_l"] - ra["body_l"], rb["inner_l"] - rb["body_l"], rows)
        wr = paired(ra["body_r"] - ra["inner_r"], rb["body_r"] - rb["inner_r"], rows)
        d = [cm(*x[:2]) for x in (bl, br, ol, orr, il, ir, wl, wr)]
        note = []
        if bl[2] < len(rows):
            note.append("torso apart from the arms in only %d of %d rows" % (bl[2], len(rows)) if bl[2] else "arms joined to the torso in one or both: outline only")
        split = [int((~np.isnan(t["inner_l"][rows])).sum()) for t in (ra, rb)]
        if max(split) and min(split) < len(rows):
            note.append("legs apart in %d (ref) and %d (ours) of %d rows" % (split[0], split[1], len(rows)))
        one = lambda v: fmt(v, "%+5.1f")
        say("  %-11s %.3f-%.3f |        %s %s %s |     %s %s %s |        %s %s |       %s %s | %s" % (
            name, lo, hi, one(d[0]), one(d[1]), one(d[0] + d[1]), one(d[2]), one(d[3]), one(d[2] + d[3]), one(d[4]), one(d[5]), one(d[6]), one(d[7]), "; ".join(note)))
        data["bands"].append({"band": name, "from": lo, "to": hi, "rows": len(rows), "torso_rows": bl[2],
                              "torso_l_cm": d[0], "torso_r_cm": d[1], "outline_l_cm": d[2], "outline_r_cm": d[3],
                              "leg_inner_l_cm": d[4], "leg_inner_r_cm": d[5], "leg_width_l_cm": d[6], "leg_width_r_cm": d[7],
                              "ref_torso_width_m": bl[0] + br[0], "ours_torso_width_m": bl[1] + br[1],
                              "ref_outline_width_m": ol[0] + orr[0], "ours_outline_width_m": ol[1] + orr[1]})

    # arms and hands
    lows = {s: (hand_low(ra, s), hand_low(rb, s)) for s in "lr"}
    hand_from = max([p[0] for pair in lows.values() for p in pair if p] or [0.33]) + 0.01
    cells, data["arm_outer_cm"] = [], {}
    for label, lo, hi in (*ARM_BANDS, ("hand", hand_from, HAND_TOP)):
        rows = rows_of(lo, hi)
        d = [cm(*paired(-ra["out_l"], -rb["out_l"], rows)[:2]), cm(*paired(ra["out_r"], rb["out_r"], rows)[:2])]
        cells.append("%s %.2f-%.2f  L %+.1f  R %+.1f" % (label, lo, hi, *d))
        data["arm_outer_cm"][label] = {"from": lo, "to": hi, "l": d[0], "r": d[1]}
    say("  arm outer edge:  " + "   ".join(cells))
    rows = rows_of(hand_from, HAND_TOP)
    d = [cm(*paired(-ra["arm_in_l"], -rb["arm_in_l"], rows)[:2]), cm(*paired(ra["arm_in_r"], rb["arm_in_r"], rows)[:2])]
    say("  hand inner edge (the side towards the leg), %.2f-%.2f:  L %s  R %s" % (hand_from, HAND_TOP, fmt(d[0], "%+.1f"), fmt(d[1], "%+.1f")))
    data["hand_inner_cm"] = {"from": hand_from, "to": HAND_TOP, "l": d[0], "r": d[1]}
    data["hands"] = {}
    for s, label in (("l", "L"), ("r", "R")):
        ha, hb = lows[s]
        if ha and hb:
            say("  hand %s lowest point: ref at height %.3f, its middle %.3f m from the centre line; ours at %.3f, %.3f m: ours %.1f cm %s and %.1f cm %s" % (
                label, ha[0], ha[1], hb[0], hb[1], abs(hb[0] - ha[0]) * 100, "lower" if hb[0] < ha[0] else "higher",
                abs(hb[1] - ha[1]) * 100, "further out" if hb[1] > ha[1] else "closer in"))
            data["hands"][s] = {"ref": {"lowest_h": ha[0], "from_centre_m": ha[1]}, "ours": {"lowest_h": hb[0], "from_centre_m": hb[1]}}
        else:
            say("  hand %s: not apart from the body in %s" % (label, "the reference" if not ha else "ours"))
    na, nb = neck_of(ra), neck_of(rb)
    sa, sb = shoulder_line(a, na[2]), shoulder_line(b, nb[2])
    cells, data["shoulder_line"] = [], []
    for dist in SHOULDER_AT:
        va, vb = [np.nan if np.all(np.isnan(v)) else float(np.nanmean(v)) for v in ([s[(dist, "l")], s[(dist, "r")]] for s in (sa, sb))]
        cells.append("%.2f m: %s %s %s" % (dist, fmt(va, "%.3f", "neck"), fmt(vb, "%.3f", "neck"), fmt(cm(va, vb), "%+.1f")))
        data["shoulder_line"].append({"at_m": dist, "ref_h": va, "ours_h": vb})
    say("  shoulder line, height of the top of the shoulder at a distance from the centre line (ref  ours  ours higher in cm; mean of both sides):")
    say("    " + "    ".join(cells))
    crotch = [float(height_of(np.nonzero(~np.isnan(t["inner_l"]))[0].min()) + 0.5 / SIZE) if np.any(~np.isnan(t["inner_l"])) else np.nan for t in (ra, rb)]
    say("  crotch (where the legs part): ref %.3f, ours %.3f: ours %.1f cm %s;   narrowest neck: ref %.3f m wide at height %.3f, ours %.3f m at %.3f" % (
        crotch[0], crotch[1], abs(cm(*crotch)), "lower" if crotch[1] < crotch[0] else "higher", na[1], na[0], nb[1], nb[0]))
    data["crotch_h"] = {"ref": crotch[0], "ours": crotch[1]}
    data["neck"] = {"ref": {"h": na[0], "width_m": na[1]}, "ours": {"h": nb[0], "width_m": nb[1]}}
    mid = [float(np.nanmean(((t["body_l"] + t["body_r"]) / 2)[rows_of(*CHEST)])) for t in (ra, rb)]
    say("  centring check: the middle of the outline at the chest is %+.1f cm (ref) and %+.1f cm (ours) off the centre line" % (mid[0] * 100, mid[1] * 100))
    data["chest_middle_off_centre_m"] = {"ref": mid[0], "ours": mid[1]}
    return data


def profile_report(a, b, ca, cb, brief, say):
    a, b = tidy(a), tidy(b)
    pa, pb = profile_rows(a, ca), profile_rows(b, cb)
    sample = sample_rows()
    data = {"rows": [row_record(y, pa, pb) for y in sample], "bands": []}
    say("")
    if not faces_left(a) or not faces_left(b):
        say("WARNING: a profile does not seem to face left (ref %s, ours %s); front and back below assume both face left" % (
            "left" if faces_left(a) else "right", "left" if faces_left(b) else "right"))
    if not brief:
        say("profile (facing left), metres from the centre line, each edge counted outwards (ref  ours  ours further out);")
        say("  arm = the bare arm or hand is what reaches furthest there (f = at the front, b = at the back), so the clothes' own edge is hidden")
        say("    h   |    front edge        |    back edge         |    depth             | arm ref ours")
        for y in sample:
            fa, fb, ba, bb = pa["front"][y], pb["front"][y], pa["back"][y], pb["back"][y]
            flags = [("f" if t["skin_f"][y] else "") + ("b" if t["skin_b"][y] else "") or "-" for t in (pa, pb)]
            say("  %.3f | %s %s %s | %s %s %s | %s %s %s |     %-3s %s" % (
                height_of(y), fmt(fa, "%6.3f"), fmt(fb, "%6.3f"), fmt(fb - fa), fmt(ba, "%6.3f"), fmt(bb, "%6.3f"), fmt(bb - ba),
                fmt(fa + ba, "%6.3f"), fmt(fb + bb, "%6.3f"), fmt(fb + bb - fa - ba), flags[0], flags[1]))
        say("")
    say("profile by band, cm, + = ours further out than the reference (front + = further forward, back + = further back):")
    say("  clothes only = the same over the rows where neither figure's edge is the bare arm or hand")
    say("  band        heights     | front  back  depth | clothes only: front  back | note")
    for name, lo, hi in BANDS:
        rows = rows_of(lo, hi)
        f = paired(pa["front"], pb["front"], rows)
        k = paired(pa["back"], pb["back"], rows)
        cf = paired(pa["front"], pb["front"], rows, ~pa["skin_f"] & ~pb["skin_f"])
        ck = paired(pa["back"], pb["back"], rows, ~pa["skin_b"] & ~pb["skin_b"])
        d = [cm(*x[:2]) for x in (f, k, cf, ck)]
        note = []
        for label, key in (("front", "skin_f"), ("back", "skin_b")):
            share = [t[key][rows].mean() * 100 for t in (pa, pb)]
            if max(share) > 0:
                note.append("%s edge is the bare arm or hand in %.0f%% (ref) and %.0f%% (ours) of the rows" % (label, *share))
        one = lambda v: fmt(v, "%+5.1f")
        say("  %-11s %.3f-%.3f | %s %s  %s |               %s %s | %s" % (name, lo, hi, one(d[0]), one(d[1]), one(d[0] + d[1]), one(d[2]), one(d[3]), "; ".join(note)))
        data["bands"].append({"band": name, "from": lo, "to": hi, "rows": len(rows), "front_cm": d[0], "back_cm": d[1],
                              "clothes_front_cm": d[2], "clothes_back_cm": d[3], "clothes_front_rows": cf[2], "clothes_back_rows": ck[2],
                              "ref_front_m": f[0], "ours_front_m": f[1], "ref_back_m": k[0], "ours_back_m": k[1]})
    # the bare arm and hand themselves
    data["bare_arm"] = {}
    for who, t in (("ref", pa), ("ours", pb)):
        if np.all(np.isnan(t["arm_f"])):
            continue
        yf, yb, low = int(np.nanargmax(t["arm_f"])), int(np.nanargmax(t["arm_b"])), int(np.nonzero(~np.isnan(t["arm_f"]))[0].max())
        data["bare_arm"][who] = {"front_m": float(t["arm_f"][yf]), "front_h": float(height_of(yf)), "back_m": float(t["arm_b"][yb]), "back_h": float(height_of(yb)),
                                 "lowest_h": float(height_of(low) - 0.5 / SIZE)}
    if len(data["bare_arm"]) == 2:
        r, o = data["bare_arm"]["ref"], data["bare_arm"]["ours"]
        say("  bare arm and hand: furthest forward ref %.3f m in front of the centre line (at height %.2f), ours %.3f m (at %.2f): ours %+.1f cm further forward;" % (
            r["front_m"], r["front_h"], o["front_m"], o["front_h"], cm(r["front_m"], o["front_m"])))
        say("    furthest back (elbow) ref %.3f m behind it (at %.2f), ours %.3f m (at %.2f): ours %+.1f cm further back;  lowest point ref %.3f, ours %.3f" % (
            r["back_m"], r["back_h"], o["back_m"], o["back_h"], cm(r["back_m"], o["back_m"]), r["lowest_h"], o["lowest_h"]))
    shift, score = best_shift(a, b)
    legs = [float(np.nanmean(((t["back"] - t["front"]) / 2)[rows_of(*SHANK)])) for t in (pa, pb)]
    say("  centring check: each outline is centred between its own furthest points, as for the IoU. The outlines overlap best (IoU %.3f) with ours moved %.1f cm %s;"
        % (score, abs(shift) * 100.0 / SIZE, "back" if shift >= 0 else "forward"))
    say("    the middle of the lower leg (%.2f-%.2f) lies %+.1f cm (ref) and %+.1f cm (ours) behind the centre line. Moving ours x cm back adds x to every back figure and takes x off every front figure"
        % (*SHANK, legs[0] * 100, legs[1] * 100))
    data["best_overlap"] = {"ours_moved_back_cm": shift * 100.0 / SIZE, "iou": float(score)}
    data["lower_leg_middle_behind_centre_m"] = {"ref": legs[0], "ours": legs[1]}
    return data


def width_report(pairs, brief, report):
    """pairs: {'front': (ref outline, our outline), 'profile': (ref outline, ours, ref colours, our colours)}"""
    out = []
    out.append("widths: figure 1.0 m tall, feet 0.0, top of the cap 1.0; same scaling and centring as the IoU "
               "(1 px = %.1f mm); L and R are the picture's left and right" % (1000.0 / SIZE))
    out.append("bands by share of the height: " + ", ".join("%s %s-%s" % (n, ("%.3f" % lo).rstrip("0").ljust(4, "0"), ("%.3f" % hi).rstrip("0").ljust(4, "0")) for n, lo, hi in BANDS[::-1]))
    report["bands"] = [{"band": n, "from": lo, "to": hi} for n, lo, hi in BANDS]
    report["front"] = front_report(*pairs["front"], brief, out.append)
    report["profile"] = profile_report(*pairs["profile"], brief, out.append)
    return out


# ---------------------------------------------------------------------------------------------- surface

def lightness(a):
    """CIE L* (0 to 100) of sRGB colours: evenly spaced for the eye, so a spread means the same dark or light."""
    c = a / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    y = lin @ np.array([0.2126, 0.7152, 0.0722])
    return np.where(y > 0.008856, 116 * np.cbrt(y) - 16, 903.3 * y)


def run_lengths(flat, cloth):
    """Lengths of the unbroken stretches of flat cloth along each line of two arrays."""
    lengths = []
    for f, c in zip(flat, cloth):
        d = np.diff(np.concatenate([[0], (f & c).astype(np.int8), [0]]))
        lengths.append(np.nonzero(d == -1)[0] - np.nonzero(d == 1)[0])
    return np.concatenate(lengths) if lengths else np.zeros(0)


def surface_of(im, m, debug=None):
    """The navy cloth of one figure: lightness spread, share of edge pixels, typical facet size in metres.
    None when the figure has next to no navy cloth."""
    rgb = squared_colour(im, m, FINE)
    fig = squared(m, FINE)
    fig = np.pad(fig, ((0, 0), ((rgb.shape[1] - fig.shape[1]) // 2,) * 2)) if rgb.shape[1] > fig.shape[1] else fig
    h = height_of(np.arange(FINE), FINE)[:, None]
    cloth = fig & is_navy(rgb) & (h > CLOTH[0]) & (h < CLOTH[1])
    cloth = ndimage.binary_opening(cloth, iterations=1)
    lum = lightness(rgb)
    sigma = BLUR * FINE
    weight = ndimage.gaussian_filter(cloth.astype(np.float64), sigma)
    smooth = ndimage.gaussian_filter(np.where(cloth, lum, 0.0), sigma) / np.maximum(weight, 1e-6)   # cloth only: no skin or belt bleeding in
    inner = ndimage.binary_erosion(cloth, iterations=int(round(RIM * FINE)))                         # away from the cloth's own border
    gy, gx = np.gradient(smooth)
    slope = np.hypot(gx, gy) * FINE / 100.0          # L* per centimetre
    edges = slope > EDGE
    flat = ~edges
    runs = np.concatenate([run_lengths(flat, inner), run_lengths(flat.T, inner.T)])
    values = smooth[inner]
    if len(values) < 0.002 * FINE * FINE or not len(runs):
        return None
    p10, p90 = np.percentile(values, [10, 90])
    wide = ndimage.gaussian_filter(np.where(cloth, lum, 0.0), 0.03 * FINE) / np.maximum(ndimage.gaussian_filter(cloth.astype(np.float64), 0.03 * FINE), 1e-6)
    if debug:
        pic = np.zeros((*cloth.shape, 3), np.uint8)
        pic[inner] = np.clip(smooth[inner] * 2.55, 0, 255)[:, None]
        pic[inner & edges] = (255, 60, 60)
        Image.fromarray(pic).save(debug)
    return {"pixels": int(inner.sum()), "mean": float(values.mean()), "std": float(values.std()), "range": float(p90 - p10),
            "local": float((smooth - wide)[inner].std()), "slope": float(slope[inner].mean()), "edges": float(edges[inner].mean()),
            "facet": float((runs * runs).sum() / runs.sum() / FINE), "facet_mean": float(runs.mean() / FINE)}


def surface_report(shots, brief, report, debug=None):
    """shots: {'front': ((ref picture, ref outline), (our picture, our outline)), 'back': ...}"""
    out = []
    got = {v: [surface_of(im, m, debug and "%s-%s-%s.png" % (debug, v, who)) for who, (im, m) in zip(("ref", "ours"), pair)] for v, pair in shots.items()}
    missing = ["%s %s" % (who, v) for v, pair in got.items() for who, s in zip(("the reference's", "our"), pair) if s is None]
    if missing:
        report["surface"] = None
        return ["surface ours/ref: n/a (no navy cloth found in %s view)" % ", ".join(missing)]
    if not brief:
        out.append("")
        out.append("surface of the navy cloth (shirt and trousers, heights %.2f-%.2f, skin, belt, gold and shoes left out), 1 px = %.1f mm:" % (*CLOTH, 1000.0 / FINE))
        out.append("  lightness is L* (0 black to 100 white) after a %.0f mm blur; edge = lightness changing faster than %.0f L* per cm;" % (BLUR * 1000, EDGE))
        out.append("  facet = length of the stretch between edges a cloth pixel typically lies in (along rows and columns)")
        out.append("  local std = spread left after taking out shading broader than 3 cm; change = mean lightness change, L* per cm")
        out.append("  view   figure | lightness mean   std  p10-p90  local std  change | edge share | facet cm (plain mean of the stretches)")
        for v, pair in got.items():
            for who, s in zip(("ref", "ours"), pair):
                out.append("  %-6s %-6s |          %5.1f  %5.2f   %5.2f      %5.2f   %5.2f |     %5.1f%% |    %5.2f (%.2f)" % (
                    v, who, s["mean"], s["std"], s["range"], s["local"], s["slope"], s["edges"] * 100, s["facet"] * 100, s["facet_mean"] * 100))
    ratio = {k: float(np.mean([p[1][k] for p in got.values()]) / np.mean([p[0][k] for p in got.values()])) for k in ("std", "range", "local", "slope", "edges", "facet")}
    if not brief:
        out.append("  ours/ref, mean of the views: std %.2f  p10-p90 %.2f  local std %.2f  change %.2f  edge share %.2f  facet %.2f" % tuple(ratio[k] for k in ("std", "range", "local", "slope", "edges", "facet")))
        out.append("  (in the line below spread = std; below 1 = ours is flatter, has fewer edges; facet above 1 = ours has larger unbroken stretches)")
    out.append("surface ours/ref: spread %.2f  edges %.2f  facet %.2f" % (ratio["std"], ratio["edges"], ratio["facet"]))
    report["surface"] = {"views": {v: {"ref": p[0], "ours": p[1]} for v, p in got.items()}, "ratio": {"spread": ratio["std"], **ratio}}
    return out


# ---------------------------------------------------------------------------------------------- main

def plain(o):
    """For JSON: numpy numbers as Python's, not-a-number as null."""
    if isinstance(o, dict):
        return {str(k): plain(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [plain(v) for v in o]
    if isinstance(o, (bool, np.bool_)):
        return bool(o)
    if isinstance(o, (int, np.integer)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        return None if np.isnan(o) else round(float(o), 5)
    return o


def main(argv):
    flags = {"--widths": False, "--surface": False, "--brief": False}
    paths, json_path, debug, sheet_name = [], None, None, None
    it = iter(argv)
    for arg in it:
        if arg in flags:
            flags[arg] = True
        elif arg in ("--json", "--debug"):
            value = next(it, None)
            if value is None:
                sys.exit(arg + " needs a path")
            json_path, debug = (value, debug) if arg == "--json" else (json_path, value)
        elif arg == "--sheet":
            sheet_name = next(it, None)
            if sheet_name not in SHEETS:
                sys.exit("--sheet needs one of: " + ", ".join(SHEETS))
        elif arg.startswith("--"):
            sys.exit("unknown option " + arg + "\n" + __doc__)
        else:
            paths.append(arg)
    if len(paths) < 4:
        sys.exit(__doc__)

    views = ("front", "profile", "back")
    use(sheet_name or sheet_of(paths[0]))
    sheet_picture = Image.open(paths[0])
    sheet = figures(mask_of(sheet_picture), 3)
    tiles, scores, kept = [], [], {}
    for view, ref, path in zip(views, sheet, paths[1:4]):
        picture = Image.open(path)
        ours = figures(mask_of(picture), 1)[0]
        a, b = squared(ref), squared(ours)
        if ENCLOSED:
            a, b = enclosed(a), enclosed(b)
        scores.append((a & b).sum() / (a | b).sum())
        rgb = np.full((*a.shape, 3), 255, np.uint8)
        rgb[a & b] = (150, 150, 150)
        rgb[a & ~b] = (220, 60, 60)
        rgb[~a & b] = (60, 90, 220)
        tiles.append(rgb)
        kept[view] = (a, b, ref, ours, picture)
    print("IoU front %.3f  profile %.3f  back %.3f  mean %.3f" % (*scores, sum(scores) / 3))
    if len(paths) > 4:
        Image.fromarray(np.concatenate(tiles, axis=1)).save(paths[4])

    report = {"sheet": sheet_name or sheet_of(paths[0]), "iou": dict(zip(views, map(float, scores)))}
    if flags["--widths"]:
        a, b, ref, ours, picture = kept["profile"]
        pairs = {"front": kept["front"][:2], "profile": (a, b, squared_colour(sheet_picture, ref), squared_colour(picture, ours))}
        print("\n".join(width_report(pairs, flags["--brief"], report)))
    if flags["--surface"]:
        shots = {v: ((sheet_picture, kept[v][2]), (kept[v][4], kept[v][3])) for v in ("front", "back")}
        print("\n".join(surface_report(shots, flags["--brief"], report, debug)))
    if json_path:
        with open(json_path, "w") as f:
            json.dump(plain(report), f, indent=1)


if __name__ == "__main__":
    main(sys.argv[1:])
