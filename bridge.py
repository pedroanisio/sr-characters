"""An acted character handed to another program: a transparent clip and a strict record of what it shows.

srstudio builds episodes and keeps its own interpreter; it reads a 3D set as data (its location record, ADR 0179:
each shot's camera, where every mark lands in the frame). This module is the other half for the cast: it stands a
character on a mark of such a record, under that shot's camera, has it act, and writes a cutout the episode lays
over its picture of the set:

    from characters import bridge
    f, anchor = bridge.from_shot("airliner-1080x1920.json", "down-the-aisle", "aisle", "anchor", facing_deg=180)
    anchor.do(0.4, "wave")
    bridge.say_take(anchor, {"id": "take-1", "words": [{"text": "Boa", "start": 0.0, "end": 0.2}, ...]}, at=0.5)
    record = bridge.cutout(f, "out/anchor", seconds=3)      # out/anchor/frames/00000.png ..., out/anchor/clip.json

or, with no Python of the caller's own, from a request file (see `parse_request`):

    SRLOCATIONS_PY -m characters.bridge REQUEST.json OUT_DIR

`cutout()` writes RGBA PNG frames at the film's full size (straight alpha; the character's shadow on the ground is
in the alpha) and `clip.json`, which `characters.clip_record` describes and reads: who drew it, the frame, the
camera, each figure, and for every frame where its feet and head are in the picture and the frame's SHA-256. The
record is read back with that reader, files and all, before `cutout()` returns: nothing it would refuse is handed on.
Captions and sound are the episode's: a spoken take moves the mouth here and is written in the record, nothing more.

Three things are settled here, each measured (the numbers are in SDK.md, "A character for srstudio"):

- **The studio.** The low-poly finish lights a figure near the origin for a camera on +z (its lamps, the lamp
  that casts the shadow, the floor that catches it). A mark is anywhere in a set and a shot looks from anywhere,
  so the film is built in the studio's space and the record written in the set's: `Stage` is the turn about the
  vertical, the move and the scale between the two. The picture is the same, since a camera and what it looks at
  moved together show the same thing, and `from_shot()` checks it on the mark's own pixels.
- **Facing.** A mark's `facing_deg` and `Film.add(yaw=)` are one convention in the set's space: 0 faces +z, 90
  faces +x (`srlocations.Transform.at(yaw=a)` sends (0, 0, 1) to (sin a, 0, cos a), and the record's facing is that
  direction's atan2(x, z)). A character has the mark's facing unless `facing_deg=` gives another. A mark faces
  where its location says, which may be away from a shot's camera: `aisle` in the airliner faces 0, the galley, and
  `down-the-aisle` looks from behind it.
- **Height.** A figure's own `height` field (the mannequin's) is refused here: it moves the joints and leaves
  every drawn part the size it was (measured on `anchor` at 1.7: the head, trunk, hips and shoes are as large as
  at 1.0 and the legs 1.69 times as long). `height_m=` is how tall the character stands in the set instead, and it is
  the camera that gives it: the studio's metre is `height_m / stature` of the set's, so every part, the ground
  under the feet and every gesture are scaled alike. Without it a character is drawn at its own size (a low-poly
  person is 1.0 m, where a mark is recorded for a body of 1.7 m).

Run it with srlocations' interpreter. Low poly is the only finish that writes alpha (see `ALPHA_FINISHES`).
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import struct
import subprocess
import sys
import time
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Union

from srlocations.compiler import Projection
from srlocations.geometry import Vec3

from . import blender, clip_record, mascots3d, speech
from . import film as films

ALPHA_FINISHES = ("lowpoly",)          # the finishes whose frames can be written with alpha
REQUEST = "characters.cutout-request/1.0.0"
LOCATION_MAJOR = "1"                   # srstudio's location record, schema 1.x (location_bridge.SCHEMA_VERSION)
LETTER_FLOOR = 0.01                    # seconds a word lasts at the least (srstudio.supplied.LETTER_FLOOR)
MAX_REQUEST_BYTES = 1_000_000
MAX_LOCATION_BYTES = 4_000_000         # srstudio.location_bridge.MAX_BYTES
PIXEL = 1e-6                           # how far apart, in pixels, the studio's camera and the set's may put a point
ROOT = Path(__file__).resolve().parent


class BridgeError(ValueError):
    """Something asked of the bridge cannot be done; the message says what and what there is instead."""


class RequestError(BridgeError):
    """A request file that cannot be used: bad JSON, an unknown or missing field, a wrong type."""


# --- the set's space and the studio's ------------------------------------------------------------------------------


def _turned(x: float, z: float, degrees: float) -> tuple[float, float]:
    """(x, z) turned about the vertical as a figure's yaw turns it: (0, 1) goes to (sin, cos)."""
    s, c = math.sin(math.radians(degrees)), math.cos(math.radians(degrees))
    return (x * c + z * s, -x * s + z * c)


