"""The actions of the cast: short motions a character plays over whatever pose it holds.

`ACTIONS` holds the ones any character can play, `PAW_ACTIONS` the arm actions of the characters with paws (the
plush family), `GAITS` the ways of going from one place to another. An `Action` says, as functions of its progress
`u` (0..1) and of the time `t` in seconds, what it adds to the pose and to the soft parts (squash, ears, tail,
wrist, feet, face). `characters.motion.perform()` plays them; `characters.film.Actor.do()` is the usual way in.

A new action goes here: write its function, then add it to `ACTIONS` (or `PAW_ACTIONS`). `characters.motion`
re-exports every name of this module, so `motion.ACTIONS` and `motion.Action` are these same objects.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping, Optional, Sequence

SIDES = ("left", "right")


# ----------------------------------------------------------------------------- actions
def _bell(u: float, rise: float = 0.2, fall: float = 0.25) -> float:
    """0 at the ends, 1 in the middle: eased in over `rise` and out over `fall` of the action."""
    if u <= 0 or u >= 1:
        return 0.0
    k = u / rise if u < rise else (1 - u) / fall if u > 1 - fall else 1.0
    return k * k * (3 - 2 * k)


@dataclass(frozen=True)
class Action:
    """A short motion over the held pose. `offsets(u, t, side)` gives degrees added to controls at progress u
    (0..1) and time t (s) into the action; `gesture` blends the arm(s) toward a named arm gesture by `_bell`;
    `face` is what the face becomes while the action's bell is above a half; `seated` offsets replace `offsets`
    for a seated figure (extras "sit")."""
    seconds: float
    offsets: Callable[[float, float, str], Mapping[str, float]]
    face: Mapping[str, Any] = None
    gesture: str = ""
    both: bool = False            # the gesture takes both arms (else the action's side)
    seated: Optional[Callable[[float, float, str], Mapping[str, float]]] = None
    squash: Optional[Callable[[float, float], float]] = None   # (u, t) -> squash (-) or stretch (+) of the soft body
    arm: float = 1.0              # how much longer the gesturing arm is drawn at the action's height
    ears: Optional[Callable[[float, float, str], tuple[float, float, float]]] = None   # (u, t, side) -> degrees
    #                               (left ear out, right ear out, both back) added while the action plays
    tail: Optional[Callable[[float, float], tuple[float, float]]] = None   # (u, t) -> degrees (sway, lift)
    air: Optional[Callable[[float], float]] = None   # u -> metres off the ground (a standing figure: a hop, a jump)
    feet: Optional[Callable[[float, float, bool], tuple]] = None   # (u, t, seated) -> metres (left up, right up,
    #                               left ahead, right ahead): the feet lifting (MascotFigure.foot_left_up ...)
    wink: float = 0.0             # how far the eye on the action's side shuts at its height (1 = a wink)
    blush: float = 0.0            # how much bigger the cheeks' blush grows at the action's height (0.5 = half again)
    lid: float = 0.0              # how far the eyelids lower at the action's height (0 to 1: heavy, sleepy eyes)
    gesture2: str = ""            # a second gesture the arm swings to and back from while the action plays ...
    mix: Optional[Callable[[float, float], float]] = None      # ... (u, t) -> its share, 0 to 1
    wrist: Optional[Callable[[float, float], float]] = None    # (u, t) -> degrees the paw flaps away from the body
    aimed: bool = False           # the arm points where the action's option "aim" (yaw, pitch in degrees) says
    reach: bool = False           # the arm goes to a point: the option "reach" (metres out, up, forward of the shoulder)
    flicker: Optional[Callable[[float, float], float]] = None   # (u, t) -> what a robot's screen power is times
    icon: bool = False            # a robot's screen shows the option "icon" in place of its face while it plays
    tip: Optional[Callable[[float, float], float]] = None   # (u, t) -> degrees what it holds tips toward its face
    pop: Optional[Callable[[float], float]] = None   # u -> how far a held bottle's pop has got (0 none .. 1 over)
    spin: Optional[Callable[[float], float]] = None   # u -> degrees the whole figure has turned (a pirouette);
    #                               toward its side; what it reaches at the end stays, so make that a full turn
    gaze: Optional[Callable[[float, float], tuple[float, float]]] = None   # (u, t) -> where the eyes look while it
    #                               plays, as a Pose's look (x, y; + y is down): eyes that move (an eye roll)
    topple: Optional[Callable[[float], float]] = None   # u -> degrees the whole figure leans over toward its side,
    #                               about its feet (a faint); it must be back at 0 by the end
    fly: Optional[Callable[[float], float]] = None   # u -> how far what it holds has flown from its hand to where
    #                               the option "fly" says (0 in the hand .. 1 there): a throw
    lift: Optional[Callable[[float], float]] = None   # u -> how far up a load in front of it is (0 on the ground
    #                               .. 1 carried): a crate picked up, carried and put down


def _giggle(u, t, side):
    e, shake = _bell(u), math.sin(2 * math.pi * 6.0 * t)
    out = {"chest.front_back": -5 * e, "head.nod_down_up": -6 * e + 2.5 * e * shake, "spine.front_back": -3 * e,
           "head.tilt_left_right": 4 * e}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = e * (7 + 5 * shake)
    return out


def _nod(u, t, side):
    return {"head.nod_down_up": -13 * _bell(u, 0.15, 0.2) * (0.5 - 0.5 * math.cos(2 * math.pi * 2 * u)),
            "neck.nod_down_up": -4 * _bell(u) * (0.5 - 0.5 * math.cos(2 * math.pi * 2 * u))}


def _shake(u, t, side):
    return {"head.turn_left_right": 16 * _bell(u, 0.15, 0.3) * math.sin(2 * math.pi * 2.5 * u)}


def _tilt(u, t, side):
    k = 1 if side == "right" else -1
    return {"head.tilt_left_right": 13 * k * _bell(u, 0.25, 0.3), "spine.left_right": -3 * k * _bell(u, 0.25, 0.3)}


def _wave(u, t, side):
    e, swing = _bell(u, 0.22, 0.25), math.sin(2 * math.pi * 3.0 * t)
    k = 1 if side == "right" else -1
    return {f"{side}_lower_arm.twist_in_out": 24 * e * swing, f"{side}_hand.in_out": 18 * e * swing,
            f"{side}_upper_arm.front_back": 6 * e * swing, "spine.left_right": 3 * k * e,
            "head.tilt_left_right": -5 * k * e}


def _cheer(u, t, side):
    e, bob = _bell(u, 0.2, 0.3), math.sin(2 * math.pi * 3.0 * t)
    out = {"chest.front_back": 4 * e, "head.nod_down_up": 6 * e, "spine.front_back": 2 * e * bob}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = 8 * e + 3 * e * bob
        out[f"{s}_upper_arm.front_back"] = 5 * e * bob
    return out


def _bounce(u, t, side):
    bend = 16 * _bell(u, 0.1, 0.15) * (0.5 - 0.5 * math.cos(2 * math.pi * 2 * u))   # two dips of the knees
    out = {"spine.front_back": -0.25 * bend}
    for s in SIDES:
        out.update({f"{s}_upper_leg.front_back": -bend, f"{s}_lower_leg.stretch": -2 * bend,
                    f"{s}_foot.up_down": -bend, f"{s}_shoulder.down_up": 0.4 * bend})
    return out


def _bounce_seated(u, t, side):
    bob = _bell(u, 0.1, 0.15) * math.sin(2 * math.pi * 2 * u)                        # seated: the back and shoulders
    out = {"spine.front_back": -5 * bob, "chest.front_back": -3 * bob, "head.nod_down_up": 4 * bob}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = 7 * abs(bob)
    return out


def _surprise(u, t, side):
    e = _bell(u, 0.08, 0.45)                                                          # fast in, slow out
    out = {"chest.front_back": 6 * e, "spine.front_back": 4 * e, "head.nod_down_up": 7 * e}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = 12 * e
    return out


ACTIONS: dict[str, Action] = {
    "giggle": Action(1.3, _giggle, face={"eyes": "closed", "mouth": "smile"},
                     squash=lambda u, t: _bell(u) * (-0.03 + 0.045 * math.sin(2 * math.pi * 6.0 * t)),
                     ears=lambda u, t, side: (*(2 * (7 * _bell(u) * math.sin(2 * math.pi * 6.0 * t - 0.8),)), 0.0)),
    "nod": Action(0.9, _nod, squash=lambda u, t: -0.03 * _bell(u) * (0.5 - 0.5 * math.cos(2 * math.pi * 2 * u))),
    "shake": Action(1.0, _shake),
    "tilt": Action(1.3, _tilt),
    "wave": Action(1.6, _wave, face={"mouth": "smile"}, gesture="raise", arm=1.45,
                   squash=lambda u, t: 0.04 * _bell(u, 0.22, 0.25)),
    "cheer": Action(1.5, _cheer, face={"eyes": "closed", "mouth": "open"}, gesture="panic", both=True, arm=1.4,
                    squash=lambda u, t: _bell(u, 0.2, 0.3) * (0.08 + 0.04 * math.sin(2 * math.pi * 3.0 * t)),
                    ears=lambda u, t, side: (-8 * _bell(u), -8 * _bell(u), -5 * _bell(u))),
    # two bounces: squashed at the bottom of each, stretched at the top
    "bounce": Action(1.0, _bounce, face={"mouth": "smile"}, seated=_bounce_seated,
                     squash=lambda u, t: 0.13 * _bell(u, 0.1, 0.15) * math.sin(2 * math.pi * 2 * u + math.pi)),
    "surprise": Action(0.9, _surprise, face={"eyes": "wide", "brows": "raised", "mouth": "o"},
                       squash=lambda u, t: 0.14 * _bell(u, 0.08, 0.45),
                       ears=lambda u, t, side: (*(2 * (-14 * _bell(u, 0.08, 0.45),)), -8 * _bell(u, 0.08, 0.45))),
    # ears only: one ear flicks (its side), both prick up, both droop
    "twitch": Action(0.35, lambda u, t, side: {},
                     ears=lambda u, t, side: ((0.0, 16 * math.sin(math.pi * u) ** 2, 0.0) if side == "right" else
                                              (16 * math.sin(math.pi * u) ** 2, 0.0, 0.0))),
    "perk": Action(1.2, lambda u, t, side: {"head.nod_down_up": 3 * _bell(u, 0.12, 0.4)},
                   ears=lambda u, t, side: (*(2 * (-16 * _bell(u, 0.12, 0.4),)), -6 * _bell(u, 0.12, 0.4))),
    "droop": Action(2.2, lambda u, t, side: {"head.nod_down_up": -5 * _bell(u, 0.3, 0.3)},
                    ears=lambda u, t, side: (*(2 * (24 * _bell(u, 0.3, 0.3),)), 10 * _bell(u, 0.3, 0.3))),
}
def _wag(amount: float, rate: float = 4.0, lift: float = 6.0):
    return lambda u, t: (amount * _bell(u) * math.sin(2 * math.pi * rate * t), lift * _bell(u))


for _name, _tail in (("giggle", _wag(16.0)), ("cheer", _wag(20.0, 4.5, 10.0)), ("wave", _wag(12.0, 3.0)),
                     ("bounce", _wag(10.0, 2.0, 8.0)),
                     ("surprise", lambda u, t: (0.0, 18.0 * _bell(u, 0.08, 0.45))),
                     ("droop", lambda u, t: (0.0, -12.0 * _bell(u, 0.3, 0.3)))):
    ACTIONS[_name] = replace(ACTIONS[_name], tail=_tail)
ACTIONS["wag"] = Action(1.6, lambda u, t, side: {"hips.twist_left_right": 0.0}, tail=_wag(22.0, 4.0, 8.0))   # tail only



# ---- off the ground: a crouch, the air, a landing that squashes and wobbles
UP, DOWN = 0.28, 0.72   # the share of a hop at which the feet leave the ground, and land


def _air(height: float, hops: int = 1):
    def at(u: float) -> float:
        v = (u * hops) % 1.0
        k = (v - UP) / (DOWN - UP)
        return height * 4 * k * (1 - k) if 0 < k < 1 else 0.0
    return at


def _crouch(v: float) -> float:
    """How bent the legs are through one hop: down before the launch, a little tucked in the air, down on landing."""
    if v < UP:
        return math.sin(math.pi * min(1.0, v / (UP * 0.85))) ** 0.8 if v < UP * 0.85 else 0.0
    if v < DOWN:
        return 0.3 * math.sin(math.pi * (v - UP) / (DOWN - UP))
    return math.exp(-(v - DOWN) * 11)


def _hop_squash(amount: float, hops: int = 1):
    def at(u: float, t: float) -> float:
        v = (u * hops) % 1.0
        if v < UP * 0.85:
            return -amount * math.sin(math.pi * v / (UP * 0.85)) ** 0.8                 # squashed in the crouch
        if v < DOWN:
            k = (v - UP * 0.85) / (DOWN - UP * 0.85)
            return amount * 1.1 * math.exp(-3.0 * k)                                    # stretched off the ground
        return -amount * 1.2 * math.exp(-(v - DOWN) * 13) * math.cos((v - DOWN) * 24)   # the landing, and its wobble
    return at


def _hop(bend: float, hops: int = 1):
    def offsets(u, t, side):
        v = (u * hops) % 1.0
        c, up = bend * _crouch(v), (math.sin(math.pi * (v - UP) / (DOWN - UP)) if UP < v < DOWN else 0.0)
        out = {"spine.front_back": -0.3 * c + 3 * up, "head.nod_down_up": -0.25 * c + 4 * up}
        for s in SIDES:
            out.update({f"{s}_upper_leg.front_back": -c, f"{s}_lower_leg.stretch": -2 * c, f"{s}_foot.up_down": -c,
                        f"{s}_upper_arm.down_up": 22 * up - 0.3 * c, f"{s}_shoulder.down_up": 6 * up})
        return out
    return offsets


def _kick(u, t, side):
    e, beat = _bell(u), math.sin(2 * math.pi * 2.6 * t)            # standing: marching on the spot
    out = {"spine.left_right": 2.5 * e * beat, "head.tilt_left_right": -2 * e * beat}
    for s, k in (("left", 1), ("right", -1)):
        lift = e * max(0.0, k * beat)
        out.update({f"{s}_upper_leg.front_back": -16 * lift, f"{s}_lower_leg.stretch": -26 * lift,
                    f"{s}_upper_arm.front_back": 8 * e * k * beat})
    return out


def _kick_seated(u, t, side):
    e, beat = _bell(u), math.sin(2 * math.pi * 2.6 * t)            # seated: the legs kick in turn
    out = {"spine.front_back": 3 * e, "chest.front_back": 2 * e, "head.nod_down_up": 3 * e,
           "spine.left_right": 1.5 * e * beat}
    for s, k in (("left", 1), ("right", -1)):
        out.update({f"{s}_upper_leg.front_back": -20 * e * k * beat, f"{s}_lower_leg.stretch": -10 * e * max(0.0, -k * beat),
                    f"{s}_upper_leg.in_out": 5 * e * k * beat, f"{s}_foot.up_down": 18 * e * k * beat})
    return out


ACTIONS.update({
    # a seated figure cannot leave its seat: it bounces instead
    "hop": Action(0.75, _hop(20.0), face={"mouth": "smile"}, seated=_bounce_seated, air=_air(0.07),
                  squash=_hop_squash(0.11), tail=lambda u, t: (0.0, 14.0 * _bell(u))),
    "jump": Action(1.1, _hop(28.0), face={"eyes": "closed", "mouth": "open"}, seated=_bounce_seated, air=_air(0.2),
                   squash=_hop_squash(0.16), tail=lambda u, t: (0.0, 20.0 * _bell(u))),
    "hops": Action(1.5, _hop(16.0, 3), face={"mouth": "smile"}, seated=_bounce_seated, air=_air(0.05, 3),
                   squash=_hop_squash(0.09, 3), tail=_wag(14.0, 2.0, 8.0)),
    "kick": Action(1.8, _kick, face={"mouth": "smile"}, seated=_kick_seated, tail=_wag(12.0, 2.6)),
})
ACTIONS["giggle"] = replace(ACTIONS["giggle"], blush=0.3)


def _kick_feet(u, t, seated):
    e, beat = _bell(u), math.sin(2 * math.pi * 2.6 * t)
    left, right = e * max(0.0, beat), e * max(0.0, -beat)
    return (0.05 * left, 0.05 * right, 0.035 * left, 0.035 * right) if seated else (0.045 * left, 0.045 * right, 0.0, 0.0)


def _tuck_feet(hops: int = 1):
    def feet(u, t, seated):
        v = (u * hops) % 1.0
        up = 0.0 if seated or not UP < v < DOWN else 0.02 * math.sin(math.pi * (v - UP) / (DOWN - UP))
        return (up, up, 0.0, 0.0)
    return feet


ACTIONS["kick"] = replace(ACTIONS["kick"], feet=_kick_feet)
for _name, _n in (("hop", 1), ("jump", 1), ("hops", 3)):
    ACTIONS[_name] = replace(ACTIONS[_name], feet=_tuck_feet(_n))
ACTIONS["droop"] = replace(ACTIONS["droop"], lid=0.5)
# one eye shuts (the action's side), the head tips that way, the mouth smiles
ACTIONS["wink"] = Action(0.8, lambda u, t, side: {"head.tilt_left_right": (5 if side == "right" else -5) * _bell(u),
                                                  "head.nod_down_up": -2 * _bell(u)},
                         face={"mouth": "smile"}, wink=1.0)
LINE_MOUTHS = ("flat", "smile", "frown", "smug", "wavy")   # mouths that turn into each other (MascotFigure.mouth_mix)
MORPH = 0.12         # s a line mouth or the brows take to become the next
OPEN_MOUTHS = ("open", "yell", "o")
_FACE_KEYS = ("lid", "mouth_open", "eye_scale", "blush", "mouth_mix", "brow_mix", "lid_left", "lid_right")   # mouths that open and close over a few frames (MascotFigure.mouth_open)


# ---- arm actions of the characters with paws (the plush family: a wrist, pads, arms drawn as long as the reach)
def _wave_paw(u, t, side):
    e, k = _bell(u, 0.22, 0.25), (1 if side == "right" else -1)
    return {"spine.left_right": 3 * k * e, "head.tilt_left_right": -6 * k * e, "chest.front_back": 2 * e}


def _clap(u, t, side):
    e, hit = _bell(u), math.cos(2 * math.pi * 3.0 * t)
    out = {"head.nod_down_up": 3 * e - 1.5 * e * hit, "chest.front_back": -2 * e}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = e * (4 - 3 * hit)
    return out


def _shy(u, t, side):
    e, k = _bell(u, 0.25, 0.3), (1 if side == "right" else -1)
    out = {"head.tilt_left_right": 9 * k * e, "head.nod_down_up": -5 * e, "spine.left_right": -3 * k * e,
           "hips.twist_left_right": 7 * e * math.sin(2 * math.pi * 0.9 * t)}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = 9 * e
    return out


def _pat(u, t, side):
    e, beat = _bell(u), math.sin(2 * math.pi * 2.5 * t)
    return {"left_upper_arm.front_back": 7 * e * beat, "right_upper_arm.front_back": -7 * e * beat,
            "head.nod_down_up": -3 * e, "head.tilt_left_right": 4 * e * math.sin(2 * math.pi * 1.25 * t),
            "chest.front_back": -3 * e}


def _palm(u, t, side):
    e, k = _bell(u, 0.22, 0.3), (1 if side == "right" else -1)
    return {"spine.left_right": 2 * k * e, "chest.front_back": 2 * e, "head.tilt_left_right": -2 * k * e}


# A wave sweeps the paw from beside the cheek out and back, the paw flapping a beat behind the arm (overlap).
PAW_ACTIONS: dict[str, Action] = {
    # a talking gesture: one open paw comes up beside the face, palm out (its pad and toe beans show), the wrist
    # turns out a little as the point is made, then the paw goes back down. A point made, a limit set, an opening.
    "palm": Action(1.6, _palm, gesture="palm", arm=1.0,
                   wrist=lambda u, t: 10 * _bell(u, 0.3, 0.3)),
    "wave": replace(ACTIONS["wave"], offsets=_wave_paw, gesture="wave-in", gesture2="wave-out", arm=1.0,
                    mix=lambda u, t: 0.5 - 0.5 * math.cos(2 * math.pi * 2.4 * t),
                    wrist=lambda u, t: -24 * _bell(u, 0.22, 0.25) * math.sin(2 * math.pi * 2.4 * t)),
    "cheer": replace(ACTIONS["cheer"], gesture="cheer", arm=1.0,
                     wrist=lambda u, t: 16 * _bell(u, 0.2, 0.3) * math.sin(2 * math.pi * 3.0 * t)),
    # paws apart, then together, three times a second; the body gives a little on each clap
    "clap": Action(1.7, _clap, face={"mouth": "smile"}, gesture="clap-open", gesture2="clap", both=True,
                   mix=lambda u, t: (0.5 - 0.5 * math.cos(2 * math.pi * 3.0 * t)) ** 0.7,
                   squash=lambda u, t: 0.025 * _bell(u) * math.cos(2 * math.pi * 3.0 * t), tail=_wag(14.0)),
    "shy": Action(2.0, _shy, face={"eyes": "closed", "mouth": "smile"}, gesture="cheeks", both=True,
                  squash=lambda u, t: -0.04 * _bell(u, 0.25, 0.3), blush=0.55,
                  ears=lambda u, t, side: (*(2 * (10 * _bell(u, 0.25, 0.3),)), 6 * _bell(u, 0.25, 0.3))),
    "pat": Action(1.6, _pat, face={"eyes": "closed", "mouth": "smile"}, gesture="tummy", both=True),
}


ACTIONS.setdefault("palm", Action(1.6, _palm, gesture="present"))   # without paws: an open hand, forward


# ---- talking and explaining (2026-11-11): what a character does with its arms and head while it makes a point
def _k(side: str) -> int:
    return 1 if side == "right" else -1


def _point(u, t, side):
    e, k = _bell(u, 0.2, 0.3), _k(side)
    return {"spine.left_right": 2 * k * e, "head.turn_left_right": 6 * k * e, "chest.front_back": 2 * e,
            "head.tilt_left_right": -3 * k * e}


def _tada(u, t, side):
    e = _bell(u, 0.15, 0.3)
    out = {"chest.front_back": 5 * e, "spine.front_back": 3 * e, "head.nod_down_up": 6 * e}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = 6 * e
    return out


def _beat(u, t, side):
    e, b = _bell(u, 0.15, 0.2), math.sin(2 * math.pi * 2.2 * t)
    out = {"head.nod_down_up": 2.5 * e * b, "chest.front_back": 1.5 * e * b}
    for s, k in (("left", 1), ("right", -1)):                       # the hands beat in turn
        out.update({f"{s}_lower_arm.stretch": 10 * e * k * b, f"{s}_upper_arm.front_back": 6 * e * k * b,
                    f"{s}_hand.down_up": 10 * e * k * b})
    return out


def _think(u, t, side):
    e, k = _bell(u, 0.2, 0.25), _k(side)
    return {"head.tilt_left_right": 8 * k * e, "head.nod_down_up": 5 * e, "spine.left_right": -2 * k * e,
            "hips.twist_left_right": 3 * e * math.sin(2 * math.pi * 0.5 * t)}


def _idea(u, t, side):
    e = _bell(u, 0.1, 0.4)                                           # fast in, slow out
    out = {"chest.front_back": 5 * e, "head.nod_down_up": 8 * e, "spine.front_back": 3 * e}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = 8 * e
    return out


def _shrug(u, t, side):
    e = _bell(u, 0.2, 0.3)
    out = {"head.tilt_left_right": 7 * _k(side) * e, "head.nod_down_up": -3 * e}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = 14 * e
    return out


def _nono(u, t, side):
    e = _bell(u, 0.2, 0.25)
    return {"head.turn_left_right": 9 * e * math.sin(2 * math.pi * 2.2 * t), "head.nod_down_up": -3 * e,
            "chest.front_back": -2 * e}


def _come(u, t, side):
    e, pull = _bell(u, 0.2, 0.25), 0.5 - 0.5 * math.cos(2 * math.pi * 2.0 * t)
    return {"spine.front_back": -3 * e * pull, "chest.front_back": -2 * e * pull, "head.nod_down_up": 4 * e * pull,
            "head.tilt_left_right": 4 * _k(side) * e}


def _listen(u, t, side):
    e, k = _bell(u, 0.2, 0.3), _k(side)
    return {"spine.left_right": 6 * k * e, "chest.left_right": 3 * k * e, "head.tilt_left_right": 9 * k * e,
            "head.turn_left_right": -8 * k * e}


def _whisper(u, t, side):
    e, k = _bell(u, 0.2, 0.3), _k(side)
    return {"spine.left_right": 8 * k * e, "head.tilt_left_right": 6 * k * e, "head.turn_left_right": 12 * k * e,
            "chest.front_back": -3 * e, "head.nod_down_up": -3 * e + 1.5 * e * math.sin(2 * math.pi * 4.0 * t)}


ACTIONS.update({
    # the arm goes out toward something: the option "aim" (yaw, pitch) says where; characters.film gives it from
    # `do(time, "point-at", at=actor or point)` and picks the arm on that side
    "point-at": Action(1.8, _point, gesture="point-front", aimed=True, squash=lambda u, t: 0.03 * _bell(u, 0.2, 0.3)),
    # here it is: both arms flung open, the chest up
    "tada": Action(1.8, _tada, face={"brows": "raised", "mouth": "smile"}, gesture="tada", both=True,
                   squash=lambda u, t: 0.07 * _bell(u, 0.15, 0.3), tail=_wag(16.0, 3.5, 8.0),
                   ears=lambda u, t, side: (*(2 * (-10 * _bell(u, 0.15, 0.3),)), -4 * _bell(u, 0.15, 0.3))),
    # the hands beat in front of the body, in turn, as a point is made (play it under a line of speech)
    "beat": Action(1.8, _beat, gesture="beat", both=True,
                   wrist=lambda u, t: 8 * _bell(u) * math.sin(2 * math.pi * 2.2 * t)),
    # a hand to the chin, the head tipped, the eyes up and away
    "think": Action(2.6, _think, face={"eyes": "normal", "brows": "arched", "look": (0.55, -0.6)}, gesture="chin",
                    tail=lambda u, t: (8.0 * _bell(u) * math.sin(2 * math.pi * 0.6 * t), 0.0),
                    ears=lambda u, t, side: ((0.0, 10 * _bell(u), 0.0) if side == "right" else (10 * _bell(u), 0.0, 0.0))),
    # an idea: a start, a small hop, one arm straight up, the eyes wide
    "idea": Action(1.5, _idea, face={"eyes": "wide", "brows": "raised", "mouth": "open"}, gesture="point-up",
                   air=_air(0.05), squash=lambda u, t: 0.12 * _bell(u, 0.1, 0.4),
                   tail=lambda u, t: (0.0, 18.0 * _bell(u, 0.1, 0.4)),
                   ears=lambda u, t, side: (*(2 * (-14 * _bell(u, 0.1, 0.4),)), -6 * _bell(u, 0.1, 0.4))),
    # who knows: the shoulders up, both hands out, the head to one side
    "shrug": Action(1.6, _shrug, face={"eyes": "side", "brows": "raised", "mouth": "smug"}, gesture="shrug",
                    both=True, squash=lambda u, t: -0.03 * _bell(u, 0.2, 0.3)),
    # no, no: a raised hand wags at the wrist while the head shakes, eyes shut
    "no-no": Action(1.8, _nono, face={"eyes": "closed", "brows": "flat", "mouth": "flat"}, gesture="palm",
                    wrist=lambda u, t: 26 * _bell(u, 0.2, 0.25) * math.sin(2 * math.pi * 3.0 * t)),
    # come here: the hand goes out and curls back to the face, twice a second
    "come-here": Action(2.0, _come, face={"mouth": "smile"}, gesture="present", gesture2="wave-in",
                        mix=lambda u, t: 0.5 - 0.5 * math.cos(2 * math.pi * 2.0 * t),
                        wrist=lambda u, t: -18 * _bell(u) * math.sin(2 * math.pi * 2.0 * t)),
    # listening: it leans to its side, a hand by the ear, that ear turned out
    "listen": Action(2.2, _listen, face={"eyes": "side", "brows": "raised"}, gesture="wave-in",
                     ears=lambda u, t, side: ((0.0, 18 * _bell(u, 0.2, 0.3), 0.0) if side == "right" else
                                              (18 * _bell(u, 0.2, 0.3), 0.0, 0.0))),
    # a whisper: it leans over to its side, a hand beside the mouth, the eyes half shut
    "whisper": Action(2.4, _whisper, face={"eyes": "half", "mouth": "o"}, gesture="cheeks"),
})


# ---- reactions (2026-11-11): what a feeling does to the whole body
def _legs(bend: float) -> dict[str, float]:
    """Both knees bent by `bend` degrees, the feet staying flat."""
    out = {}
    for s in SIDES:
        out.update({f"{s}_upper_leg.front_back": -bend, f"{s}_lower_leg.stretch": -2 * bend, f"{s}_foot.up_down": -bend})
    return out


def _laugh(u, t, side):
    e, ha = _bell(u, 0.15, 0.3), math.sin(2 * math.pi * 5.5 * t)
    out = {"chest.front_back": 6 * e + 2 * e * ha, "spine.front_back": 4 * e, "head.nod_down_up": 10 * e + 3 * e * ha}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = e * (8 + 6 * ha)
    return out


def _cry(u, t, side):
    e, sob = _bell(u, 0.2, 0.3), math.sin(2 * math.pi * 4.0 * t)
    out = {"spine.front_back": -5 * e, "chest.front_back": -4 * e, "head.nod_down_up": -9 * e + 2 * e * sob}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = e * (7 + 5 * max(0.0, sob))
    return out


def _breath(u: float) -> float:
    """A sigh's or a yawn's breath: up to 1 as the air goes in (the first 45%), down to -1 as it is let out."""
    return math.sin(math.pi * u / 0.9) if u < 0.45 else -math.sin(math.pi * (u - 0.45) / 0.55) ** 0.7


def _sigh(u, t, side):
    b = _breath(u)
    out = {"chest.front_back": 4 * b, "head.nod_down_up": 4 * b if b > 0 else 8 * b, "spine.front_back": 2 * b}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = 9 * b if b > 0 else 6 * b
    return out


def _yawn(u, t, side):
    e = _bell(u, 0.3, 0.3)
    out = {"chest.front_back": 6 * e, "spine.front_back": 3 * e, "head.nod_down_up": 11 * e,
           "head.tilt_left_right": 4 * _k(side) * e}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = 8 * e
    return out


def _shiver(u, t, side):
    e, j = _bell(u, 0.15, 0.25), math.sin(2 * math.pi * 11.0 * t)
    out = {"spine.left_right": 1.6 * e * j, "head.turn_left_right": 2.6 * e * j, "head.nod_down_up": -4 * e,
           "spine.front_back": -3 * e, **_legs(4 * e)}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = e * (11 + 2 * j)
    return out


def _shiver_seated(u, t, side):
    return {n: v for n, v in _shiver(u, t, side).items() if "_leg." not in n and "_foot." not in n}


def _flinch(u, t, side):
    e, k = _bell(u, 0.07, 0.5), _k(side)                             # in at once, out slowly
    out = {"chest.front_back": 8 * e, "spine.front_back": 6 * e, "spine.left_right": -4 * k * e,
           "head.turn_left_right": -14 * k * e, "head.nod_down_up": -4 * e}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = 14 * e
    return out


def _cower(u, t, side):
    e, j = _bell(u, 0.15, 0.3), math.sin(2 * math.pi * 9.0 * t)
    out = {"spine.front_back": -8 * e, "chest.front_back": -5 * e, "head.nod_down_up": -8 * e,
           "head.turn_left_right": 1.6 * e * j, **_legs(14 * e)}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = 12 * e
    return out


def _cower_seated(u, t, side):
    return {n: v for n, v in _cower(u, t, side).items() if "_leg." not in n and "_foot." not in n}


def _huff(u, t, side):
    e, k = _bell(u, 0.18, 0.3), _k(side)
    puff = math.exp(-((u - 0.12) / 0.07) ** 2)                       # the "hmph" itself, at the start
    out = {"head.turn_left_right": 22 * k * e, "head.nod_down_up": 6 * e + 4 * puff, "chest.front_back": 4 * e,
           "spine.left_right": -2 * k * e}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = 5 * e + 6 * puff
    return out


STOMPS = 2           # how many times a stomp's foot comes down


def _stomp_lift(u: float) -> float:
    """How far up the stomping foot is: up and down `STOMPS` times, its landings at the ends of each rise."""
    return max(0.0, math.sin(2 * math.pi * STOMPS * u - 0.5)) * _bell(u, 0.1, 0.15)


def _stomp(u, t, side):
    lift, hit = _stomp_lift(u), max(0.0, -math.sin(2 * math.pi * STOMPS * u - 0.5)) ** 3 * _bell(u, 0.1, 0.15)
    out = {f"{side}_upper_leg.front_back": -22 * lift, f"{side}_lower_leg.stretch": -34 * lift,
           "spine.left_right": -3 * _k(side) * lift, "head.nod_down_up": -7 * hit, "spine.front_back": -4 * hit}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = 6 * _bell(u) + 5 * hit
        out[f"{s}_upper_arm.front_back"] = -8 * hit
    return out


def _puff(u, t, side):
    e = _bell(u, 0.25, 0.3)
    out = {"chest.front_back": 7 * e, "spine.front_back": 3 * e, "head.nod_down_up": 6 * e,
           "head.tilt_left_right": 3 * _k(side) * e}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = 5 * e
        out[f"{s}_shoulder.front_back"] = -6 * e
    return out


ACTIONS.update({
    # a real laugh: the head back, the mouth wide, the body shaking, the hands on the tummy
    "laugh": Action(2.0, _laugh, face={"eyes": "closed", "mouth": "yell"}, gesture="tummy", both=True, blush=0.3,
                    squash=lambda u, t: _bell(u, 0.15, 0.3) * (0.03 + 0.05 * math.sin(2 * math.pi * 5.5 * t)),
                    tail=_wag(20.0, 5.5, 8.0),
                    ears=lambda u, t, side: (*(2 * (8 * _bell(u) * math.sin(2 * math.pi * 5.5 * t - 0.8),)), 4 * _bell(u))),
    # crying: the head down into the hands, the shoulders jerking, a tear
    "cry": Action(2.6, _cry, face={"eyes": "normal", "brows": "worried", "mouth": "frown"}, gesture="cheeks",
                  both=True, lid=0.55, squash=lambda u, t: -0.05 * _bell(u, 0.2, 0.3),
                  tail=lambda u, t: (0.0, -14.0 * _bell(u, 0.2, 0.3)),
                  ears=lambda u, t, side: (*(2 * (22 * _bell(u, 0.2, 0.3),)), 10 * _bell(u, 0.2, 0.3))),
    # a sigh: the chest and shoulders rise as the air goes in, then everything sinks as it is let out
    "sigh": Action(2.2, _sigh, face={"eyes": "half", "mouth": "o"}, lid=0.4,
                   squash=lambda u, t: 0.06 * _breath(u),
                   ears=lambda u, t, side: (*(2 * (10 * max(0.0, -_breath(u)),)), 5 * max(0.0, -_breath(u)))),
    # a yawn: the head back, the mouth as wide as it goes, both arms stretched out and up
    "yawn": Action(2.6, _yawn, face={"eyes": "closed", "mouth": "yell"}, gesture="tada", both=True,
                   squash=lambda u, t: 0.08 * _bell(u, 0.3, 0.3),
                   ears=lambda u, t, side: (*(2 * (-6 * _bell(u, 0.3, 0.3),)), 10 * _bell(u, 0.3, 0.3))),
    # cold, or afraid: hunched, the arms held in, everything trembling
    "shiver": Action(1.8, _shiver, face={"eyes": "squint", "brows": "worried", "mouth": "wavy"}, gesture="tummy",
                     both=True, seated=_shiver_seated,
                     squash=lambda u, t: _bell(u, 0.15, 0.25) * (-0.04 + 0.012 * math.sin(2 * math.pi * 11.0 * t)),
                     tail=lambda u, t: (3.0 * _bell(u) * math.sin(2 * math.pi * 11.0 * t), -10.0 * _bell(u)),
                     ears=lambda u, t, side: (*(2 * (_bell(u) * (8 + 3 * math.sin(2 * math.pi * 11.0 * t)),)), 6 * _bell(u))),
    # a flinch: it jerks back and turns its face away from its side, a hand up between
    "flinch": Action(1.1, _flinch, face={"eyes": "closed", "brows": "worried", "mouth": "wavy"}, gesture="palm",
                     squash=lambda u, t: -0.08 * _bell(u, 0.07, 0.5),
                     tail=lambda u, t: (0.0, 16.0 * _bell(u, 0.07, 0.5)),
                     ears=lambda u, t, side: (*(2 * (12 * _bell(u, 0.07, 0.5),)), 14 * _bell(u, 0.07, 0.5))),
    # cowering: crouched low and small behind its hands, wide-eyed, trembling
    "cower": Action(2.4, _cower, face={"eyes": "wide", "brows": "worried", "mouth": "wavy"}, gesture="cheeks",
                    both=True, seated=_cower_seated, squash=lambda u, t: -0.1 * _bell(u, 0.15, 0.3),
                    tail=lambda u, t: (0.0, -16.0 * _bell(u, 0.15, 0.3)),
                    ears=lambda u, t, side: (*(2 * (24 * _bell(u, 0.15, 0.3),)), 12 * _bell(u, 0.15, 0.3))),
    # hmph: a puff of the chest, then the face turned away to its side, chin up, arms folded
    "huff": Action(1.9, _huff, face={"eyes": "closed", "brows": "angry", "mouth": "frown"}, gesture="tummy",
                   both=True, squash=lambda u, t: 0.06 * math.exp(-((u - 0.12) / 0.07) ** 2),
                   tail=lambda u, t: (14.0 * _bell(u, 0.18, 0.3) * math.sin(2 * math.pi * 1.5 * t), 4.0 * _bell(u)),
                   ears=lambda u, t, side: (0.0, 0.0, 12 * _bell(u, 0.18, 0.3))),
    # a stomp: the foot of its side comes up and down twice, the body giving on each landing
    "stomp": Action(1.5, _stomp, face={"brows": "angry", "mouth": "frown"},
                    seated=lambda u, t, side: {n: v for n, v in _stomp(u, t, side).items() if "_leg." not in n},
                    squash=lambda u, t: -0.07 * _bell(u, 0.1, 0.15) * max(0.0, -math.sin(2 * math.pi * STOMPS * u - 0.5)) ** 3,
                    ears=lambda u, t, side: (0.0, 0.0, 10 * _bell(u))),
    # proud of itself: the chest out, the shoulders back, the chin up, eyes shut
    "puff": Action(2.2, _puff, face={"eyes": "closed", "brows": "raised", "mouth": "smug"},
                   squash=lambda u, t: 0.06 * _bell(u, 0.25, 0.3), tail=lambda u, t: (0.0, 16.0 * _bell(u, 0.25, 0.3)),
                   ears=lambda u, t, side: (*(2 * (-12 * _bell(u, 0.25, 0.3),)), -4 * _bell(u, 0.25, 0.3))),
})


# ---- everyday moves (2026-11-11): small things a body does between its lines
def _peak(u: float, at: float, wide: float) -> float:
    """A short bump round `at` (a share of the action), `wide` across: 1 at its top."""
    return math.exp(-((u - at) / wide) ** 2)


def _rise(u: float, until: float) -> float:
    """0 to 1 over the action's first `until`, eased; then 0 (what follows lets go at once)."""
    return math.sin(0.5 * math.pi * min(1.0, u / until)) ** 2 if u < until + 0.03 else 0.0


