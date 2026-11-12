"""Scene documents small enough for the engine: every clip goes through `package()`.

The engine refuses a scene document over 256 MiB (`MAX_DOCUMENT_BYTES`, a constant in scene-render's sr-model; 64 MiB
in the official 0.8.0, raised in our build of it: /home/dev/data/scene-render-patched).
A cast acted by characters.motion is keyed on every frame, and the SDK writes those keys with indentation, times
of 17 digits and keys that say nothing new, so eight figures at 24 fps pass the limit in a few seconds.
`package()` is `srlocations.portable.package()` followed by `slim()`, which rewrites the document without changing
the picture:

- indentation is dropped (each element keeps its own line: the engine loads one long line very slowly);
- a key's time is written with at most five decimals (10 microseconds);
- a key between two keys is dropped when the straight line between them passes through it, within `slack` units
  of the last digit it was written with (animations and keys that name a curve are left alone: only linear ones).

Measured on one acted figure (2 s at 24 fps, frames compared with the unslimmed document): slack 4 leaves 61% of
the bytes at 70 dB PSNR or better, slack 20 leaves 55% at 62 dB, slack 60 leaves 49% at 57 dB; none can be seen.
`package()` starts at 4 and goes to 20, then 60, only when the document would not fit otherwise.

Use `clip.package(scene, path)` wherever a scene is written for the engine, never `portable.package` directly.
`clip.encode(renderer, scene, out)` is the whole step for a video: package, slim, check the limit, encode.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Union

from srlocations import portable

LIMIT = 256 << 20         # bytes the engine accepts (sr-model limits.rs MAX_DOCUMENT_BYTES, in our build of 0.8.0)
PARALLEL = 3              # time segments the engine renders and encodes at once (encode --parallel): on one GPU
                          # 3 halve the time and 6 give no more (measured, 509 frames at 1080x1920: 51 s, 26 s, 28 s)
FARM = Path("/home/dev/data/scene-render-patched/farm")   # `workers` (a host a line) and `token`: the render workers
TURN = 90.0               # a rotation key is kept when dropping it would leave a turn of more than this (degrees)

_ANIMATE = re.compile(rb"(<animate\b[^>]*>)(.*?)(</animate>)", re.S)
_KEY = re.compile(rb'<key time="([^"]*)" value="([^"]*)"/>')
_OTHER_KEY = re.compile(rb"<key\b(?![^>]*\btime=\"[^\"]*\" value=\"[^\"]*\"/>)")
_NUMBER = re.compile(rb"^-?\d+(?:\.\d+)?$")


def _short(time: bytes) -> bytes:
    """A time with at most five decimals, and no more than it needs."""
    if b"." not in time or len(time.split(b".")[1]) <= 5:
        return time
    text = f"{float(time):.5f}".rstrip("0").rstrip(".")
    return (text or "0").encode()


def _thinned(head: bytes, body: bytes, loose: float = 4.0) -> bytes:
    """The keys of one <animate>, without those a straight line between their neighbours already gives."""
    linear = b"nterpolation" not in head and b"curve" not in head and not _OTHER_KEY.search(body)
    found = _KEY.findall(body)
    if not found or _KEY.sub(b"", body).strip():        # something else than plain keys in it: leave it as it is
        return body
    keys = [(_short(t), v) for t, v in found]
    if linear and len(keys) > 2 and all(_NUMBER.match(v) for _t, v in keys):
        turning = b'property="rotation' in head
        times, values = [float(t) for t, _v in keys], [float(v) for _t, v in keys]
        # `loose` units of the last digit the values were written with
        slack = loose * 10.0 ** -max((len(v.split(b".")[1]) if b"." in v else 0) for _t, v in keys)
        kept = [0]
        for i in range(1, len(keys) - 1):
            a, b = kept[-1], i + 1                      # would the line from the last kept key to the next pass i..?
            span = times[b] - times[a]
            ok = span > 0 and not (turning and abs(values[b] - values[a]) > TURN)
            if ok:
                for j in range(a + 1, b):
                    on_line = values[a] + (values[b] - values[a]) * (times[j] - times[a]) / span
                    if abs(on_line - values[j]) > slack:
                        ok = False
                        break
            if not ok:
                kept.append(i)
        kept.append(len(keys) - 1)
        keys = [keys[i] for i in kept]
    return b"".join(b'<key time="%s" value="%s"/>' % key for key in keys)


SLACKS = (4.0, 20.0, 60.0)   # tried in turn until the document fits


def _slimmed(data: bytes, slack: float) -> bytes:
    data = _ANIMATE.sub(lambda m: m.group(1) + _thinned(m.group(1), m.group(2), slack) + m.group(3), data)
    if b"<![CDATA[" not in data and b"xml:space" not in data:
        # Indentation goes, the line breaks stay: with the whole document on one line the engine takes minutes to
        # load it (8 minutes and not done for 57 MB, against seconds with a line per element).
        data = re.sub(rb">\s+<", b">\n<", data)        # white space between elements only: text is never touched
    return data


def slim(document: Union[str, Path], slack: float = SLACKS[0]) -> tuple[int, int]:
    """Rewrites a scene document smaller, the picture unchanged (see the module's text). (bytes before, after)."""
    document = Path(document)
    data = document.read_bytes()
    small = _slimmed(data, slack)
    document.write_bytes(small)
    return len(data), len(small)


def package(scene, document: Union[str, Path], quiet: bool = False) -> Path:
    """`portable.package()` and then slimmed, as little as fits. Refuses, with what to do, a document that is still
    over the engine's limit."""
    document = portable.package(scene, document)
    data = document.read_bytes()
    for slack in SLACKS:
        small = _slimmed(data, slack)
        if len(small) <= LIMIT:
            break
    document.write_bytes(small)
    if not quiet:
        print(f"scene file: {len(small) / 2**20:.0f} MB (written as {len(data) / 2**20:.0f} MB, slack {slack:g})",
              flush=True)
    if len(small) > LIMIT:
        raise SystemExit(f"{document.name} is {len(small) / 2**20:.0f} MB after slimming and the engine takes "
                         f"{LIMIT >> 20} MB: render it in shorter pieces and join them, or key it on twos (fps 12)")
    return document


def engine_env(workers: Optional[bool] = None) -> dict:
    """The environment the engine runs in. `workers` True names the render workers of `FARM` (the engine on another
    machine, `scene-render serve`), which then render part of a video; False renders here alone whatever the
    environment says; None leaves it to the caller's environment (`SR_WORKERS`, `SR_WORKER_TOKEN`). A worker that is
    off or cannot be reached is left out by the engine, with a note, and the render goes on here.

    The two machines' GPUs do not draw the same pixels (36.8 dB apart, along outlines): measure and compare frames
    with `workers=False`."""
    env = dict(os.environ)
    if workers is False:
        env["SR_WORKERS"] = ""
    elif workers:
        hosts = [h.strip() for h in (FARM / "workers").read_text().split() if h.strip()]
        env["SR_WORKERS"] = ",".join(hosts)
        env["SR_WORKER_TOKEN"] = (FARM / "token").read_text().strip()
    return env


def encode(renderer, scene, out: Union[str, Path], hw: str = "software", quiet: bool = False,
           own_output: bool = False, parallel: Optional[int] = None, workers: Optional[bool] = None) -> Path:
    """A video of `scene` at `out`: packaged, slimmed and encoded by the engine. With `own_output`, the scene has
    an <output> of its own writing to `out` (sound, burned subtitles: characters.soundtrack) and it is used as it
    is; without it the engine writes a plain video of the picture. `parallel` segments (default `PARALLEL`) are rendered at once and
    joined without encoding again (1: one after the other; the picture is the same to 50 dB, not to the bit).
    `workers` is `engine_env()`'s: True also renders on the other machine."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        document = package(scene, Path(folder) / f"{out.stem}.scene.xml", quiet)
        command = [str(renderer.engine), "encode", str(document), "--hw", hw, "--parallel",
                   str(max(1, int(PARALLEL if parallel is None else parallel)))]
        done = subprocess.run(command if own_output else command + ["--path", str(out)], text=True, capture_output=True,
                              env=engine_env(workers))
    if done.returncode:
        raise SystemExit(done.stdout[-2000:] + done.stderr[-2000:])
    return out
