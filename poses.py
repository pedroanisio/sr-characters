"""Named poses. Every character has the FULL canonical set (CANON), so any video can ask any character for any of
them; a video uses whichever subset it needs. A character may also have extra poses of its own (EXTRA).

- CANON: the generic version of each pose, used as is unless a character tunes it.
- TUNED: per-character versions (gaze, tilt, which arm).
- EXTRA: poses beyond the canonical set (the plush family's seated poses).

A new character must get the full set: characters.check() refuses a character with a missing pose or an arm
gesture the models cannot do.
"""

from __future__ import annotations

from .doodle import Pose as P

CANON: dict[str, P] = {
    "idle": P(),
    "talk": P(mouth="open"),
    "cheerful": P(eyes="normal", brows="raised", mouth="smile", arms="present", look=(0.7, 0.3), tilt=3),
    "confident": P(eyes="normal", brows="raised", mouth="smile", look=(0.2, -0.1), tilt=-3),
    "smug": P(eyes="half", brows="skeptic", mouth="smug", arms="point", look=(0.3, -0.2), tilt=-4),
    "explain": P(eyes="closed", brows="flat", mouth="smile", arms="present", tilt=4),
    "proud": P(eyes="closed", brows="raised", mouth="smile", arms="point", tilt=5),
    "ask": P(eyes="wide", brows="worried", arms="raise", look=(0.2, -0.4), tilt=6, extras=("question",)),
    "puzzled": P(eyes="wide", brows="raised", arms="raise", tilt=-5, extras=("question",)),
    "suspicious": P(eyes="normal", brows="skeptic", arms="chin", look=(1.0, 0.2), tilt=4),
    "worried": P(eyes="normal", brows="worried", mouth="wavy", arms="chin", look=(-0.5, -0.5), tilt=3),
    "sulk": P(eyes="normal", brows="worried", mouth="frown", look=(-0.8, -0.6), tilt=-5),
    "shrug": P(eyes="side", brows="raised", mouth="smug", arms="shrug", look=(0.8, 0.1), tilt=-3),
    "surprised": P(eyes="wide", brows="raised", mouth="o", look=(0.9, 0.1), tilt=-3),
    "yell": P(eyes="wide", brows="angry", mouth="yell"),
    "dizzy": P(eyes="spiral", brows="worried", mouth="yell", arms="panic", tilt=-9, extras=("sweat",)),
}

TUNED: dict[str, dict[str, P]] = {
    "bear": {}, "cat": {}, "pig": {}, "bunny": {},  # the plush family (plush3d.py)
    "redpanda": {}, "quokka": {}, "fennec": {}, "otter": {}, "koala": {}, "pika": {},
    "axolotl": {}, "arcticfox": {}, "hippo": {},
    "lion": {}, "tiger": {}, "panda": {}, "eagle": {}, "duck": {}, "dragon": {}, "armadillo": {}, "shark": {},
}

EXTRA: dict[str, dict[str, P]] = {
    "bear": {}, "cat": {}, "pig": {}, "bunny": {},
    "redpanda": {}, "quokka": {}, "fennec": {}, "otter": {}, "koala": {}, "pika": {},
    "axolotl": {}, "arcticfox": {}, "hippo": {},
    "lion": {}, "tiger": {}, "panda": {}, "eagle": {}, "duck": {}, "dragon": {}, "armadillo": {}, "shark": {},
}

# The plush family sits (extras "sit": legs out in front), on the floor or on a step. Every plush animal has these.
PLUSH_SEATED: dict[str, P] = {
    "sit": P(extras=("sit",)),
    "sit-happy": P(eyes="closed", mouth="smile", tilt=4, extras=("sit",)),
    "sit-cuddle": P(eyes="normal", mouth="smile", arms="cuddle", look=(0.2, 0.0), tilt=-3, extras=("sit",)),
    "sit-chat": P(eyes="side", mouth="open", look=(0.6, 0.1), tilt=3, extras=("sit",)),
    "sit-wonder": P(eyes="wide", brows="raised", mouth="o", look=(0.5, 0.5), extras=("sit",)),
    "sit-sleep": P(eyes="closed", mouth="o", tilt=8, extras=("sit",), joints=(("head.nod_down_up", -8.0),)),
}
PLUSH = ("bear", "cat", "pig", "bunny", "redpanda", "quokka", "fennec", "otter", "koala", "pika", "axolotl",
         "arcticfox", "hippo", "lion", "tiger", "panda", "eagle", "duck", "dragon", "armadillo", "shark", "treefrog")
TUNED["treefrog"] = {}
EXTRA["treefrog"] = {}
ROBOTS = ("bip", "zap", "tec", "lata", "java", "c", "python", "claude", "chatgpt")  # the plush robots (plush3d.py)
PLUSH += ROBOTS
for _who in ROBOTS:
    TUNED[_who], EXTRA[_who] = {}, {}
for _who in PLUSH:
    EXTRA[_who] = {**EXTRA[_who], **PLUSH_SEATED}

POSES: dict[str, dict[str, P]] = {
    who: {**{name: TUNED[who].get(name, pose) for name, pose in CANON.items()}, **EXTRA[who]}
    for who in TUNED
}
