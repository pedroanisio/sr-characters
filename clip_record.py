"""A cutout clip as data: the record `characters.bridge.cutout()` writes beside its frames, and its strict reader.

A cutout is an acted character drawn alone on a transparent film: numbered RGBA PNG frames (`frames/00000.png` ...,
straight alpha, the character's shadow on the ground in the alpha) and one `clip.json` that says what they are, so
another program can lay them over a set without running this package:

    record = clip_record.load("out/anchor/clip.json")      # refuses anything it cannot vouch for
    record.frame.width, record.fps, record.frame_count
    record.pattern, record.first                            # "frames/%05d.png", 0: an image sequence as it is named
    record.frames[45].figures[0].feet_px                    # where the character stands in frame 45, in pixels
    record.camera.project((0.0, 1.0, 3.0))                  # any point of the set, with the camera the clip was drawn by

The record is untrusted until it parses. `parse()` takes its text: one strict JSON object (no NaN or Infinity, no key
twice, at most `MAX_BYTES`), closed (an unknown or a missing field is refused), of schema `characters.clip/1.x.y`.
Then every number is checked against the others: the frame count against the duration and the frames a second, the
camera's focal length against its lens, the gate and the frame, its axes against where it looks, and on every frame
each figure's feet, head and scale against where that camera puts them. `load()` reads the file and, with `files`
(the default), also opens every frame it names: present, of the size written, with the SHA-256 written. What is
refused is refused with its own error (see the classes), and the message says what was found and what was expected.

Units are in the field names, as in srstudio's location record (ADR 0179), and the camera has that record's fields
under the same names: metres (`_m`), millimetres (`_mm`), degrees (`_deg`), seconds (`_s`), pixels (`_px`, from the
frame's top left, y down). World axes are srlocations': x right, y up, z away. A point `d` metres from the eye lands at
`(width / 2 + focal * d.right / d.forward, height / 2 - focal * d.up / d.forward)`.

    {"schema": "characters.clip/1.0.0",
     "producer": {"package": "sr-characters", "commit": "<40 hex> or null", "dirty": true, "srlocations": "0.1.0"},
     "finish": "lowpoly", "alpha": "straight",
     "frame": {"width_px": 1080, "height_px": 1920}, "fps": 30, "frame_count": 90, "duration_s": 3.0,
     "sequence": {"pattern": "frames/%05d.png", "first": 0},
     "camera": {"eye_m": [..], "look_at_m": [..], "lens_mm": 15.0, "gate_mm": [36.0, 24.0], "fit": "height",
                "focal_px": 1200.0, "near_m": 0.05, "right": [..], "up": [..], "forward": [..]},
     "location": null or {"name": "airliner", "version": "1.0.1", "digest": "<64 hex>", "shot": "down-the-aisle",
                          "mark": "aisle", "record_sha256": "<64 hex>"},
     "figures": [{"name": "anchor", "who": "anchor", "at_m": [..], "facing_deg": 180.0, "height_m": 1.0, "scale": 1.0}],
     "speech": [{"figure": "anchor", "take": "take-1", "at_s": 0.5, "audio_sha256": null,
                 "words": [{"text": "Boa", "start_s": 0.0, "end_s": 0.22}]}],
     "frames": [{"file": "frames/00000.png", "sha256": "<64 hex>", "bytes": 61234,
                 "figures": [{"feet_m": [..], "head_m": [..], "feet_px": [540.0, 1300.47], "head_px": [..],
                              "pixels_per_metre": 279.07}]}]}

`figures[].at_m` is where the figure stands on the first frame and `facing_deg` the way it then faces (0 faces +z,
90 faces +x: a mark's `facing_deg`); `height_m` is how tall it stands in the set and `scale` the set's metres to one
metre of the character's own (1.0: drawn at its own size). A frame's `figures` are in the same order: `feet_m` is the
point of the ground the figure stands over (it stays on the ground while the figure jumps), `head_m` the middle of
its head, both in the set's metres, and `feet_px`, `head_px` where the camera puts them (null behind the camera);
`pixels_per_metre` is the scale at the feet. A take's word times are seconds from the take's start; the take starts
`at_s` into the clip.

This module imports only the standard library, so a program that cannot import `characters` (srstudio keeps its own
interpreter) can load it by its file path, as srstudio's exporter loads srstudio's readers into srlocations':

    spec = importlib.util.spec_from_file_location("clip_record", ".../characters/clip_record.py")
    clip_record = importlib.util.module_from_spec(spec)
    sys.modules["clip_record"] = clip_record        # before exec: dataclasses look their module up by name
    spec.loader.exec_module(clip_record)
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Union

NAME = "characters.clip"
SCHEMA_VERSION = "1.0.0"
SCHEMA = f"{NAME}/{SCHEMA_VERSION}"
PACKAGE = "sr-characters"
GATE_MM = (36.0, 24.0)             # srlocations' film gate (compiler.Projection.SENSOR)
PATTERN = "frames/%05d.png"        # the one way frames are named, relative to the record's folder
ALPHA = "straight"                 # PNG's own: colour not multiplied by alpha
MAX_BYTES = 16_000_000             # a frame of one figure is about 450 bytes of record: half an hour at 30 a second
MAX_FRAMES = 60_000
MAX_FRAME_PX = 16_384
MAX_FRAME_BYTES = 256 << 20        # one PNG
MAX_FIGURES = 32
MAX_TAKES, MAX_WORDS = 256, 4096
MAX_NAME = 128
MAX_HEIGHT_M = 3.0
MAX_FPS = 240.0
TOLERANCE = 1e-6                   # relative to the size of the number, at least this absolute

Vec3 = tuple[float, float, float]
Pixel = tuple[float, float]

_SCHEMA = re.compile(r"([a-z][a-z0-9.-]*)/((0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*))")
_SEMVER = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:[-+.][0-9A-Za-z.+-]{1,64})?")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_DIGEST = re.compile(r"[0-9a-f]{64}")
_ITEM = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class ClipRecordError(ValueError):
    """Anything this module refuses."""


class ClipFormatError(ClipRecordError):
    """Not one strict JSON record of this schema: bad JSON, too many bytes, an unknown or missing field, a wrong type,
    a number that is not finite, or text outside its pattern."""


class ClipSchemaError(ClipRecordError):
    """A record of another kind, or of a schema major this reader does not know."""


class ClipValueError(ClipRecordError):
    """Well formed, but its numbers contradict each other."""


class ClipCountError(ClipValueError):
    """The frames listed, the frame count, the duration and the frames a second do not agree."""


class ClipCameraError(ClipValueError):
    """The camera contradicts itself: its focal length is not its lens on the gate fitted to the frame, or its axes
    are not a level camera that looks at its target."""


class ClipProjectionError(ClipValueError):
    """A figure's pixels on a frame are not where the camera puts its place in the set."""


