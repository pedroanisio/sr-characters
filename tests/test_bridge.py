"""The bridge to srstudio: a character on a mark of a location record, and the clip record that goes with its cutout.

    SRLOCATIONS_PY -m pytest characters/tests/test_bridge.py -q              # no render: a few seconds
    LOOKS=1 SRLOCATIONS_PY -m pytest characters/tests/test_bridge.py -q      # and one small cutout drawn (GPU, Blender)

The location record here is srstudio's airliner fixture (tests/data/location-bridge/airliner-1080x1920.json at its
pin), written out from its numbers: the shot `down-the-aisle` and its two marks. Where that file is on this
machine, it is read too.
"""
import importlib.util
import json
import math
import os
import struct
import subprocess
import sys
import zlib
from pathlib import Path

import pytest
from srlocations import Shot
from srlocations.compiler import Projection
from srlocations.geometry import Vec3

from characters import bridge, clip_record, export, film

EYE, LOOK_AT, LENS = (0.0, 1.22, -1.3), (0.0, 1.22, 8.0), 15.0          # the fixture's shot down-the-aisle
MARKS = (("aisle", (0.0, 0.0, 3.0), 0.0), ("galley-door", (0.0, 0.0, 10.9), 180.0))
FEET, SCALE, HEAD = (540.0, 1300.4651162790697), 279.06976744186045, (540.0, 826.046511627907)   # aisle, 1080x1920
PINNED = Path(os.environ.get("SRSTUDIO_LOCATION_FIXTURE", "/home/dev/src/viral-video-orchestrator/vendor/srstudio/"
                             "d80eb6d/tests/data/location-bridge/airliner-1080x1920.json"))


def location_record(folder: Path, width: int = 1080, height: int = 1920) -> Path:
    """The fixture's shot and marks as a location record of schema 1.0.0, for a frame of this size."""
    focal = LENS * height / 24.0
    camera = {"eye_m": list(EYE), "look_at_m": list(LOOK_AT), "lens_mm": LENS, "gate_mm": [36.0, 24.0], "fit": "height",
              "focal_px": focal, "near_m": 0.05, "right": [1.0, 0.0, 0.0], "up": [0.0, 1.0, 0.0], "forward": [0.0, 0.0, 1.0]}
    marks = []
    for name, at, facing in MARKS:
        depth = at[2] - EYE[2]
        pixel = lambda y: [width / 2 + focal * at[0] / depth, height / 2 - focal * (y - EYE[1]) / depth]   # noqa: E731
        marks.append({"mark": name, "at_m": list(at), "facing_deg": facing, "framing": "", "height_m": 1.7,
                      "feet_px": pixel(at[1]), "head_px": pixel(at[1] + 1.7), "pixels_per_metre": focal / depth,
                      "in_frame": True})
    record = {"schema_version": "1.0.0", "srlocations_commit": "be0aabced115e4e885adba380c72f2f63f80959c",
              "location": {"source": "catalog", "catalog": "studio", "name": "airliner", "version": "1.0.1",
                           "digest": "301e5701d9e16ec2b19fcc7f4955891d0eef30496ffba854cd0fe5abf905bf99"},
              "frame": {"width_px": width, "height_px": height},
              "shots": [{"name": "down-the-aisle", "camera": camera, "marks": marks}]}
    path = folder / f"airliner-{width}x{height}.json"
    path.write_text(json.dumps(record, indent=1))
    return path


def records(tmp_path: Path) -> list[Path]:
    return [location_record(tmp_path)] + ([PINNED] if PINNED.is_file() else [])


# ---- a film on a mark

def test_the_projection_agrees_with_the_fixture(tmp_path):
    for record in records(tmp_path):
        placed = bridge.read_location(record, "down-the-aisle", "aisle")
        assert placed.feet_px == pytest.approx(FEET, abs=1e-9) and placed.pixels_per_metre == pytest.approx(SCALE, abs=1e-9)
        f, actor = bridge.from_shot(record, "down-the-aisle", "aisle", "sergeant")
        assert f.size == (1080, 1920) and f.fps == 30 and [a.who for a in f.actors] == ["sergeant"]
        view = Projection(f.loc.shots["film"], *f.size)                   # the film's own camera, in the studio
        stood = Vec3.of(actor.fig.at)
        assert view.pixel(stood) == pytest.approx(FEET, abs=1e-6)
        assert view.pixels_per_metre(stood) == pytest.approx(SCALE, abs=1e-6)
        assert f.stage.to_set(tuple(stood)) == pytest.approx((0.0, 0.0, 3.0), abs=1e-9)
        assert f.stage.camera.project((0.0, 0.0, 3.0)) == pytest.approx(FEET, abs=1e-9)
        assert round(FEET[1], 2) == 1300.47 and round(SCALE, 2) == 279.07
    # and an srlocations Shot of those numbers is the record's camera, field for field: one projection, two writers
    ours = bridge.camera_of(Shot("down-the-aisle", Vec3(*EYE), Vec3(*LOOK_AT), LENS), 1080, 1920).to_data()
    theirs = json.loads(location_record(tmp_path).read_text())["shots"][0]["camera"]
    assert ours == theirs


