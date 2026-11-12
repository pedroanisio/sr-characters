"""Acting for the 3D cast: how a figure gets from one pose to the next, what it does while it holds one, the small
actions it plays on top, and where it looks.

`location.move(fig, t, pose=...)` alone blends every joint on one curve from key to key: the figure drifts all the
time, arrives nowhere, every part lands on the same frame and the face never changes. `perform()` replaces that for
the plush family (anything built on `mascots3d.MascotFigure`):

    fig = loc.add(mascots3d.figure("bear", "idle", name="bear"))
    motion.perform(loc, fig, [(1.0, "ask"), (2.4, "explain"), (5.2, "idle")],
                   actions=[(3.2, "nod"), (6.0, "giggle")], gaze=[(0.5, other), (4.0, None)])

A beat `(time, pose)` is when the pose is hit; it is then held until the next beat. What perform() adds:

- **holds and snap**: a pose is held, and the change takes about a quarter of a second, not the whole gap;
- **anticipation**: a small wind-up the other way, and a dip in the knees, before a change;
- **overshoot and settle**: every joint is a damped spring, so it passes its pose a little and settles into it;
- **overlap**: the body leads; the chest, arms, head, hands and fingers follow, each a few frames later, and a
  fast arm bends at the elbow as it swings (drag), so it travels on an arc instead of sweeping round stiff;
- **a living hold**: breathing, a slow sway and head drift, so a held pose is never a frozen picture;
- **the face acts**: the expression changes as the move starts (eyes lead the body), with a blink on the change,
  and the figure blinks now and then while it holds;
- **actions** (`ACTIONS`): short motions any character plays over whatever pose it holds: giggle, nod, shake, tilt,
  wave, cheer, bounce, surprise. `(time, name)` or `(time, name, {"side": "left", "scale": 1.5})`. An action moves
  the body and takes the face with it (a giggle shuts the eyes into arcs and smiles), then gives both back;
- **a soft body** (the mascots and the plush family, not Dev): it squashes in the wind-up, stretches as it goes
  and wobbles as it settles; actions squash and stretch it too (a bounce, a surprise), and a wave or a cheer draws
  the arm longer so it reads on stubby arms (`MascotFigure.squash`, `arm_left`, `arm_right`);
- **ears** (the plush family): they trail the head's tilt and nod and swing back past it, draw in when the body
  stretches and spread when it squashes, flick now and then, and react: a surprise pricks them up, a giggle
  shakes them; the ear-only actions are `twitch`, `perk` and `droop`;
- **tails** (the plush family): a tail trails the body's lean, sways slowly on its own, lifts on a stretch and
  wags with the happy actions (giggle, cheer, wave, bounce); `wag` is the tail-only action. Tails and long ears
  bend along their length, the tip more than the root;
- **gaze**: `(time, target)` turns the eyes, then the head, to another figure, a point `(x, y, z)`, or back ahead
  (`None`). The eyes go first and take what the head's turn leaves.

It bakes one pose key per frame (`fps`), so the engine plays exactly this motion. Every value stays inside the
skeleton's joint ranges. `seed` gives each figure its own breathing phase and blink times (default: from its name),
so a group never moves in unison. `energy` scales the anticipation, dip and overshoot (0 = none, 1 = default).
`stagger()` spreads one action over a group so it ripples through it.

The actions themselves are written in `characters.actions` and the lip sync in `characters.speech`; every name
of both is also a name of this module (`motion.ACTIONS`, `motion.lipsync`).

`perform()` is a short list of steps, each a private function below with its own text, in the order they run:
what was asked is read once into a `_Script` (the beats, the actions made ready, turns, lying down, a screen's
power, looks, trips, the lip-sync track); `_key_body` keys the body frame by frame (the springs, then the knees'
dip, the arms' drag, the trips, the actions, the look, the life of a hold, and the figure's own fields: ears,
tail, squash, where it is, what it holds, eyes); `_key_things` keys what it holds and a screen's pictures; and
`_key_face` keys the face. Something new that perform() should do is a new step, or a line in the step it belongs to.
"""

from __future__ import annotations

import math
import random
import zlib
from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping, Optional, Sequence, Union

from srlocations.geometry import Vec3
from srlocations.stock.mannequin import PARAMETERS

from . import actions as _actions
from . import speech as _speech
from .actions import (DOWN, GAITS, LEAPS, LINE_MOUTHS, MORPH, OPEN_MOUTHS, SIDES, UP, VARY, _FACE_KEYS, _action, _bell,
                      _hop, _hop_squash, _varied)
from .doodle import Pose
from .poses import POSES

# Every name of the action library (characters.actions) and of the lip sync (characters.speech) is also a name of
# this module, as it was when they were written here: motion.ACTIONS, motion.Action, motion.lipsync, ...
globals().update({_n: _v for _m in (_actions, _speech) for _n, _v in vars(_m).items() if not _n.startswith("__")})

LEAD = 0.24          # s before a beat that its move starts, so the first peak of the spring lands on the beat
ANTICIPATION = 0.16  # s of wind-up before a move
WIND_UP = 0.12       # share of the coming change that the wind-up goes the other way
DIP = 15.0           # degrees of knee bend before a big change (a full arm gesture)
BLINK = 0.11         # s the eyes stay shut
DRAG, DRAG_MAX = 0.05, 22.0   # elbow bend per deg/s of upper-arm speed, and its most (degrees)
SUB = 4              # spring steps per frame
HEAD_SHARE, HEAD_TURN, HEAD_NOD = 0.6, 28.0, 14.0   # how much of a look the head takes, and its most (degrees)

# joint group -> (lag in s after the body starts, spring frequency in rad/s, damping ratio)
GROUPS = {
    "body": (0.00, 13.0, 0.72),      # hips, spine, legs, feet
    "chest": (0.03, 13.0, 0.66),     # chest, shoulders
    "head": (0.07, 11.0, 0.52),      # neck, head: the last to settle
    "upper_arm": (0.04, 14.0, 0.70),
    "lower_arm": (0.08, 15.0, 0.66),
    "hand": (0.12, 16.0, 0.50),
    "fingers": (0.15, 16.0, 0.60),
    "eye": (0.00, 30.0, 1.00),
}
_OF = {"hips": "body", "spine": "body", "upper_leg": "body", "lower_leg": "body", "foot": "body", "toes": "body",
       "chest": "chest", "shoulder": "chest", "neck": "head", "head": "head", "upper_arm": "upper_arm",
       "lower_arm": "lower_arm", "hand": "hand", "eye": "eye"}


TAIL_LAG, TAIL_MAX = 1.6, 32.0   # how far a tail trails the body's lean, and its most (degrees)
EAR_LAG, EAR_MAX = 1.3, 28.0   # how far ears trail the head's tilt and nod (times the lag), and their most (degrees)
SQUASH = 0.09        # how far a soft body squashes in the wind-up before a big change (then it stretches and settles)


# ----------------------------------------------------------------------------- the figure's own vocabulary
def _group(control: str) -> str:
    joint = control.split(".")[0]
    for side in ("left_", "right_"):
        joint = joint.removeprefix(side)
    return _OF.get(joint, "fingers")


def _controls(fig, pose: Pose) -> dict[str, float]:
    from . import mascots3d
    return mascots3d.controls(fig.who, pose)


def _aimed(kind: str) -> Optional[tuple[float, float]]:
    """(how far to the side, how far up), each 0 to 1, of a gesture "point@yaw,pitch"; None for any other."""
    if not kind.startswith("point@"):
        return None
    yaw, pitch = (float(v) for v in kind[6:].split(","))
    return min(1.0, abs(yaw) / 90.0), max(0.0, min(1.0, pitch / 70.0))


def _between(a: Mapping[str, float], b: Mapping[str, float], share: float) -> dict[str, float]:
    return {n: a.get(n, b.get(n, 0.0)) + share * (b.get(n, a.get(n, 0.0)) - a.get(n, b.get(n, 0.0)))
            for n in set(a) | set(b)}


def _gesture(fig, kind: str) -> dict[str, float]:
    from . import mascots3d
    aim = _aimed(kind)
    if aim is None:
        return mascots3d.gesture(fig.who, kind)
    front, side, up = (mascots3d.gesture(fig.who, k) for k in ("point-front", "point-side", "point-up"))
    return _between(_between(front, side, aim[0]), up, aim[1])   # ahead, round to the side, then up


def _stretch(fig, kind: str) -> dict[str, float]:
    from . import mascots3d
    if not isinstance(fig, mascots3d.MascotFigure):
        return {}
    aim = _aimed(kind)
    if aim is None:
        return mascots3d.gesture_stretch(fig.who, kind)
    front, side, up = (mascots3d.gesture_stretch(fig.who, k) for k in ("point-front", "point-side", "point-up"))
    return _between(_between(front, side, aim[0]), up, aim[1])


def _mirrored(controls: Mapping[str, float]) -> dict[str, float]:
    """An arm gesture on the other arm (the skeleton's arm controls are the same either side)."""
    swap = {"left_": "right_", "right_": "left_"}
    return {next((swap[p] + n[len(p):] for p in swap if n.startswith(p)), n): v for n, v in controls.items()}


def _pose(fig, pose: Union[str, Pose]) -> Pose:
    return POSES[fig.who][pose] if isinstance(pose, str) else pose


def _clamped(name: str, value: float) -> float:
    dof = PARAMETERS.get(name)
    return value if dof is None else max(dof.low, min(dof.high, value))