class ClipFileError(ClipRecordError):
    """A frame the record names is missing, is not a file inside the record's folder, or is not the file recorded
    (its size or its SHA-256 differs)."""


@dataclass(frozen=True)
class Frame:
    width: int
    height: int


@dataclass(frozen=True)
class Camera:
    """The clip's camera as srlocations' `compiler.Projection` computes it; the same fields as the location record's."""

    eye: Vec3
    look_at: Vec3
    lens_mm: float
    gate_mm: tuple[float, float]
    fit: str                       # "width" | "height"
    focal_px: float
    near_m: float
    right: Vec3
    up: Vec3
    forward: Vec3
    frame: Frame

    def _along(self, point: Vec3) -> Vec3:
        d = (point[0] - self.eye[0], point[1] - self.eye[1], point[2] - self.eye[2])
        return (_dot(d, self.right), _dot(d, self.up), _dot(d, self.forward))

    def depth(self, point: Vec3) -> float:
        """How far in front of the camera `point` is, in metres along its view; negative behind it."""
        return self._along(point)[2]

    def project(self, point: Vec3) -> Optional[Pixel]:
        """Where a world point lands in the frame, in it or out of it; None behind the camera."""
        x, y, z = self._along(point)
        if z < self.near_m:
            return None
        return (self.frame.width / 2 + self.focal_px * x / z, self.frame.height / 2 - self.focal_px * y / z)

    def pixels_per_metre(self, point: Vec3) -> float:
        """Pixels to a metre across at `point`, capped at the near plane as srlocations caps it."""
        return self.focal_px / max(self.depth(point), self.near_m)

    def to_data(self) -> dict[str, object]:
        return {"eye_m": list(self.eye), "look_at_m": list(self.look_at), "lens_mm": self.lens_mm,
                "gate_mm": list(self.gate_mm), "fit": self.fit, "focal_px": self.focal_px, "near_m": self.near_m,
                "right": list(self.right), "up": list(self.up), "forward": list(self.forward)}