def _wrapped(degrees: float) -> float:
    """An angle within half a turn: -180 < a <= 180."""
    a = (degrees + 180.0) % 360.0 - 180.0
    return 180.0 if a == -180.0 else a


@dataclass(frozen=True)
class Stage:
    """How a film stands in a set: the set's camera, the point of the set that is the studio's origin, the turn
    about the vertical (degrees) that brings the studio's +z to where the set's camera is, and how many of the
    set's metres a metre of the studio is. `location` names the set, the shot and the mark when there is one."""

    camera: clip_record.Camera
    origin: tuple[float, float, float] = (0.0, 0.0, 0.0)
    turn_deg: float = 0.0
    scale: float = 1.0
    location: Optional[Mapping[str, str]] = None

    def to_studio(self, point: Sequence[float]) -> tuple[float, float, float]:
        d = [(p - o) / self.scale for p, o in zip(point, self.origin)]
        x, z = _turned(d[0], d[2], -self.turn_deg)
        return (x, d[1], z)

    def to_set(self, point: Sequence[float]) -> tuple[float, float, float]:
        x, z = _turned(point[0], point[2], self.turn_deg)
        return (self.origin[0] + self.scale * x, self.origin[1] + self.scale * point[1], self.origin[2] + self.scale * z)

    def yaw(self, facing_deg: float) -> float:
        """The yaw, in the studio, of a figure that faces `facing_deg` in the set."""
        return _wrapped(facing_deg - self.turn_deg)

    def facing(self, yaw: float) -> float:
        return _wrapped(yaw + self.turn_deg)


def camera_of(shot, width: int, height: int) -> clip_record.Camera:
    """An srlocations Shot as the record's camera: `compiler.Projection`'s numbers under the record's names (as
    srstudio's exporter writes a location's)."""
    view = Projection(shot, width, height)
    fits = {"width": shot.lens * width / view.SENSOR[0], "height": shot.lens * height / view.SENSOR[1]}
    fit = next((side for side, focal in fits.items() if math.isclose(view.focal, focal, rel_tol=1e-12)), None)
    if fit is None:
        raise BridgeError(f"a focal length of {view.focal} px fits neither side of a {width}x{height} frame")
    column = [tuple(float(view.basis[row][c]) for row in range(3)) for c in range(3)]
    return clip_record.Camera(
        eye=tuple(float(v) for v in shot.eye), look_at=tuple(float(v) for v in shot.look_at), lens_mm=float(shot.lens),
        gate_mm=(float(view.SENSOR[0]), float(view.SENSOR[1])), fit=fit, focal_px=float(view.focal),
        near_m=float(view.NEAR), right=column[0], up=column[1], forward=column[2],
        frame=clip_record.Frame(width, height))


def stage_of(film: films.Film) -> Stage:
    """The film's stage: the one `from_shot()` gave it, else the film's own space and camera as they are."""
    stage = getattr(film, "stage", None)
    if stage is not None:
        return stage
    if "film" not in film.loc.shots:
        raise BridgeError("the film has no camera: film.camera(eye, look_at, lens)")
    return Stage(camera_of(film.loc.shots["film"], *film.size))


# --- a location record, as much of it as a cutout needs ------------------------------------------------------------


@dataclass(frozen=True)
class Placement:
    """A mark of a location record in one of its shots."""

    frame: clip_record.Frame
    camera: clip_record.Camera
    at: tuple[float, float, float]
    facing_deg: float
    height_m: float
    feet_px: Optional[tuple[float, float]]
    pixels_per_metre: float
    location: Mapping[str, str]


