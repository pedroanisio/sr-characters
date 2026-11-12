"""A performed location as plain geometry, frame by frame: what another renderer needs to draw the same film.

    from characters import export
    export.frames(loc, "film", folder, fps=24, seconds=6, size=(1080, 1920))

writes `export.json` (what the film is) and one `NNNN.json` per frame:

    {"frame": 12, "time": 0.5,
     "camera": {"eye": [x, y, z], "look_at": [...], "lens": mm, "focus": metres, "gate": "vertical" | "horizontal"},
     "parts": [{"id": "bear/head/head#1", "figure": "bear", "name": "head/head", "material": "bear.fur",
                "kind": "fur", "pile": 0.0075, "colour": "#B98A5E", "nu": 28, "nv": 18, "verts": [x, y, z, ...]}],
     "props": [{"id": "step-1", "material": "steps.wood", "colour": "#E8CFA4", "verts": [...], "faces": [[...]]}]}

Metres, y up, a figure with yaw 0 facing +z (the SDK's space). A part is a grid of `nu` columns (closed round)
by `nv + 1` rows, row by row. A part's `id` is the same on every frame it exists, so a renderer can keep what it
grew on it (hairs) from frame to frame. `kind` is characters.cloth's. Contact shadows are left out: a renderer
with lights casts its own. `film.Film.export()` calls this.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Optional, Sequence, Union

from srlocations.geometry import Vec3

from . import cloth, fixed, mascots3d

FORMAT = 1
_ENV = {"sin": lambda d: math.sin(math.radians(d)), "cos": lambda d: math.cos(math.radians(d)), "min": min, "max": max,
        "abs": abs, "pow": pow, "sign": lambda v: (v > 0) - (v < 0)}      # what the engine's surface expressions use
_CODES: dict[str, object] = {}
_CORNERS = [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]
_BOX_FACES = [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [2, 3, 7, 6], [1, 2, 6, 5], [0, 4, 7, 3]]


def _code(expr: str):
    if expr not in _CODES:
        _CODES[expr] = compile(expr, "<surface>", "eval")
    return _CODES[expr]


def _drawn(item) -> bool:
    """A part that says where its own facets are (role "drawn", as characters.lowpoly3d.Loft does)."""
    return "drawn" in getattr(item, "role", "").split()


def _grid(item, world, detail: float) -> tuple[int, int, list[float]]:
    """A parametric surface sampled into nu columns by nv + 1 rows, in the location's space. A `drawn` part is
    sampled exactly where it says: its samples are its corners."""
    nu, nv = max(10, round(item.samples[0] * detail)), max(6, round(item.samples[1] * detail))
    if _drawn(item):
        nu, nv = item.samples
    fx, fy, fz = _code(item.x), _code(item.y), _code(item.z)
    verts: list[float] = []
    for j in range(nv + 1):
        v = item.v[0] + (item.v[1] - item.v[0]) * j / nv
        for i in range(nu):
            scope = {**_ENV, "u": item.u[0] + (item.u[1] - item.u[0]) * i / nu, "v": v}
            q = world.apply(Vec3(eval(fx, scope), eval(fy, scope), eval(fz, scope)))
            verts += [round(q.x, 5), round(q.y, 5), round(q.z, 5)]
    return nu, nv, verts


def frame(now, shot: str, detail: float = 1.0) -> dict:
    """One moment of a location (`loc.at(time)`) as parts, props and camera (see the module's text)."""
    colour = lambda name: now.registry.materials.get(name).color   # noqa: E731
    parts, props, heads = [], [], []
    for node in now.nodes:
        if isinstance(node, mascots3d.MascotFigure):
            seen: dict[str, int] = {}
            with fixed.exact():            # each part with its own surface, not the film's fixed list
                leaves = list(node.walk())
            for leaf in leaves:
                item = leaf.item
                if isinstance(item, mascots3d.Contact) or not hasattr(item, "x"):
                    continue
                seen[item.name] = seen.get(item.name, 0) + 1
                kind = cloth.kind(item.material, item.name)
                nu, nv, verts = _grid(item, leaf.world, detail)
                part = {"id": f"{node.name}/{item.name}#{seen[item.name]}", "figure": node.name, "name": item.name,
                        "material": item.material, "kind": kind, "colour": colour(item.material),
                        "nu": nu, "nv": nv, "verts": verts}
                if _drawn(item):
                    part["drawn"] = True
                    for tag in item.role.split():
                        # "facet:80:14": its sides break into facets about 80 mm across and up to 14 mm deep; then,
                        # if it gives them, the width of each of its sides and the length of each of its bands (mm)
                        field = tag.split(":")
                        if field[0] == "facet" and len(field) >= 3:
                            part["facet"] = {"size": float(field[1]) / 1000.0, "depth": float(field[2]) / 1000.0}
                            for key, text in zip(("sides", "bands"), field[3:5]):
                                part["facet"][key] = [float(x) / 1000.0 for x in text.split(",")]
                        elif field[0] == "crease" and len(field) == 2:      # the older tag: a depth alone
                            part["facet"] = {"size": 0.08, "depth": float(field[1]) / 1000.0}
                    if "facet" in part:      # its facets are its character's (who it is), not the actor's name in a film:
                        # the same person breaks the same way in every film, and another person in another way
                        part["facet"]["key"] = f"{node.who}/{item.name}#{seen[item.name]}"
                if kind == "fur":
                    part["pile"] = cloth.pile(item.material)
                parts.append(part)
                if item.name == "head/head":
                    heads.append(leaf.world.apply(Vec3(0, 0, 0)))
            continue
        if not hasattr(node, "walk"):
            continue
        for k, leaf in enumerate(node.walk()):
            item = leaf.item
            if not hasattr(item, "half_extents") or not getattr(item, "material", None):
                continue                                   # lights and skies: the other renderer has its own
            if hasattr(item, "x") and hasattr(item, "samples"):
                nu, nv, verts = _grid(item, leaf.world, detail)
                faces = [[j * nu + i, j * nu + (i + 1) % nu, (j + 1) * nu + (i + 1) % nu, (j + 1) * nu + i]
                         for j in range(nv) for i in range(nu)]
            else:                                          # a box, or anything else as its bounding box
                he = item.half_extents()
                corners = [leaf.world.apply(Vec3(sx * he.x, sy * he.y, sz * he.z)) for sx, sy, sz in _CORNERS]
                verts = [round(c, 5) for q in corners for c in (q.x, q.y, q.z)]
                faces = _BOX_FACES
            props.append({"id": f"{leaf.path}-{k}", "material": item.material, "colour": colour(item.material),
                          "verts": verts, "faces": faces})
    cam = now.shots[shot]
    eye, aim = Vec3.of(cam.eye), Vec3.of(cam.look_at)
    # focus on the head nearest to what the camera looks at (a face), else on what it looks at
    target = min(heads, key=lambda h: (h - aim).length, default=aim)
    focus = max(0.05, (target - eye).length - (0.15 if heads else 0.0))
    return {"camera": {"eye": [eye.x, eye.y, eye.z], "look_at": [aim.x, aim.y, aim.z], "lens": cam.lens,
                       "focus": round(focus, 4)},
            "parts": parts, "props": props}


def frames(loc, shot: str, folder: Union[str, Path], fps: float, seconds: float, size: Sequence[int],
           first: int = 0, last: Optional[int] = None, detail: float = 1.0, name: str = "") -> Path:
    """Writes the location's motion as frames `first`..`last` (default: all) into `folder`. Gives the folder.
    Frames already written are kept, so an interrupted export picks up where it stopped."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    count = int(round(seconds * fps))
    last = count - 1 if last is None else min(last, count - 1)
    width, height = size
    meta = {"format": FORMAT, "name": name, "fps": fps, "frames": count, "size": [width, height], "shot": shot,
            # the engine's gate: a frame narrower than 3:2 takes its field of view from the sensor's height (24 mm)
            "gate": "vertical" if width / height < 1.5 else "horizontal", "kinds": list(cloth.KINDS)}
    (folder / "export.json").write_text(json.dumps(meta, indent=1))
    for k in range(first, last + 1):
        target = folder / f"{k:04d}.json"
        if target.exists():
            continue
        data = {"frame": k, "time": k / fps, **frame(loc.at(k / fps), shot, detail)}
        target.write_text(json.dumps(data, separators=(",", ":")))
    return folder