@dataclass(frozen=True)
class Producer:
    package: str
    commit: Optional[str]          # the commit of `characters` that drew it; None when it was not in a repository
    dirty: bool                    # the working tree differed from that commit
    srlocations: str               # the version of srlocations it was acted with


@dataclass(frozen=True)
class Location:
    """The set the clip was staged for: a catalog item of srlocations, the shot and the mark, and the SHA-256 of the
    location record they were read from."""

    name: str
    version: str
    digest: str
    shot: str
    mark: str
    record_sha256: str


@dataclass(frozen=True)
class Figure:
    name: str
    who: str
    at: Vec3
    facing_deg: float
    height_m: float
    scale: float


@dataclass(frozen=True)
class Word:
    text: str
    start_s: float
    end_s: float


@dataclass(frozen=True)
class Take:
    figure: str
    take: str
    at_s: float
    words: tuple[Word, ...]
    audio_sha256: Optional[str]


@dataclass(frozen=True)
class FigureInFrame:
    feet: Vec3
    head: Vec3
    feet_px: Optional[Pixel]
    head_px: Optional[Pixel]
    pixels_per_metre: float


@dataclass(frozen=True)
class ClipFrame:
    file: str
    sha256: str
    bytes: int
    figures: tuple[FigureInFrame, ...]


@dataclass(frozen=True)
class ClipRecord:
    schema: str
    producer: Producer
    finish: str
    alpha: str
    frame: Frame
    fps: float
    frame_count: int
    duration_s: float
    pattern: str
    first: int
    camera: Camera
    location: Optional[Location]
    figures: tuple[Figure, ...]
    speech: tuple[Take, ...]
    frames: tuple[ClipFrame, ...]

    @property
    def last(self) -> int:
        """The number of the last frame file."""
        return self.first + self.frame_count - 1

    def figure(self, name: str) -> int:
        """The place of a figure in `figures`, and in every frame's `figures`."""
        for index, figure in enumerate(self.figures):
            if figure.name == name:
                return index
        raise KeyError(f"no figure {name!r} in this clip; it has {', '.join(f.name for f in self.figures)}")

    def placed(self, frame: int, name: Optional[str] = None) -> FigureInFrame:
        """A figure on a frame (the only figure when none is named)."""
        return self.frames[frame].figures[0 if name is None else self.figure(name)]


# --- reading -------------------------------------------------------------------------------------------------------


def load(path: Union[str, Path], files: bool = True) -> ClipRecord:
    """The record at `path`. With `files`, every frame it names is opened too: there, the size and the SHA-256
    written (`ClipFileError`). The frames are looked for beside the record."""
    path = Path(path)
    try:
        with open(path, "rb") as handle:
            raw = handle.read(MAX_BYTES + 1)
    except OSError as error:
        raise ClipFormatError(f"cannot read the clip record {path}: {error}") from None
    record = parse(raw)
    if files:
        check_files(record, path.parent)
    return record