def test_the_studio_is_the_set_turned_moved_and_scaled(tmp_path):
    """The film is built where the finish's lamps are (the figure at the origin, the camera on +z); a point of the
    set and its place in the studio land on the same pixel, whatever the turn and the scale."""
    record = location_record(tmp_path)
    for tall in (None, 1.7, 0.5):
        f, actor = bridge.from_shot(record, "down-the-aisle", "aisle", "sergeant", height_m=tall)
        stage, view = f.stage, Projection(f.loc.shots["film"], *f.size)
        eye = f.loc.shots["film"].eye
        assert tuple(Vec3.of(actor.fig.at)) == (0.0, 0.0, 0.0) and abs(eye.x) < 1e-9 and eye.z > 0
        assert stage.scale == pytest.approx(1.0 if tall is None else tall / actor.fig.stature())
        for point in ((0.0, 0.0, 3.0), (0.4, 1.1, 5.0), (-0.7, 0.3, 2.2), (0.0, 1.7, 3.0)):
            there = stage.to_studio(point)
            assert stage.to_set(there) == pytest.approx(point, abs=1e-9)
            assert view.pixel(Vec3(*there)) == pytest.approx(stage.camera.project(point), abs=1e-6)
    # at the mark's own height the top of the body is on the record's head pixel: the camera gives the size
    f, actor = bridge.from_shot(record, "down-the-aisle", "aisle", "sergeant", height_m=1.7)
    top = Vec3(0.0, actor.fig.stature(), 0.0)
    assert Projection(f.loc.shots["film"], *f.size).pixel(top) == pytest.approx(HEAD, abs=1e-6)


def _middle(parts, name):
    found = [p["verts"] for p in parts if p["name"].split("/")[0] == name]
    return tuple((min(c for v in found for c in v[k::3]) + max(c for v in found for c in v[k::3])) / 2 for k in range(3))


def test_a_mark_s_facing_is_the_film_s_yaw(tmp_path):
    """0 faces +z and 90 faces +x, for a mark and for Film.add(yaw=) alike: the nose is on that side of the head,
    and in the picture a point in front of the figure is where the nose points."""
    record = location_record(tmp_path)
    for facing, ahead in ((0.0, (0.0, 1.0)), (90.0, (1.0, 0.0)), (180.0, (0.0, -1.0)), (-90.0, (-1.0, 0.0))):
        f, actor = bridge.from_shot(record, "down-the-aisle", "aisle", "sergeant", facing_deg=facing)
        stage = f.stage
        assert stage.facing(actor.fig.yaw) == pytest.approx(facing)
        parts = export.frame(f.loc, "film")["parts"]
        nose, head = stage.to_set(_middle(parts, "nose")), stage.to_set(_middle(parts, "head"))
        way = (nose[0] - head[0], nose[2] - head[2])
        far = math.hypot(*way)
        assert far > 0.03 and (way[0] / far, way[1] / far) == pytest.approx(ahead, abs=0.05), (facing, way)
        front = (head[0] + 0.5 * math.sin(math.radians(facing)), head[1], head[2] + 0.5 * math.cos(math.radians(facing)))
        to_front = stage.camera.project(front)[0] - stage.camera.project(head)[0]       # pixels to the picture's right
        to_nose = stage.camera.project(nose)[0] - stage.camera.project(head)[0]
        nearer = stage.camera.depth(head) - stage.camera.depth(nose)                    # metres the nose is nearer the camera
        if facing in (90.0, -90.0):      # across the picture: +x is its right for this camera, which looks along +z
            side = 1 if facing > 0 else -1
            assert side * to_nose > 5 and side * to_front > 100 and abs(nearer) < 0.01, (facing, to_nose, to_front)
        else:                            # along the camera's view: facing 0 is away from it, 180 toward it
            assert abs(to_nose) < 2 and abs(to_front) < 2 and nearer * (1 if facing == 180.0 else -1) > 0.03, (facing, nearer)
    # the mark's own facing when none is given: `aisle` faces 0, away from this shot's camera
    f, actor = bridge.from_shot(record, "down-the-aisle", "aisle", "sergeant")
    assert f.stage.facing(actor.fig.yaw) == pytest.approx(0.0)
    parts = export.frame(f.loc, "film")["parts"]
    assert f.stage.camera.depth(f.stage.to_set(_middle(parts, "nose"))) > f.stage.camera.depth(f.stage.to_set(_middle(parts, "head")))


