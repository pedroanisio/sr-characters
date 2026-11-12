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
    beats = sorted(((float(t), _pose(fig, p)) for t, p in beats), key=lambda b: b[0])
    if beats and beats[0][0] <= 0:
        raise ValueError("beats come after the start: [(time > 0, pose), ...]")
    acts, icons = [], []
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
            base = options["seed"] if "seed" in options else (
                seed if seed is not None else zlib.crc32(str(getattr(fig, "name", "") or id(fig)).encode()))
            which = name if "seed" in options else f"{name}:{len(acts)}"
            action, k = _varied(action, random.Random(zlib.crc32(f"{base}:{which}".encode())), amount,
                                sync=bool(options.get("sync")))
            size *= k
        if action.icon:
            icons.append((float(t), action.seconds, str(options.get("icon", "heart"))))
        acts.append((float(t), action, options.get("side", "right"), size))
    # travel [(time, (x, z) in the location[, {"style": "waddle" | "hops", "seconds": s, "turn": 0..1}])]: the figure
    # goes there, rocking from foot to foot or in small hops, its body turned part of the way toward where it goes
    trips, gone = [], [0.0, 0.0]
    base, yaw0, roll0 = tuple(Vec3.of(fig.at)), float(getattr(fig, "yaw", 0.0)), float(getattr(fig, "roll", 0.0))
    # turns [(time, yaw in degrees: 0 faces +z, seconds)]: it turns on the spot to face that way, and stays so
    swings, turned_to = [], 0.0
    for t0, to_yaw, secs in sorted((float(a), float(b), float(c)) for a, b, c in turns):
        delta = (to_yaw - yaw0 - turned_to + 180.0) % 360.0 - 180.0   # the short way round
        swings.append((t0, max(0.1, secs), turned_to, delta))
        turned_to += delta

    def facing(t: float) -> float:
        """How far the figure has turned from the way it faced at the start, at t (its turns, not its travels)."""
        out = 0.0
        for t0, secs, was, delta in swings:
            if t >= t0:
                u = min(1.0, (t - t0) / secs)
                out = was + delta * u * u * (3 - 2 * u)
        return out

    # lays [(time, degrees over on its side: 0 upright, seconds)]: it lies down on its side, or gets up, and stays so
    lies, lay_was = [], 0.0
    for t0, to_roll, secs in sorted((float(a), float(b), float(c)) for a, b, c in lays):
        lies.append((t0, max(0.1, secs), lay_was, to_roll))
        lay_was = to_roll

    def laid(t: float) -> float:
        out = 0.0
        for t0, secs, was, to in lies:
            if t >= t0:
                u = min(1.0, (t - t0) / secs)
                k = u * u if abs(to) > abs(was) else u * u * (3 - 2 * u)     # it goes down faster and faster
                out = was + (to - was) * k
        return out

    # powers [(time, level: 0 off .. 1 on, seconds)]: a robot's screen goes off, or comes on, and stays so
    levels, level_was = [], 1.0
    for t0, to_level, secs in sorted((float(a), float(b), float(c)) for a, b, c in powers):
        levels.append((t0, max(0.1, secs), level_was, to_level))
        level_was = to_level
    flickers = any(action.flicker for _t, action, _s, _k in acts)
    handled = any(action.tip or action.pop for _t, action, _s, _k in acts)

    def powered(t: float) -> float:
        out = 1.0
        for t0, secs, was, to in levels:
            if t >= t0:
                u = min(1.0, (t - t0) / secs)
                out = was + (to - was) * u * u * (3 - 2 * u)
                if to > was and 0.1 < u < 0.75 and math.sin(2 * math.pi * 11.0 * t) > 0.2:
                    out *= 0.35                                     # coming on, it stutters
        return out

    def aim_at(t: float, target) -> tuple[float, float]:
        way = facing(t)
        return _aim(fig.posed({"yaw": yaw0 + way}) if way else fig, target)

    # a look is taken from the way the figure faces when it looks, and again when it has turned
    wanted = sorted(((float(t), target) for t, target in gaze), key=lambda g: g[0])
    looks = [(t, aim_at(t, target)) for t, target in wanted]
    for t0, secs, _was, _delta in swings:
        held = next((target for t, target in reversed(wanted) if t <= t0 + secs), None)
        if held is not None:
            looks.append((t0 + secs, aim_at(t0 + secs, held)))
    looks.sort(key=lambda g: g[0])
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
            own = options["seed"] if "seed" in options else (
                seed if seed is not None else zlib.crc32(str(getattr(fig, "name", "") or id(fig)).encode()))
            dice = random.Random(zlib.crc32(f"{own}:go:{len(trips)}".encode()))
            gait = (dice.uniform(0.0, 2 * math.pi), 1.0 + amount * dice.uniform(-1.0, 1.0))
        if trips and float(t0) < trips[-1][0] + trips[-1][1] - 1e-6:
            raise ValueError(f"it sets off at {float(t0):g} s before it has arrived from the trip of "
                             f"{trips[-1][0]:g} s, which ends at {trips[-1][0] + trips[-1][1]:.2f} s")
        # how far round from the way it faces when it sets off (its turns before then count)
        heading = (math.degrees(math.atan2(dx, dz)) - yaw0 - facing(float(t0)) + 180.0) % 360.0 - 180.0
        if style == "cartwheel" or (style in GAITS and GAITS[style].back):
            heading = 0.0                                      # it does not turn to where it goes
        if style == "cartwheel":                               # over toward the side it goes to, as it faces then
            facing_now = math.radians(yaw0 + facing(float(t0)))
            n = 1 if dx * math.cos(facing_now) - dz * math.sin(facing_now) >= 0 else -1
        trips.append((float(t0), seconds, tuple(gone), (dx, dz), style, n,
                      heading * float(options.get("turn", 0.7)), gait, float(options.get("rise", 0.0))))
        gone = [gone[0] + dx, gone[1] + dz]
    mouths = sorted(((float(m[0]), m[1], None if len(m) < 3 or m[2] is None else float(m[2])) for m in mouths),
                    key=lambda s: s[0])
    seed = zlib.crc32(str(getattr(fig, "name", "") or id(fig)).encode()) if seed is None else seed
    rng = random.Random(seed)
    last = max([t for t, _p in beats] + [t + a.seconds for t, a, _s, _k in acts] + [t for t, _g in looks]
               + [m[0] for m in mouths] + [trip[0] + trip[1] for trip in trips] + [0.0])
    end = last + 1.0 if end is None else float(end)
    frames = int(round(end * fps))
    start_face = getattr(fig, "expression", None)
    seated = start_face is not None and "sit" in start_face.extras
    spins = any(action.spin or action.topple for _t, action, _s, _k in acts)

    def sitting(t: float) -> bool:
        """Whether the figure is seated at t: as the pose it holds then says (it may sit down and stand up)."""
        now = seated
        for at, p in beats:
            if t >= at:
                now = "sit" in _pose(fig, p).extras
        return now

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
    times = [0.0] + [t for t, _p in beats]

    # ---- targets: a step per beat, with a wind-up before it
    def starts(i: int, lag: float) -> float:   # when the move into beat i starts
        return max(times[i - 1] + 0.02, times[i] - LEAD) + lag

    def winds(i: int) -> bool:                 # room for a wind-up before the move into beat i?
        return energy > 0 and times[i] - times[i - 1] >= 0.6

    def target(name: str, lag: float, t: float) -> float:
        value = poses[0].get(name, 0.0)
        for i in range(1, len(poses)):
            s, nxt = starts(i, lag), poses[i].get(name, 0.0)
            if t >= s:
                value = nxt
            elif winds(i) and t >= s - ANTICIPATION:
                return value - WIND_UP * energy * (nxt - value)
            else:
                break
        return value

    # ---- the dip: knees bend before a change, in proportion to how far the arms travel (not for a seated figure)
    def reach(i: int) -> float:
        arms = [abs(poses[i].get(n, 0.0) - poses[i - 1].get(n, 0.0)) for n in names if "_arm." in n]
        return min(1.0, max(arms, default=0.0) / 70.0)

    def dip_target(t: float) -> float:
        if sitting(t):
            return 0.0
        for i in range(1, len(poses)):
            s = starts(i, 0.0)
            if winds(i) and s - ANTICIPATION <= t < s + 0.05:
                return DIP * energy * reach(i)
        return 0.0

    # ---- gaze: the head takes a share of each look, a little after the eyes
    def head_goal(t: float) -> tuple[float, float]:
        yaw = pitch = 0.0
        for at, (y, p) in looks:
            if t >= at + 0.1:
                yaw, pitch = y, p
        return (max(-HEAD_TURN, min(HEAD_TURN, HEAD_SHARE * yaw)), max(-HEAD_NOD, min(HEAD_NOD, HEAD_SHARE * pitch)))

    # ---- springs, one per control, stepped SUB times a frame
    groups = {n: GROUPS[_group(n)] for n in names}
    x = {n: poses[0].get(n, 0.0) for n in names}
    v = dict.fromkeys(names, 0.0)
    dip, dip_v = 0.0, 0.0
    turn, turn_v, nod, nod_v = 0.0, 0.0, 0.0, 0.0
    soft = hasattr(fig, "squash")                             # a soft body (mascots, plush): squash and stretch
    jelly, jelly_v = 0.0, 0.0
    eared = hasattr(fig, "ear_back")                          # ears that trail the head and react
    trail = None                                              # [tilt follower, its speed, nod follower, its speed]
    # small darts of the eyes while nothing else moves them: a glance aside, then back (a separate random stream,
    # so they change nothing else that is drawn from the seed)
    darts, dice, at = [], random.Random(seed + 7), 0.0
    while life and at < end:
        at += dice.uniform(0.9, 2.8)
        aside = (dice.uniform(-0.32, 0.32), dice.uniform(-0.16, 0.2))
        darts += [(at, aside), (at + dice.uniform(0.25, 0.7), (0.0, 0.0))]
    air_was = [0.0]                                           # how high it was a frame ago
    tail_trail = None                                         # [body lean follower, its speed]
    flicks = []                                               # now and then one ear flicks on its own
    at = rng.uniform(1.0, 3.5)
    while eared and life and at < end:
        flicks.append((at, rng.choice(SIDES)))
        at += rng.uniform(2.5, 6.0)

    def jelly_target(t: float) -> float:
        """Squashed in the wind-up, stretched as the move goes, then left to settle (the spring wobbles it)."""
        for i in range(1, len(poses)):
            s0 = starts(i, 0.0)
            if winds(i) and s0 - ANTICIPATION <= t < s0:
                return -SQUASH * energy * max(0.35, reach(i))
            if energy > 0 and s0 <= t < s0 + 0.12:
                return 0.8 * SQUASH * energy * max(0.35, reach(i))
        return 0.0
    dt = 1.0 / (fps * SUB)
    phase = [rng.uniform(0, 2 * math.pi) for _ in range(4)]

    for frame in range(1, frames + 1):
        for step in range(SUB):
            t = (frame - 1) / fps + (step + 1) * dt
            for n in names:
                lag, w, z = groups[n]
                z = z if energy > 0 else 1.0
                a = w * w * (target(n, lag, t) - x[n]) - 2 * z * w * v[n]
                v[n] += a * dt
                x[n] += v[n] * dt
            a = 12.0 ** 2 * (dip_target(t) - dip) - 2 * 0.55 * 12.0 * dip_v
            dip_v += a * dt
            dip += dip_v * dt
            goal = head_goal(t)
            turn_v += (9.0 ** 2 * (goal[0] - turn) - 2 * 0.75 * 9.0 * turn_v) * dt
            turn += turn_v * dt
            nod_v += (9.0 ** 2 * (goal[1] - nod) - 2 * 0.75 * 9.0 * nod_v) * dt
            nod += nod_v * dt
            jelly_v += (15.0 ** 2 * (jelly_target(t) - jelly) - 2 * 0.38 * 15.0 * jelly_v) * dt
            jelly += jelly_v * dt
        t = frame / fps
        pose = dict(x)

        def add(name: str, amount: float) -> None:
            pose[name] = pose.get(name, 0.0) + amount

        bend = max(0.0, dip)                                  # knees: thigh forward, shin back, foot kept flat
        for side in SIDES:
            add(f"{side}_upper_leg.front_back", -bend)
            add(f"{side}_lower_leg.stretch", -2 * bend)
            add(f"{side}_foot.up_down", -bend)
        add("spine.front_back", -0.25 * bend)                 # and the back gives a little with them

        for side in SIDES:                                    # drag: a fast arm breaks at the elbow, then straightens
            speed = max((abs(v[n]) for n in names if n.startswith(f"{side}_upper_arm.")), default=0.0)
            add(f"{side}_lower_arm.stretch", -min(DRAG_MAX, DRAG * speed) * (energy > 0))

        squash, arms, wrists = jelly, {"left": 1.0, "right": 1.0}, {"left": 0.0, "right": 0.0}
        hop_h, step, turned, rock, climbed = 0.0, [0.0, 0.0], 0.0, 0.0, 0.0
        feet = [0.0, 0.0, 0.0, 0.0]                           # left up, right up, left ahead, right ahead (m)
        for t0, seconds, start, (dx, dz), style, n, heading, (stride0, stride), rise in trips:   # off the spot
            u = (t - t0) / seconds
            if u <= 0:
                continue
            if u >= 1:
                step = [start[0] + dx, start[1] + dz]
                climbed += rise                               # up on a step, it stays up
                continue
            turned = heading * _bell(u, 0.18, 0.18)
            aside = (0.0, 0.0)
            if style == "leap":                               # one long jump: down, off, over and a deep landing
                far = math.hypot(dx, dz)
                air = max(0.0, min(1.0, (u - UP) / (DOWN - UP)))
                go = air * air * (3 - 2 * air)
                hop_h += min(0.34, 0.14 + 0.3 * far) * 4 * air * (1 - air)
                squash += _hop_squash(0.16)(u, t)
                for control, amount in _hop(34.0)(u, t, "right").items():
                    add(control, amount)
                for s in SIDES:                               # the arms thrown up, the legs tucked while it is over
                    add(f"{s}_upper_arm.down_up", 60 * math.sin(math.pi * air))
                    add(f"{s}_lower_leg.stretch", -30 * math.sin(math.pi * air))
                add("spine.front_back", -8 * math.sin(math.pi * air))
            elif style == "cartwheel":                        # over on to its hands and round, to its side
                go = u * u * (3 - 2 * u)
                e = _bell(u, 0.15, 0.15)
                rock = -n * 360.0 * go
                squash += 0.05 * e - 0.1 * (math.exp(-((u - 0.06) / 0.05) ** 2) + math.exp(-((u - 0.95) / 0.05) ** 2))
                for s in SIDES:                               # a star: the arms up and the legs apart
                    add(f"{s}_upper_arm.down_up", 105 * e)
                    add(f"{s}_lower_arm.stretch", 8 * e)
                    add(f"{s}_upper_leg.in_out", 24 * e)
            elif style == "climb-step":                       # a knee up, the weight over it, and up
                knee, up = _bell(u, 0.2, 0.45), max(0.0, min(1.0, (u - 0.3) / 0.45))
                up = up * up * (3 - 2 * up)
                go = up
                climbed += rise * up
                follow = math.exp(-((u - 0.72) / 0.14) ** 2)   # the other leg comes up after it
                add("right_upper_leg.front_back", -62 * knee * (1 - up))
                add("right_lower_leg.stretch", -70 * knee * (1 - up))
                add("left_upper_leg.front_back", -40 * follow)
                add("left_lower_leg.stretch", -55 * follow)
                add("spine.front_back", -12 * _bell(u, 0.25, 0.3))
                add("head.nod_down_up", -8 * knee * (1 - up))
                for s, k in (("left", 1), ("right", -1)):
                    add(f"{s}_upper_arm.front_back", 14 * k * _bell(u, 0.25, 0.3))
                    add(f"{s}_upper_arm.down_up", 18 * _bell(u, 0.25, 0.3))
                squash += 0.05 * math.sin(math.pi * up) - 0.07 * math.exp(-((u - 0.86) / 0.07) ** 2)
            elif style == "hops":                               # small hops: it moves while it is in the air
                done, part = divmod(u * n, 1.0)
                air = max(0.0, min(1.0, (part - UP) / (DOWN - UP)))
                go = (done + air * air * (3 - 2 * air)) / n
                hop_h += 0.055 * 4 * air * (1 - air)
                squash += _hop_squash(0.09)(part, t)
                for control, amount in _hop(15.0)(part, t, "right").items():
                    add(control, amount)
            elif style in GAITS:                              # on two legs: a walk, a run, a sneak, a skip
                g = GAITS[style]
                go, e = u * u * (3 - 2 * u), _bell(u, 0.12, 0.12) * stride
                skid = 0.0
                if g.skid:                                    # the end of the trip is a skid: no more steps
                    into = max(0.0, min(1.0, (u - (1.0 - g.skid)) / 0.12))
                    into = into * into * (3 - 2 * into)
                    out_of = max(0.0, min(1.0, (u - 0.9) / 0.1))
                    skid, e = into * (1.0 - out_of * out_of * (3 - 2 * out_of)), e * (1.0 - into)
                    go = 1.0 - (1.0 - u) ** 2.2               # it comes in fast and slows all the way
                    add("spine.front_back", 17 * skid)
                    add("left_upper_leg.front_back", -30 * skid)
                    add("right_upper_leg.front_back", -16 * skid)
                    add("left_lower_leg.stretch", 6 * skid)
                    add("head.nod_down_up", -8 * skid)
                    for s in SIDES:
                        add(f"{s}_upper_arm.down_up", 62 * skid)
                        add(f"{s}_foot.up_down", 18 * skid)
                    squash -= 0.06 * skid
                    turned += 28 * skid
                if g.stumble:                                 # a foot catches: forward, arms out, and saved
                    caught = math.exp(-((u - g.stumble) / 0.07) ** 2)
                    add("spine.front_back", -26 * caught)
                    add("chest.front_back", -12 * caught)
                    add("head.nod_down_up", 14 * caught)
                    add("right_upper_leg.front_back", 26 * caught)
                    add("right_lower_leg.stretch", -40 * caught)
                    for s in SIDES:
                        add(f"{s}_upper_arm.front_back", 60 * caught)
                        add(f"{s}_upper_arm.down_up", 40 * caught)
                    hop_h += 0.025 * caught
                    squash += 0.05 * caught - 0.07 * math.exp(-((u - g.stumble - 0.12) / 0.06) ** 2)
                    go = max(0.0, min(1.0, go + 0.05 * (caught - math.exp(-((u - g.stumble - 0.16) / 0.1) ** 2))))
                beat = 2 * math.pi * g.rate * (t - t0) + stride0
                swing = math.sin(beat)
                rock = g.rock * e * swing
                hop_h += g.lift * e * abs(math.cos(beat))
                squash -= g.squash * e * abs(swing)
                for s, k in (("left", 1), ("right", -1)):
                    add(f"{s}_upper_leg.front_back", e * (g.thigh * k * swing - g.crouch))
                    add(f"{s}_lower_leg.stretch", -e * (g.knee * max(0.0, k * math.sin(beat + 0.9)) + 2 * g.crouch))
                    add(f"{s}_foot.up_down", -e * g.crouch)
                    add(f"{s}_upper_arm.front_back", e * (g.hands - g.arm * k * swing))
                    add(f"{s}_lower_arm.stretch", -e * g.elbow)
                    add(f"{s}_shoulder.down_up", e * g.shoulders)
                    add(f"{s}_upper_arm.down_up", e * g.out)
                    add(f"{s}_foot.up_down", -e * g.toes)
                if g.sway:                                    # lolling, slower than the steps
                    loll = math.sin(0.43 * beat + 1.0)
                    add("spine.left_right", g.sway * e * loll)
                    add("head.tilt_left_right", 1.2 * g.sway * e * math.sin(0.43 * beat + 0.3))
                    add("head.nod_down_up", -0.8 * g.sway * e)
                if g.weave:
                    far = math.hypot(dx, dz) or 1.0
                    off = g.weave * e * math.sin(0.5 * beat)
                    aside = (dz / far * off, -dx / far * off)
                add("spine.front_back", -g.lean * e)
                add("chest.front_back", -0.5 * g.lean * e)
                add("spine.twist_left_right", g.twist * e * swing)
                add("spine.left_right", -1.5 * e * swing)
                add("head.turn_left_right", g.scan * e * math.sin(0.5 * beat))
            else:                                             # a waddle: it rocks from foot to foot as it goes
                go, e, beat = (u * u * (3 - 2 * u), _bell(u, 0.12, 0.12) * stride,
                               2 * math.pi * 1.6 * (t - t0) + stride0)
                rock = 7.0 * e * math.sin(beat)
                swing = math.sin(beat)                        # the foot on the lifted side leaves the ground and swings on
                feet[0] += 0.03 * e * max(0.0, swing)
                feet[1] += 0.03 * e * max(0.0, -swing)
                feet[2] += 0.02 * e * math.cos(beat) * (swing > 0)
                feet[3] -= 0.02 * e * math.cos(beat) * (swing < 0)
                hop_h += 0.012 * e * abs(math.cos(beat))
                squash -= 0.025 * e * abs(math.sin(beat))
                for s, k in (("left", 1), ("right", -1)):
                    add(f"{s}_upper_leg.front_back", 13 * e * k * math.sin(beat))
                    add(f"{s}_upper_arm.front_back", -9 * e * k * math.sin(beat))
                add("spine.left_right", -2.5 * e * math.sin(beat))
                add("head.tilt_left_right", -3.0 * e * math.sin(beat))
            step = [start[0] + dx * go + aside[0], start[1] + dz * go + aside[1]]
        tipped, popped = 0.0, 0.0                             # what it holds: tipped to the face, a bottle's pop
        level = powered(t)
        if level < 1.0:                                       # a robot that is off hangs its head and shoulders
            down = 1.0 - level
            add("head.nod_down_up", -14 * down)
            add("neck.nod_down_up", -5 * down)
            add("spine.front_back", -5 * down)
            for s in SIDES:
                add(f"{s}_shoulder.down_up", -6 * down)
            squash -= 0.04 * down
        turned += facing(t)                                   # the way it has turned to face, for good
        rock += laid(t)                                       # how far over it lies, for good
        for t0, secs, was, to in lies:                        # it gives as it lands, and as it pushes itself up
            squash -= 0.1 * math.exp(-((t - t0 - (secs if abs(to) > abs(was) else 0.25 * secs)) / 0.09) ** 2)
        for t0, secs, _was, delta in swings:                  # ... with a small lift and a give as it comes round
            if t0 < t < t0 + secs:
                way = math.sin(math.pi * (t - t0) / secs) * min(1.0, abs(delta) / 90.0)
                hop_h += 0.015 * way
                squash += 0.03 * way
        for at, action, side, scale in acts:                  # actions, over the pose
            if action.spin and t >= at + action.seconds:      # a spin that is over leaves the figure where it got to
                turned += (1 if side == "right" else -1) * action.spin(1.0)
            u = (t - at) / action.seconds
            if not 0 < u < 1:
                continue
            if action.spin:
                turned += (1 if side == "right" else -1) * action.spin(u)
            if action.topple and not sitting(t):              # the whole figure goes over toward its side
                rock += (-1 if side == "right" else 1) * action.topple(u)
            if action.flicker:
                level *= action.flicker(u, t - at)
            if action.tip:
                tipped += scale * action.tip(u, t - at)
            if action.pop:
                popped = max(popped, action.pop(u))
            if action.squash:
                squash += scale * action.squash(u, t - at)
            if action.air and not sitting(t):
                hop_h += scale * action.air(u)
            if action.feet:
                for i, value in enumerate(action.feet(u, t - at, sitting(t))):
                    feet[i] += scale * value
            if action.arm != 1.0:
                for arm_side in (SIDES if action.both else (side,)):
                    arms[arm_side] = max(arms[arm_side], 1.0 + (action.arm - 1.0) * _bell(u, 0.22, 0.25))
            if action.gesture:                                # the arm goes to the gesture and comes back
                k = _bell(u, 0.22, 0.25)
                key = (action.gesture, side, action.both)
                g, longer = gestures[key], longest[key]
                if action.gesture2:                           # ... swinging to a second gesture and back
                    key2, share = (action.gesture2, side, action.both), max(0.0, min(1.0, action.mix(u, t - at)))
                    g2 = gestures[key2]
                    g = {n: g.get(n, g2.get(n, 0.0)) + share * (g2.get(n, g.get(n, 0.0)) - g.get(n, g2.get(n, 0.0)))
                         for n in set(g) | set(g2)}
                    longer += share * (longest[key2] - longer)
                for n, value in g.items():
                    pose[n] = pose.get(n, 0.0) + k * (value - pose.get(n, 0.0))
                for arm_side in (SIDES if action.both else (side,)):
                    # the arm grows late and shrinks early, so it is not long while it swings out past the side
                    arms[arm_side] = max(arms[arm_side], 1.0 + (longer - 1.0) * k ** 3)
            if action.wrist:
                for arm_side in (SIDES if action.both else (side,)):
                    wrists[arm_side] += scale * action.wrist(u, t - at)
            move = action.seated if sitting(t) and action.seated else action.offsets
            for n, amount in move(u, t - at, side).items():
                add(n, scale * amount)

        add("head.turn_left_right", turn)
        add("head.nod_down_up", nod)

        if life:
            breath = math.sin(2 * math.pi * t / 3.6 + phase[0])
            late = math.sin(2 * math.pi * t / 3.6 + phase[0] - 0.7)
            sway = math.sin(2 * math.pi * t / 7.3 + phase[1])
            drift = math.sin(2 * math.pi * t / 5.1 + phase[2])
            bobbing = math.sin(2 * math.pi * t / 6.4 + phase[3])
            add("chest.front_back", 1.3 * life * breath)
            add("spine.front_back", -0.6 * life * breath)
            add("spine.left_right", 0.9 * life * sway)
            add("head.tilt_left_right", -0.7 * life * sway)   # the head stays level over a swaying body
            add("head.turn_left_right", 1.2 * life * drift)
            if sitting(t):                                    # seated legs are never still: the feet sway in turn
                for s, k in (("left", 1), ("right", -1)):
                    add(f"{s}_upper_leg.front_back", 2.2 * life * k * math.sin(2 * math.pi * t / 2.9 + phase[2]))
                    add(f"{s}_foot.up_down", 5.0 * life * k * math.sin(2 * math.pi * t / 2.9 + phase[2] - 0.6))
            else:                                             # standing, the weight settles on one leg, then the other
                lean = math.sin(2 * math.pi * t / 6.1 + phase[3])
                lean = math.copysign(abs(lean) ** 0.45, lean)  # it stays on a leg a while, and crosses quickly
                add("spine.left_right", 1.8 * life * lean)
                add("chest.left_right", -1.2 * life * lean)
                for s, k in (("left", 1), ("right", -1)):
                    free = life * max(0.0, k * lean)          # the free leg's knee gives
                    add(f"{s}_upper_leg.front_back", -5 * free)
                    add(f"{s}_lower_leg.stretch", -9 * free)
            add("head.nod_down_up", 0.8 * life * bobbing)
            for side in SIDES:
                add(f"{side}_shoulder.down_up", 1.2 * life * breath)
                add(f"{side}_upper_arm.front_back", 1.0 * life * late)

        keyed = {"pose": {n: _clamped(n, value) for n, value in pose.items()}}
        if eared:
            # Ears are soft and trail the head: a loose spring follows the head's tilt and nod, and the ears lean by
            # how far it is behind. + tilt takes the head's top toward the figure's right (+x); the right ear is sx +1.
            tilt_now = pose.get("head.tilt_left_right", 0.0) + pose.get("spine.left_right", 0.0)
            nod_now = pose.get("head.nod_down_up", 0.0) + pose.get("spine.front_back", 0.0)
            if trail is None:
                trail = [tilt_now, 0.0, nod_now, 0.0]
            for _ in range(SUB):
                trail[1] += (11.0 ** 2 * (tilt_now - trail[0]) - 2 * 0.32 * 11.0 * trail[1]) * dt
                trail[0] += trail[1] * dt
                trail[3] += (11.0 ** 2 * (nod_now - trail[2]) - 2 * 0.32 * 11.0 * trail[3]) * dt
                trail[2] += trail[3] * dt
            swing = EAR_LAG * (trail[0] - tilt_now)           # ears' tips toward +x by this much
            out_l, out_r, back = -swing, swing, EAR_LAG * (trail[2] - nod_now)
            spread = -45.0 * squash                           # stretched, ears draw in; squashed, they spread
            rise = (hop_h - air_was[0]) * fps                 # going up, the ears are pressed out; coming down, they fly up
            spread += max(-14.0, min(14.0, 16.0 * rise))
            back += max(-8.0, min(8.0, 8.0 * rise))
            out_l, out_r = out_l + spread, out_r + spread
            for at, action, side, scale in acts:
                u = (t - at) / action.seconds
                if action.ears and 0 < u < 1:
                    a_l, a_r, a_b = action.ears(u, t - at, side)
                    out_l, out_r, back = out_l + scale * a_l, out_r + scale * a_r, back + scale * a_b
            for at, side in flicks:
                if 0 < t - at < 0.3:
                    flick = 12.0 * math.sin(math.pi * (t - at) / 0.3) ** 2
                    out_l, out_r = out_l + flick * (side == "left"), out_r + flick * (side == "right")
            lim = lambda value: max(-EAR_MAX, min(EAR_MAX, value))  # noqa: E731
            keyed.update(ear_left=lim(out_l), ear_right=lim(out_r), ear_back=lim(back))
        if hasattr(fig, "tail_sway"):
            # The tail trails the body's lean the same way, sways slowly on its own, and wags with happy actions.
            lean_now = pose.get("spine.left_right", 0.0) + pose.get("chest.left_right", 0.0)
            if tail_trail is None:
                tail_trail = [lean_now, 0.0]
            for _ in range(SUB):
                tail_trail[1] += (8.0 ** 2 * (lean_now - tail_trail[0]) - 2 * 0.3 * 8.0 * tail_trail[1]) * dt
                tail_trail[0] += tail_trail[1] * dt
            sway_t = TAIL_LAG * (tail_trail[0] - lean_now) + 5.0 * life * math.sin(2 * math.pi * t / 2.6 + phase[1])
            lift_t = 60.0 * squash - max(-16.0, min(16.0, 18.0 * (hop_h - air_was[0]) * fps))   # and trails a hop
            for at, action, side, scale in acts:
                u = (t - at) / action.seconds
                if action.tail and 0 < u < 1:
                    a_s, a_l = action.tail(u, t - at)
                    sway_t, lift_t = sway_t + scale * a_s, lift_t + scale * a_l
            keyed.update(tail_sway=max(-TAIL_MAX, min(TAIL_MAX, sway_t)), tail_lift=max(-20.0, min(TAIL_MAX, lift_t)))
        if soft:
            if life:
                squash += 0.012 * life * math.sin(2 * math.pi * t / 3.6 + phase[0])   # it breathes
            keyed.update(squash=max(-0.22, min(0.22, squash)), arm_left=arms["left"], arm_right=arms["right"])
        if abs(rock) > 1.0 and hasattr(fig, "lying_lift"):    # leaning over, it rests on the ground: not in it
            hop_h += fig.lying_lift(rock)
        if hasattr(fig, "hop"):
            keyed.update(hop=hop_h, step_x=step[0], step_z=step[1])
            if hasattr(fig, "step_y") and any(trip[8] for trip in trips):
                keyed.update(step_y=climbed)
        if hasattr(fig, "foot_left_up"):
            keyed.update(foot_left_up=feet[0], foot_right_up=feet[1], foot_left_ahead=feet[2], foot_right_ahead=feet[3])
            if trips or swings or spins or lies:
                keyed.update(yaw=yaw0 + turned, roll=roll0 + rock)
        if hasattr(fig, "wrist_left"):
            keyed.update(wrist_left=wrists["left"], wrist_right=wrists["right"])
        if hasattr(fig, "power") and (levels or flickers):
            keyed.update(power=max(0.0, min(1.0, level)))
        if hasattr(fig, "item_tilt") and handled:
            keyed.update(item_tilt=max(-40.0, min(80.0, tipped)), pop=popped)
        if hasattr(fig, "look_x"):
            # the eyes dart ahead of the head: they take what the head has still to turn, and give it back as it comes
            final = head_goal(t + 0.12)
            dart = next((d for at, d in reversed(darts) if t >= at), (0.0, 0.0))   # and are never quite still
            keyed.update(look_x=max(-1.0, min(1.0, 0.9 * (final[0] - turn) / 22.0 + dart[0])),
                         look_y=max(-1.0, min(1.0, -0.9 * (final[1] - nod) / 16.0 + dart[1])))
        air_was[0] = hop_h
        loc.move(fig, t, ease="linear", **keyed)

    if hasattr(fig, "item"):                                  # holds [(time, "side:thing" | None)]: from when
        for t0, value in sorted((float(a), b or "") for a, b in holds):
            loc.move(fig, max(t0, 0.001), ease="hold", item=value)   # (a key comes after the start)
    if hasattr(fig, "icon"):                                  # a picture on a robot's screen, while its action plays
        for t0, secs, name in icons:
            loc.move(fig, t0 + 0.12, ease="hold", icon=name)
            loc.move(fig, t0 + secs - 0.12, ease="hold", icon="")

    # ---- the face, frame by frame: the beat's face, the look, an action's face, a blink; keyed where it changes
    if start_face is None:
        return
    faces = [(0.0, start_face)] + [(max(1.0 / fps, starts(i, 0.0)), p) for i, (_t, p) in enumerate(beats, 1)]
    shut: list[tuple[float, float]] = []                      # when the eyes are shut by a blink
    for i, (t, face) in enumerate(faces):
        if not blink:
            break
        if i and "closed" not in (faces[i - 1][1].eyes, face.eyes) and faces[i - 1][1] != face:
            shut.append((t - BLINK, t))                       # a blink into the new face
        if face.eyes in ("closed", "spiral", "squint"):
            continue
        until = faces[i + 1][0] if i + 1 < len(faces) else end
        at = t + rng.uniform(1.4, 3.0)
        while at + BLINK + 0.2 < until:
            shut.append((at, at + BLINK))
            if rng.random() < 0.2 and at + 2 * BLINK + 0.4 < until:   # now and then it blinks twice
                shut.append((at + BLINK + 0.14, at + 2 * BLINK + 0.14))
            at += rng.uniform(2.2, 4.5)
    if blink:
        shut += [(at, at + BLINK) for at, _g in looks]        # and a blink as the eyes move to a new look

    def face_at(t: float) -> Pose:
        face = next(f for at, f in reversed(faces) if t >= at)
        aim = next((g for at, g in reversed(looks) if t >= at), None)
        if aim is not None and face.eyes not in ("closed", "spiral"):
            head = head_goal(t + 1.0)                         # what the head will take; the eyes take the rest
            lx = max(-1.0, min(1.0, (aim[0] - head[0]) / 22.0 + aim[0] / 70.0))
            ly = max(-1.0, min(1.0, -((aim[1] - head[1]) / 16.0 + aim[1] / 60.0)))   # a Pose's look: + y is down
            face = replace(face, look=(round(lx, 2), round(ly, 2)),
                           eyes="normal" if face.eyes == "side" else face.eyes)
        for at, action, _side, _scale in acts:
            u = (t - at) / action.seconds
            if action.face and 0 < u < 1 and _bell(u) > 0.5:
                face = replace(face, **action.face)
            if action.gaze and 0 < u < 1 and face.eyes not in ("closed", "spiral"):   # eyes that move while it plays
                gx, gy = action.gaze(u, t - at)
                face = replace(face, look=(round(max(-1.0, min(1.0, gx)), 2), round(max(-1.0, min(1.0, gy)), 2)))
        if any(a <= t < b for a, b in shut) and face.eyes not in ("spiral",):
            face = replace(face, eyes="closed")
        spoken = next((m for at, m, _o in reversed(mouths) if t >= at), None)
        if spoken is not None:
            face = replace(face, mouth=spoken)
        return face

    def spoken_open(t: float) -> Optional[float]:   # the lip-sync track's openness at t, if it gives one
        return next((o for at, m, o in reversed(mouths) if t >= at), None) if mouths else None

    ffps = float(face_fps or fps)
    fframes = int(round(end * ffps))

    # A face that moves between its drawings (a figure with `lid`: the plush family): the lids come down before a
    # blink and rise after it, an open mouth opens and closes over a few frames, wide eyes pop (a squint first,
    # then bigger than they stay), the blush grows with a shy or giggling action.
    drawn = [start_face] + [face_at(frame / ffps) for frame in range(1, fframes + 1)]
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
            given = spoken_open(t)
            if given is not None:                              # the lip sync says how far open (0 on a closed mouth)
                openness = given
                held = face.mouth if face.mouth in OPEN_MOUTHS else held
            elif face.mouth in OPEN_MOUTHS:
                openness, held = min(1.0, openness + 1.0 / ffps / 0.08), face.mouth
            else:
                openness = max(0.0, openness - 1.0 / ffps / 0.07)
                if openness > 0.15 and held in OPEN_MOUTHS:   # still closing: the open mouth stays, smaller
                    face = replace(face, mouth=held)
            lid = 0.0
            if not closed[frame]:
                ahead = next((k for k in range(1, 4) if frame + k <= fframes and closed[frame + k]), None)
                behind = next((k for k in range(1, 5) if closed[frame - k]), None) if frame >= 4 else None
                lid = 0.8 * max(0.0, 1 - ahead / ffps / 0.07 if ahead else 0.0, 1 - behind / ffps / 0.13 if behind else 0.0)
            pop, blush = 1.0, 1.0
            for at in pops:
                tau = t - at
                pop += -0.1 if -0.09 < tau < 0 else 0.16 * math.exp(-7 * tau) * math.cos(15 * tau) if tau >= 0 else 0.0
            for at, action, _side, scale in acts:
                u = (t - at) / action.seconds
                if 0 < u < 1:
                    blush += scale * action.blush * _bell(u)
                    lid = max(lid, min(0.8, scale * action.lid * _bell(u, 0.3, 0.3)))
            if face.mouth != mouth_now:
                mouth_now, mouth_was, mouth_at = face.mouth, mouth_now, t
            if face.brows != brows_now:
                brows_now, brows_was, brows_at = face.brows, brows_now, t
            lines = mouth_now in LINE_MOUTHS and mouth_was in LINE_MOUTHS
            mouth_mix = min(1.0, (t - mouth_at + 1.0 / ffps) / MORPH) if lines else 1.0
            brow_mix = min(1.0, (t - brows_at + 1.0 / ffps) / MORPH)
            winks = {"left": 0.0, "right": 0.0}
            for at, action, side, scale in acts:
                u = (t - at) / action.seconds
                if action.wink and 0 < u < 1:
                    winks[side] = max(winks[side], min(1.0, scale * action.wink * _bell(u, 0.25, 0.3) * 1.25))
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


aim = _aim          # the public name: (yaw, pitch) from a figure's head to a target