def parse(text: Union[str, bytes]) -> ClipRecord:
    """One record from its JSON text. The frames' files are not opened: `load()` or `check_files()` does that."""
    if len(text) > MAX_BYTES:
        raise ClipFormatError(f"a clip record is at most {MAX_BYTES} bytes, not {len(text)}")
    if isinstance(text, bytes):
        try:
            text = text.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ClipFormatError(f"a clip record is UTF-8 text: {error}") from None
    try:
        data = json.loads(text, parse_constant=_no_constant, object_pairs_hook=_unique_keys)
    except json.JSONDecodeError as error:
        raise ClipFormatError(f"a clip record is one JSON object: {error}") from None
    except RecursionError:
        raise ClipFormatError("a clip record is not nested this deep") from None
    return from_data(data)


TOP = ("schema", "producer", "finish", "alpha", "frame", "fps", "frame_count", "duration_s", "sequence", "camera",
       "location", "figures", "speech", "frames")


def from_data(data: object) -> ClipRecord:
    """A record from decoded JSON: what it is first, then its shape, then its numbers against each other."""
    if not isinstance(data, dict):
        raise ClipFormatError(f"a clip record is a JSON object, not {type(data).__name__}")
    schema = data.get("schema")
    found = _SCHEMA.fullmatch(schema) if isinstance(schema, str) else None
    if found is None:
        raise ClipFormatError(f"schema must read {NAME}/major.minor.patch, not {schema!r}")
    if found.group(1) != NAME:
        raise ClipSchemaError(f"this reader reads {NAME} records, not {found.group(1)!r}")
    if found.group(3) != SCHEMA_VERSION.split(".")[0]:
        raise ClipSchemaError(f"this reader reads schema {SCHEMA} and its minors, not {schema}")
    top = _fields(data, "record", TOP)
    alpha = top["alpha"]
    if alpha != ALPHA:
        raise ClipFormatError(f"alpha is {ALPHA!r} (colour not multiplied by alpha), not {alpha!r}")
    frame = _frame(top["frame"])
    sequence = _fields(top["sequence"], "sequence", ("pattern", "first"))
    if sequence["pattern"] != PATTERN:
        raise ClipFormatError(f"sequence.pattern is {PATTERN!r}, not {sequence['pattern']!r}")
    first = _int(sequence["first"], "sequence.first")
    figures = _list(top["figures"], "figures", MAX_FIGURES)
    frames = _list(top["frames"], "frames", MAX_FRAMES)
    record = ClipRecord(
        schema=schema,
        producer=_producer(top["producer"]),
        finish=_text(top["finish"], "finish", _ITEM),
        alpha=ALPHA,
        frame=frame,
        fps=_number(top["fps"], "fps"),
        frame_count=_int(top["frame_count"], "frame_count"),
        duration_s=_number(top["duration_s"], "duration_s"),
        pattern=PATTERN,
        first=first,
        camera=camera_from_data(top["camera"], "camera", frame),
        location=None if top["location"] is None else _location(top["location"]),
        figures=tuple(_figure(item, f"figures[{i}]") for i, item in enumerate(figures)),
        speech=tuple(_take(item, f"speech[{i}]") for i, item in enumerate(_list(top["speech"], "speech", MAX_TAKES))),
        frames=tuple(_clip_frame(item, f"frames[{i}]", len(figures)) for i, item in enumerate(frames)),
    )
    check(record)
    return record


def _producer(value: object) -> Producer:
    f = _fields(value, "producer", ("package", "commit", "dirty", "srlocations"))
    if f["package"] != PACKAGE:
        raise ClipFormatError(f"producer.package is {PACKAGE!r}, not {f['package']!r}")
    return Producer(PACKAGE, None if f["commit"] is None else _text(f["commit"], "producer.commit", _COMMIT),
                    _bool(f["dirty"], "producer.dirty"), _text(f["srlocations"], "producer.srlocations", _SEMVER))