def read_location(path: Union[str, Path], shot: str, mark: str) -> Placement:
    """A shot's camera and a mark's place from srstudio's location record (`srstudio.location_bridge`, schema 1.x).
    It reads what a cutout needs and checks that much: strict JSON, the schema's major, the camera against itself
    (`clip_record.check_camera`, the rules of srstudio's reader) and the mark's pixels against that camera. The whole
    record is srstudio's to vouch for: it reads it with its own reader before it uses the clip."""
    path = Path(path)
    try:
        with open(path, "rb") as handle:
            raw = handle.read(MAX_LOCATION_BYTES + 1)
    except OSError as error:
        raise BridgeError(f"cannot read the location record {path}: {error}") from None
    if len(raw) > MAX_LOCATION_BYTES:
        raise BridgeError(f"a location record is at most {MAX_LOCATION_BYTES} bytes; {path} has more")
    try:
        data = json.loads(raw.decode("utf-8"), parse_constant=clip_record._no_constant,
                          object_pairs_hook=clip_record._unique_keys)
        if not isinstance(data, dict):
            raise BridgeError(f"{path} is not a location record: a JSON object with shots")
        version = data.get("schema_version")
        if not isinstance(version, str) or version.split(".")[0] != LOCATION_MAJOR:
            raise BridgeError(f"{path}: this bridge reads location records of schema {LOCATION_MAJOR}.x, not {version!r}")
        frame = clip_record._frame(data.get("frame"))
        shots = {item.get("name"): item for item in data.get("shots", ()) if isinstance(item, dict)}
        if shot not in shots:
            raise BridgeError(f"no shot {shot!r} in {path.name}; it has {', '.join(map(str, shots))}")
        camera = clip_record.camera_from_data(shots[shot].get("camera"), f"shot {shot!r}: camera", frame)
        clip_record.check_camera(camera, f"shot {shot!r}: camera")
        marks = {item.get("mark"): item for item in shots[shot].get("marks", ()) if isinstance(item, dict)}
        if mark not in marks:
            raise BridgeError(f"no mark {mark!r} in shot {shot!r}; it has {', '.join(map(str, marks))}")
        m, where = marks[mark], f"mark {mark!r}"
        at = clip_record._vec3(m.get("at_m"), f"{where}.at_m")
        facing = clip_record._number(m.get("facing_deg"), f"{where}.facing_deg")
        tall = clip_record._number(m.get("height_m"), f"{where}.height_m")
        feet = clip_record._pixel(m.get("feet_px"), f"{where}.feet_px")
        scale = clip_record._number(m.get("pixels_per_metre"), f"{where}.pixels_per_metre")
        source = data.get("location")
        if not isinstance(source, dict):
            raise BridgeError(f"{path}: a location record names its location")
        location = {"name": clip_record._text(source.get("name"), "location.name", clip_record._ITEM),
                    "version": clip_record._text(source.get("version"), "location.version", clip_record._SEMVER),
                    "digest": clip_record._text(source.get("digest"), "location.digest", clip_record._DIGEST),
                    "shot": shot, "mark": mark, "record_sha256": hashlib.sha256(raw).hexdigest()}
    except (UnicodeDecodeError, json.JSONDecodeError, clip_record.ClipRecordError) as error:
        raise BridgeError(f"{path} is not a location record this bridge can use: {error}") from None
    expected = camera.project(at)
    if (expected is None) != (feet is None) or (expected and feet and max(abs(a - b) for a, b in zip(expected, feet)) > 1e-4):
        raise BridgeError(f"{path}: mark {mark!r} at {at} is recorded at {feet} px; its camera puts it at {expected}")
    if expected is None:
        raise BridgeError(f"mark {mark!r} is behind the camera of shot {shot!r}: a character there is not in the picture")
    return Placement(frame, camera, at, facing, tall, feet, scale, location)


# --- a film on a mark ----------------------------------------------------------------------------------------------


