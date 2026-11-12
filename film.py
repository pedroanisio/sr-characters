"""The front door to the plush family: a film in a few lines.

    from characters import film

    f = film.Film("hello", size=(1080, 1080))
    bear = f.add("bear", "idle", at=(0.4, 0, 0))
    bunny = f.add("bunny", "idle", at=(-0.4, 0, 0))
    f.camera((0, 0.9, 12), look_at=(0, 0.4, 0), lens=110)

    bear.look(0.5, bunny).do(1.0, "wave").do(3.0, "jump")
    bunny.look(0.8, bear).do(1.6, "giggle").go(4.0, (-0.9, 0.3), style="hops")

    f.still("out/hello.png")                 # the picture before anything moves
    f.render("out/hello.mp4", seconds=6)     # acted, checked, slimmed, encoded
    f.strip("out/hello-strip.png")           # frames of the clip side by side, to look it over

The cast is the plush family and nothing else (`film.CAST`; the operator, 2026-11-11: "remova Dev e os outros,
vamos focar na familia de pelucia"). Dev and the three older mascots keep their models for the videos already
made with them, in `sr-data/characters_legacy/`; they are no longer characters of this package.

Everything a script needs is here: the stage and its look, the cast by name, what each character
can do (`film.can(who)`), acting (characters.motion), heads that never run into each other (characters.staging),
and scene files small enough for the engine (characters.clip). The modules underneath stay usable for what this
does not cover: `f.loc` is the srlocations Location, `actor.fig` the figure.

Run it with srlocations' interpreter (characters.SRLOCATIONS_PY).
"""
from __future__ import annotations

import math
import subprocess
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Union

from srlocations import Renderer, Styled

from . import blender, clip, export, fixed, kit, lowpoly3d, mascots3d, motion, plush3d, soundtrack, staging, vinyl3d
from .doodle import Pose
from .poses import POSES

PLUSH = tuple(plush3d.ANIMALS)                                   # the plush family
PEOPLE = (*vinyl3d.PEOPLE, *lowpoly3d.PEOPLE)                   # vinyl toys (vinyl3d), low-poly grown-ups (lowpoly3d)
CAST = (*PLUSH, *PEOPLE)                                         # the whole cast of a film
_REMOVED = ("dev", "frog", "chick", "mouse")                     # no longer characters (kept in characters_legacy)

# which way a positive roll leans a figure, measured: +1 if it leans toward the picture's right for a camera on +z
_ROLL_RIGHT = 1.0 if tuple(mascots3d.figure("bear", "idle", roll=10).transform.apply((0, 1, 0)))[0] < 0 else -1.0


class FilmError(Exception):
    """Something in the film cannot be done as asked; the message says what and what there is instead."""


def _known(who: str) -> None:
    if who in CAST:
        return
    if who in _REMOVED:
        raise FilmError(f"{who} was removed from the cast: films are made with the plush family ({', '.join(CAST)})")
    raise FilmError(f"no character {who!r}; the cast is {', '.join(CAST)}")


MOVES = ("body", "blinks", "gaze", "squash", "hop", "travel", "paws", "ears", "tail", "eyelids", "blush", "eye darts",
         "wink", "mouth opening", "mouth and brow morphs", "lip-sync")


LYING = 84.0         # degrees over a figure that lies on its side is
WAYS = ("waddle", "hops", *motion.GAITS, *motion.LEAPS)        # how a character goes from one place to another: go(style=)
SCREEN_ONLY = ("screen-icon",)                  # actions only a character with a screen for a face can play
THINGS = ("gift", "ball", "glass", "mug", "bottle")   # what a character can hold (a glass of wine, a mug of beer)
DRINKS = ("glass", "mug")


def _robot(who: str) -> bool:
    animal = plush3d.ANIMALS.get(who)      # (the cast has characters that are not plush animals or robots)
    return bool(animal and animal.visor)


def can(who: str) -> dict[str, tuple[str, ...]]:
    """What a character can do: its poses, the actions it can play, and what moves on it (the same for the whole
    family). {"poses": ..., "actions": ..., "moves": ...}"""
    _known(who)
    if who in PEOPLE:      # no paws, ears, tail or soft body: the paw actions and what trails are not theirs
        actions = [a for a in motion.ACTIONS if a not in ("twitch", "perk", "droop", "wag", "listen")]
        moves = tuple(x for x in MOVES if x not in ("squash", "paws", "ears", "tail", "blush"))
        return {"poses": tuple(POSES[who]), "actions": tuple(sorted(actions)), "moves": moves, "ways": WAYS}
    actions = sorted(a for a in {**motion.ACTIONS, **motion.PAW_ACTIONS} if a not in SCREEN_ONLY or _robot(who))
    return {"poses": tuple(POSES[who]), "actions": tuple(actions), "moves": MOVES, "ways": WAYS}


