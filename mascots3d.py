"""The figure the plush family is built on: a mascot on the mannequin's skeleton (sr-data/decisions/0001).

A `Spec` gives a character its proportions (a `Build`) and body; a builder registered in `BUILDERS` draws its face,
ears, belly and tail (`plush3d.py` registers the plush family). The body is designed in the skeleton's rest pose
and carried by the chest bone, so the spine can bend it; arms and legs are tubes between the solved joints, so the
IK gestures move them. The look, the ink and the paper come from `dev3d.py`.

Professor Frog, Chick and the Mouse used to be built here; they were removed on 2026-11-11 (the cast is the plush
family) and live on, as they were, in `sr-data/characters_legacy/`.
"""

from __future__ import annotations

import math
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "characters"

from srlocations import Location, Material, Registry  # noqa: E402
from srlocations.geometry import Transform, Vec3  # noqa: E402
from srlocations.stock.mannequin import KINDS, RELAXED, Build, Limb, Mannequin, _egg  # noqa: E402
from srlocations.stock.mannequin import POSES as BODY_POSES  # noqa: E402

from . import dev3d, fixed  # noqa: E402
from .dev3d import FONT, ROOT, VIEWS, _basis, _cross, _grid, _scaled, _unit, render, stage, tube  # noqa: E402
from .doodle import MOUTHS, Pose  # noqa: E402
from .poses import POSES  # noqa: E402

COLOURS = {
    "plush.contact": "#8C8C8C", "plush.contact-soft": "#C8C8C8",   # the contact shadow's two tones (see Contact)
    "m.white": "#FBFAF5", "m.ink": "#1C1B1A", "m.mouth": "#9A3236", "m.tongue": "#E07A74", "m.sweat": "#7FC0E8",
}


COLOURS.update({"item.gift": "#E0605A", "item.band": "#F6D24A", "item.ball": "#58A6E6",   # what a figure may hold
                "item.glass": "#E4EEF2", "item.wine": "#8E2A3A", "item.beer": "#E9A93A", "item.foam": "#FFFBF0",
                "item.bottle": "#2F6B4A", "item.label": "#F4EBD8", "item.cork": "#C9A46B"})


def register(registry: Registry) -> None:
    for name, colour in COLOURS.items():
        registry.materials.add(name, Material(colour), override=True)


CONTACT_LOOK = "plush.paper"   # the look that knows how to draw a contact shadow (plush3d.look)


@dataclass
class Contact(Limb):
    """A figure's contact shadow: a flat oval on what it stands or sits on. It is no part of the body (nothing
    collides with it) and only the plush look draws it, as shade (plush3d.ContactShade); any other look leaves it out."""

    def hulls(self, world):
        return []


def _mul(a, b):
    return tuple(tuple(sum(a[r][k] * b[k][c] for k in range(3)) for c in range(3)) for r in range(3))


def _t(a):
    return tuple(tuple(a[c][r] for c in range(3)) for r in range(3))


class Carry:
    """Moves what was designed in the rest pose with a bone: rest space -> the bone as it is now."""

    def __init__(self, now: Transform, rest: Transform, shift: float = 0.0,
                 scale: Sequence[float] = (1.0, 1.0, 1.0), pivot: Sequence[float] = (0.0, 0.0, 0.0), lift: float = 0.0):
        self.now, self.rest, self.shift = now, rest, shift
        self.turn = _mul(now.basis, _t(rest.basis))
        # squash and stretch: design space is scaled about `pivot` and then lifted, so everything carried (the
        # shape, its face, ears, belly, tail) squashes as one piece
        self.scale, self.pivot, self.lift = tuple(scale), tuple(pivot), lift

    def point(self, p) -> Vec3:
        """`p` is in design space (the body designed with its centre at y 0.4), lifted by `shift` onto the rest pose."""
        x, y, z = (self.pivot[i] + (p[i] - self.pivot[i]) * self.scale[i] for i in range(3))
        return self.now.apply(self.rest.undo(Vec3(x, y + self.lift + self.shift, z)))

    def basis(self, b):
        return _mul(self.turn, b)

    def vec(self, v) -> Vec3:
        r = self.turn
        x, y, z = v
        return Vec3(r[0][0] * x + r[0][1] * y + r[0][2] * z, r[1][0] * x + r[1][1] * y + r[1][2] * z,
                    r[2][0] * x + r[2][1] * y + r[2][2] * z)


IDENTITY = ((1, 0, 0), (0, 1, 0), (0, 0, 1))

BROWS = {"flat": (0.0, 0.0), "raised": (0.1, 0.08), "worried": (0.12, -0.05), "angry": (-0.12, 0.06)}


def smooth(points, per: int = 5):
    """A Catmull-Rom curve through 3D points."""
    out = []
    n = len(points)
    for i in range(n - 1):
        p0, p1, p2, p3 = (points[max(0, min(n - 1, j))] for j in (i - 1, i, i + 1, i + 2))
        for k in range(per):
            t = k / per
            out.append(tuple(0.5 * (2 * p1[a] + (-p0[a] + p2[a]) * t + (2 * p0[a] - 5 * p1[a] + 4 * p2[a] - p3[a]) * t * t
                                    + (-p0[a] + 3 * p1[a] - 3 * p2[a] + p3[a]) * t ** 3) for a in range(3)))
    return out + [points[-1]]


def spiral(on, stroke, fx: float, fy: float, size: float, r: float, turns: float = 2.0) -> None:
    """Dizzy eyes: a spiral line drawn on the face (design-space points from `on`)."""
    n = int(turns * 16)
    pts = []
    for i in range(n + 1):
        a = 2 * math.pi * turns * i / n
        rr = size * (0.12 + 0.88 * i / n)
        pts.append(on(fx + rr * math.cos(a), fy + rr * math.sin(a) * 1.1, 0.01))
    stroke("eye/spiral", pts, r)



def brows(on, stroke, e, fx: float, fy: float, half: float, r: float, was: str = "", mix: float = 1.0,
          lift: float = 0.0) -> None:
    """Brows as strokes lying on the face's surface, shaped by the pose's `brows` (as on the 2D drawings). Becoming
    these from `was` (`mix` 0 to 1): one shape turns into the other; brows that were not there grow from their
    middle, and brows that go shrink into it. `lift` raises them (a start of surprise)."""
    def ends(kind, sx):
        if kind == "skeptic":
            return (0.13, 0.1) if sx > 0 else (-0.03, -0.03)
        if kind == "arched":  # one brow up a little, the other as it rests; the eyes stay open
            return (0.06, 0.05) if sx > 0 else (0.0, 0.0)
        return BROWS.get(kind, (0.0, 0.0))

    k = max(0.0, min(1.0, mix))
    k = k * k * (3 - 2 * k)
    now, before = e.brows, (was or e.brows)
    if k >= 1.0 or before == now:
        before, k = now, 1.0
    if now == "none" and before == "none":
        return
    for sx in (-1, 1):
        size = 1.0
        if before == "none":      # growing in
            inner, outer, size = *ends(now, sx), k
        elif now == "none":       # shrinking away
            inner, outer, size = *ends(before, sx), 1.0 - k
        else:
            (i0, o0), (i1, o1) = ends(before, sx), ends(now, sx)
            inner, outer = i0 + (i1 - i0) * k, o0 + (o1 - o0) * k
        if size < 0.08:
            continue
        reach = half * (0.35 + 0.65 * size)
        pts = [on(sx * (fx - reach), fy + lift + inner, 0.01), on(sx * fx, fy + lift + (inner + outer) / 2 + 0.03, 0.01),
               on(sx * (fx + reach), fy + lift + outer, 0.01)]
        stroke("brow/line", smooth(pts, 4), r * (0.45 + 0.55 * size))