# ---- signs (2026-11-11): what a hand says by itself. No model bends single fingers, so a count, a thumbs-up and
# air quotes are told by the arm, the wrist and the head
COUNTS = 3           # how many a "count" counts


def _count_beat(u: float) -> float:
    """0 to 1 and back, once for each number counted."""
    return sum(_peak(u, (i + 1.0) / (COUNTS + 1.5), 0.09) for i in range(COUNTS))


def _count(u, t, side):
    e, b, k = _bell(u, 0.15, 0.2), _count_beat(u), _k(side)
    return {f"{side}_lower_arm.stretch": -12 * e * b, f"{side}_upper_arm.front_back": -5 * e * b,
            "head.nod_down_up": -5 * e * b, "head.turn_left_right": 7 * k * e, "head.tilt_left_right": 3 * k * e}


def _facepalm(u, t, side):
    e = _bell(u, 0.18, 0.3)
    return {"head.nod_down_up": -13 * e, "chest.front_back": -5 * e, "spine.front_back": -3 * e,
            "head.turn_left_right": 4 * e * math.sin(2 * math.pi * 0.9 * t) * _peak(u, 0.6, 0.25), **_legs(4 * e)}


def _chin_rub(u, t, side):
    e, rub, k = _bell(u, 0.2, 0.25), math.sin(2 * math.pi * 1.6 * t), _k(side)
    return {"head.tilt_left_right": -5 * k * e, "head.nod_down_up": -4 * e + 1.5 * e * rub,
            f"{side}_lower_arm.stretch": 7 * e * rub, f"{side}_hand.down_up": 9 * e * rub,
            "spine.left_right": 2 * k * e}