class Actor:
    """One character in a film. Its methods add to what it will do and give the actor back, so they chain."""

    def __init__(self, film: "Film", who: str, fig) -> None:
        self.film, self.who, self.fig = film, who, fig
        self.beats: list[tuple] = []
        self.actions: list[tuple] = []
        self.gaze: list[tuple] = []
        self.trips: list[tuple] = []
        self.turns: list[tuple] = []
        self.powers: list[tuple] = []
        self.lays: list[tuple] = []
        self.holds: list[tuple] = []
        self.mouths: list[tuple] = []
        self.options: dict[str, Any] = {}

    def __repr__(self) -> str:
        return f"<Actor {self.fig.name}>"

    def pose(self, time: float, pose: Union[str, Pose]) -> "Actor":
        """From `time` it takes this pose (a name of film.can(who)["poses"], or a Pose)."""
        if isinstance(pose, str) and pose not in POSES[self.who]:
            raise FilmError(f"{self.who} has no pose {pose!r}; it has {', '.join(POSES[self.who])}")
        if time <= 0:
            raise FilmError("a pose change comes after the start; give the first pose to film.add()")
        self.beats.append((float(time), pose))
        return self

    def do(self, time: float, action: str, side: str = "right", scale: float = 1.0,
           at: Union["Actor", Sequence[float], None] = None, seed: Optional[int] = None,
           vary: Optional[float] = None, seconds: Optional[float] = None, icon: Optional[str] = None,
           **more: Any) -> "Actor":
        """At `time` it plays an action (a name of film.can(who)["actions"]) over whatever pose it holds. `at` is
        another actor or a point of the location the action is turned to: it picks the arm on that side
        (instead of `side`), and "point-at" points there. `seed` plays it a little differently (its size, its
        length, where its beat starts): the same seed always gives the same playing, another seed another.
        `vary` says how much (0.15 = up to 15% either way; 0 = exactly as written). `acting(vary=...)` varies
        every action of the actor without a seed each. `seconds` plays it for that long instead of its own
        length: a "dance" or a "tap-foot" goes on, beat after beat. `icon` is the picture a robot's
        "screen-icon" shows: heart, question, exclaim or dots."""
        allowed = can(self.who)["actions"]
        if action not in allowed:
            raise FilmError(f"{self.who} cannot {action!r}; it can {', '.join(allowed)}")
        options = {"side": side, "scale": scale}
        if seed is not None:
            options["seed"] = seed
        if vary is not None:
            options["vary"] = vary
        if seconds is not None:
            options["seconds"] = seconds
        if icon is not None:
            if icon not in plush3d.ICONS:
                raise FilmError(f"no picture {icon!r} for a screen; there are {', '.join(plush3d.ICONS)}")
            options["icon"] = icon
        options.update(more)       # what the film's own helpers pass on (reach, sync)
        if at is not None:
            yaw, pitch = motion.aim(self.fig, at.fig if isinstance(at, Actor) else at)
            options.update(side="right" if yaw >= 0 else "left", aim=(yaw, pitch))
        self.actions.append((float(time), action, options))
        return self

    def look(self, time: float, target: Union["Actor", Sequence[float], None]) -> "Actor":
        """From `time` it looks at another actor, at a point of the location, or (None) straight ahead again."""
        self.gaze.append((float(time), target.fig if isinstance(target, Actor) else target))
        return self

    def climb(self, time: float, to: Sequence[float], rise: float = 0.12, seconds: Optional[float] = None) -> "Actor":
        """At `time` it steps up on to something `rise` metres high at (x, z): a knee up, its weight over it, and
        up; it then stands that much higher (its shadow with it: put a box or a step there with prop()). A
        negative `rise` steps down again."""
        return self.go(time, to, style="climb-step", seconds=seconds, rise=rise)

    def go(self, time: float, to: Sequence[float], style: str = "waddle", seconds: Optional[float] = None,
           turn: float = 0.7, seed: Optional[int] = None, vary: Optional[float] = None, rise: float = 0.0) -> "Actor":
        """At `time` it sets off to (x, z) in the location: rocking from foot to foot ("waddle"), in small hops
        ("hops"), or on two legs: "walk", "run", "sneak" (crouched, looking round), "skip", "tiptoe", "march",
        "stagger", "trip" (a walk with a stumble in it) and "slide-stop" (a run that ends in a skid). "back-away"
        and "moonwalk" go without turning to where they go: send it to a place behind it. "leap" is one long
        jump; "cartwheel" goes over on its hands, to a place at its side; "climb-step" is climb(). A `seed`
        gives the steps their own start and size, as it does an action. It does not go round other characters:
        the film is checked for heads that meet, not bodies."""
        if style not in WAYS:
            raise FilmError(f"no way of going {style!r}; there are {', '.join(WAYS)}")
        options = {"style": style, "turn": turn, **({"seconds": seconds} if seconds else {})}
        if rise:
            options["rise"] = float(rise)
        if seed is not None:
            options["seed"] = seed
        if vary is not None:
            options["vary"] = vary
        self.trips.append((float(time), tuple(to), options))
        return self

    def turn(self, time: float, to: Union["Actor", Sequence[float], float], seconds: float = 0.7) -> "Actor":
        """At `time` it turns on the spot to face another actor, a point (x, z) of the location, or a direction
        in degrees (0 faces a camera on +z), the short way round, and stays so. Its looks go on meaning the
        same thing after it."""
        if isinstance(to, (int, float)):
            yaw = float(to)
        else:
            here = tuple(motion.Vec3.of(self.fig.at))
            there = tuple(motion.Vec3.of(to.fig.at)) if isinstance(to, Actor) else tuple(to)
            yaw = math.degrees(math.atan2(there[0] - here[0], there[-1] - here[2]))
        self.turns.append((float(time), yaw, float(seconds)))
        return self

    def hold(self, time: float, thing: Optional[str], side: str = "right") -> "Actor":
        """From `time` it holds a thing (film.THINGS: a gift, a ball) in the hand of `side`; None puts it away."""
        if thing is not None and thing not in THINGS:
            raise FilmError(f"nothing called {thing!r} to hold; there are {', '.join(THINGS)}")
        self.holds.append((float(time), f"{side}:{thing}" if thing else None))
        return self

    def holding(self, time: float) -> Optional[tuple[str, str]]:
        """(side, thing) of what it holds at `time`, or None."""
        value = next((v for t, v in sorted(self.holds, key=lambda h: h[0], reverse=True) if t <= time), None)
        return tuple(value.split(":", 1)) if value else None

    def drink(self, time: float, thing: str = "glass", seed: Optional[int] = None) -> "Actor":
        """At `time` it drinks from what it holds: the drink comes to the mouth and tips, the head goes back. If
        it holds no drink then, it has `thing` (a "glass" of wine or a "mug" of beer) from the start of the film."""
        held = self.holding(time)
        if held is None or held[1] not in DRINKS:
            if thing not in DRINKS:
                raise FilmError(f"{thing!r} is not a drink; there are {', '.join(DRINKS)}")
            self.hold(0.0, thing)
            held = ("right", thing)
        return self.do(time, "drink", side=held[0], seed=seed)

    def pop_cork(self, time: float, seed: Optional[int] = None) -> "Actor":
        """At `time` it pops the bottle it holds (it has one from the start of the film if it holds none): a
        shake, the cork flies, the foam bursts, and the bottle stays open."""
        held = self.holding(time)
        if held is None or held[1] != "bottle":
            self.hold(0.0, "bottle")
            held = ("right", "bottle")
        self.do(time, "pop-cork", side=held[0], seed=seed, sync=True)
        self.holds.append((float(time) + motion.ACTIONS["pop-cork"].seconds * motion.POP, f"{held[0]}:bottle-open"))
        return self

    def power_down(self, time: float, seconds: float = 1.2) -> "Actor":
        """A robot switches off at `time`: its eyes shut, its face leaves the screen, its head and shoulders sink.
        It stays off until power_up()."""
        return self._power(time, 0.0, seconds)

    def power_up(self, time: float, seconds: float = 1.6) -> "Actor":
        """A robot comes on at `time`: the screen stutters, the eyes open, the face comes back, it straightens up."""
        return self._power(time, 1.0, seconds)

    def _power(self, time: float, level: float, seconds: float) -> "Actor":
        if not _robot(self.who):
            raise FilmError(f"{self.who} has no screen to switch: only the robots do "
                            f"({', '.join(k for k in CAST if _robot(k))})")
        self.powers.append((float(time), level, float(seconds)))
        return self

    def follow(self, time: float, leader: "Actor", gap: float = 0.45, style: Optional[str] = None,
               seed: Optional[int] = None) -> "Actor":
        """From `time` it goes where `leader` goes, a moment after and `gap` metres short of it, in the leader's
        way of going (or `style`). Give it after the leader's own go() calls: it follows the trips it finds."""
        here = tuple(motion.Vec3.of(leader.fig.at))
        was = (here[0], here[2])
        for t0, to, options in sorted(leader.trips, key=lambda trip: trip[0]):
            dx, dz = to[0] - was[0], to[-1] - was[1]
            far = math.hypot(dx, dz) or 1.0
            if t0 >= time:
                self.go(t0 + 0.4, (to[0] - gap * dx / far, to[-1] - gap * dz / far),
                        style=style or options.get("style", "waddle"), seed=seed)
            was = (to[0], to[-1])
        return self

    def sit(self, time: float, pose: str = "sit") -> "Actor":
        """At `time` it sits down where it stands, into a seated pose, and settles."""
        if "sit" not in POSES[self.who].get(pose, Pose()).extras:
            raise FilmError(f"{pose!r} is not a seated pose of {self.who}; there are "
                            f"{', '.join(p for p, v in POSES[self.who].items() if 'sit' in v.extras)}")
        return self.pose(time, pose).do(time + 0.35, "bounce", scale=0.5)

    def stand(self, time: float, pose: str = "idle") -> "Actor":
        """At `time` it gets up from its seat into a standing pose."""
        if pose not in POSES[self.who] or "sit" in POSES[self.who][pose].extras:
            raise FilmError(f"{pose!r} is not a standing pose of {self.who}")
        return self.pose(time, pose).do(time + 0.3, "bounce", scale=0.5)

    def lie_down(self, time: float, side: str = "right", seconds: float = 1.1) -> "Actor":
        """At `time` it lies down on its `side` where it stands, and stays so until get_up(). It needs the room:
        about its own height to that side. Give it a face for it with pose() (eyes closed to sleep)."""
        if side not in ("left", "right"):
            raise FilmError("it lies down on its left or its right side")
        self.lays.append((float(time), (-LYING if side == "right" else LYING), float(seconds)))
        return self

    def get_up(self, time: float, seconds: float = 1.3) -> "Actor":
        """At `time` it gets up from lying (lie_down()) and stands as it stood."""
        self.lays.append((float(time), 0.0, float(seconds)))
        return self.do(time + seconds, "bounce", scale=0.5)

    def wake_up(self, time: float, pose: Optional[str] = None) -> "Actor":
        """At `time` it wakes: it stirs, stretches with a yawn, and is left awake in `pose` (default: "sit" if it
        was in a seated pose, else "idle")."""
        if pose is None:
            was = next((p for t, p in sorted(self.beats, key=lambda b: b[0], reverse=True) if t <= time), None)
            now = (POSES[self.who].get(was, Pose()) if isinstance(was, str) else was) if was is not None else self.fig.expression
            pose = "sit" if "sit" in getattr(now, "extras", ()) else "idle"
        return self.do(time, "wake-up").pose(time + 0.8 * motion.ACTIONS["wake-up"].seconds, pose)

    def say(self, alignment: Mapping[str, Any], at: float, audio: Union[str, Path, None] = None,
            subtitles: bool = True) -> "Actor":
        """It speaks a voice take starting at `at`: `alignment` is the voice's character timestamps (ElevenLabs),
        `audio` the voice file. The mouth follows the words (louder syllables open wider, see motion.lipsync), the
        voice is heard in the film, and the words are subtitled (`subtitles=False` leaves them out)."""
        self.mouths += motion.lipsync(alignment, at=at, audio=audio)
        if audio is not None:
            self.film.sound(audio, at=at, role="dialogue")
        if subtitles:
            self.film.cues += soundtrack.cues_of(soundtrack.words_of(alignment, at), self.film.subtitle_look)
        return self

    def acting(self, **options: Any) -> "Actor":
        """Options of motion.perform() for this actor: energy, life, blink, seed, and vary (every action it
        plays a little different each time, from the actor's seed: 0.15 = up to 15% either way)."""
        self.options.update(options)
        return self