def shaped(radii, ring: float = 1.0, cap: float = 1.0) -> dict[str, str]:
    """A surface inside `radii`: round the y axis by `ring` and from pole to pole by `cap` (1 = an egg's curve,
    towards 0 = square). ring 1 with a small cap is a cylinder along y; both small is a box."""
    x, y, z = (f"{r:.5f}" for r in radii)
    cu, su = (f"sign({f}(u))*pow(abs({f}(u)),{ring})" for f in ("cos", "sin"))
    return {"x": f"{x}*{cu}*pow(abs(cos(v)),{cap})", "y": f"{y}*sign(sin(v))*pow(abs(sin(v)),{cap})",
            "z": f"{z}*{su}*pow(abs(cos(v)),{cap})"}


def box_egg(radii, e: float) -> dict[str, str]:
    """An egg's surface squared off: a rounded box inside the same radii (a superellipsoid of exponent e)."""
    x, y, z = (f"{r:.5f}" for r in radii)
    cu, su = f"sign(cos(u))*pow(abs(cos(u)),{e})", f"sign(sin(u))*pow(abs(sin(u)),{e})"
    return {"x": f"{x}*{cu}*pow(abs(cos(v)),{e})", "y": f"{y}*sign(sin(v))*pow(abs(sin(v)),{e})",
            "z": f"{z}*{su}*pow(abs(cos(v)),{e})"}


def _dot(a, b) -> float:
    return a.x * b.x + a.y * b.y + a.z * b.z


@dataclass
class Spec:
    """One mascot: proportions, body, and what it adds to them."""
    key: str
    build: Build
    body: tuple[tuple[float, float, float], tuple[float, float, float], str]  # centre, radii, material (rest pose)
    face: str = "body"            # "body": the face is on the body; "head": on its own head (the plush family)
    head: Optional[tuple[tuple[float, float, float], tuple[float, float, float], str]] = None
    limb: str = ""                # material of arms and legs
    arm_r: float = 0.03
    leg_r: float = 0.03
    shift: float = 0.0            # how far the body designed at y 0.4 moves to sit on this skeleton
    paw: str = ""                 # material of hands and feet ("" = the limbs')
    foot_m: str = ""              # material of the feet alone (a bird's yellow feet)
    merge: bool = False           # arms and legs join the body's ink group: one soft shape, no line at the shoulder
    foot: Optional[tuple[float, float, float]] = None  # a foot's radii (x, y, z)
    splay: float = 0.0            # resting arms held out from the body (share of the arm's length)
    arm_taper: tuple[float, float, float] = (1.0, 0.92, 0.85)  # radius at shoulder, elbow, wrist (times arm_r)
    leg_taper: tuple[float, float, float] = (1.0, 0.92, 0.85)  # at hip, knee, ankle (times leg_r)
    hand: float = 1.35            # a hand's radius (times arm_r)
    pad: str = ""                 # material of a paw's pads ("" = a plain round hand): a mitten paw with a palm
    reach: float = 0.12           # how far short of a gesture's target a hand may stop (stubby arms: further)
    rest_hands: Optional[tuple[float, float, float]] = None  # where resting hands go (x out from the middle, y, z)
    stance: Mapping[str, float] = field(default_factory=dict)  # skeleton controls under every pose (a family's stance)
    # Gestures were laid out for a 0.7 m toy whose hand is a ball on its wrist. A bigger figure with a real hand
    # (characters.lowpoly3d) says how much further its hands go from the shoulder, and how long the hand is past
    # the wrist, so a hand "at the chin" stops with its fingers there and not across the face. 1 and 0 change nothing.
    gesture_scale: float = 1.0
    hand_length: float = 0.0
    sit_drop: float = 0.0         # how far a seated figure comes down to rest on its seat (a body of its own whose
    #                               lowest part is not where the skeleton's is: characters.robots3d)
    # An arm keeps its length and bends at the elbow. For a hand further off than it reaches it is drawn longer, by
    # no more than `stretch`; where it has to go round a big head to a hand on the face, by no more than `detour`.
    stretch: float = 1.8
    detour: float = 2.0
    boxy: tuple[float, float] = (0.0, 0.0)  # body and head as rounded boxes of the same radii (a robot): the
    #                                         exponent of each, 1 = the ellipsoid, 0.5 = a soft box; 0 = an ellipsoid


SPECS: dict[str, Spec] = {}        # who -> its Spec; plush3d fills it with the plush family

LOOKS: dict[str, Callable] = {}     # who -> a look of its own (default: dev3d's)
BUILDERS: dict[str, Callable] = {}  # who -> builder(figure, frames, body, head, put) for families in other modules
WHOLE: dict[str, Callable] = {}     # who -> builder(figure, frames) of a figure that draws all of itself (robots3d)
_REST: dict[str, dict[str, Transform]] = {}
_SOLVED: dict = {}        # joints solved for a figure in a pose (MascotFigure.frames)
_BUILDING_REST = [False]  # while the rest pose itself is solved, draw the mannequin's own body (no recursion)
_GESTURES: dict[tuple[str, str], dict[str, float]] = {}


