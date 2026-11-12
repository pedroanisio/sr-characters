"""Doodle kit v4 ("marker"): felt-tip pen and coloured pencil on paper, the finish of the reference Reel.

The characters, poses and geometry are doodle.py's; only how they are put on paper changes:

- pen: outlines are a felt-tip line of near-constant width; a closed outline starts anywhere, and either stops
  short of where it began or runs a little past it, as a hand-drawn line does;
- colour: each volume is coloured in with pencil (shaders/pencil.glsl): strokes, paper tooth, uneven pressure,
  and the colour stops short of the outline. Bellies and eye whites stay paper;
- paper: every volume first gets an opaque paper underfill, so what is behind it is hidden even where the pencil
  leaves the paper bare. The photographed-paper light and fibres go over the whole frame (paper.py);
- shape: ellipses get a fixed, lumpy, off-model silhouette per shape (the same in every boil variant);
- no vector-illustration extras: no crescent shading, no blush, no sparkles.
"""

from __future__ import annotations

import math
import os
import random
import re
import zlib
from pathlib import Path

from . import doodle
from .doodle import Kit, Pt, filled, jitter, poly_path, spline

OLD_INK = doodle.INK
PEN = "#1C1B1AFF"
PAPER = "#F7F6F1FF"
SHADER = Path(__file__).resolve().parent / "shaders" / "pencil.glsl"

# old paint -> (how it is put down, colour). pencil: coloured pencil; marker: an even felt-tip fill;
# paper: left uncoloured; skip: not drawn at all.
PAINT = {
    # Professor Frog
    "#93C46FFF": ("pencil", "#74AD45FF"), "#6E9F55FF": ("pencil", "#4F8636FF"),
    "#E1ECB9FF": ("paper", None), "#C7D89BFF": ("paper", None),
    "#B9474AFF": ("marker", "#B8423FFF"), "#8E3236FF": ("marker", "#7E2A2AFF"), "#E58C8CFF": ("marker", "#E58A84FF"),
    "#EBA79AFF": ("skip", None),
    # eyes, pointer
    "#FFFDF5FF": ("paper", None), "#E9E4D6FF": ("paper", None), "#FFFFFFFF": ("paper", None),
    "#B07A45FF": ("marker", "#9C6A3CFF"), "#F3F0E6FF": ("paper", None),
    # Chick
    "#F9D252FF": ("pencil", "#FFD43AFF"), "#E0AE2CFF": ("pencil", "#F0B020FF"),
    "#EE8A32FF": ("marker", "#E8862EFF"), "#C96A1EFF": ("marker", "#C96A1EFF"), "#F2A28AFF": ("skip", None),
    # extras
    "#F2C14EFF": ("marker", "#EDB93AFF"), "#A8DBF5FF": ("pencil", "#7FC0E8FF"), "#79BFE6FF": ("pencil", "#5FA8D8FF"),
    # Mouse
    "#B5B0ABFF": ("pencil", "#9E9A95FF"), "#8F8A85FF": ("pencil", "#85807BFF"), "#F2B4B0FF": ("pencil", "#EE9C98FF"),
    "#C8443AFF": ("pencil", "#C8443AFF"), "#9A2F28FF": ("pencil", "#9A2F28FF"), "#C46D6DFF": ("marker", "#C46D6DFF"),
    "#E8E4DFFF": ("paper", None), "#D2CCC5FF": ("paper", None), "#D99490FF": ("pencil", "#D98682FF"),
    # Dev
    "#2B2522FF": ("marker", "#231E1BFF"), "#1E1916FF": ("marker", "#1E1916FF"), "#E9782FFF": ("marker", "#E9782FFF"),
    "#2E2E33FF": ("marker", "#2A2A2FFF"), "#4A4A52FF": ("marker", "#55555EFF"), "#2C3048FF": ("marker", "#2C3048FF"),
    "#E2A574FF": ("pencil", "#E7A06AFF"), "#C98852FF": ("pencil", "#C98852FF"), "#4F63A3FF": ("pencil", "#4A5FA6FF"),
    "#3C4E86FF": ("pencil", "#3C4E86FF"), "#B84A30FF": ("pencil", "#BE4A2EFF"), "#943A25FF": ("pencil", "#943A25FF"),
    "#A3A3ADFF": ("pencil", "#9A9AA6FF"), "#82828CFF": ("pencil", "#82828CFF"),
}