def _frame(value: object) -> Frame:
    f = _fields(value, "frame", ("width_px", "height_px"))
    width, height = (_int(f[k], f"frame.{k}") for k in ("width_px", "height_px"))
    for key, size in (("width_px", width), ("height_px", height)):
        if not 0 < size <= MAX_FRAME_PX:
            raise ClipFormatError(f"frame.{key} is 1 to {MAX_FRAME_PX} pixels, not {size}")
    return Frame(width, height)


CAMERA_KEYS = ("eye_m", "look_at_m", "lens_mm", "gate_mm", "fit", "focal_px", "near_m", "right", "up", "forward")


def camera_from_data(value: object, path: str, frame: Frame) -> Camera:
    """A camera from its ten fields, the location record's (`shots[].camera`) and this record's alike. Its shape
    only: `check_camera()` checks its numbers."""
    f = _fields(value, path, CAMERA_KEYS)
    fit = f["fit"]
    if fit not in ("width", "height"):
        raise ClipFormatError(f"{path}.fit is 'width' or 'height', not {fit!r}")
    gate = _vector(f["gate_mm"], f"{path}.gate_mm", 2)
    return Camera(
        eye=_vec3(f["eye_m"], f"{path}.eye_m"),
        look_at=_vec3(f["look_at_m"], f"{path}.look_at_m"),
        lens_mm=_number(f["lens_mm"], f"{path}.lens_mm"),
        gate_mm=(gate[0], gate[1]),
        fit=str(fit),
        focal_px=_number(f["focal_px"], f"{path}.focal_px"),
        near_m=_number(f["near_m"], f"{path}.near_m"),
        right=_vec3(f["right"], f"{path}.right"),
        up=_vec3(f["up"], f"{path}.up"),
        forward=_vec3(f["forward"], f"{path}.forward"),
        frame=frame,
    )


def _location(value: object) -> Location:
    f = _fields(value, "location", ("name", "version", "digest", "shot", "mark", "record_sha256"))
    return Location(_text(f["name"], "location.name", _ITEM), _text(f["version"], "location.version", _SEMVER),
                    _text(f["digest"], "location.digest", _DIGEST), _name(f["shot"], "location.shot"),
                    _name(f["mark"], "location.mark"), _text(f["record_sha256"], "location.record_sha256", _DIGEST))


def _figure(value: object, path: str) -> Figure:
    f = _fields(value, path, ("name", "who", "at_m", "facing_deg", "height_m", "scale"))
    return Figure(_name(f["name"], f"{path}.name"), _text(f["who"], f"{path}.who", _ITEM), _vec3(f["at_m"], f"{path}.at_m"),
                  _number(f["facing_deg"], f"{path}.facing_deg"), _number(f["height_m"], f"{path}.height_m"),
                  _number(f["scale"], f"{path}.scale"))


def _take(value: object, path: str) -> Take:
    f = _fields(value, path, ("figure", "take", "at_s", "words", "audio_sha256"))
    words = []
    for i, item in enumerate(_list(f["words"], f"{path}.words", MAX_WORDS)):
        w = _fields(item, f"{path}.words[{i}]", ("text", "start_s", "end_s"))
        words.append(Word(_name(w["text"], f"{path}.words[{i}].text"), _number(w["start_s"], f"{path}.words[{i}].start_s"),
                          _number(w["end_s"], f"{path}.words[{i}].end_s")))
    audio = f["audio_sha256"]
    return Take(_name(f["figure"], f"{path}.figure"), _name(f["take"], f"{path}.take"), _number(f["at_s"], f"{path}.at_s"),
                tuple(words), None if audio is None else _text(audio, f"{path}.audio_sha256", _DIGEST))