def from_shot(record_path: Union[str, Path], shot: str, mark: str, who: str, pose: str = "idle", fps: float = 30,
              *, facing_deg: Optional[float] = None, height_m: Optional[float] = None, name: Optional[str] = None,
              **fields: Any) -> tuple[films.Film, films.Actor]:
    """A film of the record's frame size with that shot's camera and the character standing on that mark, facing
    as the mark faces (`facing_deg` gives another way: 0 faces +z in the set, 90 faces +x) and at its own size
    (`height_m`: how tall it stands in the set, see the module's text). `fields` are the figure's own, as for
    `Film.add()`. Gives the film and its actor: have it act, then `cutout(film, folder, seconds)`.

    The film is in the studio's space (the character at the origin, the camera on +z): a point of the set is
    `film.stage.to_studio(point)` there, and a direction to turn to is `film.stage.yaw(facing_deg)`."""
    if "height" in fields:
        raise BridgeError("a figure's `height` field moves its joints and leaves its drawn parts the size they were: "
                          "say how tall the character stands in the set with height_m=")
    if "at" in fields or "yaw" in fields:
        raise BridgeError("the mark says where the character stands and how it faces: use facing_deg= to turn it")
    placed = read_location(record_path, shot, mark)
    try:
        own = float(mascots3d.figure(who, pose).stature()) if who in films.CAST else 1.0
    except Exception:      # an unknown pose: Film.add() below says so in its own words
        own = 1.0
    if height_m is not None and not 0 < height_m <= clip_record.MAX_HEIGHT_M:
        raise BridgeError(f"height_m is above 0 and at most {clip_record.MAX_HEIGHT_M} m, not {height_m!r}")
    scale = 1.0 if height_m is None else float(height_m) / own
    eye = placed.camera.eye
    level = math.hypot(eye[0] - placed.at[0], eye[2] - placed.at[2])
    turn = math.degrees(math.atan2(eye[0] - placed.at[0], eye[2] - placed.at[2])) if level > 1e-9 else 0.0
    stage = Stage(placed.camera, placed.at, turn, scale, placed.location)
    f = films.Film(f"{who}-on-{mark}", size=(placed.frame.width, placed.frame.height), fps=fps)
    f.stage = stage
    try:
        actor = f.add(who, pose, at=(0.0, 0.0, 0.0), yaw=stage.yaw(placed.facing_deg if facing_deg is None else facing_deg),
                      name=name, **fields)
    except films.FilmError as error:
        raise BridgeError(str(error)) from None
    f.camera(stage.to_studio(eye), stage.to_studio(placed.camera.look_at), lens=placed.camera.lens_mm)
    # the studio's camera shows the studio what the set's camera shows the set: the mark's own pixels say so
    view = Projection(f.loc.shots["film"], *f.size)
    for point in (placed.at, (placed.at[0], placed.at[1] + own * scale, placed.at[2])):
        ours, theirs = view.pixel(Vec3(*stage.to_studio(point))), placed.camera.project(point)
        if ours is None and theirs is None and point is not placed.at:      # its head is behind the camera in both
            continue
        if ours is None or theirs is None or max(abs(a - b) for a, b in zip(ours, theirs)) > PIXEL:
            raise BridgeError(f"the studio's camera puts {point} at {ours} and the set's at {theirs}")
    return f, actor


# --- speech --------------------------------------------------------------------------------------------------------


def _words(words: object) -> list[tuple[str, float, float]]:
    if not isinstance(words, (list, tuple)) or not words:
        raise BridgeError("a take has words: [{text, start, end}, ...], seconds from the take's start")
    out, before = [], 0.0
    for k, word in enumerate(words):
        if not isinstance(word, Mapping) or not {"text", "start", "end"} <= set(word):
            raise BridgeError(f"word {k} is {{text, start, end}}, not {word!r}")
        text, start, end = word["text"], word["start"], word["end"]
        if not isinstance(text, str) or not text or any(c.isspace() for c in text):
            raise BridgeError(f"word {k} is one word of text with no space in it, not {text!r}")
        for value in (start, end):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise BridgeError(f"word {k} ({text!r}) has times in seconds, not {value!r}")
        if not before <= start <= end:
            raise BridgeError(f"word {k} ({text!r}) runs {start} to {end} s: a word ends after it starts and starts "
                              f"no earlier than the one before ({before} s)")
        out.append((text, float(start), float(end)))
        before = float(start)
    return out