def test_what_from_shot_refuses(tmp_path):
    record = location_record(tmp_path)
    with pytest.raises(bridge.BridgeError, match="height_m="):
        bridge.from_shot(record, "down-the-aisle", "aisle", "sergeant", height=1.7)      # the mannequin's own field
    with pytest.raises(bridge.BridgeError, match="no shot 'window'.*down-the-aisle"):
        bridge.from_shot(record, "window", "aisle", "sergeant")
    with pytest.raises(bridge.BridgeError, match="no mark 'door'.*aisle, galley-door"):
        bridge.from_shot(record, "down-the-aisle", "door", "sergeant")
    with pytest.raises(bridge.BridgeError, match="no character 'nobody'"):
        bridge.from_shot(record, "down-the-aisle", "aisle", "nobody")
    with pytest.raises(bridge.BridgeError, match="height_m is above 0"):
        bridge.from_shot(record, "down-the-aisle", "aisle", "sergeant", height_m=0)
    data = json.loads(record.read_text())
    data["shots"][0]["marks"][0]["feet_px"][1] += 2.0                     # a mark that is not where its camera puts it
    moved = tmp_path / "moved.json"
    moved.write_text(json.dumps(data))
    with pytest.raises(bridge.BridgeError, match="its camera puts it at"):
        bridge.from_shot(moved, "down-the-aisle", "aisle", "sergeant")
    data = json.loads(record.read_text())
    data["shots"][0]["camera"]["focal_px"] = 1000.0
    moved.write_text(json.dumps(data))
    with pytest.raises(bridge.BridgeError, match="15.0 mm lens is 1200.0 px"):
        bridge.from_shot(moved, "down-the-aisle", "aisle", "sergeant")
    data = json.loads(record.read_text())
    data["schema_version"] = "2.0.0"
    moved.write_text(json.dumps(data))
    with pytest.raises(bridge.BridgeError, match="schema 1.x"):
        bridge.from_shot(moved, "down-the-aisle", "aisle", "sergeant")
    f, _actor = bridge.from_shot(record, "down-the-aisle", "aisle", "sergeant")
    with pytest.raises(bridge.BridgeError, match="lowpoly writes alpha"):
        bridge.cutout(f, tmp_path / "out", 1.0, finish="fur")
    assert not (tmp_path / "out").exists()


# ---- speech

WORDS = [{"text": "Boa", "start": 0.10, "end": 0.34}, {"text": "noite,", "start": 0.40, "end": 0.82},
         {"text": "a", "start": 0.82, "end": 0.88}, {"text": "todos", "start": 1.30, "end": 1.75}]


def test_alignment_from_words():
    got = bridge.alignment_from_words(WORDS)
    chars, starts, ends = got["characters"], got["character_start_times_seconds"], got["character_end_times_seconds"]
    assert "".join(chars) == "Boa noite, a todos" and len(chars) == len(starts) == len(ends)
    assert all(a <= b for a, b in zip(starts, ends))                               # a letter ends after it starts
    assert all(ends[i] <= starts[i + 1] + 1e-9 for i in range(len(chars) - 1))     # and the next starts no earlier
    at = 0
    for k, word in enumerate(WORDS):
        if k:
            assert chars[at] == " " and starts[at] == pytest.approx(WORDS[k - 1]["end"]) and ends[at] == pytest.approx(word["start"])
            at += 1
        n = len(word["text"])
        assert "".join(chars[at:at + n]) == word["text"]
        assert starts[at] == pytest.approx(word["start"], abs=1e-6) and ends[at + n - 1] == pytest.approx(word["end"], abs=1e-6)
        widths = [ends[i] - starts[i] for i in range(at, at + n)]
        assert max(widths) - min(widths) < 2e-6                                    # its letters share its span evenly
        at += n
    assert at == len(chars)
    # a word that starts before the last one ended starts where that one ended; a word of no length still lasts
    got = bridge.alignment_from_words([{"text": "ab", "start": 0.0, "end": 0.5}, {"text": "cd", "start": 0.4, "end": 0.4}])
    assert got["character_start_times_seconds"][3] == pytest.approx(0.5)
    assert got["character_end_times_seconds"][-1] == pytest.approx(0.5 + bridge.LETTER_FLOOR)
    for bad in ([], [{"text": "", "start": 0, "end": 1}], [{"text": "a b", "start": 0, "end": 1}], [{"text": "a", "start": 1, "end": 0.5}],
                [{"text": "a", "start": 0, "end": float("nan")}], [{"text": "a", "start": 0}],
                [{"text": "a", "start": 1.0, "end": 1.2}, {"text": "b", "start": 0.5, "end": 0.7}]):
        with pytest.raises(bridge.BridgeError):
            bridge.alignment_from_words(bad)