def _head_point(fig) -> Vec3:
    """Where the figure's head is in the location (its head bone, in the pose it was built with)."""
    return fig.transform.apply(fig.frames()["head"].apply((0, 0, 0)))


def _aim(fig, target) -> tuple[float, float]:
    """(yaw, pitch) in degrees from the figure's head to `target`, in the figure's own frame: + yaw toward its +x,
    + pitch up. `target` is a figure (its head), a point, or None (straight ahead)."""
    if target is None:
        return 0.0, 0.0
    point = _head_point(target) if hasattr(target, "frames") else Vec3.of(target)
    here = tuple(fig.frames()["head"].apply((0, 0, 0)))
    there = tuple(fig.transform.undo(point))
    dx, dy, dz = (there[i] - here[i] for i in range(3))
    return math.degrees(math.atan2(dx, dz)), math.degrees(math.atan2(dy, math.hypot(dx, dz)))


# ----------------------------------------------------------------------------- perform
def perform(loc, fig, beats: Sequence[tuple[float, Union[str, Pose]]] = (), fps: float = 24,
            seed: Optional[int] = None, energy: float = 1.0, life: float = 1.0, blink: bool = True,
            end: Optional[float] = None, actions: Sequence[tuple] = (), gaze: Sequence[tuple] = (),
            mouths: Sequence[tuple] = (), travel: Sequence[tuple] = (), face_fps: Optional[float] = None,
            vary: float = 0.0, turns: Sequence[tuple] = (), powers: Sequence[tuple] = (),
            holds: Sequence[tuple] = (), lays: Sequence[tuple] = ()) -> None:
    """Keys `fig` in `loc` through `beats` [(time, pose name or Pose)], acted (see the module's text), with
    `actions` [(time, name[, options])] played on top and `gaze` [(time, figure | point | None)]. The figure starts
    in the pose it was built with. `end` keeps it alive until then (default: 1 s after the last thing it does).
    `life` scales breathing and sway (0 = a still hold). `mouths` is a lip-sync track [(time, mouth | None[,
    openness])] in the Pose's mouth vocabulary: from each time the mouth is that one, over whatever the face is; None
    gives the mouth back to the face; `openness` (0..1, for open, yell and o) sets how far it is open, else it opens
    and closes on its own over a few frames (see `lipsync()`). `face_fps` keys the face (expression, lids, mouth)
    at its own rate, e.g. 24 while the body is keyed on twos (fps=12) to keep the scene file small."""
    # what was asked, sorted and worked out (the steps of this half are under "perform: what was asked")
    beats = _beats_in_order(fig, beats)
    acts, icons, flights = _actions_ready(fig, actions, seed, vary)
    yaw0, roll0 = float(getattr(fig, "yaw", 0.0)), float(getattr(fig, "roll", 0.0))
    swings = _turns_on_the_spot(turns, yaw0)
    lies = _lying_down(lays)
    levels = _power_levels(powers)
    looks = _looks_taken(fig, gaze, swings, yaw0)
    trips = _trips(fig, travel, swings, yaw0, seed, vary)
    mouths = _mouth_track(mouths)
    seed = _own_seed(fig) if seed is None else seed
    rng = random.Random(seed)
    end = _last_thing(beats, acts, looks, mouths, trips) + 1.0 if end is None else float(end)
    start_face = getattr(fig, "expression", None)
    poses, gestures, longest, names = _poses_and_gestures(fig, beats, acts)
    darts, flicks, phase = _restlessness(fig, life, end, seed, rng)
    script = _Script(fig=fig, fps=fps, energy=energy, life=life, end=end, beats=beats, acts=acts, flights=flights,
                     swings=swings, lies=lies, levels=levels, looks=looks, trips=trips, mouths=mouths, yaw0=yaw0,
                     roll0=roll0, start_face=start_face,
                     seated=start_face is not None and "sit" in start_face.extras, poses=poses,
                     times=[0.0] + [t for t, _p in beats], names=names, gestures=gestures, longest=longest,
                     darts=darts, flicks=flicks, phase=phase)
    # the keys (the steps of each are under "perform: the body", "... what it holds" and "... the face")
    _key_body(loc, script)
    _key_things(loc, fig, holds, icons)
    if start_face is not None:                                # a figure with a face
        faces = _faces(script)
        _key_face(loc, script, faces, _blinks(script, faces, rng, blink), face_fps)


# ----------------------------------------------------------------------------- perform: what was asked
@dataclass
class _Script:
    """What a figure was asked to do, read once from perform()'s arguments before any frame is keyed. The steps
    that key the figure read it; none of them changes it."""
    fig: Any
    fps: float
    energy: float
    life: float
    end: float           # s: when the performance is over
    beats: list          # [(time, Pose)], in order of time
    acts: list           # the actions, ready to play [(time, Action, side, scale)]
    flights: dict        # {a throw's time: where what it holds flies to}
    swings: list         # turns on the spot [(time, seconds, degrees turned before it, degrees it turns)]
    lies: list           # lying down and getting up [(time, seconds, degrees over before it, degrees over after)]
    levels: list         # a robot's screen going off and on [(time, seconds, level before it, level after)]
    looks: list          # [(time, (yaw, pitch) from the figure's head)]
    trips: list          # [(time, seconds, (x, z) gone before it, (dx, dz), style, n, heading, gait, rise)]
    mouths: list         # the lip-sync track [(time, mouth | None, openness | None)]
    yaw0: float          # the way it faces, and how far it leans, as it was built
    roll0: float
    start_face: Any      # the Pose it was built with (None: a figure with no face)
    seated: bool         # whether it starts seated
    poses: list          # the controls of the pose it starts in, then of each beat's
    times: list          # when each of `poses` is hit (0 for the first)
    names: list          # every control that is keyed, in a fixed order
    gestures: dict       # {(gesture, side, both arms): the arm's controls}, for the actions that use one
    longest: dict        # {(gesture, side, both arms): how much longer the arm is drawn so the paw arrives}
    darts: list          # small glances of the eyes [(time, (x, y))]
    flicks: list         # an ear flicking on its own [(time, side)]
    phase: list          # where the breathing, the sway, the head's drift and its bobbing start in their cycles


def _own_seed(fig) -> int:
    """The seed a figure has from its name, so that a group never moves in unison."""
    return zlib.crc32(str(getattr(fig, "name", "") or id(fig)).encode())


def _beats_in_order(fig, beats: Sequence[tuple]) -> list[tuple[float, Pose]]:
    """The beats [(time, Pose)] in order of time, a pose's name looked up in the figure's poses."""
    beats = sorted(((float(t), _pose(fig, p)) for t, p in beats), key=lambda b: b[0])
    if beats and beats[0][0] <= 0:
        raise ValueError("beats come after the start: [(time > 0, pose), ...]")
    return beats


def _actions_ready(fig, actions: Sequence[tuple], seed: Optional[int], vary: float) -> tuple[list, list, dict]:
    """The actions asked for [(time, name[, options])], in order of time, each made ready to play with its options
    (where its arm aims or reaches, how long it goes on, its own variation): [(time, Action, side, scale)]. With
    them, the pictures a robot's screen shows [(time, seconds, icon)] and where what is thrown flies to
    {time: (x, y, z)}."""
    acts, icons, flights = [], [], {}
    for item in sorted(actions, key=lambda a: a[0]):
        t, name, options = (*item, {})[:3]
        action = _action(fig, name)
        if action.aimed:   # the arm goes where "aim" says: (yaw, pitch) from the figure, degrees (ahead and out)
            yaw, pitch = options.get("aim", (35.0, 5.0))
            action = replace(action, gesture=f"point@{abs(yaw):.0f},{pitch:.0f}")
        if "seconds" in options:   # for as long as asked (a dance, a tapping foot: what beats in it goes on)
            action = replace(action, seconds=float(options["seconds"]))
        if action.reach:           # the arm goes to a point: metres out, up and forward of its shoulder
            out_, up_, fwd_ = options.get("reach", (0.1, 0.12, 0.2))
            action = replace(action, gesture=f"reach@{out_:.3f},{up_:.3f},{fwd_:.3f}")
        size = float(options.get("scale", 1.0))
        amount = float(options.get("vary", VARY if "seed" in options else vary))
        if amount > 0:     # never twice the same: by its own seed, or by the figure's and where it comes in the list
            base = options["seed"] if "seed" in options else (seed if seed is not None else _own_seed(fig))
            which = name if "seed" in options else f"{name}:{len(acts)}"
            action, k = _varied(action, random.Random(zlib.crc32(f"{base}:{which}".encode())), amount,
                                sync=bool(options.get("sync")))
            size *= k
        if action.icon:
            icons.append((float(t), action.seconds, str(options.get("icon", "heart"))))
        if action.fly:             # where what it holds flies to: metres to its side, up and ahead of the figure
            flights[float(t)] = tuple(float(v) for v in options.get("fly", (0.0, 0.3, 0.8)))
        acts.append((float(t), action, options.get("side", "right"), size))
    return acts, icons, flights


def _turns_on_the_spot(turns: Sequence[tuple], yaw0: float) -> list[tuple]:
    """turns [(time, yaw in degrees: 0 faces +z, seconds)]: it turns on the spot to face that way, and stays so.
    Gives the swings [(time, seconds, degrees turned before it, degrees it turns: the short way round)]."""
    swings, turned_to = [], 0.0
    for t0, to_yaw, secs in sorted((float(a), float(b), float(c)) for a, b, c in turns):
        delta = (to_yaw - yaw0 - turned_to + 180.0) % 360.0 - 180.0   # the short way round
        swings.append((t0, max(0.1, secs), turned_to, delta))
        turned_to += delta
    return swings