def _clip_frame(value: object, path: str, figures: int) -> ClipFrame:
    f = _fields(value, path, ("file", "sha256", "bytes", "figures"))
    if not isinstance(f["file"], str):
        raise ClipFormatError(f"{path}.file is a frame's name, not {f['file']!r}")
    placed = _list(f["figures"], f"{path}.figures", MAX_FIGURES)
    if len(placed) != figures:
        raise ClipFormatError(f"{path}.figures places {len(placed)} figure(s); the clip has {figures}")
    out = []
    for i, item in enumerate(placed):
        p = _fields(item, f"{path}.figures[{i}]", ("feet_m", "head_m", "feet_px", "head_px", "pixels_per_metre"))
        out.append(FigureInFrame(_vec3(p["feet_m"], f"{path}.figures[{i}].feet_m"), _vec3(p["head_m"], f"{path}.figures[{i}].head_m"),
                                 _pixel(p["feet_px"], f"{path}.figures[{i}].feet_px"),
                                 _pixel(p["head_px"], f"{path}.figures[{i}].head_px"),
                                 _number(p["pixels_per_metre"], f"{path}.figures[{i}].pixels_per_metre")))
    return ClipFrame(f["file"], _text(f["sha256"], f"{path}.sha256", _DIGEST), _int(f["bytes"], f"{path}.bytes"), tuple(out))


# --- the numbers against each other --------------------------------------------------------------------------------


def check(record: ClipRecord) -> None:
    """Every number of a record against the others (see the module's text). `from_data()` calls it."""
    if not 0 < record.fps <= MAX_FPS:
        raise ClipCountError(f"fps is above 0 and at most {MAX_FPS:g}, not {record.fps}")
    if record.frame_count < 1:
        raise ClipCountError(f"a clip has at least one frame, not frame_count {record.frame_count}")
    if len(record.frames) != record.frame_count:
        raise ClipCountError(f"frame_count is {record.frame_count}, and frames lists {len(record.frames)}")
    expected = record.frame_count / record.fps
    if not _close(record.duration_s, expected):
        raise ClipCountError(f"{record.frame_count} frames at {record.fps:g} a second last {expected} s, "
                             f"not duration_s {record.duration_s}")
    if record.first < 0:
        raise ClipCountError(f"sequence.first is 0 or more, not {record.first}")
    for index, frame in enumerate(record.frames):
        name = PATTERN % (record.first + index)
        if frame.file != name:
            raise ClipCountError(f"frames[{index}].file is {frame.file!r}; frame {index} of the sequence is {name!r}")
        if not 0 < frame.bytes <= MAX_FRAME_BYTES:
            raise ClipFormatError(f"frames[{index}].bytes is 1 to {MAX_FRAME_BYTES}, not {frame.bytes}")
    check_camera(record.camera, "camera")
    if not record.figures:
        raise ClipValueError("a clip shows at least one figure")
    names = [figure.name for figure in record.figures]
    if len(set(names)) != len(names):
        raise ClipValueError(f"figure names repeat: {', '.join(names)}")
    for index, figure in enumerate(record.figures):
        path = f"figures[{index}] ({figure.name})"
        if not 0 < figure.height_m <= MAX_HEIGHT_M or figure.scale <= 0:
            raise ClipValueError(f"{path}: a height above 0 and at most {MAX_HEIGHT_M} m and a scale above 0, "
                                 f"not {figure.height_m} and {figure.scale}")
        if not -180.0 <= figure.facing_deg <= 180.0:
            raise ClipValueError(f"{path}: a facing is within half a turn, not {figure.facing_deg} degrees")
        start = record.frames[0].figures[index].feet
        if not all(map(_close, figure.at, start)):
            raise ClipValueError(f"{path}: at_m is {figure.at}; on the first frame it stands at {start}")
    for index, frame in enumerate(record.frames):
        for figure, placed in zip(record.figures, frame.figures):
            _check_placed(placed, record.camera, f"frames[{index}] {figure.name}")
    for index, take in enumerate(record.speech):
        _check_take(take, record, f"speech[{index}] ({take.take})")