def alignment_from_words(words: Sequence[Mapping[str, Any]]) -> dict[str, list]:
    """Word times (sreditor's takes: `words: [{text, start, end}]`, seconds from the take's start) as the character
    timestamps `Actor.say()` and `speech.lipsync()` read (ElevenLabs' `alignment`): the letters of each word share
    its span evenly (at least LETTER_FLOOR for the word), and a space between two words spans the gap between them.
    A word that starts before the last one ended starts where that one ended. It is srstudio's own adapter
    (`supplied.spread`), so a mouth moves here as srstudio would time it."""
    chars: list[str] = []
    starts: list[float] = []
    ends: list[float] = []
    for k, (text, start, end) in enumerate(_words(words)):
        a = max(start, ends[-1] if ends else 0.0)
        span = max(end - a, LETTER_FLOOR)
        if k:
            chars.append(" ")
            starts.append(ends[-1])
            ends.append(a)
        step = span / len(text)
        for j, c in enumerate(text):
            chars.append(c)
            starts.append(round(a + j * step, 6))
            ends.append(round(a + (j + 1) * step, 6))
    return {"characters": chars, "character_start_times_seconds": starts, "character_end_times_seconds": ends}


def say_take(actor: films.Actor, take: Mapping[str, Any], at: float, audio: Union[str, Path, None] = None) -> films.Actor:
    """The actor speaks a take (`{"id": ..., "words": [{text, start, end}, ...]}`) from `at` seconds: its mouth
    follows the words, and with `audio` (the take's voice) opens wider on what is said louder. Nothing is heard
    and nothing is subtitled, since the voice and the captions are the episode's; the take is written in the clip's
    record (its id, its words, the SHA-256 of `audio`)."""
    if not isinstance(take, Mapping) or not isinstance(take.get("id"), str) or not take["id"]:
        raise BridgeError("a take is {id, words}: its id names it in the clip's record")
    if isinstance(at, bool) or not isinstance(at, (int, float)) or not math.isfinite(at) or at < 0:
        raise BridgeError(f"a take starts at 0 s or later, not {at!r}")
    words = _words(take.get("words"))
    if audio is not None and not Path(audio).is_file():
        raise BridgeError(f"no voice file {audio}")
    actor.mouths += speech.lipsync(alignment_from_words(take["words"]), at=float(at), audio=audio)
    spoken = getattr(actor, "takes", None)
    if spoken is None:
        spoken = actor.takes = []
    spoken.append({"figure": actor.fig.name, "take": take["id"], "at_s": float(at),
                   "words": [{"text": t, "start_s": a, "end_s": b} for t, a, b in words],
                   "audio_sha256": None if audio is None else clip_record.sha256(audio)})
    return actor


# --- the cutout ----------------------------------------------------------------------------------------------------


def producer() -> dict[str, Any]:
    """Who draws: the commit of this package and whether its files differ from it, and srlocations' version."""
    def git(*words: str) -> Optional[str]:
        try:
            done = subprocess.run(["git", "-C", str(ROOT), *words], text=True, capture_output=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return done.stdout if done.returncode == 0 else None

    top, commit, status = git("rev-parse", "--show-toplevel"), git("rev-parse", "HEAD"), git("status", "--porcelain")
    ours = top is not None and Path(top.strip()).resolve() == ROOT      # not a repository that merely holds this folder
    commit = commit.strip() if ours and commit and clip_record._COMMIT.fullmatch(commit.strip()) else None
    try:
        version = metadata.version("srlocations")
    except metadata.PackageNotFoundError:
        version = "0.0.0"
    return {"package": clip_record.PACKAGE, "commit": commit, "dirty": commit is None or status is None or bool(status.strip()),
            "srlocations": version}


def _png(path: Path) -> tuple[int, int, int, int]:
    """(width, height, bit depth, colour type) of a PNG file, from its header."""
    with open(path, "rb") as handle:
        head = handle.read(26)
    if len(head) < 26 or head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        raise BridgeError(f"{path} is not a PNG file")
    return struct.unpack(">IIBB", head[16:26])


def _figure_at(now, name: str):
    for node in now.nodes:
        if isinstance(node, mascots3d.MascotFigure) and node.name == name:
            return node
    raise BridgeError(f"no figure {name!r} in the film at this moment")


def _head(parts: Sequence[Mapping[str, Any]], name: str) -> tuple[float, float, float]:
    """The middle of a figure's head on an exported frame: of the box round its head part (its body, if it has no
    head of its own)."""
    for wanted in ("head/head", "body/body", None):
        found = [p["verts"] for p in parts if p["figure"] == name and (wanted is None or p["name"] == wanted)]
        if found:
            xs, ys, zs = ([c for verts in found for c in verts[k::3]] for k in range(3))
            return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2)
    raise BridgeError(f"the exported frame draws nothing of {name!r}")