def _facing(swings: Sequence[tuple], t: float) -> float:
    """How far the figure has turned from the way it faced at the start, at t (its turns, not its travels)."""
    out = 0.0
    for t0, secs, was, delta in swings:
        if t >= t0:
            u = min(1.0, (t - t0) / secs)
            out = was + delta * u * u * (3 - 2 * u)
    return out


def _lying_down(lays: Sequence[tuple]) -> list[tuple]:
    """lays [(time, degrees over on its side: 0 upright, seconds)]: it lies down on its side, or gets up, and stays
    so. Gives [(time, seconds, degrees over before it, degrees over after)]."""
    lies, lay_was = [], 0.0
    for t0, to_roll, secs in sorted((float(a), float(b), float(c)) for a, b, c in lays):
        lies.append((t0, max(0.1, secs), lay_was, to_roll))
        lay_was = to_roll
    return lies


def _laid(lies: Sequence[tuple], t: float) -> float:
    """How far over on its side the figure lies at t (degrees)."""
    out = 0.0
    for t0, secs, was, to in lies:
        if t >= t0:
            u = min(1.0, (t - t0) / secs)
            k = u * u if abs(to) > abs(was) else u * u * (3 - 2 * u)     # it goes down faster and faster
            out = was + (to - was) * k
    return out


def _power_levels(powers: Sequence[tuple]) -> list[tuple]:
    """powers [(time, level: 0 off .. 1 on, seconds)]: a robot's screen goes off, or comes on, and stays so. Gives
    [(time, seconds, level before it, level after)]."""
    levels, level_was = [], 1.0
    for t0, to_level, secs in sorted((float(a), float(b), float(c)) for a, b, c in powers):
        levels.append((t0, max(0.1, secs), level_was, to_level))
        level_was = to_level
    return levels


def _powered(levels: Sequence[tuple], t: float) -> float:
    """How far on a robot's screen is at t (0 off .. 1 on)."""
    out = 1.0
    for t0, secs, was, to in levels:
        if t >= t0:
            u = min(1.0, (t - t0) / secs)
            out = was + (to - was) * u * u * (3 - 2 * u)
            if to > was and 0.1 < u < 0.75 and math.sin(2 * math.pi * 11.0 * t) > 0.2:
                out *= 0.35                                     # coming on, it stutters
    return out


def _looks_taken(fig, gaze: Sequence[tuple], swings: Sequence[tuple], yaw0: float) -> list[tuple]:
    """gaze [(time, figure | point | None)] as [(time, (yaw, pitch))] from the figure's head. A look is taken from
    the way the figure faces when it looks, and again when it has turned."""
    def aim_at(t: float, target) -> tuple[float, float]:
        way = _facing(swings, t)
        return _aim(fig.posed({"yaw": yaw0 + way}) if way else fig, target)

    wanted = sorted(((float(t), target) for t, target in gaze), key=lambda g: g[0])
    looks = [(t, aim_at(t, target)) for t, target in wanted]
    for t0, secs, _was, _delta in swings:
        held = next((target for t, target in reversed(wanted) if t <= t0 + secs), None)
        if held is not None:
            looks.append((t0 + secs, aim_at(t0 + secs, held)))
    looks.sort(key=lambda g: g[0])
    return looks


def _trips(fig, travel: Sequence[tuple], swings: Sequence[tuple], yaw0: float, seed: Optional[int],
           vary: float) -> list[tuple]:
    """travel [(time, (x, z) in the location[, {"style": "waddle" | "hops", "seconds": s, "turn": 0..1}])]: the figure
    goes there, rocking from foot to foot or in small hops, its body turned part of the way toward where it goes.
    Gives the trips [(time, seconds, (x, z) gone before it, (dx, dz), style, n, heading, gait, rise)]: `n` its
    hops (or the side a cartwheel goes over to), `heading` how far it turns toward where it goes, `gait` where its
    step starts in its cycle and how big it is, `rise` how far up a step takes it."""
    trips, gone = [], [0.0, 0.0]
    base = tuple(Vec3.of(fig.at))
    for item in sorted(travel, key=lambda a: a[0]):
        t0, to, options = (*item, {})[:3]
        style = options.get("style", "waddle")
        dx, dz = to[0] - base[0] - gone[0], to[-1] - base[2] - gone[1]
        dist = math.hypot(dx, dz)
        n = max(1, math.ceil(dist / 0.16))
        pace = GAITS[style].speed if style in GAITS else 0.38
        own_time = {"leap": 1.1, "cartwheel": 1.5, "climb-step": 1.5}.get(style)
        seconds = float(options.get("seconds", own_time or (n * 0.42 if style == "hops" else max(0.5, dist / pace))))
        gait = (0.0, 1.0)          # where its step starts in its cycle, and how big it is: its own with a seed
        amount = float(options.get("vary", VARY if "seed" in options else vary))
        if amount > 0:
            own = options["seed"] if "seed" in options else (seed if seed is not None else _own_seed(fig))
            dice = random.Random(zlib.crc32(f"{own}:go:{len(trips)}".encode()))
            gait = (dice.uniform(0.0, 2 * math.pi), 1.0 + amount * dice.uniform(-1.0, 1.0))
        if trips and float(t0) < trips[-1][0] + trips[-1][1] - 1e-6:
            raise ValueError(f"it sets off at {float(t0):g} s before it has arrived from the trip of "
                             f"{trips[-1][0]:g} s, which ends at {trips[-1][0] + trips[-1][1]:.2f} s")
        # how far round from the way it faces when it sets off (its turns before then count)
        heading = (math.degrees(math.atan2(dx, dz)) - yaw0 - _facing(swings, float(t0)) + 180.0) % 360.0 - 180.0
        if style == "cartwheel" or (style in GAITS and GAITS[style].back):
            heading = 0.0                                      # it does not turn to where it goes
        if style == "cartwheel":                               # over toward the side it goes to, as it faces then
            facing_now = math.radians(yaw0 + _facing(swings, float(t0)))
            n = 1 if dx * math.cos(facing_now) - dz * math.sin(facing_now) >= 0 else -1
        trips.append((float(t0), seconds, tuple(gone), (dx, dz), style, n,
                      heading * float(options.get("turn", 0.7)), gait, float(options.get("rise", 0.0))))
        gone = [gone[0] + dx, gone[1] + dz]
    return trips


def _mouth_track(mouths: Sequence[tuple]) -> list[tuple]:
    """The lip-sync track in order of time, each item (time, mouth | None, openness | None)."""
    return sorted(((float(m[0]), m[1], None if len(m) < 3 or m[2] is None else float(m[2])) for m in mouths),
                  key=lambda s: s[0])


def _last_thing(beats: Sequence[tuple], acts: Sequence[tuple], looks: Sequence[tuple], mouths: Sequence[tuple],
                trips: Sequence[tuple]) -> float:
    """When the last thing the figure was asked to do is over (0 if it was asked nothing)."""
    return max([t for t, _p in beats] + [t + a.seconds for t, a, _s, _k in acts] + [t for t, _g in looks]
               + [m[0] for m in mouths] + [trip[0] + trip[1] for trip in trips] + [0.0])


def _poses_and_gestures(fig, beats: Sequence[tuple], acts: Sequence[tuple]) -> tuple[list, dict, dict, list]:
    """The controls of the pose the figure starts in and of each beat's pose; the arm gestures its actions use
    {(gesture, side, both arms): controls}, each solved once; how much longer the arm is drawn for each; and the
    name of every control these key, in a fixed order."""
    first = dict(fig.values())
    poses = [first] + [_controls(fig, p) for _t, p in beats]
    gestures, longest = {}, {}
    for _t, action, side, _k in acts:
        for kind in (action.gesture, action.gesture2):
            if not kind or (kind, side, action.both) in gestures:
                continue
            g = _gesture(fig, kind)                               # solved for the right arm (or both)
            arm = {n: v for n, v in g.items() if n.startswith("right_")} if not action.both else dict(g)
            gestures[(kind, side, action.both)] = _mirrored(arm) if side == "left" and not action.both else arm
            # how much longer the arm is drawn so the paw arrives (stubby arms; 1 = it reaches)
            longest[(kind, side, action.both)] = max(_stretch(fig, kind).values(), default=1.0)
    names = sorted({n for pose in poses for n in pose} | {n for g in gestures.values() for n in g})
    return poses, gestures, longest, names


def _restlessness(fig, life: float, end: float, seed: int, rng: random.Random) -> tuple[list, list, list]:
    """What a figure does on its own while it holds a pose. `darts`: small darts of the eyes while nothing else
    moves them, a glance aside, then back [(time, (x, y))] (a separate random stream, so they change nothing else
    that is drawn from the seed). `flicks`: now and then one ear flicks on its own [(time, side)]. `phase`: where
    its breathing, sway, head drift and bobbing start in their cycles. No darts and no flicks with life=0."""
    darts, dice, at = [], random.Random(seed + 7), 0.0
    while life and at < end:
        at += dice.uniform(0.9, 2.8)
        aside = (dice.uniform(-0.32, 0.32), dice.uniform(-0.16, 0.2))
        darts += [(at, aside), (at + dice.uniform(0.25, 0.7), (0.0, 0.0))]
    eared = hasattr(fig, "ear_back")
    flicks = []
    at = rng.uniform(1.0, 3.5)
    while eared and life and at < end:
        flicks.append((at, rng.choice(SIDES)))
        at += rng.uniform(2.5, 6.0)
    phase = [rng.uniform(0, 2 * math.pi) for _ in range(4)]
    return darts, flicks, phase