def _thumbs_up(u, t, side):
    e, push, k = _bell(u, 0.15, 0.3), _peak(u, 0.3, 0.14), _k(side)
    return {"chest.front_back": 3 * e, "head.nod_down_up": -4 * push + 2 * e, "head.tilt_left_right": 5 * k * e,
            f"{side}_hand.down_up": 30 * e, f"{side}_upper_arm.front_back": -5 * push}


def _salute(u, t, side):
    e = _bell(u, 0.1, 0.18)                                          # snapped up, held, snapped down
    out = {"chest.front_back": 6 * e, "spine.front_back": 3 * e, "head.nod_down_up": 4 * e}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = 4 * e
    return out


def _shush(u, t, side):
    e = _bell(u, 0.2, 0.3)
    return {"spine.front_back": -6 * e, "chest.front_back": -5 * e, "head.nod_down_up": 6 * e,
            "head.turn_left_right": 5 * e * math.sin(2 * math.pi * 0.45 * t), **_legs(5 * e)}


def _quote_twitch(u: float) -> float:
    return _peak(u, 0.38, 0.08) + _peak(u, 0.6, 0.08)                # the two twitches of air quotes


def _air_quotes(u, t, side):
    e, q = _bell(u, 0.18, 0.25), _quote_twitch(u)
    out = {"head.tilt_left_right": 7 * _k(side) * e, "head.nod_down_up": -3 * e * q, "chest.front_back": 2 * e}
    for s in SIDES:
        out.update({f"{s}_hand.down_up": -28 * e * q, f"{s}_lower_arm.stretch": -5 * e * q})
    return out