def test_a_take_moves_the_mouth_and_nothing_else(tmp_path):
    f, actor = bridge.from_shot(location_record(tmp_path), "down-the-aisle", "aisle", "sergeant")
    assert bridge.say_take(actor, {"id": "take-7", "words": WORDS, "text": "sreditor's other fields are its own"}, at=0.5) is actor
    keyed = [m for m in actor.mouths if m[1] is not None]
    assert keyed and 0.5 <= min(m[0] for m in keyed) + 0.1 and max(m[0] for m in actor.mouths) == pytest.approx(0.5 + 1.75, abs=0.01)
    assert any((m[2] or 0) > 0.3 for m in keyed)                                   # it opens
    assert f.sounds == [] and f.cues == []                                         # nothing heard, nothing subtitled
    assert actor.takes == [{"figure": "sergeant", "take": "take-7", "at_s": 0.5, "audio_sha256": None,
                            "words": [{"text": w["text"], "start_s": w["start"], "end_s": w["end"]} for w in WORDS]}]
    for bad in ({"words": WORDS}, {"id": "t", "words": []}):
        with pytest.raises(bridge.BridgeError):
            bridge.say_take(actor, bad, at=0.0)
    with pytest.raises(bridge.BridgeError, match="no voice file"):
        bridge.say_take(actor, {"id": "t", "words": WORDS}, at=0.0, audio=tmp_path / "missing.mp3")


# ---- the record

def fake_clip(folder: Path, frames: int = 3, fps: int = 30) -> tuple[Path, dict]:
    """A tiny clip: frames of a few bytes each (the record vouches for bytes, not for pictures) and its record,
    a figure walking away from the aisle mark under the fixture's camera."""
    camera = bridge.camera_of(Shot("down-the-aisle", Vec3(*EYE), Vec3(*LOOK_AT), LENS), 1080, 1920)
    (folder / "frames").mkdir(parents=True)
    listed = []
    for k in range(frames):
        name = clip_record.PATTERN % k
        (folder / name).write_bytes(b"\x89PNG\r\n\x1a\n frame %d" % k)
        feet, head = (0.02 * k, 0.0, 3.0 + 0.1 * k), (0.02 * k, 0.9, 3.0 + 0.1 * k)
        listed.append({"file": name, "sha256": clip_record.sha256(folder / name), "bytes": (folder / name).stat().st_size,
                       "figures": [{"feet_m": list(feet), "head_m": list(head), "feet_px": list(camera.project(feet)),
                                    "head_px": list(camera.project(head)), "pixels_per_metre": camera.pixels_per_metre(feet)}]})
    data = {"schema": clip_record.SCHEMA,
            "producer": {"package": "sr-characters", "commit": "b" * 40, "dirty": False, "srlocations": "0.1.0"},
            "finish": "lowpoly", "alpha": "straight", "frame": {"width_px": 1080, "height_px": 1920}, "fps": fps,
            "frame_count": frames, "duration_s": frames / fps, "sequence": {"pattern": clip_record.PATTERN, "first": 0},
            "camera": camera.to_data(),
            "location": {"name": "airliner", "version": "1.0.1", "digest": "3" * 64, "shot": "down-the-aisle",
                         "mark": "aisle", "record_sha256": "a" * 64},
            "figures": [{"name": "sergeant", "who": "sergeant", "at_m": [0.0, 0.0, 3.0], "facing_deg": 180.0,
                         "height_m": 1.0, "scale": 1.0}],
            "speech": [{"figure": "sergeant", "take": "take-7", "at_s": 0.01, "audio_sha256": None,
                        "words": [{"text": "Boa", "start_s": 0.0, "end_s": 0.05}]}],
            "frames": listed}
    path = folder / "clip.json"
    path.write_text(clip_record.dumps(data))
    return path, data