def _sitting(script: _Script, t: float) -> bool:
    """Whether the figure is seated at t: as the pose it holds then says (it may sit down and stand up)."""
    now = script.seated
    for at, p in script.beats:
        if t >= at:
            now = "sit" in _pose(script.fig, p).extras
    return now


# ----------------------------------------------------------------------------- perform: where the springs go
def _move_starts(script: _Script, i: int, lag: float) -> float:
    """When the move into beat i starts, for a part that follows the body by `lag` seconds."""
    return max(script.times[i - 1] + 0.02, script.times[i] - LEAD) + lag


def _winds_up(script: _Script, i: int) -> bool:
    """Whether there is room for a wind-up before the move into beat i."""
    return script.energy > 0 and script.times[i] - script.times[i - 1] >= 0.6


def _target(script: _Script, name: str, lag: float, t: float) -> float:
    """Where a control's spring is headed at t: a step per beat, with a wind-up the other way before it."""
    poses = script.poses
    value = poses[0].get(name, 0.0)
    for i in range(1, len(poses)):
        s, nxt = _move_starts(script, i, lag), poses[i].get(name, 0.0)
        if t >= s:
            value = nxt
        elif _winds_up(script, i) and t >= s - ANTICIPATION:
            return value - WIND_UP * script.energy * (nxt - value)
        else:
            break
    return value


def _arm_travel(script: _Script, i: int) -> float:
    """How big the change into beat i is, 0 to 1: by how far the arms travel (1 = a full arm gesture)."""
    arms = [abs(script.poses[i].get(n, 0.0) - script.poses[i - 1].get(n, 0.0)) for n in script.names if "_arm." in n]
    return min(1.0, max(arms, default=0.0) / 70.0)


def _dip_target(script: _Script, t: float) -> float:
    """The dip: knees bend before a change, in proportion to how far the arms travel (not for a seated figure)."""
    if _sitting(script, t):
        return 0.0
    for i in range(1, len(script.poses)):
        s = _move_starts(script, i, 0.0)
        if _winds_up(script, i) and s - ANTICIPATION <= t < s + 0.05:
            return DIP * script.energy * _arm_travel(script, i)
    return 0.0


def _head_goal(script: _Script, t: float) -> tuple[float, float]:
    """Gaze: the (turn, nod) the head takes of the look it holds at t, a share of it and a little after the eyes."""
    yaw = pitch = 0.0
    for at, (y, p) in script.looks:
        if t >= at + 0.1:
            yaw, pitch = y, p
    return (max(-HEAD_TURN, min(HEAD_TURN, HEAD_SHARE * yaw)), max(-HEAD_NOD, min(HEAD_NOD, HEAD_SHARE * pitch)))


def _jelly_target(script: _Script, t: float) -> float:
    """Squashed in the wind-up, stretched as the move goes, then left to settle (the spring wobbles it)."""
    for i in range(1, len(script.poses)):
        s0 = _move_starts(script, i, 0.0)
        if _winds_up(script, i) and s0 - ANTICIPATION <= t < s0:
            return -SQUASH * script.energy * max(0.35, _arm_travel(script, i))
        if script.energy > 0 and s0 <= t < s0 + 0.12:
            return 0.8 * SQUASH * script.energy * max(0.35, _arm_travel(script, i))
    return 0.0


# ----------------------------------------------------------------------------- perform: the body
class _Springs:
    """What carries from one frame of the body to the next: a damped spring for every control, for the knees' dip,
    for the head's turn and nod to a look and for the soft body's squash, and the loose followers that the ears
    and the tail trail behind."""

    def __init__(self, script: _Script) -> None:
        self.groups = {n: GROUPS[_group(n)] for n in script.names}
        self.x = {n: script.poses[0].get(n, 0.0) for n in script.names}   # each control, and its speed
        self.v = dict.fromkeys(script.names, 0.0)
        self.dip, self.dip_v = 0.0, 0.0
        self.turn, self.turn_v, self.nod, self.nod_v = 0.0, 0.0, 0.0, 0.0
        self.jelly, self.jelly_v = 0.0, 0.0
        self.ears = None                                          # [tilt follower, its speed, nod follower, its speed]
        self.tail = None                                          # [body lean follower, its speed]
        self.air_was = 0.0                                        # how high it hopped or jumped a frame ago


class _Moment:
    """The figure at one frame, as the steps put it together one after the other: its pose (control -> degrees),
    and what its other fields are keyed from."""

    def __init__(self, t: float, pose: dict[str, float], squash: float) -> None:
        self.t, self.pose = t, pose
        self.squash = squash                                      # the soft body: squashed (-) or stretched (+)
        self.arms = {"left": 1.0, "right": 1.0}                   # how much longer each arm is drawn
        self.wrists = {"left": 0.0, "right": 0.0}                 # degrees each paw flaps away from the body
        self.hop = 0.0                                            # metres off the ground
        self.step = [0.0, 0.0]                                    # metres from where it stood (x, z)
        self.turned = 0.0                                         # degrees round from the way it was built facing
        self.rock = 0.0                                           # degrees over on its side
        self.climbed = 0.0                                        # metres up on a step
        self.feet = [0.0, 0.0, 0.0, 0.0]                          # left up, right up, left ahead, right ahead (m)
        self.tipped, self.popped = 0.0, 0.0                       # what it holds: tipped to the face, a bottle's pop
        self.flown, self.flying = 0.0, (0.0, 0.0, 0.0)            # ... thrown, and where to
        self.lifted = 0.0                                         # a load in front of it, how far up
        self.level = 1.0                                          # how far on a robot's screen is

    def add(self, name: str, amount: float) -> None:
        """Adds degrees to a control of the pose."""
        self.pose[name] = self.pose.get(name, 0.0) + amount


def _key_body(loc, script: _Script) -> None:
    """Keys the body, one key a frame: the springs go a frame on toward the beats' poses, and over what they give
    come, in this order, the knees' dip, the arms' drag, the trips, a screen that is off, turning and lying down,
    the actions, the head's look and the life of a hold. What that makes is keyed with the figure's own fields."""
    springs = _Springs(script)
    for frame in range(1, int(round(script.end * script.fps)) + 1):
        _step_springs(script, springs, frame)
        now = _Moment(frame / script.fps, dict(springs.x), springs.jelly)
        _bend_knees(now, springs.dip)
        _drag_elbows(now, script, springs)
        _travel(now, script.trips)
        _hang_when_off(now, script)
        _turn_and_lie(now, script)
        _play_actions(now, script)
        now.add("head.turn_left_right", springs.turn)
        now.add("head.nod_down_up", springs.nod)
        _live(now, script)
        loc.move(script.fig, now.t, ease="linear", **_keys_of(now, script, springs))


def _step_springs(script: _Script, springs: _Springs, frame: int) -> None:
    """Takes the springs from the frame before to `frame`, in SUB steps: one per control toward its target, the
    knees' dip, the head's turn and nod toward the look, the soft body's squash."""
    dt = 1.0 / (script.fps * SUB)
    x, v = springs.x, springs.v
    for step in range(SUB):
        t = (frame - 1) / script.fps + (step + 1) * dt
        for n in script.names:
            lag, w, z = springs.groups[n]
            z = z if script.energy > 0 else 1.0
            a = w * w * (_target(script, n, lag, t) - x[n]) - 2 * z * w * v[n]
            v[n] += a * dt
            x[n] += v[n] * dt
        a = 12.0 ** 2 * (_dip_target(script, t) - springs.dip) - 2 * 0.55 * 12.0 * springs.dip_v
        springs.dip_v += a * dt
        springs.dip += springs.dip_v * dt
        goal = _head_goal(script, t)
        springs.turn_v += (9.0 ** 2 * (goal[0] - springs.turn) - 2 * 0.75 * 9.0 * springs.turn_v) * dt
        springs.turn += springs.turn_v * dt
        springs.nod_v += (9.0 ** 2 * (goal[1] - springs.nod) - 2 * 0.75 * 9.0 * springs.nod_v) * dt
        springs.nod += springs.nod_v * dt
        springs.jelly_v += (15.0 ** 2 * (_jelly_target(script, t) - springs.jelly)
                            - 2 * 0.38 * 15.0 * springs.jelly_v) * dt
        springs.jelly += springs.jelly_v * dt


def _bend_knees(now: _Moment, dip: float) -> None:
    """The dip before a change. Knees: thigh forward, shin back, foot kept flat."""
    bend = max(0.0, dip)
    for side in SIDES:
        now.add(f"{side}_upper_leg.front_back", -bend)
        now.add(f"{side}_lower_leg.stretch", -2 * bend)
        now.add(f"{side}_foot.up_down", -bend)
    now.add("spine.front_back", -0.25 * bend)                 # and the back gives a little with them


def _drag_elbows(now: _Moment, script: _Script, springs: _Springs) -> None:
    """Drag: a fast arm breaks at the elbow, then straightens."""
    for side in SIDES:
        speed = max((abs(springs.v[n]) for n in script.names if n.startswith(f"{side}_upper_arm.")), default=0.0)
        now.add(f"{side}_lower_arm.stretch", -min(DRAG_MAX, DRAG * speed) * (script.energy > 0))