@dataclass
class MascotFigure(Mannequin):
    """A mascot on the mannequin skeleton. `who` picks its Spec; `expression` its face, as for Dev."""
    who: str = "bear"
    expression: Pose = field(default_factory=Pose)
    kind: Optional[str] = None
    kinds: Mapping[str, Build] = field(default_factory=lambda: dict(KINDS), repr=False, compare=False)
    # Soft-toy motion, keyed in time by characters.motion: `squash` above 0 stretches the body and head taller and
    # thinner, below 0 squashes them shorter and wider (volume kept; 0.1 = a tenth); `arm_left`/`arm_right` draw
    # that arm longer (1.4 = 40% longer) so a wave or a cheer reads on stubby arms.
    squash: float = 0.0
    arm_left: float = 1.0
    arm_right: float = 1.0
    # ears that move (the plush family): degrees each ear leans out from the head (+) or in (-), and both lean back
    ear_left: float = 0.0
    ear_right: float = 0.0
    ear_back: float = 0.0
    # a tail that moves (the plush family): degrees it swings to the figure's right (+) or left, and lifts (+)
    tail_sway: float = 0.0
    tail_lift: float = 0.0
    # Off the spot (keyed in time by characters.motion): `hop` is how high the whole figure is off the ground (m),
    # `step_x`/`step_z` how far it has travelled from `at` in the location (m).
    hop: float = 0.0
    # the contact shadow under it: 1 as drawn, 0 none, between for a fainter (smaller) one
    shadow: float = 1.0
    step_x: float = 0.0
    step_z: float = 0.0
    step_y: float = 0.0           # how far up it has climbed (a step, a box): its shadow comes up with it
    # A face that moves between its drawings (keyed in time by characters.motion; the plush family, and
    # `mouth_open` every mascot): `lid` lowers the upper eyelids (0 open, 1 shut: a blink's in-between frames),
    # `eye_scale` sizes the eyes (a pop of surprise), `mouth_open` is how far an open mouth is open (it opens and
    # closes over a few frames instead of appearing), `blush` sizes the cheeks' blush, `look_x`/`look_y` add to the
    # expression's look (the eyes dart ahead of the head).
    lid: float = 0.0
    eye_scale: float = 1.0
    mouth_open: float = 1.0
    # A line mouth and the brows morph from what they were: `mouth_from` / `brows_from` name the drawing before
    # this one and `mouth_mix` / `brow_mix` say how far it has become the new one (1 = it is the new one).
    # `lid_left` / `lid_right` add to `lid` on that eye alone (a wink).
    mouth_from: str = ""
    mouth_mix: float = 1.0
    brows_from: str = ""
    brow_mix: float = 1.0
    lid_left: float = 0.0
    lid_right: float = 0.0
    blush: float = 1.0
    look_x: float = 0.0
    look_y: float = 0.0
    # a wrist (the plush family): degrees each paw flaps away from the body (+) or toward it, in the picture's plane
    wrist_left: float = 0.0
    wrist_right: float = 0.0
    # Feet that lift (keyed in time by characters.motion): metres each foot is off the ground, and ahead of where it
    # stands. The legs are short and hidden in the body, so a step, a march or a kick shows only in its feet.
    foot_left_up: float = 0.0
    foot_right_up: float = 0.0
    foot_left_ahead: float = 0.0
    foot_right_ahead: float = 0.0
    # seated, a long tail curls round beside the body: on the figure's local +x side (1) or its -x side (-1)
    tail_side: float = 1.0
    # A robot's screen (keyed in time by characters.motion): `power` is how far it is on (1 = on, 0 = dark: the
    # eyes shut as it goes down, then the face leaves the screen), `icon` a picture it shows in place of its face
    # ("heart", "question", "exclaim", "dots").
    power: float = 1.0
    icon: str = ""
    # what it holds, as "side:thing" ("right:gift", "left:ball", "right:glass"); "" = nothing. `item_tilt` tips it
    # toward the face (degrees: a drink); `pop` is how far a bottle's pop has got (0 none .. 1 over): its cork
    # flies off and its foam bursts
    item: str = ""
    item_tilt: float = 0.0
    pop: float = 0.0
    # its fixed list of parts for the film it acts in (characters.fixed.settle gives it): one object for each part
    # it ever shows, sized by keys, so the scene holds the figure once
    fixed: Any = field(default=None, repr=False, compare=False)

    @property
    def transform(self) -> Transform:
        base = super().transform
        drop = self.spec.sit_drop if "sit" in self.expression.extras else 0.0
        if not (self.hop or self.step_x or self.step_z or self.step_y or drop):
            return base
        return Transform(base.position + Vec3(self.step_x, self.hop + self.step_y - drop, self.step_z), base.basis)

    def frames(self):
        """The joints as the pose puts them. A film asks this of the same moment more than once (the checks, the
        fixed list of parts, the compiler), each time of a new copy of the figure: what was solved is kept."""
        pose = self.pose if isinstance(self.pose, str) else tuple(sorted(self.pose.items()))
        key = (self.who, pose, tuple(sorted(self.adjust.items())), self.height, self.kind, self.seed, self.grounded,
               self.limits, self.lower, self.balanced, tuple(self.holds), tuple(sorted(self.let_go.items())),
               self.transform if self.holds else None, id(self.poses), self.looks and tuple(self.looks))
        if key not in _SOLVED:
            if len(_SOLVED) > 6000:
                _SOLVED.clear()
            _SOLVED[key] = super().frames()
        return _SOLVED[key]

    def __post_init__(self) -> None:
        spec = SPECS[self.who]
        self.kind = spec.key
        self.kinds = {**KINDS, spec.key: spec.build}
        super().__post_init__()

    @property
    def spec(self) -> Spec:
        return SPECS[self.who]

    def _rest(self) -> dict[str, Transform]:
        """The skeleton in its rest pose, which the body was designed in (solved with the mannequin's own body, as
        the joint positions the designs were measured from were)."""
        if self.who not in _REST:
            _BUILDING_REST[0] = True
            try:
                _REST[self.who] = MascotFigure(pose=dict(RELAXED), who=self.who, looks=self.looks).frames()
            finally:
                _BUILDING_REST[0] = False
        return _REST[self.who]

    # -- parts
    def _egg_part(self, name, centre, radii, material, basis=IDENTITY, samples=(20, 14)) -> Limb:
        radii = tuple(float(r) for r in radii)
        box = {"body/body": self.spec.boxy[0], "head/head": self.spec.boxy[1]}.get(name, 0.0)
        if box:
            return Limb(**box_egg(radii, box), radii=radii, at=Vec3(*centre), basis=basis, name=name,
                        material=material, samples=(44, 30), casts_shadow=False, looks=self.looks)
        return Limb(**_egg(radii), radii=radii, at=Vec3(*centre), basis=basis, name=name, material=material,
                    samples=samples, casts_shadow=False, looks=self.looks)

    def _drop(self, frames) -> float:
        """How far the lowest part of the figure is above the floor, as the mannequin has it, but with the contact
        shadow taken where it lies under a figure that stands on the ground. The shadow stays down under a figure
        in the air (`hop`); counted where it then is, it was the lowest part and the figure was stood on it: a
        jump lifted the body twice and left the feet behind. (A seated figure's `Spec.sit_drop` still counts on
        the shadow being in this.)"""
        if not self.grounded:
            return 0.0
        leans = abs(float(getattr(self, "roll", 0.0))) > 0.5      # its shadow is then placed from the ground up
        return min(part.bounds(part.transform)[0].y + (self.hop if isinstance(part, Contact) else 0.0)
                   for part in self._drawn(frames) if not (leans and isinstance(part, Contact)))

    def _parts(self, frames):
        parts = self._drawn(frames)
        if self.fixed is not None and fixed.wanted() and not _BUILDING_REST[0]:
            return self.fixed.fit(parts, self.transform)
        return parts

    def _drawn(self, frames):
        need = ("hips", "chest", "neck", "head", "left_hand", "right_hand", "left_foot", "right_foot")
        if _BUILDING_REST[0] or not all(n in frames for n in need):
            return super()._parts(frames)
        whole = WHOLE.get(self.who)
        if whole is not None:  # a figure with a body of its own (characters.robots3d): nothing of the plush body
            return whole(self, frames) + self._held(frames) + self._contact(frames)
        rest = self._rest()
        (c, r, m) = self.spec.body
        k = max(-0.3, min(0.3, self.squash))
        tall, wide = 1.0 + k, 1.0 / math.sqrt(1.0 + k)               # volume kept
        scale = (wide, tall, wide)
        # the body squashes about its base; the head about its own base, riding on the body's top as it moves
        body = Carry(frames["chest"], rest["chest"], self.spec.shift, scale, (c[0], c[1] - r[1], c[2]))
        if self.spec.face == "head":
            hc, hr, _hm = self.spec.head
            head = Carry(frames["head"], rest["head"], 0.0, scale, (hc[0], hc[1] - hr[1], hc[2]),
                         lift=2 * r[1] * (tall - 1.0))
        else:
            head = body
        parts = []
        put = lambda carry, name, c, r, m, b=IDENTITY, samples=(20, 14): parts.append(  # noqa: E731
            self._egg_part(name, carry.point(c), tuple(x * q for x, q in zip(r, carry.scale)), m, carry.basis(b),
                           samples))
        put(body, "body/body", c, r, m, samples=(30, 20))
        if self.spec.head:
            hc, hr, hm = self.spec.head
            parts.append(tube("neck/neck", frames["neck"].position, frames["head"].position, 0.045, 0.045, hm,
                              looks=self.looks))
            put(head, "head/head", hc, hr, hm, samples=(28, 18))
        for side in ("left", "right"):
            parts += self._arm(frames, side) + self._leg(frames, side)
        build = BUILDERS.get(self.who)
        if build is None:
            raise KeyError(f"no builder for {self.who!r}: import characters.plush3d, which registers the plush family")
        parts += build(self, frames, body, head, put)
        parts += self._held(frames)
        parts += self._contact(frames)
        return parts

    def _head_now(self, frames):
        """The head as it is drawn now: (its centre, how it is turned, its radii, how square it is: 2 an egg, more
        a box); None for a figure whose face is on its body."""
        if self.spec.face != "head" or not self.spec.head or "head" not in frames or "chest" not in frames:
            return None
        rest = self._rest()
        (_c, r, _m), (hc, hr, _hm) = self.spec.body, self.spec.head
        k = max(-0.3, min(0.3, self.squash))
        tall, wide = 1.0 + k, 1.0 / math.sqrt(1.0 + k)
        scale = (wide, tall, wide)
        head = Carry(frames["head"], rest["head"], 0.0, scale, (hc[0], hc[1] - hr[1], hc[2]),
                     lift=2 * r[1] * (tall - 1.0))
        box = self.spec.boxy[1]
        return head.point(hc), head.turn, tuple(x * q for x, q in zip(hr, scale)), (2.0 / box if box else 2.0)

    def arm_points(self, frames, side):
        """Shoulder, elbow and wrist as the arm is drawn. The arm keeps its length: it bends at the elbow for a hand
        nearer than it reaches, and is drawn longer only for a hand further off (`arm_left`, `arm_right`). It is
        kept out of the head: the shoulders sit under a head far wider than they are, so an arm that goes straight
        to the face runs through the head, and the two are then drawn as one lump with a hand growing out of the
        face. Here the hand stops on the head's surface and the elbow swings round the line from shoulder to wrist
        to where the forearm is clear of the head; only if it is clear nowhere is the arm drawn longer, by no more
        than `Spec.detour`, and if that is not enough the hand stops short of where it was going (the arm was
        pushed out as far as it took, and grew to five times its length)."""
        s, e, w = (frames[f"{side}_{b}"].position for b in ("upper_arm", "lower_arm", "hand"))
        longer = self.arm_left if side == "left" else self.arm_right
        head = self._head_now(frames)
        if head is None:
            if longer != 1.0:  # a cartoon's stretch: the same arm, drawn longer from the shoulder out
                e2 = s + _scaled(e - s, longer)
                e, w = e2, e2 + _scaled(w - e, longer)
            return s, e, w
        centre, turn, radii, power = head
        r = self.spec.arm_r
        upper, fore = (e - s).length, (w - e).length
        bones, share = upper + fore, upper / max(1e-6, upper + fore)
        w = s + _scaled(w - s, longer)                 # where the hand is going

        def push(p, margin):
            """How `p` must move to be `margin` clear of the head (nothing when it already is)."""
            d = p - centre
            q = [sum(turn[k][i] * (d.x, d.y, d.z)[k] for k in range(3)) for i in range(3)]      # in the head's axes
            n = sum(abs(q[i] / (radii[i] + margin)) ** power for i in range(3)) ** (1.0 / power)
            if n >= 1.0 or n < 1e-6:
                return None
            g = [q[i] * (1.0 / n - 1.0) for i in range(3)]                                     # straight out from its middle
            return Vec3(*(sum(turn[k][i] * g[i] for i in range(3)) for k in range(3)))

        most = bones * max(self.spec.detour, longer)
        step = math.radians(15.0)

        def solve(w):
            """(elbow, wrist, how far into the head the forearm still is) for a hand going to `w`."""
            for last in (False, False, True):              # the hand out of the head, and no further than the arm goes
                by = push(w + _scaled(_unit(w - e), r * 1.1), 0.75 * r * self.spec.hand)   # the hand's middle (_arm)
                if by is not None:
                    w = w + by
                far = (w - s).length
                if far > most and not last:
                    w = s + _scaled(w - s, most / far)
            far = max(1e-6, (w - s).length)
            along = _scaled(w - s, 1.0 / far)
            bend = (e - s) - _scaled(along, _dot(e - s, along))      # the way the elbow bends: as the pose has it
            if bend.length < 0.004:                                   # a straight arm: out, down and back
                pole = Vec3(0.6 if side == "right" else -0.6, -0.6, -0.6)
                bend = pole - _scaled(along, _dot(pole, along))
            bend, across = _unit(bend), _cross(along, _unit(bend))

            def elbow(total, angle):
                a, b = total * share, total * (1.0 - share)
                d = min(far, total - 1e-6)
                x = (a * a - b * b + d * d) / (2.0 * d)
                h = math.sqrt(max(0.0, a * a - x * x))
                return s + _scaled(along, x) + _scaled(bend, h * math.cos(angle)) + _scaled(across, h * math.sin(angle))

            def inside(total, angle):
                """How far into the head the forearm is (0: clear of it). The shoulder and the elbow are under the head."""
                at = elbow(total, angle)
                deep = 0.0
                for t in (0.3, 0.55, 0.8):
                    by = push(at + _scaled(w - at, t), 0.9 * r)
                    deep += by.length if by is not None else 0.0
                return deep


            def swing(total):
                """(the least swing of the elbow that clears the head, 0) or (the swing nearest to clear, how deep)."""
                best = (0.0, inside(total, 0.0))
                if best[1] < 1e-5:
                    return best
                for k in range(1, 13):
                    for sign in (1.0, -1.0):
                        deep = inside(total, sign * k * step)
                        if deep < 1e-5:
                            lo, hi = sign * (k - 1) * step, sign * k * step       # the edge of clear, between the two
                            for _ in range(5):
                                mid = 0.5 * (lo + hi)
                                lo, hi = (lo, mid) if inside(total, mid) < 1e-5 else (mid, hi)
                            return hi, 0.0
                        if deep < best[1]:
                            best = (sign * k * step, deep)
                return best

            short = max(bones, far)                          # its own length, or as long as the hand is far
            total, (angle, deep) = short, swing(short)
            if deep > 0.0 and most > short + 1e-4:           # clear nowhere: the arm is drawn longer, as little as will do
                angle2, deep2 = swing(most)
                if deep2 == 0.0:
                    lo, hi = short, most
                    for _ in range(6):
                        mid = 0.5 * (lo + hi)
                        lo, hi = (lo, mid) if swing(mid)[1] == 0.0 else (mid, hi)
                    total, angle, deep = hi, swing(hi)[0], 0.0
                elif deep2 < deep:
                    total, angle, deep = most, angle2, deep2
            return elbow(total, angle), w, deep

        e2, w2, deep = solve(w)
        if deep > 0.0:
            # No arm of this length goes round the head to there: the hand stops short, as near as it gets with the
            # forearm clear (a paw held up before the face, not one growing out of it).
            near = s + _scaled(Vec3(0.5 if side == "right" else -0.5, -0.25, 0.85), bones)
            e3, w3, deep3 = solve(near)
            if deep3 == 0.0:
                lo, hi = 0.0, 1.0
                for _ in range(6):
                    mid = 0.5 * (lo + hi)
                    got = solve(w + _scaled(near - w, mid))
                    if got[2] == 0.0:
                        hi, (e3, w3) = mid, got[:2]
                    else:
                        lo = mid
                e2, w2 = e3, w3
            elif deep3 < deep:
                e2, w2 = e3, w3
        return s, e2, w2

    def _held(self, frames) -> list:
        """What the figure holds (`item`), on the hand that holds it, wherever that hand has got to: a gift, a
        ball, a glass of wine, a mug of beer, a bottle (corked, or open). `item_tilt` tips it toward the
        figure's face (a drink); `pop` sends a bottle's cork off and its foam up."""
        if not self.item or ":" not in self.item:
            return []
        side, thing = self.item.split(":", 1)
        if not all(f"{side}_{b}" in frames for b in ("upper_arm", "lower_arm", "hand")):
            return []
        s, e, w = self.arm_points(frames, side)   # as the arm is drawn (MascotFigure._arm)
        # a drink is drawn half as big again as it would be: at its true size it is a speck in a paw
        big = 1.5 if thing in ("glass", "mug", "bottle", "bottle-open") else 1.0
        lift = {"glass": 0.062, "mug": 0.058, "bottle": 0.07, "bottle-open": 0.07}.get(thing, 0.052) * big
        at = w + _scaled(_unit(w - e), self.spec.arm_r * 1.1) + Vec3(0.0, lift, 0.03)
        c, sn = math.cos(math.radians(self.item_tilt)), math.sin(math.radians(self.item_tilt))
        turn = ((1.0, 0.0, 0.0), (0.0, c, sn), (0.0, -sn, c))       # its top goes back, toward the face
        out_side = 1.0 if side == "right" else -1.0

        def to(p):          # a point of the thing (x across, y up it, z forward), where it is
            x, y, z = (big * v for v in p)
            return at + Vec3(x, c * y + sn * z, -sn * y + c * z)

        def solid(name, p, radii, material, ring=1.0, cap=1.0, samples=(18, 12)):
            radii = tuple(float(r) * big for r in radii)
            return Limb(**shaped(radii, ring, cap), radii=radii, at=to(p), basis=turn, name=name, material=material,
                        samples=samples, casts_shadow=False, looks=self.looks)

        def rod(name, p0, p1, r0, r1, material):
            return tube(name, to(p0), to(p1), r0 * big, r1 * big, material, looks=self.looks, samples=(10, 12))

        if thing == "ball":
            return [solid("item/ball", (0, 0, 0), (0.04, 0.04, 0.04), "item.ball"),
                    solid("itemband/band", (0, 0, 0), (0.0405, 0.012, 0.0405), "item.band", samples=(16, 8))]
        if thing == "glass":    # a glass of red wine: a foot, a stem, the bowl full, a rim of glass
            return [solid("glass/foot", (0, -0.05, 0), (0.022, 0.004, 0.022), "item.glass", cap=0.3, samples=(16, 8)),
                    rod("glass/stem", (0, -0.05, 0), (0, -0.012, 0), 0.0045, 0.0045, "item.glass"),
                    solid("wine/wine", (0, 0.014, 0), (0.027, 0.031, 0.027), "item.wine"),
                    solid("glass/rim", (0, 0.038, 0), (0.0255, 0.007, 0.0255), "item.glass", cap=0.4, samples=(18, 8))]
        if thing == "mug":      # a mug of beer: the beer, its head of foam, a handle on the outside
            ring, thin = 0.017 * big, 0.0055 * big
            handle = Limb(x=f"({ring}+{thin}*cos(v))*cos(u)", y=f"({ring}+{thin}*cos(v))*sin(u)", z=f"-{thin}*sin(v)",
                          u=(0, 360), v=(0, 360), samples=(22, 8), closed=(True, True),
                          radii=(ring + thin, ring + thin, thin), at=to((out_side * 0.03, 0.0, 0.0)), basis=turn,
                          name="mughandle/handle", material="item.glass", casts_shadow=False, looks=self.looks)
            return [handle, solid("beer/beer", (0, -0.004, 0), (0.029, 0.036, 0.029), "item.beer", cap=0.25),
                    solid("foam/head", (0, 0.036, 0), (0.031, 0.014, 0.031), "item.foam", samples=(18, 10)),
                    solid("foam/blob", (0.012, 0.045, 0.006), (0.014, 0.011, 0.014), "item.foam", samples=(12, 8))]
        if thing in ("bottle", "bottle-open"):   # a bottle of sparkling wine: label, long neck, gold foil
            parts = [solid("bottle/body", (0, -0.012, 0), (0.025, 0.05, 0.025), "item.bottle", cap=0.3),
                     rod("bottle/neck", (0, 0.03, 0), (0, 0.092, 0), 0.022, 0.0095, "item.bottle"),
                     solid("label/label", (0, -0.018, 0), (0.0256, 0.018, 0.0256), "item.label", cap=0.2, samples=(18, 8)),
                     solid("foil/foil", (0, 0.094, 0), (0.0115, 0.017, 0.0115), "item.band", cap=0.4, samples=(14, 8))]
            mouth, k = (0.0, 0.114, 0.0), max(0.0, min(1.0, self.pop))
            if thing == "bottle":
                parts.append(solid("cork/cork", (0, 0.118, 0), (0.0095, 0.012, 0.0095), "item.cork", cap=0.5,
                                   samples=(12, 8)))
            else:               # open: a little foam at its mouth
                parts.append(solid("foam/mouth", mouth, (0.012, 0.009, 0.012), "item.foam", samples=(12, 8)))
            if 0.0 < k < 1.0:   # the pop: the cork flies up and away to the outside, the foam bursts and falls back
                fly = (out_side * 0.3 * k, 0.118 + 0.62 * k - 0.6 * k * k, 0.12 * k)
                parts.append(solid("cork/cork", fly, (0.0095, 0.012, 0.0095), "item.cork", cap=0.5, samples=(12, 8)))
                burst = math.sin(math.pi * min(1.0, k * 1.25)) ** 0.7
                for i, (dx, dz) in enumerate(((0.0, 0.0), (0.014, 0.006), (-0.012, 0.008), (0.006, -0.012),
                                              (-0.004, 0.004))):
                    r = 0.017 * burst * (1.0 - 0.13 * i)
                    parts.append(solid(f"foam/spray_{i}", (dx * (1 + 2.5 * burst), mouth[1] + 0.012 + 0.034 * i * burst,
                                                         dz * (1 + 2.5 * burst)), (r, r, r), "item.foam", samples=(10, 8)))
            return parts
        r = 0.038               # a gift: a box, a ribbon round it, a bow on top
        return [solid("item/gift", (0, 0, 0), (r, r, r), "item.gift", 0.35, 0.35, (28, 18)),
                solid("itemband/ribbon", (0, 0, 0), (r * 1.03, r * 1.03, r * 0.28), "item.band", 0.35, 0.35, (28, 18)),
                solid("itemband/bow", (0, r, 0), (0.017, 0.012, 0.017), "item.band", samples=(10, 8))]

    def lying_size(self) -> tuple[float, list]:
        """(How tall the figure is, its big round parts as (height of the middle, radius across, radius up))."""
        (c, r, _m) = self.spec.body
        rounds = [(c[1] + self.spec.shift, r[0], r[1])]
        if self.spec.head:
            (hc, hr, _hm) = self.spec.head
            rounds.append((hc[1], hr[0], hr[1]))
        return max(y + up for y, _a, up in rounds), rounds

    def lying_lift(self, roll: float) -> float:
        """How far the figure must come up off the ground when it leans `roll` degrees over about its feet, so
        that its body and head rest on the ground and do not sink into it (lying on its side: about a head's
        radius)."""
        th = math.radians(roll)
        low = min(y * math.cos(th) - math.sqrt((across * math.sin(th)) ** 2 + (up * math.cos(th)) ** 2)
                  for y, across, up in self.lying_size()[1])
        return max(0.0, -low)

    def _contact(self, frames) -> list:
        """The contact shadow: two flat ovals under the body (a soft rim round a darker middle), on the ground the
        figure stands or sits on. Off the ground (`hop`) it stays down and shrinks; squashed, it spreads."""
        if self.shadow <= 0:
            return []
        hips = frames["hips"].position
        seated = "sit" in self.expression.extras
        air = max(0.0, self.hop - self.lying_lift(float(getattr(self, "roll", 0.0))))   # lying, it is not in the air
        k = self.shadow * max(0.35, 1.0 - 2.5 * air) / math.sqrt(1.0 + max(-0.3, min(0.3, self.squash)))
        (_c, r, _m) = self.spec.body
        wide, deep = r[0] * 1.5 * k, r[2] * (1.75 if seated else 1.45) * k
        at = Vec3(hips.x, 0.003 - self.hop + (self.spec.sit_drop if seated else 0.0), hips.z + (0.07 if seated else 0.02))
        turn = IDENTITY
        if abs(float(getattr(self, "roll", 0.0))) > 0.5:
            # The shadow is in the figure's own frame, so under a figure that leans over (`roll`: a faint, lying
            # down) it would tip up on edge with it. It is put back flat on the ground under the figure's middle,
            # and grows to the length of the figure as it comes to lie.
            place, down = self.transform, abs(math.sin(math.radians(self.roll)))
            tall = self.lying_size()[0]
            mid = place.apply(Vec3(0.0, 0.5 * tall, 0.0))
            fwd = _unit(Vec3(place.basis[0][2], 0.0, place.basis[2][2]))
            flat = ((fwd.z, 0.0, fwd.x), (0.0, 1.0, 0.0), (-fwd.x, 0.0, fwd.z))       # turned as the figure faces
            at, turn = place.undo(Vec3(mid.x, 0.003, mid.z)), _mul(_t(place.basis), flat)
            wide = wide + (0.68 * tall * k - wide) * down
        out = []
        for name, share, lift in (("soft", 1.0, 0.0), ("dark", 0.72, 0.001)):
            radii = (wide * share, 0.003, deep * share)
            out.append(Contact(**_egg(radii), radii=radii, at=at + Vec3(0, lift, 0), basis=turn, name=f"contact/{name}",
                               material="plush.contact" if name == "dark" else "plush.contact-soft",
                               samples=(24, 8), casts_shadow=False, looks=(CONTACT_LOOK,)))
        return out

    def _arm(self, frames, side):
        s, e, w = self.arm_points(frames, side)
        # An arm is its own ink group, the paw with it: a line runs round it wherever it lies over the body. In the
        # body's group (as it was, for a soft join at the shoulder) an arm the colour of the body had no edge at
        # all against it, and read as a lump.
        g, r, m = f"arm_{side[0]}", self.spec.arm_r, self.spec.limb
        t0, t1, t2 = self.spec.arm_taper
        out = [tube(f"{g}/upper", s, e, r * t0, r * t1, m, looks=self.looks),
               tube(f"{g}/fore", e, w, r * t1, r * t2, m, looks=self.looks)]
        d = _unit(w - e)
        wrist = self.wrist_left if side == "left" else self.wrist_right
        if wrist:  # the paw flaps at the wrist, about the figure's front-to-back axis
            th = math.radians(-wrist if side == "right" else wrist)
            d = Vec3(d.x * math.cos(th) - d.y * math.sin(th), d.x * math.sin(th) + d.y * math.cos(th), d.z)
        hand = w + _scaled(d, r * 1.1)
        paw = self.spec.paw or m
        name = f"{g}/hand"
        if not self.spec.pad:
            # merged, a paw is the soft end of the arm (the body's ink group), not a ball stuck on it
            out.append(self._egg_part(name, hand, (r * self.spec.hand,) * 3, paw, samples=(16, 12)))
            return out
        # A mitten paw with a palm: a pad and three toe beans. The palm faces the body while the arm hangs or
        # reaches in front (pads hidden against the tummy or the face) and faces forward once the paw is raised
        # out beside the head (a wave shows its pads).
        R, sign = r * self.spec.hand, (1.0 if side == "right" else -1.0)
        up = max(0.0, min(1.0, (w.y - s.y) / 0.05 + 0.3)) * max(0.0, min(1.0, (abs(w.x - s.x) - 0.06) / 0.03))
        ref = Vec3(-sign * (1.0 - up), 0.0, up + 1e-3)
        k = ref.x * d.x + ref.y * d.y + ref.z * d.z
        n = Vec3(ref.x - d.x * k, ref.y - d.y * k, ref.z - d.z * k)
        n = _unit(n) if n.length > 1e-4 else _unit(_cross(d, Vec3(0, 1, 0)))
        across = _cross(d, n)
        basis = ((d.x, n.x, across.x), (d.y, n.y, across.y), (d.z, n.z, across.z))
        long_, deep, wide = R * 1.12, R * 0.86, R
        out.append(self._egg_part(name, hand, (long_, deep, wide), paw, basis, samples=(16, 12)))

        def on(a, c, radii):  # a pad lying on the palm, `a` along the paw and `c` across it (shares of its radii)
            h = math.sqrt(max(0.0, 1.0 - a * a - c * c))
            at = hand + _scaled(d, a * long_) + _scaled(across, c * wide) + _scaled(n, h * deep - 0.004)
            out.append(self._egg_part(f"pad_{side[0]}/pad", at, radii, self.spec.pad, basis, samples=(10, 8)))

        if up > 0.5:  # the pads show only on a raised paw; a resting paw stays the plain soft shape
            on(-0.12, 0.0, (R * 0.36, 0.008, R * 0.46))
            for a, c in ((0.5, -0.5), (0.66, 0.0), (0.5, 0.5)):
                on(a, c, (R * 0.19, 0.007, R * 0.17))
        return out

    def _leg(self, frames, side):
        hip, knee, ankle, toes = (frames[f"{side}_{b}"].position for b in ("upper_leg", "lower_leg", "foot", "toes"))
        g, r = f"leg_{side[0]}", self.spec.leg_r
        ahead = _unit(Vec3(toes.x - ankle.x, 0, toes.z - ankle.z))
        m = self.spec.limb
        foot_m = self.spec.foot_m or self.spec.paw or m
        t0, t1, t2 = self.spec.leg_taper
        g = "body" if self.spec.merge else g
        out = [tube(f"{g}/thigh", hip, knee, r * t0, r * t1, m, looks=self.looks),
               tube(f"{g}/shin", knee, ankle, r * t1, r * t2, m, looks=self.looks)]
        size = self.spec.foot or (0.045, 0.018, 0.06)
        lift = max(0.0, self.foot_left_up if side == "left" else self.foot_right_up)
        reach = self.foot_left_ahead if side == "left" else self.foot_right_ahead
        c = Vec3(ankle.x, size[1] - 0.004 + lift, ankle.z) + _scaled(ahead, size[2] * 0.55 + reach)
        across = Vec3(ahead.z, 0, -ahead.x)  # the foot turns with the leg (toes in, toes out)
        tip = math.radians(min(28.0, lift * 500.0))          # a lifted foot hangs toes down
        up = Vec3(ahead.x * math.sin(tip), math.cos(tip), ahead.z * math.sin(tip))
        out.append(self._egg_part(f"foot_{side[0]}/foot", c, size, foot_m, _basis(across, up), samples=(18, 12)))
        return out

    # -- face helpers: features on an ellipsoid (centre, radii) in rest space, carried by a bone
    def _face(self, carry: Carry, centre, radii, put):
        C, R = Vec3(*centre), Vec3(*radii)

        def on(fx, fy, out=0.0):
            z = math.sqrt(max(0.0, 1 - fx * fx - fy * fy))
            return (C.x + fx * R.x, C.y + fy * R.y, C.z + (z + out) * R.z)

        def limb(name, point, radii_, material, yaw=0.0, pitch=0.0, roll=0.0, samples=(14, 10)):
            from srlocations.geometry import rotation
            material = {"dev.ink": "m.ink", "dev.white": "m.white", "dev.skin": self.spec.body[2],
                        "dev.sweat": "m.sweat"}.get(material, material)
            put(carry, name, point, radii_, material, rotation(yaw, pitch, roll), samples)

        def stroke(name, points, r, material="m.ink"):  # a continuous line through design-space points
            for a, b in zip(points, points[1:]):
                self._extra.append(tube(name, carry.point(a), carry.point(b), r, r, material, looks=self.looks,
                                        samples=(8, 9)))

        self._stroke = stroke
        return on, limb, R

    def _lip(self, on, limb, R, m: str, fy0: float, width: float, line: float = 0.03):
        """A mouth of the shared vocabulary at fy0 on a face: a line of lumps, or an opening."""
        if m in ("open", "yell"):
            w, h = (width * 1.1, 0.16) if m == "yell" else (width * 0.85, 0.1)
            k = max(0.0, min(1.0, self.mouth_open))           # opening or closing: smaller, mostly less tall
            w, h = w * (0.72 + 0.28 * k), h * (0.22 + 0.78 * k)
            cy = fy0 - h * 0.45
            limb("mouth", on(0.0, cy, 0.0), (w * R.x, h * R.y, 0.07 * R.z), "m.mouth")
            limb("tongue", on(0.0, cy - h * 0.5, 0.035), (w * 0.55 * R.x, h * 0.32 * R.y, 0.03 * R.z), "m.tongue")
            return
        if m == "o":
            k = max(0.0, min(1.0, self.mouth_open))
            limb("mouth", on(0.0, fy0, 0.0), ((0.045 + 0.025 * k) * R.x, (0.03 + 0.055 * k) * R.y, 0.06 * R.z),
                 "m.mouth")
            return
        shape = {"flat": lambda u: 0.0, "smile": lambda u: 0.09 * u * u, "frown": lambda u: -0.07 * u * u + 0.035,
                 "smug": lambda u: 0.1 * max(0.0, u) ** 2, "wavy": lambda u: 0.03 * math.sin(u * 7)}
        curve = shape.get(m, shape["flat"])
        was = self.mouth_from
        if was == "flat" and getattr(self, "_rest_mouth", ""):
            was = self._rest_mouth                            # what this face draws for a flat mouth
        if self.mouth_mix < 1.0 and was in shape and was != m:   # becoming this mouth from the line before it
            k = max(0.0, min(1.0, self.mouth_mix))
            k, old, new = k * k * (3 - 2 * k), shape[was], curve
            curve = lambda u: (1 - k) * old(u) + k * new(u)   # noqa: E731
        pts = [on((i - 6) / 6 * width, fy0 + curve((i - 6) / 6), 0.01) for i in range(13)]
        self._stroke("mouth/line", pts, line * 0.5 * R.y)


    @property
    def _extra(self) -> list:
        if not hasattr(self, "_extra_parts"):
            object.__setattr__(self, "_extra_parts", [])
        return self._extra_parts

    def _take_extra(self) -> list:
        out = list(self._extra)
        self._extra.clear()
        return out


