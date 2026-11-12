"""The robot kit: robots built as machines, not as plush animals with a square head (the operator, 2026-11-11,
after the first robots: "go with 1", a purpose-built kit in the same engine).

A robot here stands on the family's skeleton (so every pose, action, gaze, lip-sync and `characters.film` call
works) but draws all of itself: its own proportions (a `Build` with real legs and arms), hard-surface parts (boxes
and cylinders: `shape()`), ball joints at shoulder, elbow, hip and knee, flared forearms that telescope where a
plush arm stretches, gripper hands, boots, a flat screen in a bezel with a lit face, and nothing that squashes.

    PY=/home/dev/src/viral-video-orchestrator/.venvs/srlocations/bin/python
    $PY characters/robots3d.py proof          # examples/out/robot-kit-proof.png: the kit's Claude beside the plush one

The proof robot is registered as `claude2` in mascots3d only (not in the cast) until the operator has seen it.
"""

from __future__ import annotations

import math
import subprocess
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
from .dev3d import ROOT, _basis, _cross, _scaled, _unit, render, tube  # noqa: E402
from .poses import POSES  # noqa: E402

COLOURS = {
    "robot.joint": "#3F4450", "robot.steel": "#9099A8", "robot.gloss": "#FFFFFF", "robot.sole": "#3F4450",
    "robot.glass": "#FFFFFF",
}
m.COLOURS.update(COLOURS)

# Real legs and arms under a head that is still big (a friendly machine, not a baby): rest-pose joints (m): hips
# 0.24, chest 0.35, neck 0.52, shoulders 0.48 (x 0.15), elbows 0.37, wrists 0.28, knees 0.13, ankles 0.03.
BUILD = Build(height=0.74, head=2.3, torso=1.15, legs=0.5, arms=0.8, shoulders=1.5, hips=1.2)
TORSO = ((0.0, 0.405, 0.0), (0.132, 0.105, 0.092))
HEAD = ((0.0, 0.68, 0.01), (0.19, 0.128, 0.135))
SCREEN = (0.128, 0.086)             # the screen's half-width and half-height
FACE = (0.145, 0.17, 0.135)         # what the shared face's shares are measured in on the screen (x, y, depth)
BOX, PILL = 0.4, 0.16               # exponents: a soft-cornered box; a cylinder's flat end


def shape(radii, ring: float = 1.0, cap: float = 1.0) -> dict[str, str]:
    """A surface inside `radii`: round the y axis by `ring` and from pole to pole by `cap` (1 = an egg's curve,
    towards 0 = square). ring 1 with a small cap is a cylinder along y; both small is a box."""
    x, y, z = (f"{r:.5f}" for r in radii)
    cu, su = (f"sign({f}(u))*pow(abs({f}(u)),{ring})" for f in ("cos", "sin"))
    return {"x": f"{x}*{cu}*pow(abs(cos(v)),{cap})", "y": f"{y}*sign(sin(v))*pow(abs(sin(v)),{cap})",
            "z": f"{z}*{su}*pow(abs(cos(v)),{cap})"}


@dataclass(frozen=True)
class Robot:
    key: str
    name: str
    body: str            # the shell's colour
    accent: str          # hands, boots, pods
    led: str             # what the face is lit in
    gear: str = ""       # on its head: "sun"
    gear_colour: str = ""
    chest: str = ""      # on its chest: "bubble-lines"
    rest_mouth: str = "smile"
    tilt: float = 6.0    # how far its head rests to one side (degrees)


ROBOTS = {
    "claude2": Robot("claude2", "Claude", "claude.fur", "claude.accent", "claude.led", gear="sun",
                     gear_colour="claude.ray", chest="bubble-lines"),
}