def _travel(now: _Moment, trips: Sequence[tuple]) -> None:
    """Off the spot: where the trips have taken the figure by now, and, on the one it is on, how it goes: a
    function for each way of going moves the body and says how far along the trip it has got."""
    for t0, seconds, start, (dx, dz), style, n, heading, (stride0, stride), rise in trips:
        u = (now.t - t0) / seconds
        if u <= 0:
            continue
        if u >= 1:
            now.step = [start[0] + dx, start[1] + dz]
            now.climbed += rise                               # up on a step, it stays up
            continue
        now.turned = heading * _bell(u, 0.18, 0.18)
        aside = (0.0, 0.0)
        if style == "leap":
            go = _go_leap(now, u, math.hypot(dx, dz))
        elif style == "cartwheel":
            go = _go_cartwheel(now, u, n)
        elif style == "climb-step":
            go = _go_climb_step(now, u, rise)
        elif style == "hops":
            go = _go_hops(now, u, n)
        elif style in GAITS:
            go, aside = _go_on_two_legs(now, GAITS[style], u, now.t - t0, stride0, stride, dx, dz)
        else:
            go = _go_waddle(now, u, now.t - t0, stride0, stride)
        now.step = [start[0] + dx * go + aside[0], start[1] + dz * go + aside[1]]


def _go_leap(now: _Moment, u: float, far: float) -> float:
    """One long jump: down, off, over and a deep landing."""
    air = max(0.0, min(1.0, (u - UP) / (DOWN - UP)))
    go = air * air * (3 - 2 * air)
    now.hop += min(0.34, 0.14 + 0.3 * far) * 4 * air * (1 - air)
    now.squash += _hop_squash(0.16)(u, now.t)
    for control, amount in _hop(34.0)(u, now.t, "right").items():
        now.add(control, amount)
    for s in SIDES:                               # the arms thrown up, the legs tucked while it is over
        now.add(f"{s}_upper_arm.down_up", 60 * math.sin(math.pi * air))
        now.add(f"{s}_lower_leg.stretch", -30 * math.sin(math.pi * air))
    now.add("spine.front_back", -8 * math.sin(math.pi * air))
    return go


def _go_cartwheel(now: _Moment, u: float, n: int) -> float:
    """A cartwheel: over on to its hands and round, to its side (`n`: +1 or -1, the side it goes over to)."""
    go = u * u * (3 - 2 * u)
    e = _bell(u, 0.15, 0.15)
    now.rock = -n * 360.0 * go
    now.squash += 0.05 * e - 0.1 * (math.exp(-((u - 0.06) / 0.05) ** 2) + math.exp(-((u - 0.95) / 0.05) ** 2))
    for s in SIDES:                               # a star: the arms up and the legs apart
        now.add(f"{s}_upper_arm.down_up", 105 * e)
        now.add(f"{s}_lower_arm.stretch", 8 * e)
        now.add(f"{s}_upper_leg.in_out", 24 * e)
    return go


def _go_climb_step(now: _Moment, u: float, rise: float) -> float:
    """A step up (or down) of `rise` metres: a knee up, the weight over it, and up."""
    knee, up = _bell(u, 0.2, 0.45), max(0.0, min(1.0, (u - 0.3) / 0.45))
    up = up * up * (3 - 2 * up)
    go = up
    now.climbed += rise * up
    follow = math.exp(-((u - 0.72) / 0.14) ** 2)   # the other leg comes up after it
    now.add("right_upper_leg.front_back", -62 * knee * (1 - up))
    now.add("right_lower_leg.stretch", -70 * knee * (1 - up))
    now.add("left_upper_leg.front_back", -40 * follow)
    now.add("left_lower_leg.stretch", -55 * follow)
    now.add("spine.front_back", -12 * _bell(u, 0.25, 0.3))
    now.add("head.nod_down_up", -8 * knee * (1 - up))
    for s, k in (("left", 1), ("right", -1)):
        now.add(f"{s}_upper_arm.front_back", 14 * k * _bell(u, 0.25, 0.3))
        now.add(f"{s}_upper_arm.down_up", 18 * _bell(u, 0.25, 0.3))
    now.squash += 0.05 * math.sin(math.pi * up) - 0.07 * math.exp(-((u - 0.86) / 0.07) ** 2)
    return go


def _go_hops(now: _Moment, u: float, n: int) -> float:
    """Small hops, `n` of them: it moves while it is in the air."""
    done, part = divmod(u * n, 1.0)
    air = max(0.0, min(1.0, (part - UP) / (DOWN - UP)))
    go = (done + air * air * (3 - 2 * air)) / n
    now.hop += 0.055 * 4 * air * (1 - air)
    now.squash += _hop_squash(0.09)(part, now.t)
    for control, amount in _hop(15.0)(part, now.t, "right").items():
        now.add(control, amount)
    return go


def _go_on_two_legs(now: _Moment, g, u: float, since: float, stride0: float, stride: float, dx: float,
                    dz: float) -> tuple[float, tuple[float, float]]:
    """On two legs, in the Gait `g`: a walk, a run, a sneak, a skip. `since` is the time since it set off;
    `stride0` and `stride` are where its step starts in its cycle and how big it is. Gives how far along the trip
    it is and how far it weaves to the side of its way (x, z)."""
    go, e = u * u * (3 - 2 * u), _bell(u, 0.12, 0.12) * stride
    aside = (0.0, 0.0)
    if g.skid:
        go, e = _skid(now, g, u, e)
    if g.stumble:
        go = _stumble(now, g, u, go)
    beat = 2 * math.pi * g.rate * since + stride0
    swing = math.sin(beat)
    now.rock = g.rock * e * swing
    now.hop += g.lift * e * abs(math.cos(beat))
    now.squash -= g.squash * e * abs(swing)
    for s, k in (("left", 1), ("right", -1)):
        now.add(f"{s}_upper_leg.front_back", e * (g.thigh * k * swing - g.crouch))
        now.add(f"{s}_lower_leg.stretch", -e * (g.knee * max(0.0, k * math.sin(beat + 0.9)) + 2 * g.crouch))
        now.add(f"{s}_foot.up_down", -e * g.crouch)
        now.add(f"{s}_upper_arm.front_back", e * (g.hands - g.arm * k * swing))
        now.add(f"{s}_lower_arm.stretch", -e * g.elbow)
        now.add(f"{s}_shoulder.down_up", e * g.shoulders)
        now.add(f"{s}_upper_arm.down_up", e * g.out)
        now.add(f"{s}_foot.up_down", -e * g.toes)
    if g.sway:                                    # lolling, slower than the steps
        loll = math.sin(0.43 * beat + 1.0)
        now.add("spine.left_right", g.sway * e * loll)
        now.add("head.tilt_left_right", 1.2 * g.sway * e * math.sin(0.43 * beat + 0.3))
        now.add("head.nod_down_up", -0.8 * g.sway * e)
    if g.weave:
        far = math.hypot(dx, dz) or 1.0
        off = g.weave * e * math.sin(0.5 * beat)
        aside = (dz / far * off, -dx / far * off)
    now.add("spine.front_back", -g.lean * e)
    now.add("chest.front_back", -0.5 * g.lean * e)
    now.add("spine.twist_left_right", g.twist * e * swing)
    now.add("spine.left_right", -1.5 * e * swing)
    now.add("head.turn_left_right", g.scan * e * math.sin(0.5 * beat))
    return go, aside


def _skid(now: _Moment, g, u: float, e: float) -> tuple[float, float]:
    """The end of the trip is a skid: no more steps. Gives how far along the trip it is and what is left of the
    size of its steps."""
    into = max(0.0, min(1.0, (u - (1.0 - g.skid)) / 0.12))
    into = into * into * (3 - 2 * into)
    out_of = max(0.0, min(1.0, (u - 0.9) / 0.1))
    skid, e = into * (1.0 - out_of * out_of * (3 - 2 * out_of)), e * (1.0 - into)
    go = 1.0 - (1.0 - u) ** 2.2               # it comes in fast and slows all the way
    now.add("spine.front_back", 17 * skid)
    now.add("left_upper_leg.front_back", -30 * skid)
    now.add("right_upper_leg.front_back", -16 * skid)
    now.add("left_lower_leg.stretch", 6 * skid)
    now.add("head.nod_down_up", -8 * skid)
    for s in SIDES:
        now.add(f"{s}_upper_arm.down_up", 62 * skid)
        now.add(f"{s}_foot.up_down", 18 * skid)
    now.squash -= 0.06 * skid
    now.turned += 28 * skid
    return go, e


def _stumble(now: _Moment, g, u: float, go: float) -> float:
    """A foot catches: forward, arms out, and saved. Gives how far along the trip it is, held up a moment."""
    caught = math.exp(-((u - g.stumble) / 0.07) ** 2)
    now.add("spine.front_back", -26 * caught)
    now.add("chest.front_back", -12 * caught)
    now.add("head.nod_down_up", 14 * caught)
    now.add("right_upper_leg.front_back", 26 * caught)
    now.add("right_lower_leg.stretch", -40 * caught)
    for s in SIDES:
        now.add(f"{s}_upper_arm.front_back", 60 * caught)
        now.add(f"{s}_upper_arm.down_up", 40 * caught)
    now.hop += 0.025 * caught
    now.squash += 0.05 * caught - 0.07 * math.exp(-((u - g.stumble - 0.12) / 0.06) ** 2)
    return max(0.0, min(1.0, go + 0.05 * (caught - math.exp(-((u - g.stumble - 0.16) / 0.1) ** 2))))