def _sweep(u: float) -> float:
    """How far the open hand has swept out to the side: out by a third of the way, held, back at the end."""
    k = max(0.0, min(1.0, (u - 0.12) / 0.28))
    return k * k * (3 - 2 * k)


def _present(u, t, side):
    e, w, k = _bell(u, 0.15, 0.25), _sweep(u), _k(side)
    there = w * (1.0 - 0.75 * _sweep(u - 0.33))                      # it looks at the thing, then back at us
    return {"spine.left_right": 5 * k * e * w, "chest.left_right": 3 * k * e * w,
            "head.turn_left_right": 16 * k * e * there, "head.tilt_left_right": -4 * k * e * w,
            f"{side}_hand.down_up": 12 * e * w}


def _stop(u, t, side):
    e = _bell(u, 0.08, 0.3)                                          # thrown up fast, let down slowly
    return {"spine.front_back": 4 * e, "chest.front_back": 3 * e, "head.nod_down_up": -3 * e,
            f"{side}_hand.down_up": 55 * e, **_legs(5 * e)}


def _so_so(u, t, side):
    e, rock, k = _bell(u, 0.2, 0.25), math.sin(2 * math.pi * 1.8 * t), _k(side)
    return {"head.tilt_left_right": 7 * e * rock, "head.nod_down_up": -2 * e, "spine.left_right": 2 * e * rock,
            f"{side}_lower_arm.twist_in_out": 26 * e * rock * k, f"{side}_hand.down_up": 8 * e}


ACTIONS.update({
    # one, two, three: a hand held up beats once for each, the head nodding along, the eyes on the hand
    "count": Action(2.4, _count, face={"brows": "raised", "look": (0.4, 0.1)}, gesture="count",
                    wrist=lambda u, t: 16 * _bell(u) * _count_beat(u)),
    # a hand over the forehead, the head dropped into it, the eyes shut
    "facepalm": Action(2.4, _facepalm, face={"eyes": "closed", "brows": "worried", "mouth": "frown"},
                       gesture="brow", squash=lambda u, t: -0.05 * _bell(u, 0.18, 0.3),
                       ears=lambda u, t, side: (*(2 * (12 * _bell(u, 0.18, 0.3),)), 6 * _bell(u, 0.18, 0.3))),
    # it weighs something up: a hand strokes the chin, the eyes down and narrowed
    "chin-rub": Action(2.6, _chin_rub, face={"eyes": "half", "brows": "flat", "mouth": "flat", "look": (-0.3, 0.5)},
                       gesture="chin", wrist=lambda u, t: 10 * _bell(u) * math.sin(2 * math.pi * 1.6 * t)),
    # well done: a fist pushed out in front, a nod with it, a wink
    "thumbs-up": Action(1.8, _thumbs_up, face={"brows": "raised", "mouth": "smile"}, gesture="thumb", wink=1.0,
                        squash=lambda u, t: 0.04 * _peak(u, 0.3, 0.14), tail=_wag(12.0, 3.5, 6.0)),
    # a salute: it draws itself up and the hand snaps to the temple
    "salute": Action(1.8, _salute, face={"brows": "flat", "mouth": "flat"}, gesture="salute",
                     squash=lambda u, t: 0.06 * _bell(u, 0.1, 0.18),
                     ears=lambda u, t, side: (*(2 * (-8 * _bell(u, 0.1, 0.18),)), 0.0)),
    # quiet: a hand to the lips, it leans in and looks from side to side
    "shush": Action(2.2, _shush, face={"eyes": "half", "brows": "raised", "mouth": "o"}, gesture="lips",
                    squash=lambda u, t: -0.03 * _bell(u, 0.2, 0.3)),
    # so-called: both hands up beside the head twitch twice, the head to one side
    "air-quotes": Action(2.0, _air_quotes, face={"eyes": "side", "brows": "raised", "mouth": "smug"},
                         gesture="quotes", both=True, wrist=lambda u, t: -22 * _bell(u) * _quote_twitch(u)),
    # this, here: an open hand sweeps out to its side; it looks at the thing, then back
    "present": Action(2.2, _present, face={"brows": "raised", "mouth": "smile"}, gesture="present",
                      gesture2="show", mix=lambda u, t: _sweep(u)),
    # stop: a flat palm thrown out in front, the body braced behind it
    "stop": Action(1.8, _stop, face={"eyes": "wide", "brows": "angry", "mouth": "flat"}, gesture="halt",
                   squash=lambda u, t: -0.04 * _bell(u, 0.08, 0.3)),
    # more or less: a hand held out rocks from side to side, the head rocking with it
    "so-so": Action(2.2, _so_so, face={"brows": "worried", "mouth": "wavy"}, gesture="soso",
                    wrist=lambda u, t: 22 * _bell(u) * math.sin(2 * math.pi * 1.8 * t)),
})


# ---- strong reactions (2026-11-12): a feeling that takes the whole figure over
def _gasp(u, t, side):
    e = _bell(u, 0.08, 0.35)                                         # in at once
    out = {"chest.front_back": 7 * e, "spine.front_back": 4 * e, "head.nod_down_up": 5 * e}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = 12 * e
    return out


def _both_hands(u, t, side):
    e, k = _bell(u, 0.18, 0.3), _k(side)
    out = {"head.nod_down_up": -15 * e, "chest.front_back": -7 * e, "spine.front_back": -5 * e,
           "head.turn_left_right": 6 * e * math.sin(2 * math.pi * 0.8 * t) * _peak(u, 0.55, 0.3),
           "head.tilt_left_right": 2 * k * e, **_legs(5 * e)}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = 8 * e
    return out


def _roll_turn(u: float) -> float:
    """How far round the eyes have got: 0 at one side, 1 at the other, over the top."""
    k = max(0.0, min(1.0, (u - 0.22) / 0.5))
    return k * k * (3 - 2 * k)


def _eye_roll(u, t, side):
    e, k = _bell(u, 0.15, 0.25), _roll_turn(u)
    return {"head.nod_down_up": 6 * e * math.sin(math.pi * k), "head.turn_left_right": -5 * e * math.cos(math.pi * k),
            "head.tilt_left_right": 4 * e * (2 * k - 1), "chest.front_back": 2 * e}


def _eye_roll_gaze(u, t):
    e, k = _bell(u, 0.15, 0.25), _roll_turn(u)
    return (-0.85 * e * math.cos(math.pi * k), -0.9 * e * math.sin(math.pi * k) - 0.1 * e)


def _swallow(u: float) -> float:
    return _peak(u, 0.5, 0.1)                                        # the moment it goes down


def _gulp(u, t, side):
    e, g = _bell(u, 0.2, 0.3), _swallow(u)
    out = {"head.nod_down_up": 4 * e - 9 * g, "chest.front_back": 3 * e, "spine.front_back": 2 * e}
    for s in SIDES:
        out.update({f"{s}_shoulder.down_up": 10 * e + 4 * g, f"{s}_upper_arm.down_up": -4 * e})
    return out


def _wipe(u: float) -> float:
    """The hand across the brow: 0 one side, 1 the other, in the action's first half."""
    k = max(0.0, min(1.0, (u - 0.18) / 0.3))
    return k * k * (3 - 2 * k)


def _relief(u, t, side):
    e, out_ = _bell(u, 0.15, 0.25), _bell(max(0.0, (u - 0.45) / 0.55), 0.3, 0.4)   # then the air goes out of it
    res = {"head.nod_down_up": 4 * e * (1 - out_) - 6 * out_, "chest.front_back": 3 * e - 7 * out_,
           "spine.front_back": -4 * out_, "head.tilt_left_right": 4 * _k(side) * e, **_legs(4 * out_)}
    for s in SIDES:
        res[f"{s}_shoulder.down_up"] = 6 * e * (1 - out_) - 8 * out_
    return res


TANTRUM = 3.4        # beats a second of a tantrum


def _tantrum(u, t, side):
    e, b = _bell(u, 0.12, 0.2), math.sin(2 * math.pi * TANTRUM * t)
    out = {"head.turn_left_right": 12 * e * b, "head.nod_down_up": -5 * e, "spine.left_right": 5 * e * b,
           "chest.left_right": 3 * e * b, "chest.front_back": -3 * e}
    for s, k in (("left", 1), ("right", -1)):
        out.update({f"{s}_upper_arm.front_back": -14 * e * k * b, f"{s}_lower_arm.stretch": 12 * e * k * b,
                    f"{s}_upper_leg.front_back": -16 * e * max(0.0, k * b), f"{s}_lower_leg.stretch": -26 * e * max(0.0, k * b)})
    return out


def _tantrum_feet(u, t, seated):
    e, b = _bell(u, 0.12, 0.2), math.sin(2 * math.pi * TANTRUM * t)
    return (0.045 * e * max(0.0, b), 0.045 * e * max(0.0, -b), 0.0, 0.0)


FAINT = 82.0         # degrees a faint lays the figure over


def _faint_down(u: float) -> float:
    """0 standing, 1 flat: it goes over faster and faster, lies there, and gets up at the end."""
    if u < 0.3:
        return 0.0
    if u < 0.44:
        return ((u - 0.3) / 0.14) ** 2
    if u < 0.8:
        return 1.0
    k = max(0.0, min(1.0, (0.97 - u) / 0.17))
    return k * k * (3 - 2 * k)