for _r in ROBOTS.values():
    m.SPECS[_r.key] = m.Spec(_r.key, BUILD, (*TORSO, _r.body), face="head", head=(*HEAD, _r.body),
                             limb="robot.steel", reach=0.05, stance={"head.tilt_left_right": _r.tilt},
                             sit_drop=0.053)  # seated, its boots are 0.106 above the seat; the drop counts twice
    #                                          (the skeleton comes down with the figure it stands in)
    m.NAMES[_r.key] = _r.name
    m.LOOKS[_r.key] = plush3d.look


def _whole(fig: m.MascotFigure, frames) -> list:
    """Every part of one robot, from its skeleton as it is posed."""
    r, e = ROBOTS[fig.who], fig.expression
    rest, looks = fig._rest(), fig.looks
    parts: list = []

    def solid(name, at, radii, material, basis=m.IDENTITY, ring=1.0, cap=1.0, samples=(26, 16)):
        radii = tuple(float(x) for x in radii)
        parts.append(Limb(**shape(radii, ring, cap), radii=radii, at=Vec3(*at), basis=basis, name=name,
                          material=material, samples=samples, casts_shadow=False, looks=looks))

    def put(carry, name, c, radii, material, basis=m.IDENTITY, samples=(20, 14), ring=1.0, cap=1.0):
        solid(name, carry.point(c), radii, material, carry.basis(basis), ring, cap, samples)

    def box(carry, name, c, radii, material, soft=BOX, samples=(40, 26)):
        put(carry, name, c, radii, material, samples=samples, ring=soft, cap=soft)

    def rod(name, a, b, r0, r1, material, **kw):
        parts.append(tube(name, a, b, r0, r1, material, looks=looks, **kw))

    def ball(name, at, radius, material):
        solid(name, at, (radius,) * 3, material, samples=(14, 10))

    hips = m.Carry(frames["hips"], rest["hips"])
    chest = m.Carry(frames["chest"], rest["chest"])
    head = m.Carry(frames["head"], rest["head"])
    (tx, ty, tz), (trx, try_, trz) = TORSO
    (hx, hy, hz), (hrx, hry, hrz) = HEAD
    dark, steel = "robot.joint", "robot.steel"

    # -- the trunk: a pelvis block, a waist joint, the chest shell with a pack on its back, a neck
    box(hips, "pelvis/pelvis", (0.0, 0.24, 0.0), (0.084, 0.036, 0.064), r.body)
    box(hips, "belt/belt", (0.0, 0.262, 0.0), (0.074, 0.012, 0.058), dark, samples=(28, 10))
    rod("waist/waist", frames["hips"].position, frames["chest"].position, 0.046, 0.046, steel)
    box(chest, "body/body", (tx, ty, tz), (trx, try_, trz), r.body)
    box(chest, "pack/pack", (0.0, ty + 0.012, tz - trz - 0.012), (0.082, 0.07, 0.034), dark, samples=(28, 18))
    for sx in (-1, 1):  # a vent slot on each side of the pack
        box(chest, "vent/vent", (sx * 0.035, ty + 0.012, tz - trz - 0.045), (0.02, 0.045, 0.006), steel,
            samples=(16, 10))
    put(chest, "collar/collar", (0.0, ty + try_ + 0.004, 0.0), (0.07, 0.016, 0.062), steel, ring=1.0, cap=PILL,
        samples=(28, 10))
    rod("neck/neck", frames["neck"].position, frames["head"].position, 0.036, 0.036, dark)

    n_t = 2.0 / BOX

    def on_chest(dx, dy, lift=0.0):  # metres from the middle of the chest's front, and out of it
        z = max(0.0, 1 - abs(dx / trx) ** n_t - abs(dy / try_) ** n_t) ** (1 / n_t)
        return (tx + dx, ty + dy, tz + trz * z + lift)

    across = chest.vec((1, 0, 0))
    if r.chest == "bubble-lines":  # a speech bubble with two lines of text (picture left is +x)
        put(chest, "bubble/bubble", on_chest(-0.012, 0.016), (0.07, 0.048, 0.01), r.accent, samples=(24, 12))
        rod("bubble/tail", chest.point(on_chest(0.02, -0.018)), chest.point(on_chest(0.046, -0.058)), 0.015, 0.003,
            r.accent, ref=across, deep=0.4, samples=(10, 12))
        for x0, x1, y in ((-0.04, 0.04, 0.03), (-0.04, 0.016, 0.006)):
            rod("text/line", chest.point(on_chest(-0.012 - x0, y, 0.011)), chest.point(on_chest(-0.012 - x1, y, 0.011)),
                0.0062, 0.0062, r.body, samples=(8, 9))
    for i in range(3):  # three status lights low on the chest
        put(chest, f"status_{i}/light", on_chest(-0.075 + 0.026 * i, -0.066, 0.002), (0.009, 0.009, 0.006),
            r.led if i == 0 else dark, samples=(10, 8))
    rod("seam/seam", chest.point(on_chest(0.11, -0.084, 0.001)), chest.point(on_chest(0.02, -0.084, 0.001)), 0.0028,
        0.0028, dark, samples=(6, 8))
    # a painted highlight: metal that catches the light, top left as the picture sees it
    rod("gloss/gloss", chest.point(on_chest(0.098, 0.074, 0.001)), chest.point(on_chest(0.068, 0.082, 0.001)), 0.0058,
        0.0058, "robot.gloss", samples=(8, 9))

    # -- arms: a ball at the shoulder and the elbow, a thin upper arm, a flared forearm, a gripper
    for side in ("left", "right"):
        s, el, w = (frames[f"{side}_{b}"].position for b in ("upper_arm", "lower_arm", "hand"))
        longer = fig.arm_left if side == "left" else fig.arm_right
        g = f"arm_{side[0]}"
        ball(f"{g}_shoulder/ball", s, 0.037, dark)
        rod(f"{g}_upper/upper", s, el, 0.024, 0.024, steel)
        ball(f"{g}_elbow/ball", el, 0.031, dark)
        d = _unit(w - el)
        if longer != 1.0:  # where a plush arm stretches, this one telescopes: an inner rod slides out of the forearm
            reach = (w - el).length * (longer - 1.0) * 1.9
            rod(f"{g}_slide/slide", w, w + _scaled(d, reach), 0.02, 0.02, steel)
            sleeve_end, w = w, w + _scaled(d, reach)
        else:
            sleeve_end = w
        rod(f"{g}_fore/fore", el, sleeve_end, 0.03, 0.043, r.body)
        wrist = fig.wrist_left if side == "left" else fig.wrist_right
        if wrist:  # the gripper turns at the wrist, about the figure's front-to-back axis
            th = math.radians(-wrist if side == "right" else wrist)
            d = Vec3(d.x * math.cos(th) - d.y * math.sin(th), d.x * math.sin(th) + d.y * math.cos(th), d.z)
        ref = Vec3(0, 0, 1) if abs(d.z) < 0.9 else Vec3(0, 1, 0)
        a = _unit(_cross(d, ref))                       # the way the two fingers part
        solid(f"{g}_cuff/cuff", w, (0.034, 0.034, 0.034), dark, samples=(14, 10))
        palm = w + _scaled(d, 0.034)
        solid(f"{g}_hand/palm", palm, (0.03, 0.026, 0.034), r.accent, _basis(d, a), samples=(16, 12))
        for sgn in (-1, 1):
            base = palm + _scaled(a, sgn * 0.02) + _scaled(d, 0.016)
            mid = base + _scaled(d, 0.03) + _scaled(a, sgn * 0.014)
            tip = mid + _scaled(d, 0.024) - _scaled(a, sgn * 0.013)
            rod(f"{g}_hand/finger", base, mid, 0.0125, 0.0115, r.accent, samples=(10, 12))
            rod(f"{g}_hand/finger", mid, tip, 0.0115, 0.009, r.accent, samples=(10, 12))

    # -- legs: a ball at the hip and the knee, a thin thigh, a flared shin, a boot on a dark sole
    for side in ("left", "right"):
        hip, knee, ankle, toes = (frames[f"{side}_{b}"].position for b in ("upper_leg", "lower_leg", "foot", "toes"))
        g = f"leg_{side[0]}"
        ball(f"{g}_hip/ball", hip, 0.034, dark)
        rod(f"{g}_thigh/thigh", hip, knee, 0.024, 0.024, steel)
        ball(f"{g}_knee/ball", knee, 0.03, dark)
        rod(f"{g}_shin/shin", knee, ankle, 0.031, 0.046, r.body)
        # the boot follows the foot as it really points (seated, its sole faces forward), not a flat footprint
        ahead = toes - ankle
        ahead = _unit(ahead) if ahead.length > 1e-4 else Vec3(0, 0, 1)
        if abs(ahead.y) < 0.6 and ankle.y < 0.06:        # standing on it: the boot lies flat on the ground
            ahead = _unit(Vec3(ahead.x, 0.0, ahead.z))
        up = knee - ankle
        k = up.x * ahead.x + up.y * ahead.y + up.z * ahead.z
        up = Vec3(up.x - ahead.x * k, up.y - ahead.y * k, up.z - ahead.z * k)
        up = _unit(up) if up.length > 1e-4 else Vec3(0, 1, 0)
        basis = _basis(_cross(up, ahead), up)            # x across the foot, y up out of it, z along it
        c = ankle + _scaled(ahead, 0.034)
        solid(f"{g}_sole/sole", c - _scaled(up, 0.019), (0.058, 0.014, 0.09), "robot.sole", basis, ring=0.55,
              cap=0.3, samples=(26, 12))
        solid(f"{g}_boot/boot", c + _scaled(up, 0.006), (0.054, 0.032, 0.084), r.accent, basis, ring=0.6, cap=0.6,
              samples=(26, 16))

    # -- the head: a shell, a pod at each side, a bezel and a flat screen
    box(head, "head/head", (hx, hy, hz), (hrx, hry, hrz), r.body, soft=0.42, samples=(44, 30))
    quarter = rotation(0, 0, 90)                       # a cylinder along x
    for sx in (-1, 1):
        put(head, f"pod_{sx}/pod", (sx * (hrx + 0.006), hy - 0.005, hz), (0.05, 0.02, 0.05), r.accent, quarter,
            samples=(24, 10), cap=PILL)
        put(head, f"podcap_{sx}/cap", (sx * (hrx + 0.024), hy - 0.005, hz), (0.027, 0.01, 0.027), dark, quarter,
            samples=(18, 8), cap=PILL)
    front = hz + hrz
    sw, sh = SCREEN
    sy = hy - 0.012
    # the screen sits back in a deep frame, as a monitor's does; a renderer with real glass (Blender) gets a pane
    # over it, which the drawn look leaves out
    for sgn in (-1, 1):  # the frame: a bar above and below the screen, one at each side
        box(head, "bezel/bar", (hx, sy + sgn * (sh + 0.007), front + 0.01), (sw + 0.016, 0.009, 0.022), dark,
            soft=0.35, samples=(28, 14))
        box(head, "bezel/bar", (hx + sgn * (sw + 0.007), sy, front + 0.01), (0.009, sh + 0.016, 0.022), dark,
            soft=0.35, samples=(28, 14))
    box(head, "visor/visor", (hx, sy, front + 0.002), (sw, sh, 0.011), "robot.screen", soft=0.3)
    radii = (sw + 0.003, sh + 0.003, 0.004)
    parts.append(Limb(**shape(radii, 0.3, 0.3), radii=radii, at=head.point((hx, sy, front + 0.029)),
                      basis=head.basis(m.IDENTITY), name="glass/glass", material="robot.glass", samples=(40, 14),
                      casts_shadow=False, looks=("blender",)))
    n_h = 2.0 / 0.42

    def on_head(dx, dy, lift=0.0):  # metres from the middle of the shell's front, and out of it
        z = max(0.0, 1 - abs(dx / hrx) ** n_h - abs(dy / hry) ** n_h) ** (1 / n_h)
        return (hx + dx, hy + dy, hz + hrz * z + lift)

    for sx in (-1, 1):  # a rivet at each top corner of the shell's face
        put(head, "rivet/rivet", on_head(sx * 0.158, 0.098), (0.009, 0.009, 0.006), steel, samples=(10, 8))
    rod("gloss/gloss", head.point(on_head(0.118, 0.106, 0.001)), head.point(on_head(0.07, 0.11, 0.001)), 0.0065,
        0.0065, "robot.gloss", samples=(8, 9))

    # -- on its head
    top = hy + hry
    sway = math.radians(fig.ear_right - fig.ear_left) * 0.5      # what the head's motion gives the ears, it takes
    back = math.radians(fig.ear_back)

    def swung(p):  # a point of the head gear, leaning about the middle of the head's top
        dx, dy, dz = p[0] - hx, p[1] - top, p[2] - hz
        x, y = dx * math.cos(sway) + dy * math.sin(sway), -dx * math.sin(sway) + dy * math.cos(sway)
        y, z = y * math.cos(back) + dz * math.sin(back), dz * math.cos(back) - y * math.sin(back)
        return head.point((hx + x, top + y, hz + z))

    if r.gear == "sun":  # a rising sun: a half disc standing on the head, and seven fins for rays
        put(head, "sun/disc", (hx, top - 0.004, hz), (0.066, 0.046, 0.016), r.gear_colour, samples=(24, 12))
        for i, deg in enumerate(range(-75, 76, 25)):
            sn, cs = math.sin(math.radians(deg)), math.cos(math.radians(deg))
            long_ = 0.042 if i % 2 == 0 else 0.03
            p0 = (hx + 0.086 * sn, top - 0.004 + 0.064 * cs, hz)
            rod(f"ray_{i}/ray", swung(p0), swung((p0[0] + long_ * sn, p0[1] + long_ * cs, hz)), 0.0095, 0.0095,
                r.gear_colour, ref=head.vec((0, 0, 1)), deep=0.75, wide=1.0, samples=(10, 12))

    # -- the face, lit on the screen: the family's eyes, brows and mouth, so every expression and lip-sync works
    _on, limb, _R = fig._face(head, (hx, sy, front), (FACE[0], FACE[1], FACE[2]),
                              lambda carry, name, c, rr, mat, b=m.IDENTITY, samples=(14, 10): put(
                                  carry, name, c, rr, mat, b, samples))
    stroke0 = fig._stroke
    R = Vec3(*FACE)
    plane = front + 0.014

    def on(fx, fy, out=0.0):  # the face's shares, laid flat on the screen (the plush face sits low: lifted here)
        return (hx + fx * FACE[0], sy + (fy + 0.24) * FACE[1], plane + out * FACE[2] * 0.5)

    lit = {"plush.eye": r.led, "m.ink": r.led, "m.mouth": r.led, "m.tongue": "robot.screen", "dev.white": None}

    def led(name, point, radii_, material, **kw):
        material = lit.get(material, material)
        if material is not None:
            limb(name, point, radii_, material, **kw)

    def stroke(name, points, rad, material="m.ink"):
        stroke0(name, points, rad * (1.5 if material == "m.ink" else 1.0), lit.get(material, material))

    fig._stroke = stroke
    seen = e if not (fig.look_x or fig.look_y) else _replace(e, look=(e.look[0] + fig.look_x, e.look[1] + fig.look_y))
    plush3d.eyes(on, led, stroke, R, seen, "plush", "robot.screen", shut=fig.lid, scale=fig.eye_scale,
                 shut_each=(fig.lid_left, fig.lid_right), screen=True)
    fig._rest_mouth = r.rest_mouth
    m.brows(on, stroke, e, plush3d.EYE_X, 0.12, 0.11, 0.0065, was=fig.brows_from, mix=fig.brow_mix,
            lift=0.3 * (fig.eye_scale - 1.0))
    mouth = r.rest_mouth if (e.mouth == "flat" and r.rest_mouth) else e.mouth
    fig._lip(on, led, R, mouth, -0.5, 0.22, line=0.03)
    if "sweat" in e.extras:
        put(head, "sweat/drop", (-(hrx + 0.03), hy + hry * 0.6, front - 0.02), (0.014, 0.022, 0.014), "m.sweat",
            samples=(10, 8))
    return parts + fig._take_extra()


