"""The kit every family is drawn with: vectors, tubes and blocks, the pencil-and-ink look, the paper finish, the
stage, a still.

- `unit`, `cross`, `scaled`, `basis`: the little vector algebra the models use.
- `tube()`: a tapered tube between two points (limbs); `shape()`: a surface between an egg, a cylinder and a
  soft-cornered block (hard-surface parts).
- `PencilFlat`, `InkByMaterial`, `look()`: the paper look's passes. `finish()`: the photographed-paper finish over
  a compiled scene. `stage()`: a location lit for the look. `render()`: a still. `grid()`: labelled tiles (sheets).

This was `dev3d.py`, Dev's model, the first 3D character; Dev was removed on 2026-11-11 and what stayed was the
kit, so it got its own name. `dev3d` still imports everything from here, under the old names too.
"""


from __future__ import annotations

import math
import random
import subprocess
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Mapping, Optional, Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "characters"

from srlocations import Location, Material, Registry, Renderer, Sky, Styled, Sun  # noqa: E402
from srlocations.geometry import Transform, Vec3, rotation  # noqa: E402
from srlocations.looks import Flat, Ink, Look, Stage  # noqa: E402
from srlocations.nodes import Box  # noqa: E402
from srlocations.stock.mannequin import BY_NAME, KINDS, RELAXED, Build, Limb, Mannequin, _egg, both, curled  # noqa: E402
from srlocations.stock.mannequin import PoseError  # noqa: E402

from . import paper  # noqa: E402
from .doodle import MOUTHS, Pose  # noqa: E402
from .marker import SHADER  # noqa: E402
from .poses import POSES  # noqa: E402

ROOT = Path(__file__).resolve().parent
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# ----------------------------------------------------------------------------- body and colours

COLOURS = {  # material -> colour (the flat colour the pencil lays down); the names the plush models still use
    "dev.skin": "#E7A06A", "dev.ink": "#1C1B1A", "dev.white": "#FBFAF5", "dev.sweat": "#7FC0E8",
}


def register(registry: Registry) -> None:
    for name, colour in COLOURS.items():
        registry.materials.add(name, Material(colour), override=True)


# ----------------------------------------------------------------------------- shapes along bones
def unit(v: Vec3) -> Vec3:
    n = v.length or 1.0
    return Vec3(v.x / n, v.y / n, v.z / n)


def cross(a: Vec3, b: Vec3) -> Vec3:
    return Vec3(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x)


def scaled(v: Vec3, k: float) -> Vec3:
    return Vec3(v.x * k, v.y * k, v.z * k)


def basis(axis: Vec3, ref: Vec3):
    """A rotation whose x is `axis` and whose y is as near `ref` as it can be (z completes it)."""
    x = unit(axis)
    d = ref.x * x.x + ref.y * x.y + ref.z * x.z
    r = Vec3(ref.x - x.x * d, ref.y - x.y * d, ref.z - x.z * d)
    if r.length < 1e-6:
        r = Vec3(0, 0, 1) if abs(x.y) > 0.9 else Vec3(0, 1, 0)
    y = unit(r)
    z = cross(x, y)
    return ((x.x, y.x, z.x), (x.y, y.y, z.y), (x.z, y.z, z.z))


def _n(v: float) -> str:
    return f"{v:.5f}"


