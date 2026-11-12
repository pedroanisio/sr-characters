"""Low-poly people: grown-ups of heroic build, modelled on a reference sheet (front, profile, back), a third family
beside the plush animals and the vinyl toys (the operator, 2026-11-11: "a referencia para se modelar eh a imagem";
"tudo tem que ser feito de maneira a construir o SDK e gerar componentes reutilizaveis").

A person stands on the family's skeleton, so every pose, action, gaze, lip-sync and `characters.film` call works,
and draws all of itself (`mascots3d.WHOLE`), as the robots and the vinyl people do. It is made of parts that are
written once and shared:

- the BODY (`_body`): legs and shoes, hips, waist, chest, sleeves, bare arms, hands with four fingers and a thumb,
  neck, head, jaw, ears, hair, eyes, brows, nose, mouth. Its measures are shares of the height read off the sheet
  (`BUILD` and the tables below), so a taller or shorter person is another `Build`, not another model. A build
  (`BODIES`: `man` and `woman`, heroic toys with a large head; `tall`, an adult) also says how large its head is
  and how far up it carries it (`Body.head`, `head_up`, `up`): the head and all it carries, a hat too, are sized
  with it, and the trunk and the hips are drawn on the man's heights, so an outfit fits every build as it is.
- an OUTFIT (`OUTFITS`): what a profession wears and carries over that body. `officer` is the pilot: peaked cap,
  collar, placket, pockets, epaulettes, badge, belt with buckle, pouches and a radio. `cook` is the second: a
  toque, a double-breasted jacket with long sleeves, a neckerchief, a waist apron. `firefighter` is the third: a
  helmet, a turnout coat with reflective bands round the chest, forearms and shins. `suit` is the fourth, and has
  no hat: a jacket (`_jacket`: its body is a `_coat`, one shell with six rings and large facets that lies on the
  trunk, which is drawn slimmer under it, and hangs off the hips to a hem over where the legs part; taken in at
  the waist, its shoulders out to the arms, open in front below its one round button, carried by the chest and
  the hips between them; notched lapels that cross at the button, a low collar round the back of the neck, flat
  flap pockets, a seam down the back, sleeve buttons) over a shirt (`_open_collar` closed: two wings that frame
  the knot; `_shirt_bib`, `_shirt_cuffs`) and a tie (`_tie`), trousers that have turn-ups if the person does
  (`Person.turn_ups`, `_turn_ups`). Each of those is a part of its own: a lawyer, a presenter, a groom are the
  same parts in other colours, or some of them (a tie on a shirt with no jacket, a jacket over other trousers).
- a FACE (`FACES`, picked with `Person.face`): the head's planes and what is drawn on them, as one table (`Face`):
  the skull's sections, the eyes (place, opening, outline, iris, a lid that rests part way down), the brows (a bar
  of hair, or an outline of their own), the nose (a wedge, or one with wings and nostrils), the mouth (a painted
  line, or modelled `Lips`), the ears. With none a person has the kit's first face on its build's own skull;
  "lean" is the anchor's. A face is in the head's own measures, so it goes on any build and is sized with its
  head, and every face speaks the whole vocabulary of eyes, brows and mouths. What a face draws that no stack of
  sections makes is a `_shell` (corner by corner) or a `_ribbon` (a strip that follows the face's planes).
- HAIR for a bare head (`HAIR_TOPS`, picked with `Person.hair_style`): a top over the build's own hair ("brushed"),
  or a whole head of hair (`Hair`: "swept": sides with sideburns, a top with a hairline that runs down the back
  of the head in a V), in one colour or two (`Person.temples`).
- a `Person`: a name, an outfit, colours and a few options of its own: its hair when it wears no hat
  (`hair_style`, HAIR_TOPS, with `temples` for sides of another colour), how heavy its brows are (`brow`), how low
  its shoes (`shoe`) and the colour of their soles. Another profession is another `Person` and, if its clothes
  differ, another outfit function; nothing of the body is written again. `anchor` is the tall build in the suit,
  bare-headed, with the "lean" face and "swept" hair, grey at the temples. `enlist(person)` puts a Person in the cast, the kit's
  own and one made at run time alike.

Shapes are `Loft`s: sections stacked along a height or along a bone, each an octagon unless it says otherwise
(`profile=`), whose corners the finish keeps exactly and whose sides it can break into irregular facets
(`facet=`, `crease=`). What lies on one (a pocket, a badge, a belt, a stripe, a hat's band, the face) is placed
with `Loft.seat`, `Loft.around`, `Loft.band`, `Parts.flat` and `Parts.hung`, so it sits on the facets in every view;
cloth that lies on one and follows it (a lapel, a shirt's front, a tie's blade, a seam) is a `_panel`.

Sizes come from measuring against the sheet, not from the eye: `characters/tools/lowpoly/round.sh` prints the outline
match, the centimetres each body band is off, and a surface score. Change a table, run it, read the numbers.

Draw it with `finish="lowpoly"` (characters.blender): every part becomes a few flat facets that ride the figure.

    PY=/home/dev/src/viral-video-orchestrator/.venvs/srlocations/bin/python
    $PY characters/lowpoly3d.py proof [who]    # examples/out/lowpoly-<who>.png: front, profile, back (any of PEOPLE)
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from dataclasses import replace as _replace
from pathlib import Path
from typing import Callable

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "characters"

from srlocations.geometry import Vec3, rotation  # noqa: E402
from srlocations.stock.mannequin import Build, Limb  # noqa: E402

from . import mascots3d as m  # noqa: E402
from . import plush3d  # noqa: E402
from .kit import cross, scaled, shape, tube, unit  # noqa: E402
from .poses import CANON, PLUSH_SEATED, POSES  # noqa: E402

COLOURS = {
    "lp.skin": "#EE9C5E", "lp.skin-shade": "#CE7C46", "lp.hair": "#3A2823", "lp.white": "#F7F3EE",
    "lp.iris": "#3A2416", "lp.shoe": "#423E3E", "lp.sole": "#2B2828",
    "lp.eye": "#4E2D1B", "lp.pupil": "#17100E",       # an eye's brown iris and its pupil, matte (lp.iris is a dark bead)
    "lp.tooth": "#F4EFE6",                            # teeth, matte (lp.white is a gloss, for an eye's white and its light)
    "lp.navy": "#34336C", "lp.navy-dark": "#282755", "lp.leather": "#3B3636", "lp.gold": "#F5A93A",
    "lp.steel": "#8A8686", "lp.button": "#8F8389",
    # a second skin and hair, and the cook's whites
    "lp.skin-brown": "#B9703F", "lp.skin-brown-shade": "#965530", "lp.hair-black": "#231815",
    "lp.jacket": "#F2EEE6", "lp.apron": "#DDD6C8", "lp.check": "#5A5F6B", "lp.red": "#C8322B", "lp.black": "#2A2828",
    # the firefighter's turnout coat, its reflective bands, the helmet and the boots
    "lp.coat": "#2E303E", "lp.lime": "#C6E83A", "lp.helmet": "#C22A22", "lp.boot": "#D9A91E",
    # what a uniform carries: a cap's band and its dark peak (satin, characters.cloth: matte with a soft light on it;
    # as a gloss the low-poly finish makes it a mirror, white in the light), the slots of a radio's speaker, and a badge and a buckle as the sheet paints
    # them, flat and bright (lp.gold and lp.steel are mirrors too, which go dark in a studio)
    "lp.band": "#786B77", "lp.patent": "#221D1F", "lp.slot": "#1B1818", "lp.brass": "#F6AE3C", "lp.pewter": "#857B7E",
    # a suit and who wears it: a shirt (matte: lp.white is a gloss), a tie, brown dress shoes and their darker sole, a
    # third skin, dark hair that is grey at the temples, a darker eye
    "lp.suit": "#2B2A52", "lp.suit-dark": "#201F40", "lp.shirt": "#F6EFE8", "lp.orange": "#E2631C",
    "lp.shoe-brown": "#6A3B25", "lp.sole-brown": "#3A2217", "lp.skin-tan": "#CC7A44", "lp.skin-tan-shade": "#A25B30",
    "lp.hair-dark": "#352A2B", "lp.hair-grey": "#7A6E6B", "lp.eye-dark": "#33190E",
    # skin in deep shade, any skin's: the line between two lips, a fold (Lips.ink)
    "lp.crease": "#5C2E1D", "lp.eye-deep": "#47210E",       # (and a warm dark iris, for an eye that is nearly all iris)
}
m.COLOURS.update(COLOURS)


CREASE, FACET = 14.0, 80.0             # cloth breaks into facets up to this deep and about this large (millimetres)
SKIN_CREASE, SKIN_FACET = 7.0, 65.0    # and bare skin over muscle: shallower and smaller
SEAT_CREASE = 11.0                     # cloth that pockets, buttons and a badge are seated on: they would stand off deeper dents
HAT_CREASE = 8.0                       # the cloth of a hat, which is stiffer (and carries a badge)
FLAT = 0.6             # how much of a section's width and depth is flat (see Loft)
# a limb's outline (Loft `profile`): six sides, a flat at each side and a crease down the front and the back, so
# its sides are half as wide again as an octagon's and its facets as large as the sheet's
HEX = ((1.0, 0.45), (0.0, 1.0), (-1.0, 0.45), (-1.0, -0.45), (0.0, -1.0), (1.0, -0.45))
LEG_STAGGER, ARM_STAGGER = 0.014, 0.008     # how far a limb's rings zigzag (Loft `stagger`), metres
# how a limb is drawn (Parts.span): six sides, rings that zigzag, and facets so large that each stretch of a side
# between two rings is cut once, corner to corner (it is not flat, its corners being staggered: a real fold)
LEG = dict(profile=HEX, stagger=LEG_STAGGER, facet=180.0)
SLEEVE = dict(profile=HEX, stagger=ARM_STAGGER, facet=180.0)
BARE = dict(profile=HEX, stagger=ARM_STAGGER, crease=SKIN_CREASE, facet=130.0)


class Loft:
    """A part whose shape is drawn as sections stacked along its height, as a tailor's block or a turned leg is:
    each section is (y, half width, half depth, how far forward its middle is[, flat]), in the rest pose.

    A section is an octagon: a flat front, back and sides joined by four chamfers; `flat` is the share of the
    width and of the depth that is flat (0.41 a regular octagon, 1 a box, 0 a diamond). Between sections the
    surface runs straight. The part is `drawn`: the low-poly finish keeps exactly these corners, so whatever is
    placed with `front`, `seat`, `around` or `band` lies on its facets, neither sunk in them nor floating.

    A section may have another outline than the octagon: `profile` gives its corners (x, z) as shares of the half
    width and the half depth, round from the picture's left of the front as `ring` gives them (HEX is one), for
    every section; a section whose fifth value is such a list of corners instead of a `flat` has its own (all
    with as many corners), so a part's outline can change along it, as a face's planes do. Fewer corners are
    fewer and wider sides, hence larger facets. `stagger` (metres) moves every other corner of the sections
    between the two ends up and the others down, the other way on the next section, so the rings that the
    sections draw round a limb zigzag instead of lying level one above the other."""

    def __init__(self, sections, flat: float = FLAT, crease: float = 0.0, facet: float = FACET, profile=None,
                 stagger: float = 0.0):
        own = lambda x: len(x) > 4 and not isinstance(x[4], (int, float))        # noqa: E731
        rows = sorted(((*x[:4], flat if len(x) < 5 or own(x) else x[4]),
                       tuple((float(a), float(b)) for a, b in x[4]) if own(x) else profile and tuple(profile))
                      for x in sections)
        self.s = [r[0] for r in rows]                 # (y, half width, half depth, forward, flat)
        self.o = [r[1] or None for r in rows]         # each section's own corners; None: the octagon its `flat` makes
        self.flat, self.profile, self.stagger = flat, profile and tuple(profile), stagger
        self.sides = len(next((o for o in self.o if o), ())) or 8
        if any(o and len(o) != self.sides for o in self.o) or (any(self.o) and not all(self.o) and self.sides != 8):
            raise ValueError("a loft's sections all have as many corners")
        # millimetres: its sides break into irregular facets about `facet` across and up to `crease` deep, as cloth
        # does (0: they stay as drawn). Its corners and the edges between them do not move.
        self.crease, self.facet = crease, facet

    @staticmethod
    def octagon(f: float):
        """The corners of the octagon whose flat share is `f`, as shares of the half width and half depth."""
        return ((1.0, f), (f, 1.0), (-f, 1.0), (-1.0, f), (-1.0, -f), (-f, -1.0), (f, -1.0), (1.0, -f))

    def _corners(self, i: int):
        return self.o[i] or self.octagon(self.s[i][4])

    def shape(self, y: float):
        """The section's outline at height y: its corners as shares of the half width and the half depth."""
        s = self.s
        if y <= s[0][0]:
            return self._corners(0)
        for i in range(len(s) - 1):
            if y <= s[i + 1][0]:
                t = (y - s[i][0]) / (s[i + 1][0] - s[i][0])
                return tuple((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
                             for a, b in zip(self._corners(i), self._corners(i + 1)))
        return self._corners(len(s) - 1)

    def at(self, y: float):
        """(half width, half depth, forward, flat) at height y."""
        s = self.s
        if y <= s[0][0]:
            return s[0][1:]
        for a, b in zip(s, s[1:]):
            if y <= b[0]:
                t = (y - a[0]) / (b[0] - a[0])
                return tuple(a[i] + (b[i] - a[i]) * t for i in (1, 2, 3, 4))
        return s[-1][1:]

    def ring(self, y: float):
        """The section's corners (x, z) at height y (eight for an octagon), round from the picture's left of the front."""
        rx, rz, zc, f = self.at(y)
        if not any(self.o):
            return [(rx, zc + f * rz), (f * rx, zc + rz), (-f * rx, zc + rz), (-rx, zc + f * rz),
                    (-rx, zc - f * rz), (-f * rx, zc - rz), (f * rx, zc - rz), (rx, zc - f * rz)]
        return [(rx * a, zc + rz * b) for a, b in self.shape(y)]

    @staticmethod
    def _reach(ring, at: float, axis: int, far=max) -> float:
        """How far the outline `ring` reaches along the other axis where its coordinate `axis` is `at` (clamped to
        the outline): its front at an x, its side at a z; with `far=min`, its back at an x."""
        lo, hi = min(p[axis] for p in ring), max(p[axis] for p in ring)
        at = max(lo, min(hi, at))
        best = None
        for a, b in zip(ring, ring[1:] + ring[:1]):
            a0, b0 = a[axis], b[axis]
            if min(a0, b0) - 1e-12 <= at <= max(a0, b0) + 1e-12:
                t = 0.0 if abs(b0 - a0) < 1e-12 else (at - a0) / (b0 - a0)
                for v in ((a[1 - axis], b[1 - axis]) if abs(b0 - a0) < 1e-12 else (a[1 - axis] + (b[1 - axis] - a[1 - axis]) * t,)):
                    best = v if best is None else far(best, v)
        return best

    def front(self, x: float, y: float, lift: float = 0.0) -> float:
        """z of the front surface at (x, y), plus `lift`."""
        rx, rz, zc, f = self.at(y)
        if any(self.o):
            return self._reach(self.ring(y), x, 0) + lift
        over = (abs(x) - f * rx) / max(1e-9, rx - f * rx)
        return zc + rz * (1.0 - (1.0 - f) * max(0.0, min(1.0, over))) + lift

    def back(self, x: float, y: float, lift: float = 0.0) -> float:
        """z of the back surface at (x, y), `lift` out of it (further back): where a seam down a back lies."""
        rx, rz, zc, f = self.at(y)
        if any(self.o):
            return self._reach(self.ring(y), x, 0, min) - lift
        over = (abs(x) - f * rx) / max(1e-9, rx - f * rx)
        return zc - rz * (1.0 - (1.0 - f) * max(0.0, min(1.0, over))) - lift

    def side(self, z: float, y: float, lift: float = 0.0) -> float:
        """x of the side surface (the picture's left; the other side is its mirror) at depth z and height y, plus
        `lift`: where an ear, a sideburn, a stripe down a seam lies."""
        rx, rz, zc, f = self.at(y)
        if any(self.o):
            return self._reach(self.ring(y), z, 1) + lift
        over = (abs(z - zc) - f * rz) / max(1e-9, rz - f * rz)
        return rx * (1.0 - (1.0 - f) * max(0.0, min(1.0, over))) + lift

    def seat(self, x: float, y: float, lift: float = 0.0):
        """Where a flat thing lies on the front at (x, y): its place, `lift` out of the facet, and the turn that
        lays it flat on that facet."""
        d = 0.002
        yaw = math.degrees(math.atan2(self.front(x - d, y) - self.front(x + d, y), 2 * d))
        pitch = math.degrees(math.atan2(self.front(x, y - d) - self.front(x, y + d), 2 * d))
        n = rotation(yaw, pitch, 0)
        return (x + n[0][2] * lift, y + n[1][2] * lift, self.front(x, y) + n[2][2] * lift), n

    def around(self, deg: float, y: float, out: float = 0.0):
        """Where a thing hangs on the part's side at height y, `deg` round from the front toward the picture's
        left: its place, `out` off the facet, and the turn (degrees of yaw) that faces it outward."""
        zc = self.at(y)[2]
        a = math.radians(deg)
        dx, dz = math.sin(a), math.cos(a)
        ring = self.ring(y)
        for (x0, z0), (x1, z1) in zip(ring, ring[1:] + ring[:1]):
            ex, ez = x1 - x0, z1 - z0
            den = dx * ez - dz * ex
            if abs(den) < 1e-12:
                continue
            t = (x0 * ez - (z0 - zc) * ex) / den
            w = (x0 * dz - (z0 - zc) * dx) / den
            if t > 0 and -1e-9 <= w <= 1 + 1e-9:
                nx, nz = unit(Vec3(-ez, 0.0, ex)).x, unit(Vec3(-ez, 0.0, ex)).z
                if nx * dx + nz * dz < 0:
                    nx, nz = -nx, -nz
                return (dx * t + nx * out, y, zc + dz * t + nz * out), math.degrees(math.atan2(nx, nz))
        return (0.0, y, zc), 0.0

    def band(self, y0: float, y1: float, out: float) -> "Loft":
        """A band round this part from y0 to y1, `out` off its facets: a belt, a stripe, a hat's band, a collar."""
        ys = [y0, *(x[0] for x in self.s if y0 < x[0] < y1), y1]
        own = (lambda y: self.shape(y)) if any(self.o) else (lambda y: self.at(y)[3])     # the same outline, further out
        return Loft([(y, *(lambda rx, rz, zc, f: (rx + out, rz + out, zc))(*self.at(y)), own(y)) for y in ys], self.flat)

    def limb(self, name: str, carry, material: str, looks, tilt=m.IDENTITY, move=(0.0, 0.0, 0.0)) -> Limb:
        """The part, carried by a bone; `move` puts it somewhere else than where its sections were drawn, and
        `tilt` turns it about its middle."""
        lo, hi = self.s[0], self.s[-1]
        s = [(lo[0] - 0.0005, 0.001, 0.001, lo[3], lo[4]), *self.s, (hi[0] + 0.0005, 0.001, 0.001, hi[3], hi[4])]
        mid = (s[0][0] + s[-1][0]) / 2

        def line(value, shift=0.0):      # a value that runs straight from section to section as v counts them
            out = f"{value(s[0]) - shift:.5f}"
            for i in range(1, len(s)):
                d = value(s[i]) - value(s[i - 1])
                if abs(d) > 1e-9:
                    out += f"+({d:.5f})*min(max(v-{i - 1},0),1)"
            return "(" + out + ")"

        f = line(lambda x: x[4])
        side = "min(max((abs(cos(u))-abs(sin(u)))*1000,0),1)"        # 1 on the two corners of a side, 0 on the others
        reach = (max(x[1] for x in s), (s[-1][0] - s[0][0]) / 2, max(x[2] + abs(x[3]) for x in s))
        n = self.sides
        # how far a corner of a section is moved along the part (`stagger`): none at its two ends
        lifted = lambda j, i: self.stagger * (-1 if (i + j) % 2 else 1) if 0 < j < len(self.s) - 1 else 0.0   # noqa: E731
        role = "drawn"
        if self.crease:
            # "facet:<across>:<deep>:<sides>:<bands>" (mm): with the size of its facets, how wide each of its
            # sides is and how long each band between two sections (0 for its closed ends). The finish cuts the
            # sides by these, which are the same on every frame, so no facet comes or goes as the figure moves.
            rings = [[(px, x[0] + lifted(j, i), pz) for i, (px, pz) in enumerate(self.ring(x[0]))] for j, x in enumerate(self.s)]
            bands = [sum(math.dist(a, b) for a, b in zip(lo_, hi_)) / n for lo_, hi_ in zip(rings, rings[1:])]
            width = lambda ring, i: math.dist(ring[i], ring[(i + 1) % n])
            sides = [sum((width(a, i) + width(b, i)) / 2 * h for a, b, h in zip(rings, rings[1:], bands)) / sum(bands)
                     for i in range(n)]
            role += (f" facet:{self.facet:g}:{self.crease:g}:" + ",".join(str(round(w * 1000)) for w in sides)
                     + ":" + ",".join(["0", *(str(round(h * 1000)) for h in bands), "0"]))
        place = dict(v=(0, len(s) - 1), closed=(True, False), radii=reach, at=carry.point((move[0], mid + move[1], move[2])),
                     basis=carry.basis(tilt), name=name, material=material, role=role, casts_shadow=False, looks=looks)
        if not any(self.o) and not self.stagger:      # the octagon: its corners are where u is 22.5, 67.5, ... degrees
            return Limb(x=f"{line(lambda x: x[1])}*sign(cos(u))*({f}+(1-{f})*{side})", y=line(lambda x: x[0], mid),
                        z=f"{line(lambda x: x[3])}+{line(lambda x: x[2])}*sign(sin(u))*(1-(1-{f})*{side})",
                        u=(22.5, 382.5), samples=(8, len(s) - 1), **place)
        # any other outline: u counts the corners, and each corner's share of the half width and of the half depth
        # runs from section to section as the sizes do
        outline = [self._corners(0), *(self._corners(j) for j in range(len(self.s))), self._corners(len(self.s) - 1)]
        corner = lambda i: f"(max(1-abs(u-{i}),0)" + (f"+max(1-abs(u-{n}),0))" if i == 0 else ")")      # 1 on corner i  # noqa: E731

        def across(axis):
            terms = []
            for i in range(n):
                share = [o[i][axis] for o in outline]
                text = f"{share[0]:.5f}"
                for j in range(1, len(share)):
                    if abs(share[j] - share[j - 1]) > 1e-9:
                        text += f"+({share[j] - share[j - 1]:.5f})*min(max(v-{j - 1},0),1)"
                if text != "0.00000":
                    terms.append(f"({text})*{corner(i)}")
            return "(" + "+".join(terms or ["0"]) + ")"

        y = line(lambda x: x[0], mid)
        if self.stagger:        # +1 and -1 on alternate corners, the other way round on the next section
            zig = "+".join(f"({1 if i % 2 else -1})*{corner(i)}" for i in range(n))
            rows = "+".join(f"({1 if j % 2 else -1})*max(1-abs(v-{j + 1}),0)" for j in range(1, len(self.s) - 1)) or "0"
            y += f"+{self.stagger:.5f}*({zig})*({rows})"
        return Limb(x=f"{line(lambda x: x[1])}*{across(0)}", y=y, z=f"{line(lambda x: x[3])}+{line(lambda x: x[2])}*{across(1)}",
                    u=(0, n), samples=(n, len(s) - 1), **place)


class Span:
    """Carries a Loft along a bone, from joint `a` to joint `b`: the loft's y is metres from `a`, its z the
    bone's own front (`frame` is the bone as posed), so a limb's shape turns with the limb."""

    def __init__(self, a: Vec3, b: Vec3, frame):
        self.a, self.length = a, (b - a).length
        along = unit(b - a) if self.length > 1e-6 else Vec3(0, 1, 0)
        for col in (2, 0):
            f = Vec3(*(frame.basis[i][col] for i in range(3)))
            f = f - scaled(along, f.x * along.x + f.y * along.y + f.z * along.z)
            if f.length > 0.3:
                break
        f = unit(f)
        side = cross(along, f)
        self.m = ((side.x, along.x, f.x), (side.y, along.y, f.y), (side.z, along.z, f.z))

    def point(self, p) -> Vec3:
        r = self.m
        return self.a + Vec3(*(r[i][0] * p[0] + r[i][1] * p[1] + r[i][2] * p[2] for i in range(3)))

    def basis(self, b):
        return m._mul(self.m, b)


# The sheet's man, 1 m tall here (the plush are 0.7 m): hip joints 0.45 of the height above the ground, knees 0.25,
# the legs parting at 0.39, shoulders 0.70 and 0.22 wide at the joints, elbows 0.57, wrists 0.46, chin 0.775, the
# cap's peak 0.895: the head with its cap is 0.225 of him. Rest-pose joints: hips 0.473, chest 0.592, neck 0.776,
# head 0.829, shoulders 0.729 (x 0.108) before the stance lowers them by 0.019 (STANCE); standing, the hips come
# down 0.009 as the feet part. The arms are short for the skeleton (0.81): upper arm 0.151, forearm 0.119.
BUILD = Build(height=1.0, head=1.75, torso=0.95, legs=0.84, arms=0.81, shoulders=0.83, hips=1.08)
# sections read off the sheet's front (widths) and profile (depths): y, half width, half depth, forward
TRUNK = Loft([(0.512, 0.088, 0.066, 0.006), (0.532, 0.092, 0.074, 0.006), (0.556, 0.085, 0.073, 0.007),
              (0.60, 0.098, 0.078, 0.006), (0.645, 0.118, 0.089, -0.001), (0.68, 0.124, 0.087, -0.009),
              (0.705, 0.126, 0.079, -0.014), (0.733, 0.122, 0.067, -0.011), (0.745, 0.108, 0.06, -0.009),
              (0.753, 0.078, 0.054, -0.007), (0.771, 0.058, 0.047, -0.004), (0.786, 0.047, 0.042, -0.003)],
             flat=0.72, crease=SEAT_CREASE)
# (the shirt blouses out over the belt, then the waist, a front that is flat up to the chest's pockets and leans
# back from there to the collar, a back fullest at the shoulder blades, and shoulders that slope from a high collar)
# (the hips: the legs part 0.39 of the height up, and the seat is flat: 0.065 behind the hip joints, where the belly is 0.07 in front)
PELVIS = Loft([(0.394, 0.03, 0.034, 0.0), (0.418, 0.086, 0.057, 0.0), (0.45, 0.102, 0.07, 0.002),
               (0.49, 0.102, 0.068, 0.002), (0.535, 0.092, 0.066, 0.005)], flat=0.72, crease=SEAT_CREASE)
# how far the head and what it wears are carried above where their sections put them. The sheet's face is short
# under its cap (chin to peak 0.12 of the height, where it was first drawn 0.16), so the cap comes down by the
# difference and the skull's sections start higher: the chin stays on the collar.
HEAD_LIFT = -0.023
# the foot of the neck, in the collar: what a build's head is sized about (Body.head), the man's being drawn
NECK_FOOT = (0.0, 0.78 + HEAD_LIFT, 0.0)


def _bigger(sections, k: float, about: float = 0.78):
    """Sections grown by `k` about the height `about` (the neck) and lifted by HEAD_LIFT: a bigger head on a neck."""
    return [(about + (x[0] - about) * k + HEAD_LIFT, x[1] * k, x[2] * k, x[3] * k, *x[4:]) for x in sections]


HEAD_K = 1.02          # the head and its cap, against the sections as first measured
# the head by its planes (as the planes-of-the-head casts painters study): a chin that comes forward, a square jaw,
# cheekbones the widest, eyes set back under a brow that comes forward, a forehead that leans back to the crown
# (measured on the sheet: 0.148 of the height wide at the cheekbones and 0.158 deep with the hair, the face's front
# one upright plane from chin to brow before the head is carried back by the stance)
def face_planes(n: float, c: float, b: float, a: float, d: float = 0.6, e: float = 0.55):
    """A section of a head by its planes, ten corners (a Loft section's own outline): the front is flat `n` of the
    half width each side of the middle (the chin, the mouth, the bridge of the nose); a cheek's plane runs from
    there to the corner (c, b); a temple's from that to the side, which is flat from `a` in front to `d` behind;
    the back is flat over `e`."""
    return ((1.0, a), (c, b), (n, 1.0), (-n, 1.0), (-c, b), (-1.0, a), (-1.0, -d), (-e, -1.0), (e, -1.0), (1.0, -d))


# (the sections: under the chin, the chin, the cheekbones, the eyes' band, which is upright and set back between
# the cheekbones and the brow so an eye lies on one plane, the brow, the forehead, the crown. From the chin to the
# cheekbones the face is one set of planes: the front the mouth lies on, a cheek each side, the jaw. The chin
# stands forward of the cheekbones, and the head under its hair is narrower than the hair)
# (the bridge of the nose in the middle, and a socket each side of it that is turned out by some 20 degrees, so an
# eye shows from the side as well)
_EYES = face_planes(0.13, 0.7, 0.8, 0.1)
SKULL = Loft(_bigger([(0.798, 0.038, 0.03, 0.058, face_planes(0.55, 0.88, 0.8, 0.35)),
                      (0.816, 0.051, 0.048, 0.045, face_planes(0.5, 0.88, 0.8, 0.3)),
                      (0.857, 0.062, 0.07, 0.017, face_planes(0.42, 0.86, 0.78, 0.2)),
                      (0.871, 0.065, 0.07, 0.011, _EYES), (0.896, 0.065, 0.07, 0.011, _EYES),
                      (0.911, 0.067, 0.077, 0.012, face_planes(0.5, 0.84, 0.82, 0.25)),
                      (0.935, 0.065, 0.072, 0.006, face_planes(0.45, 0.82, 0.78, 0.25)),
                      (0.962, 0.054, 0.058, 0.0, face_planes(0.4, 0.8, 0.75, 0.3))], HEAD_K))
# hair's outline (a Loft's profile): sides that are flat far forward, to the temples, and a narrow back
HAIR_SHAPE = ((1.0, 0.8), (0.6, 1.0), (-0.6, 1.0), (-1.0, 0.8), (-1.0, -0.6), (-0.6, -1.0), (0.6, -1.0), (1.0, -0.6))
# his hair: over the back and the sides of the skull, from the nape up under whatever he wears on his head. Low
# down it is behind the ears only; from the ear's height up it comes forward to the temples, so its front edge
# runs from behind the ear's lobe up across the ear to the temple and leaves a sideburn in front of the ear
HAIR_SECTIONS = ((0.832, 0.044, 0.016, -0.036), (0.856, 0.06, 0.024, -0.036), (0.878, 0.068, 0.047, -0.023),
                 (0.905, 0.073, 0.0555, -0.0145), (0.935, 0.071, 0.0545, -0.0135), (0.962, 0.056, 0.045, -0.015))
HAIR = Loft(_bigger(HAIR_SECTIONS, HEAD_K), profile=HAIR_SHAPE)
# the hair on top of a bare head (Person.hair_style), over the build's own back and sides, which may be another
# colour (Person.temples). It starts on that hair's own ring at the top of the brow (HAIR_SECTIONS[-2], a hair
# wider), so the two are one surface with no ledge where the colour changes, at the sides and behind; in front
# that ring lies inside the head, at the temples, and the top leans forward from it to the hairline, which
# leaves the forehead bare.
# "brushed": short hair brushed up and back, with volume: it stands a little forward of the forehead over the
# hairline, is highest toward the front and falls away to the back, over the crown
_HAIR_RING = (HAIR_SECTIONS[-2][0], HAIR_SECTIONS[-2][1] + 0.0008, HAIR_SECTIONS[-2][2] + 0.0008, HAIR_SECTIONS[-2][3])


def hair_planes(s: float, c: float = 0.6, d: float = 0.6, e: float = 0.6):
    """A section of hair round a head, eight corners (as HAIR_SHAPE, which is hair_planes(0.8)): the sides are flat
    from `s` of the half depth in front to `d` behind; the front is flat over `c` of the half width (it lies in
    the head, or is the hair's edge at a temple) and the back over `e`."""
    return ((1.0, s), (c, 1.0), (-c, 1.0), (-1.0, s), (-1.0, -d), (-e, -1.0), (e, -1.0), (1.0, -d))


def crown_planes(s: float, c: float, f: float, d: float, e: float, b: float):
    """A section of the hair on top of a head, ten corners: hair_planes with a corner in the middle of the front
    and of the back as well, so a hairline can come to a peak and the hair's edge to a V behind. The front's
    corners are at (c, f) and the back's at (e, -b)."""
    return ((1.0, s), (c, f), (0.0, 1.0), (-c, f), (-1.0, s), (-1.0, -d), (-e, -b), (0.0, -1.0), (e, -b), (1.0, -d))


@dataclass(frozen=True)
class Hair:
    """A whole head of hair for a bare head (HAIR_TOPS), worn in place of the build's own. `sides` is the back and
    the sides (in Person.temples, where that is another colour): its front edge is the sideburn and the temple.
    `top` lies over it, sections of ten corners (crown_planes); its lowest ring is its hem, and `hem` says how far
    each corner of that ring is moved up (the hairline, over the forehead) or down: one that comes down lies on
    the sides' hair, which is how the top runs down the back of the head in a V. Its sections are as the head is
    drawn (no _bigger); `Loft.stagger` makes the rings of either zigzag, which is what breaks them into facets."""
    sides: Loft
    top: Loft
    hem: tuple


HAIR_TOPS = {
    "brushed": Loft(_bigger([_HAIR_RING, (0.9486, 0.0696, 0.0713, 0.0017), (0.9692, 0.0647, 0.073, 0.0044),
                             (0.9849, 0.0529, 0.0618, 0.0069), (0.9947, 0.0333, 0.0422, 0.0127)], HEAD_K),
                    profile=HAIR_SHAPE, crease=8.0, facet=45.0),
    # "swept": full hair swept up and back from a clear hairline. The sides stand well out of the head, widest
    # at the top of the temples, and narrow down to the ears; in front of an ear they end in a sideburn, behind
    # it they run down to the nape. The top stands forward of the hairline, is highest over the front third,
    # overhangs the sides a little and comes down the back of the head in a V. It is as tall as "brushed" (its
    # top at 0.976), so a head is the same height with either
    "swept": Hair(
        # (its back, off the sheet's profile: 0.088 behind the head's middle at the top of the sides, and in from
        # there to 0.047 at the nape)
        sides=Loft([(0.806, 0.0384, 0.0125, -0.0345, hair_planes(0.8)), (0.8314, 0.0576, 0.02, -0.04, hair_planes(0.8)),
                    (0.8511, 0.0653, 0.0285, -0.0405, hair_planes(0.8)), (0.8624, 0.0672, 0.048, -0.024, hair_planes(0.9, 0.94)),
                    (0.8897, 0.0749, 0.0535, -0.0225, hair_planes(0.93, 0.85)), (0.9198, 0.0802, 0.053, -0.023, hair_planes(0.47, 0.675)),
                    (0.9282, 0.073, 0.049, -0.023, hair_planes(0.47, 0.675))], stagger=0.003),
        # (behind, the sides stay inside the line from the point of the top's V up to the top's own back, so that the
        # top is proud of them all the way down the V)
        top=Loft([(0.9198, 0.0821, 0.078, -0.007, crown_planes(0.14, 0.62, 1.0, 0.45, 0.62, 0.96)),
                  (0.9395, 0.0739, 0.0845, -0.0005, crown_planes(0.2, 0.62, 0.96, 0.5, 0.62, 0.95)),
                  (0.9545, 0.0614, 0.0697, 0.0133, crown_planes(0.25, 0.6, 0.93, 0.5, 0.6, 0.93)),
                  (0.9686, 0.0442, 0.0538, 0.0162, crown_planes(0.25, 0.6, 0.93, 0.5, 0.6, 0.93)),
                  (0.9762, 0.0269, 0.0319, 0.0131, crown_planes(0.25, 0.6, 0.93, 0.5, 0.6, 0.93))], stagger=0.004),
        hem=(0.0, 0.016, 0.016, 0.016, 0.0, -0.004, -0.025, -0.055, -0.025, -0.004)),
}
# a peaked cap, drawn upright and worn tilted back (_peaked_cap): a band round the head over the brow; a crown that
# starts inside the band, flares out over it to a rim (widest at the sides and the back) and closes in a flat top
CAP_BAND = Loft(_bigger([(0.94, 0.0755, 0.081, 0.006), (0.96, 0.0765, 0.082, 0.006)], HEAD_K), flat=0.66)
# (its top comes to a narrow front edge, so that from the front the crown is a low gable, as the sheet's)
CAP_CROWN = Loft(_bigger([(0.954, 0.072, 0.077, 0.006), (0.994, 0.103, 0.088, 0.0, 0.5), (1.027, 0.078, 0.082, 0.006, 0.3)],
                         HEAD_K), flat=0.5, crease=HAT_CREASE)
CAP_TILT = 9.0         # the cap is worn tilted back: raised at the front, down over the hair behind (degrees)
CAP_RISE = 8.0         # and its crown is raised at the front that much more than its band
PEAK_DROP = 21.0       # the peak slopes down to the front (degrees below the head's level; the head is carried back)
TORSO = ((0.0, 0.668, 0.0), (0.134, 0.092, 0.092))      # the chest as one block, for what asks the body's size
# the ellipsoid the face is laid out on: its middle is the eyes' line, between the chin and the crown
HEAD = ((0.0, 0.78 + 0.103 * HEAD_K + HEAD_LIFT, 0.01 * HEAD_K), (0.073 * HEAD_K, 0.08 * HEAD_K, 0.075 * HEAD_K))
# the ears, as the sheet's profile and front have them: this far behind the head's middle and below the eyes' line,
# and turned out from the head by so many degrees, the back edge standing off it, so they show from the front
EAR_BACK, EAR_DROP, EAR_TURN = 0.008, 0.009, 32.0
BELT_Y = 0.5
BELT = PELVIS.band(BELT_Y - 0.02, BELT_Y + 0.02, 0.008)
# (an ear: a thick plate, its lobe narrow and forward, widest above its middle; and the hollow in its outer side,
# drawn in the skin's shade: (how far up the ear, half width, half thickness))
EAR = Loft([(-0.023, 0.003, 0.008, 0.004), (-0.01, 0.006, 0.016, 0.0), (0.011, 0.006, 0.021, -0.003), (0.023, 0.004, 0.014, -0.006)])
EAR_HOLLOW = ((-0.013, 0.003, 0.0012), (0.004, 0.011, 0.0012), (0.015, 0.005, 0.0012))
# a leg by its sections along the bone: share of its length, half width, half depth, forward
# (read off the sheet against the leg's bone: a trouser leg is deeper than it is wide; the thigh is full in front
# and narrows to just above the knee; the calf swells behind and to the sides; the hem stands forward on the boot)
# (few sections, unevenly spaced: each is a ring round the leg, and rings evenly stacked read as a grid)
THIGH = [(-0.12, 0.046, 0.05, 0.0), (0.22, 0.052, 0.059, 0.006), (0.55, 0.0495, 0.055, 0.0065), (0.88, 0.0415, 0.053, 0.002),
         (1.03, 0.044, 0.054, -0.0045)]
SHIN = [(-0.03, 0.044, 0.054, -0.0045), (0.2, 0.051, 0.055, -0.01), (0.52, 0.0435, 0.052, -0.002), (0.76, 0.047, 0.053, 0.006),
        (0.93, 0.049, 0.054, 0.006)]
KNEE = (0.036, 0.042, 0.044)                            # the ball that closes the knee, inside the two of them
ELBOW, SLEEVE_ELBOW = (0.032, 0.034, 0.036), (0.038, 0.038, 0.038)     # and the elbow, bare and in a long sleeve
# an arm the same way. A sleeve starts in the shoulder (its cap, above the joint); a short one ends in a hem that
# stands off the bare arm; a long one is fuller at the elbow and ends in a cuff
SLEEVE_CAP = [(-0.16, 0.03, 0.032, 0.0), (0.0, 0.045, 0.048, 0.0)]
SLEEVE_HEM = [(0.047, 0.052, 0.0), (0.05, 0.055, 0.0)]            # (half width, half depth, forward) part way and at the hem
SLEEVE_UPPER = [*SLEEVE_CAP, (0.45, 0.048, 0.05, 0.0), (1.04, 0.047, 0.047, 0.0)]
SLEEVE_FORE = [(-0.04, 0.047, 0.047, 0.0), (0.28, 0.051, 0.049, 0.0), (0.9, 0.036, 0.034, 0.0), (0.96, 0.039, 0.037, 0.0),
               (1.02, 0.039, 0.037, 0.0)]
# the bare arm: an upper arm that is fullest above the elbow (its first section is moved to the sleeve's hem), and
# a forearm that swells below the elbow and narrows to the wrist
ARM_UPPER = [(0.54, 0.041, 0.045, 0.0), (0.8, 0.041, 0.047, 0.0), (1.04, 0.038, 0.044, 0.0)]
ARM_FORE = [(-0.04, 0.038, 0.044, 0.0), (0.3, 0.042, 0.046, 0.0), (0.65, 0.034, 0.036, 0.0), (1.0, 0.026, 0.026, 0.0)]
SOFT, PILL = 0.66, 0.2                                  # exponents (kit.shape): a soft-cornered block; a flat end
SIT_DROP = 0.139                                        # rests a seated figure on its seat (the drop counts twice)
# he stands with his feet apart and his toes turned out a little, as on the sheet
STANCE = {"left_upper_leg.in_out": 6.0, "right_upper_leg.in_out": 6.0, "left_upper_leg.twist_in_out": 8.0,
          "right_upper_leg.twist_in_out": 8.0, "left_upper_leg.front_back": 6.0, "right_upper_leg.front_back": 6.0,
          # and upright: the trunk one straight line that leans back a little from the waist, the shoulders drawn
          # back and sloping down from the collar, the neck upright on it and the chin lifted
          # (measured on the joints: above 0 a part of the trunk leans back, a shoulder goes back or up, the head
          # tips back; the sheet's profile has the collar 1.5 cm behind the hips and the face's front leaning 11)
          "spine.front_back": 3.0, "chest.front_back": 0.0, "upper_chest.front_back": 0.0,
          "left_shoulder.front_back": 3.0, "right_shoulder.front_back": 3.0,
          "left_shoulder.down_up": -11.0, "right_shoulder.down_up": -11.0,
          "neck.nod_down_up": -3.0, "head.nod_down_up": 11.0}
# resting wrists, out from the hips as the sheet stands: where the arms are solved to before the stance lowers the
# shoulders and leans the trunk, which brings the wrists to 0.211 out, 0.458 up and 0.016 behind the hips: the
# elbow then lies 0.044 behind them and a little out, the forearm near upright, the hand within the thigh's depth
REST_HANDS = (0.255, 0.501, -0.006)
EYE_X, EYE_Y = 0.37, 0.0                                # an eye on the face, as shares of the head's radii
# an eye as the sheet draws it: a small almond, wider than it is tall, that is nearly all iris (the iris is as tall
# as the opening, so the white shows at its two sides), a pupil, one light, and a dark line of lashes along its top
EYE = (0.016, 0.009)                                    # half the opening's width and half its height, metres
IRIS, PUPIL, GLINT = 0.0096, 0.0045, 0.0022             # radii (the lids cut the iris, top and bottom)
# outlines of flat things (_plate), bottom to top: (share of the half height, share of the half width)
ALMOND = ((-1.0, 0.42), (-0.3, 1.0), (0.4, 0.88), (1.0, 0.4))
ROUND = ((-1.0, 0.41), (-0.41, 1.0), (0.41, 1.0), (1.0, 0.41))
# the nose, a wedge that leads the profile, from under its tip up to the bridge between the eyes: (height from the
# eyes' line, half its width on the face, how far it stands out of the face, the share of that width its ridge keeps)
NOSE = ((-0.037, 0.013, 0.004, 0.5), (-0.025, 0.021, 0.027, 0.4), (0.013, 0.006, 0.004, 0.8))
MOUTH_X, MOUTH_Y = 0.5, -0.58                           # half the mouth's width and its height, shares of the head's radii
# which mouths fold the cheek at a corner, and how much: the picture's right, then its left
FOLDS = {"smile": (1.0, 1.0), "smug": (0.0, 1.0)}


# ----------------------------------------------------------------------------- faces: a choice per person
@dataclass(frozen=True)
class Lips:
    """A mouth that is modelled instead of painted (Face.lips): a dark line between an upper lip, a plane in the
    skin's shade, and a fuller lower lip that stands out of the face, in the skin's own colour, so the light
    models it. It speaks the same vocabulary as the painted line (expression.MOUTHS) and opens with the voice."""
    upper: float = 0.0038           # how tall the upper lip is at its fullest, metres
    lower: float = 0.0056           # and the lower lip
    proud: float = 0.0028           # how far the lower lip's ridge stands out of the face
    line: float = 0.001             # half the thickness of the line between them, in its middle
    bend: float = 0.6               # how far the line bends (smug, a frown, wavy): a share of the painted mouth's
    smile: float = 0.28             # and for a smile, which is what the mouth rests in: a slight one
    skew: float = 0.025             # a lopsided smile: the corner on the picture's left is raised this much more
    ink: str = "lp.crease"          # the line between the lips: skin in deep shade
    folds: tuple = (("smile", (0.45, 1.0)), ("smug", (0.0, 1.0)))     # as FOLDS: the picture's right, its left


@dataclass(frozen=True)
class Face:
    """A face: the head's planes and what is drawn on them. A person picks one by name (Person.face, FACES); with
    none it has this one, the kit's first, on its build's own skull. Its measures are the head's own (shares of
    HEAD's radii across and up the face, metres on the head as it is drawn), so a face is carried by the head and
    is sized with it on any build, and every face speaks the whole vocabulary of eyes, brows and mouths."""
    skull: Loft | None = None       # the head by its planes; None: the build's (Body.skull)
    # eyes: where they are, the opening (half width, half height), its outline, the iris, the pupil, the light
    eye_x: float = EYE_X
    eye_y: float = EYE_Y
    eye: tuple = EYE
    eye_shape: tuple = ALMOND
    iris: float = IRIS
    pupil: float = PUPIL
    glint: float = GLINT
    lid: float = 0.0                # a heavy upper lid: how far down it rests over the eye (0 not at all, 1 shut)
    slant: float = 0.0              # degrees the eye's outer corner is raised above its inner one
    wide: float = 1.32              # how much taller the opening is when the eyes are wide
    # the lashes' dark line lies along the lid and comes down the eye's two sides: as far below the lid as this
    # share of the opening's half height, and no lower than this share of it from its middle (-1 its bottom)
    lash: tuple = (0.6, -0.2)
    # brows: where their middle is and half their length (shares); None draws a bar of hair bent once, rows
    # (BROW_*) a brow with its own outline; `brow_down` is how much of a pose's lowering it takes (it is set low)
    brow_at: tuple = (EYE_X + 0.02, 0.3, 0.26)
    brows: tuple | None = None
    brow_down: float = 1.0
    # the nose (NOSE's rows; a fifth value gives it wings, see _nose), and how large its nostrils are (metres)
    nose: tuple = NOSE
    nostril: float = 0.0
    # the mouth: half its width and its height (shares); None paints a line, Lips models it
    mouth_x: float = MOUTH_X
    mouth_y: float = MOUTH_Y
    lips: Lips | None = None
    # the ears: how far behind the head's middle and below the eyes' line of the head, how far turned out, how large
    ear_back: float = EAR_BACK
    ear_drop: float = EAR_DROP
    ear_turn: float = EAR_TURN
    ear: float = 1.0
    ear_out: float = 0.001          # how far out of the skull's side an ear is set (hair that stands out would bury it)


FACE = Face()          # what a person with no face of its own has
# an eye's outline that comes to a point at both corners (as ALMOND: bottom to top), for an eye under a heavy lid
LENS = ((-1.0, 0.22), (-0.6, 0.74), (-0.05, 1.0), (0.5, 0.82), (1.0, 0.3))
# a heavy brow, set low: rows from its inner end, by the nose, to its outer end: (share of its length, its lower
# edge, its upper edge), the edges in shares of the head's half height from the line through its two ends. It is
# thickest by the nose (12 mm), its top rises a little to an arch two thirds of the way out, and from there it
# comes down to a point
BROW_HEAVY = ((0.0, -0.085, 0.061), (0.15, -0.08, 0.08), (0.69, -0.015, 0.098), (1.0, -0.07, -0.052))
# the "lean" face, read off the anchor's sheet: longer from the eyes to the chin than the first and narrower (its
# width 0.59 of the head's height with the hair, the first's 0.66); a jaw that runs straight down from the
# cheekbones to a corner under the mouth and from there in to a chin with a flat front; the eyes 8 mm higher on
# the head, level with the tops of the ears, dark, nearly all iris; a band for them that ends in a sharp rim under
# the brow, where thick brows lie low over them, heaviest by the nose; a nose with a narrow flat ridge, side
# planes, and wings and nostrils at its base; modelled lips in a lopsided smile; a higher forehead that leans
# back; larger ears set further back. The head is as tall as the first's, from the same chin (0.775) to the same
# top of the hair (0.976, with HAIR_TOPS["swept"] as with "brushed"), so a build's head size (Body.head) means
# the same with either face. Sections as the skull's are, here as the head is drawn (no _bigger): y, half
# width, half depth, forward, planes
LEAN_SKULL = Loft([(0.775, 0.0226, 0.0182, 0.0595, face_planes(0.6, 0.9, 0.8, 0.3)),
                   (0.7863, 0.0357, 0.0304, 0.053, face_planes(0.55, 0.88, 0.82, 0.2)),
                   (0.7976, 0.0493, 0.045, 0.0384, face_planes(0.42, 0.72, 0.78, -0.25)),
                   (0.8192, 0.0555, 0.0592, 0.0253, face_planes(0.42, 0.75, 0.76, 0.0)),
                   (0.8455, 0.0597, 0.0671, 0.0155, face_planes(0.4, 0.84, 0.78, 0.2)),
                   (0.8582, 0.0606, 0.0671, 0.0105, _EYES), (0.8798, 0.0606, 0.0671, 0.0105, _EYES),
                   (0.8822, 0.0606, 0.0719, 0.0111, face_planes(0.5, 0.84, 0.82, 0.25)),
                   (0.8972, 0.0606, 0.0733, 0.0115, face_planes(0.5, 0.84, 0.82, 0.25)),
                   (0.9188, 0.0564, 0.07, 0.007, face_planes(0.45, 0.82, 0.78, 0.25)),
                   (0.9423, 0.047, 0.0602, 0.0038, face_planes(0.4, 0.8, 0.75, 0.3))])
FACES = {
    "lean": Face(skull=LEAN_SKULL, eye_x=0.371, eye_y=0.103, eye=(0.0136, 0.0077), eye_shape=LENS, iris=0.0086,
                 pupil=0.0045, glint=0.0019, lid=0.05, slant=5.0, wide=1.2, lash=(0.3, 0.3),
                 brow_at=(0.367, 0.301, 0.301), brows=BROW_HEAVY, brow_down=0.4,
                 nose=((0.0188, 0.0056, 0.0028, 0.7, -1.0), (0.0, 0.0061, 0.0066, 0.65, -1.0), (-0.0188, 0.0089, 0.015, 0.55, -0.7),
                       (-0.031, 0.0155, 0.023, 0.5, -0.1), (-0.0367, 0.0164, 0.0211, 0.5, 0.05), (-0.0404, 0.0122, 0.0113, 0.6, -1.0)),
                 nostril=0.0028, mouth_x=0.395, mouth_y=-0.506, lips=Lips(),
                 ear_back=0.0207, ear_drop=0.0105, ear=1.11, ear_turn=36.0, ear_out=0.004),
}


@dataclass(frozen=True)
class Body:
    """A build: the skeleton's proportions and the sections of what is drawn on it. Every person of that build
    shares it, whatever they wear; an outfit asks it where the chest, the hips and the belt are."""
    build: Build
    trunk: Loft
    pelvis: Loft
    thigh: tuple = tuple(THIGH)
    shin: tuple = tuple(SHIN)
    hair: tuple = ((HAIR, (0.0, 0.0, 0.0)),)     # lofts carried by the head, each with where it is moved to
    skull: Loft = SKULL                          # the face's planes: the jaw and the chin differ, the crown does not
    brow: float = 0.74                           # how heavy the brows are
    arm: float = 1.0                             # how thick the arms are, against the man's
    leg: float = 1.0
    rest_hands: tuple = REST_HANDS
    hand: float = 1.0                            # how large the hands are, against the man's (HAND_* tables)
    foot: float = 1.0                            # and the boots (BOOT_* tables)
    # A build with other legs than the man's is drawn on the same heights as he is: its hips, its trunk and all an
    # outfit puts on them are given where the man has them (the belt at BELT_Y) and carried `up` higher, by what
    # its hip joints are above his. So an outfit fits it with nothing asked.
    up: float = 0.0
    # Its head with all it carries (skull, ears, hair, face, whatever hat): `head` times the man's, about the foot
    # of the neck (NECK_FOOT), and carried `head_up` higher than his: `up`, and more for a longer trunk or neck
    head: float = 1.0
    head_up: float = 0.0
    neck: tuple = (0.046, 0.044)                 # the neck's radius at its foot and under the head
    stance: dict | None = None                   # how it stands, under every pose (None: STANCE, the man's)
    sit_drop: float = SIT_DROP                   # rests it on its seat when it sits
    # a long sleeve by its sections, upper arm and forearm (times `arm`, as the other arm tables are), and the
    # balls that close the knee, the bare elbow and the elbow in a long sleeve (times `leg` and `arm`)
    sleeve_upper: tuple = tuple(SLEEVE_UPPER)
    sleeve_fore: tuple = tuple(SLEEVE_FORE)
    knee: tuple = KNEE
    elbow: tuple = ELBOW
    sleeve_elbow: tuple = SLEEVE_ELBOW

    @property
    def belt(self) -> Loft:
        return self.pelvis.band(BELT_Y - 0.02, BELT_Y + 0.02, 0.008)

    def on_head(self, p) -> tuple:
        """Where a point of the head as it is drawn (the man's, at rest) is on this build's."""
        if self.head == 1.0 and not self.head_up:
            return tuple(p)
        return tuple(a + (x - a) * self.head + d for x, a, d in zip(p, NECK_FOOT, (0.0, self.head_up, 0.0)))

    @property
    def reach_head(self) -> tuple:
        """What this build's gestures aim at and its arms stay out of (REACH_HEAD is the man's): (centre, radii)."""
        return self.on_head(REACH_HEAD[0]), tuple(r * self.head for r in REACH_HEAD[1])

    @property
    def torso(self) -> tuple:
        """Its chest as one block (TORSO is the man's)."""
        return (TORSO[0][0], TORSO[0][1] + self.up, TORSO[0][2]), TORSO[1]


_HEAD_Y = HEAD[0][1]
BODIES = {
    "man": Body(BUILD, TRUNK, PELVIS),
    # a woman: narrower shoulders and waist, fuller hips, slimmer limbs, her hair down to the collar and tied back
    "woman": Body(
        Build(height=1.0, head=1.75, torso=0.95, legs=0.84, arms=0.81, shoulders=0.7, hips=1.08),
        Loft([(0.512, 0.084, 0.064, 0.006), (0.532, 0.086, 0.07, 0.006), (0.556, 0.072, 0.064, 0.006),
              (0.60, 0.08, 0.068, 0.005), (0.645, 0.095, 0.08, 0.002), (0.68, 0.1, 0.084, -0.004),
              (0.705, 0.102, 0.072, -0.012), (0.733, 0.098, 0.06, -0.011), (0.745, 0.086, 0.054, -0.009),
              (0.753, 0.064, 0.049, -0.007), (0.771, 0.048, 0.043, -0.004), (0.784, 0.04, 0.039, -0.003)],
             flat=0.72, crease=SEAT_CREASE),
        Loft([(0.394, 0.03, 0.034, 0.0), (0.418, 0.09, 0.058, 0.0), (0.45, 0.106, 0.072, 0.001),
              (0.49, 0.102, 0.069, 0.001), (0.535, 0.086, 0.064, 0.005)], flat=0.72, crease=SEAT_CREASE),
        hair=((Loft(_bigger([(0.814, 0.04, 0.02, -0.042), *HAIR_SECTIONS], HEAD_K), profile=HAIR_SHAPE), (0.0, 0.0, 0.0)),
              (Loft([(-0.03, 0.018, 0.018, 0.0), (-0.011, 0.032, 0.032, 0.0), (0.014, 0.032, 0.032, 0.0),
                     (0.03, 0.018, 0.018, 0.0)], flat=0.5), (0.0, _HEAD_Y + 0.012, -0.09))),
        # (her face has the man's planes: a narrower jaw that comes to a smaller chin, less forward, and a softer brow)
        skull=Loft(_bigger([(0.8, 0.028, 0.026, 0.052, face_planes(0.55, 0.88, 0.8, 0.35)),
                            (0.816, 0.042, 0.043, 0.041, face_planes(0.5, 0.88, 0.8, 0.3)),
                            (0.857, 0.06, 0.068, 0.016, face_planes(0.42, 0.86, 0.78, 0.2)),
                            (0.871, 0.064, 0.069, 0.0105, _EYES), (0.896, 0.064, 0.069, 0.0105, _EYES),
                            (0.911, 0.066, 0.074, 0.0105, face_planes(0.5, 0.84, 0.82, 0.25)),
                            (0.935, 0.065, 0.072, 0.006, face_planes(0.45, 0.82, 0.78, 0.25)),
                            (0.962, 0.054, 0.058, 0.0, face_planes(0.4, 0.8, 0.75, 0.3))], HEAD_K)),
        brow=0.36, arm=0.8, leg=0.98, rest_hands=(0.238, 0.498, -0.006), hand=0.88, foot=0.93),
    # an adult as a turnaround sheet draws one (the anchor's: characters/tools/lowpoly/ref/anchor-sheet.png), where the man
    # and the woman are heroic toys: of the height, the head from chin to the top of its hair is 0.15 (theirs
    # 0.19, 0.225 with a cap), the legs part at 0.45 (0.39), the shoulders are at 0.76 (0.70) and 0.20 apart at
    # the joints, the arm is 0.28 from shoulder to wrist and the hand 0.12, the trunk is 0.21 wide at the chest
    # (0.25) and the legs are slim and straight. Measured with characters/tools/lowpoly/sheet_match.py.
    # Its skeleton: hip joints 0.50 above the ground standing, knees 0.27, shoulders 0.763 (x 0.098), neck 0.835;
    # upper arm 0.156, forearm 0.122. Its tables are on the man's heights (`up`): add 0.047 for where a section
    # is on the figure as it stands.
    "tall": Body(
        Build(height=1.0, head=1.25, torso=0.99, legs=0.945, arms=0.838, shoulders=0.75, hips=1.08),
        # (square shoulders, 0.28 across over the sleeves' heads, which stand 0.025 out of the trunk's own
        # shoulders as the man's do: a coat that an outfit lays on the trunk stays inside them; a chest 0.21 wide,
        # a flat back. No more sections than the man's between the waist and the collar: a lapel has a row at
        # each, and the paper finish's engine takes no surface whose formula is longer than 2048 characters)
        Loft([(0.512, 0.086, 0.068, 0.013), (0.556, 0.084, 0.070, 0.014), (0.613, 0.094, 0.070, 0.008),
              (0.645, 0.107, 0.071, 0.005), (0.685, 0.113, 0.073, 0.001), (0.733, 0.118, 0.062, -0.008),
              (0.745, 0.118, 0.057, -0.011), (0.753, 0.110, 0.053, -0.011), (0.783, 0.050, 0.038, -0.005),
              (0.795, 0.037, 0.033, -0.003)], flat=0.72, crease=SEAT_CREASE),
        Loft([(0.401, 0.03, 0.034, 0.0), (0.425, 0.086, 0.056, 0.0), (0.455, 0.099, 0.069, 0.0),
              (0.49, 0.099, 0.070, 0.001), (0.535, 0.088, 0.069, 0.006)], flat=0.72, crease=SEAT_CREASE),
        # (trousers that are slim and straight: 0.098 wide at the top of the thigh, 0.08 at the knee, 0.07 at the hem)
        thigh=((-0.12, 0.045, 0.05, 0.0), (0.22, 0.049, 0.057, 0.006), (0.55, 0.044, 0.053, 0.005), (0.88, 0.0385, 0.0475, 0.002),
               (1.03, 0.0395, 0.048, -0.003)),
        shin=((-0.03, 0.0395, 0.048, -0.003), (0.2, 0.040, 0.047, -0.002), (0.52, 0.036, 0.043, 0.001), (0.76, 0.035, 0.0415, 0.003),
              (0.93, 0.035, 0.0415, 0.004)),
        # (a sleeve 0.067 across from under its head, which is fuller, to a cuff 0.064 across: times `arm`)
        arm=0.72,
        sleeve_upper=((-0.16, 0.044, 0.038, 0.0), (0.0, 0.062, 0.054, 0.0), (0.45, 0.05, 0.052, 0.0), (1.04, 0.046, 0.047, 0.0)),
        sleeve_fore=((-0.04, 0.046, 0.047, 0.0), (0.28, 0.046, 0.047, 0.0), (0.9, 0.043, 0.042, 0.0), (0.96, 0.045, 0.044, 0.0),
                     (1.02, 0.045, 0.044, 0.0)),
        # the arms hang close: the wrists come to 0.149 out, 0.496 up and 0.007 behind the hips, the elbows 0.04
        # behind them, inside the back's outline in profile; the fingertips at 0.375, on the middle of the thigh.
        # Seated, it comes down by what puts its hips and thighs where the man's are on a seat (0.107 and 0.08 up)
        rest_hands=(0.216, 0.541, 0.0), hand=0.84, foot=0.84, sit_drop=0.17,
        # the head: 0.79 of the man's (0.13 wide at the ears, chin 0.85 of the height, the top of the hair 1.0)
        up=0.049, head=0.79, head_up=0.0724, neck=(0.039, 0.038),
        knee=(0.029, 0.038, 0.04),               # (inside the slimmer leg: the man's shows at its sides)
        # feet under the hips and nearly straight legs, shoulders that slope a little more, a face held upright
        stance={**STANCE, "left_upper_leg.in_out": 2.5, "right_upper_leg.in_out": 2.5, "left_upper_leg.front_back": 3.0,
                "right_upper_leg.front_back": 3.0, "left_shoulder.down_up": -15.0, "right_shoulder.down_up": -15.0,
                "head.nod_down_up": 5.0}),
}


@dataclass(frozen=True)
class Person:
    key: str
    name: str
    outfit: str = "officer"         # what it wears: OUTFITS
    body: str = "man"               # its build: BODIES
    skin: str = "lp.skin"
    shade: str = "lp.skin-shade"    # the hollow of an ear, a fold in a cheek: the same skin, two tones down
    hair: str = "lp.hair"
    top: str = "lp.navy"            # shirt (or a jacket, a coat: the trunk and the sleeves)
    bottom: str = "lp.navy"         # trousers
    trim: str = "lp.navy-dark"      # placket, pockets, epaulettes, the cap's band; a jacket's seams
    dark: str = "lp.leather"        # belt and what hangs on it, the cap's peak
    shoes: str = "lp.shoe"
    shiny: str = "lp.brass"         # badges
    metal: str = "lp.pewter"        # buckle
    tilt: float = 1.0               # how far its head rests to one side (degrees)
    sleeve: float = 0.58            # how much of the upper arm the sleeve covers; 1 or more is a long sleeve to the wrist
    buttons: str = "lp.button"
    eyes: str = "lp.eye"            # the iris
    sole: str = "lp.sole"           # the shoes' sole and heel
    shoe: float = 1.0               # how tall its shoes are, against a boot: lower is a dress shoe (a thinner sole, a lower toe)
    shirt: str = "lp.shirt"         # what shows under a jacket: the shirt's front, its collar, its cuffs
    tie: str = "lp.red"             # a tie, where the outfit has one
    turn_ups: float = 0.0           # turn-ups on a suit's trousers: how tall, a share of the shin's length (0: none; 0.1 is usual)
    # the hair on top of the head (HAIR_TOPS). None: the head wears a hat, and the build's hair is the back and the
    # sides only, as far up as the hat hides
    hair_style: str | None = None
    temples: str | None = None      # the hair of the sides and the back, where it is another colour than the top's
    brow: float = 1.0               # how heavy its brows are, against its build's
    face: str | None = None         # its face (FACES); None: the kit's first face, on its build's own skull


PEOPLE = {
    "sergeant": Person("sergeant", "Sergeant"),
    "cook": Person("cook", "Cook", outfit="cook", skin="lp.skin-brown", shade="lp.skin-brown-shade", hair="lp.hair-black",
                   top="lp.jacket", bottom="lp.check", trim="lp.apron", dark="lp.red", shoes="lp.black", sleeve=1.0,
                   buttons="lp.black"),
    "firefighter": Person("firefighter", "Firefighter", outfit="firefighter", top="lp.coat", bottom="lp.coat",
                          trim="lp.lime", dark="lp.leather", shoes="lp.boot", sleeve=1.0, buttons="lp.steel"),
    # the same uniform on the other build: nothing of the outfit or the body is written again
    "captain": Person("captain", "Captain", body="woman", skin="lp.skin-brown", shade="lp.skin-brown-shade",
                      hair="lp.hair-black", tilt=-1.0),
    # a news anchor: the tall build (an adult, as his sheet draws him) in a suit, bare-headed, with the face of his
    # sheet (FACES["lean"]) and his hair swept up and back, grey at the temples (HAIR_TOPS["swept"])
    "anchor": Person("anchor", "Anchor", outfit="suit", body="tall", skin="lp.skin-tan", shade="lp.skin-tan-shade", hair="lp.hair-dark",
                     temples="lp.hair-grey", hair_style="swept", face="lean", brow=1.08, eyes="lp.eye-deep", top="lp.suit",
                     bottom="lp.suit", trim="lp.suit-dark", shirt="lp.shirt", tie="lp.orange", shoes="lp.shoe-brown",
                     sole="lp.sole-brown", shoe=0.75, sleeve=1.0, buttons="lp.suit-dark"),
}

# What the gestures aim at (mascots3d.gesture: a hand at the chin, on the lips, over the eyes, on the brow). On a
# toy's head the mouth is 0.1 of the head's half height under its middle and the eyes 0.18 over it; a person's are
# where the face has them (MOUTH_Y and EYE_Y on HEAD). So the gestures are given the ellipsoid on which those two
# shares fall on this mouth and these eyes: as wide and as deep as HEAD, and taller, from under the collar to the
# top of a hat, which is also what an arm stays out of and where a hand pats.
_REACH = (EYE_Y - MOUTH_Y) * HEAD[1][1] / 0.28
REACH_HEAD = ((HEAD[0][0], HEAD[0][1] + EYE_Y * HEAD[1][1] - 0.18 * _REACH, HEAD[0][2]), (HEAD[1][0], _REACH, HEAD[1][2]))
# and how much of the hand is past the wrist when it is put to the face: to the first joint of its fingers (the
# man's: his knuckles are 0.08 from the wrist, that joint 0.125, his fingertips 0.166). With it the fingers of a
# hand "at the chin" end on the chin, under the mouth, and hands "over the eyes" cover the eyes and the brows
HAND_REACH = 0.12
# (the people are put in the cast by `enlist`, at the end: what a build says of its head, its hands, its stance
# goes into the person's mascots3d.Spec there)


class Sized(m.Carry):
    """A carry that also sizes what it carries: everything drawn with it is `k` times as large about the point
    `about` (in the rest pose) and `up` higher, places and sizes alike, as one piece. A build's head is carried
    by one (Body.head, Body.head_up), so the skull, the hair, the face and any hat follow the build with nothing
    asked of them. `k` is there for what gives a size in metres of its own (a line's thickness)."""

    def __init__(self, now, rest, k: float = 1.0, about=(0.0, 0.0, 0.0), up: float = 0.0):
        # (a size of 1 is carried exactly as a plain Carry carries: nothing is computed about the point)
        super().__init__(now, rest, 0.0, (k, k, k), tuple(about) if k != 1.0 else (0.0, 0.0, 0.0), up)
        self.k = k

    def basis(self, b):
        r = super().basis(b)
        return r if self.k == 1.0 else tuple(tuple(x * self.k for x in row) for row in r)


class Parts:
    """What a body or an outfit is drawn with: shapes carried by a bone, and where the bones are."""

    def __init__(self, fig: m.MascotFigure, frames, person: Person):
        self.fig, self.frames, self.p, self.b = fig, frames, person, BODIES[person.body]
        self.made: list = []
        self.limbs: dict = {}        # the limbs drawn with span(), by name: what goes round one asks for it
        rest = fig._rest()
        # the hips, the chest and the head are drawn where the man has them: the build says how far up it carries
        # them, and how large its head is
        self.hips = Sized(frames["hips"], rest["hips"], up=self.b.up)
        self.chest = Sized(frames["chest"], rest["chest"], up=self.b.up)
        self.head = Sized(frames["head"], rest["head"], self.b.head, NECK_FOOT, self.b.head_up)

    def solid(self, name, at, radii, material, basis=m.IDENTITY, ring=1.0, cap=1.0, samples=(22, 14)):
        radii = tuple(float(x) for x in radii)
        self.made.append(Limb(**shape(radii, ring, cap), radii=radii, at=Vec3(*at), basis=basis, name=name,
                              material=material, samples=samples, casts_shadow=False, looks=self.fig.looks))

    def put(self, carry, name, c, radii, material, basis=m.IDENTITY, samples=(20, 12), ring=1.0, cap=1.0):
        """A shape designed in the rest pose, moved with `carry`'s bone."""
        self.solid(name, carry.point(c), radii, material, carry.basis(basis), ring, cap, samples)

    def block(self, carry, name, c, radii, material, soft=SOFT, basis=m.IDENTITY, samples=(26, 16)):
        self.put(carry, name, c, radii, material, basis, samples, soft, soft)

    def rod(self, name, a, b, r0, r1, material, **kw):
        self.made.append(tube(name, a, b, r0, r1, material, looks=self.fig.looks, **kw))

    def loft(self, carry, name, loft: Loft, material, tilt=m.IDENTITY, move=(0.0, 0.0, 0.0)):
        self.made.append(loft.limb(name, carry, material, self.fig.looks, tilt, move))

    def span(self, name, a, b, frame, sections, material, flat=0.5, girth=1.0, crease=CREASE, facet=FACET, profile=None,
             stagger=0.0):
        """A limb between two joints, drawn as sections along it: (share of its length, half width, half depth,
        forward). Shares below 0 and above 1 run past the joints, into the next part. `profile` and `stagger` are
        the Loft's: another outline than the octagon, and rings that zigzag."""
        on = Span(a, b, frame)
        loft = Loft([(x[0] * on.length, x[1] * girth, x[2] * girth, *x[3:]) for x in sections], flat, crease, facet,
                    profile=profile, stagger=stagger)
        self.loft(on, name, loft, material)
        self.limbs[name] = (on, loft)

    def cuff(self, name, limb, share0, share1, material, out=0.004):
        """A band round a limb drawn with `span`, between two shares of its length: a stripe, a cuff."""
        on, loft = self.limbs[limb]
        self.loft(on, name, loft.band(share0 * on.length, share1 * on.length, out), material)

    def flat(self, carry, name, loft: Loft, dx, y, radii, material, lift=0.0, roll=0.0, soft=SOFT, samples=(12, 8)):
        """A flat thing lying on a lofted part's front at (dx, y), turned to its facet: a pocket, a button."""
        at, turn = loft.seat(dx, y, lift)
        self.put(carry, name, at, radii, material, m._mul(turn, rotation(0, 0, roll)), samples, soft, soft)

    def hung(self, carry, name, loft: Loft, deg, y, radii, material, out=0.0, soft=SOFT, samples=(12, 10)):
        """A thing hanging on a lofted part's side, `deg` round from the front, facing outward: a pouch, a radio."""
        at, yaw = loft.around(deg, y, out)
        self.put(carry, name, at, radii, material, rotation(yaw, 0, 0), samples, soft, soft)

    def on_chest(self, dx, y, lift=0.0):
        """A point on the shirt's front at height `y`, `dx` from the middle, and `lift` out of it."""
        return self.b.trunk.seat(dx, y, lift)[0]


# ----------------------------------------------------------------------------- boots and hands: drawn parts
class _Facing:
    """What `Span` asks of a bone, for a part that lies along a line with its front toward `front`."""

    def __init__(self, front: Vec3, other: Vec3):
        self.basis = ((other.x, 0.0, front.x), (other.y, 0.0, front.y), (other.z, 0.0, front.z))


def _drawn(k: Parts, name: str, at: Vec3, along: Vec3, front: Vec3, rows, material: str, size: float = 1.0,
           flat: float = 1.0, profile=None) -> None:
    """A part that keeps its corners, drawn along a line: `rows` are (how far along it from `at`, half width, where
    it starts and where it ends toward `front`[, its own corners there]), in metres times `size`. A box when
    `flat` is 1; `profile` (or a row's corners) gives it another outline (see Loft)."""
    z0 = rows[0][0]
    # its line runs through the middle of its depth: the figure is stood on the lowest of its parts' boxes, and a
    # part's box is as deep to either side of that line as the part reaches on one
    mid = (min(r[2] for r in rows) + max(r[3] for r in rows)) / 2
    at = at + scaled(unit(front - scaled(along, front.x * along.x + front.y * along.y + front.z * along.z)), mid * size)
    on = Span(at + scaled(along, z0 * size), at + scaled(along, rows[-1][0] * size), _Facing(front, cross(along, front)))
    # each end is closed on a point in the middle of its face. (A Loft closes on a ring 2 mm across just beyond its
    # end, which is open: a dark dot where the end is in view, as a fingertip's and a boot's toe are. Those two
    # rings are left out of what is drawn: `v` runs over this part's own rows.)
    point = lambda r, step: (r[0] + step, 0.0, (r[2] + r[3]) / 2, (r[2] + r[3]) / 2, *r[4:])      # noqa: E731
    rows = [point(rows[0], -2e-5), *rows, point(rows[-1], 2e-5)]
    loft = Loft([((z - z0) * size, half * size, (hi - lo) / 2 * size, ((hi + lo) / 2 - mid) * size, *own)
                 for z, half, lo, hi, *own in rows], flat, profile=profile)
    k.made.append(_own_rows(loft.limb(name, on, material, k.fig.looks), len(rows)))


def _own_rows(part: Limb, rows: int) -> Limb:
    """A lofted part whose first and last rows close it on a point of their own: only its `rows` are drawn, not
    the two rings a Loft closes with."""
    return _replace(part, v=(1, rows), samples=(part.samples[0], rows - 1))


def _roof(wall: float, top: float):
    """A boot's outline across the foot: a flat bottom, walls that stand up to `wall` (-1 the bottom, 1 the top) and
    lean in from there to a flat top that is `top` of the width."""
    return ((1.0, wall), (top, 1.0), (-top, 1.0), (-1.0, wall), (-1.0, -1.0), (1.0, -1.0))


# A boot, read off the sheet: metres from the point of the ground under the ankle, on the man's foot (Body.foot
# scales it): how far toward the toes, half width, bottom, top. The sole: a heel, an arch that stands clear of the
# ground (the heel's step), a tread that is widest at the ball of the foot and ends in a toe cut at its corners
BOOT_SOLE = [(-0.042, 0.035, 0.0, 0.022), (-0.006, 0.037, 0.0, 0.022), (-0.005, 0.036, 0.009, 0.022),
             (0.007, 0.038, 0.009, 0.022), (0.008, 0.039, 0.0, 0.022), (0.122, 0.047, 0.0, 0.022),
             (0.140, 0.035, 0.002, 0.022)]
# its upper, standing in the sole: the heel's counter, a shaft that goes up inside the trouser leg, the instep
# coming down from it, a toe cap that is low, wide and blunt at the front
BOOT_UPPER = [(-0.037, 0.029, 0.018, 0.046, _roof(0.6, 0.7)), (-0.01, 0.035, 0.018, 0.072, _roof(0.6, 0.7)),
              (0.034, 0.038, 0.018, 0.076, _roof(0.5, 0.7)), (0.064, 0.042, 0.018, 0.06, _roof(0.3, 0.62)),
              (0.088, 0.0445, 0.018, 0.051, _roof(0.3, 0.68)), (0.12, 0.0435, 0.018, 0.05, _roof(0.3, 0.68)),
              (0.134, 0.038, 0.018, 0.04, _roof(0.3, 0.68))]
ANKLE_UP = 0.036       # how far above the boot's ground the ankle is


def _boot(k: Parts, g: str, ground: Vec3, ahead: Vec3, up: Vec3) -> None:
    """A boot on the ground at `ground` (the point under the ankle), its toes `ahead`: a sole with a heel's step,
    and the upper from the heel over a shaft to a toe cap. They take the person's colours (`sole`, `shoes`), and
    are as low as the person's shoes are (`shoe`: every height of the boot's, times that)."""
    low = lambda rows: rows if k.p.shoe == 1.0 else [(z, half, a * k.p.shoe, b * k.p.shoe, *own) for z, half, a, b, *own in rows]   # noqa: E731
    _drawn(k, f"{g}/sole", ground, ahead, up, low(BOOT_SOLE), k.p.sole, k.b.foot)
    _drawn(k, f"{g}/upper", ground, ahead, up, low(BOOT_UPPER), k.p.shoes, k.b.foot)


# A hand, read off the sheet: metres from the wrist, on the man's hand (Body.hand scales it). The palm is a block
# with its edges cut, from the wrist to the knuckles: how far down the hand, half thickness, how far it reaches toward the little
# finger (below 0) and toward the thumb from the forearm's line: it widens to the knuckles, more on the little
# finger's side. HAND_BACK: how far its middle lies toward the back of the hand
HAND_PALM = [(-0.005, 0.02, -0.0215, 0.02), (0.02, 0.0235, -0.034, 0.02), (0.045, 0.0225, -0.043, 0.031),
             (0.083, 0.0195, -0.047, 0.029)]
HAND_BACK = 0.003
# the four fingers, index first: how far toward the thumb its knuckle is, how far down the hand, its length against
# the middle finger's, how many degrees more than that one it curls
HAND_FINGERS = (("index", 0.019, 0.079, 0.95, -3.0), ("middle", 0.0003, 0.081, 1.0, 0.0),
                ("ring", -0.0184, 0.078, 0.94, 4.0), ("little", -0.0371, 0.071, 0.8, 9.0))
FINGER = (0.045, 0.04, 0.0091, 0.0105)     # a finger's two bones, its half width and half thickness
FINGER_CURL = (27.0, 40.0)                 # degrees a resting finger bends at the knuckle, and again at its joint
# the thumb: where it leaves the palm (down the hand, toward the thumb's side, toward the palm), the way its two
# bones point in the same three (it stands off the palm's face and hangs beside the index finger), their lengths,
# half width, half thickness
THUMB_ROOT, THUMB_WAY, THUMB = (0.04, 0.029, 0.016), ((0.86, 0.0, 0.5), (0.96, 0.0, 0.25)), (0.034, 0.03, 0.014, 0.0115)
HAND_LEAN = 6.0        # degrees a hanging hand still leans out from upright, as the sheet's does
HAND_BEND = 22.0       # the most its wrist bends to get there, from a forearm that leans out more


def _hand(k: Parts, g: str, out: float, shoulder: Vec3, elbow: Vec3, w: Vec3, flap: float) -> None:
    """A hand at the wrist `w`: a palm, four fingers of two bones each, curled toward the palm, and a thumb that
    stands apart. `out` is 1 for the arm on the side where x is positive and -1 for the other, its mirror; `flap`
    is the pose's turn of the wrist (degrees, about the figure's front-to-back axis)."""
    size, skin = k.b.hand, k.p.skin
    d = unit(w - elbow)
    # a hand that hangs does not follow a forearm that leans out: the wrist bends it back toward upright
    lean = math.degrees(math.atan2(out * d.x, -d.y))
    hang = max(0.0, min(1.0, (-d.y - 0.6) / 0.3))                               # 1 while the forearm hangs
    bend = max(0.0, min(HAND_BEND, lean - HAND_LEAN)) * hang
    th = math.radians(-out * (flap + bend))
    d = Vec3(d.x * math.cos(th) - d.y * math.sin(th), d.x * math.sin(th) + d.y * math.cos(th), d.z)
    # the palm faces the body while the arm hangs or reaches in front, and forward once the hand is raised out
    # beside the head (a wave shows it); a hand that points sideways turns it down
    up = max(0.0, min(1.0, (w.y - shoulder.y) / 0.05 + 0.3)) * max(0.0, min(1.0, (abs(w.x - shoulder.x) - 0.06) / 0.03))
    square = lambda v: v - scaled(d, v.x * d.x + v.y * d.y + v.z * d.z)       # noqa: E731
    p = square(Vec3(-out * (1.0 - up), 0.0, up))
    if p.length < 0.5:
        p = p + scaled(square(Vec3(0.0, -1.0, 0.0)), 0.5 - p.length)
    p = unit(p) if p.length > 1e-3 else unit(cross(d, Vec3(0.0, 0.0, 1.0)))     # out of the palm
    n = scaled(cross(p, d), out)                                                # toward the thumb
    way = lambda a, b, c: unit(scaled(d, a) + scaled(n, b) + scaled(p, c))      # noqa: E731
    _drawn(k, f"{g}/hand", w - scaled(p, HAND_BACK * size), d, n, HAND_PALM, skin, size, flat=0.72)
    # the fingers lie in the back of the hand at the knuckles; they curl while the arm hangs, and a hand that is
    # held out or up opens them
    lifted = max(up, 1.0 - hang)
    openness = 1.0 - 0.6 * lifted
    l1, l2, half, thick = FINGER
    for name, across, down, long_, more in HAND_FINGERS:
        a1 = math.radians((FINGER_CURL[0] + more) * openness)
        a2 = a1 + math.radians((FINGER_CURL[1] + more) * openness)
        at = w + scaled(d, down * size) + scaled(n, across * size) + scaled(p, (thick - HAND_BACK - HAND_PALM[-1][1]) * size)
        for part, a, length, r0, r1, back in ((name, a1, l1, 1.0, 0.95, 0.004), (f"{name}-tip", a2, l2, 0.95, 0.8, 0.008)):
            along = way(math.cos(a), 0.0, math.sin(a))
            _drawn(k, f"{g}/{part}", at, along, way(-math.sin(a), 0.0, math.cos(a)),
                   [(-back, half * r0, -thick * r0, thick * r0), (length * long_, half * r1, -thick * r1, thick * r1)], skin, size)
            at = at + scaled(along, length * long_ * size)
    # the thumb leaves the palm's edge near the wrist and stands in front of the palm; out to the side on an open hand
    l1, l2, half, thick = THUMB
    at = w + scaled(d, THUMB_ROOT[0] * size) + scaled(n, THUMB_ROOT[1] * size) + scaled(p, THUMB_ROOT[2] * size)
    for part, (a, b, c), length, r0, r1, back in (("thumb", THUMB_WAY[0], l1, 1.0, 0.9, 0.012), ("thumb-tip", THUMB_WAY[1], l2, 0.9, 0.7, 0.008)):
        along = way(a, b + 0.5 * lifted, c * openness)
        _drawn(k, f"{g}/{part}", at, along, n,
               [(-back, half * r0, -thick * r0, thick * r0), (length, half * r1, -thick * r1, thick * r1)], skin, size)
        at = at + scaled(along, length * size)


# ----------------------------------------------------------------------------- the body, shared by every person
def _legs(k: Parts) -> None:
    p, f = k.p, k.frames
    for side in ("left", "right"):
        hip, knee, ankle, toes = (f[f"{side}_{b}"].position for b in ("upper_leg", "lower_leg", "foot", "toes"))
        g = f"leg_{side[0]}"
        # trousers: one line from hip to knee to a hem wider than the knee (the same width where two tubes meet)
        # (a leg is flatter front to back than it is wide, as the sheet's profile shows)
        # trousers: a full thigh, a break at the knee, the calf behind, and cloth that stacks on the shoe at the hem
        k.span(f"{g}/thigh", hip, knee, f[f"{side}_upper_leg"], k.b.thigh, p.bottom, girth=k.b.leg, **LEG)
        k.span(f"{g}/shin", knee, ankle, f[f"{side}_lower_leg"], k.b.shin, p.bottom, girth=k.b.leg, **LEG)
        k.solid(f"{g}/knee", knee, tuple(r * k.b.leg for r in k.b.knee), p.bottom, samples=(10, 8))
        ahead = toes - ankle
        ahead = unit(ahead) if ahead.length > 1e-4 else Vec3(0, 0, 1)
        if abs(ahead.y) < 0.6 and ankle.y < 0.09:        # standing on it: the shoe lies flat on the ground
            ahead = unit(Vec3(ahead.x, 0.0, ahead.z))
            ground = Vec3(ankle.x, 0.0, ankle.z)
            up = Vec3(0, 1, 0)
        else:                                            # lifted, or seated: it follows the foot
            up = unit(knee - ankle)
            up = unit(up - scaled(ahead, up.x * ahead.x + up.y * ahead.y + up.z * ahead.z))
            ground = ankle - scaled(up, ANKLE_UP * k.b.foot)
        _boot(k, f"shoe_{side[0]}", ground, ahead, up)


def _trunk(k: Parts) -> None:
    k.loft(k.hips, "hips/hips", k.b.pelvis, k.p.bottom)
    k.loft(k.chest, "body/body", k.b.trunk, k.p.top)


def _arms(k: Parts) -> None:
    p, f, fig = k.p, k.frames, k.fig
    for side in ("left", "right"):
        s, el, w = (f[f"{side}_{b}"].position for b in ("upper_arm", "lower_arm", "hand"))
        g = f"arm_{side[0]}"
        up, low = f[f"{side}_upper_arm"], f[f"{side}_lower_arm"]
        if p.sleeve >= 1.0:          # a long sleeve: the whole arm in cloth, fuller at the elbow, a cuff at the wrist
            k.span(f"sleeve_{side[0]}/upper", s, el, up, k.b.sleeve_upper, p.top, girth=k.b.arm, **SLEEVE)
            k.span(f"sleeve_{side[0]}/fore", el, w, low, k.b.sleeve_fore, p.top, girth=k.b.arm, **SLEEVE)
            k.solid(f"sleeve_{side[0]}/elbow", el, tuple(r * k.b.arm for r in k.b.sleeve_elbow), p.top, samples=(10, 8))
        else:                        # a short one: its hem stands off the bare arm, which starts at the hem
            k.span(f"{g}/upper", s, el, up, [(p.sleeve - 0.04, *ARM_UPPER[0][1:]), *ARM_UPPER[1:]], p.skin, girth=k.b.arm, **BARE)
            k.span(f"{g}/fore", el, w, low, ARM_FORE, p.skin, girth=k.b.arm, **BARE)
            k.solid(f"{g}/elbow", el, tuple(r * k.b.arm for r in k.b.elbow), p.skin, samples=(10, 8))
            k.span(f"sleeve_{side[0]}/sleeve", s, el, up, [*SLEEVE_CAP, (p.sleeve * 0.6, *SLEEVE_HEM[0]), (p.sleeve, *SLEEVE_HEM[1])],
                   p.top, girth=k.b.arm, **SLEEVE)
        _hand(k, g, 1.0 if side == "right" else -1.0, s, el, w, fig.wrist_left if side == "left" else fig.wrist_right)


def _plate(k: Parts, carry, name: str, outline, half: float, tall: float, material: str, at, turn, thick: float = 0.001,
           low: float = -1.0, high: float = 1.0) -> None:
    """A flat shape that lies on a facet at `at` (`turn` as Loft.seat gives it) and keeps its corners: `outline`
    says how wide it is, as shares of its half width `half`, at shares of its half height `tall`, bottom to top
    (ALMOND, ROUND). It is cut off below `low` and above `high` (shares of `tall`), as a lid cuts an eye, and
    has as many sections however it is cut."""
    def wide(t):
        for (t0, w0), (t1, w1) in zip(outline, outline[1:]):
            if t <= t1:
                return w0 + (w1 - w0) * max(0.0, (t - t0) / (t1 - t0))
        return outline[-1][1]

    cut = [max(low, min(max(low, high), t)) for t, _w in outline]
    _piece(k, carry, name, [(t * tall, max(0.0004, wide(t) * half), thick) for t in cut], material, at, turn)


def _shell(k: Parts, carry, name: str, rings, material: str) -> None:
    """A part drawn corner by corner, for a shape that no stack of level sections makes (a brow or a lip that
    follows the face's planes, hair whose edge dips): `rings` are its rows, each as many points (x, y, z) in the
    carry's rest space, round the part. It closes at each end on the middle of its first and of its last ring,
    and the finish keeps its corners exactly, as a Loft's. The rings may be given either way round. A shell of
    many rings and corners is drawn as two or more parts of the same name that share a ring, so that none of
    its formulas is longer than SHELL_LONG (the paper engine takes none over 2,048 characters)."""
    n = len(rings[0])
    mid = lambda ring: tuple(sum(q[a] for q in ring) / n for a in range(3))      # noqa: E731
    rows = [[mid(rings[0])] * n, *([tuple(q) for q in ring] for ring in rings), [mid(rings[-1])] * n]
    # its faces look outward as a Loft's do (what it holds, counted the way the corners run, comes out below 0)
    held = sum(a[0] * (b[1] * c[2] - b[2] * c[1]) + a[1] * (b[2] * c[0] - b[0] * c[2]) + a[2] * (b[0] * c[1] - b[1] * c[0])
               for lo, hi in zip(rows, rows[1:]) for i in range(n)
               for a, b, c in ((lo[i], lo[(i + 1) % n], hi[(i + 1) % n]), (lo[i], hi[(i + 1) % n], hi[i])))
    if held > 0:
        rows = [[row[0], *row[:0:-1]] for row in rows]
    corner = lambda i: f"(max(1-abs(u-{i}),0)" + (f"+max(1-abs(u-{n}),0))" if i == 0 else ")")      # 1 on corner i  # noqa: E731

    def drawn(rows):
        low, high = ([f(q[a] for row in rows for q in row) for a in range(3)] for f in (min, max))
        c = tuple((a + b) / 2 for a, b in zip(low, high))

        def along(a):        # a corner's place runs straight from ring to ring as v counts them
            terms = []
            for i in range(n):
                text = f"{rows[0][i][a] - c[a]:.5f}"
                for j in range(1, len(rows)):
                    d = rows[j][i][a] - rows[j - 1][i][a]
                    if abs(d) >= 5e-6:
                        text += f"+({d:.5f})*min(max(v-{j - 1},0),1)"
                if text not in ("0.00000", "-0.00000"):
                    terms.append(f"({text})*{corner(i)}")
            return "(" + "+".join(terms or ["0"]) + ")"

        x, y, z = along(0), along(1), along(2)
        if max(len(x), len(y), len(z)) > SHELL_LONG and len(rows) > 2:
            cut = len(rows) // 4 * 2 or 1        # (an even row where there is one: the two parts' facets then run as one part's)
            return drawn(rows[:cut + 1]) + drawn(rows[cut:])
        return [Limb(x=x, y=y, z=z, u=(0, n), v=(0, len(rows) - 1), samples=(n, len(rows) - 1), closed=(True, False),
                     radii=tuple(max(0.001, (b - a) / 2) for a, b in zip(low, high)), at=carry.point(c),
                     basis=carry.basis(m.IDENTITY), name=name, material=material, role="drawn", casts_shadow=False,
                     looks=k.fig.looks)]

    k.made.extend(drawn(rows))


SHELL_LONG = 1800      # the longest formula a _shell writes for one part (the size a build gives its head is written in front of it)


def _ribbon(k: Parts, name: str, on, stations, material: str, deep: float = 0.003, rows=()) -> None:
    """A strip that lies on the face and follows its planes: a brow, a lip, a lash, a fold. `stations` are places
    along it; each gives its edge there from one side to the other as points on the face: (across, up, how far
    out of the face in metres), as `on.lay` takes them. Behind those it is sunk `deep` into the face. Where it
    crosses an edge between two of the face's planes (`on.edges`) it is given a place more, so it bends with them;
    and a strip that is tall is given `rows`, the heights at which the face bends (`on.rows`): every edge gets a
    point at each that the strip reaches, so it bends there too instead of cutting through the face."""
    reach = [q[1] for edge in stations for q in edge]
    rows = [y for y in rows if min(reach) + 0.005 < y < max(reach) - 0.005]
    if rows:
        def bent(edge):
            out = [edge[0]]
            for a, b in zip(edge, edge[1:]):
                for y in sorted(rows, reverse=b[1] < a[1]):
                    t = max(0.0, min(1.0, (y - a[1]) / (b[1] - a[1]))) if abs(b[1] - a[1]) > 1e-9 else 0.0
                    out.append(tuple(p + (q - p) * t for p, q in zip(a, b)))
                out.append(b)
            return out

        stations = [bent(edge) for edge in stations]
    placed = [stations[0]]
    for a, b in zip(stations, stations[1:]):
        x0, x1 = a[0][0], b[0][0]
        for x in sorted(on.edges((a[0][1] + a[-1][1] + b[0][1] + b[-1][1]) / 4), reverse=x1 < x0):
            if min(x0, x1) + 0.02 < x < max(x0, x1) - 0.02:
                t = (x - x0) / (x1 - x0)
                placed.append([tuple(p + (q - p) * t for p, q in zip(pa, pb)) for pa, pb in zip(a, b)])
        placed.append(b)
    _shell(k, k.head, name, [[*(on.lay(*q) for q in edge), on.lay(*edge[-1][:2], -deep), on.lay(*edge[0][:2], -deep)]
                             for edge in placed], material)


def _eyes(k: Parts, on, limb, face: Face = FACE) -> None:
    """An eye (Face.eye): lashes, a white, an iris, a pupil and one small light, each a flat plate on the one
    before, in the socket's plane. It looks where the pose looks; wide, the opening is taller and the white shows
    round the iris; it narrows from the top as a lid comes down (half shut, a blink on its way), the iris cut with
    it; shut, it is a curved line. A face with a heavy lid (Face.lid) has the lid part way down at rest, drawn in
    the skin's shade over the eye, and a shut eye that is drawn as its lashes are, not painted."""
    fig, e, p = k.fig, k.fig.expression, k.p
    lx = max(-1.0, min(1.0, e.look[0] + fig.look_x))
    ly = max(-1.0, min(1.0, e.look[1] + fig.look_y))
    w = face.eye[0]
    h = min(0.0122, face.eye[1] * {"wide": face.wide, "squint": 0.72}.get(e.eyes, 1.0) * fig.eye_scale)   # the skull's band for the eyes is that tall
    rx, ry = HEAD[1][0], HEAD[1][1]
    smiling = e.mouth in ("smile", "smug", "flat")
    rest = 0.0 if e.eyes == "wide" else face.lid     # where a heavy lid rests
    g = face.iris / IRIS                             # the eye's size, against the first face's
    size = getattr(k.head, "k", 1.0)                 # the head's size on this build: a painted line is as much thinner
    for sx in (-1, 1):
        fx, fy = sx * face.eye_x, face.eye_y
        shut = min(1.0, fig.lid + (fig.lid_right if sx > 0 else fig.lid_left))
        if e.eyes == "half":
            shut = max(shut, 0.5)
        if e.eyes == "closed" or shut >= 0.9:
            up = 1.0 if smiling else -0.6
            if face.lid:        # the lashes, a dark strip along the closed lids
                _ribbon(k, "eye-lash", on, [[(fx + t * w / rx, fy + (up * 0.3 * (1 - t * t) - 0.25 + s * 0.14 * (1.15 - t * t)) * h / ry, 0.0008)
                                             for s in (1, -1)] for t in (-1.0, -0.5, 0.0, 0.5, 1.0)], p.hair)
                continue
            fig._stroke("eye/closed", [on(fx + (i - 3) / 3 * 0.2, fy + up * 0.04 * (1 - ((i - 3) / 3) ** 2), 0.012)
                                       for i in range(7)], 0.003 * size)
            continue
        if e.eyes == "spiral":
            m.spiral(on, fig._stroke, fx, fy, 0.13, 0.003 * size)
            continue
        shut = rest + (1.0 - rest) * shut
        turn = rotation(*on.turn(fx, fy), 0)         # an eye lies flat in its socket's plane: it neither floats nor sinks
        if face.slant:
            turn = m._mul(turn, rotation(0, 0, sx * face.slant))
        lay = lambda dx, dy, lift: on(fx + dx / rx, fy + dy / ry, (lift - 0.002) / 0.03)   # noqa: E731  metres from its middle
        top = (1.0 - 2.0 * shut) * h                 # where the lid has come down to
        _plate(k, k.head, "eye-lash", face.eye_shape, w + 0.0014, h + 0.0015, p.hair, lay(0.0, 0.0, 0.0007), turn, 0.0007,
               low=max(-1.0, min(face.lash[1], (top - face.lash[0] * h) / (h + 0.0015))), high=(top + 0.0015) / (h + 0.0015))    # it comes down with the lid
        if face.lid and top + 0.0015 < h:            # the lid itself, from the lashes up to the top of the opening
            _plate(k, k.head, "eye-lid", face.eye_shape, w + 0.0014, h + 0.0015, p.shade, lay(0.0, 0.0, 0.0005), turn, 0.0007,
                   low=(top + 0.001) / (h + 0.0015))
        _plate(k, k.head, "eye-white", face.eye_shape, w, h, "lp.white", lay(0.0, 0.0, 0.0013), turn, 0.0009, high=top / h)
        dx, dy = 0.0042 * g * lx, 0.0028 * g * ly
        for name, r, material, lift in (("eye", face.iris, p.eyes, 0.0019), ("eye-pupil", face.pupil, "lp.pupil", 0.0024)):
            lo, hi = (-h + 0.0005 - dy) / r, (top - 0.0005 - dy) / r         # what of it the opening shows
            if hi > max(lo, -1.0) + 0.1:
                _plate(k, k.head, name, ROUND, r, r, material, lay(dx, dy, lift), turn, 0.0008, low=max(-1.0, lo), high=min(1.0, hi))
        gy = dy + 0.0036 * g                         # the light, up and to the picture's right of the pupil
        if face.lid:                                 # (under a heavy lid it keeps below the lid)
            gy = min(gy, top - face.glint - 0.0008)
        if dy + 0.0034 * g + face.glint < top - 0.0005 or (face.lid and gy - face.glint > -h):
            limb("eye-shine", lay(dx - 0.0034 * g, gy, 0.003), (face.glint, face.glint, 0.0007), "lp.white", *on.turn(fx, fy),
                 samples=(8, 6))


def _head(k: Parts) -> None:
    p, f, fig, e = k.p, k.frames, k.fig, k.fig.expression
    (hx, hy, hz), (rx, ry, rz) = HEAD
    face = FACES[p.face] if p.face else FACE         # the person's own face, or the kit's first
    skull = face.skull or k.b.skull                  # whose planes are its own, or the build's
    k.rod("neck/neck", f["neck"].position - Vec3(0, 0.03, 0), f["head"].position + Vec3(0, 0.01, 0), *k.b.neck, p.skin)
    k.loft(k.head, "head/head", skull, p.skin)
    ear, hollow = EAR, EAR_HOLLOW
    if face.ear != 1.0:      # the same ear, larger or smaller
        ear = Loft([(*(v * face.ear for v in s[:4]), s[4]) for s in EAR.s])
        hollow = tuple((a * face.ear, half * face.ear, thick) for a, half, thick in EAR_HOLLOW)
    for sx in (-1, 1):       # an ear on the skull's side, turned out (Face.ear_turn), and the hollow in its outer side
        ey, ez = hy - face.ear_drop, hz - face.ear_back
        ex = sx * skull.side(ez, ey, face.ear_out)
        swing = rotation(-sx * face.ear_turn, 0, 0)
        k.loft(k.head, f"ear_{sx}/ear", ear, p.skin, swing, move=(ex, ey, ez))
        out, back = (sx * swing[0][0], 0.0, sx * swing[2][0]), (-swing[0][2], 0.0, -swing[2][2])
        _piece(k, k.head, f"ear_{sx}/hollow", hollow, p.shade,
               tuple(c + n * (ear.at(0.0)[0] + 0.0006) + b * 0.003 for c, n, b in zip((ex, ey, ez), out, back)),
               _lie((0.0, 1.0, 0.0), out))
    style = HAIR_TOPS[p.hair_style] if p.hair_style else None
    if isinstance(style, Hair):      # a whole head of hair of its own
        _hair(k, style)
    else:
        for loft, move in k.b.hair:      # the back and the sides, as the build has them
            k.loft(k.head, "hair/hair", loft, p.temples or p.hair, move=move)
        if style:                        # bare-headed: the hair on top of the head as well (HAIR_TOPS)
            k.loft(k.head, "hair/top", style, p.hair)
    # the face is laid out on the skull's own front: `out` lifts a part off its facet (1 is 3 cm)
    _on, limb, R = fig._face(k.head, (hx, hy, hz), (rx, ry, rz),
                             lambda carry, name, c, r, mat, b=m.IDENTITY, samples=(14, 10): k.put(carry, name, c, r, mat, b, samples))
    on = lambda fx, fy, out=0.0: (hx + fx * rx, hy + fy * ry, skull.front(hx + fx * rx, hy + fy * ry, 0.002 + 0.03 * out))

    def turn(fx, fy, d=0.002):       # (yaw, pitch) that lay a flat thing on the face's plane there, as Loft.seat does
        x, y, z = hx + fx * rx, hy + fy * ry, skull.front
        return (math.degrees(math.atan2(z(x - d, y) - z(x + d, y), 2 * d)), math.degrees(math.atan2(z(x, y - d) - z(x, y + d), 2 * d)))

    on.turn = turn
    # the same place, lifted by so many metres (what a _ribbon is given), and where the face's planes meet at a
    # height: a strip that crosses one of those edges has to bend there
    on.lay = lambda fx, fy, lift=0.0: (hx + fx * rx, hy + fy * ry, skull.front(hx + fx * rx, hy + fy * ry, lift))
    on.edges = lambda fy: sorted((x - hx) / rx for x, z in skull.ring(hy + fy * ry) if z > skull.at(hy + fy * ry)[2])
    on.rows = tuple((s[0] - hy) / ry for s in skull.s)       # and the heights at which they do
    _eyes(k, on, limb, face)
    browed = e if e.brows != "none" else _replace(e, brows="flat")       # his brows are always there
    heavy = k.b.brow * p.brow        # how heavy the brows are: the build's, and the person's own

    def bar(name, points, r, material=None):      # a brow is a bar of his hair, bent once: heavy from the nose, thinner at its
        # outer end, and set into the brow so that it does not stand off it in profile
        ends = [k.head.point((q[0], q[1], q[2] - 0.92 * heavy * r)) for q in (points[0], points[len(points) // 2], points[-1])]
        thick = [heavy * r * s * getattr(k.head, "k", 1.0) for s in (0.95, 1.0, 0.55)]      # (as thick as the head is large)
        for a, b, r0, r1 in zip(ends, ends[1:], thick, thick[1:]):
            k.rod("hair/brow", a, b, r0, r1, p.hair, samples=(8, 5))

    def strip(name, points, r, material=None):    # or a strip with an outline of its own (Face.brows), lying on the brow:
        # the pose says where its two ends are; a lowering is taken in part, the brow being low already
        (x0, y0, _z0), (x1, y1, _z1) = points[0], points[-1]
        level = face.brow_at[1]
        y0, y1 = (level + (y - level) * (face.brow_down if y < level else 1.0) for y in (y0, y1))
        weigh = heavy / BODIES["man"].brow * (r / 0.0105 - 0.45) / 0.55       # (thinner while it grows in or goes)
        _ribbon(k, "hair/brow", on, [[(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t + edge * weigh, 0.0015) for edge in (hi, lo)]
                                     for t, lo, hi in face.brows], p.hair, rows=on.rows)

    m.brows((lambda fx, fy, out=0.0: (fx, fy, 0.0)) if face.brows else on, strip if face.brows else bar, browed, *face.brow_at,
            0.0105, was=fig.brows_from or "flat", mix=fig.brow_mix, lift=0.3 * (fig.eye_scale - 1.0))
    _nose(k, skull, face)
    _mouth(k, on, limb, face)


def _hair(k: Parts, style: Hair) -> None:
    """A whole head of hair (Hair, HAIR_TOPS): its back and sides, and over them its top, whose hem is moved as
    the style says: up over the forehead, down onto the sides' hair behind."""
    p, top, sides = k.p, style.top, style.sides
    k.loft(k.head, "hair/hair", sides, p.temples or p.hair)
    rings = []
    for j, s in enumerate(top.s):
        ring = []
        for i, (x, z) in enumerate(top.ring(s[0])):
            y = s[0] + (style.hem[i] if j == 0 else top.stagger * (-1 if (i + j) % 2 else 1) if j < len(top.s) - 1 else 0.0)
            if j == 0 and style.hem[i] < 0:          # it comes down: onto the sides' hair, a little proud of it
                (x, y, z), _yaw = sides.around(math.degrees(math.atan2(x, z - sides.at(y)[2])), y, 0.004)
            ring.append((x, y, z))
        rings.append(ring)
    _shell(k, k.head, "hair/top", rings, p.hair)


def _nose(k: Parts, skull: Loft, face: Face) -> None:
    """The nose (Face.nose): a wedge, narrow at the bridge and wide at its base, with a flat ridge from the bridge
    out to its tip (the plane that takes the light) and a short underside back to the lip (the one in shade). Its
    back lies inside the face. A row with a fifth value has wings: the side stands out of the face as far as
    that share of the nose's depth (-1 its back, 1 its ridge) before it turns in to the ridge, so the base is a
    block with planes of its own; and `Face.nostril` lays a nostril on the underside of each."""
    hy, ry = HEAD[0][1], HEAD[1][1]
    y0 = hy + face.eye_y * ry                        # the eyes' line
    z, sink = (lambda y: skull.front(0.0, y)), 0.005
    wedge = lambda t: ((1.0, -1.0), (t, 1.0), (-t, 1.0), (-1.0, -1.0), (-0.4, -1.0), (0.4, -1.0))      # noqa: E731
    winged = lambda t, w: ((1.0, -1.0), (1.0, w), (t, 1.0), (-t, 1.0), (-1.0, w), (-1.0, -1.0), (-0.4, -1.0), (0.4, -1.0))   # noqa: E731
    wings = any(len(row) > 4 for row in face.nose)
    nose = Loft([(y0 + dy, half, (out + sink) / 2, z(y0 + dy) + (out - sink) / 2, winged(t, *w) if wings else wedge(t))
                 for dy, half, out, t, *w in face.nose])
    k.loft(k.head, "nose/nose", nose, k.p.skin)
    if face.nostril:         # on the underside, between the base and the row above it, half way out to the wing
        y = (nose.s[0][0] + nose.s[1][0]) / 2
        for sx in (-1, 1):
            at, lie = nose.seat(sx * 0.5 * nose.at(y)[0], y, 0.0004)
            _plate(k, k.head, "nose/nostril", ((-1.0, 0.45), (1.0, 1.0)), face.nostril, 0.75 * face.nostril, k.p.shade, at, lie, 0.0006)


# the line of a closed mouth, by its name: how high it is (a share of the head's half height) across the mouth,
# from -1 at the corner on the picture's right to 1 at the one on its left
MOUTH_LINES = {"smile": lambda u: 0.17 * u * u - 0.05, "frown": lambda u: -0.1 * u * u + 0.035,
               "smug": lambda u: 0.15 * max(0.0, u) ** 2 - 0.015, "wavy": lambda u: 0.03 * math.sin(u * 7), "flat": lambda u: 0.0}


def _lips(k: Parts, on, face: Face, mouth: str, was: str, mix: float) -> None:
    """A modelled mouth (Lips): the dark between the lips, a line when the mouth is closed and an opening (with a
    row of teeth) when it speaks; the upper lip over it, a plane in the skin's shade that dips in its middle; the
    lower lip under it, fuller, a ridge that stands out of the face; and a fold in the cheek at a corner that a
    smile raises. A closed mouth bends from one shape into the next as the painted line does."""
    fig, p, lips = k.fig, k.p, face.lips
    ry = HEAD[1][1]
    y0, half, thin = face.mouth_y, face.mouth_x, 1.0
    across = (-1.0, -0.62, -0.3, 0.0, 0.3, 0.62, 1.0)
    full = lambda u: max(0.0, 1.0 - u * u) ** 0.6                               # noqa: E731  how full a lip is across the mouth
    bow = lambda u: full(u) * (1.0 - 0.22 * max(0.0, 1.0 - abs(u) / 0.3))       # noqa: E731  the upper one dips in its middle
    curve = None
    if mouth in ("open", "yell", "o"):
        openness = max(0.0, min(1.0, fig.mouth_open))
        w, h = {"open": (0.24, 0.085), "yell": (0.3, 0.13), "o": (0.1, 0.07)}[mouth]
        half, h, thin = w * (0.75 + 0.25 * openness), h * (0.25 + 0.75 * openness), 0.8
        arch = lambda u: math.sqrt(max(0.0, 1.0 - u * u))                       # noqa: E731
        top, low, dark = (lambda u: y0 - 0.3 * h + h * arch(u)), (lambda u: y0 - 0.3 * h - h * arch(u)), "lp.pupil"
        if mouth != "o" and openness > 0.3:
            _ribbon(k, "mouth/teeth", on, [[(half * u, min(top(u) - 0.05 * h, y0 + 0.56 * h), 0.0016), (half * u, y0 + 0.08 * h, 0.0016)]
                                           for u in (-0.74, -0.4, 0.0, 0.4, 0.74)], "lp.tooth")
    else:
        line = lambda name: ((lambda u: lips.smile * MOUTH_LINES[name](u) + lips.skew * max(0.0, u) ** 2) if name == "smile"      # noqa: E731
                             else (lambda u: lips.bend * MOUTH_LINES[name](u)))
        curve = line(mouth if mouth in MOUTH_LINES else "flat")
        if fig.mouth_mix < 1.0 and was in MOUTH_LINES and was != mouth:        # becoming this mouth from the line before it
            old, new = line(was), curve
            curve = lambda u: (1 - mix) * old(u) + mix * new(u)                 # noqa: E731
        gap = lambda u: lips.line * (0.3 + 0.7 * max(0.0, 1.0 - u * u)) / ry    # noqa: E731
        top, low, dark = (lambda u: y0 + curve(u) + gap(u)), (lambda u: y0 + curve(u) - gap(u)), lips.ink
        across = (-1.1, *across, 1.1)                # the line runs a little past the lips, into the corners
    _ribbon(k, "mouth/line", on, [[(half * u, top(u), 0.0007), (half * u, low(u), 0.0007)] for u in across], dark)
    across = across[1:-1] if curve else across
    _ribbon(k, "mouth/upper", on, [[(half * u, top(u) + lips.upper * thin * bow(u) / ry, 0.0004), (half * u, top(u), 0.0013)]
                                   for u in across], p.shade)
    _ribbon(k, "mouth/lower", on, [[(half * u, low(u), 0.0012),
                                    (half * u, low(u) - 0.45 * lips.lower * thin * full(u) / ry, 0.0006 + lips.proud * thin * full(u)),
                                    (half * u, low(u) - lips.lower * thin * full(u) / ry, 0.0002)] for u in across], p.skin)
    if curve is None:
        return
    # the fold a smile makes in the cheek, from a raised corner up toward the nose: it comes and goes with the mouth
    folds = dict(lips.folds)
    fold = folds.get(mouth, (0.0, 0.0))
    if mix < 1.0 and was != mouth:
        fold = tuple((1 - mix) * a + mix * b for a, b in zip(folds.get(was, (0.0, 0.0)), fold))
    for sx, s in zip((-1, 1), fold):
        if s > 0.2:
            # (a short crease that starts just outside the corner and curves up and out of it)
            y, wide = y0 + curve(sx * 1.0), 0.009 * s
            _ribbon(k, "mouth/fold", on, [[(sx * (half + 0.03 + 0.045 * t * t - wide * b), y - 0.015 + (0.05 + 0.06 * s) * t, 0.0006),
                                           (sx * (half + 0.03 + 0.045 * t * t + wide * b), y - 0.015 + (0.05 + 0.06 * s) * t, 0.0006)]
                                          for t, b in ((0.0, 0.2), (0.4, 1.0), (1.0, 0.15))], p.shade)


def _mouth(k: Parts, on, limb, face: Face = FACE) -> None:
    """The mouth, in the shared vocabulary (expression.MOUTHS): a painted line that bends from one shape into the
    next, or a dark opening with a row of teeth that opens and closes with the voice; or, on a face that has
    them, modelled lips (_lips)."""
    fig, e = k.fig, k.fig.expression
    rx, ry = HEAD[1][0], HEAD[1][1]
    fig._rest_mouth = "smile"
    mouth = "smile" if e.mouth == "flat" else e.mouth
    y0 = face.mouth_y
    was = fig.mouth_from if fig.mouth_from != "flat" else "smile"
    mix = max(0.0, min(1.0, fig.mouth_mix))
    mix = mix * mix * (3 - 2 * mix)
    if face.lips:
        return _lips(k, on, face, mouth, was, mix)
    if mouth in ("open", "yell", "o"):
        openness = max(0.0, min(1.0, fig.mouth_open))
        w, h = {"open": (0.24, 0.085), "yell": (0.3, 0.13), "o": (0.1, 0.07)}[mouth]
        w, h = w * (0.75 + 0.25 * openness), h * (0.25 + 0.75 * openness)
        # the opening and the teeth are flat plates on the face's front, matte, as the eyes are
        lay = lambda fy, lift: on(0.0, fy, (lift - 0.002) / 0.03)       # noqa: E731
        turn = rotation(*on.turn(0.0, y0 - 0.3 * h), 0)
        _plate(k, k.head, "mouth-inside", ROUND, w * rx, h * ry, "lp.pupil", lay(y0 - 0.3 * h, 0.0012), turn, 0.0012)
        if mouth != "o" and openness > 0.3:
            _plate(k, k.head, "mouth-teeth", ((-1.0, 0.85), (1.0, 1.0)), 0.74 * w * rx, 0.24 * h * ry, "lp.tooth",
                   lay(y0 - 0.3 * h + 0.62 * h, 0.0028), turn, 0.0008)
        return
    shape = {"smile": lambda u: 0.17 * u * u - 0.05, "frown": lambda u: -0.1 * u * u + 0.035,
             "smug": lambda u: 0.15 * max(0.0, u) ** 2 - 0.015, "wavy": lambda u: 0.03 * math.sin(u * 7), "flat": lambda u: 0.0}
    curve = shape.get(mouth, shape["flat"])
    if fig.mouth_mix < 1.0 and was in shape and was != mouth:       # becoming this mouth from the line before it
        t, old, new = mix, shape[was], curve
        curve = lambda u: (1 - t) * old(u) + t * new(u)             # noqa: E731
    size = getattr(k.head, "k", 1.0)         # the head's size on this build: a painted line is as much thinner
    fig._stroke("mouth/line", [on(face.mouth_x * u, y0 + curve(u), -0.1) for u in (i / 4 - 1 for i in range(9))], 0.0019 * size)
    # the one fold a smile makes in the cheek, from each corner up toward the nose (FOLDS), in the skin's shade:
    # it comes and goes with the mouth, as the line does
    fold = FOLDS.get(mouth, (0.0, 0.0))
    if mix < 1.0 and was != mouth:
        fold = tuple((1 - mix) * a + mix * b for a, b in zip(FOLDS.get(was, (0.0, 0.0)), fold))
    for sx, s in zip((-1, 1), fold):
        if s > 0.2:
            y = y0 + curve(sx * 1.0)
            fig._stroke("mouth/fold", [on(sx * (face.mouth_x + 0.035), y + 0.005, -0.1), on(sx * (face.mouth_x + 0.075), y + 0.035 + 0.075 * s, -0.1)],
                        0.0017 * size, k.p.shade)


def _body(k: Parts) -> None:
    _legs(k)          # first: the trunk sits over their tops
    _trunk(k)
    _arms(k)
    _head(k)


# ----------------------------------------------------------------------------- outfits: one function a profession
# What an outfit is made of is written once, below, and placed by asking the build (`k.b`): a height on the shirt is
# a share of the way from the belt to the neck (_up), a width a share of the chest's flat front (_across), a collar
# stands where the trunk ends at the neck, a strap lies on the shoulder's own slope, a hat is fitted to the head's
# tables, and what hangs on a belt hangs on its corners (_corner). So the same parts dress every build.
# What must keep its corners (a box, a pointed flap, a shield) is a `_piece`: the finish draws it as it is given.
class Worn:
    """A carry turned about a point: what is drawn with it (Parts.loft, put, flat, hung, _piece) is designed
    upright and comes out turned, as one piece. A cap worn tilted back, a radio that faces out of a hip."""

    def __init__(self, carry, turn, about):
        self.carry, self.turn, self.about = carry, turn, tuple(about)

    def point(self, p) -> Vec3:
        d = [p[i] - self.about[i] for i in range(3)]
        return self.carry.point(tuple(self.about[i] + sum(self.turn[i][j] * d[j] for j in range(3)) for i in range(3)))

    def basis(self, b):
        return self.carry.basis(m._mul(self.turn, b))

    def undo(self, p):
        """Where a point of the carry was before the turn: what is drawn there comes out at `p`."""
        d = [p[i] - self.about[i] for i in range(3)]
        return tuple(self.about[i] + sum(self.turn[j][i] * d[j] for j in range(3)) for i in range(3))

    def off(self, dx: float = 0.0, dy: float = 0.0, dz: float = 0.0):
        """A place given from the point it turns about: `dx` across, `dy` up, `dz` out."""
        return (self.about[0] + dx, self.about[1] + dy, self.about[2] + dz)


def _piece(k: Parts, carry, name: str, sections, material: str, at, turn=m.IDENTITY, flat: float = 1.0) -> None:
    """A small solid that keeps its corners (a Loft): `sections` are (how far along it, half width, half thickness
    [, forward[, flat]]) from its own origin, which goes to `at`; `turn` says how it lies (a Loft.seat's turn lays
    it on that facet: its length up the facet, its thickness out of it). `flat` 1 is a box, 0 a ridge between two
    knife edges, between them a box with chamfered edges; a box or a ridge is half the triangles of the others."""
    loft = Loft([(*s, 0.0) if len(s) == 3 else s for s in sections], flat)
    mid = (loft.s[0][0] + loft.s[-1][0]) / 2          # a loft is turned about its middle: say where that goes
    k.loft(carry, name, loft, material, turn,
           move=(at[0] + turn[0][1] * mid, at[1] + turn[1][1] * mid - mid, at[2] + turn[2][1] * mid))


def _lie(along, out):
    """The turn that lays a piece with its length along `along` and its thickness toward `out`."""
    y = unit(Vec3(*along))
    z = Vec3(*out)
    z = unit(z - scaled(y, z.x * y.x + z.y * y.y + z.z * y.z))
    x = cross(y, z)
    return ((x.x, y.x, z.x), (x.y, y.y, z.y), (x.z, y.z, z.z))


def _up(k: Parts, share: float) -> float:
    """A height on the shirt: `share` of the way from the belt up to where the trunk ends at the neck."""
    return BELT_Y + share * (k.b.trunk.s[-1][0] - BELT_Y)


def _across(k: Parts, y: float, loft: Loft | None = None) -> float:
    """Half the width of the chest's flat front at height `y` (or of another part's, `loft`): what lies within it
    lies flat."""
    loft = loft or k.b.trunk
    ring = loft.ring(y)
    front = max(z for _x, z in ring)
    return max(0.5 * loft.at(y)[0], max(x for x, z in ring if z > front - 1e-6))


def _laid(loft: Loft, x: float, y0: float, y1: float, lift: float = 0.0):
    """Where a stiff flat thing lies on a part's front between two heights, `x` from its middle: the place of its
    lower end and the turn that lays its length up the part. It rests on whatever stands highest between the two
    (`lift` above that), as a starched collar's wing rests on a chest."""
    z0, z1 = loft.front(x, y0), loft.front(x, y1)
    along = unit(Vec3(0.0, y1 - y0, z1 - z0))
    out = Vec3(0.0, -along.z, along.y)
    rise = max([0.0, *((s[0] - y0) * out.y + (loft.front(x, s[0]) - z0) * out.z for s in loft.s if y0 < s[0] < y1)])
    return (x, y0 + out.y * (rise + lift), z0 + out.z * (rise + lift)), _lie(along, out)


def _panel(k: Parts, carry, name: str, loft: Loft, rows, material: str, proud: float = 0.004, deep: float = 0.008,
           back: bool = False) -> None:
    """A piece of cloth that lies on a part's front (or its back) and follows it: a lapel, the shirt between two
    lapels, a tie's blade, a seam. `rows` are (height, where it starts across the part, where it ends), each at
    its own height, with straight edges from one to the next; a row is added at each of the part's own sections
    between them, and across the part it bends at the corners of the part's outline (at the two that stand
    highest, if it lies over more), so it bends where the part does. It stands `proud` of the part's surface and
    goes `deep` under it (a part's facets dent that far), keeps its corners, and closes on a point at each end."""
    rows = sorted((y, min(a, b), max(a, b)) for y, a, b in rows)
    surface, out = (loft.back, -1.0) if back else (loft.front, 1.0)

    def bends(y, a, b):     # where the part's outline turns between the two edges: two places (an edge, if fewer)
        xs = sorted({x for x, z in loft.ring(y) if a + 1e-6 < x < b - 1e-6 and abs(surface(x, y) - z) < 1e-9})
        za, zb = surface(a, y), surface(b, y)
        over = lambda x: out * (surface(x, y) - (za + (zb - za) * (x - a) / (b - a)))       # noqa: E731  above the straight line
        while len(xs) > 2:
            xs.remove(min(xs, key=over))
        return [a] * (2 - len(xs)) + xs

    def across(y):          # its two edges at a height between two rows
        for (y0, a0, b0), (y1, a1, b1) in zip(rows, rows[1:]):
            if y <= y1:
                t = (y - y0) / (y1 - y0)
                return a0 + (a1 - a0) * t, b0 + (b1 - b0) * t
        return rows[-1][1:]

    heights = sorted({*(r[0] for r in rows), *(s[0] for s in loft.s if rows[0][0] < s[0] < rows[-1][0])})
    middle = (min(r[1] for r in rows) + max(r[2] for r in rows)) / 2

    def section(y, corners):          # a Loft's section with these corners (x, z): its own outline
        zs = [z for _x, z in corners]
        zc, rz = (max(zs) + min(zs)) / 2, max(1e-5, (max(zs) - min(zs)) / 2)
        rx = max(1e-5, max(abs(x - middle) for x, _z in corners))
        return (y, rx, rz, zc, [((x - middle) / rx, (z - zc) / rz) for x, z in corners])

    sections = []
    for y in heights:
        a, b = across(y)
        a, b = (a, b) if b - a > 0.0006 else ((a + b) / 2 - 0.0003, (a + b) / 2 + 0.0003)      # a point keeps a width
        c, d = bends(y, a, b)
        shown = [(x, surface(x, y) + out * proud) for x in (b, d, c, a)]          # the side that shows: over the part
        under = [(x, surface(x, y) - out * deep) for x in (a, b)]                # and the one inside it
        sections.append(section(y, shown + under if not back else under[::-1] + shown[::-1]))
    ends = []
    for (y, _rx, _rz, zc, _corners), step in ((sections[0], -2e-5), (sections[-1], 2e-5)):
        ends.append(section(y + step, [(sum(across(y)) / 2, zc)] * 6))
    sections = [ends[0], *sections, ends[1]]
    part = Loft(sections).limb(name, carry, material, k.fig.looks, move=(middle, 0.0, 0.0))
    k.made.append(_own_rows(part, len(sections)))


def _shoulder(trunk: Loft, x: float | None = None):
    """(half width, height, forward) of the top of the shoulder `x` from the middle, on the slope from the neck out;
    with no `x`, of the shoulder's point: the highest place where the trunk is about as wide as it gets."""
    top = trunk.s[::-1]
    wide = 0.95 * max(s[1] for s in top)
    if x is None:
        return next((s[1], s[0], s[3]) for s in top if s[1] >= wide)
    for a, b in zip(top, top[1:]):
        if a[1] <= x <= b[1]:
            t = (x - a[1]) / max(1e-9, b[1] - a[1])
            return x, a[0] + (b[0] - a[0]) * t, a[3] + (b[3] - a[3]) * t
        if b[1] >= wide:
            return b[1], b[0], b[3]
    return top[0][1], top[0][0], top[0][3]


def _stand(k: Parts, material: str, low: float = 0.03, high: float = 0.0, tilt: float = 0.0,
           name: str = "collar/stand", out: float = 0.0, front: float = 1.0) -> Loft:
    """A collar that stands round the neck, from `low` under where the trunk ends at the neck, wider there and
    proud of the back and the front, to `high` over it. Tilted, it is high behind the neck and comes down to the
    front, as a shirt's collar does. Gives the ring as drawn upright (a kerchief is a band of it).
    `out` makes it that much larger, to go round another collar. `front` is how much of its depth in front of the
    neck's middle it keeps: under 1 it stops at the sides of the neck, where it runs into the neck, as a jacket's
    collar does, which is open in front."""
    yn, rxn, rzn, zcn = k.b.trunk.s[-1][:4]
    lean = low * math.sin(math.radians(tilt))        # its foot stays under the neck however it is tilted
    cut = (1.0 - front) / 2                          # the share of its depth that is taken off its front
    foot, rim = rzn + 0.014 + out, rzn + 0.006 + out
    ring = Loft([(yn - low, rxn + 0.02 + out, foot * (1.0 - cut), zcn + lean - foot * cut),
                 (yn + high, rxn + 0.005 + out, rim * (1.0 - cut), zcn - rim * cut)], flat=0.6)
    carry = Worn(k.chest, rotation(0, -tilt, 0), (0.0, yn + high, zcn)) if tilt else k.chest
    k.loft(carry, name, ring, material)
    return ring


def _open_collar(k: Parts, tilt: float = 14.0, drop: float = 0.068, under: str | None = None, material: str | None = None,
                 spread: float = 0.016, high: float = 0.0, wide: float = 0.021, thick: float = 0.005, on: Loft | None = None,
                 top: float = 0.005, rise: float = 0.004, lift: float = 0.003) -> None:
    """A shirt's collar: a band that stands round the neck, highest behind it (`high` over where the trunk ends);
    two wings folded down from the sides of the neck onto the chest, stiff and with thickness (`wide` and `thick`
    are half a wing's width and half its thickness), their points `drop` under the neck; between them the opening
    down to the first button, with an undershirt in it.
    `spread` is how far a wing's point stands out from where it leaves the neck: worn open the points are apart;
    below 0 they come in toward the middle, as a collar closed over a tie has them (the opening is then the shirt
    itself: `under`). `material` is the shirt's colour when it is not the person's top (a shirt under a jacket,
    whose lapels lie over the wings: thinner wings stay under them), and `on` what the wings and the opening lie
    on when that is not the trunk (a jacket's body, `Coat.loft`).
    A wing's top is `top` wide (half of it) and `rise` over where the trunk ends at the neck, and its middle
    stands `lift` off what it lies on: one that is wide at its top and starts lower hangs from the band's front,
    as the wing of a collar closed over a tie does under a chin."""
    p, c, trunk = k.p, k.chest, k.b.trunk
    yn, rxn = trunk.s[-1][:2]
    cloth, on = material or p.top, on or trunk
    _stand(k, cloth, low=0.034, high=high, tilt=tilt, name="collar/band")
    # the opening: a triangle of the undershirt, its point down
    at, turn = _laid(on, 0.0, yn - drop - 0.004, yn - 0.012, -0.001)
    _piece(k, c, "collar/under", [(0.0, 0.002, 0.004), (drop - 0.008, rxn - 0.006, 0.004)], under or p.trim, at, turn)
    for sx in (-1, 1):
        # a wing: a kite from the side of the neck down to its point, which stands out from the neck's side
        at, turn = _laid(on, sx * (rxn + 0.004), yn - drop, yn + min(0.0, rise), lift)
        roll = math.degrees(math.atan2(spread, drop))
        _piece(k, c, "collar/wing", [(-0.003, 0.002, thick), (0.52 * drop, wide, thick), (drop + rise, top, thick)], cloth,
               (at[0] + sx * (spread - 0.008), at[1], at[2]), m._mul(turn, rotation(0, 0, sx * roll)))


def _button(k: Parts, carry, name: str, loft: Loft, x: float, y: float, material: str, size: float = 0.0095,
            lift: float = 0.003, shape: str = "stud") -> None:
    """A button on a part's front. "stud": a small stud set on its corner, so it reads as a diamond (a shirt's, a
    pocket's). "round": a flat disc with eight sides, `size` its radius, lying on the facet (a jacket's)."""
    if shape == "round":
        at, turn = loft.seat(x, y, lift)
        thick = 0.3 * size
        _piece(k, carry, name, [(-size, 0.41 * size, thick), (-0.41 * size, size, thick), (0.41 * size, size, thick),
                                (size, 0.41 * size, thick)], material, at, turn)
        return
    k.flat(carry, name, loft, x, y, (size, size, 0.7 * size), material, lift=lift, roll=45, soft=0.55, samples=(8, 6))


def _flap(k: Parts, carry, loft: Loft, x: float, y: float, half: float, material: str, tall: float = 0.037,
          point: float = 0.009, name: str = "pocket/flap", thick: float = 0.008, sink: float = 0.002) -> None:
    """A pocket's flap on a part's front, its top edge at height `y`, `tall` from there down: its lower edge comes
    to a point in the middle over the last `point` of that (0: it is cut straight, as a jacket's is). It is thick
    enough to stand out of the facets it lies on: `thick` is half its thickness and its middle lies `sink` under
    the part's surface (thinner and less sunk, it is flatter: for cloth that dents less)."""
    at, turn = loft.seat(x, y - 0.018, -sink)
    low = 0.018 - tall
    _piece(k, carry, name, [(low, 0.003 if point else half, thick), *([(low + point, half, thick)] if point else []),
                            (0.018, half, thick)], material, at, turn)


def _pocket(k: Parts, x: float, y: float, half: float, tall: float = 0.07) -> None:
    """A patch pocket on the chest, its top at height `y`: the patch, a flap that comes down to a point over it,
    a button on the flap."""
    p, c, trunk = k.p, k.chest, k.b.trunk
    at, turn = _laid(trunk, x, y - tall, y - 0.004, -0.004)
    _piece(k, c, "pocket/pocket", [(0.0, 0.94 * half, 0.007), (tall - 0.004, 0.94 * half, 0.007)], p.top, at, turn)
    _flap(k, c, trunk, x, y, half, p.top)
    _button(k, c, "pocket/button", trunk, x, y - 0.017, p.buttons, 0.0085, 0.007)


def _shirt_front(k: Parts, pockets: bool = True, buttons=(0.68, 0.43, 0.19)) -> None:
    """A uniform shirt's front: an open collar over an undershirt, a line of buttons (each a share of the way from
    the belt to the neck), two pockets with pointed flaps."""
    _open_collar(k)
    for share in buttons:
        _button(k, k.chest, "placket/button", k.b.trunk, 0.0, _up(k, share), k.p.buttons)
    if pockets:
        y = _up(k, 0.6)
        half = min(0.038, 0.42 * _across(k, y))
        for sx in (-1, 1):
            _pocket(k, sx * (_across(k, y) - half - 0.002), y, half)


def _epaulettes(k: Parts, material: str | None = None, wide: float = 0.019) -> None:
    """A strap on each shoulder, from near the collar out to the sleeve's seam, lying on the shoulder's slope, with
    a button at the collar's end."""
    trunk = k.b.trunk
    x0, y0, z0 = _shoulder(trunk, trunk.s[-1][1] + 0.027)
    x1, y1, _z1 = _shoulder(trunk)
    length = math.hypot(x1 - x0, y1 - y0)
    ax, ay = (x1 - x0) / length, (y1 - y0) / length              # along the strap, out and down
    nx, ny = -ay, ax                                             # out of the shoulder
    rise = max([0.0, *((s[1] - x0) * nx + (s[0] - y0) * ny for s in trunk.s if x0 < s[1] < x1 and s[0] > y1)])
    for sx in (-1, 1):
        turn = _lie((sx * ax, ay, 0.0), (sx * nx, ny, 0.0))
        foot = lambda along, out: (sx * (x0 + ax * along + nx * (rise + out)), y0 + ay * along + ny * (rise + out), z0 - 0.004)
        _piece(k, k.chest, "epaulette/strap", [(0.0, wide, 0.007), (length + 0.014, wide, 0.007)], material or k.p.top,
               foot(-0.002, 0.002), turn)
        k.put(k.chest, "epaulette/button", foot(0.014, 0.01), (0.0075, 0.0075, 0.004), k.p.buttons, turn, samples=(8, 6))


def _badge(k: Parts, carry, seat, size: float) -> None:
    """A shield lying on a facet (`seat` is a Loft's seat()), `size` half its height: a point at the top and one at
    the bottom, straight sides, a ridge down its middle from which its two faces fall away."""
    at, turn = seat
    t = 0.32 * size
    _piece(k, carry, "badge/badge", [(-size, 0.05 * size, 0.3 * t), (-0.32 * size, 0.86 * size, t), (0.7 * size, 0.96 * size, t),
                                     (size, 0.05 * size, 0.3 * t)], k.p.shiny, at, turn, flat=0.0)


def _corner(loft: Loft, y: float, where: str, side: float = 0.5) -> float:
    """The angle, for Loft.around, of a place on one of a part's four corner facets at height `y`: "front-left",
    "front-right", "back-left" or "back-right" (the picture's left and right, seen from the front). `side` is how
    far along the facet: 0 where it leaves the front (or the back), 1 where it reaches the side."""
    ring, zc = loft.ring(y), loft.at(y)[2]
    front = where.startswith("front")
    want = math.radians(45.0 if front else 135.0)

    def off(edge):          # how far the side between two corners faces from the corner asked for (its left one)
        (ax, az), (bx, bz) = edge
        return abs(math.atan2(bz - az, ax - bx) - want) if math.hypot(bx - ax, bz - az) > 1e-9 else 9.0

    a, b = min(zip(ring, ring[1:] + ring[:1]), key=off)
    if (a[1] < b[1]) == front:                      # from its end at the front (or the back) to its end at the side
        a, b = b, a
    deg = math.degrees(math.atan2(a[0] + (b[0] - a[0]) * side, a[1] + (b[1] - a[1]) * side - zc))
    return deg if where.endswith("left") else -deg


def _hang(carry, loft: Loft, deg: float, y: float) -> Worn:
    """What hangs on a part's side, `deg` round it at height `y`, is drawn with this: upright and facing the
    front, from the place on the facet (Worn.off), and it comes out facing out of the facet."""
    at, yaw = loft.around(deg, y)
    return Worn(carry, rotation(yaw, 0, 0), at)


GEAR_SINK = 0.008      # what hangs on a belt starts this far inside it: a box wider than its facet still touches


def _pouch(k: Parts, on: Worn, material: str, snap: str, wide: float = 0.022, deep: float = 0.012) -> None:
    """A box pouch on a belt, `deep` off it (slim, as the sheet's profile has it): the box, a flap that closes
    over its top and overhangs it all round, a snap on the flap."""
    half = (deep + GEAR_SINK) / 2
    _piece(k, on, "pouch/pouch", [(-0.044, wide, half), (0.036, wide, half)], material, on.off(dz=half - GEAR_SINK))
    _piece(k, on, "pouch/flap", [(-0.009, wide + 0.003, half + 0.002), (0.041, wide + 0.003, half + 0.002)], material,
           on.off(dz=half - GEAR_SINK))
    k.put(on, "pouch/snap", on.off(dy=0.003, dz=deep + 0.002), (0.008, 0.008, 0.0035), snap, samples=(8, 6))


def _radio(k: Parts, on: Worn, material: str, outer: float, slots=(0.026, 0.015, 0.004), deep: float = 0.011) -> None:
    """A radio on a belt, `deep` off it: its body, the slots of its speaker, a short thick antenna on its outer
    side (`outer` is 1 when that is the picture's left, -1 when it is the right)."""
    half = (deep + GEAR_SINK) / 2
    _piece(k, on, "radio/radio", [(-0.04, 0.0215, half), (0.039, 0.0215, half)], material, on.off(dz=half - GEAR_SINK))
    for dy in slots:
        _piece(k, on, "radio/slot", [(-0.0028, 0.014, 0.002), (0.0028, 0.014, 0.002)], "lp.slot", on.off(dy=dy, dz=deep - 0.0005))
    _piece(k, on, "radio/antenna", [(0.0, 0.008, 0.008), (0.012, 0.008, 0.008), (0.014, 0.0058, 0.0058), (0.046, 0.0052, 0.0052)],
           material, on.off(dx=outer * 0.0105, dy=0.039, dz=deep - 0.01))


def _duty_belt(k: Parts, pouches=("front-left", "back-left"), radio: str | None = "front-right") -> None:
    """A belt with a buckle and what it carries, each thing on one of the belt's four corners (_corner): box
    pouches, and a radio with its antenna. What is on a front corner is nearer the buckle and turned to the front;
    what is on a back corner is nearer the hip, and slimmer, so it stays behind the arm. As the sheet has it:
    pouches on his right hip, one in front and one behind, and the radio on his left, so that the front shows a
    pouch on the picture's left and the radio on its right, and the back the radio on its left (from behind,
    past the hip) and one pouch on its right."""
    p, h, belt = k.p, k.hips, k.b.belt
    k.loft(h, "belt/belt", belt, p.dark)
    at, turn = belt.seat(0.0, BELT_Y, 0.002)
    _piece(k, h, "buckle/buckle", [(-0.0225, 0.026, 0.006), (0.0225, 0.026, 0.006)], p.metal, at, turn)
    hang = lambda where: _hang(h, belt, _corner(belt, BELT_Y, where, 0.3 if where.startswith("front") else 0.7), BELT_Y)
    for where in pouches:
        front = where.startswith("front")
        _pouch(k, hang(where), p.dark, p.buttons, 0.022 if front else 0.021, 0.012 if front else 0.009)
    if radio:
        _radio(k, hang(radio), p.dark, 1.0 if radio.endswith("left") else -1.0)


def _peak(k: Parts, carry, at, half: float, reach: float, material: str, drop: float = PEAK_DROP, sink: float = 0.03,
          name: str = "cap/peak") -> None:
    """A hat's peak: a stiff plate that leaves the hat's front at `at`, `half` wide, and reaches `reach` forward,
    sloping down by `drop` degrees and narrowing to its front edge. It starts `sink` inside the hat, so that its
    corners meet the hat's sides where they turn back."""
    a = math.radians(drop)
    _piece(k, carry, name, [(0.0, half, 0.005), (sink + 0.55 * reach, 0.93 * half, 0.0045), (sink + reach, 0.62 * half, 0.0035)],
           material, (at[0], at[1] + sink * math.sin(a), at[2] - sink * math.cos(a)), rotation(0, -(90 + drop), 0))


def _covering(crown: Loft, skull: Loft, worn, clear: float = 0.008) -> Loft:
    """A hat's crown, made tall enough to cover the top of the head it is worn on: `worn` (a point as the head has
    it -> the same point as the crown is drawn) says how the hat is tilted."""
    ys = skull.s[-1][0]
    need = max(worn((x, ys, z))[1] for x, z in skull.ring(ys)) + clear
    top = crown.s[-1]
    return Loft([*crown.s[:-1], (max(top[0], need), *top[1:])], crown.flat, crown.crease, crown.facet)


def _peaked_cap(k: Parts, band: str = "lp.band", peak: str = "lp.patent") -> None:
    """A peaked cap, worn tilted back: a band round the head; a crown that flares out over it at the sides and the
    back, rises to the front and closes in a flat top; a dark peak that slopes down over the brow; a badge on
    the crown's front; a button at each end of the band."""
    p = k.p
    y0, y1 = CAP_BAND.s[0][0], CAP_BAND.s[-1][0]
    brow = (0.0, y0, CAP_BAND.front(0.0, y0))                 # the cap turns about the band's front, over the brow
    cap = Worn(k.head, rotation(0, CAP_TILT, 0), brow)
    k.loft(cap, "cap/band", CAP_BAND, band)
    for sx in (-1, 1):
        k.hung(cap, "cap/button", CAP_BAND, sx * 68, (y0 + y1) / 2, (0.009, 0.009, 0.0045), p.buttons, out=0.001, samples=(8, 6))
    lift = Worn(cap, rotation(0, CAP_RISE, 0), (0.0, y1, CAP_BAND.front(0.0, y1)))      # the crown, raised at the front
    crown = _covering(CAP_CROWN, k.b.skull, lambda q: lift.undo(cap.undo(q)))
    k.loft(lift, "cap/crown", crown, p.top)
    _badge(k, lift, crown.seat(0.0, crown.s[1][0] - 0.008, 0.004), 0.024 * HEAD_K)
    _peak(k, k.head, (0.0, y0 + 0.002, brow[2]), 0.95 * CAP_BAND.at(y0)[0], 0.043 * HEAD_K, peak)     # out of the band's lower edge


def _officer(k: Parts) -> None:
    _shirt_front(k)
    _epaulettes(k)
    y = _up(k, 0.675)
    _badge(k, k.chest, k.b.trunk.seat(-(_across(k, y) - 0.019), y, 0.003), 0.023)     # on his left, over the pocket
    _duty_belt(k)
    _peaked_cap(k)


# -- the cook: the same body in whites
TOQUE_BAND = Loft(_bigger([(0.924, 0.0765, 0.082, 0.006), (0.968, 0.078, 0.083, 0.006)], HEAD_K), flat=0.66)
TOQUE_TOP = Loft(_bigger([(0.964, 0.079, 0.084, 0.006), (1.006, 0.105, 0.108, 0.004), (1.08, 0.114, 0.116, -0.002),
                          (1.114, 0.086, 0.09, -0.006)], HEAD_K), flat=0.55, crease=HAT_CREASE)


def _toque(k: Parts) -> None:
    """A chef's hat: a straight band, and a top that swells out over it."""
    k.loft(k.head, "toque/band", TOQUE_BAND, k.p.top)
    k.loft(k.head, "toque/top", TOQUE_TOP, k.p.top)


def _double_breasted(k: Parts, rows: int = 4) -> None:
    """A chef's jacket: a standing collar, two columns of buttons, a neckerchief with its knot."""
    p, c = k.p, k.chest
    yn = k.b.trunk.s[-1][0]
    ring = _stand(k, p.top)
    k.loft(c, "kerchief/band", ring.band(yn - 0.026, yn - 0.012, 0.004), p.dark)
    k.flat(c, "kerchief/knot", k.b.trunk, 0.0, yn - 0.042, (0.02, 0.02, 0.008), p.dark, lift=0.002, roll=45, soft=0.6, samples=(8, 6))
    for i in range(rows):
        y = _up(k, 0.71 - 0.158 * i)
        for sx in (-1, 1):
            k.flat(c, "jacket/button", k.b.trunk, sx * 0.41 * _across(k, y), y, (0.008, 0.008, 0.004), p.buttons, soft=0.6,
                   samples=(8, 6))


def _apron(k: Parts) -> None:
    """A waist apron: its string round the waist, and a panel down the front of the legs to the knee."""
    p, h = k.p, k.hips
    k.loft(h, "apron/string", k.b.pelvis.band(BELT_Y, BELT_Y + 0.024, 0.006), p.trim)
    if "sit" in k.fig.expression.extras:     # seated, it lies over the lap instead of hanging through the legs
        k.block(h, "apron/panel", (0.0, BELT_Y - 0.032, k.b.pelvis.front(0.0, BELT_Y - 0.03) + 0.07), (0.076, 0.012, 0.085), p.trim,
                soft=0.3, samples=(14, 10))
    else:
        k.block(h, "apron/panel", (0.0, BELT_Y - 0.095, k.b.pelvis.front(0.0, BELT_Y - 0.05) + 0.005), (0.076, 0.1, 0.008), p.trim,
                soft=0.3, samples=(14, 10))


def _cook(k: Parts) -> None:
    _double_breasted(k)
    _apron(k)
    _toque(k)


# -- the firefighter: the same body in a turnout coat
HELMET = Loft(_bigger([(0.914, 0.086, 0.098, 0.004), (0.96, 0.088, 0.1, 0.004), (1.008, 0.076, 0.088, 0.002),
                       (1.036, 0.04, 0.048, 0.0)], HEAD_K), flat=0.6)
HELMET_BRIM = Loft(_bigger([(0.907, 0.104, 0.126, -0.008), (0.92, 0.104, 0.126, -0.008)], HEAD_K), flat=0.6)


def _limb_bands(k: Parts, material: str) -> None:
    """A band round each forearm and each shin, where a turnout coat and its trousers carry them."""
    for side in ("l", "r"):
        k.cuff(f"band_{side}/arm", f"sleeve_{side}/fore", 0.5, 0.7, material)
        k.cuff(f"band_{side}/leg", f"leg_{side}/shin", 0.5, 0.66, material)


def _helmet(k: Parts) -> None:
    """A fire helmet: a dome, a brim that is longest at the back, a crest over the top, a shield on the front."""
    k.loft(k.head, "helmet/dome", HELMET, "lp.helmet")
    k.loft(k.head, "helmet/brim", HELMET_BRIM, "lp.helmet")
    top = HELMET.s[-1][0]
    k.block(k.head, "helmet/crest", (0.0, top - 0.012, HELMET.s[-1][3]), (0.011, 0.022, 0.078), "lp.helmet", soft=0.4, samples=(10, 10))
    y = (HELMET.s[0][0] + HELMET.s[1][0]) / 2 + 0.014
    _badge(k, k.head, HELMET.seat(0.0, y, 0.003), 0.022)


def _firefighter(k: Parts) -> None:
    for y in (_up(k, 0.345), _up(k, 0.655)):         # the coat's reflective stripes
        k.loft(k.chest, "band/band", k.b.trunk.band(y - 0.012, y + 0.012, 0.005), k.p.trim)
    _limb_bands(k, k.p.trim)
    _stand(k, k.p.top)
    _duty_belt(k, pouches=(), radio=None)
    _helmet(k)


# -- a suit: the same body in a jacket over a shirt and a tie. The long sleeves are the jacket's (the person's
# `top`) and its body is a coat of its own over the trunk and the hips (`_coat`); what makes a suit is written
# below, part by part, each usable without the others
def _into(carry, at) -> tuple:
    """A place of the figure as it is posed, in `carry`'s own space (the rest pose's): what `carry.point` undoes."""
    q = carry.rest.apply(carry.now.undo(at))
    p = (q.x, q.y - carry.lift - carry.shift, q.z)
    return tuple(carry.pivot[i] + (p[i] - carry.pivot[i]) / carry.scale[i] for i in range(3))


_FORMULA = 2000        # the longest formula a part is written with: the paper finish's engine takes none over 2048
#                        characters (srlocations.templates.MAX_SURFACE_EXPRESSION)


def _skin(k: Parts, carry, name: str, rings, material: str, crease: float = 0.0, facet: float = FACET, measured=None,
          ends=None) -> None:
    """A drawn part through rings of corners that are each given where they are: (x, y, z) in `carry`'s space,
    round as a Loft's ring goes, as many in every ring. It says what a Loft cannot: a ring that is not level, and
    a part some of whose rings another bone carries (those rings are given where that bone puts them, brought into
    `carry` with `_into`: cloth between two bones). It keeps its corners and closes on a point at each end (`ends`;
    the middle of its end rings if not given). With `crease` its sides break into facets as a Loft's do (`facet`
    across, millimetres); `measured` are the rings those are measured on: the rest pose's, so that the same facets
    ride the part however it is posed. A part with many corners is made as several parts of the same name, one
    above the other, so that none has a formula longer than the paper finish's engine takes (`_FORMULA`).
    (`_shell` draws a part corner by corner too, for the face and the hair; this one also says how its sides
    break and where it closes.)"""
    n = len(rings[0])
    middle = lambda ring: tuple(sum(p[i] for p in ring) / n for i in range(3))      # noqa: E731
    ends = ends or (middle(rings[0]), middle(rings[-1]))
    # its faces look outward, as a Loft's do: rings given the other way round are turned (what the part holds,
    # counted the way its corners run, comes out below 0 for a Loft)
    held = sum(a[0] * (b[1] * c[2] - b[2] * c[1]) + a[1] * (b[2] * c[0] - b[0] * c[2]) + a[2] * (b[0] * c[1] - b[1] * c[0])
               for lo, hi in zip(rings, rings[1:]) for i in range(n)
               for a, b, c in ((lo[i], lo[(i + 1) % n], hi[(i + 1) % n]), (lo[i], hi[(i + 1) % n], hi[i])))
    if held > 0:
        rings, measured = ([[ring[0], *ring[:0:-1]] for ring in each] if each else each for each in (rings, measured))
    rows = [[tuple(ends[0])] * n, *rings, [tuple(ends[1])] * n]
    corner = lambda i: f"(max(1-abs(u-{i}),0)" + (f"+max(1-abs(u-{n}),0))" if i == 0 else ")")      # noqa: E731  1 on corner i

    def piece(first, last):     # the rows first..last as one part: its three formulas, where it is, how far it reaches
        part = rows[first:last + 1]
        every = [p for row in part for p in row]
        at = tuple((min(p[i] for p in every) + max(p[i] for p in every)) / 2 for i in range(3))

        def axis(a):            # a coordinate of every corner, running straight from ring to ring as v counts them
            terms = []
            for i in range(n):
                text = f"{part[0][i][a] - at[a]:.5f}"
                for j in range(1, len(part)):
                    step = part[j][i][a] - part[j - 1][i][a]
                    if abs(step) > 5e-6:
                        text += f"+({step:.5f})*min(max(v-{j - 1},0),1)"
                terms.append(f"({text})*{corner(i)}")
            return "+".join(terms)

        return (axis(0), axis(1), axis(2)), at, tuple(max(1e-4, max(abs(p[i] - at[i]) for p in every)) for i in range(3))

    # The paper finish's engine takes no formula longer than _FORMULA. A part that has more to say is written as
    # several, one above the other, each on from the ring the last one ended on (they bear the same name).
    pieces, todo = [], [(0, len(rows) - 1)]
    while todo:
        first, last = todo.pop(0)
        made = piece(first, last)
        if max(len(text) for text in made[0]) > _FORMULA and last - first > 1:
            todo[:0] = [(first, (first + last) // 2), ((first + last) // 2, last)]
        else:
            pieces.append((first, last, *made))
    if crease:              # as Loft.limb says it: how wide each side is and how long each band (0: a closed end)
        on = measured or rings
        bands = [0.0, *(sum(math.dist(a, b) for a, b in zip(lo, hi)) / n for lo, hi in zip(on, on[1:])), 0.0]
        width = lambda ring, i: math.dist(ring[i], ring[(i + 1) % n])      # noqa: E731
        sides = [sum((width(a, i) + width(b, i)) / 2 * h for a, b, h in zip(on, on[1:], bands[1:])) / sum(bands) for i in range(n)]
        # (written as several, none of its sides is cut across: along a ring that two pieces share the only
        # points are then its corners, which both have, and the pieces meet with no crack)
        across = facet if len(pieces) == 1 else max(facet, 1000.0 * max(sides) / 1.45)
    for first, last, (x, y, z), at, reach in pieces:
        role = "drawn"
        if crease:
            role += (f" facet:{across:g}:{crease:g}:" + ",".join(str(round(w * 1000)) for w in sides)
                     + ":" + ",".join(str(round(h * 1000)) for h in bands[first:last]))
        k.made.append(Limb(x=x, y=y, z=z, u=(0, n), v=(0, last - first), samples=(n, last - first), closed=(True, False),
                           radii=reach, at=carry.point(at), basis=carry.basis(m.IDENTITY), name=name, material=material,
                           role=role, casts_shadow=False, looks=k.fig.looks))


def _open_front(f: float, slot: float = 0.0, floor: float = 1.0, fold: float = 0.45):
    """A coat's outline, fifteen corners: the octagon whose flat share is `f`, with a corner in the middle of its
    back (the seam: each half of the back is a side of its own) and, in front, on each half a corner at `fold` of
    the half width (so a front is two sides, which break apart) and the opening between the two fronts: a slot
    `slot` of the half width each side of the middle, back to `floor` (a share of the half depth). With no slot
    (0, 1) the four corners of the opening are one, in the middle of the front."""
    return ((1.0, f), (f, 1.0), (fold, 1.0), (slot, 1.0), (slot, floor), (-slot, floor), (-slot, 1.0), (-fold, 1.0), (-f, 1.0),
            (-1.0, f), (-1.0, -f), (-f, -1.0), (0.0, -1.0), (f, -1.0), (1.0, -f))


_FRONT, _FLOOR, _SEAM = (0, 1, 2, 3, 6, 7, 8, 9), (4, 5), 12       # _open_front's corners: the fronts', the opening's floor, the seam's
# how far each corner of a coat's rings is moved off its ring's height, as shares of the coat's `stagger`: one up
# and the next down round the ring, by uneven amounts (and the other way on the next ring), so that no ring reads
# as a level line; the opening's four corners, which are one where it is closed, move as one. In the middle of
# the front they move little: a corner moved off a ring where the coat bends takes the cloth off the shape that
# lapels, a shirt's front and a tie are laid on (`Coat.loft`), and there the lapels hide the ring anyway
_ZIGZAG = (0.8, -0.6, 0.25, -0.25, -0.25, -0.25, -0.25, 0.25, -0.5, 1.0, -0.7, 0.9, -1.0, 0.6, -0.8)


@dataclass(frozen=True)
class Coat:
    """A jacket's body as it is worn (`_coat`). `loft` is its shape in the rest pose: what lies on it is placed on
    that (lapels, a shirt's front, a tie, a button, flaps). `rings` are its corners where the pose puts them, in
    the chest's space (a seam runs along them). `waist`, `pocket` and `hem` are the heights of three of its rings;
    `fronts` carry what lies on its skirt in front, on the side x < 0 (-1) and on the other (1): with the hips,
    and laid forward with the skirt when that thigh is raised."""
    loft: Loft
    rings: tuple
    waist: float
    pocket: float
    hem: float
    fronts: dict


class _Raised:
    """A carry, and what it carries that much higher."""

    def __init__(self, carry, up: float):
        self.carry, self.up = carry, up

    def point(self, p) -> Vec3:
        return self.carry.point((p[0], p[1] + self.up, p[2]))

    def basis(self, b):
        return self.carry.basis(b)


def _coat(k: Parts, material: str, out: float = 0.001, hang: float = 0.01, flare: float = 0.014, waist: float = 0.9,
          shoulder: float = 0.85, vent: float = 0.3, cut: float = 0.03, above: float = 0.03, under: float = 0.009,
          flat: float = 0.72, crease: float = 7.0, facet: float = 100.0, stagger: float = 0.014, slope: float = 0.012) -> Coat:
    """A jacket's body, or a coat's: one shell of cloth over the trunk and the hips, from the collar to a hem
    `above` where the legs part. It is measured on the build. From the waist up it lies on the trunk (`out` off
    it: a build's trunk is measured with its clothes on), and the trunk under it is drawn `under` slimmer, so no
    dent of the cloth lets it through. Its skirt hangs straight from the waist to the hem, off the hips: at the
    hem `hang` in front of them and behind and `flare` to their sides, or more where the hips above the hem need
    it (it flares over the seat). The waist is taken in (`waist`: 1 lies on the
    trunk's own waist, 0 hangs straight from the chest to the hem). Its shoulders stand out to the arm
    (`shoulder`: how much of the sleeve's half width past the shoulder's joint) and come down to it (`slope`: how
    far the shoulder's point is under the shoulder's line, metres).
    It has six rings and no more, for each is a line that shows: the hem, the pockets' line, the waist, the chest
    (where the trunk stands furthest out between the waist and the shoulders), the shoulders, the neck. Their
    corners are moved off the ring's height, each its own way (`stagger`, metres, along the coat's own edges), and
    its sides break into few large facets (`facet`, `crease`): no level line runs round it.
    The chest carries it from the waist up and the hips carry its skirt (the two lowest rings); the cloth between
    runs from one to the other, so there is no seam between two parts and none opens when the trunk leans.
    The skirt is open in front below the pockets' line, as the two fronts part under the button: `vent` is half
    the opening at the hem, a share of the half width (0: closed), and `cut` how much of the fronts' corners is cut
    away there. A thigh that is raised takes the front of the skirt on its side with it (seated, the fronts lie on
    the lap), and one that goes back takes the back. Gives the Coat: its loft, for what lies on it."""
    trunk, pelvis, rest = k.b.trunk, k.b.pelvis, k.fig._rest()

    def on(part, y, more=0.0):      # (half width, front, back) of a part of the body at a height, and `more` off it
        rx, rz, zc, _flat = part.at(y)
        return [rx + more, zc + rz + more, zc - rz - more]

    yn = trunk.s[-1][0]
    # the shoulders: the highest place where the trunk is still nearly as wide as it gets (square shoulders are high)
    neck = yn - 0.01
    top = min(max(s[0] for s in trunk.s if s[1] >= 0.9 * max(x[1] for x in trunk.s)), neck - 0.02)
    seat = max(pelvis.s, key=lambda s: s[1])[0]                   # the height at which the hips are widest
    hem = pelvis.s[0][0] + above
    pocket = hem + 0.36 * (top - hem)                             # the pockets' line: a share of the coat's length
    # the waist: where the trunk is narrowest, over the pockets' line
    middle = max(min((s for s in trunk.s if s[0] < top - 0.06), key=lambda s: s[1])[0], pocket + 0.035)
    # the chest: the one place where the trunk stands furthest out of the straight line from the waist to the shoulders
    bulge = lambda s: sum(max(0.0, sign * (a - (p + (q - p) * (s[0] - middle) / (top - middle))))      # noqa: E731
                          for a, p, q, sign in zip(on(trunk, s[0]), on(trunk, middle), on(trunk, top), (1.0, 1.0, -1.0)))
    chest = max((s for s in trunk.s if middle + 0.03 < s[0] < top - 0.03), key=bulge, default=((middle + top) / 2,))[0]
    size = {y: on(trunk, y, out) for y in (middle, chest, top, neck)}
    hips = on(pelvis, seat)
    size[hem] = [hips[0] + flare, hips[1] + hang, hips[2] - hang]
    sleeve = next((k.limbs[name][1].at(0.0)[0] for name in ("sleeve_l/upper", "sleeve_l/sleeve") if name in k.limbs), 0.0)
    arm = abs(rest["left_upper_arm"].position.x) + shoulder * sleeve          # the shoulder's joint, and that much of the sleeve
    size[top][0] = max(size[top][0], arm)
    line = lambda a, b, y: [p + (q - p) * (y - a) / (b - a) for p, q in zip(size[a], size[b])]      # noqa: E731
    # the waist: taken in from the straight line between the hem and the chest toward the trunk's own
    size[middle] = [tight + (1.0 - waist) * (straight - tight) if sign * (straight - tight) > 0 else tight
                    for tight, straight, sign in zip(size[middle], line(hem, chest, middle), (1.0, 1.0, -1.0))]
    # Between two rings the cloth runs straight. From the waist up it is nowhere so far inside the trunk's own
    # surface that a dent would reach the trunk as it is drawn under it: the nearer ring is let out for that
    upper = sorted(size)[1:]
    for _ in range(4):
        for s in trunk.s:
            if upper[0] < s[0] < upper[-1] and s[0] not in size:
                a, b = max(q for q in upper if q <= s[0]), min(q for q in upper if q >= s[0])
                t = (s[0] - a) / (b - a)
                near, share = (a, 1.0 - t) if t < 0.5 else (b, t)
                for i, (want, have, sign) in enumerate(zip(on(trunk, s[0], 0.007 - under), line(a, b, s[0]), (1.0, 1.0, -1.0))):
                    if sign * (want - have) > 0:
                        size[near][i] += (want - have) / share
    # and the skirt hangs straight from the waist to the hem: the hem is let out (by up to 15 mm) until that line
    # is clear of the hips all the way down, by half of `hang`: it flares over the seat. Hips that swell too soon
    # under the waist for that let the pockets' line out as well
    under_waist = [(s[0], on(part, s[0], more)) for part, more in ((pelvis, 0.5 * hang), (trunk, 0.007 - under))
                   for s in part.s if hem < s[0] < middle]
    for i, sign in enumerate((1.0, 1.0, -1.0)):
        most = size[hem][i] + sign * 0.015
        for y, want in under_waist:
            t = (middle - y) / (middle - hem)
            least = (want[i] - size[middle][i] * (1.0 - t)) / t
            if sign * (least - size[hem][i]) > 0:
                size[hem][i] = least if sign * (most - least) > 0 else most
    size[pocket] = line(hem, middle, pocket)
    for i, sign in enumerate((1.0, 1.0, -1.0)):
        for y, want in under_waist:
            a, b = (hem, pocket) if y <= pocket else (pocket, middle)
            t = (y - a) / (b - a)
            short = sign * (want[i] - (size[a][i] + (size[b][i] - size[a][i]) * t))
            if short > 0:
                size[pocket][i] += sign * short / max(0.3, t if a == hem else 1.0 - t)
    heights = sorted(size)
    # the coat takes the trunk's place: what is drawn of the trunk under it is that much slimmer
    for n, part in enumerate(k.made):
        if part.name == "body/body":
            slim = Loft([(s[0], max(0.004, s[1] - under), max(0.004, s[2] - under), s[3], own or s[4]) for s, own in zip(trunk.s, trunk.o)],
                        trunk.flat, trunk.crease, trunk.facet, stagger=trunk.stagger)
            k.made[n] = slim.limb(part.name, k.chest, part.material, k.fig.looks)
    folds = dict(zip(heights, (vent + 0.16, 0.36, 0.3, 0.42, 0.5, 0.5)))
    loft = Loft([(y, w, (front - back) / 2, (front + back) / 2,
                  _open_front(flat, vent if y == hem else 0.0, -0.2 if y == hem and vent else 1.0, folds[y]))
                 for y, (w, front, back) in sorted(size.items())], crease=crease, facet=facet)
    sides = loft.sides

    def covered(drop):              # with its point that far down, the shoulder's line still passes over the trunk's own shoulder
        x0, y0 = loft.at(top - drop)[0], top - drop
        x1, y1 = size[neck][0], neck
        return all(y0 + (x0 - s[1]) / (x0 - x1) * (y1 - y0) >= s[0] - 0.002 for s in trunk.s if top <= s[0] < neck and s[1] > x1)

    drop = next((d for d in (slope, 0.75 * slope, 0.5 * slope, 0.25 * slope) if covered(d)), 0.0)

    def lifted(j, i):               # how far corner i of ring j is off its ring's height
        if j == 0:                  # the hem is level, but for the fronts' corners, which are cut away
            return cut if vent and i in (3, 4, 5, 6) else 0.0
        if j >= len(heights) - 2:   # the shoulders and the neck, each an edge of its own: a shoulder slopes down to its point
            return 0.0 if j > len(heights) - 2 else -drop * {0: 1.0, 9: 1.0, 10: 1.0, 14: 1.0, 1: 0.5, 8: 0.5, 11: 0.5, 13: 0.5}.get(i, 0.0)
        # (by no more than three tenths of the way to the nearer ring: two rings never cross)
        reach = min(stagger, 0.3 * min(heights[j] - heights[j - 1], heights[j + 1] - heights[j]))
        return reach * _ZIGZAG[i] * (-1.0 if j % 2 else 1.0)

    def corner(j, i):               # the corner, moved along the coat's own edge through it
        y = heights[j] + lifted(j, i)
        x, z = loft.ring(y)[i]
        return (x, y, z)

    drawn = [[corner(j, i) for i in range(sides)] for j in range(len(heights))]
    # the skirt as the legs have it: a thigh's angle from hanging, to the front and to the back (in the hips' own
    # space; the few degrees of a stance are not a raised thigh). Its fronts turn about the top of a level thigh,
    # or about the pockets' line if that is lower (they are then lifted onto the thigh as well)
    hip = rest["left_upper_leg"].position.y - k.hips.lift                 # the hip's joint, at the height the hips are drawn at
    lap = hip + max(s[2] + s[3] for s in k.b.thigh) * k.b.leg + 0.006
    turns, lap = min(pocket, lap), max(0.0, lap - pocket)

    def raised(side):
        a, b = (_into(k.hips, k.frames[f"{side}_{bone}"].position) for bone in ("upper_leg", "lower_leg"))
        deg = math.degrees(math.atan2(b[2] - a[2], a[1] - b[1]))
        return (a[0], math.radians(max(0.0, min(90.0, (deg - 8.0) * 90.0 / 82.0))), math.radians(max(0.0, min(60.0, -deg - 12.0))))

    legs = sorted(raised(side) for side in ("left", "right"))                    # the leg on the side x < 0, then the other
    swing = lambda x: legs[0] if x < -1e-6 else legs[1] if x > 1e-6 else tuple((a + b) / 2 for a, b in zip(*legs))  # noqa: E731

    def laid(j, i, p):              # a corner of the skirt, where the thighs put it
        _x, fore, aft = swing(p[0])
        low = max(0.0, turns - p[1])                                              # how far it hangs under where the skirt turns
        if i in _FRONT:
            return (p[0], p[1] + low * (1.0 - math.cos(fore)) + lap * math.sin(fore), p[2] + low * math.sin(fore))
        if i in _FLOOR or j:
            return p
        return (p[0], p[1] + low * (1.0 - math.cos(aft)), p[2] - low * math.sin(aft))

    posed = [[_into(k.chest, k.hips.point(laid(j, i, p))) if j < 2 else p for i, p in enumerate(ring)] for j, ring in enumerate(drawn)]
    # closed on a point at each end: under the hem behind the opening's floor (every side of the hem is seen from
    # there, so its underside is a fan with no fold), and in the neck
    floor = min(z for _x, z in loft.ring(hem)[4:6]) if vent else loft.at(hem)[2]
    under = (0.0, hem - 2e-5, (floor + loft.back(0.0, hem)) / 2)
    ends = (_into(k.chest, k.hips.point(under)), (0.0, neck + 2e-5, loft.at(neck)[2]))
    _skin(k, k.chest, "jacket/coat", posed, material, crease, facet, measured=drawn, ends=ends)
    fronts = {}
    for sx in (-1, 1):              # what lies on a front of the skirt turns with it about the pockets' line
        _x, fore, _aft = swing(sx)
        i = 1 if sx > 0 else 8      # (that front's outer corner: from the pockets' line to the hem, as it hangs and as it is laid)
        (_xa, ya, za), (_xb, yb, zb) = drawn[1][i], drawn[0][i]
        (_xc, yc, zc), (_xd, yd, zd) = laid(1, i, drawn[1][i]), laid(0, i, drawn[0][i])
        turn = math.degrees(math.atan2(zd - zc, yc - yd) - math.atan2(zb - za, ya - yb))
        fronts[sx] = Worn(_Raised(k.hips, lap * math.sin(fore)), rotation(0, turn, 0), (0.0, ya, za))
    return Coat(loft, tuple(tuple(ring) for ring in posed), middle, pocket, hem, fronts)


def _seam(k: Parts, coat: Coat, material: str, half: float = 0.0015, proud: float = 0.0015) -> None:
    """The seam down the middle of a coat's back: a line of `material` along the coat's own edge there, from the
    hem to the neck, so it is one line that lies on the cloth wherever the cloth goes."""
    _skin(k, k.chest, "jacket/seam", [[(x + half, y, z + 0.004), (x - half, y, z + 0.004), (x - half, y, z - proud), (x + half, y, z - proud)]
                                      for x, y, z in (ring[_SEAM] for ring in coat.rings)], material)


def _lapels(k: Parts, material: str, to: float = 0.25, notch: float = 0.62, wide: float = 0.86, proud: float = 0.008,
            over: int = -1, on: Loft | None = None) -> None:
    """A jacket's lapels, with the ends of its collar: on each side of the chest a panel with thickness from the
    side of the neck down to a point at the button (`to`, a share of the way from the belt to the neck). Its
    inner edge is the side of the opening the shirt shows in, one straight line from the neck to the button; its
    outer edge runs out to the lapel's point (`notch` of the way up from the button to the neck, `wide` of the
    chest's flat front from the middle), comes in along the lapel's top edge to the notch, steps out again as
    the end of the collar and runs up to the side of the neck, where the collar that stands round the neck takes
    over. The lapel on the side `over` (-1: the wearer's left, as a man's jacket closes; 1: the right) crosses
    over the other at the button. They lie on `on` (a jacket's body, `Coat.loft`; the trunk if none is given)."""
    on = on or k.b.trunk
    yn, rxn = k.b.trunk.s[-1][:2]
    y0, y1 = _up(k, to), min(yn - 0.014, on.s[-1][0] - 0.002)
    tip = y0 + notch * (yn - y0)
    reach = wide * _across(k, tip, on)
    edge = lambda y: (rxn - 0.004) * (y - y0) / (yn - y0)          # noqa: E731  the opening's half width at a height
    for sx in (-1, 1):
        upper = sx == over
        cross = -over * (0.006 if upper else 0.004)                 # both end past the middle, on the under one's side
        _panel(k, k.chest, "jacket/lapel", on,
               [(y0 - 0.01, cross, cross), (tip, sx * edge(tip), sx * reach),
                (tip + 0.014, sx * edge(tip + 0.014), sx * (reach - 0.03)),
                (tip + 0.017, sx * edge(tip + 0.017), sx * (reach - 0.008)), (y1, sx * (rxn + 0.002), sx * (rxn + 0.016))],
               material, proud=proud if upper else proud - 0.002)


def _shirt_bib(k: Parts, material: str, to: float = 0.25, proud: float = 0.002, on: Loft | None = None) -> None:
    """The shirt that shows between a jacket's lapels: a triangle on the chest, as wide as the neck under the
    collar, down to its point at `to` (a share of the way from the belt to the neck). It lies on `on` (a jacket's
    body, `Coat.loft`; the trunk if none is given)."""
    on = on or k.b.trunk
    yn, rxn = k.b.trunk.s[-1][:2]
    _panel(k, k.chest, "shirt/front", on, [(_up(k, to), 0.0, 0.0), (min(yn - 0.008, on.s[-1][0] - 0.001), -rxn, rxn)], material,
           proud=proud)


def _tie(k: Parts, material: str, to: float = 0.3, half: float = 0.021, proud: float = 0.004, point: float = 0.05,
         on: Loft | None = None) -> None:
    """A tie, worn with any shirt collar: its knot at the throat, under the collar's band and between its points,
    a small trapezoid that is wider at its top; and its blade down the shirt's front, widening from the knot to
    `half` and ending in a point at `to` (a share of the way from the belt to the neck), `point` long: under a
    jacket it is given a point lower than where the jacket closes, and goes behind the lapels and the button. It
    lies on the shirt (on `on`: a jacket's body, `Coat.loft`; the trunk if none is given) and stands off it."""
    on = on or k.b.trunk
    yn = k.b.trunk.s[-1][0]
    knot = yn - 0.03
    at, turn = on.seat(0.0, knot, 0.002)
    _piece(k, k.chest, "tie/knot", [(-0.013, 0.55 * half, 0.0045), (0.013, 0.9 * half, 0.0045)], material, at, turn)
    y0 = _up(k, to)
    _panel(k, k.chest, "tie/blade", on, [(y0, 0.0, 0.0), (y0 + point, -half, half), (knot - 0.008, -0.55 * half, 0.55 * half)],
           material, proud=proud, deep=0.004)


def _shirt_cuffs(k: Parts, material: str, show: float = 0.09, slim: float = 0.004) -> None:
    """A shirt's cuffs under a jacket's sleeves: one plain band that comes out of each long sleeve at the wrist,
    `show` of the forearm's length past the sleeve's end, `slim` slimmer than the sleeve is there."""
    for side in ("l", "r"):
        on, sleeve = k.limbs[f"sleeve_{side}/fore"]
        y, wide, deep, forward = sleeve.s[-1][:4]
        k.loft(on, f"cuff_{side}/cuff", Loft([(y - 0.012, wide - slim, deep - slim, forward),
                                             (y + show * on.length, wide - slim, deep - slim, forward)], profile=sleeve.profile), material)


def _sleeve_buttons(k: Parts, material: str, count: int = 3, size: float = 0.0062) -> None:
    """The buttons on a jacket's sleeves: a row up from the cuff, on the back of each long sleeve toward its
    outer side."""
    for side, turn in (("l", 1.0), ("r", -1.0)):
        on, loft = k.limbs[f"sleeve_{side}/fore"]
        for i in range(count):
            k.hung(on, f"sleeve_{side}/button", loft, turn * 150.0, (0.9 - 0.105 * i) * on.length, (size, size, 0.6 * size),
                   material, out=0.0015, soft=0.55, samples=(8, 6))


def _turn_ups(k: Parts, material: str, tall: float = 0.1) -> None:
    """Trousers with turn-ups: a band of their cloth round each leg at the hem, `tall` of the shin's length."""
    for side in ("l", "r"):
        k.cuff(f"leg_{side}/turn-up", f"leg_{side}/shin", 0.935 - tall, 0.935, material, out=0.005)


def _closes(k: Parts, coat: Coat) -> float:
    """Where a jacket closes, as the share of the way from the belt to the neck that lapels, a shirt's front and
    a tie are given: a little over its waist, with its button just under."""
    return (coat.waist + 0.02 - BELT_Y) / (k.b.trunk.s[-1][0] - BELT_Y)


def _jacket(k: Parts, material: str, trim: str, buttons: str) -> Coat:
    """A single-breasted jacket (the long sleeves are its cloth): a coat over the trunk and the hips, taken in at
    the waist, with one round button a little over it, and open in front below the pockets; lapels down to the
    button; a collar that stands round the back of the neck, low and close, and stops at its sides; a flat flap
    pocket on each hip; a seam down the middle of the back, in `trim`; buttons on the sleeves. Gives its Coat: a
    shirt's front and a tie lie on its loft, and close where it does (`_closes`)."""
    coat = _coat(k, material)
    closes = _closes(k, coat)
    _lapels(k, material, to=closes, on=coat.loft)
    # (its collar: a closed shirt collar's band, `_suit`'s, stands inside it and shows over it)
    _stand(k, material, low=0.036, tilt=20.0, name="jacket/collar", out=0.002, front=0.75)
    # the button, under the point where the lapels cross
    _button(k, k.chest, "jacket/button", coat.loft, 0.0, _up(k, closes) - 0.022, buttons, 0.0105, 0.003, shape="round")
    y = coat.pocket - 0.006                                    # the pockets' flaps, on the skirt's flat front
    reach = _across(k, y - 0.015, coat.loft)
    half = 0.4 * reach
    for sx in (-1, 1):
        _flap(k, coat.fronts[sx], coat.loft, sx * (reach - half - 0.004), y, half, material, tall=0.028, point=0.0,
              name="jacket/flap", thick=0.0035, sink=-0.0005)
    _seam(k, coat, trim)
    _sleeve_buttons(k, buttons)
    return coat


def _suit(k: Parts) -> None:
    """A suit, bare-headed: a jacket; a shirt whose collar is closed over a tie, its two wings framing the knot;
    cuffs at the wrists; trousers, with turn-ups if the person has them (`turn_ups`); in the person's `top` (with
    `trim` and `buttons`), `shirt`, `tie` and `bottom`."""
    p = k.p
    coat = _jacket(k, p.top, p.trim, p.buttons)
    closes = _closes(k, coat)
    _open_collar(k, tilt=20.0, drop=0.05, under=p.shirt, material=p.shirt, spread=-0.018, high=0.004, wide=0.017, thick=0.0015,
                 on=coat.loft, top=0.017, rise=-0.016, lift=0.003)
    _shirt_bib(k, p.shirt, to=closes, on=coat.loft)
    _tie(k, p.tie, to=closes - 0.03, on=coat.loft)
    _shirt_cuffs(k, p.shirt)
    if p.turn_ups:
        _turn_ups(k, p.bottom, p.turn_ups)


OUTFITS: dict[str, Callable[[Parts], None]] = {"officer": _officer, "cook": _cook, "firefighter": _firefighter, "suit": _suit}


def _whole(fig: m.MascotFigure, frames) -> list:
    """Every part of one person, from its skeleton as it is posed: the shared body, then what it wears."""
    k = Parts(fig, frames, PEOPLE[fig.who])
    _body(k)
    OUTFITS[k.p.outfit](k)
    made = k.made if k.b.head == 1.0 else [_sized(part) for part in k.made]
    return made + fig._take_extra()        # the face's strokes (brows, the mouth's line) are drawn through the figure


def _sized(part: Limb) -> Limb:
    """A part that a Sized carry made larger or smaller has its size in its basis. Every finish takes that but
    the paper one, whose engine turns a part and does not size it: so the size goes into the part's own formulas
    (and what it tells the low-poly finish of its sides), and its basis is left a pure turn."""
    size = math.sqrt(sum(part.basis[i][0] ** 2 for i in range(3)))
    if abs(size - 1.0) < 1e-9:
        return part
    role = " ".join(_facets(tag, size) for tag in part.role.split())
    return _replace(part, basis=tuple(tuple(x / size for x in row) for row in part.basis), role=role,
                    radii=tuple(r * size for r in part.radii), **{axis: f"{size:.6f}*({getattr(part, axis)})" for axis in "xyz"})


def _facets(tag: str, size: float) -> str:
    """A Loft's "facet:<across>:<deep>:<sides>:<bands>" for the same part `size` times as large: its sides and its
    bands are that much wider (the facets it asks for stay as large and as deep)."""
    field = tag.split(":")
    if field[0] != "facet" or len(field) < 5:
        return tag
    wider = lambda text: ",".join(str(round(float(x) * size)) for x in text.split(","))       # noqa: E731
    return ":".join([*field[:3], wider(field[3]), wider(field[4]), *field[5:]])


def enlist(person: Person) -> Person:
    """Puts a person in the cast, as the kit's own are: in PEOPLE, and with the family's skeleton (its Spec: the
    build's proportions, what its gestures aim at, its hands, its stance), its name, its look, its poses and the
    function that draws it. Its build is read from BODIES now, so a build made at run time is registered there
    first. Enlisting a key again replaces what was there."""
    b = BODIES[person.body]
    PEOPLE[person.key] = person
    m.SPECS[person.key] = m.Spec(person.key, b.build, (*b.torso, person.top), face="head", head=(*b.reach_head, person.skin),
                                 limb=person.skin, reach=0.22, rest_hands=b.rest_hands, gesture_scale=1.5,
                                 hand_length=HAND_REACH * b.hand,
                                 stance={"head.tilt_left_right": person.tilt, **(STANCE if b.stance is None else b.stance)},
                                 sit_drop=b.sit_drop)
    m.NAMES[person.key] = person.name
    m.LOOKS[person.key] = plush3d.look
    POSES.setdefault(person.key, {**CANON, **PLUSH_SEATED})
    m.WHOLE[person.key] = _whole
    # what was solved for another person of this key (its rest pose, its poses, its gestures) is no longer its own
    m._REST.pop(person.key, None)
    for kept in (m._SOLVED, m._GESTURES):
        for key in [key for key in kept if key[0] == person.key]:
            del kept[key]
    return person


for _p in list(PEOPLE.values()):
    enlist(_p)


def proof(out: Path | None = None, who: str = "sergeant") -> Path:
    """`who` from the front, in profile and from the back, as a reference sheet shows a character."""
    from . import film
    out = out or Path(__file__).resolve().parent / "examples" / "out" / f"lowpoly-{who}.png"
    tiles = []
    for view, yaw in (("front", 0), ("profile", 90), ("back", 180)):
        f = film.Film(f"lowpoly-{view}", size=(720, 1080))
        f.add(who, "idle", at=(0, 0, 0), yaw=yaw)
        f.camera((0.0, 0.58, 6.0), look_at=(0, 0.56, 0), lens=118)
        tiles.append(f.still(out.with_name(f"{out.stem}-{view}.png"), finish="lowpoly"))
    import subprocess
    subprocess.run(["ffmpeg", "-v", "error", "-y", *(a for t in tiles for a in ("-i", str(t))), "-filter_complex",
                    f"hstack=inputs={len(tiles)}", str(out)], check=True)
    return out


if __name__ == "__main__":
    if sys.argv[1:2] == ["proof"]:
        args = sys.argv[2:]
        who = args.pop(0) if args and args[0] in PEOPLE else "sergeant"
        print("wrote", proof(Path(args[0]) if args else None, who))
    else:
        print(__doc__)