# fills that reach the outline (dark marker areas: a paper gap inside them reads as a halo)
TIGHT = {"#2B2522FF", "#1E1916FF", "#2E2E33FF", "#2C3048FF"}

# pencil effect variants (angle of the strokes, seed): a hand does not colour every shape at the same angle
PENCILS = [("pencil-a", 1.05, 1.0), ("pencil-b", 0.85, 2.0), ("pencil-c", 1.25, 3.0), ("pencil-d", 0.95, 4.0)]


def add_effects(fx, scene_dir: str | Path, seed: int = 11) -> str:
    """Declare the pencil, marker and hand-wobble effects in the scene's <effects>; returns the effects a character
    group uses. `scene_dir` is where the scene XML will be written: the shader path is made relative to it."""
    src = os.path.relpath(SHADER, Path(scene_dir).resolve())
    for eid, angle, s in PENCILS:
        e = fx.add_effect(id=eid, type="shader", src=src)
        for k, v in (("angle", angle), ("spacing", 3.0), ("density", 0.66), ("tooth", 1.0), ("seed", s)):
            e.add_param(name=k, value=str(v))
    e = fx.add_effect(id="marker", type="shader", src=src)
    for k, v in (("angle", 0.9), ("spacing", 5.0), ("density", 0.95), ("tooth", 0.25), ("seed", 9.0)):
        e.add_param(name=k, value=str(v))
    fx.add_effect(id="hand-wobble", type="turbulent-displace", amount=1.6, size=40, seed=seed)
    return "hand-wobble"


# ----------------------------------------------------------------------------- off-model silhouettes
def _key(*vals: float) -> int:
    return zlib.crc32(",".join(f"{v:.0f}" for v in vals).encode())


def lumpy_ellipse(cx, cy, rx, ry, rng: random.Random, amp=0.03, n=14) -> list[Pt]:
    """doodle.ellipse with a fixed lumpy silhouette per shape (same in every boil variant) and a smaller boil."""
    h = random.Random(_key(cx, cy, rx, ry))
    a2, a3, p2, p3 = h.uniform(0.03, 0.06), h.uniform(0.02, 0.04), h.uniform(0, 6.3), h.uniform(0, 6.3)
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        k = 1 + a2 * math.sin(2 * a + p2) + a3 * math.sin(3 * a + p3) + rng.uniform(-amp, amp) * 0.5
        pts.append((cx + rx * k * math.cos(a), cy + ry * k * math.sin(a)))
    return pts



# ----------------------------------------------------------------------------- pen
def _ribbon(curve: list[Pt], width: float, rng: random.Random, cap: int = 4) -> str:
    """A felt-tip line along the polyline: width varies by about 10 %, the ends round off over `cap` samples."""
    n = len(curve)
    ph = rng.uniform(0, 6.3)
    left, right = [], []
    for i, (x, y) in enumerate(curve):
        a, b = curve[max(0, i - 1)], curve[min(n - 1, i + 1)]
        tx, ty = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(tx, ty) or 1
        nx, ny = ty / ln, -tx / ln
        t = i / max(1, n - 1)
        end = min(1.0, (min(i, n - 1 - i) + 0.6) / cap) ** 0.5
        w = width * (1 + 0.1 * math.sin(2 * math.pi * 3 * t + ph)) * end
        left.append((x + nx * w / 2, y + ny * w / 2))
        right.append((x - nx * w / 2, y - ny * w / 2))
    return poly_path(left + list(reversed(right)))