def check_camera(camera: Camera, path: str = "camera") -> None:
    """The camera against itself: srlocations' gate fitted to the frame as srlocations fits it, the focal length that
    lens gives, and three unit axes, square to each other, level, that look at the target."""
    if camera.lens_mm <= 0 or camera.near_m <= 0:
        raise ClipCameraError(f"{path}: a lens and a near plane are positive, not {camera.lens_mm}, {camera.near_m}")
    if camera.gate_mm != GATE_MM:
        raise ClipCameraError(f"{path}: srlocations' gate is {GATE_MM} mm, not {camera.gate_mm}")
    width, height = camera.frame.width, camera.frame.height
    fit = "width" if width / height >= GATE_MM[0] / GATE_MM[1] else "height"
    if camera.fit != fit:
        raise ClipCameraError(f"{path}: a {width}x{height} frame fits the gate to its {fit}, not {camera.fit}")
    focal = camera.lens_mm * (width / GATE_MM[0] if fit == "width" else height / GATE_MM[1])
    if not _close(camera.focal_px, focal):
        raise ClipCameraError(f"{path}: a {camera.lens_mm} mm lens is {focal} px on this frame, not {camera.focal_px}")
    axes = {"right": camera.right, "up": camera.up, "forward": camera.forward}
    for name, axis in axes.items():
        if not _close(_dot(axis, axis), 1.0):
            raise ClipCameraError(f"{path}: the camera's {name} axis is not unit length")
    for a, b in (("right", "up"), ("up", "forward"), ("right", "forward")):
        if not _close(_dot(axes[a], axes[b]), 0.0):
            raise ClipCameraError(f"{path}: the camera's {a} and {b} axes are not square to each other")
    if not all(_close(c, f) for c, f in zip(_cross(camera.right, camera.up), camera.forward)):
        raise ClipCameraError(f"{path}: the camera's axes are mirrored: right x up is not forward")
    if not _close(camera.right[1], 0.0) or camera.up[1] < -TOLERANCE:
        raise ClipCameraError(f"{path}: the camera is rolled: srlocations' cameras keep their right axis level")
    sight = tuple(t - e for t, e in zip(camera.look_at, camera.eye))
    length = math.sqrt(_dot(sight, sight))
    if length == 0:
        raise ClipCameraError(f"{path}: the camera's eye is on its target")
    if not all(_close(s / length, f) for s, f in zip(sight, camera.forward)):
        raise ClipCameraError(f"{path}: the camera's forward axis does not look at its target")


def _check_placed(placed: FigureInFrame, camera: Camera, path: str) -> None:
    for name, point, recorded in (("feet", placed.feet, placed.feet_px), ("head", placed.head, placed.head_px)):
        expected = camera.project(point)
        if (expected is None) != (recorded is None):
            where = "behind" if expected is None else "in front of"
            raise ClipProjectionError(f"{path}: its {name} at {point} are {where} the camera, and the record says "
                                      f"{recorded}")
        if expected is not None and recorded is not None and not all(map(_close, recorded, expected)):
            raise ClipProjectionError(f"{path}: its {name}_px is {recorded}; the camera puts {point} at {expected}")
    scale = camera.pixels_per_metre(placed.feet)
    if placed.pixels_per_metre <= 0 or not _close(placed.pixels_per_metre, scale):
        raise ClipProjectionError(f"{path}: {placed.pixels_per_metre} px per metre; the camera gives {scale} at its feet")


def _check_take(take: Take, record: ClipRecord, path: str) -> None:
    if take.figure not in [figure.name for figure in record.figures]:
        raise ClipValueError(f"{path}: spoken by {take.figure!r}, who is not a figure of the clip")
    if not 0 <= take.at_s < record.duration_s:
        raise ClipValueError(f"{path}: it starts {take.at_s} s into a clip of {record.duration_s} s")
    if not take.words:
        raise ClipValueError(f"{path}: a take has at least one word")
    before = 0.0
    for index, word in enumerate(take.words):
        if not before <= word.start_s <= word.end_s:
            raise ClipValueError(f"{path}: word {index} ({word.text!r}) runs {word.start_s} to {word.end_s} s; a word "
                                 f"ends after it starts and starts no earlier than the one before ({before} s)")
        before = word.start_s