def test_a_record_of_a_tiny_clip_parses(tmp_path):
    path, data = fake_clip(tmp_path)
    record = clip_record.load(path)
    assert record.schema == "characters.clip/1.0.0" and record.frame == clip_record.Frame(1080, 1920)
    assert (record.fps, record.frame_count, record.duration_s, record.first, record.last) == (30, 3, pytest.approx(0.1), 0, 2)
    assert record.pattern == "frames/%05d.png" and record.alpha == "straight" and record.finish == "lowpoly"
    assert record.producer == clip_record.Producer("sr-characters", "b" * 40, False, "0.1.0")
    assert record.camera.project((0.0, 0.0, 3.0)) == pytest.approx(FEET) and record.camera.focal_px == 1200.0
    assert record.placed(0).feet_px == pytest.approx(FEET) and record.placed(0, "sergeant").pixels_per_metre == pytest.approx(SCALE)
    assert record.placed(2).feet == (0.04, 0.0, 3.2) and record.figure("sergeant") == 0
    assert record.location.mark == "aisle" and record.speech[0].words[0] == clip_record.Word("Boa", 0.0, 0.05)
    assert clip_record.parse(path.read_bytes()) == record == clip_record.from_data(data)     # text, bytes, data: one record
    data["location"], data["speech"] = None, []                                              # a film of its own, silent
    assert clip_record.from_data(data).location is None


def _spoiled(data: dict, change) -> dict:
    copy = json.loads(json.dumps(data))
    change(copy)
    return copy