def _faint(u, t, side):
    sway = _bell(min(u, 0.3) / 0.3 * 0.5, 0.5, 0.0) * (1.0 - _faint_down(u))      # it grows until it goes
    d, k, w = _faint_down(u), _k(side), math.sin(2 * math.pi * 0.9 * t)
    out = {"spine.left_right": 7 * sway * w, "chest.left_right": 5 * sway * w, "head.tilt_left_right": 10 * sway * w + 9 * k * d,
           "head.nod_down_up": 6 * sway - 4 * d, "spine.front_back": 3 * sway}
    for s in SIDES:
        out.update({f"{s}_upper_arm.down_up": 10 * sway + 22 * d, f"{s}_shoulder.down_up": -5 * d,
                    f"{s}_upper_leg.in_out": 8 * d})
    return out


def _blush_hide(u, t, side):
    e, k, sq = _bell(u, 0.2, 0.3), _k(side), math.sin(2 * math.pi * 1.4 * t)
    out = {"head.turn_left_right": -16 * k * e, "chest.left_right": -7 * k * e, "spine.left_right": -5 * k * e,
           "hips.twist_left_right": 6 * e * sq, "head.nod_down_up": -8 * e, "head.tilt_left_right": -5 * k * e + 2 * e * sq}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = 11 * e
    return out


def _startle(u, t, side):
    e = _bell(u, 0.06, 0.45)                                         # in at once
    out = {"chest.front_back": 6 * e, "spine.front_back": 4 * e, "head.nod_down_up": 4 * e}
    for s in SIDES:
        out.update({f"{s}_shoulder.down_up": 14 * e, f"{s}_upper_leg.in_out": 9 * e, f"{s}_foot.up_down": -12 * e})
    return out


ACTIONS.update({
    # a gasp: the breath goes in at once, both hands fly to the mouth, the eyes wide
    "gasp": Action(1.6, _gasp, face={"eyes": "wide", "brows": "raised", "mouth": "o"}, gesture="gasp", both=True,
                   squash=lambda u, t: 0.09 * _bell(u, 0.08, 0.35), tail=lambda u, t: (0.0, 16.0 * _bell(u, 0.08, 0.35)),
                   ears=lambda u, t, side: (*(2 * (-12 * _bell(u, 0.08, 0.35),)), -5 * _bell(u, 0.08, 0.35))),
    # hurray: a jump with both arms thrown up
    "cheer-jump": replace(ACTIONS["jump"], seconds=1.3, face={"eyes": "closed", "brows": "raised", "mouth": "open"},
                          gesture="panic", both=True, air=_air(0.26), tail=_wag(18.0, 4.0, 10.0)),
    # it cannot look: the head down into both hands, shaking slowly
    "facepalm-double": Action(2.8, _both_hands, face={"eyes": "closed", "brows": "worried", "mouth": "frown"},
                              gesture="eyes", both=True, squash=lambda u, t: -0.06 * _bell(u, 0.18, 0.3),
                              ears=lambda u, t, side: (*(2 * (14 * _bell(u, 0.18, 0.3),)), 8 * _bell(u, 0.18, 0.3))),
    # oh, please: the eyes go round over the top from one side to the other, the head after them
    "eye-roll": Action(1.9, _eye_roll, face={"eyes": "normal", "brows": "flat", "mouth": "flat"}, gaze=_eye_roll_gaze,
                       lid=0.35),
    # a nervous swallow: it stiffens, the shoulders up, and the head dips as it goes down
    "gulp": Action(1.6, _gulp, face={"eyes": "wide", "brows": "worried", "mouth": "wavy", "look": (0.5, 0.0)},
                   squash=lambda u, t: 0.04 * _bell(u, 0.2, 0.3) - 0.07 * _swallow(u),
                   ears=lambda u, t, side: (*(2 * (8 * _bell(u, 0.2, 0.3),)), 6 * _bell(u, 0.2, 0.3))),
    # that was close: a hand across the brow, then the air goes out and the shoulders drop
    "relief": Action(2.6, _relief, face={"eyes": "closed", "brows": "raised", "mouth": "smile"}, gesture="brow",
                     gesture2="salute", mix=lambda u, t: _wipe(u),
                     squash=lambda u, t: 0.03 * _bell(u, 0.15, 0.25) - 0.08 * _bell(max(0.0, (u - 0.45) / 0.55), 0.3, 0.4)),
    # a tantrum: the fists pump, the feet stamp in turn, the head shakes, the mouth wide
    "tantrum": Action(2.4, _tantrum, face={"eyes": "closed", "brows": "angry", "mouth": "yell"}, gesture="panic",
                      gesture2="beat", both=True, mix=lambda u, t: 0.5 - 0.5 * math.cos(2 * math.pi * TANTRUM * t),
                      feet=_tantrum_feet, seated=_bounce_seated,
                      squash=lambda u, t: 0.05 * _bell(u, 0.12, 0.2) * math.sin(4 * math.pi * TANTRUM * t),
                      ears=lambda u, t, side: (*(2 * (10 * _bell(u),)), 10 * _bell(u)),
                      tail=lambda u, t: (10.0 * _bell(u) * math.sin(2 * math.pi * TANTRUM * t), 12.0 * _bell(u))),
    # a faint: it sways, wider and wider, goes over on to its side, lies there, and gets up again
    "faint": Action(3.6, _faint, face={"eyes": "spiral", "mouth": "wavy"}, seated=_bounce_seated,
                    topple=lambda u: FAINT * _faint_down(u),
                    squash=lambda u, t: -0.1 * _peak(u, 0.46, 0.04),
                    ears=lambda u, t, side: (*(2 * (14 * _faint_down(u),)), 0.0)),
    # too shy to look: it turns away from its side, both hands on its cheeks, blushing, squirming
    "blush-hide": Action(2.4, _blush_hide, face={"eyes": "closed", "brows": "worried", "mouth": "wavy"},
                         gesture="cheeks", both=True, blush=0.9, squash=lambda u, t: -0.05 * _bell(u, 0.2, 0.3),
                         tail=_wag(8.0, 1.4, -6.0)),
    # a fright: straight up off the ground, stiff, arms flung wide
    "startle-jump": Action(1.0, _startle, face={"eyes": "wide", "brows": "raised", "mouth": "yell"}, gesture="tada",
                           both=True, air=_air(0.13), squash=lambda u, t: 0.14 * _bell(u, 0.06, 0.45),
                           tail=lambda u, t: (0.0, 24.0 * _bell(u, 0.06, 0.45)),
                           ears=lambda u, t, side: (*(2 * (-16 * _bell(u, 0.06, 0.45),)), -8 * _bell(u, 0.06, 0.45))),
})


# ---- small things of every day (2026-11-12)
def _scratch(u, t, side):
    e, k, s = _bell(u, 0.2, 0.25), _k(side), math.sin(2 * math.pi * 4.5 * t)
    return {"head.tilt_left_right": 9 * k * e, "head.nod_down_up": -3 * e, "spine.left_right": 2 * k * e,
            f"{side}_lower_arm.stretch": 6 * e * s, f"{side}_hand.down_up": 12 * e * s}


HICCUPS = (0.16, 0.42, 0.56, 0.86)      # when a hiccup's jolts come (shares of the action): not evenly


def _hic(u: float) -> float:
    return sum(_peak(u, at, 0.035) for at in HICCUPS)


def _hiccup(u, t, side):
    h = _hic(u)
    out = {"chest.front_back": 7 * h, "head.nod_down_up": 8 * h, "spine.front_back": 3 * h}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = 16 * h
    return out


COUGHS = (0.3, 0.46, 0.62)


def _hack(u: float) -> float:
    return sum(_peak(u, at, 0.05) for at in COUGHS)


def _cough(u, t, side):
    e, c = _bell(u, 0.15, 0.25), _hack(u)
    out = {"chest.front_back": -4 * e - 9 * c, "spine.front_back": -3 * e - 6 * c, "head.nod_down_up": -4 * e - 8 * c}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = 4 * e + 9 * c
    return out


def _rub_eyes(u, t, side):
    e, rub = _bell(u, 0.2, 0.3), math.sin(2 * math.pi * 2.2 * t)
    out = {"head.nod_down_up": -7 * e, "chest.front_back": -3 * e, "head.tilt_left_right": 3 * e * rub}
    for s, k in (("left", 1), ("right", -1)):
        out.update({f"{s}_lower_arm.twist_in_out": 20 * e * rub * k, f"{s}_hand.down_up": 8 * e * rub,
                    f"{s}_shoulder.down_up": 6 * e})
    return out


def _wake(u, t, side):
    up, st = _rise(min(u, 0.45), 0.45) if u < 0.45 else 1.0, _bell(max(0.0, (u - 0.3) / 0.7), 0.3, 0.35)
    stir = math.sin(2 * math.pi * 1.1 * t) * (1.0 - up)
    out = {"head.nod_down_up": 9 * (1 - _bell(u, 0.3, 0.2)) * 0 + 4 * stir + 9 * st, "head.tilt_left_right": 4 * stir,
           "chest.front_back": 6 * st, "spine.front_back": 5 * st}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = 12 * st
    return out


def _watch(u, t, side):
    e, k = _bell(u, 0.18, 0.25), _k(side)
    return {"head.nod_down_up": -12 * e, "head.turn_left_right": 5 * k * e, "head.tilt_left_right": 4 * k * e,
            "chest.front_back": -3 * e, f"{side}_hand.down_up": 14 * e}


def _watch_feet(u, t, seated):
    tap = 0.022 * _bell(u, 0.35, 0.15) * max(0.0, math.sin(2 * math.pi * 3.0 * t))
    return (tap, 0.0, 0.0, 0.0)


def _dust(u, t, side):
    e, b = _bell(u, 0.15, 0.25), math.sin(2 * math.pi * 3.2 * t)
    out = {"head.nod_down_up": -11 * e, "chest.front_back": -5 * e, "spine.front_back": -4 * e,
           "spine.left_right": 3 * e * b, **_legs(4 * e)}
    for s, k in (("left", 1), ("right", -1)):
        out.update({f"{s}_upper_arm.front_back": 9 * e * k * b, f"{s}_lower_arm.stretch": 14 * e * k * b,
                    f"{s}_hand.down_up": 16 * e * k * b})
    return out


def _tummy(u, t, side):
    e, a = _bell(u, 0.2, 0.25), 2 * math.pi * 1.3 * t
    return {f"{side}_upper_arm.front_back": 7 * e * math.sin(a), f"{side}_upper_arm.down_up": 6 * e * math.cos(a),
            f"{side}_lower_arm.stretch": 8 * e * math.cos(a), "head.nod_down_up": -6 * e,
            "head.tilt_left_right": 5 * _k(side) * e, "hips.twist_left_right": 2 * e * math.sin(a)}


ACTIONS.update({
    # puzzled: a hand scratches the top of the head, the head tipped toward it
    "scratch-head": Action(2.2, _scratch, face={"brows": "raised", "mouth": "wavy", "look": (0.3, -0.5)},
                           gesture="scalp", wrist=lambda u, t: 14 * _bell(u) * math.sin(2 * math.pi * 4.5 * t)),
    # hiccups: small jolts that come when they like, the shoulders jumping, a little off the ground
    "hiccup": Action(2.8, _hiccup, face={"brows": "raised", "mouth": "flat"}, air=lambda u: 0.012 * min(1.0, _hic(u)),
                     squash=lambda u, t: 0.09 * _hic(u), tail=lambda u, t: (0.0, 14.0 * _hic(u)),
                     ears=lambda u, t, side: (*(2 * (-9 * _hic(u),)), 0.0)),
    # a cough: a fist to the mouth, the body jerking forward three times
    "cough": Action(2.0, _cough, face={"eyes": "closed", "brows": "worried", "mouth": "o"}, gesture="lips",
                    squash=lambda u, t: -0.06 * _hack(u)),
    # sleepy: both fists rub the eyes
    "rub-eyes": Action(2.4, _rub_eyes, face={"eyes": "closed", "mouth": "flat"}, gesture="eyes", both=True, lid=0.6,
                       wrist=lambda u, t: 10 * _bell(u) * math.sin(2 * math.pi * 2.2 * t),
                       ears=lambda u, t, side: (*(2 * (10 * _bell(u),)), 6 * _bell(u))),
    # waking: it stirs, then a long stretch with a yawn, both arms out. The pose after it is the film's to give
    # (Actor.wake_up() does both)
    "wake-up": Action(3.0, _wake, face={"eyes": "closed", "mouth": "yell"}, gesture="tada", both=True, lid=0.7,
                      squash=lambda u, t: 0.1 * _bell(max(0.0, (u - 0.3) / 0.7), 0.3, 0.35),
                      ears=lambda u, t, side: (*(2 * (-8 * _bell(u, 0.4, 0.3),)), 8 * _bell(u, 0.4, 0.3))),
    # what time is it: the forearm comes up across the chest, the head goes down to it, a foot taps
    "check-wrist": Action(2.4, _watch, face={"brows": "flat", "mouth": "flat", "look": (0.0, 0.8)}, gesture="watch",
                          feet=_watch_feet),
    # it brushes itself down: both hands sweep the tummy in turn, the head down to look
    "dust-off": Action(2.2, _dust, face={"brows": "flat", "mouth": "flat", "look": (0.0, 0.8)}, gesture="tummy",
                       both=True, wrist=lambda u, t: 14 * _bell(u) * math.sin(2 * math.pi * 3.2 * t)),
    # hungry, or full: a hand goes round and round on the tummy
    "tummy-rub": Action(2.4, _tummy, face={"eyes": "closed", "mouth": "smile"}, gesture="tummy",
                        tail=_wag(8.0, 1.3, 4.0)),
})