def _go_waddle(now: _Moment, u: float, since: float, stride0: float, stride: float) -> float:
    """A waddle: it rocks from foot to foot as it goes."""
    go, e, beat = (u * u * (3 - 2 * u), _bell(u, 0.12, 0.12) * stride,
                   2 * math.pi * 1.6 * since + stride0)
    now.rock = 7.0 * e * math.sin(beat)
    swing = math.sin(beat)                        # the foot on the lifted side leaves the ground and swings on
    now.feet[0] += 0.03 * e * max(0.0, swing)
    now.feet[1] += 0.03 * e * max(0.0, -swing)
    now.feet[2] += 0.02 * e * math.cos(beat) * (swing > 0)
    now.feet[3] -= 0.02 * e * math.cos(beat) * (swing < 0)
    now.hop += 0.012 * e * abs(math.cos(beat))
    now.squash -= 0.025 * e * abs(math.sin(beat))
    for s, k in (("left", 1), ("right", -1)):
        now.add(f"{s}_upper_leg.front_back", 13 * e * k * math.sin(beat))
        now.add(f"{s}_upper_arm.front_back", -9 * e * k * math.sin(beat))
    now.add("spine.left_right", -2.5 * e * math.sin(beat))
    now.add("head.tilt_left_right", -3.0 * e * math.sin(beat))
    return go


def _hang_when_off(now: _Moment, script: _Script) -> None:
    """A robot's screen as its powers have it at this frame; a robot that is off hangs its head and shoulders."""
    now.level = _powered(script.levels, now.t)
    if now.level < 1.0:
        down = 1.0 - now.level
        now.add("head.nod_down_up", -14 * down)
        now.add("neck.nod_down_up", -5 * down)
        now.add("spine.front_back", -5 * down)
        for s in SIDES:
            now.add(f"{s}_shoulder.down_up", -6 * down)
        now.squash -= 0.04 * down


def _turn_and_lie(now: _Moment, script: _Script) -> None:
    """Turns on the spot and lying down: where they have left the figure, and what the body does as it goes."""
    t = now.t
    now.turned += _facing(script.swings, t)                   # the way it has turned to face, for good
    now.rock += _laid(script.lies, t)                         # how far over it lies, for good
    for t0, secs, was, to in script.lies:                     # it gives as it lands, and as it pushes itself up
        now.squash -= 0.1 * math.exp(-((t - t0 - (secs if abs(to) > abs(was) else 0.25 * secs)) / 0.09) ** 2)
    for t0, secs, _was, delta in script.swings:               # ... with a small lift and a give as it comes round
        if t0 < t < t0 + secs:
            way = math.sin(math.pi * (t - t0) / secs) * min(1.0, abs(delta) / 90.0)
            now.hop += 0.015 * way
            now.squash += 0.03 * way


def _play_actions(now: _Moment, script: _Script) -> None:
    """Actions, over the pose: each one that is playing at this frame moves the whole figure and what it holds,
    then its arms, then adds its offsets to the pose (its seated ones, if it has them and the figure sits)."""
    t = now.t
    for at, action, side, scale in script.acts:
        if action.spin and t >= at + action.seconds:      # a spin that is over leaves the figure where it got to
            now.turned += (1 if side == "right" else -1) * action.spin(1.0)
        u = (t - at) / action.seconds
        if not 0 < u < 1:
            continue
        _act_whole(now, script, at, action, side, scale, u)
        _act_arms(now, script, at, action, side, scale, u)
        move = action.seated if _sitting(script, t) and action.seated else action.offsets
        for n, amount in move(u, t - at, side).items():
            now.add(n, scale * amount)


def _act_whole(now: _Moment, script: _Script, at: float, action, side: str, scale: float, u: float) -> None:
    """What an action that is playing does to the whole figure (a spin, a faint, a hop, squash, the feet), to a
    robot's screen and to what the figure holds (tipped, popped, thrown, lifted)."""
    t = now.t
    if action.spin:
        now.turned += (1 if side == "right" else -1) * action.spin(u)
    if action.topple and not _sitting(script, t):         # the whole figure goes over toward its side
        now.rock += (-1 if side == "right" else 1) * action.topple(u)
    if action.flicker:
        now.level *= action.flicker(u, t - at)
    if action.tip:
        now.tipped += scale * action.tip(u, t - at)
    if action.pop:
        now.popped = max(now.popped, action.pop(u))
    if action.fly and action.fly(u) > 0.0:
        now.flown, now.flying = action.fly(u), script.flights.get(at, (0.0, 0.3, 0.8))
    if action.lift:
        now.lifted = max(now.lifted, action.lift(u))
    if action.squash:
        now.squash += scale * action.squash(u, t - at)
    if action.air and not _sitting(script, t):
        now.hop += scale * action.air(u)
    if action.feet:
        for i, value in enumerate(action.feet(u, t - at, _sitting(script, t))):
            now.feet[i] += scale * value


def _act_arms(now: _Moment, script: _Script, at: float, action, side: str, scale: float, u: float) -> None:
    """What an action that is playing does with the arms: the arm (or both) goes to the action's gesture and comes
    back, drawn longer while it is there so the paw arrives, and the wrist flaps."""
    t = now.t
    pose, arms = now.pose, now.arms
    if action.arm != 1.0:
        for arm_side in (SIDES if action.both else (side,)):
            arms[arm_side] = max(arms[arm_side], 1.0 + (action.arm - 1.0) * _bell(u, 0.22, 0.25))
    if action.gesture:                                # the arm goes to the gesture and comes back
        k = _bell(u, 0.22, 0.25)
        key = (action.gesture, side, action.both)
        g, longer = script.gestures[key], script.longest[key]
        if action.gesture2:                           # ... swinging to a second gesture and back
            key2, share = (action.gesture2, side, action.both), max(0.0, min(1.0, action.mix(u, t - at)))
            g2 = script.gestures[key2]
            g = {n: g.get(n, g2.get(n, 0.0)) + share * (g2.get(n, g.get(n, 0.0)) - g.get(n, g2.get(n, 0.0)))
                 for n in set(g) | set(g2)}
            longer += share * (script.longest[key2] - longer)
        for n, value in g.items():
            pose[n] = pose.get(n, 0.0) + k * (value - pose.get(n, 0.0))
        for arm_side in (SIDES if action.both else (side,)):
            # the arm grows late and shrinks early, so it is not long while it swings out past the side
            arms[arm_side] = max(arms[arm_side], 1.0 + (longer - 1.0) * k ** 3)
    if action.wrist:
        for arm_side in (SIDES if action.both else (side,)):
            now.wrists[arm_side] += scale * action.wrist(u, t - at)


def _live(now: _Moment, script: _Script) -> None:
    """A living hold: breathing, a slow sway and head drift, the weight going from leg to leg (seated: the feet
    swaying in turn). Scaled by `life`; nothing with life=0."""
    life, phase, t = script.life, script.phase, now.t
    if not life:
        return
    breath = math.sin(2 * math.pi * t / 3.6 + phase[0])
    late = math.sin(2 * math.pi * t / 3.6 + phase[0] - 0.7)
    sway = math.sin(2 * math.pi * t / 7.3 + phase[1])
    drift = math.sin(2 * math.pi * t / 5.1 + phase[2])
    bobbing = math.sin(2 * math.pi * t / 6.4 + phase[3])
    now.add("chest.front_back", 1.3 * life * breath)
    now.add("spine.front_back", -0.6 * life * breath)
    now.add("spine.left_right", 0.9 * life * sway)
    now.add("head.tilt_left_right", -0.7 * life * sway)   # the head stays level over a swaying body
    now.add("head.turn_left_right", 1.2 * life * drift)
    if _sitting(script, t):                               # seated legs are never still: the feet sway in turn
        for s, k in (("left", 1), ("right", -1)):
            now.add(f"{s}_upper_leg.front_back", 2.2 * life * k * math.sin(2 * math.pi * t / 2.9 + phase[2]))
            now.add(f"{s}_foot.up_down", 5.0 * life * k * math.sin(2 * math.pi * t / 2.9 + phase[2] - 0.6))
    else:                                                 # standing, the weight settles on one leg, then the other
        lean = math.sin(2 * math.pi * t / 6.1 + phase[3])
        lean = math.copysign(abs(lean) ** 0.45, lean)     # it stays on a leg a while, and crosses quickly
        now.add("spine.left_right", 1.8 * life * lean)
        now.add("chest.left_right", -1.2 * life * lean)
        for s, k in (("left", 1), ("right", -1)):
            free = life * max(0.0, k * lean)              # the free leg's knee gives
            now.add(f"{s}_upper_leg.front_back", -5 * free)
            now.add(f"{s}_lower_leg.stretch", -9 * free)
    now.add("head.nod_down_up", 0.8 * life * bobbing)
    for side in SIDES:
        now.add(f"{side}_shoulder.down_up", 1.2 * life * breath)
        now.add(f"{side}_upper_arm.front_back", 1.0 * life * late)