def test_each_kind_of_corruption_has_its_own_error(tmp_path):
    path, data = fake_clip(tmp_path)

    def refused(kind, said, change):
        with pytest.raises(kind, match=said) as caught:
            clip_record.from_data(_spoiled(data, change))
        assert type(caught.value) is kind, caught.value           # its own error, not a kin of it
        return str(caught.value)

    def at(*keys):
        def put(d, value):
            for key in keys[:-1]:
                d = d[key]
            d[keys[-1]] = value
        return put

    # the shape: a closed record of finite numbers
    refused(clip_record.ClipFormatError, r"record has unknown field\(s\) \['note'\]", lambda d: d.update(note="hello"))
    refused(clip_record.ClipFormatError, r"frames\[1\] has unknown field", lambda d: d["frames"][1].update(mask="m.png"))
    refused(clip_record.ClipFormatError, r"camera lacks field\(s\) \['near_m'\]", lambda d: d["camera"].pop("near_m"))
    refused(clip_record.ClipFormatError, "fps is a number, not '30'", lambda d: d.update(fps="30"))
    refused(clip_record.ClipFormatError, "alpha is 'straight'", lambda d: d.update(alpha="premultiplied"))
    refused(clip_record.ClipFormatError, "sha256 must match", lambda d: d["frames"][0].update(sha256="ABC"))
    refused(clip_record.ClipFormatError, r"frames\[2\].figures places 0 figure", lambda d: d["frames"][2].update(figures=[]))
    refused(clip_record.ClipFormatError, "schema must read", lambda d: d.update(schema="1.0.0"))
    # another record, another major
    refused(clip_record.ClipSchemaError, "not characters.clip/2.0.0", lambda d: d.update(schema="characters.clip/2.0.0"))
    refused(clip_record.ClipSchemaError, "not 'characters.take'", lambda d: d.update(schema="characters.take/1.0.0"))
    assert clip_record.from_data(_spoiled(data, lambda d: d.update(schema="characters.clip/1.4.2"))).schema.endswith("1.4.2")
    # the count: frames listed, frame_count, duration and fps
    refused(clip_record.ClipCountError, "frame_count is 4, and frames lists 3", lambda d: d.update(frame_count=4))
    refused(clip_record.ClipCountError, "3 frames at 30 a second last 0.1 s, not duration_s 3.0", lambda d: d.update(duration_s=3.0))
    refused(clip_record.ClipCountError, "3 frames at 24 a second", lambda d: d.update(fps=24))
    refused(clip_record.ClipCountError, "frame 1 of the sequence is 'frames/00001.png'",
            lambda d: d["frames"][1].update(file="frames/00002.png"))
    refused(clip_record.ClipCountError, "frame 0 of the sequence", lambda d: d["frames"][0].update(file="../frames/00000.png"))
    # the camera against itself
    refused(clip_record.ClipCameraError, "a 15.0 mm lens is 1200.0 px on this frame, not 1000.0",
            lambda d: d["camera"].update(focal_px=1000.0))
    refused(clip_record.ClipCameraError, "fits the gate to its height", lambda d: d["camera"].update(fit="width"))
    refused(clip_record.ClipCameraError, r"gate is \(36.0, 24.0\) mm", lambda d: d["camera"].update(gate_mm=[35.0, 24.0]))
    refused(clip_record.ClipCameraError, "does not look at its target", lambda d: d["camera"].update(look_at_m=[1.0, 1.22, 8.0]))
    refused(clip_record.ClipCameraError, "mirrored", lambda d: d["camera"].update(right=[-1.0, 0.0, 0.0]))
    # a figure's pixels against the camera and its place in the set
    said = refused(clip_record.ClipProjectionError, r"frames\[1\] sergeant: its feet_px is",
                   lambda d: d["frames"][1]["figures"][0].update(feet_px=[540.0, 1310.0]))
    assert "(540.0, 1310.0)" in said and "the camera puts (0.02, 0.0, 3.1) at (545.45" in said     # found, and expected
    refused(clip_record.ClipProjectionError, "its head_px is", lambda d: d["frames"][0]["figures"][0].update(head_m=[0.0, 1.0, 3.0]))
    refused(clip_record.ClipProjectionError, "px per metre; the camera gives 279.06",
            lambda d: d["frames"][0]["figures"][0].update(pixels_per_metre=300.0))
    refused(clip_record.ClipProjectionError, "the record says None", lambda d: d["frames"][0]["figures"][0].update(head_px=None))
    # what is not a count, a camera or a projection
    refused(clip_record.ClipValueError, "on the first frame it stands at", lambda d: d["figures"][0].update(at_m=[0.0, 0.0, 3.5]))
    refused(clip_record.ClipValueError, "a height above 0", lambda d: d["figures"][0].update(height_m=0.0))
    refused(clip_record.ClipValueError, "who is not a figure of the clip", lambda d: d["speech"][0].update(figure="bear"))
    refused(clip_record.ClipValueError, "ends after it starts",
            lambda d: d["speech"][0]["words"][0].update(start_s=0.2))

    # the text: strict JSON, of a size
    text = path.read_text()
    with pytest.raises(clip_record.ClipFormatError, match="finite numbers only, not NaN"):
        clip_record.parse(text.replace('"fps": 30', '"fps": NaN'))
    with pytest.raises(clip_record.ClipFormatError, match="repeats the key 'fps'"):
        clip_record.parse(text.replace('"fps": 30', '"fps": 30, "fps": 30'))
    with pytest.raises(clip_record.ClipFormatError, match="one JSON object"):
        clip_record.parse(text[:-20])
    with pytest.raises(clip_record.ClipFormatError, match=f"at most {clip_record.MAX_BYTES} bytes"):
        clip_record.parse(text + " " * clip_record.MAX_BYTES)
    with pytest.raises(clip_record.ClipFormatError, match="a JSON object, not list"):
        clip_record.parse("[]")
    with pytest.raises(clip_record.ClipFormatError, match="cannot read"):
        clip_record.load(tmp_path / "missing.json")


def test_the_frames_are_the_ones_the_record_names(tmp_path):
    path, data = fake_clip(tmp_path)
    clip_record.load(path)
    frame = tmp_path / "frames" / "00001.png"
    kept = frame.read_bytes()
    frame.write_bytes(kept[:-1] + b"X")                                    # the same size, other bytes
    with pytest.raises(clip_record.ClipFileError, match=r"frames\[1\]: frames/00001.png has SHA-256 .* the record says " + data["frames"][1]["sha256"]) as caught:
        clip_record.load(path)
    assert type(caught.value) is clip_record.ClipFileError
    assert clip_record.load(path, files=False).frame_count == 3            # the record alone still reads
    frame.write_bytes(kept + b"more")
    with pytest.raises(clip_record.ClipFileError, match=f"is {len(kept) + 4} bytes; the record says {len(kept)}"):
        clip_record.load(path)
    frame.unlink()
    with pytest.raises(clip_record.ClipFileError, match="frames/00001.png is not a file in"):
        clip_record.load(path)
    frame.symlink_to(tmp_path / "frames" / "00000.png")                    # a link is not a frame
    with pytest.raises(clip_record.ClipFileError, match="is not a file in"):
        clip_record.load(path)
    frame.unlink()
    frame.write_bytes(kept)
    wrong = _spoiled(data, lambda d: d["frames"][2].update(sha256="0" * 64))        # the record's hash, not the file
    path.write_text(clip_record.dumps(wrong))
    with pytest.raises(clip_record.ClipFileError, match=r"frames\[2\].*the record says 0000"):
        clip_record.load(path)


