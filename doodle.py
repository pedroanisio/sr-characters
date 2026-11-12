"""The `Pose` every character acts with, and the 2D drawing kit (brush ink, boil) the marker style is built on.

A Pose picks eyes, brows, mouth, arms, gaze, tilt and extras; `MOUTHS` is the mouth vocabulary. The 3D models read
it (mascots3d.py, plush3d.py).

The hand-drawn Professor Frog, Chick and Mouse that lived here were removed on 2026-11-11 (the cast is the plush
family); they are in `sr-data/characters_legacy/doodle.py`.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

INK = "#2A2320FF"
CLEAR = "#00000000"
BOIL = 1 / 8

Pt = tuple[float, float]


# ----------------------------------------------------------------------------- curves
def spline(points: list[Pt], closed: bool, per: int = 10) -> list[Pt]:
    """Sample a Catmull-Rom spline through the points."""
    n = len(points)
    get = (lambda i: points[i % n]) if closed else (lambda i: points[max(0, min(n - 1, i))])
    out: list[Pt] = []
    for i in range(n if closed else n - 1):
        p0, p1, p2, p3 = get(i - 1), get(i), get(i + 1), get(i + 2)
        for s in range(per):
            t = s / per
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2
                                    + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3) for k in (0, 1)))
    if not closed:
        out.append(points[-1])
    return out


def ellipse(cx, cy, rx, ry, rng: random.Random, amp=0.03, n=14) -> list[Pt]:
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        k = 1 + rng.uniform(-amp, amp)
        pts.append((cx + rx * k * math.cos(a), cy + ry * k * math.sin(a)))
    return pts


def jitter(points: list[Pt], rng: random.Random, amp: float) -> list[Pt]:
    return [(x + rng.uniform(-amp, amp), y + rng.uniform(-amp, amp)) for x, y in points]


def _f(v: float) -> str:
    return f"{v:.1f}"


def poly_path(pts: list[Pt]) -> str:
    return "M" + " L".join(f"{_f(x)} {_f(y)}" for x, y in pts) + " Z"


def _wobble(rng: random.Random):
    a1, a2, p1, p2 = rng.uniform(0.1, 0.22), rng.uniform(0.05, 0.12), rng.uniform(0, 6.3), rng.uniform(0, 6.3)
    return lambda t: 1 + a1 * math.sin(2 * math.pi * 2 * t + p1) + a2 * math.sin(2 * math.pi * 5 * t + p2)


LIGHT = (0.45, 0.89)  # direction of the shadow side (down, a little right): ink is heavier there


def ring(points: list[Pt], width: float, rng: random.Random) -> str:
    """A closed brush outline: a filled band around the curve, heavier on the shadow side (fill-rule evenodd)."""
    curve = spline(points, closed=True, per=8)
    n = len(curve)
    cx = sum(p[0] for p in curve) / n
    cy = sum(p[1] for p in curve) / n
    wob = _wobble(rng)
    outer, inner = [], []
    for i, (x, y) in enumerate(curve):
        tx = curve[(i + 1) % n][0] - curve[i - 1][0]
        ty = curve[(i + 1) % n][1] - curve[i - 1][1]
        ln = math.hypot(tx, ty) or 1
        nx, ny = ty / ln, -tx / ln
        if nx * (x - cx) + ny * (y - cy) < 0:
            nx, ny = -nx, -ny
        w = width * wob(i / n) * (0.75 + 0.6 * max(0.0, nx * LIGHT[0] + ny * LIGHT[1]))
        outer.append((x + nx * w / 2, y + ny * w / 2))
        inner.append((x - nx * w / 2, y - ny * w / 2))
    return poly_path(outer) + " " + poly_path(list(reversed(inner)))


def stroke(points: list[Pt], width: float, rng: random.Random, taper: float = 0.7) -> str:
    """An open brush stroke: a filled ribbon, tapered at both ends."""
    curve = spline(points, closed=False, per=8)
    n = len(curve)
    wob = _wobble(rng)
    left, right = [], []
    for i, (x, y) in enumerate(curve):
        a, b = curve[max(0, i - 1)], curve[min(n - 1, i + 1)]
        tx, ty = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(tx, ty) or 1
        nx, ny = ty / ln, -tx / ln
        t = i / (n - 1)
        w = width * wob(t) * ((1 - taper) + taper * math.sin(math.pi * t) ** 0.7)
        left.append((x + nx * w / 2, y + ny * w / 2))
        right.append((x - nx * w / 2, y - ny * w / 2))
    return poly_path(left + list(reversed(right)))


def filled(points: list[Pt]) -> str:
    return poly_path(spline(points, closed=True, per=8))


# ----------------------------------------------------------------------------- pose
from .expression import MOUTHS, Pose  # noqa: E402,F401  (they moved to expression.py; the old import path stays)


# ----------------------------------------------------------------------------- the kit
class Kit:
    """Draws into one group. Every shape boils between three seeded variants.
    The character code takes its ellipses from the kit (`k.ellipse`), so a style can change silhouettes."""

    ellipse = staticmethod(ellipse)

    def __init__(self, parent, prefix: str, seed: int):
        self.parent, self.prefix, self.seed, self.n = parent, prefix, seed, 0

    def shape(self, draw, fill: str, evenodd: bool = False, name: str = "s"):
        self.n += 1
        variants = [draw(random.Random(self.seed * 1009 + self.n * 31 + v)) for v in range(3)]
        sh = self.parent.add_shape(id=f"{self.prefix}{name}-{self.n}", shape="path", path=variants[0], fill=fill,
                                   width=1080, height=1920, **({"fillRule": "evenodd"} if evenodd else {}))
        anim = sh.add_animate(property="path", defaultInterpolation="hold", extrapolateAfter="loop")
        for i, d in enumerate(variants + [variants[0]]):
            anim.add_key(time=round(i * BOIL, 4), value=d)
        return sh

    # a shaded, inked volume: dark crescent, lit fill shifted up-left, brush outline
    def volume(self, pts_fn, light: str, dark: str, ink=7.5, shade=0.9, name="vol"):
        self.shape(lambda r: filled(pts_fn(r)), dark, name=name + "-dark")
        if shade:
            def lit(r):
                pts = pts_fn(r)
                cx = sum(p[0] for p in pts) / len(pts)
                cy = sum(p[1] for p in pts) / len(pts)
                return filled([(cx + (x - cx) * 0.9 - 9 * shade, cy + (y - cy) * 0.9 - 11 * shade) for x, y in pts])
            self.shape(lit, light, name=name + "-lit")
        if ink:
            self.shape(lambda r: ring(pts_fn(r), ink, r), INK, evenodd=True, name=name + "-ink")

    def line(self, pts: list[Pt], width=7.0, color=INK, amp=2.0, taper=0.7, name="ln"):
        self.shape(lambda r: stroke(jitter(pts, r, amp), width, r, taper), color, name=name)

    def blob(self, cx, cy, rx, ry, color, amp=0.04, name="dot"):
        self.shape(lambda r: filled(self.ellipse(cx, cy, rx, ry, r, amp)), color, name=name)


# ----------------------------------------------------------------------------- shared face parts
def eyes_on(k: Kit, centers: list[Pt], r: float, pose: Pose, lid_color: str, white: bool):
    lx, ly = pose.look
    for i, (x, y) in enumerate(centers):
        if pose.eyes == "closed":   # calm closed: a soft downward arc
            k.line([(x - r * 0.9, y), (x, y + r * 0.35), (x + r * 0.9, y)], width=6.5, name="lid")
            continue
        if pose.eyes == "squint":   # > <
            s = -1 if i == 0 else 1
            k.line([(x - s * r * 0.7, y - r * 0.6), (x + s * r * 0.5, y), (x - s * r * 0.7, y + r * 0.6)], width=6.5,
                   taper=0.4, name="squint")
            continue
        if pose.eyes == "spiral":
            pts = [(x + r * 0.85 * (j / 18) * math.cos(j * 0.8), y + r * 0.85 * (j / 18) * math.sin(j * 0.8))
                   for j in range(19)]
            k.line(pts, width=5.0, taper=0.3, name="spiral")
            continue
        size = r * (1.25 if pose.eyes == "wide" else 1.0)
        if white:
            k.volume(lambda rng, x=x, y=y: k.ellipse(x, y, size, size * 1.05, rng, 0.03), "#FFFDF5FF", "#E9E4D6FF",
                     ink=5.5, shade=0.4, name="white")
            pr = size * (0.32 if pose.eyes == "wide" else 0.42)
            px, py = x + lx * size * 0.45 + (6 if pose.eyes == "side" else 0), y + ly * size * 0.35
        else:
            pr = size * (0.55 if pose.eyes == "wide" else 0.5)
            px, py = x + lx * 6, y + ly * 5
        k.blob(px, py, pr, pr * 1.08, INK, name="pupil")
        k.blob(px - pr * 0.35, py - pr * 0.4, pr * 0.3, pr * 0.3, "#FFFFFFFF", name="shine")
        if pose.eyes == "half":  # heavy upper lid: a fill over the top half, inked lid line
            top = y - size * 0.05
            k.shape(lambda rng, x=x: filled(jitter([(x - size * 1.05, top), (x - size * 0.7, y - size * 1.05),
                                                     (x + size * 0.7, y - size * 1.05), (x + size * 1.05, top)], rng, 1.5)),
                    lid_color, name="lidfill")
            k.line([(x - size * 1.05, top + 2), (x, top - 4), (x + size * 1.05, top + 2)], width=7, taper=0.3,
                   name="lidline")


def brows_on(k: Kit, centers: list[Pt], r: float, pose: Pose, lift: float):
    if pose.brows == "none":
        return
    for i, (x, y) in enumerate(centers):
        s = -1 if i == 0 else 1          # -1 left eye, +1 right eye
        by = y - r - lift
        inner_dy, outer_dy = {"flat": (0, 0), "raised": (-10, -6), "worried": (-14, 6), "angry": (12, -8),
                              "skeptic": ((-16, -12) if i == 1 else (4, 4)),
                              "arched": ((-12, -8) if i == 1 else (0, 0))}[pose.brows]
        pts = [(x - s * r * 0.15, by + inner_dy), (x + s * r * 0.45, by - 6 + (inner_dy + outer_dy) / 2),
               (x + s * r * 0.95, by + outer_dy)]
        k.line(pts, width=11, taper=0.8, name="brow")


def extras_on(k: Kit, pose: Pose, head_top: Pt, side_x: float):
    hx, hy = head_top
    if "question" in pose.extras:
        k.line([(hx + 60, hy - 95), (hx + 75, hy - 130), (hx + 105, hy - 135), (hx + 120, hy - 110),
                (hx + 100, hy - 80), (hx + 92, hy - 55)], width=12, taper=0.5, name="q")
        k.blob(hx + 92, hy - 28, 9, 9, INK, name="qdot")
    if "sparkle" in pose.extras:
        for dx, dy, s in ((side_x, hy + 10, 1.0), (side_x + 40, hy + 60, 0.6)):
            pts = [(dx, dy - 26 * s), (dx + 6 * s, dy - 6 * s), (dx + 26 * s, dy), (dx + 6 * s, dy + 6 * s), (dx, dy + 26 * s),
                   (dx - 6 * s, dy + 6 * s), (dx - 26 * s, dy), (dx - 6 * s, dy - 6 * s)]
            k.shape(lambda rng, pts=pts: poly_path(jitter(pts, rng, 1.2)), "#F2C14EFF", name="spark")
    if "sweat" in pose.extras:
        for i, (dx, dy) in enumerate(((side_x - 40, hy + 40), (side_x + 10, hy + 110))):
            k.volume(lambda rng, dx=dx, dy=dy: [(dx, dy - 30), (dx + 16, dy + 2), (dx, dy + 18), (dx - 16, dy + 2)],
                     "#A8DBF5FF", "#79BFE6FF", ink=4.5, shade=0.4, name="sweat")



def add_texture_effects(scene, seed: int = 11):
    """Declare the crayon grain and the hand-drawn edge wobble once; groups use them by id."""
    fx = scene.add_effects()
    fx.add_effect(id="crayon-grain", type="noise", amount=0.11)
    fx.add_effect(id="hand-wobble", type="turbulent-displace", amount=2.2, size=36, seed=seed)
    return "hand-wobble crayon-grain"



# ----------------------------------------------------------------------------- Mouse, the full character
MOUSE_BELLY, MOUSE_BELLY_DARK, MOUSE_FOOT_DARK = "#E8E4DFFF", "#D2CCC5FF", "#D99490FF"