def _keys_of(now: _Moment, script: _Script, springs: _Springs) -> dict[str, Any]:
    """What is keyed at this frame: the pose, every joint inside its range, and those of the figure's own fields
    that it has, in this order: ears, tail, soft body, off the spot, what it holds, eyes."""
    fig = script.fig
    keyed = {"pose": {n: _clamped(n, value) for n, value in now.pose.items()}}
    if hasattr(fig, "ear_back"):                              # ears that trail the head and react
        keyed.update(_ear_keys(now, script, springs))
    if hasattr(fig, "tail_sway"):
        keyed.update(_tail_keys(now, script, springs))
    if hasattr(fig, "squash"):                                # a soft body (mascots, plush): squash and stretch
        if script.life:
            now.squash += 0.012 * script.life * math.sin(2 * math.pi * now.t / 3.6 + script.phase[0])   # it breathes
        keyed.update(squash=max(-0.22, min(0.22, now.squash)), arm_left=now.arms["left"], arm_right=now.arms["right"])
    in_air = now.hop                                          # off the ground by its own doing: a hop, a jump
    keyed.update(_place_keys(now, script))                    # (lying down lifts it: it rests on the ground)
    keyed.update(_held_keys(now, script))
    if hasattr(fig, "look_x"):
        keyed.update(_eye_keys(now, script, springs))
    springs.air_was = in_air                                  # (not the lift of lying down: ears and tail read this)
    return keyed


def _ear_keys(now: _Moment, script: _Script, springs: _Springs) -> dict[str, float]:
    """Ears are soft and trail the head: a loose spring follows the head's tilt and nod, and the ears lean by how
    far it is behind. + tilt takes the head's top toward the figure's right (+x); the right ear is sx +1. They
    draw in on a stretch, are pressed out by a hop, react to actions and flick on their own."""
    t, pose, dt = now.t, now.pose, 1.0 / (script.fps * SUB)
    tilt_now = pose.get("head.tilt_left_right", 0.0) + pose.get("spine.left_right", 0.0)
    nod_now = pose.get("head.nod_down_up", 0.0) + pose.get("spine.front_back", 0.0)
    if springs.ears is None:
        springs.ears = [tilt_now, 0.0, nod_now, 0.0]
    trail = springs.ears
    for _ in range(SUB):
        trail[1] += (11.0 ** 2 * (tilt_now - trail[0]) - 2 * 0.32 * 11.0 * trail[1]) * dt
        trail[0] += trail[1] * dt
        trail[3] += (11.0 ** 2 * (nod_now - trail[2]) - 2 * 0.32 * 11.0 * trail[3]) * dt
        trail[2] += trail[3] * dt
    swing = EAR_LAG * (trail[0] - tilt_now)           # ears' tips toward +x by this much
    out_l, out_r, back = -swing, swing, EAR_LAG * (trail[2] - nod_now)
    spread = -45.0 * now.squash                       # stretched, ears draw in; squashed, they spread
    rise = (now.hop - springs.air_was) * script.fps   # going up, the ears are pressed out; coming down, they fly up
    spread += max(-14.0, min(14.0, 16.0 * rise))
    back += max(-8.0, min(8.0, 8.0 * rise))
    out_l, out_r = out_l + spread, out_r + spread
    for at, action, side, scale in script.acts:
        u = (t - at) / action.seconds
        if action.ears and 0 < u < 1:
            a_l, a_r, a_b = action.ears(u, t - at, side)
            out_l, out_r, back = out_l + scale * a_l, out_r + scale * a_r, back + scale * a_b
    for at, side in script.flicks:
        if 0 < t - at < 0.3:
            flick = 12.0 * math.sin(math.pi * (t - at) / 0.3) ** 2
            out_l, out_r = out_l + flick * (side == "left"), out_r + flick * (side == "right")
    lim = lambda value: max(-EAR_MAX, min(EAR_MAX, value))  # noqa: E731
    return {"ear_left": lim(out_l), "ear_right": lim(out_r), "ear_back": lim(back)}


def _tail_keys(now: _Moment, script: _Script, springs: _Springs) -> dict[str, float]:
    """The tail trails the body's lean the same way, sways slowly on its own, and wags with happy actions."""
    t, pose, dt = now.t, now.pose, 1.0 / (script.fps * SUB)
    lean_now = pose.get("spine.left_right", 0.0) + pose.get("chest.left_right", 0.0)
    if springs.tail is None:
        springs.tail = [lean_now, 0.0]
    tail_trail = springs.tail
    for _ in range(SUB):
        tail_trail[1] += (8.0 ** 2 * (lean_now - tail_trail[0]) - 2 * 0.3 * 8.0 * tail_trail[1]) * dt
        tail_trail[0] += tail_trail[1] * dt
    sway_t = (TAIL_LAG * (tail_trail[0] - lean_now)
              + 5.0 * script.life * math.sin(2 * math.pi * t / 2.6 + script.phase[1]))
    # ... and trails a hop
    lift_t = 60.0 * now.squash - max(-16.0, min(16.0, 18.0 * (now.hop - springs.air_was) * script.fps))
    for at, action, side, scale in script.acts:
        u = (t - at) / action.seconds
        if action.tail and 0 < u < 1:
            a_s, a_l = action.tail(u, t - at)
            sway_t, lift_t = sway_t + scale * a_s, lift_t + scale * a_l
    return {"tail_sway": max(-TAIL_MAX, min(TAIL_MAX, sway_t)), "tail_lift": max(-20.0, min(TAIL_MAX, lift_t))}


def _place_keys(now: _Moment, script: _Script) -> dict[str, float]:
    """Off the spot: how high the figure is and where it has got to, its feet, and the way it faces and leans
    (only if something in the performance turns it or lays it down)."""
    fig, trips, keyed = script.fig, script.trips, {}
    if abs(now.rock) > 1.0 and hasattr(fig, "lying_lift"):    # leaning over, it rests on the ground: not in it
        now.hop += fig.lying_lift(now.rock)
    if hasattr(fig, "hop"):
        keyed.update(hop=now.hop, step_x=now.step[0], step_z=now.step[1])
        if hasattr(fig, "step_y") and any(trip[8] for trip in trips):
            keyed.update(step_y=now.climbed)
    if hasattr(fig, "foot_left_up"):
        feet = now.feet
        keyed.update(foot_left_up=feet[0], foot_right_up=feet[1], foot_left_ahead=feet[2], foot_right_ahead=feet[3])
        spins = any(action.spin or action.topple for _t, action, _s, _k in script.acts)
        if trips or script.swings or spins or script.lies:
            keyed.update(yaw=script.yaw0 + now.turned, roll=script.roll0 + now.rock)
    return keyed


def _held_keys(now: _Moment, script: _Script) -> dict[str, float]:
    """The wrists, a robot's screen, and what the figure holds (tipped, popped, thrown, lifted): each only on a
    figure that has the field, and only if something in the performance moves it."""
    fig, acts, keyed = script.fig, script.acts, {}
    if hasattr(fig, "wrist_left"):
        keyed.update(wrist_left=now.wrists["left"], wrist_right=now.wrists["right"])
    if hasattr(fig, "power") and (script.levels or any(action.flicker for _t, action, _s, _k in acts)):
        keyed.update(power=max(0.0, min(1.0, now.level)))
    if hasattr(fig, "item_tilt") and any(action.tip or action.pop for _t, action, _s, _k in acts):
        keyed.update(item_tilt=max(-40.0, min(80.0, now.tipped)), pop=now.popped)
    if hasattr(fig, "item_fly") and script.flights:
        flying = now.flying
        keyed.update(item_fly=now.flown, item_to_x=flying[0], item_to_y=flying[1], item_to_z=flying[2])
    if hasattr(fig, "item_lift") and any(action.lift for _t, action, _s, _k in acts):
        keyed.update(item_lift=now.lifted)
    return keyed


def _eye_keys(now: _Moment, script: _Script, springs: _Springs) -> dict[str, float]:
    """The eyes dart ahead of the head: they take what the head has still to turn, and give it back as it comes;
    and they are never quite still (the darts)."""
    t = now.t
    final = _head_goal(script, t + 0.12)
    dart = next((d for at, d in reversed(script.darts) if t >= at), (0.0, 0.0))
    return {"look_x": max(-1.0, min(1.0, 0.9 * (final[0] - springs.turn) / 22.0 + dart[0])),
            "look_y": max(-1.0, min(1.0, -0.9 * (final[1] - springs.nod) / 16.0 + dart[1]))}


# ----------------------------------------------------------------------------- perform: what it holds
def _key_things(loc, fig, holds: Sequence[tuple], icons: Sequence[tuple]) -> None:
    """Keys what changes at a moment and stays: holds [(time, "side:thing" | None)], the thing in a hand from
    then on, and a picture on a robot's screen while its action plays."""
    if hasattr(fig, "item"):
        for t0, value in sorted((float(a), b or "") for a, b in holds):
            loc.move(fig, max(t0, 0.001), ease="hold", item=value)   # (a key comes after the start)
    if hasattr(fig, "icon"):
        for t0, secs, name in icons:
            loc.move(fig, t0 + 0.12, ease="hold", icon=name)
            loc.move(fig, t0 + secs - 0.12, ease="hold", icon="")


# ----------------------------------------------------------------------------- perform: the face
def _faces(script: _Script) -> list[tuple[float, Pose]]:
    """The face of each stretch of the performance [(from when, Pose)]: the one the figure starts with, then each
    beat's, from the moment the move into the beat starts."""
    return [(0.0, script.start_face)] + [(max(1.0 / script.fps, _move_starts(script, i, 0.0)), p)
                                         for i, (_t, p) in enumerate(script.beats, 1)]


