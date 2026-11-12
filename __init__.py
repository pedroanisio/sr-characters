"""The plush family: our cast, for any video made with scene-render.

Every character is a 3D model with a skeleton, and the render makes it 2D at the camera's angle
(sr-data/decisions/0001). The cast is the plush family and nothing else (the operator, 2026-11-11); Dev, Professor
Frog, Chick and the Mouse were removed and are kept, as they were, in `sr-data/characters_legacy/` for the videos
made with them.

    import sys; sys.path.insert(0, "/home/dev/data/sr-data")
    from characters import film            # the SDK: see SDK.md

`CAST` names every character and its model; `POSES[who]` its poses; `check()` says what a character lacks.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SR_CORE = Path(os.environ.get("SR_CORE", "/home/dev/src/viral-video-orchestrator/vendor/sr-core/v1.9.0"))
ENGINE = os.environ.get("SCENE_RENDER", "/home/dev/src/viral-video-orchestrator/vendor/bin/scene-render")
SRLOCATIONS_PY = os.environ.get("SRLOCATIONS_PY", "/home/dev/src/viral-video-orchestrator/.venvs/srlocations/bin/python")
try:  # sr-core is standard-library only: put it on the path if the caller has not
    import sr_core  # noqa: F401
except ImportError:
    sys.path.insert(0, str(SR_CORE))

from . import doodle, marker, paper  # noqa: E402
from .doodle import INK, Kit, Pose  # noqa: E402
from .marker import PAPER, PEN, MarkerKit  # noqa: E402
from .poses import CANON, POSES  # noqa: E402

STYLES = {"marker": MarkerKit, "doodle": Kit}


@dataclass(frozen=True)
class Character:
    key: str
    name: str
    model: str    # the 3D model's module and name, run in srlocations' interpreter (SRLOCATIONS_PY)


ARMS_3D = {"rest", "present", "point", "raise", "chin", "shrug", "panic", "run", "cuddle"}  # the 3D models' arm gestures (IK)


def model_only(key: str, name: str, model: str) -> Character:
    """A character: a 3D model, with no 2D drawing (2D only as paintover on the render, decisions/0001)."""
    return Character(key, name, model)


CAST: dict[str, Character] = {
    # the plush family: only 3D models (no 2D drawing; 2D only as paintover on the render)
    "bear": model_only("bear", "Bear Cub", "plush3d.py:bear"),
    "cat": model_only("cat", "Kitten", "plush3d.py:cat"),
    "pig": model_only("pig", "Piggy", "plush3d.py:pig"),
    "bunny": model_only("bunny", "Bunny", "plush3d.py:bunny"),
    "redpanda": model_only("redpanda", "Red Panda", "plush3d.py:redpanda"),
    "quokka": model_only("quokka", "Quokka", "plush3d.py:quokka"),
    "fennec": model_only("fennec", "Fennec", "plush3d.py:fennec"),
    "otter": model_only("otter", "Sea Otter", "plush3d.py:otter"),
    "koala": model_only("koala", "Koala", "plush3d.py:koala"),
    "pika": model_only("pika", "Pika", "plush3d.py:pika"),
    "axolotl": model_only("axolotl", "Axolotl", "plush3d.py:axolotl"),
    "treefrog": model_only("treefrog", "Tree Frog", "plush3d.py:treefrog"),
    "arcticfox": model_only("arcticfox", "Arctic Fox", "plush3d.py:arcticfox"),
    "hippo": model_only("hippo", "Pygmy Hippo", "plush3d.py:hippo"),
    "lion": model_only("lion", "Lion", "plush3d.py:lion"),
    "tiger": model_only("tiger", "Tiger", "plush3d.py:tiger"),
    "panda": model_only("panda", "Panda", "plush3d.py:panda"),
    "eagle": model_only("eagle", "Bald Eagle", "plush3d.py:eagle"),
    "duck": model_only("duck", "Duck", "plush3d.py:duck"),
    "dragon": model_only("dragon", "Dragon", "plush3d.py:dragon"),
    "armadillo": model_only("armadillo", "Armadillo", "plush3d.py:armadillo"),
    "shark": model_only("shark", "Shark", "plush3d.py:shark"),
    # the plush robots
    "bip": model_only("bip", "Bip", "plush3d.py:bip"),
    "zap": model_only("zap", "Zap", "plush3d.py:zap"),
    "tec": model_only("tec", "Tec", "plush3d.py:tec"),
    "lata": model_only("lata", "Latinha", "plush3d.py:lata"),
    "java": model_only("java", "Java", "plush3d.py:java"),
    "c": model_only("c", "C", "plush3d.py:c"),
    "python": model_only("python", "Python", "plush3d.py:python"),
    "claude": model_only("claude", "Claude", "plush3d.py:claude"),
    "chatgpt": model_only("chatgpt", "ChatGPT", "plush3d.py:chatgpt"),
}


def check(who: str | None = None) -> list[str]:
    """What keeps a character from being complete: a missing canonical pose, or an arm gesture the 3D models cannot
    do. Empty when complete."""
    problems = []
    for w in [who] if who else list(CAST):
        poses = POSES.get(w, {})
        problems += [f"{w}: missing pose {name!r}" for name in CANON if name not in poses]
        problems += [f"{w}: pose {name!r} uses arms={p.arms!r}, which the 3D models cannot do"
                     for name, p in poses.items() if p.arms not in ARMS_3D]
    return problems


def pose_of(who: str, pose: str | Pose | None) -> Pose:
    if pose is None:
        return Pose()
    if isinstance(pose, Pose):
        return pose
    try:
        return POSES[who][pose]
    except KeyError:
        raise KeyError(f"{who} has no pose {pose!r}; poses: {', '.join(POSES.get(who, {}))}") from None


__all__ = ["ARMS_3D", "model_only", "CANON", "CAST", "Character", "ENGINE", "INK", "Kit", "MarkerKit", "PAPER", "PEN", "POSES", "Pose",
           "ROOT", "STYLES", "check", "doodle", "marker", "paper", "pose_of"]