def cutout(film: films.Film, out_dir: Union[str, Path], seconds: float, finish: str = "lowpoly",
           quality: Union[str, Mapping[str, Any]] = "standard", device: str = "OPTIX") -> Path:
    """The film's cast alone on a transparent film: performs it for `seconds` (if it is not yet), exports it,
    has Blender draw every frame at the film's full size with alpha, and writes `out_dir/frames/00000.png` ...
    and `out_dir/clip.json` (see `characters.clip_record`). Gives the record's path, after reading it back with
    `clip_record.load()`: every frame there, with the size and the SHA-256 the record says.

    `finish` is "lowpoly", the one finish that writes alpha. `quality` is a name of `blender.QUALITY` or its own
    settings; whatever it says, the frames are drawn at full size. What was in `out_dir` of an earlier cutout
    (frames, record) is replaced. The camera does not move in a cutout, and set pieces added with `prop()` would
    be drawn into it: a film for a cutout holds its cast and nothing else."""
    if finish not in ALPHA_FINISHES:
        raise BridgeError(f"no cutout in the finish {finish!r}: {', '.join(ALPHA_FINISHES)} writes alpha "
                          f"(fur, terry and vinyl draw a studio behind the figure)")
    if isinstance(quality, str) and quality not in blender.QUALITY:
        raise BridgeError(f"no quality {quality!r}; there are {', '.join(blender.QUALITY)}")
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds <= 0:
        raise BridgeError(f"a cutout lasts more than 0 s, not {seconds!r}")
    stage = stage_of(film)
    width, height = film.size
    count = int(round(seconds * film.fps))
    if count < 1:
        raise BridgeError(f"{seconds} s at {film.fps} frames a second is no frame")
    if count > clip_record.MAX_FRAMES:
        raise BridgeError(f"a cutout holds at most {clip_record.MAX_FRAMES} frames, not {count}")
    try:
        if film._performed is None:
            film.perform(float(seconds))
        elif abs(film._performed - seconds) > 1e-9:
            raise BridgeError(f"the film is performed for {film._performed} s, not {seconds} s")
    except films.FilmError as error:
        raise BridgeError(str(error)) from None

    out_dir = Path(out_dir)
    frames, work, record_path = out_dir / "frames", out_dir / ".work", out_dir / "clip.json"
    for stale in (frames, work):
        if stale.exists():
            shutil.rmtree(stale)
    record_path.unlink(missing_ok=True)
    frames.mkdir(parents=True)
    film.export(work / "export")

    # where each figure is on each frame, in the set's space: its place on the ground, the middle of its head
    placed: list[list[dict[str, Any]]] = []
    shot = film.loc.shots["film"]
    for k in range(count):
        now = film.loc.at(k / film.fps)
        if (tuple(now.shots["film"].eye), tuple(now.shots["film"].look_at), now.shots["film"].lens) != \
                (tuple(shot.eye), tuple(shot.look_at), shot.lens):
            raise BridgeError("the camera moves in this film: a cutout has one camera for the whole clip")
        parts = json.loads((work / "export" / f"{k:04d}.json").read_text())["parts"]
        row = []
        for actor in film.actors:
            node = _figure_at(now, actor.fig.name)
            root, base = node.transform.position, Vec3.of(node.at)
            feet = stage.to_set((root.x, base.y + float(getattr(node, "step_y", 0.0)), root.z))
            head = stage.to_set(_head(parts, actor.fig.name))
            feet_px, head_px = stage.camera.project(feet), stage.camera.project(head)
            row.append({"feet_m": list(feet), "head_m": list(head),
                        "feet_px": None if feet_px is None else list(feet_px),
                        "head_px": None if head_px is None else list(head_px),
                        "pixels_per_metre": stage.camera.pixels_per_metre(feet)})
        placed.append(row)

    settings = {**(blender.QUALITY[quality] if isinstance(quality, str) else dict(quality)), "scale": 1.0, "alpha": True}
    started = time.time()
    try:
        blender.render(work / "export", work / "png", finish, settings, device, log=out_dir / "render.log")
    except blender.BlenderError as error:
        raise BridgeError(str(error)) from error
    took = time.time() - started

    listed = []
    for k in range(count):
        source, name = work / "png" / f"{k:04d}.png", clip_record.PATTERN % k
        if _png(source) != (width, height, 8, 6):
            raise BridgeError(f"frame {k} is {_png(source)} (width, height, bits, PNG colour type); a cutout frame is "
                              f"{(width, height, 8, 6)}: 8-bit RGBA at the film's size")
        source.replace(out_dir / name)
        listed.append({"file": name, "sha256": clip_record.sha256(out_dir / name), "bytes": (out_dir / name).stat().st_size,
                       "figures": placed[k]})
    shutil.rmtree(work)

    data = {
        "schema": clip_record.SCHEMA,
        "producer": producer(),
        "finish": finish,
        "alpha": clip_record.ALPHA,
        "frame": {"width_px": width, "height_px": height},
        "fps": film.fps,
        "frame_count": count,
        "duration_s": count / film.fps,
        "sequence": {"pattern": clip_record.PATTERN, "first": 0},
        "camera": stage.camera.to_data(),
        "location": None if stage.location is None else dict(stage.location),
        "figures": [{"name": actor.fig.name, "who": actor.who, "at_m": placed[0][n]["feet_m"],
                     "facing_deg": stage.facing(float(actor.fig.yaw)),
                     "height_m": float(actor.fig.stature()) * stage.scale, "scale": stage.scale}
                    for n, actor in enumerate(film.actors)],
        "speech": [take for actor in film.actors for take in getattr(actor, "takes", ())],
        "frames": listed,
    }
    try:
        clip_record.from_data(json.loads(clip_record.dumps(data)))      # nothing is written that the reader refuses
    except clip_record.ClipRecordError as error:
        raise BridgeError(f"the cutout's own record does not hold together: {error}") from error
    record_path.write_text(clip_record.dumps(data))
    clip_record.load(record_path)                                       # and the frames are the ones it names
    size = sum(item["bytes"] for item in listed)
    print(f"cutout: {count} frames {width}x{height} in {took:.0f} s ({took / count:.2f} s a frame with Blender's start), "
          f"{size / count / 1024:.0f} KiB a frame, {record_path}", flush=True)
    return record_path