def pen_ring(points: list[Pt], width: float, rng: random.Random) -> str:
    """A closed outline drawn in one go: it starts anywhere and stops short or runs a little past the start."""
    curve = spline(points, closed=True, per=8)
    n = len(curve)
    s = rng.randrange(n)
    curve = curve[s:] + curve[:s]
    cx, cy = sum(p[0] for p in curve) / n, sum(p[1] for p in curve) / n
    ext = int(n * rng.uniform(-0.035, 0.07))
    if ext < 0:
        curve = curve[:n + ext]
    else:  # the overshoot drifts outward, so the line does not meet itself exactly
        tail = []
        for j, (x, y) in enumerate(curve[:ext + 1]):
            d = math.hypot(x - cx, y - cy) or 1
            o = width * 0.5 * (j / max(1, ext))
            tail.append((x + (x - cx) / d * o, y + (y - cy) / d * o))
        curve = curve + tail
    return _ribbon(curve, width, rng)


def pen_width(w: float) -> float:
    """doodle's brush widths -> a felt-tip pen: nearly the same width for every line."""
    return 7.5 + 0.25 * w


def inset(points: list[Pt], rng: random.Random, d: float) -> list[Pt]:
    """The area the pencil covers: pulled in from the outline (more in some places), a little off-register."""
    n = len(points)
    cx, cy = sum(p[0] for p in points) / n, sum(p[1] for p in points) / n
    r = min(math.hypot(x - cx, y - cy) for x, y in points) or 1
    d = min(d, r * 0.3)
    ox, oy = rng.uniform(-0.4, 0.4) * d, rng.uniform(-0.4, 0.4) * d
    out = []
    for x, y in points:
        L = math.hypot(x - cx, y - cy) or 1
        k = d * rng.uniform(0.6, 1.4)
        out.append((x - (x - cx) / L * k + ox, y - (y - cy) / L * k + oy))
    return out


# ----------------------------------------------------------------------------- the kit
_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def _tighten(variants: list[str], pad: float = 4.0) -> tuple[list[str], dict]:
    """Move path data (absolute M/L/Z only, as this kit writes it) so its bounding box starts at (pad, pad);
    return the moved paths and the shape attributes (x, y, width, height) that put it back where it was."""
    nums = [[float(v) for v in _NUM.findall(d)] for d in variants]
    xs = [v for n in nums for v in n[0::2]]
    ys = [v for n in nums for v in n[1::2]]
    ox, oy = math.floor(min(xs) - pad), math.floor(min(ys) - pad)
    moved = []
    for d in variants:
        it = iter(range(10 ** 9))
        moved.append(_NUM.sub(lambda m_: f"{float(m_.group()) - (ox if next(it) % 2 == 0 else oy):.1f}", d))
    return moved, {"x": ox, "y": oy, "width": math.ceil(max(xs) - ox + pad), "height": math.ceil(max(ys) - oy + pad)}