def test_the_reader_loads_by_its_path_with_the_standard_library_alone(tmp_path):
    """srstudio cannot import `characters` (nor srlocations, nor sr-core): it loads this one file."""
    path, _data = fake_clip(tmp_path)
    program = (
        "import importlib.util, sys\n"
        "before = set(sys.modules)\n"
        f"spec = importlib.util.spec_from_file_location('clip_record', {str(Path(clip_record.__file__))!r})\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "sys.modules['clip_record'] = module\n"
        "spec.loader.exec_module(module)\n"
        f"record = module.load({str(path)!r})\n"
        "new = {name.split('.')[0] for name in set(sys.modules) - before}\n"
        "foreign = sorted(name for name in new if name not in sys.stdlib_module_names and name != 'clip_record')\n"
        "print(record.frame_count, record.frames[0].figures[0].feet_px, foreign)\n")
    done = subprocess.run([sys.executable, "-I", "-S", "-c", program], text=True, capture_output=True, cwd=str(tmp_path))
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == f"3 {FEET} []"


# ---- the command line

REQUEST = {"schema": bridge.REQUEST, "location": "airliner-1080x1920.json", "shot": "down-the-aisle", "mark": "aisle",
           "who": "sergeant", "seconds": 0.1, "facing_deg": 180.0,
           "actions": [{"at": 0.0, "do": "wave", "side": "left"}],
           "takes": [{"id": "take-7", "at": 0.0, "words": WORDS[:1]}]}


def test_a_request_is_closed(tmp_path, capsys):
    asked = bridge.parse_request(json.dumps(REQUEST))
    assert asked["who"] == "sergeant" and asked["actions"][0]["do"] == "wave" and asked["takes"][0]["id"] == "take-7"
    for change, said in ((lambda d: d.update(camera="mine"), r"unknown field\(s\) \['camera'\]"),
                         (lambda d: d.pop("mark"), r"lacks field\(s\) \['mark'\]"),
                         (lambda d: d.update(schema="characters.cutout-request/2.0.0"), "request.schema is"),
                         (lambda d: d["actions"][0].update(when=1), r"actions\[0\] has unknown field"),
                         (lambda d: d["actions"][0].update(side="up"), "'left' or 'right'"),
                         (lambda d: d["takes"][0].update(voice="x.mp3"), r"takes\[0\] has unknown field"),
                         (lambda d: d["takes"][0]["words"][0].update(word="Boa"), r"words\[0\] has unknown field"),
                         (lambda d: d.update(seconds="3"), "request.seconds is a number")):
        with pytest.raises(bridge.RequestError, match=said):
            bridge.parse_request(json.dumps(_spoiled(REQUEST, change)))
    with pytest.raises(bridge.RequestError, match="finite numbers only"):
        bridge.parse_request(json.dumps(REQUEST).replace("0.1", "Infinity", 1))
    # the command: its usage, a request it cannot read, and one that asks for what the character cannot do
    assert bridge.main([]) == 2 and "REQUEST.json OUT_DIR" in capsys.readouterr().err
    assert bridge.main([str(tmp_path / "none.json"), str(tmp_path / "out")]) == 2
    location_record(tmp_path)
    request = tmp_path / "request.json"
    request.write_text(json.dumps(_spoiled(REQUEST, lambda d: d["actions"][0].update(do="fly"))))
    capsys.readouterr()
    assert bridge.main([str(request), str(tmp_path / "out")]) == 1
    assert "sergeant cannot 'fly'" in capsys.readouterr().err and not (tmp_path / "out").exists()


# ---- one cutout drawn