for _k in ROBOTS:
    m.WHOLE[_k] = _whole


def proof(out: Path | None = None) -> Path:
    """The kit's Claude beside the plush one: three views, then four poses of each."""
    out = out or ROOT / "examples" / "out" / "robot-kit-proof.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    shots = [("view", [("claude", "idle", yaw, x) for yaw, x in ((0, 1.35), (325, 0.75), (270, 0.2))] +
              [("claude2", "idle", yaw, x) for yaw, x in ((0, -0.3), (325, -0.9), (270, -1.45))])]
    for i, quad in enumerate((("cheerful", "ask", "shrug"), ("surprised", "sit-chat", "dizzy"))):
        shots.append((f"pose{i}", [("claude", p, 0, 1.35 - 0.56 * k) for k, p in enumerate(quad)] +
                      [("claude2", p, 0, -0.3 - 0.56 * k) for k, p in enumerate(quad)]))
    for label, cast in shots:
        loc = m._stage(f"robot-proof-{label}")
        for k, (who, pose, yaw, x) in enumerate(cast):
            loc.add(m.figure(who, POSES["claude"][pose], name=f"{who}-{k}", at=(x, 0, 0), yaw=yaw))
        loc.shot("row", (0.0, 0.5, 14.0), (0.0, 0.42, 0), lens=150)
        tile = out.parent / f".robot-proof-{label}.png"
        render(loc, "row", tile, 1920, 660, plush3d.look())
        rows.append(tile)
    subprocess.run(["ffmpeg", "-v", "error", "-y", *[a for t in rows for a in ("-i", str(t))], "-filter_complex",
                    f"vstack={len(rows)}", str(out)], check=True)
    for t in rows:
        t.unlink()
    return out