def _sneeze_in(u: float) -> float:
    return _rise(u, 0.55)                                            # the breath drawn in ...


def _sneeze_out(u: float) -> float:
    return _peak(u, 0.67, 0.09)                                      # ... and the sneeze


def _sneeze(u, t, side):
    a, b = _sneeze_in(u), _sneeze_out(u)
    quiver = 1.2 * a * math.sin(2 * math.pi * 9.0 * t)
    out = {"head.nod_down_up": 10 * a + quiver - 15 * b, "chest.front_back": 5 * a - 8 * b,
           "spine.front_back": 3 * a - 7 * b}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = 9 * a + 4 * b
    return out


def _ohno(u, t, side):
    e = _bell(u, 0.12, 0.3)
    out = {"chest.front_back": 4 * e, "head.nod_down_up": 3 * e,
           "head.turn_left_right": 6 * e * math.sin(2 * math.pi * 1.5 * t)}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = 10 * e
    return out


def _look_around(u, t, side):
    e, k = _bell(u, 0.15, 0.2), _k(side)
    sweep = math.sin(2 * math.pi * 0.8 * t)                          # one way, then the other
    return {"head.turn_left_right": 26 * k * e * sweep, "neck.turn_left_right": 8 * k * e * sweep,
            "spine.twist_left_right": 5 * k * e * sweep, "head.nod_down_up": 4 * e * math.sin(2 * math.pi * 0.4 * t),
            "spine.left_right": 2 * k * e * sweep}


def _take_one(u: float) -> float:
    return _bell(u / 0.34, 0.3, 0.4) if u < 0.34 else 0.0            # the first, idle glance


def _take_two(u: float) -> float:
    return _bell((u - 0.46) / 0.54, 0.1, 0.45) if u > 0.46 else 0.0   # the second: whipped back, and held


def _double_take(u, t, side):
    k, a, b = _k(side), _take_one(u), _take_two(u)
    return {"head.turn_left_right": k * (11 * a + 22 * b), "neck.turn_left_right": 6 * k * b,
            "chest.front_back": -4 * b, "spine.front_back": -3 * b, "head.nod_down_up": 3 * b,
            "spine.twist_left_right": 4 * k * b}


def _peek(u, t, side):
    e, k = _bell(u, 0.25, 0.3), _k(side)
    return {"spine.left_right": 12 * k * e, "chest.left_right": 6 * k * e, "head.tilt_left_right": -8 * k * e,
            "head.turn_left_right": 6 * k * e, "head.nod_down_up": 2 * e * math.sin(2 * math.pi * 0.7 * t)}


def _sink(u: float) -> float:
    return _rise(u, 0.72)                                            # the head going down, asleep ...


def _start(u: float) -> float:
    return _peak(u, 0.84, 0.07)                                      # ... and the start awake


def _nod_off(u, t, side):
    a, b = _sink(u), _start(u)
    drift = math.sin(2 * math.pi * 0.4 * t)
    out = {"head.nod_down_up": -15 * a + 9 * b, "neck.nod_down_up": -5 * a, "spine.front_back": -4 * a + 4 * b,
           "head.tilt_left_right": 6 * _k(side) * a, "spine.left_right": 2 * a * drift}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = -4 * a + 10 * b
    return out


def _love(u, t, side):
    e, k = _bell(u, 0.2, 0.3), _k(side)
    sway = math.sin(2 * math.pi * 0.7 * t)
    return {"head.tilt_left_right": 10 * k * e, "spine.left_right": 3 * e * sway, "head.nod_down_up": 3 * e,
            "hips.twist_left_right": 5 * e * sway, "chest.front_back": 2 * e}


def _bow(u, t, side):
    e = _bell(u, 0.3, 0.3)
    return {"hips.front_back": -10 * e, "spine.front_back": -16 * e, "chest.front_back": -12 * e,
            "head.nod_down_up": -10 * e}


def _stretch_out(u, t, side):
    e = _bell(u, 0.3, 0.3)
    lean = math.sin(2 * math.pi * 0.6 * t)
    out = {"chest.front_back": 6 * e, "spine.front_back": 5 * e, "head.nod_down_up": 8 * e,
           "spine.left_right": 4 * e * lean, "head.tilt_left_right": 3 * e * lean}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = 12 * e
    return out


def _crouch_down(u, t, side):
    e = _bell(u, 0.2, 0.25)
    out = {"spine.front_back": -6 * e, "chest.front_back": -3 * e, "head.nod_down_up": 6 * e, **_legs(20 * e)}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = 5 * e
    return out


ACTIONS.update({
    # a sneeze: the head goes back as the breath is drawn in, quivering, then snaps forward
    "sneeze": Action(1.7, _sneeze, face={"eyes": "closed", "brows": "worried", "mouth": "open"},
                     squash=lambda u, t: 0.07 * _sneeze_in(u) - 0.11 * _sneeze_out(u),
                     tail=lambda u, t: (0.0, 18.0 * _sneeze_out(u)),
                     ears=lambda u, t, side: (*(2 * (-8 * _sneeze_in(u) + 18 * _sneeze_out(u),)), -10 * _sneeze_out(u))),
    # oh no: both hands to the cheeks, the eyes wide, the head going from side to side
    "oh-no": Action(2.0, _ohno, face={"eyes": "wide", "brows": "worried", "mouth": "o"}, gesture="cheeks",
                    both=True, squash=lambda u, t: 0.06 * _bell(u, 0.12, 0.3),
                    ears=lambda u, t, side: (*(2 * (10 * _bell(u, 0.12, 0.3),)), 10 * _bell(u, 0.12, 0.3))),
    # looking for something: the head sweeps one way and the other, the body following a little
    "look-around": Action(2.6, _look_around, face={"brows": "raised"}),
    # a double take: an idle glance to its side, away, then the head whipped back there, eyes wide, leaning in
    "double-take": Action(1.6, _double_take, face={"eyes": "wide", "brows": "raised"},
                          squash=lambda u, t: 0.08 * _take_two(u),
                          ears=lambda u, t, side: (*(2 * (-14 * _take_two(u),)), -6 * _take_two(u))),
    # a peek: the whole body leans out to its side, the head staying level, to see round something
    "peek": Action(2.0, _peek, face={"eyes": "side", "brows": "raised"},
                   tail=lambda u, t: (-14.0 * _bell(u, 0.25, 0.3), 0.0)),
    # nodding off: the head sinks, the eyelids come down, then it starts awake
    "nod-off": Action(3.0, _nod_off, lid=0.8, squash=lambda u, t: -0.05 * _sink(u) + 0.07 * _start(u),
                      tail=lambda u, t: (0.0, -10.0 * _sink(u)),
                      ears=lambda u, t, side: (*(2 * (20 * _sink(u) - 12 * _start(u),)), 8 * _sink(u))),
    # in love: both hands under the chin, the head to one side, swaying, eyes shut, the cheeks glowing
    "love": Action(2.4, _love, face={"eyes": "closed", "mouth": "smile"}, gesture="cuddle", both=True, blush=0.7,
                   squash=lambda u, t: 0.03 * _bell(u, 0.2, 0.3), tail=_wag(10.0, 0.7, 6.0),
                   ears=lambda u, t, side: (*(2 * (8 * _bell(u, 0.2, 0.3),)), 4 * _bell(u, 0.2, 0.3))),
    # a bow: from the hips, a hand on the tummy, eyes shut
    "bow": Action(2.0, _bow, face={"eyes": "closed", "mouth": "smile"}, gesture="tummy",
                  squash=lambda u, t: -0.03 * _bell(u, 0.3, 0.3), tail=lambda u, t: (0.0, 12.0 * _bell(u, 0.3, 0.3))),
    # a good stretch: both arms up as far as they go, the back arched, leaning one way and the other
    "stretch": Action(2.6, _stretch_out, face={"eyes": "closed", "mouth": "smile"}, gesture="cheer", both=True,
                      arm=1.25, squash=lambda u, t: 0.12 * _bell(u, 0.3, 0.3),
                      tail=lambda u, t: (0.0, 14.0 * _bell(u, 0.3, 0.3)),
                      ears=lambda u, t, side: (*(2 * (-6 * _bell(u, 0.3, 0.3),)), 10 * _bell(u, 0.3, 0.3))),
    # a crouch: down on bent knees and up again, looking ahead (seated: it ducks)
    "crouch": Action(1.8, _crouch_down,
                     seated=lambda u, t, side: {n: v for n, v in _crouch_down(u, t, side).items() if "_leg." not in n
                                                and "_foot." not in n},
                     squash=lambda u, t: -0.12 * _bell(u, 0.2, 0.25),
                     ears=lambda u, t, side: (*(2 * (8 * _bell(u, 0.2, 0.25),)), 6 * _bell(u, 0.2, 0.25))),
})


# ---- on the move (2026-11-11): turning round, and moves that go on for as long as they are given
def _no_legs(move):
    return lambda u, t, side: {n: v for n, v in move(u, t, side).items() if "_leg." not in n and "_foot." not in n}


def _round(u: float) -> float:
    """How far round a spin is, 0 to 1: nothing during the wind-up, then eased all the way."""
    v = max(0.0, min(1.0, (u - 0.14) / 0.76))
    return v * v * (3 - 2 * v)


def _spin(u, t, side):
    wind, e = _peak(u, 0.1, 0.08), _bell(u, 0.18, 0.2)
    out = {"spine.front_back": -4 * wind + 3 * e, "head.nod_down_up": 4 * e, **_legs(10 * wind)}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = 9 * e
        out[f"{s}_upper_arm.down_up"] = 30 * e                       # the arms fly out
    return out


def _dance(u, t, side):
    e, b = _bell(u, 0.08, 0.1), 2 * math.pi * 1.0 * t
    s1 = math.sin(b)
    out = {"spine.left_right": 7 * e * s1, "hips.left_right": -5 * e * s1, "head.tilt_left_right": -8 * e * s1,
           "head.nod_down_up": 3 * e * abs(math.sin(2 * b)), **_legs(7 * e * abs(s1))}
    for s, k in (("left", 1), ("right", -1)):                       # one arm up as the other comes down
        out.update({f"{s}_shoulder.down_up": e * (6 + 6 * k * s1), f"{s}_upper_arm.down_up": e * (14 + 14 * k * s1),
                    f"{s}_upper_arm.front_back": 8 * e * k * math.cos(b)})
    return out


def _tap(u, t, side):
    e, k = _bell(u, 0.15, 0.2), _k(side)
    tap = max(0.0, math.sin(2 * math.pi * 3.2 * t))
    return {f"{side}_foot.up_down": 16 * e * tap, "head.tilt_left_right": 5 * k * e, "spine.front_back": 3 * e,
            "spine.left_right": -2 * k * e, "head.nod_down_up": 1.5 * e * tap}


def _wobble(u, t, side):
    e, w = _bell(u, 0.15, 0.3), 2 * math.pi * 0.9 * t
    out = {"spine.left_right": 9 * e * math.sin(w), "spine.front_back": 5 * e * math.cos(w),
           "hips.left_right": -4 * e * math.sin(w), "head.tilt_left_right": -9 * e * math.sin(w - 0.9),
           "head.nod_down_up": 5 * e * math.cos(w - 0.9)}
    for s, k in (("left", 1), ("right", -1)):
        out.update({f"{s}_shoulder.down_up": 6 * e, f"{s}_upper_arm.down_up": 12 * e * (1 + 0.5 * k * math.sin(w)),
                    f"{s}_upper_leg.front_back": -5 * e * max(0.0, k * math.sin(w))})
    return out