def tube(name: str, a: Vec3, b: Vec3, r0: float, r1: float, material: str, ref: Vec3 = Vec3(0, 0, 1),
         cap0: Optional[float] = None, cap1: Optional[float] = None, wide: float = 1.0, deep: float = 1.0,
         looks: Sequence[str] = (), samples=(22, 27)) -> Limb:
    """A tapered tube from a to b, radius r0 to r1, rounded at each end (a cap as long as its radius unless `cap0` or
    `cap1` says), its cross-section `wide` along `ref` and `deep` across. Tubes of one material and group overlap at a
    joint into one smooth limb, which is what an egg per bone could not do."""
    L = (b - a).length
    c0, c1 = r0 if cap0 is None else cap0, r1 if cap1 is None else cap1
    va, vb, vc = "min(v,1)", "min(max(v-1,0),1)", "max(v-2,0)"
    x = f"{_n(c0)}*sin(-90+90*{va})+{_n(L)}*{vb}+{_n(c1)}*sin(90*{vc})-{_n(L / 2)}"
    rho = f"({_n(r0)}*cos(-90+90*{va})+{_n(r1 - r0)}*{vb}+{_n(r1)}*cos(90*{vc})-{_n(r1)})"
    big = max(r0, r1)
    return Limb(x=x, y=f"{rho}*{_n(wide)}*cos(u)", z=f"{rho}*{_n(deep)}*sin(u)", u=(0, 360), v=(0, 3),
                samples=samples, closed=(True, False), radii=(L / 2 + max(c0, c1), big * wide, big * deep),
                at=scaled(a + b, 0.5), basis=basis(b - a, ref), name=name, material=material, casts_shadow=False,
                looks=looks, inward=True)  # this parametrisation winds the other way from an egg: outward faces


# ----------------------------------------------------------------------------- poses: the shared vocabulary

# ----------------------------------------------------------------------------- the model

# ----------------------------------------------------------------------------- the look: pencil and pen on paper
@dataclass
class PencilFlat(Flat):
    """Flat colour laid down through the pencil shader, in ONE group: separate groups each draw their 3D with their own
    depth, so a second group's face showed through the back of the head. The shader puts dark colours (hair, ink,
    headphones) down as marker and light ones as pencil (`bydark`)."""

    def add(self, stage: Stage) -> None:
        e = stage.effects.add_effect(id="pencil-3d", type="shader", src=str(SHADER))
        for k, v in dict(angle=1.05, spacing=3.0, density=0.72, tooth=1.0, seed=1.0, bydark=1.0).items():
            e.add_param(name=k, value=str(v))
        group = stage.group("flat", ["pencil-3d"])

        def paint(skin, leaf):
            material = stage.material_of(skin.name, skin.own, leaf)
            color = self.color(skin.name, material, leaf)
            return f"flat-{skin.name.replace('.', '-')}{stage.aimed(leaf)}", {"baseColor": color, "unlit": True}, None

        for index, leaf in enumerate(stage.solids):
            stage.coat(group, leaf, index, "flat-", paint, False)


@dataclass
class InkByMaterial(Ink):
    """Ink between materials, not between bones: all of one figure's skin is one surface, so a line falls where skin
    meets shirt or hair, and round the outline, but not at every joint of the skeleton under it."""

    def surfaces(self, stage: Stage):
        out = []
        for leaf, key in super().surfaces(stage):
            if isinstance(leaf.item, Limb):
                key = f"{leaf.path.split('/')[0]}|{leaf.item.material}|{leaf.item.name.split('/')[0]}"
            out.append((leaf, key))
        return out


def look() -> Look:
    return Look([PencilFlat(), InkByMaterial(color="#1C1B1A", width=4.5, vary=0.25, wobble=0.9)],
                sky=paper.marker.PAPER[:7], name="dev.paper")


def finish(scene, width: int, height: int) -> None:
    """The photographed-paper finish of characters/paper.py over a compiled srlocations scene."""
    comp = scene.find("composition")
    assets = scene.find("assets") or scene.add_assets()
    paints = scene.find("paints") or scene.add_paints()
    g = paints.add_linearGradient(id="photo-light", units="object", x1=0, y1=0, x2=0, y2=1)
    for off, col in paper.LIGHT_STOPS:
        g.add_stop(offset=off, color=col)
    r = paints.add_radialGradient(id="photo-falloff", units="object")
    for off, col in ((0.0, "#FFFFFFFF"), (0.45, "#FFFFFFFF"), (1.0, "#F4F4F0FF")):
        r.add_stop(offset=off, color=col)
    fx = scene.find("effects") or scene.add_effects()
    fx.add_effect(id="cam-soft", type="blur", radius=0.7)
    fx.add_effect(id="cam-grain", type="film-grain", amount=0.035, size=1.6, seed=5)
    paper.photograph(assets, comp, width, height, camera_id="photo-camera")