def acting(out: Path | None = None) -> Path:
    """The kit's robot acting through characters.film: a wave (the forearm telescopes), a nod, a jump, a walk and
    a line of speech. Writes the clip and a strip of its frames."""
    from . import film
    out = out or ROOT / "examples" / "out" / "robot-kit-acting.mp4"
    film.CAST = (*film.CAST, *(k for k in ROBOTS if k not in film.CAST))     # for this proof only
    for k in ROBOTS:
        POSES.setdefault(k, POSES["claude"])
    f = film.Film("robot-kit-acting", size=(1280, 720))
    a = f.add("claude2", "idle", at=(0.35, 0, 0))
    b = f.add("bear", "idle", at=(-0.45, 0, 0))
    f.camera((0, 0.6, 9.5), look_at=(0, 0.42, 0), lens=110)
    a.look(0.2, b).do(0.5, "wave").pose(2.2, "cheerful").do(3.0, "nod").do(4.0, "jump").go(5.2, (0.75, 0.2))
    a.pose(6.4, "surprised").pose(7.2, "idle")
    b.look(0.4, a).do(1.2, "wave", side="left").do(4.4, "giggle")
    f.render(str(out), seconds=8)
    f.strip(str(out.with_name(out.stem + "-strip.png")))
    return out


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "proof"
    print("wrote", acting() if what == "acting" else proof())