class MarkerKit(Kit):
    """Same interface as doodle.Kit; draws with pen, pencil and paper.
    `tight` (rigged characters): every shape gets a box around its own drawing instead of the whole frame, so its
    pencil pass is small. Moving joints re-render those passes every frame; frame-sized ones ran the GPU out of
    memory. Mascots keep frame-sized boxes, so their scenes stay exactly as they were."""

    tight = False

    ellipse = staticmethod(lumpy_ellipse)

    def _boil(self, draw, fill: str, key: int, name: str, evenodd=False, effects: str | None = None):
        """One boiling shape. Shapes drawn with the same `key` get the same random numbers in each variant."""
        self.n += 1
        variants = [draw(random.Random(self.seed * 1009 + key * 31 + v)) for v in range(3)]
        attrs = {"fillRule": "evenodd"} if evenodd else {}
        if effects:
            attrs["effects"] = effects
        box = {"width": 1080, "height": 1920}
        if self.tight:  # the shape's box around its own drawing (its effect pass covers only that)
            variants, box = _tighten(variants)
        sh = self.parent.add_shape(id=f"{self.prefix}{name}-{self.n}", shape="path", path=variants[0], fill=fill,
                                   **box, **attrs)
        anim = sh.add_animate(property="path", defaultInterpolation="hold", extrapolateAfter="loop")
        for i, d in enumerate(variants + [variants[0]]):
            anim.add_key(time=round(i * doodle.BOIL, 4), value=d)
        return sh

    def _colour(self, draw, colour: str, key: int, name: str):
        kind, col = PAINT.get(colour, ("pencil", colour))
        if kind in ("paper", "skip"):
            return
        fx = "marker" if kind == "marker" else PENCILS[key % len(PENCILS)][0]
        self._boil(draw, col, key, name + "-" + kind, effects=fx)

    def shape(self, draw, fill: str, evenodd: bool = False, name: str = "s"):
        key = self.n + 1
        if name == "spark":
            return None
        if fill == OLD_INK:
            return self._boil(draw, PEN, key, name, evenodd=evenodd)
        if PAINT.get(fill, ("pencil",))[0] == "skip":
            return None
        self._boil(draw, PAPER, key, name + "-paper", evenodd=evenodd)
        self._colour(draw, fill, key, name)
        return None

    def volume(self, pts_fn, light: str, dark: str, ink=7.5, shade=0.9, name="vol"):
        if PAINT.get(light, ("pencil",))[0] == "skip":
            return
        key = self.n + 1
        self._boil(lambda r: filled(pts_fn(r)), PAPER, key, name + "-paper")
        self._colour(lambda r: filled(inset(pts_fn(r), r, 2.0 if light in TIGHT else 9.0)), light, key, name)
        if ink:
            self._boil(lambda r: pen_ring(pts_fn(r), pen_width(ink), r), PEN, key, name + "-ink")

    def line(self, pts: list[Pt], width=7.0, color=OLD_INK, amp=2.0, taper=0.7, name="ln"):
        key = self.n + 1
        if color == OLD_INK:
            # wide ones are outlines drawn as strokes (arms); small details (spiral eyes, "fine-" lines such as
            # whiskers) stay fine enough to read
            fine = name == "spiral" or name.startswith("fine")
            w = width if width > 15 else (4.5 if fine else pen_width(width))
            self._boil(lambda r: _ribbon(spline(jitter(pts, r, amp), False, 8), w, r), PEN, key, name)
            return
        if name.endswith("-fill"):    # the inside of an arm: paper
            self._boil(lambda r: doodle.stroke(jitter(pts, r, amp), width, r, taper), PAPER, key, name)
            return
        kind, col = PAINT.get(color, ("marker", color))
        if kind == "skip":
            return
        if width >= 20:               # a coloured-in arm: pencil, narrower than its paper
            self._colour(lambda r: doodle.stroke(jitter(pts, r, amp), width * 0.8, r, taper), color, key, name)
        else:                         # thin coloured lines (legs, pointer, trim): marker
            self._boil(lambda r: doodle.stroke(jitter(pts, r, amp), width, r, taper), col, key, name)

    def blob(self, cx, cy, rx, ry, color, amp=0.04, name="dot"):
        key = self.n + 1
        draw = lambda r: filled(self.ellipse(cx, cy, rx, ry, r, amp))  # noqa: E731
        if color == OLD_INK:
            self._boil(draw, PEN, key, name)
            return
        kind, col = PAINT.get(color, ("pencil", color))
        if kind == "skip":
            return
        if kind == "paper":
            self._boil(draw, PAPER, key, name)
            return
        if name == "spot":            # pencil patches straight on the coloured body, no paper under them
            self._colour(draw, color, key, name)
            return
        self._boil(draw, PAPER, key, name + "-paper")
        self._colour(draw, color, key, name)
