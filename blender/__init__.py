"""Soft toys with real fur: the film's frames drawn by Blender Cycles (scene-render has no fur).

`render(frames, pngs, finish, quality)` runs `render_frames.py` with a Python that has bpy, under the GPU guard;
`characters.film.Film.render(out, seconds, finish="fur")` exports, renders, and encodes in one call.

Measured on this host (Tesla P40, OptiX, one figure in a 1080x1920 frame): "fur" about 5 s a frame at "standard",
1 to 2 s at "draft", about 10 s at "fine"; "terry" (no hairs) about 2 s a frame. See sr-data/plush-blender/README.md.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Mapping, Optional, Union

HERE = Path(__file__).resolve().parent
PYTHON = os.environ.get("PLUSH_BLENDER_PY", "/home/dev/data/ai3d/.venv-rig/bin/python")      # a Python with bpy 4.2
LIBS = os.environ.get("PLUSH_BLENDER_LIBS", "/home/dev/data/ai3d/syslibs/usr/lib/x86_64-linux-gnu")   # libSM and friends
GUARD = Path(os.environ.get("PLUSH_GPU_GUARD", "/home/dev/data/ai3d/scripts/gpu_guard.py"))

FINISHES = ("fur", "terry", "vinyl", "lowpoly")
# samples, the share of the film's size that is drawn (then enlarged), hairs: density, drawn per grown, width
QUALITY: dict[str, dict] = {
    "draft": {"samples": 4, "scale": 0.5, "density": 0.10, "children": 20, "radius": 2.4},
    "standard": {"samples": 8, "scale": 0.66, "density": 0.15, "children": 20, "radius": 2.0},
    "fine": {"samples": 16, "scale": 0.85, "density": 0.25, "children": 20, "radius": 1.7},
}


class BlenderError(RuntimeError):
    pass


def available() -> Optional[str]:
    """None when Blender can be run here, else why not."""
    if not Path(PYTHON).exists():
        return f"no Python with bpy at {PYTHON} (set PLUSH_BLENDER_PY)"
    return None


def render(frames: Union[str, Path], pngs: Union[str, Path], finish: str = "fur", quality: Union[str, Mapping] = "standard",
           device: str = "OPTIX", guard: bool = True, log: Union[str, Path, None] = None) -> Path:
    """Draws every frame of an export (characters.export) into `pngs`, skipping those already there. `quality` is a
    name of QUALITY or its own settings. With `guard`, the GPU guard pauses the render when the card runs hot."""
    if finish not in FINISHES:
        raise BlenderError(f"no finish {finish!r}; there are {', '.join(FINISHES)}")
    why = available()
    if why:
        raise BlenderError(why)
    frames, pngs = Path(frames), Path(pngs)
    pngs.mkdir(parents=True, exist_ok=True)
    settings = dict(QUALITY[quality]) if isinstance(quality, str) else dict(quality)
    options = pngs / "options.json"
    options.write_text(json.dumps({"finish": finish, "device": device, **settings}))
    command = [PYTHON, str(HERE / "render_frames.py"), str(frames), str(pngs), str(options)]
    if guard and device != "CPU" and GUARD.exists():
        command = ["python3", str(GUARD), "--pause", "78", "--resume", "68", "--abort", "86",
                   "--log", str(pngs / "guard.csv"), "--", *command]
    env = {**os.environ, "LD_LIBRARY_PATH": LIBS + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")}
    done = subprocess.run(command, text=True, capture_output=True, env=env)
    said = [line for line in (done.stdout + done.stderr).splitlines() if line.startswith(("FRAMES", "[guard]", "Traceback", "Error"))]
    if log:
        Path(log).write_text("\n".join(said) + "\n")
    count = len(list(frames.glob("[0-9]*.json")))
    drawn = len(list(pngs.glob("[0-9]*.png")))
    if done.returncode or drawn < count:
        raise BlenderError(f"Blender drew {drawn} of {count} frames (exit {done.returncode}):\n" + "\n".join(said[-6:])
                           + "\n" + (done.stdout + done.stderr)[-1500:])
    for line in said[-2:]:
        print(line, flush=True)
    return pngs
