"""How a character's face and arms are set: the `Pose`, and the mouth vocabulary.

A Pose picks eyes, brows, mouth, arms, gaze, tilt and extras; every 3D model reads it. `MOUTHS` is the list of
mouths a model must be able to draw (and lip-sync speaks in). This lived in `doodle.py`, beside the 2D drawing kit
of the hand-drawn characters; it moved here on 2026-11-11 so the name says what it is. `doodle` still exports both.
"""
from __future__ import annotations

from dataclasses import dataclass, field

Pt = tuple[float, float]


@dataclass(frozen=True)
class Pose:
    eyes: str = "normal"      # normal | wide | half | side | closed | spiral | squint
    brows: str = "none"       # none | flat | raised | skeptic | arched | worried | angry  (arched: one brow up, no lid)
    mouth: str = "flat"       # flat | smile | smug | open | yell | frown | o | wavy
    arms: str = "rest"        # rest | point | raise | chin | present | shrug | panic (see ARMS per character)
    look: Pt = (0.0, 0.0)     # pupil offset, -1..1 in x and y
    tilt: float = 0.0         # degrees, about the feet (rigged characters: the head and a little the torso)
    extras: tuple[str, ...] = field(default_factory=tuple)  # question | sparkle | sweat | blush | sit
    joints: tuple[tuple[str, float], ...] = ()  # rigged characters: extra joint angles (deg), applied last


MOUTHS = ("flat", "smile", "smug", "open", "yell", "frown", "o", "wavy")