# ----------------------------------------------------------------------------- poses
_STRETCH: dict = {}


def gesture_stretch(who: str, kind: str) -> dict[str, float]:
    """{side: how much longer that arm is drawn so the paw arrives where the gesture puts it} (1 = it reaches)."""
    gesture(who, kind)
    return _STRETCH.get((who, kind), {})


def gesture(who: str, kind: str) -> dict[str, float]:
    """The arm controls for a gesture, solved by IK from where the hands go, scaled to the mascot's short arms."""
    if (who, kind) in _GESTURES:
        return _GESTURES[(who, kind)]
    f = MascotFigure(pose=dict(RELAXED), who=who)
    fr = f.frames()
    sh = {s: fr[f"{s}_upper_arm"].position for s in ("left", "right")}
    L = (fr["right_upper_arm"].position - fr["right_lower_arm"].position).length + \
        (fr["right_lower_arm"].position - fr["right_hand"].position).length
    (c, r, _m) = SPECS[who].head or SPECS[who].body
    lift = 0.0 if SPECS[who].head else SPECS[who].shift
    mouth = Vec3(0.0, c[1] - 0.1 * r[1] + lift, c[2] + r[2] * 0.95)

    def out(s, dx, dy, dz):
        sign = 1 if s == "right" else -1
        p = sh[s]
        return Vec3(p.x + sign * dx * L, p.y + dy * L, p.z + dz * L)

    k, hand = SPECS[who].gesture_scale, SPECS[who].hand_length

    def off(s, dx, dy, dz):  # metres from the shoulder: out to the side, up, forward (times the figure's scale)
        sign = 1 if s == "right" else -1
        return Vec3(sh[s].x + sign * dx * k, sh[s].y + dy * k, sh[s].z + dz * k)

    mouth = Vec3(mouth.x, mouth.y - 0.85 * hand, mouth.z + 0.35 * hand)   # where a wrist is for fingers at the mouth

    named = {
        "rest": ({s: Vec3((1 if s == "right" else -1) * SPECS[who].rest_hands[0], *SPECS[who].rest_hands[1:])
                  for s in ("left", "right")} if SPECS[who].rest_hands else
                 {s: out(s, SPECS[who].splay, -0.94, 0.08) for s in ("left", "right")} if SPECS[who].splay else {}),
        "present": {"right": out("right", 0.55, -0.25, 0.55)},
        "point": {"right": out("right", 0.4, 0.7, 0.3)},
        "raise": {"right": out("right", 0.25, 0.85, 0.1)},
        "chin": {"right": Vec3(mouth.x + 0.04, mouth.y - 0.02, mouth.z + 0.05)},
        "shrug": {"left": out("left", 0.65, -0.1, 0.45), "right": out("right", 0.65, -0.1, 0.45)},
        "panic": {"left": out("left", 0.45, 0.75, 0.2), "right": out("right", 0.45, 0.75, 0.2)},
        # both paws together under the chin (as near as short arms get)
        "cuddle": {s: Vec3((1 if s == "right" else -1) * 0.045, mouth.y - 0.05, mouth.z + 0.02)
                   for s in ("left", "right")},
        # the arm actions of characters.motion: a wave sweeps between "wave-in" and "wave-out"; a clap goes from
        # "clap-open" to "clap"; both paws up, to the cheeks, on the tummy. The muzzle and the eyes are out of reach.
        "wave-in": {"right": off("right", 0.09, 0.11, 0.10)},     # beside the cheek, clear of the big head
        "wave-out": {"right": off("right", 0.16, 0.03, 0.08)},
        # an open paw in front of the cheek, palm to the camera (characters.motion "palm"): out and up enough for the
        # pads to show, forward enough to be seen in front of the big head rather than behind it
        "palm": {"right": off("right", 0.095, 0.045, 0.19)},
        "cheer": {s: off(s, 0.11, 0.13, 0.06) for s in ("left", "right")},
        "clap": {s: off(s, -0.074, -0.07, 0.15) for s in ("left", "right")},
        "clap-open": {s: off(s, 0.0, -0.07, 0.14) for s in ("left", "right")},
        "cheeks": {s: off(s, 0.05, 0.035, 0.13) for s in ("left", "right")},
        "tummy": {s: off(s, -0.04, -0.125, 0.13) for s in ("left", "right")},
        # pointing (characters.motion "point-at" blends these three by where the target is): the arm straight
        # ahead, straight out to the side, straight up; past the arm's length, so it is drawn longer and reads
        "point-front": {"right": out("right", 0.12, 0.0, 1.3)},
        "point-side": {"right": out("right", 1.3, 0.02, 0.2)},
        "point-up": {"right": out("right", 0.85, 1.15, 0.3)},   # up and out: straight up hides behind a big head
        "sip": {"right": Vec3(mouth.x + 0.03, mouth.y - 0.05, mouth.z + 0.065)},   # a hand with a drink at the mouth
        "tada": {s: out(s, 0.95, 0.3, 0.5) for s in ("left", "right")},      # both arms flung open: here it is
        "beat": {s: out(s, 0.3, -0.3, 0.75) for s in ("left", "right")},     # both hands in front, low: talking
        # signs made with a hand (characters.actions, "signs"): a hand on the forehead, at the temple, a finger
        # to the lips; both hands up beside the head; an open hand swept out to the side; a flat palm, a fist
        # and a rocking hand held out in front; a hand held up to count on
        "brow": {"right": Vec3(0.02, c[1] + 0.12 * r[1] + lift - 0.85 * hand, c[2] + 0.98 * r[2] + 0.35 * hand)},
        "salute": {"right": Vec3(0.8 * r[0], c[1] + 0.35 * r[1] + lift - 0.5 * hand, c[2] + 0.55 * r[2])},
        "lips": {"right": Vec3(0.0, mouth.y + 0.03, mouth.z + 0.07)},
        "quotes": {s: out(s, 0.9, 0.6, 0.6) for s in ("left", "right")},
        # a hand on top of the head (a scratch), and a forearm held across the chest (a look at a watch)
        "scalp": {"right": Vec3(0.95 * r[0], c[1] + 0.45 * r[1] + lift, c[2] + 0.25 * r[2])},
        "watch": {"right": out("right", -0.25, 0.05, 0.7)},
        # both hands in front of the mouth (a gasp), and over the eyes (hiding the face)
        "gasp": {s: Vec3((1 if s == "right" else -1) * 0.04, mouth.y + 0.02, mouth.z + 0.06) for s in ("left", "right")},
        "eyes": {s: Vec3((1 if s == "right" else -1) * 0.32 * r[0], c[1] + 0.18 * r[1] + lift - 0.85 * hand,
                         c[2] + 0.98 * r[2] + 0.35 * hand) for s in ("left", "right")},
        "show": {"right": out("right", 1.15, -0.1, 0.4)},
        "halt": {"right": out("right", 0.6, 0.3, 1.0)},
        "thumb": {"right": out("right", 0.7, 0.2, 0.8)},
        "soso": {"right": out("right", 0.75, 0.0, 0.7)},
        "count": {"right": out("right", 0.65, 0.55, 0.55)},
    }
    if kind.startswith("reach@"):   # an arm to a point given from its shoulder: metres out, up and forward
        dx, dy, dz = (float(v) for v in kind[6:].split(","))
        targets = {"right": off("right", dx, dy, dz)}
    else:
        targets = named[kind]
    stretch = {}
    for side, point in targets.items():
        far = Vec3.of(point)
        if kind.startswith("reach@") and (far - sh[side]).length > 0.97 * L:
            # further than the arm goes: the hand goes as far as it can that way, and the arm is drawn the rest
            point = sh[side] + _scaled(far - sh[side], 0.97 * L / (far - sh[side]).length)
        # short mascot arms may not reach (a hand to the chin past a round belly): stop as near as they can
        f.reach_to(f"{side}_hand", point, tolerance=SPECS[who].reach, pole=out(side, 0.6, -0.6, -0.6))
        # ... and how much longer the arm must be drawn for the paw to arrive (MascotFigure.arm_left / arm_right)
        if kind != "rest":  # beyond the straight arm's length, the arm is drawn longer by the difference
            stretch[side] = max(1.0, min(SPECS[who].stretch, (far - sh[side]).length / L))
    _STRETCH[(who, kind)] = stretch
    keep = ("_shoulder.", "_upper_arm.", "_lower_arm.", "_hand.")
    controls = {k: v for k, v in f.values().items() if any(x in k for x in keep)}
    _GESTURES[(who, kind)] = controls
    return controls