ACTIONS.update({
    # a pirouette: a wind-up, then all the way round toward its side, arms out, and a little off the ground
    "spin": Action(1.3, _spin, face={"eyes": "closed", "mouth": "smile"}, spin=lambda u: 360.0 * _round(u),
                   air=lambda u: 0.03 * math.sin(math.pi * _round(u)),
                   squash=lambda u, t: -0.08 * _peak(u, 0.1, 0.08) + 0.07 * _bell(u, 0.2, 0.3),
                   tail=lambda u, t: (26.0 * _bell(u), 8.0 * _bell(u)),
                   ears=lambda u, t, side: (*(2 * (14 * _bell(u),)), 0.0)),
    # a dance: side to side on bending knees, one arm up as the other comes down. As long as `seconds` says
    "dance": Action(4.0, _dance, face={"eyes": "closed", "mouth": "smile"}, seated=_no_legs(_dance),
                    squash=lambda u, t: 0.05 * _bell(u, 0.08, 0.1) * math.sin(4 * math.pi * t),
                    wrist=lambda u, t: 14 * _bell(u, 0.08, 0.1) * math.sin(4 * math.pi * t), tail=_wag(18.0, 2.0, 6.0),
                    ears=lambda u, t, side: (*(2 * (10 * _bell(u, 0.08, 0.1) * math.sin(4 * math.pi * t - 0.8),)), 0.0)),
    # waiting, and not pleased: the foot of its side taps, arms folded, eyes half shut. As long as `seconds` says
    "tap-foot": Action(2.4, _tap, face={"eyes": "half", "brows": "flat", "mouth": "flat"}, gesture="tummy", both=True,
                       tail=lambda u, t: (10.0 * _bell(u) * math.sin(2 * math.pi * 1.6 * t), 0.0)),
    # dizzy: the body goes round in a slow circle over its feet, the head a beat behind, the eyes in spirals
    "wobble": Action(2.6, _wobble, face={"eyes": "spiral", "brows": "worried", "mouth": "wavy"},
                     seated=_no_legs(_wobble),
                     squash=lambda u, t: 0.03 * _bell(u, 0.15, 0.3) * math.sin(2 * math.pi * 1.8 * t),
                     tail=lambda u, t: (20.0 * _bell(u, 0.15, 0.3) * math.sin(2 * math.pi * 0.9 * t - 1.2), 0.0),
                     ears=lambda u, t, side: (14 * _bell(u) * math.sin(2 * math.pi * 0.9 * t),
                                              -14 * _bell(u) * math.sin(2 * math.pi * 0.9 * t), 0.0)),
})


@dataclass(frozen=True)
class Gait:
    """A way of going from one place to another on two legs (perform's `travel`, style)."""
    speed: float                  # metres a second
    rate: float                   # steps of one foot a second
    thigh: float                  # degrees each thigh swings forward and back
    knee: float                   # degrees the knee of the leg that swings bends
    arm: float                    # degrees each arm swings, against its leg
    elbow: float = 0.0            # degrees the elbows stay bent
    rock: float = 3.0             # degrees the body rocks from foot to foot
    lift: float = 0.008           # metres it rises between steps
    squash: float = 0.02          # how much the body gives on each step
    lean: float = 0.0             # degrees it leans forward
    crouch: float = 0.0           # degrees its knees stay bent
    twist: float = 4.0            # degrees the trunk turns with each step
    shoulders: float = 0.0        # degrees the shoulders are held up
    scan: float = 0.0             # degrees the head turns from side to side as it goes
    hands: float = 0.0            # degrees the arms are held up in front
    out: float = 0.0              # degrees the arms are held out to the sides (a balance)
    toes: float = 0.0             # degrees the feet point down: it goes on the tips of its toes
    weave: float = 0.0            # metres it strays to either side of its line
    sway: float = 0.0             # degrees the trunk and the head loll, slower than the steps
    back: bool = False            # it goes without turning to where it goes (backwards, if that is behind it)
    skid: float = 0.0             # the last share of the trip is a skid: feet out in front, leaning back
    stumble: float = 0.0          # the share of the trip at which a foot catches and it pitches forward


GAITS = {
    "walk": Gait(0.5, 1.9, 24, 26, 20, elbow=8, rock=2.5, squash=0.015, lean=2, twist=5),
    "run": Gait(1.1, 2.9, 38, 50, 36, elbow=45, lift=0.03, squash=0.04, lean=9, twist=7),
    # on tiptoe: slow, crouched and hunched, the knees coming up high, the hands held up, the head looking round
    "sneak": Gait(0.22, 1.0, 20, 44, 0, elbow=55, lift=0.0, squash=0.0, lean=10, crouch=10, twist=3, shoulders=10,
                  scan=12, hands=28),
    # a happy skip: a knee up and a lift on every step, the arms swinging wide
    "skip": Gait(0.55, 1.5, 30, 34, 26, elbow=12, rock=4, lift=0.05, squash=0.06, lean=-2),
    # more ways of going (2026-11-12). On the tips of its toes: upright, quick small steps, the arms out for balance
    "tiptoe": Gait(0.3, 2.8, 10, 14, 0, rock=1.5, lift=0.004, squash=0.0, lean=-2, twist=2, shoulders=8, out=38,
                   toes=30),
    # a parade: the knees right up, straight arms swinging high, the back straight
    "march": Gait(0.42, 1.6, 46, 70, 50, rock=1.0, lift=0.012, squash=0.02, lean=-3, twist=2),
    # dizzy or worn out: slow, off its line to one side and the other, the trunk and the head lolling
    "stagger": Gait(0.22, 1.0, 16, 20, 10, rock=9, lift=0.0, squash=0.02, lean=6, twist=8, scan=10, weave=0.06,
                    sway=9),
    # backing off from something: small steps backwards, leaning away, the hands up in front
    "back-away": Gait(0.3, 1.5, 14, 16, 0, elbow=50, rock=3, lean=-8, twist=2, shoulders=8, hands=30, back=True),
    # a run that ends in a skid: the feet out in front, leaning back, half turned, the arms out
    "slide-stop": Gait(1.0, 2.9, 38, 50, 36, elbow=45, lift=0.03, squash=0.04, lean=9, twist=7, skid=0.42),
    # a walk in which a foot catches: it pitches forward, arms out, and saves itself
    "trip": Gait(0.5, 1.9, 24, 26, 20, elbow=8, rock=2.5, squash=0.015, lean=2, twist=5, stumble=0.5),
    # it glides backwards while its legs walk forwards: no rock, no lift, the heels peeling up in turn
    "moonwalk": Gait(0.3, 1.3, 22, 36, 8, elbow=20, rock=0.0, lift=0.0, squash=0.0, lean=5, twist=3, back=True),
    # with a load (2026-11-12). Behind something heavy: leaning into it, both arms out in front, short hard steps
    "push": Gait(0.2, 1.3, 18, 26, 0, rock=2, lift=0.0, squash=0.03, lean=15, twist=2, shoulders=8),
    # ... and hauling it: backwards, leaning away from it, the arms out in front
    "pull": Gait(0.2, 1.3, 16, 22, 0, rock=2, lift=0.0, squash=0.03, lean=-12, twist=2, shoulders=6, back=True),
    # carrying something in both arms: slow, leaning back a little under it, rocking; and the same backwards
    "carry": Gait(0.3, 1.5, 18, 20, 0, rock=3.5, lift=0.004, squash=0.03, lean=-5, twist=2),
    "carry-back": Gait(0.3, 1.5, 18, 20, 0, rock=3.5, lift=0.004, squash=0.03, lean=-5, twist=2, back=True),
}
# ways of going that are not a gait: one long jump; over on its hands and round, sideways; up on to a step
LEAPS = ("leap", "cartwheel", "climb-step")


# ---- together, and robots' screens (2026-11-11): an arm that goes to a point (another's hand, head or shoulder),
# a tumble, and what a screen does
def _fall(u, t, side):
    trip, down = _peak(u, 0.08, 0.06), _bell(u, 0.2, 0.22)
    daze = math.sin(2 * math.pi * 1.2 * t)
    out = {"spine.front_back": 8 * trip + 6 * down, "chest.front_back": 5 * trip + 4 * down,
           "hips.front_back": 20 * down,                             # it tips back on to its bottom
           "head.nod_down_up": 10 * trip - 6 * down + 4 * down * daze, "head.tilt_left_right": 7 * down * daze}
    for s in SIDES:                                                 # the legs go out in front: it is on its bottom
        out.update({f"{s}_upper_leg.front_back": -78 * down, f"{s}_upper_leg.in_out": 18 * down,
                    f"{s}_foot.up_down": 10 * down, f"{s}_shoulder.down_up": 12 * trip + 6 * down,
                    f"{s}_upper_arm.down_up": 40 * trip + 14 * down})
    return out


def _slap(u: float) -> float:
    return _peak(u, 0.5, 0.07)                                       # the moment the hands meet


def _high_five(u, t, side):
    e, k, hit = _bell(u, 0.25, 0.3), _k(side), _slap(u)
    return {"spine.left_right": 3 * k * e, "chest.front_back": 3 * e, "head.tilt_left_right": -4 * k * e,
            "head.nod_down_up": 3 * e - 4 * hit}


def _hug(u, t, side):
    e, k = _bell(u, 0.25, 0.3), _k(side)
    squeeze = 0.5 - 0.5 * math.cos(2 * math.pi * 0.9 * t)
    return {"spine.left_right": 6 * k * e, "chest.left_right": 3 * k * e, "head.tilt_left_right": 7 * k * e,
            "head.nod_down_up": -3 * e, "chest.front_back": -2 * e * squeeze}


def _pat_other(u, t, side):
    e, pat = _bell(u, 0.22, 0.25), math.sin(2 * math.pi * 2.6 * t)
    return {f"{side}_upper_arm.down_up": 5 * e * pat, f"{side}_lower_arm.stretch": 6 * e * pat,
            "spine.left_right": 4 * _k(side) * e, "head.tilt_left_right": 4 * _k(side) * e}


def _hand_over(u, t, side):
    e = _bell(u, 0.25, 0.3)
    return {"spine.left_right": 3 * _k(side) * e, "chest.front_back": -3 * e, "head.nod_down_up": -3 * e}


def _glitch(u, t, side):
    e = _bell(u, 0.1, 0.15)
    a = 1.0 if math.sin(2 * math.pi * 5.3 * t) > 0 else -1.0         # it jerks, it does not swing
    b = 1.0 if math.sin(2 * math.pi * 3.1 * t + 1.0) > 0 else -1.0
    return {"head.turn_left_right": 9 * e * a, "head.tilt_left_right": 6 * e * b, "spine.left_right": 2 * e * a * b,
            "left_shoulder.down_up": 8 * e * max(0.0, a), "right_shoulder.down_up": 8 * e * max(0.0, -a)}


def _flicker(u, t):
    return 0.2 if math.sin(2 * math.pi * 9.0 * t) * math.sin(2 * math.pi * 2.3 * t + 0.7) > 0.15 else 1.0


ACTIONS.update({
    # a tumble: it trips, lands on its bottom with its legs out, sits there dazed, and gets up
    "fall": Action(2.6, _fall, face={"eyes": "spiral", "mouth": "wavy"}, seated=_bounce_seated,
                   air=lambda u: 0.05 * _peak(u, 0.1, 0.06),
                   squash=lambda u, t: -0.14 * _peak(u, 0.2, 0.05) + 0.04 * _peak(u, 0.31, 0.05),
                   tail=lambda u, t: (0.0, 16.0 * _peak(u, 0.12, 0.08)),
                   ears=lambda u, t, side: (*(2 * (18 * _peak(u, 0.14, 0.08),)), -10 * _peak(u, 0.14, 0.08))),
    # a high five: the hand of its side goes up to meet another's (film.high_five gives both the same point)
    "high-five": Action(1.5, _high_five, face={"mouth": "open"}, reach=True, squash=lambda u, t: 0.06 * _slap(u),
                        wrist=lambda u, t: -16 * _slap(u), tail=_wag(14.0, 4.0, 6.0)),
    # a hug: the arm of its side goes round another, it leans in, eyes shut (film.hug)
    "hug": Action(2.6, _hug, face={"eyes": "closed", "mouth": "smile"}, reach=True, blush=0.4,
                  squash=lambda u, t: -0.04 * _bell(u, 0.25, 0.3) * (0.5 - 0.5 * math.cos(2 * math.pi * 0.9 * t)),
                  tail=_wag(10.0, 1.5, 4.0)),
    # it pats another on the head (film.pat)
    "pat-other": Action(2.0, _pat_other, face={"mouth": "smile"}, reach=True,
                        wrist=lambda u, t: 18 * _bell(u) * math.sin(2 * math.pi * 2.6 * t)),
    # a hand held out with something in it, and a hand held out for it (film.give moves the thing across)
    "give": Action(1.9, _hand_over, face={"mouth": "smile"}, reach=True),
    "take": Action(1.9, _hand_over, face={"brows": "raised", "mouth": "smile"}, reach=True,
                   ears=lambda u, t, side: (*(2 * (-10 * _bell(u, 0.25, 0.3),)), -4 * _bell(u, 0.25, 0.3))),
    # a glitch: the head and shoulders jerk; a robot's screen cuts in and out
    "glitch": Action(1.4, _glitch, face={"eyes": "squint", "mouth": "wavy"}, flicker=_flicker,
                     squash=lambda u, t: 0.03 * _bell(u, 0.1, 0.15) * (1.0 if math.sin(2 * math.pi * 7.0 * t) > 0 else -1.0),
                     ears=lambda u, t, side: (*(2 * (10 * _bell(u) * (1.0 if math.sin(2 * math.pi * 7.0 * t) > 0 else -1.0),)), 0.0)),
    # a robot's screen shows a picture in place of its face (the option "icon"), the head tipped
    "screen-icon": Action(2.0, lambda u, t, side: {"head.tilt_left_right": 5 * _k(side) * _bell(u),
                                                   "head.nod_down_up": 2 * _bell(u)}, icon=True),
})