def _blinks(script: _Script, faces: Sequence[tuple], rng: random.Random, blink: bool) -> list[tuple[float, float]]:
    """When the eyes are shut by a blink [(from, until)]: a blink into each new face, blinks now and then while a
    face is held, and a blink as the eyes move to a new look. None with blink=False."""
    shut: list[tuple[float, float]] = []
    for i, (t, face) in enumerate(faces):
        if not blink:
            break
        if i and "closed" not in (faces[i - 1][1].eyes, face.eyes) and faces[i - 1][1] != face:
            shut.append((t - BLINK, t))                       # a blink into the new face
        if face.eyes in ("closed", "spiral", "squint"):
            continue
        until = faces[i + 1][0] if i + 1 < len(faces) else script.end
        at = t + rng.uniform(1.4, 3.0)
        while at + BLINK + 0.2 < until:
            shut.append((at, at + BLINK))
            if rng.random() < 0.2 and at + 2 * BLINK + 0.4 < until:   # now and then it blinks twice
                shut.append((at + BLINK + 0.14, at + 2 * BLINK + 0.14))
            at += rng.uniform(2.2, 4.5)
    if blink:
        shut += [(at, at + BLINK) for at, _g in script.looks]  # and a blink as the eyes move to a new look
    return shut


def _face_at(script: _Script, faces: Sequence[tuple], shut: Sequence[tuple], t: float) -> Pose:
    """The face drawn at t: the beat's face, then the look, an action's face, a blink, and the lip sync's mouth
    over them."""
    face = next(f for at, f in reversed(faces) if t >= at)
    aim = next((g for at, g in reversed(script.looks) if t >= at), None)
    if aim is not None and face.eyes not in ("closed", "spiral"):
        head = _head_goal(script, t + 1.0)                    # what the head will take; the eyes take the rest
        lx = max(-1.0, min(1.0, (aim[0] - head[0]) / 22.0 + aim[0] / 70.0))
        ly = max(-1.0, min(1.0, -((aim[1] - head[1]) / 16.0 + aim[1] / 60.0)))   # a Pose's look: + y is down
        face = replace(face, look=(round(lx, 2), round(ly, 2)),
                       eyes="normal" if face.eyes == "side" else face.eyes)
    for at, action, _side, _scale in script.acts:
        u = (t - at) / action.seconds
        if action.face and 0 < u < 1 and _bell(u) > 0.5:
            face = replace(face, **action.face)
        if action.gaze and 0 < u < 1 and face.eyes not in ("closed", "spiral"):   # eyes that move while it plays
            gx, gy = action.gaze(u, t - at)
            face = replace(face, look=(round(max(-1.0, min(1.0, gx)), 2), round(max(-1.0, min(1.0, gy)), 2)))
    if any(a <= t < b for a, b in shut) and face.eyes not in ("spiral",):
        face = replace(face, eyes="closed")
    spoken = next((m for at, m, _o in reversed(script.mouths) if t >= at), None)
    if spoken is not None:
        face = replace(face, mouth=spoken)
    return face


def _spoken_open(mouths: Sequence[tuple], t: float) -> Optional[float]:
    """The lip-sync track's openness at t, if it gives one."""
    return next((o for at, m, o in reversed(mouths) if t >= at), None) if mouths else None


def _key_face(loc, script: _Script, faces: Sequence[tuple], shut: Sequence[tuple], face_fps: Optional[float]) -> None:
    """Keys the face, frame by frame (at its own rate, if `face_fps` gives one): the drawing, where it changes,
    and, on a face that moves between its drawings (a figure with `lid`: the plush family), its numbers: the lids
    come down before a blink and rise after it, an open mouth opens and closes over a few frames, wide eyes pop
    (a squint first, then bigger than they stay), the blush grows with a shy or giggling action."""
    fig, acts, start_face = script.fig, script.acts, script.start_face
    ffps = float(face_fps or script.fps)
    fframes = int(round(script.end * ffps))
    drawn = [start_face] + [_face_at(script, faces, shut, frame / ffps) for frame in range(1, fframes + 1)]
    closed = [f.eyes == "closed" for f in drawn]
    pops = [k / ffps for k in range(1, fframes + 1) if drawn[k].eyes == "wide" and drawn[k - 1].eyes != "wide"]
    alive = hasattr(fig, "lid")
    shown, held = start_face, start_face.mouth
    mouth_now, mouth_was, mouth_at = start_face.mouth, start_face.mouth, -9.0   # the mouth drawn, the one before, since
    brows_now, brows_was, brows_at = start_face.brows, start_face.brows, -9.0
    openness = 1.0 if start_face.mouth in OPEN_MOUTHS else 0.0
    # the face's numbers are keyed only where they change (a run of equal values is one key at each end), so a
    # face keyed at 24 fps stays small in the scene file
    emitted, previous = None, None
    for frame in range(1, fframes + 1):
        t = frame / ffps
        face = drawn[frame]
        if alive:
            face, openness, held = _mouth_opening(face, _spoken_open(script.mouths, t), openness, held, ffps)
            lid = _lid_round_a_blink(closed, frame, fframes, ffps)
            pop = _eye_pop(pops, t)
            blush, lid = _blush_and_heavy_lids(acts, t, lid)
            if face.mouth != mouth_now:
                mouth_now, mouth_was, mouth_at = face.mouth, mouth_now, t
            if face.brows != brows_now:
                brows_now, brows_was, brows_at = face.brows, brows_now, t
            lines = mouth_now in LINE_MOUTHS and mouth_was in LINE_MOUTHS
            mouth_mix = min(1.0, (t - mouth_at + 1.0 / ffps) / MORPH) if lines else 1.0
            brow_mix = min(1.0, (t - brows_at + 1.0 / ffps) / MORPH)
            winks = _winks(acts, t)
            values = (round(lid, 3), round(openness if face.mouth in OPEN_MOUTHS else 1.0, 3),
                      round(max(0.8, min(1.25, pop)), 3), round(blush, 3), round(mouth_mix, 3), round(brow_mix, 3),
                      round(winks["left"], 3), round(winks["right"], 3))
            if values != previous or frame == fframes:
                if previous is not None and emitted != (frame - 1, previous):        # close the run of equal values
                    loc.move(fig, (frame - 1) / ffps, ease="linear", **dict(zip(_FACE_KEYS, previous)))
                loc.move(fig, t, ease="linear", **dict(zip(_FACE_KEYS, values)))
                emitted = (frame, values)
            previous = values
        if face != shown:
            loc.move(fig, t, ease="hold", expression=face, **({"mouth_from": mouth_was, "brows_from": brows_was}
                                                              if alive else {}))
            shown = face


def _mouth_opening(face: Pose, given: Optional[float], openness: float, held: str,
                   ffps: float) -> tuple[Pose, float, str]:
    """An open mouth opens and closes over a few frames. `given` is how far open the lip sync says (None: it
    does not say), `openness` how far open it was a frame ago, `held` the last open mouth. Gives the face to
    draw (a mouth still closing stays the open one, smaller), how far open it is, and the open mouth held."""
    if given is not None:                              # the lip sync says how far open (0 on a closed mouth)
        openness = given
        held = face.mouth if face.mouth in OPEN_MOUTHS else held
    elif face.mouth in OPEN_MOUTHS:
        openness, held = min(1.0, openness + 1.0 / ffps / 0.08), face.mouth
    else:
        openness = max(0.0, openness - 1.0 / ffps / 0.07)
        if openness > 0.15 and held in OPEN_MOUTHS:   # still closing: the open mouth stays, smaller
            face = replace(face, mouth=held)
    return face, openness, held


def _lid_round_a_blink(closed: Sequence[bool], frame: int, fframes: int, ffps: float) -> float:
    """How far the lids are down on a frame whose eyes are open: they come down over the frames before a blink
    and rise over those after it. `closed` says, frame by frame, whether the eyes are drawn shut."""
    if closed[frame]:
        return 0.0
    ahead = next((k for k in range(1, 4) if frame + k <= fframes and closed[frame + k]), None)
    behind = next((k for k in range(1, 5) if closed[frame - k]), None) if frame >= 4 else None
    return 0.8 * max(0.0, 1 - ahead / ffps / 0.07 if ahead else 0.0, 1 - behind / ffps / 0.13 if behind else 0.0)


def _eye_pop(pops: Sequence[float], t: float) -> float:
    """The size of the eyes at t (1 = as drawn): wide eyes pop, a squint first, then bigger than they stay.
    `pops` are the times the eyes go wide."""
    pop = 1.0
    for at in pops:
        tau = t - at
        pop += -0.1 if -0.09 < tau < 0 else 0.16 * math.exp(-7 * tau) * math.cos(15 * tau) if tau >= 0 else 0.0
    return pop


def _blush_and_heavy_lids(acts: Sequence[tuple], t: float, lid: float) -> tuple[float, float]:
    """What the actions playing at t do to the cheeks and the lids: (how big the blush is: 1 = as drawn, how far
    the lids are down: `lid`, or lower if an action makes the eyes heavy)."""
    blush = 1.0
    for at, action, _side, scale in acts:
        u = (t - at) / action.seconds
        if 0 < u < 1:
            blush += scale * action.blush * _bell(u)
            lid = max(lid, min(0.8, scale * action.lid * _bell(u, 0.3, 0.3)))
    return blush, lid


def _winks(acts: Sequence[tuple], t: float) -> dict[str, float]:
    """How far each eye is shut by a wink at t: the eye on the side of an action that winks."""
    winks = {"left": 0.0, "right": 0.0}
    for at, action, side, scale in acts:
        u = (t - at) / action.seconds
        if action.wink and 0 < u < 1:
            winks[side] = max(winks[side], min(1.0, scale * action.wink * _bell(u, 0.25, 0.3) * 1.25))
    return winks


aim = _aim          # the public name: (yaw, pitch) from a figure's head to a target