# a seated figure's legs (Pose.extras "sit"); grounded, it rests on its seat and the backs of its legs
SIT = {"upper_leg.front_back": -82.0, "upper_leg.in_out": 22.0, "upper_leg.twist_in_out": 8.0,
       "lower_leg.stretch": -4.0, "foot.up_down": 10.0}


def controls(who: str, pose: Pose) -> dict[str, float]:
    if pose.arms == "run":  # the skeleton's own running pose
        return {**dict(BODY_POSES["run"]), **dict(pose.joints)}
    c = {**RELAXED, **gesture(who, pose.arms if pose.arms in ("rest", "present", "point", "raise", "chin", "shrug",
                                                               "panic", "cuddle") else "rest")}
    c.update(SPECS[who].stance)
    if "sit" in pose.extras:  # seated on the floor or a step: legs out in front, a little apart, soles forward
        for side in ("left", "right"):
            c.update({f"{side}_{k}": v for k, v in SIT.items()})
    c["spine.left_right"] = max(-12.0, min(12.0, pose.tilt))
    if SPECS[who].face == "head":  # a head of its own tilts with the pose (on top of the stance's tilt)
        c["head.tilt_left_right"] = max(-20.0, min(20.0, SPECS[who].stance.get("head.tilt_left_right", 0.0) - pose.tilt))
    c.update(dict(pose.joints))
    return c