# ---- a drink in the hand (2026-11-11): a toast, a drink, a bottle popped
def _toast(u, t, side):
    e, k, clink = _bell(u, 0.25, 0.3), _k(side), _slap(u)
    return {"spine.left_right": 3 * k * e, "chest.front_back": 3 * e, "head.tilt_left_right": -4 * k * e,
            "head.nod_down_up": 4 * e - 3 * clink}


def _sip(u: float) -> float:
    return _bell(u, 0.3, 0.3)                                        # the drink at the mouth


def _drink(u, t, side):
    e = _sip(u)
    gulp = max(0.0, math.sin(2 * math.pi * 1.6 * t)) ** 2
    return {"head.nod_down_up": 11 * e + 2 * e * gulp, "chest.front_back": 4 * e, "spine.front_back": 2 * e,
            "head.tilt_left_right": 3 * _k(side) * e}


POP = 0.5            # the share of a "pop-cork" at which the cork goes


def _shaken(u: float) -> float:
    return _bell(u / POP, 0.2, 0.15) if u < POP else 0.0             # the bottle shaken, before it goes


def _popped(u: float) -> float:
    return _bell((u - POP) / (1 - POP), 0.08, 0.5) if u > POP else 0.0   # the start it gives, let go slowly


def _pop_cork(u, t, side):
    shake, start = _shaken(u), _popped(u)
    beat = math.sin(2 * math.pi * 6.0 * t)
    out = {f"{side}_upper_arm.down_up": 7 * shake * beat, f"{side}_lower_arm.stretch": 9 * shake * beat,
           "head.nod_down_up": 2 * shake * beat + 9 * start, "chest.front_back": 7 * start, "spine.front_back": 5 * start,
           "head.tilt_left_right": -5 * _k(side) * start}
    for s in SIDES:
        out[f"{s}_shoulder.down_up"] = 4 * shake + 12 * start
    return out


ACTIONS.update({
    # a toast: the hand with the glass goes up to meet the others' (film.toast gives them all the same point)
    "toast": Action(1.9, _toast, face={"eyes": "closed", "mouth": "open"}, reach=True,
                    squash=lambda u, t: 0.04 * _slap(u), tip=lambda u, t: -14 * _slap(u), tail=_wag(12.0, 3.0, 6.0)),
    # a drink: what it holds comes to the mouth and tips, the head goes back, a swallow or two (Actor.drink)
    "drink": Action(2.6, _drink, face={"eyes": "closed"}, gesture="sip", tip=lambda u, t: 58 * _sip(u),
                    squash=lambda u, t: 0.03 * _sip(u), tail=lambda u, t: (0.0, 8.0 * _sip(u))),
    # a bottle popped: it is shaken, the cork goes, the foam bursts, the figure starts back (Actor.pop_cork)
    "pop-cork": Action(2.4, _pop_cork, face={"eyes": "wide", "brows": "raised", "mouth": "open"}, gesture="present",
                       pop=lambda u: max(0.0, (u - POP) / (1 - POP)), tip=lambda u, t: -12 * _shaken(u) - 6 * _popped(u),
                       squash=lambda u, t: -0.05 * _shaken(u) + 0.1 * _popped(u),
                       wrist=lambda u, t: 14 * _shaken(u) * math.sin(2 * math.pi * 6.0 * t),
                       tail=lambda u, t: (0.0, 18.0 * _popped(u)),
                       ears=lambda u, t, side: (*(2 * (-14 * _popped(u),)), -6 * _popped(u))),
})


# ---- with things, and two together (2026-11-12): a throw and a catch, a load carried, a book, keys, a phone, a
# handshake
THROW, LAND = 0.45, 0.8      # the shares of a throw at which the thing leaves the hand, and arrives


def _throw(u, t, side):
    k, back, go = _k(side), _peak(u, 0.27, 0.13), _peak(u, 0.5, 0.1)
    return {"spine.front_back": 7 * back - 13 * go, "chest.front_back": 4 * back - 7 * go,
            "spine.left_right": k * (5 * back - 4 * go), "head.nod_down_up": 4 * back - 5 * go,
            f"{side}_upper_arm.down_up": 34 * back, f"{side}_lower_arm.stretch": -30 * back + 14 * go,
            f"{side}_shoulder.down_up": 8 * back}


def _caught(u: float) -> float:
    return _peak(u, 0.47, 0.08)                                      # the moment it lands in the hand


def _catch(u, t, side):
    e, hit = _bell(u, 0.25, 0.3), _caught(u)
    return {"head.nod_down_up": 6 * e - 7 * hit, "chest.front_back": 3 * e - 6 * hit, "spine.front_back": -5 * hit,
            f"{side}_lower_arm.stretch": -16 * hit, "spine.left_right": 3 * _k(side) * e}


def _lifting(u: float) -> float:
    return _bell(u, 0.16, 0.16)                                      # up off the ground, carried, and down again


def _lift(u, t, side):
    bend = _peak(u, 0.07, 0.07) + _peak(u, 0.93, 0.07)               # down to it, and down with it
    out = {"spine.front_back": -16 * bend - 3 * _lifting(u), "chest.front_back": -7 * bend,
           "head.nod_down_up": -8 * bend}
    for s in SIDES:
        out.update({f"{s}_upper_leg.front_back": -14 * bend, f"{s}_lower_leg.stretch": -24 * bend,
                    f"{s}_shoulder.down_up": 5 * _lifting(u)})
    return out


def _read(u, t, side):
    e, turn = _bell(u, 0.15, 0.2), _peak(u, 0.58, 0.05)
    line = (1.1 * t) % 1.0
    return {"head.nod_down_up": -11 * e + 3 * turn, "neck.nod_down_up": -3 * e,
            "head.turn_left_right": 4 * e * (line - 0.5), "head.tilt_left_right": 3 * _k(side) * e,
            f"{side}_lower_arm.stretch": 10 * turn, f"{side}_upper_arm.down_up": 6 * turn}


def _read_gaze(u, t):
    e = _bell(u, 0.15, 0.2)
    return (0.7 * e * (2 * ((1.1 * t) % 1.0) - 1.0), 0.75 * e)        # along a line, and back to the next


def _type(u, t, side):
    e = _bell(u, 0.15, 0.2)
    left, right = math.sin(2 * math.pi * 6.5 * t), math.sin(2 * math.pi * 6.5 * t + 2.2)
    burst = 0.5 + 0.5 * math.sin(2 * math.pi * 0.9 * t)             # it types in bursts
    return {"head.nod_down_up": -8 * e + 1.5 * e * burst, "head.turn_left_right": 3 * e * math.sin(2 * math.pi * 0.6 * t),
            "left_lower_arm.stretch": 9 * e * burst * left, "right_lower_arm.stretch": 9 * e * burst * right,
            "left_upper_arm.down_up": 3 * e * burst * left, "right_upper_arm.down_up": 3 * e * burst * right,
            "spine.front_back": -3 * e}


def _phone(u, t, side):
    e, k = _bell(u, 0.18, 0.2), _k(side)
    yes = max(0.0, math.sin(2 * math.pi * 0.8 * t)) ** 3            # mm-hm, now and then
    return {"head.tilt_left_right": 8 * k * e, "head.turn_left_right": -6 * k * e, "head.nod_down_up": -5 * e * yes,
            "spine.left_right": 2 * k * e, f"{side}_shoulder.down_up": 7 * e}


def _shake_hands(u, t, side):
    e, pump = _bell(u, 0.25, 0.3), math.sin(2 * math.pi * 2.6 * t)
    return {f"{side}_lower_arm.stretch": 10 * e * pump, f"{side}_upper_arm.down_up": 6 * e * pump,
            "spine.front_back": -4 * e, "head.nod_down_up": -3 * e + 3 * e * pump, "spine.left_right": 2 * _k(side) * e}


ACTIONS.update({
    # a throw: the arm goes back, then forward, and what it holds leaves the hand for where the option "fly" says
    # (film.throw aims it at another's hands)
    "throw": Action(2.0, _throw, face={"brows": "angry", "mouth": "open"}, reach=True,
                    fly=lambda u: max(0.0, min(1.0, (u - THROW) / (LAND - THROW))),
                    squash=lambda u, t: -0.05 * _peak(u, 0.27, 0.13) + 0.07 * _peak(u, 0.5, 0.1),
                    wrist=lambda u, t: -18 * _peak(u, 0.5, 0.08), tail=lambda u, t: (0.0, 14.0 * _peak(u, 0.5, 0.1))),
    # a catch: a hand up for it, and a give as it lands (film.throw puts the thing in that hand)
    "catch": Action(1.5, _catch, face={"eyes": "wide", "brows": "raised", "mouth": "open"}, reach=True,
                    squash=lambda u, t: -0.07 * _caught(u),
                    ears=lambda u, t, side: (*(2 * (-10 * _caught(u),)), -5 * _caught(u))),
    # a load picked up and held in both arms, for as long as `seconds` says, and put down (Actor.carry)
    "lift": Action(2.4, _lift, face={"brows": "worried", "mouth": "flat"}, gesture="carry", both=True, lift=_lifting,
                   squash=lambda u, t: -0.06 * (_peak(u, 0.07, 0.07) + _peak(u, 0.93, 0.07))),
    # both hands on a load in front of it, for as long as `seconds` says: braced to push it or to haul it
    # (Actor.push, Actor.pull)
    "brace": Action(2.0, lambda u, t, side: {"head.nod_down_up": -5 * _bell(u, 0.15, 0.15),
                                             "left_shoulder.down_up": 6 * _bell(u, 0.15, 0.15),
                                             "right_shoulder.down_up": 6 * _bell(u, 0.15, 0.15)},
                    face={"brows": "angry", "mouth": "flat"}, gesture="carry", both=True),
    # reading: a book held up in both hands, the head down to it, the eyes going along the lines, a page turned
    "read": Action(3.4, _read, face={"mouth": "flat"}, gesture="read", both=True, gaze=_read_gaze,
                   tip=lambda u, t: 38 * _bell(u, 0.15, 0.2), lid=0.25),
    # typing: both hands low in front, tapping in bursts, the eyes on the screen
    "type": Action(2.8, _type, face={"mouth": "flat", "brows": "angry"}, gesture="type", both=True,
                   gaze=lambda u, t: (0.25 * math.sin(2 * math.pi * 0.6 * t), 0.6 * _bell(u, 0.15, 0.2))),
    # on the phone: a hand up beside the head, the head tipped to it, a nod now and then
    "phone": Action(3.2, _phone, face={"mouth": "smile", "look": (-0.4, -0.2)}, gesture="ear"),
    # a handshake: the hand of its side out to another's, and pumped (film.handshake gives both the same point)
    "handshake": Action(2.2, _shake_hands, face={"mouth": "smile"}, reach=True, tail=_wag(10.0, 2.6, 4.0)),
})


VARY = 0.15          # how much an action with a seed of its own varies, when it does not say (its size, as a share)


def _varied(action: Action, dice: random.Random, vary: float, sync: bool = False) -> tuple[Action, float]:
    """This action played a little differently: (the action, what to scale it by). Its size changes by up to
    `vary` either way (0.15 = 15%), its length by up to 0.6 of that, and whatever beats in it (a wave's sweep, a
    laugh's shake, a shiver) starts at another point of its cycle. What it is, and when it starts, do not change."""
    size = 1.0 + vary * dice.uniform(-1.0, 1.0)
    tempo = 1.0 + 0.6 * vary * dice.uniform(-1.0, 1.0)
    if sync:                      # played with someone else: its length is theirs too
        tempo = 1.0
    shift = dice.uniform(0.0, 0.35) * min(1.0, vary / VARY)       # seconds into its beat

    def late(f, sided: bool):
        if f is None:
            return None
        return (lambda u, t, side: f(u, t + shift, side)) if sided else (lambda u, t: f(u, t + shift))

    return replace(action, seconds=action.seconds * tempo, offsets=late(action.offsets, True),
                   seated=late(action.seated, True), ears=late(action.ears, True), squash=late(action.squash, False),
                   tip=late(action.tip, False),
                   gaze=late(action.gaze, False),
                   tail=late(action.tail, False), mix=late(action.mix, False), wrist=late(action.wrist, False)), size


def _action(fig, name: str) -> Action:
    """The action of this name for this figure: a character with paws has its own arm actions."""
    paws = bool(getattr(getattr(fig, "spec", None), "pad", ""))
    if paws and name in PAW_ACTIONS:
        return PAW_ACTIONS[name]
    if name not in ACTIONS:
        only = " (clap, shy and pat need a character with paws: the plush family)" if name in PAW_ACTIONS else ""
        raise ValueError(f"no action {name!r} for {getattr(fig, 'who', 'this figure')}{only}; "
                         f"there are {', '.join(ACTIONS)}")
    return ACTIONS[name]


def stagger(figs: Sequence, name: str, start: float, gap: float = 0.18, **options) -> dict[Any, tuple]:
    """One action for each figure of a group, each `gap` seconds after the one before: {figure id: action}. Add
    `stagger(...)[id(fig)]` to that figure's actions, so the action ripples through the group."""
    return {id(fig): (start + i * gap, name, dict(options)) for i, fig in enumerate(figs)}