def check_files(record: ClipRecord, folder: Union[str, Path]) -> None:
    """Every frame the record names, in `folder` (the record's own): a plain file there, of the size and the SHA-256
    written. The first that is not stops it."""
    folder = Path(folder)
    for index, frame in enumerate(record.frames):
        path = folder / frame.file
        if path.is_symlink() or not path.is_file():
            raise ClipFileError(f"frames[{index}]: {frame.file} is not a file in {folder}")
        size = path.stat().st_size
        if size != frame.bytes:
            raise ClipFileError(f"frames[{index}]: {frame.file} is {size} bytes; the record says {frame.bytes}")
        found = sha256(path)
        if found != frame.sha256:
            raise ClipFileError(f"frames[{index}]: {frame.file} has SHA-256 {found}; the record says {frame.sha256}")


def sha256(path: Union[str, Path]) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def dumps(data: Mapping[str, object]) -> str:
    """A record's data as the text `cutout()` writes: strict JSON, keys sorted, a line a value."""
    return json.dumps(data, indent=1, sort_keys=True, allow_nan=False) + "\n"


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= TOLERANCE * max(1.0, abs(a), abs(b))


def _dot(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return sum(p * q for p, q in zip(a, b))


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


# --- the shape of each value ---------------------------------------------------------------------------------------


def _no_constant(name: str) -> object:
    raise ClipFormatError(f"a clip record holds finite numbers only, not {name}")


def _unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    out: dict[str, object] = {}
    for key, value in pairs:
        if key in out:
            raise ClipFormatError(f"a JSON object repeats the key {key!r}")
        out[key] = value
    return out


def _fields(value: object, path: str, required: tuple[str, ...], optional: tuple[str, ...] = ()) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ClipFormatError(f"{path} is a JSON object, not {type(value).__name__}")
    unknown = sorted(set(value) - set(required) - set(optional))
    if unknown:
        raise ClipFormatError(f"{path} has unknown field(s) {unknown}; it has {', '.join(required + optional)}")
    missing = [key for key in required if key not in value]
    if missing:
        raise ClipFormatError(f"{path} lacks field(s) {missing}")
    return value


def _list(value: object, path: str, most: int) -> list[object]:
    if not isinstance(value, list):
        raise ClipFormatError(f"{path} is a JSON list, not {type(value).__name__}")
    if len(value) > most:
        raise ClipFormatError(f"{path} holds at most {most} items, not {len(value)}")
    return value


def _number(value: object, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ClipFormatError(f"{path} is a number, not {value!r}")
    try:
        value = float(value)
    except OverflowError:
        raise ClipFormatError(f"{path} is a finite number, not one of {len(str(value))} digits") from None
    if not math.isfinite(value):
        raise ClipFormatError(f"{path} is a finite number, not {value!r}")
    return value


def _int(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ClipFormatError(f"{path} is a whole number, not {value!r}")
    return value


def _bool(value: object, path: str) -> bool:
    if not isinstance(value, bool):
        raise ClipFormatError(f"{path} is true or false, not {value!r}")
    return value


def _vector(value: object, path: str, size: int) -> tuple[float, ...]:
    items = _list(value, path, size)
    if len(items) != size:
        raise ClipFormatError(f"{path} holds {size} numbers, not {len(items)}")
    return tuple(_number(item, f"{path}[{i}]") for i, item in enumerate(items))


def _vec3(value: object, path: str) -> Vec3:
    x, y, z = _vector(value, path, 3)
    return (x, y, z)


def _pixel(value: object, path: str) -> Optional[Pixel]:
    if value is None:
        return None
    x, y = _vector(value, path, 2)
    return (x, y)


def _text(value: object, path: str, pattern: "re.Pattern[str]") -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ClipFormatError(f"{path} must match {pattern.pattern}, not {value!r}")
    return value


def _name(value: object, path: str) -> str:
    if not isinstance(value, str) or not value or len(value) > MAX_NAME or _CONTROL.search(value):
        raise ClipFormatError(f"{path} is a name of 1 to {MAX_NAME} printable characters, not {value!r}")
    return value