def figure(who: str, pose: str | Pose = "idle", **kw) -> MascotFigure:
    p = POSES[who][pose] if isinstance(pose, str) else pose
    return MascotFigure(pose=controls(who, p), expression=p, who=who, **kw)


# ----------------------------------------------------------------------------- renders (dev3d's look and paper)
def _stage(name: str) -> Location:
    loc = stage(name)
    register(loc.registry)
    return loc


def view(who: str, pose, yaw: float, out: Path, width: int = 480, height: int = 800) -> Path:
    loc = _stage(f"{who}-view")
    loc.add(figure(who, pose, name=who, yaw=yaw))
    h = SPECS[who].build.height
    loc.shot("full", (0, 0.56 * h, 19 * h / 1.15), (0, 0.56 * h, 0), lens=210)  # room for a raised arm
    return render(loc, "full", out, width, height, LOOKS[who]() if who in LOOKS else None)


def closeup(who: str, pose, out: Path) -> Path:
    loc = _stage(f"{who}-closeup")
    loc.add(figure(who, pose, name=who))
    (c, r, _m) = SPECS[who].head or SPECS[who].body
    y = c[1] + 0.15 * r[1]
    loc.shot("face", (0, y, 3.2 * 0.75), (0, y, 0), lens=110)
    return render(loc, "face", out, 900, 900, LOOKS[who]() if who in LOOKS else None)