# --- the command line ----------------------------------------------------------------------------------------------

REQUEST_KEYS = ("schema", "location", "shot", "mark", "who", "seconds")
REQUEST_OPTIONAL = ("pose", "fps", "facing_deg", "height_m", "name", "finish", "quality", "actions", "takes")
ACTION_KEYS, ACTION_OPTIONAL = ("at", "do"), ("side", "scale", "seconds", "seed")
TAKE_KEYS, TAKE_OPTIONAL = ("id", "at", "words"), ("audio",)


def parse_request(text: Union[str, bytes]) -> dict[str, Any]:
    """A cutout request from its JSON text: one closed object (an unknown field is refused, as in the record).

        {"schema": "characters.cutout-request/1.0.0",
         "location": "airliner-1080x1920.json",        a location record; a relative path is from the request's folder
         "shot": "down-the-aisle", "mark": "aisle", "who": "anchor", "seconds": 3.0,
         "pose": "idle", "fps": 30,                     optional, these are the defaults
         "facing_deg": 180.0,                           optional: the mark's facing when left out or null
         "height_m": 1.7,                               optional: the character's own size when left out or null
         "name": "anchor", "finish": "lowpoly", "quality": "standard",
         "actions": [{"at": 0.4, "do": "wave", "side": "right", "scale": 1.0, "seconds": null, "seed": null}],
         "takes": [{"id": "take-1", "at": 0.5, "audio": null,
                    "words": [{"text": "Boa", "start": 0.0, "end": 0.22}]}]}

    An action is `Actor.do()`'s (a name of `film.can(who)["actions"]`); a take is `say_take()`'s."""
    if len(text) > MAX_REQUEST_BYTES:
        raise RequestError(f"a cutout request is at most {MAX_REQUEST_BYTES} bytes, not {len(text)}")
    try:
        if isinstance(text, bytes):
            text = text.decode("utf-8")
        data = json.loads(text, parse_constant=clip_record._no_constant, object_pairs_hook=clip_record._unique_keys)
        top = dict(clip_record._fields(data, "request", REQUEST_KEYS, REQUEST_OPTIONAL))
        if top["schema"] != REQUEST:
            raise RequestError(f"request.schema is {REQUEST!r}, not {top['schema']!r}")
        for key in ("location", "shot", "mark", "who"):
            clip_record._name(top[key], f"request.{key}")
        for key in ("pose", "name", "finish"):
            if top.get(key) is not None:
                clip_record._name(top[key], f"request.{key}")
        if not isinstance(top.get("quality", "standard"), (str, dict)):
            raise RequestError("request.quality is a quality's name or its settings")
        for key in ("seconds", "fps", "facing_deg", "height_m"):
            if top.get(key) is not None:
                top[key] = clip_record._number(top[key], f"request.{key}")
        if top["seconds"] <= 0 or (top.get("fps") is not None and not 0 < top["fps"] <= clip_record.MAX_FPS):
            raise RequestError(f"request.seconds is above 0 and request.fps above 0 and at most {clip_record.MAX_FPS:g}, "
                               f"not {top['seconds']} and {top.get('fps')}")
        actions = []
        for i, item in enumerate(clip_record._list(top.get("actions", []), "request.actions", 256)):
            a = dict(clip_record._fields(item, f"request.actions[{i}]", ACTION_KEYS, ACTION_OPTIONAL))
            a["at"] = clip_record._number(a["at"], f"request.actions[{i}].at")
            clip_record._name(a["do"], f"request.actions[{i}].do")
            if a.get("side") is not None and a["side"] not in ("left", "right"):
                raise RequestError(f"request.actions[{i}].side is 'left' or 'right', not {a['side']!r}")
            for key in ("scale", "seconds"):
                if a.get(key) is not None:
                    a[key] = clip_record._number(a[key], f"request.actions[{i}].{key}")
            if a.get("seed") is not None:
                clip_record._int(a["seed"], f"request.actions[{i}].seed")
            actions.append(a)
        takes = []
        for i, item in enumerate(clip_record._list(top.get("takes", []), "request.takes", clip_record.MAX_TAKES)):
            t = dict(clip_record._fields(item, f"request.takes[{i}]", TAKE_KEYS, TAKE_OPTIONAL))
            clip_record._name(t["id"], f"request.takes[{i}].id")
            t["at"] = clip_record._number(t["at"], f"request.takes[{i}].at")
            for k, word in enumerate(clip_record._list(t["words"], f"request.takes[{i}].words", clip_record.MAX_WORDS)):
                clip_record._fields(word, f"request.takes[{i}].words[{k}]", ("text", "start", "end"))
            if t.get("audio") is not None:
                clip_record._name(t["audio"], f"request.takes[{i}].audio")
            takes.append(t)
        top["actions"], top["takes"] = actions, takes
    except (UnicodeDecodeError, json.JSONDecodeError, clip_record.ClipRecordError) as error:
        raise RequestError(f"a cutout request is one strict JSON object: {error}") from None
    return top