def _rgba(path: Path) -> tuple[int, int, list[bytes]]:
    """An 8-bit RGBA PNG as rows of bytes (this interpreter has no imaging library)."""
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    at, packed, size = 8, b"", None
    while at < len(data):
        length, kind = struct.unpack(">I4s", data[at:at + 8])
        body = data[at + 8:at + 8 + length]
        if kind == b"IHDR":
            width, height, bits, colour, _c, _f, interlace = struct.unpack(">IIBBBBB", body)
            assert (bits, colour, interlace) == (8, 6, 0), (bits, colour, interlace)       # RGBA, 8 bits, not interlaced
            size = (width, height)
        elif kind == b"IDAT":
            packed += body
        at += 12 + length
    width, height = size
    raw, stride, rows, last = zlib.decompress(packed), width * 4, [], bytearray(width * 4)
    for y in range(height):
        kind, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            left, up, corner = (line[i - 4] if i >= 4 else 0), last[i], (last[i - 4] if i >= 4 else 0)
            if kind == 1:
                line[i] = (line[i] + left) & 255
            elif kind == 2:
                line[i] = (line[i] + up) & 255
            elif kind == 3:
                line[i] = (line[i] + (left + up) // 2) & 255
            elif kind == 4:
                p = left + up - corner
                near = min((abs(p - left), 0, left), (abs(p - up), 1, up), (abs(p - corner), 2, corner))[2]
                line[i] = (line[i] + near) & 255
        rows.append(bytes(line))
        last = line
    return width, height, rows


FEET_WITHIN_M = 0.05      # how far from the record's feet pixel the shoes' lowest solid pixels may be, in the set's metres:
                          # the feet pixel is the ground under the figure's root, between its heels and its toes, and a
                          # shoe's toe is 0.1 m in front of that (nearer this camera, so lower in the picture)


@pytest.mark.looks
def test_a_cutout_is_drawn_with_alpha_where_the_record_says(request, tmp_path):
    if "looks" not in (request.config.getoption("markexpr") or "") and os.environ.get("LOOKS", "") in ("", "0"):
        pytest.skip("three frames drawn by Blender (GPU, about 20 s): run with -m looks or LOOKS=1")
    from characters import blender
    if blender.available():
        pytest.skip(blender.available())
    location_record(tmp_path, 540, 960)                                   # the same shot, a quarter of the pixels
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps({**REQUEST, "location": "airliner-540x960.json"}))
    assert bridge.main([str(request_path), str(tmp_path / "out")]) == 0   # as srstudio would run it
    record = clip_record.load(tmp_path / "out" / "clip.json")             # every frame there, with its SHA-256
    assert (record.frame_count, record.fps, record.frame) == (3, 30, clip_record.Frame(540, 960))
    assert record.figures[0].who == "sergeant" and record.figures[0].facing_deg == pytest.approx(180.0)
    assert record.figures[0].height_m == pytest.approx(1.0) and record.location.mark == "aisle"
    assert record.speech[0].take == "take-7" and record.producer.srlocations
    assert not (tmp_path / "out" / ".work").exists()
    for k, frame in enumerate(record.frames):
        width, height, rows = _rgba(tmp_path / "out" / frame.file)
        assert (width, height) == (540, 960)
        alpha = lambda x, y: rows[y][4 * x + 3]                           # noqa: E731
        for x, y in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1), (width // 2, 40)):
            assert rows[y][4 * x:4 * x + 4] == b"\0\0\0\0", (k, x, y)     # clear in the corners, and no colour there
        placed = frame.figures[0]
        head = tuple(round(v) for v in placed.head_px)
        assert alpha(*head) == 255 and max(rows[head[1]][4 * head[0]:4 * head[0] + 3]) > 40      # solid, and a face
        solid = [(x, y) for y in range(height) for x in range(width) if alpha(x, y) >= 250]
        low = max(y for _x, y in solid)
        shoes = [x for x, y in solid if y >= low - 6]
        middle = (min(shoes) + max(shoes)) / 2
        within = FEET_WITHIN_M * placed.pixels_per_metre                  # 7 px here
        assert placed.feet_px == pytest.approx((270.0, 650.2325581395348))
        assert abs(low - placed.feet_px[1]) <= within and abs(middle - placed.feet_px[0]) <= within, (k, low, middle)
        top = min(y for _x, y in solid)                                   # and it is as tall as a 1 m figure is there
        assert 0.9 * placed.pixels_per_metre <= low - top <= 1.12 * placed.pixels_per_metre, (k, top, low)
        shadow = [alpha(x, low + 4) for x in range(width)]                # under the shoes: its shadow, part clear
        assert 0 < max(shadow) < 250