def turnaround(who: str, out: Path, pose="idle") -> Path:
    tiles = [view(who, pose, yaw, out.parent / f".{who}-view-{i}.png") for i, (_l, yaw) in enumerate(VIEWS)]
    labels = ";".join(f"[{i}]drawtext=fontfile={FONT}:text='{label}':x=(w-tw)/2:y=h-48:fontsize=30:fontcolor=0x141414[t{i}]"
                      for i, (label, _y) in enumerate(VIEWS))
    graph = labels + ";" + "".join(f"[t{i}]" for i in range(len(VIEWS))) + f"hstack={len(VIEWS)}"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *[a for t in tiles for a in ("-i", str(t))], "-filter_complex", graph,
                    str(out)], check=True)
    for t in tiles:
        t.unlink()
    return out


NAMES: dict[str, str] = {}         # who -> the name on its sheet; plush3d fills it


def sheet(who: str, out: Optional[Path] = None) -> Path:
    """The full set from the one model: canonical poses and its own, the mouth chart, the turnaround."""
    out = out or ROOT / "sheets" / f"{who}.png"
    work = ROOT / "sheets" / "3d"
    work.mkdir(parents=True, exist_ok=True)
    poses = [(name, view(who, name, 330 if POSES[who][name].arms == "run" else 0, work / f".{who}-pose-{i}.png"))
             for i, name in enumerate(POSES[who])]
    a = _grid(poses, 6, work / f"{who}-poses.png", f"{NAMES.get(who, who)}  -  3D model  -  poses")
    mouths = []
    for i, m in enumerate(MOUTHS):
        raw = closeup(who, Pose(mouth=m), work / f".{who}-mouth-raw-{i}.png")
        tile = work / f".{who}-mouth-{i}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-vf",
                        "scale=480:480,pad=480:540:0:0:color=0xF1F0EA", str(tile)], check=True)
        raw.unlink()
        mouths.append((m, tile))
    b = _grid(mouths, 6, work / f"{who}-mouths.png", "mouths (lip-sync)")
    c = turnaround(who, work / f"{who}-turnaround-idle.png")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(a), "-i", str(b), "-i", str(c), "-filter_complex",
                    "[2]scale=2880:-1[c];[0][1][c]vstack=3", str(out)], check=True)
    for _l, t in poses + mouths:
        t.unlink()
    return out



def main() -> int:
    what = sys.argv[1] if len(sys.argv) > 1 else "sheet"
    if what == "sheet":
        for who in sys.argv[2:] or list(SPECS):
            print("wrote", sheet(who))
    elif what == "view":
        print("wrote", view(sys.argv[2], sys.argv[3], float(sys.argv[4]), Path(sys.argv[5])))
    return 0


if __name__ == "__main__":
    sys.exit(main())

cast_stage = _stage      # the public name: a location lit for the look, with every family's colours registered
#                          (not `stage`: that is the kit's, which `_stage` itself calls)