# ----------------------------------------------------------------------------- renders
def stage(name: str, registry: Optional[Registry] = None) -> Location:
    registry = registry or Registry.default()
    register(registry)
    loc = Location(name, registry)
    loc.background = paper.marker.PAPER[:7]
    loc.nodes.extend([Sky(1.0, zenith="#ffffff", horizon="#ffffff", ground="#ffffff"), Sun(2.0, yaw=-30, pitch=-50)])
    return loc


def render(loc: Location, shot: str, out: Path, width: int, height: int, look_: Optional[Look] = None) -> Path:
    """A still of `shot`, drawn by `look_` (default: this look) on the photographed paper."""
    renderer = Renderer(collisions=False)
    scene = renderer.compile(loc, shot, Styled(look_ or look(), width=width, height=height))
    finish(scene, width, height)
    return renderer.still(scene, out)


# yaw that shows each view to a camera on +z, measured one figure at a time at the origin (0 faces the camera)
VIEWS = (("front", 0), ("three-quarter right", 315), ("profile right", 270), ("back", 180), ("profile left", 90),
         ("three-quarter left", 45))
FRONT = 0



def grid(tiles: list[tuple[str, Path]], cols: int, out: Path, title: str) -> Path:
    """Labelled tiles in a grid, a title on top, written to `out` (ffmpeg)."""
    inputs = [a for _label, t in tiles for a in ("-i", str(t))]
    lab = ";".join(f"[{i}]drawtext=fontfile={FONT}:text='{label}':x=(w-tw)/2:y=h-44:fontsize=28:fontcolor=0x141414[t{i}]"
                   for i, (label, _t) in enumerate(tiles))
    rows, n = [], len(tiles)
    blank = "color=c=0xF1F0EA:s={w}x{h}"
    for r in range(0, n, cols):
        row = [f"[t{i}]" for i in range(r, min(r + cols, n))]
        rows.append(row)
    graph = lab
    for k, row in enumerate(rows):
        if len(row) < cols:  # pad the last row so every row has the same width
            for j in range(cols - len(row)):
                graph += f";[t{rows[0][0][2:-1]}]drawbox=c=0xF1F0EA:t=fill[pad{k}_{j}]"
                row = row + [f"[pad{k}_{j}]"]
        graph += ";" + "".join(row) + (f"hstack={cols}" if cols > 1 else "null") + f"[r{k}]"
    graph += ";" + "".join(f"[r{k}]" for k in range(len(rows))) + (f"vstack={len(rows)}" if len(rows) > 1 else "null")
    graph += f",pad=iw:ih+90:0:90:color=0xF1F0EA,drawtext=fontfile={FONT}:text='{title}':x=40:y=28:fontsize=44:fontcolor=0x141414"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", graph, str(out)], check=True)
    return out





def shape(radii, ring: float = 1.0, cap: float = 1.0) -> dict[str, str]:
    """A surface inside `radii`: round the y axis by `ring` and from pole to pole by `cap` (1 = an egg's curve,
    towards 0 = square). ring 1 with a small cap is a cylinder along y; both small is a block. The x, y, z
    expressions of a Limb: `Limb(**shape(radii, 0.6, 0.6), radii=radii, ...)`."""
    x, y, z = (f"{r:.5f}" for r in radii)
    cu, su = (f"sign({f}(u))*pow(abs({f}(u)),{ring})" for f in ("cos", "sin"))
    return {"x": f"{x}*{cu}*pow(abs(cos(v)),{cap})", "y": f"{y}*sign(sin(v))*pow(abs(sin(v)),{cap})",
            "z": f"{z}*{su}*pow(abs(cos(v)),{cap})"}


# the names these had while this was dev3d.py: the plush, robot and base modules still import them
_unit, _cross, _scaled, _basis, _grid = unit, cross, scaled, basis, grid
