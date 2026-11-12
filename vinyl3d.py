"""Vinyl people: collectible-toy humans, a second family beside the plush animals (the operator, 2026-11-11: "go",
after asking whether the SDK could also build vinyl figures like a toy police officer).

A vinyl person stands on the family's skeleton (so every pose, action, gaze, lip-sync and `characters.film` call
works) but draws all of itself, as the robot kit does (`mascots3d.WHOLE`): a body with real arms and legs, a big
head, hair, ears, and an OUTFIT: what it wears and carries. The officer is the pilot; another profession is another
`Person` with its own outfit and colours, not another model.

    PY=/home/dev/src/viral-video-orchestrator/.venvs/srlocations/bin/python
    $PY characters/vinyl3d.py proof           # examples/out/vinyl-officer.png (paper) and vinyl-officer-vinyl.png

Nothing squashes or stretches: it is moulded vinyl. Render it with `finish="vinyl"` (characters.blender) for the
toy look; the paper look draws it too.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from dataclasses import replace as _replace
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "characters"

from srlocations.geometry import Vec3, rotation  # noqa: E402
from srlocations.stock.mannequin import Build, Limb  # noqa: E402

from . import mascots3d as m  # noqa: E402
from . import plush3d  # noqa: E402
from .kit import basis, cross, scaled, shape, tube, unit  # noqa: E402
from .poses import CANON, PLUSH_SEATED, POSES  # noqa: E402

COLOURS = {
    "vinyl.skin": "#F0B98D", "vinyl.hair": "#4A3226", "vinyl.shoe": "#1E1E22",
    "officer.navy": "#2B3157", "officer.black": "#24242A", "officer.gold": "#F2B632", "officer.buckle": "#8E929A",
    "officer.button": "#232848",
}
m.COLOURS.update(COLOURS)

# A big wide head on a stocky body with short thick legs and real arms, as a collectible toy. Rest-pose joints (m):
# hips 0.214, chest 0.319, neck 0.481, head 0.546, shoulders 0.439 (x 0.131), elbows 0.319, wrists 0.225, hip joints
# 0.197 (x 0.05), knees 0.115, ankles 0.032.
BUILD = Build(height=0.74, head=2.6, torso=1.0, legs=0.4, arms=0.78, shoulders=1.2, hips=1.2)
TORSO = ((0.0, 0.355, 0.0), (0.13, 0.114, 0.096))
HEAD = ((0.0, 0.66, 0.012), (0.2, 0.17, 0.178))
SIT_DROP = 0.0435                    # how far a seated figure comes down onto its seat (measured: see proof)
SOFT, PILL = 0.62, 0.2              # exponents (robots3d.shape): a soft-cornered block; a cylinder's flat end


@dataclass(frozen=True)
class Person:
    key: str
    name: str
    outfit: str = "officer"        # what it wears: OUTFITS
    skin: str = "vinyl.skin"
    hair: str = "vinyl.hair"
    cloth: str = "officer.navy"    # shirt and trousers
    dark: str = "officer.black"    # belt, cap band and peak, what hangs on the belt
    shiny: str = "officer.gold"    # badges
    tilt: float = 4.0              # how far its head rests to one side (degrees)


PEOPLE = {
    "officer": Person("officer", "Officer"),
}

for _p in PEOPLE.values():
    m.SPECS[_p.key] = m.Spec(_p.key, BUILD, (*TORSO, _p.cloth), face="head", head=(*HEAD, _p.skin), limb=_p.skin,
                             reach=0.16, stance={"head.tilt_left_right": _p.tilt}, sit_drop=SIT_DROP)
    m.NAMES[_p.key] = _p.name
    m.LOOKS[_p.key] = plush3d.look
    POSES.setdefault(_p.key, {**CANON, **PLUSH_SEATED})


EYE_X, EYE_Y, EYE_W, EYE_H = 0.37, -0.14, 0.125, 0.2     # where a painted eye is on the face, and its size (shares)


def _eyes(fig, e, on, limb, skin: str) -> None:
    """A toy's painted eyes: a tall black oval with one small light in it. It looks where the pose looks, widens,
    narrows under a lid of skin (half shut, a blink on its way), and is a curved line when shut."""
    lx = max(-1.0, min(1.0, e.look[0] + fig.look_x))
    ly = max(-1.0, min(1.0, e.look[1] + fig.look_y))
    size = {"wide": 1.14, "squint": 0.82}.get(e.eyes, 1.0) * fig.eye_scale
    smiling = e.mouth in ("smile", "smug", "flat")
    for sx in (-1, 1):
        fx, fy = sx * EYE_X + 0.05 * lx, EYE_Y - 0.04 * ly
        shut = min(1.0, fig.lid + (fig.lid_right if sx > 0 else fig.lid_left))
        if e.eyes == "half":
            shut = max(shut, 0.5)
        if e.eyes == "closed" or shut >= 0.9:
            up = 1.0 if smiling else -0.6
            fig._stroke("eye/closed", [on(fx + (i - 4) / 4 * EYE_W * 1.1, fy + up * 0.05 * (1 - ((i - 4) / 4) ** 2), 0.01)
                                       for i in range(9)], 0.008)
            continue
        if e.eyes == "spiral":
            m.spiral(on, fig._stroke, fx, fy, 0.13, 0.004)
            continue
        w, h = EYE_W * size, EYE_H * size
        limb("eye", on(fx, fy, -0.03), (w * fig.spec.head[1][0], h * fig.spec.head[1][1], 0.05 * fig.spec.head[1][2]), "plush.eye",
             samples=(18, 12))
        if shut < 0.35:
            limb("eye-shine", on(fx - 0.3 * w + 0.1 * w * lx, fy + 0.42 * h, 0.012),
                 (0.26 * w * fig.spec.head[1][0], 0.2 * h * fig.spec.head[1][1], 0.012 * fig.spec.head[1][2]), "m.white", samples=(10, 8))
        if shut > 0.25:      # a lid of skin comes down over it
            cut = 1.0 - 2.0 * shut
            tall = max(0.45, (1.1 - cut) / 2)
            limb("head/lid", on(fx, fy + cut * h + tall * h, 0.0),
                 (1.35 * w * fig.spec.head[1][0], tall * h * fig.spec.head[1][1], 0.075 * fig.spec.head[1][2]), skin, samples=(16, 10))


def _whole(fig: m.MascotFigure, frames) -> list:
    """Every part of one vinyl person, from its skeleton as it is posed."""
    p, e = PEOPLE[fig.who], fig.expression
    rest, looks = fig._rest(), fig.looks
    parts: list = []

    def solid(name, at, radii, material, basis=m.IDENTITY, ring=1.0, cap=1.0, samples=(26, 16)):
        radii = tuple(float(x) for x in radii)
        parts.append(Limb(**shape(radii, ring, cap), radii=radii, at=Vec3(*at), basis=basis, name=name,
                          material=material, samples=samples, casts_shadow=False, looks=looks))

    def put(carry, name, c, radii, material, basis=m.IDENTITY, samples=(22, 14), ring=1.0, cap=1.0):
        solid(name, carry.point(c), radii, material, carry.basis(basis), ring, cap, samples)

    def block(carry, name, c, radii, material, soft=SOFT, basis=m.IDENTITY, samples=(34, 22)):
        put(carry, name, c, radii, material, basis, samples, soft, soft)

    def rod(name, a, b, r0, r1, material, **kw):
        parts.append(tube(name, a, b, r0, r1, material, looks=looks, **kw))

    hips = m.Carry(frames["hips"], rest["hips"])
    chest = m.Carry(frames["chest"], rest["chest"])
    head = m.Carry(frames["head"], rest["head"])
    (tx, ty, tz), (trx, try_, trz) = TORSO
    (hx, hy, hz), (hrx, hry, hrz) = HEAD
    n_t = 2.0 / SOFT

    def on_chest(dx, dy, lift=0.0):  # metres from the middle of the chest's front, and out of it
        z = max(0.0, 1 - abs(dx / trx) ** n_t - abs(dy / try_) ** n_t) ** (1 / n_t)
        return (tx + dx, ty + dy, tz + trz * z + lift)

    # -- legs first (the trunk sits over their tops): trousers to the ankle, a big rounded shoe
    for side in ("left", "right"):
        hip, knee, ankle, toes = (frames[f"{side}_{b}"].position for b in ("upper_leg", "lower_leg", "foot", "toes"))
        g = f"leg_{side[0]}"
        rod(f"{g}/thigh", hip, knee, 0.064, 0.063, p.cloth)
        rod(f"{g}/shin", knee, ankle + Vec3(0, 0.02, 0), 0.063, 0.067, p.cloth)
        ahead = toes - ankle
        ahead = unit(ahead) if ahead.length > 1e-4 else Vec3(0, 0, 1)
        if abs(ahead.y) < 0.6 and ankle.y < 0.07:        # standing on it: the shoe lies flat on the ground
            ahead = unit(Vec3(ahead.x, 0.0, ahead.z))
            centre = Vec3(ankle.x, 0.04, ankle.z) + scaled(ahead, 0.04)
            up = Vec3(0, 1, 0)
        else:                                            # lifted, or seated: it follows the foot
            up = unit(knee - ankle)
            up = unit(up - scaled(ahead, up.x * ahead.x + up.y * ahead.y + up.z * ahead.z))
            centre = ankle + scaled(ahead, 0.04)
        across = cross(up, ahead)
        basis = ((across.x, up.x, ahead.x), (across.y, up.y, ahead.y), (across.z, up.z, ahead.z))
        solid(f"shoe_{side[0]}/shoe", centre, (0.068, 0.042, 0.102), "vinyl.shoe", basis, ring=0.8, cap=0.75, samples=(26, 16))

    # -- the trunk: hips in trousers, the shirt, a belt with what hangs on it
    block(hips, "hips/hips", (0.0, 0.212, 0.0), (0.12, 0.062, 0.09), p.cloth, samples=(30, 18))
    block(chest, "body/body", (tx, ty, tz), (trx, try_, trz), p.cloth)
    put(hips, "belt/belt", (0.0, 0.256, 0.0), (0.134, 0.023, 0.1), p.dark, ring=0.8, cap=PILL, samples=(34, 10))
    block(hips, "buckle/buckle", (0.0, 0.256, 0.1), (0.025, 0.021, 0.008), "officer.buckle", samples=(16, 10))
    block(hips, "buckle/inner", (0.0, 0.256, 0.108), (0.013, 0.011, 0.004), p.dark, samples=(12, 8))
    block(hips, "pouch/pouch", (0.074, 0.245, 0.088), (0.034, 0.036, 0.022), p.dark, samples=(20, 14))      # picture left
    block(hips, "radio/radio", (-0.08, 0.262, 0.088), (0.018, 0.046, 0.018), p.dark, samples=(18, 14))
    rod("radio/antenna", hips.point((-0.087, 0.305, 0.09)), hips.point((-0.087, 0.355, 0.09)), 0.0055, 0.0045, p.dark,
        samples=(8, 9))
    # the shirt: a collar, a placket of buttons, two pockets with flaps, a badge
    for sx in (-1, 1):
        put(chest, "collar/flap", on_chest(sx * 0.036, 0.1, 0.004), (0.038, 0.022, 0.013), p.cloth,
            rotation(0, 0, sx * 28), samples=(16, 10))
        block(chest, "pocket/pocket", on_chest(sx * 0.064, 0.022, 0.002), (0.034, 0.028, 0.007), p.cloth, samples=(18, 12))
        block(chest, "pocket/flap", on_chest(sx * 0.064, 0.044, 0.007), (0.036, 0.012, 0.007), p.cloth, samples=(16, 8))
        put(chest, "pocket/button", on_chest(sx * 0.064, 0.038, 0.015), (0.0055, 0.0055, 0.004), "officer.button",
            samples=(8, 6))
    for k in range(3):
        put(chest, "placket/button", on_chest(0.0, 0.062 - 0.048 * k, 0.003), (0.0085, 0.0085, 0.0055), "officer.button",
            samples=(10, 8))
    put(chest, "badge/badge", on_chest(-0.066, 0.08, 0.007), (0.021, 0.026, 0.007), p.shiny, samples=(14, 10))  # its left

    # -- arms: a short sleeve, a bare arm, a fist with a thumb
    for side in ("left", "right"):
        s, el, w = (frames[f"{side}_{b}"].position for b in ("upper_arm", "lower_arm", "hand"))
        g = f"arm_{side[0]}"
        rod(f"{g}/upper", s, el, 0.044, 0.043, p.skin)
        rod(f"{g}/fore", el, w, 0.043, 0.041, p.skin)
        rod(f"sleeve_{side[0]}/sleeve", s, s + scaled(el - s, 0.52), 0.047, 0.052, p.cloth)
        d = unit(w - el)
        wrist = fig.wrist_left if side == "left" else fig.wrist_right
        if wrist:
            th = math.radians(-wrist if side == "right" else wrist)
            d = Vec3(d.x * math.cos(th) - d.y * math.sin(th), d.x * math.sin(th) + d.y * math.cos(th), d.z)
        ref = Vec3(0, 0, 1) if abs(d.z) < 0.9 else Vec3(0, 1, 0)
        a = unit(cross(d, ref))
        n = cross(a, d)                                  # roughly forward for a hanging arm
        palm = w + scaled(d, 0.036)
        basis = ((a.x, d.x, n.x), (a.y, d.y, n.y), (a.z, d.z, n.z))
        solid(f"{g}/hand", palm, (0.052, 0.06, 0.047), p.skin, basis, ring=0.9, cap=0.85, samples=(20, 14))
        solid(f"{g}/thumb", palm + scaled(n, 0.034) - scaled(d, 0.008), (0.018, 0.028, 0.018), p.skin, basis,
              samples=(12, 10))

    # -- the head: a neck, ears, hair behind and above the face, the face, the nose
    rod("neck/neck", frames["neck"].position, frames["head"].position, 0.045, 0.045, p.skin)
    put(head, "head/head", (hx, hy, hz), (hrx, hry, hrz), p.skin, samples=(36, 24))   # an ellipsoid: the face lies on it
    for sx in (-1, 1):
        put(head, f"ear_{sx}/ear", (sx * (hrx - 0.004), hy - 0.02, hz - 0.012), (0.034, 0.046, 0.03), p.skin, samples=(14, 10))
    put(head, "hair/hair", (hx, hy + 0.014, hz - 0.05), (hrx + 0.008, hry + 0.004, hrz + 0.004), p.hair,
        samples=(34, 22))
    on, limb, R = fig._face(head, (hx, hy, hz), (hrx, hry, hrz), lambda carry, name, c, r, mat, b=m.IDENTITY, samples=(20, 14):
                            put(carry, name, c, r, mat, b, samples))
    _eyes(fig, e, on, limb, p.skin)
    browed = e if e.brows != "none" else _replace(e, brows="flat")       # a toy's painted brows are always there
    m.brows(on, fig._stroke, browed, EYE_X, 0.2, 0.15, 0.013, was=fig.brows_from or "flat", mix=fig.brow_mix,
            lift=0.3 * (fig.eye_scale - 1.0))
    put(head, "nose/nose", on(0.0, -0.34, 0.03), (0.024, 0.02, 0.024), p.skin, samples=(12, 10))
    fig._rest_mouth = "smile"
    fig._lip(on, limb, R, "smile" if e.mouth == "flat" else e.mouth, -0.6, 0.2, line=0.036)

    # -- the outfit on the head
    if p.outfit == "officer":      # a peaked cap: a wide crown tipped back, a band, a peak, a badge
        back = rotation(-9, 0, 0)
        put(head, "cap/crown", (hx, hy + 0.178, hz - 0.016), (0.262, 0.078, 0.244), p.cloth, back, samples=(38, 16),
            ring=0.95, cap=0.7)
        put(head, "cap/band", (hx, hy + 0.108, hz - 0.004), (hrx + 0.012, 0.036, hrz + 0.012), p.dark, samples=(36, 10),
            ring=0.9, cap=PILL)
        put(head, "cap/peak", (hx, hy + 0.086, hz + hrz + 0.03), (0.17, 0.013, 0.102), p.dark, rotation(13, 0, 0),
            samples=(28, 10))
        put(head, "cap/badge", (hx, hy + 0.186, hz + 0.222), (0.036, 0.044, 0.01), p.shiny, rotation(-12, 0, 0),
            samples=(14, 10))
    return parts + fig._take_extra()      # the face's strokes (brows, the mouth's line) are drawn through the figure


for _k in PEOPLE:
    m.WHOLE[_k] = _whole


def proof(out: Path | None = None) -> Path:
    """The officer in the paper look and as a vinyl toy (Blender): front three-quarter, as the reference picture."""
    from . import film
    out = out or Path(__file__).resolve().parent / "examples" / "out" / "vinyl-officer.png"
    f = film.Film("vinyl-proof", size=(1080, 1080))
    f.add("officer", "idle", at=(0, 0, 0), yaw=-18)
    f.camera((0.0, 0.6, 3.5), look_at=(0, 0.45, 0), lens=70)
    f.still(out)
    f.still(out.with_name(out.stem + "-vinyl.png"), finish="vinyl")
    return out


if __name__ == "__main__":
    if sys.argv[1:2] == ["proof"]:
        print("wrote", proof())
    else:
        print(__doc__)