def run(request: Mapping[str, Any], out_dir: Union[str, Path], base: Union[str, Path] = ".") -> Path:
    """Draws the cutout a parsed request asks for into `out_dir`; relative paths in it are from `base`."""
    base = Path(base)
    fps = request.get("fps") or 30
    f, actor = from_shot(base / request["location"], request["shot"], request["mark"], request["who"],
                         request.get("pose") or "idle", int(fps) if float(fps).is_integer() else fps,
                         facing_deg=request.get("facing_deg"), height_m=request.get("height_m"), name=request.get("name"))
    try:
        for a in request.get("actions", ()):
            more = {k: a[k] for k in ("seconds", "seed") if a.get(k) is not None}
            actor.do(a["at"], a["do"], side=a.get("side") or "right", scale=1.0 if a.get("scale") is None else a["scale"], **more)
    except films.FilmError as error:
        raise BridgeError(str(error)) from None
    for t in request.get("takes", ()):
        say_take(actor, t, t["at"], None if t.get("audio") is None else base / t["audio"])
    return cutout(f, out_dir, request["seconds"], request.get("finish") or "lowpoly", request.get("quality") or "standard")


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2 or argv[0] in ("-h", "--help"):
        print("usage: python -m characters.bridge REQUEST.json OUT_DIR\n\n" + (parse_request.__doc__ or ""), file=sys.stderr)
        return 2
    path = Path(argv[0])
    try:
        with open(path, "rb") as handle:
            raw = handle.read(MAX_REQUEST_BYTES + 1)
    except OSError as error:
        print(f"bridge: cannot read the request {path}: {error}", file=sys.stderr)
        return 2
    try:
        print(run(parse_request(raw), argv[1], path.resolve().parent))
    except BridgeError as error:
        print(f"bridge: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