class Film:
    """A location, its cast, a camera, and the clip made of them."""

    def __init__(self, name: str, size: tuple[int, int] = (1080, 1920), fps: float = 24, look=None,
                 overlap: float = 0.15) -> None:
        """`overlap` is how deep (metres) one figure's body may run into another's before the film is refused: a
        figure walking through another is 0.3 to 0.4 deep, neighbours whose ears or paws cross while they act are
        under 0.12. Shallower overlaps are kept in `film.contacts` and printed, to look at in the strip."""
        self.name, self.size = name, tuple(size)
        self.overlap = float(overlap)
        self.contacts: list[tuple] = []     # (name, part, name, part, depth in m, when in s), deepest first
        self.parts: dict[str, tuple[int, int]] = {}   # after settle(): actor -> (places for parts, most showing at once)
        self.fps = int(fps) if float(fps).is_integer() else fps    # the engine takes 24, not 24.0
        self.loc = mascots3d.cast_stage(name)
        self.actors: list[Actor] = []
        self.pairs: list[tuple[Actor, Actor]] = []
        self.sounds: list[soundtrack.Sound] = []        # voices, music, effects: heard in the rendered film
        self.cues: list[soundtrack.Cue] = []            # subtitles, burned into the rendered film
        self.subtitle_look = soundtrack.CaptionLook()
        self._look, self._shot, self._performed, self._clip = look, None, None, None

    # ---- the cast and the set
    def add(self, who: str, pose: Union[str, Pose] = "idle", at: Sequence[float] = (0, 0, 0), yaw: float = 0.0,
            lean: float = 0.0, name: Optional[str] = None, **fields: Any) -> Actor:
        """Puts a character in the film, in its first pose. `lean` leans it toward the picture's right (degrees,
        for a camera on +z); `fields` are the figure's own (e.g. tail_side=-1). Gives its Actor."""
        _known(who)
        if isinstance(pose, str) and pose not in POSES[who]:
            raise FilmError(f"{who} has no pose {pose!r}; it has {', '.join(POSES[who])}")
        name = name or who
        if any(a.fig.name == name for a in self.actors):
            raise FilmError(f"there is already a {name!r} in this film; give the second one a name=")
        common = dict(name=name, at=tuple(at), yaw=yaw, roll=lean * _ROLL_RIGHT, **fields)
        actor = Actor(self, who, self.loc.add(mascots3d.figure(who, pose, **common)))
        self.actors.append(actor)
        return actor

    def prop(self, node):
        """Adds any srlocations node (a Box, a prefab) to the set and gives it back."""
        return self.loc.add(node)

    def sound(self, path: Union[str, Path], at: float = 0.0, role: str = "effects", gain: float = 0.0) -> "Film":
        """A sound heard from `at`: a voice ("dialogue"), "music", an "effects" sound or "ambience". Music and
        ambience give way to voices by themselves, and the whole mix is brought to -14 LUFS. `gain` is in dB."""
        if role not in soundtrack.ROLES:
            raise FilmError(f"no sound role {role!r}; there are {', '.join(soundtrack.ROLES)}")
        if not Path(path).exists():
            raise FilmError(f"no sound file {path}")
        self.sounds.append(soundtrack.Sound(str(path), float(at), role, float(gain)))
        return self

    def music(self, path: Union[str, Path], at: float = 0.0, gain: float = -8.0) -> "Film":
        """Music under the film, from `at`; it gives way to voices."""
        return self.sound(path, at, "music", gain)

    def subtitle(self, text: str, start: float, end: float) -> "Film":
        """A subtitle of your own, shown from `start` to `end` (actor.say() subtitles what is spoken)."""
        if end <= start:
            raise FilmError("a subtitle ends after it starts")
        self.cues.append(soundtrack.Cue(float(start), float(end), text))
        return self

    # ---- two actors at once: each one's arm goes to a point they share, and they keep the same time
    @staticmethod
    def _shoulder(actor: Actor) -> tuple[float, float, float]:
        """Where the middle of an actor's shoulders is in the location."""
        frames = actor.fig.frames()
        left, right = frames["left_upper_arm"].position, frames["right_upper_arm"].position
        return tuple(actor.fig.transform.apply(motion.Vec3((left.x + right.x) / 2, (left.y + right.y) / 2,
                                                           (left.z + right.z) / 2)))

    @staticmethod
    def _reach(actor: Actor, point: Sequence[float], side: Optional[str] = None) -> dict[str, Any]:
        """The options that send an actor's arm (the nearer one, or that of `side`) to a point of the location."""
        local = actor.fig.transform.undo(motion.Vec3(*point))
        side = side or ("right" if local.x >= 0 else "left")
        shoulder = actor.fig.frames()[f"{side}_upper_arm"].position
        out = (local.x - shoulder.x) * (1 if side == "right" else -1)
        return {"side": side, "reach": (out, local.y - shoulder.y, local.z - shoulder.z), "sync": True}

    def _both(self, time: float, a: Actor, b: Actor, names: tuple[str, str], points: tuple, seed: Optional[int]):
        for k, (actor, name, point) in enumerate(zip((a, b), names, points)):
            actor.do(time, name, seed=None if seed is None else seed + k, **self._reach(actor, point))
        self.pairs.append((a, b))       # their heads are kept from running into each other while they do it
        return self

    def high_five(self, time: float, a: Actor, b: Actor, seed: Optional[int] = None) -> "Film":
        """At `time` the two slap hands, at a point between them just above their shoulders."""
        sa, sb = self._shoulder(a), self._shoulder(b)
        meet = ((sa[0] + sb[0]) / 2, (sa[1] + sb[1]) / 2 + 0.08, (sa[2] + sb[2]) / 2 + 0.1)
        return self._both(time, a, b, ("high-five", "high-five"), (meet, meet), seed)

    def hug(self, time: float, a: Actor, b: Actor, seed: Optional[int] = None) -> "Film":
        """At `time` the two hug: each puts the arm of the other's side round the other and leans in. Stand them
        close first (`together()`, or a `go()`)."""
        sa, sb = self._shoulder(a), self._shoulder(b)
        return self._both(time, a, b, ("hug", "hug"), ((sb[0], sb[1], sb[2] + 0.06), (sa[0], sa[1], sa[2] + 0.06)), seed)

    def pat(self, time: float, a: Actor, b: Actor, seed: Optional[int] = None) -> "Film":
        """At `time` `a` pats `b` on the head, and `b` likes it."""
        (hc, hr, _m) = mascots3d.SPECS[b.who].head or mascots3d.SPECS[b.who].body
        top = tuple(b.fig.transform.apply(motion.Vec3(hc[0], hc[1] + 0.8 * hr[1], hc[2] + 0.35 * hr[2])))
        sa = self._shoulder(a)
        nudge = 0.4 * hr[0] * (1 if sa[0] > top[0] else -1)
        a.do(time, "pat-other", seed=seed, **self._reach(a, (top[0] + nudge, top[1], top[2])))
        b.do(time + 0.35, "giggle", scale=0.6, seed=None if seed is None else seed + 1)
        self.pairs.append((a, b))
        return self

    def give(self, time: float, a: Actor, b: Actor, thing: str = "gift", seed: Optional[int] = None) -> "Film":
        """At `time` `a` hands a thing to `b`: `a` holds it from the start of the film (or from its own hold()),
        both reach out to a point between them, and it changes hands as they meet."""
        if not any(value and value.endswith(":" + thing) for _t, value in a.holds):
            a.hold(0.0, thing, self._reach(a, self._shoulder(b))["side"])
        sa, sb = self._shoulder(a), self._shoulder(b)
        meet = ((sa[0] + sb[0]) / 2, (sa[1] + sb[1]) / 2 - 0.05, (sa[2] + sb[2]) / 2 + 0.12)
        self._both(time, a, b, ("give", "take"), (meet, meet), seed)
        a.hold(time + 0.95, None)
        b.hold(time + 0.95, thing, self._reach(b, meet)["side"])
        return self

    def toast(self, time: float, *actors: Actor, thing: str = "glass", seed: Optional[int] = None) -> "Film":
        """At `time` the actors (two or more) raise what they drink and touch glasses at a point between them.
        Whoever holds no drink then has `thing` (a "glass" of wine or a "mug" of beer) from the start of the film."""
        if len(actors) < 2:
            raise FilmError("a toast takes two or more")
        if thing not in DRINKS:
            raise FilmError(f"{thing!r} is not a drink; there are {', '.join(DRINKS)}")
        at = [self._shoulder(a) for a in actors]
        meet = (sum(p[0] for p in at) / len(at), sum(p[1] for p in at) / len(at) + 0.1, sum(p[2] for p in at) / len(at) + 0.12)
        for k, actor in enumerate(actors):
            held = actor.holding(time)
            if held is None or held[1] not in DRINKS:
                actor.hold(0.0, thing, self._reach(actor, meet)["side"])
                held = actor.holding(time)
            actor.do(time, "toast", seed=None if seed is None else seed + k, **self._reach(actor, meet, held[0]))
        self.pairs.extend(zip(actors, actors[1:]))
        return self

    def together(self, a: Actor, b: Actor, gap: float = 0.004) -> "Film":
        """Two actors heads together: placed so the heads touch without merging, and kept so while they act."""
        staging.nuzzle(a.fig, b.fig, gap)
        self.pairs.append((a, b))
        return self

    def camera(self, eye: Sequence[float], look_at: Sequence[float], lens: float = 50.0) -> "Film":
        """Where the camera is, what it looks at, and its lens (mm). A camera on +z sees +x on the picture's left."""
        self._shot = "film"
        self.loc.shot("film", tuple(eye), tuple(look_at), lens=lens)
        return self

    # ---- making pictures
    def look(self):
        """The drawing style: the one given, else the plush look."""
        return self._look if self._look is not None else plush3d.look()

    def _ready(self) -> None:
        if not self.actors:
            raise FilmError("the film has no cast: film.add(who, pose, at=...)")
        if self._shot is None:
            raise FilmError("the film has no camera: film.camera(eye, look_at, lens)")

    def check(self) -> None:
        """Refuses a film where two heads run into each other (before anything moves)."""
        clash = staging.merged([a.fig for a in self.actors])
        if clash:
            raise FilmError(f"heads overlap: {clash}; move them apart or use film.together(a, b)")

    def still(self, out: Union[str, Path], size: Optional[tuple[int, int]] = None, finish: str = "paper",
              quality: str = "fine", device: str = "OPTIX") -> Path:
        """A picture of the film as it stands at the start, in any finish (see render()). A Blender finish at
        "fine" takes 10 to 20 s for one picture."""
        self._ready()
        self.check()
        if self._performed is not None:
            raise FilmError("take the still before render(): the film is now keyed in time")
        width, height = size or self.size
        out = Path(out)
        if finish == "paper":
            return kit.render(self.loc, self._shot, out, width, height, self.look())
        if finish not in blender.FINISHES:
            raise FilmError(f"no finish {finish!r}; there are paper, {', '.join(blender.FINISHES)}")
        import json
        import shutil
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            frames, pngs = Path(folder) / "export", Path(folder) / "png"
            frames.mkdir()
            (frames / "export.json").write_text(json.dumps({
                "format": export.FORMAT, "name": self.name, "fps": self.fps, "frames": 1, "size": [width, height],
                "shot": self._shot, "gate": "vertical" if width / height < 1.5 else "horizontal"}))
            (frames / "0000.json").write_text(json.dumps({"frame": 0, "time": 0.0, **export.frame(self.loc, self._shot)}))
            # one picture can afford what a clip cannot: the full size and enough samples for a clean image
            settings = {**blender.QUALITY[quality], "scale": 1.0, "samples": 64} if quality in blender.QUALITY else quality
            try:
                blender.render(frames, pngs, finish, settings, device)
            except blender.BlenderError as error:
                raise FilmError(str(error)) from error
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(pngs / "0000.png", out)
        return out

    def perform(self, seconds: float) -> "Film":
        """Keys every actor through what it was told to do, for `seconds`, and parts any pair whose heads would
        meet while they act. render() calls it; call it yourself to add keys of your own before rendering."""
        self._ready()
        self.check()
        if self._performed is not None:
            raise FilmError("this film is already performed; build a new Film to change the acting")
        for a in self.actors:
            try:
                motion.perform(self.loc, a.fig, a.beats, actions=a.actions, gaze=a.gaze, travel=a.trips,
                               turns=a.turns, powers=a.powers, lays=a.lays, holds=a.holds, mouths=a.mouths, end=seconds,
                               fps=self.fps, **a.options)
            except ValueError as error:
                raise FilmError(f"{a.fig.name}: {error}") from error
        for a, b in self.pairs:
            staging.clear_in_motion(self.loc, a.fig, b.fig, self.fps)
        clash = staging.merged_in_motion(self.loc, [a.fig for a in self.actors], self.fps)
        if clash:
            raise FilmError(f"heads overlap in motion (name, name, depth in m, time in s): {clash}")
        self.contacts = staging.bodies_in_motion(self.loc, [a.fig for a in self.actors])
        through = [c for c in self.contacts if c[4] > self.overlap]
        if through:
            raise FilmError("a body runs into another (name, part, name, part, depth in m, time in s): "
                            f"{through}; change where it goes, or raise Film(overlap=...) if it is meant")
        if self.contacts:
            print(f"{self.name}: parts that cross while they act (look at the strip): "
                  + "; ".join(f"{a} {pa} / {b} {pb} {d * 100:.0f} cm at {t:g} s" for a, pa, b, pb, d, t in self.contacts),
                  flush=True)
        self.loc.move(self._shot, seconds)
        self._performed = float(seconds)
        return self

    def settle(self) -> dict[str, tuple[int, int]]:
        """Gives each actor one list of parts for the whole film (characters.fixed), so the scene holds it once and
        its sizes change on every frame. render() does it for the paper finish; after keys of your own, before
        compiling the location yourself, call it. {actor: (places, most parts showing at once)}, kept in `parts`."""
        if self._performed is None:
            raise FilmError("settle() comes after perform()")
        self.parts = fixed.settle(self.loc, [a.fig for a in self.actors], self._performed, self.fps)
        return self.parts

    def export(self, folder: Union[str, Path], seconds: Optional[float] = None,
               size: Optional[tuple[int, int]] = None) -> Path:
        """The film as plain geometry, one file a frame (characters.export): the cast's parts with what each is made
        of, the set, the camera. For a renderer other than ours; render(finish="fur") uses it."""
        if self._performed is None:
            if seconds is None:
                raise FilmError("how long is the clip? export(folder, seconds=...)")
            self.perform(seconds)
        return export.frames(self.loc, self._shot, folder, self.fps, self._performed, size or self.size, name=self.name)

    def render(self, out: Union[str, Path], seconds: Optional[float] = None,
               size: Optional[tuple[int, int]] = None, finish: str = "paper", quality: str = "standard",
               device: str = "OPTIX", workers: Optional[bool] = None) -> Path:
        """The clip: performed (if not yet), then drawn.

        `finish="paper"` (default) is our engine's drawn look: compiled, finished as photographed paper, slimmed
        and encoded. `finish="fur"` and `"terry"` are soft toys in a studio, drawn by Blender (characters.blender):
        real pile, or the same cloth with no hairs and about twice as fast. `quality` is "draft", "standard" or
        "fine" (about 1.5, 5 and 10 s a frame for one figure with fur on this host's GPU). Blender's frames are
        kept beside `out` (`<out>.frames/`), so an interrupted render picks up where it stopped. `workers=True`
        has the paper finish rendered on the second machine as well (`clip.engine_env`); compare frames without it."""
        if self._performed is None:
            if seconds is None:
                raise FilmError("how long is the clip? render(out, seconds=...)")
            self.perform(seconds)
        out = Path(out)
        width, height = size or self.size
        if finish == "paper":
            renderer = Renderer(collisions=False)
            self.settle()
            scene = renderer.compile(self.loc, self._shot, Styled(self.look(), width=width, height=height, fps=self.fps))
            kit.finish(scene, width, height)
            heard = bool(self.sounds or self.cues)
            if heard:      # the sound and the subtitles go into the same scene: one render
                soundtrack.apply(scene, width, height, self.sounds, self.cues, out, self.subtitle_look)
            self._clip = clip.encode(renderer, scene, out, own_output=heard, workers=workers)
            return self._clip
        if finish not in blender.FINISHES:
            raise FilmError(f"no finish {finish!r}; there are paper, {', '.join(blender.FINISHES)}")
        if quality not in blender.QUALITY:
            raise FilmError(f"no quality {quality!r}; there are {', '.join(blender.QUALITY)}")
        work = out.with_name(out.stem + ".frames")
        self.export(work / "export", size=(width, height))
        try:
            blender.render(work / "export", work / finish, finish, quality, device, log=work / f"{finish}.log")
        except blender.BlenderError as error:
            raise FilmError(str(error)) from error
        out.parent.mkdir(parents=True, exist_ok=True)
        heard = bool(self.sounds or self.cues)
        picture = work / "picture.mp4" if heard else out
        done = subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(self.fps), "-i", str(work / finish / "%04d.png"),
                               "-vf", f"scale={width}:{height}:flags=lanczos", "-c:v", "libx264", "-crf", "14" if heard else "16",
                               "-pix_fmt", "yuv420p", str(picture)], text=True, capture_output=True)
        if done.returncode:
            raise FilmError(done.stderr[-800:])
        if heard:          # our engine lays the sound and the subtitles over Blender's picture
            scene = soundtrack.cut(picture, width, height, self.fps, self._performed, self.sounds, self.cues, out,
                                   self.subtitle_look)
            clip.encode(Renderer(collisions=False), scene, out, quiet=True, own_output=True)
        self._clip = out
        return out

    def strip(self, out: Union[str, Path], columns: int = 6, rows: int = 2, width: int = 480,
              start: float = 0.0, seconds: Optional[float] = None, source: Union[str, Path, None] = None) -> Path:
        """Frames of the rendered clip (or of `source`) side by side, evenly spaced over `seconds` from `start`:
        the quick way to look a clip over."""
        return strip(source or self._clip, out, columns, rows, width, start, seconds)


def strip(source: Union[str, Path, None], out: Union[str, Path], columns: int = 6, rows: int = 2, width: int = 480,
          start: float = 0.0, seconds: Optional[float] = None) -> Path:
    """Frames of a clip side by side, evenly spaced over `seconds` from `start` (default: the whole clip)."""
    if source is None:
        raise FilmError("no clip yet: render() first, or give strip(source=...)")
    source, out = Path(source), Path(out)
    if seconds is None:
        probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(source)], text=True, capture_output=True)
        seconds = float(probe.stdout.strip() or 0) - start
    if seconds <= 0:
        raise FilmError(f"nothing to show of {source.name} from {start} s")
    out.parent.mkdir(parents=True, exist_ok=True)
    count = columns * rows
    done = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(start), "-t", str(seconds), "-i", str(source),
                           "-vf", f"fps={count / seconds:.5f},scale={width}:-1,tile={columns}x{rows}",
                           "-frames:v", "1", str(out)], text=True, capture_output=True)
    if done.returncode:
        raise FilmError(done.stderr[-800:])
    return out
