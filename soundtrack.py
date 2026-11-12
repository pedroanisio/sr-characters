"""Sound and subtitles for a film, written into the scene the engine renders (sr-core's audio mix and caption track).

A film has `sounds` (voices, music, effects, each a file placed at a time) and `cues` (subtitles, each with its
words' times). `apply()` adds them to a compiled scene and gives it an output that burns the subtitles in;
`cut()` builds a scene of its own over a finished picture (the fur finish, drawn by Blender). The engine mixes the
audio, lowers music under voices, brings the whole to a loudness target, and draws the subtitles with the word
being spoken in another colour.

The house subtitle look follows srstudio's (vendor/srstudio native.py, CaptionLook): bold white letters with a dark
outline, the spoken word gold, two lines of 24 characters, shown at least 0.83 s.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Union

BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
ROLES = ("dialogue", "music", "effects", "ambience")
MIN_SECONDS = 0.8333          # the shortest a subtitle is shown (srstudio ADR 0150)


@dataclass(frozen=True)
class Sound:
    path: str
    at: float = 0.0            # s into the film
    role: str = "effects"      # dialogue | music | effects | ambience
    gain: float = 0.0          # dB


@dataclass(frozen=True)
class Cue:
    """One subtitle: shown from `start` to `end`, with each word's own span (for the spoken-word highlight)."""
    start: float
    end: float
    text: str
    words: tuple[tuple[str, float, float], ...] = ()


@dataclass(frozen=True)
class CaptionLook:
    """How subtitles look. Sizes are for a picture 1080 px wide and scale with the film's width."""
    size: float = 53
    color: str = "#FFFFFF"
    active: str = "#F4D492"     # the word being spoken
    stroke: str = "#121415"
    stroke_width: float = 8
    line_height: float = 1.14
    max_chars: int = 24
    max_lines: int = 2
    centre: float = 0.69        # the block's middle, as a share of the height: under the face, clear of a Reel's own text
    width: float = 0.78         # the widest line, as a share of the width
    preset: str = "karaoke"
    font: str = BOLD
    language: str = "pt-BR"


def words_of(alignment: Mapping[str, Any], at: float = 0.0) -> list[tuple[str, float, float]]:
    """The words of a voice take with their times in the film, from its character timestamps (ElevenLabs
    `alignment`: `characters`, `character_start_times_seconds`, `character_end_times_seconds`), the take starting
    at `at`."""
    chars = alignment["characters"]
    starts, ends = alignment["character_start_times_seconds"], alignment["character_end_times_seconds"]
    out, word, first, last = [], "", 0.0, 0.0
    for c, a, b in zip(chars, starts, ends):
        if c.isspace():
            if word:
                out.append((word, at + first, at + last))
            word = ""
            continue
        if not word:
            first = a
        word, last = word + c, b
    if word:
        out.append((word, at + first, at + last))
    return out


def cues_of(words: Sequence[tuple[str, float, float]], look: CaptionLook = CaptionLook(), until: Optional[float] = None) -> list[Cue]:
    """Subtitles for a run of words: as few as fit `look` (two lines of 24 characters), cut after a sentence or a
    comma where one is near the limit, each held at least MIN_SECONDS where the next one allows. `until` is where
    the last one must be gone (default: MIN_SECONDS after its last word at most)."""
    room = look.max_chars * look.max_lines
    blocks: list[list[tuple[str, float, float]]] = []
    current: list[tuple[str, float, float]] = []
    for w in words:
        length = sum(len(x[0]) + 1 for x in current) + len(w[0])
        if current and length > room:
            # prefer the last sentence end or comma in the block, if it leaves a block of a fair size
            cut = next((k for k in range(len(current) - 1, 0, -1) if current[k - 1][0][-1] in ".!?…,;:"
                        and sum(len(x[0]) + 1 for x in current[:k]) >= room * 0.45), len(current))
            blocks.append(current[:cut])
            current = current[cut:]
        current.append(w)
        if w[0][-1] in ".!?…" and sum(len(x[0]) + 1 for x in current) >= room * 0.5:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    out = []
    for k, block in enumerate(blocks):
        start, end = block[0][1], block[-1][2]
        limit = blocks[k + 1][0][1] - 0.02 if k + 1 < len(blocks) else (until if until is not None else end + MIN_SECONDS)
        end = max(end, min(start + MIN_SECONDS, limit))
        out.append(Cue(round(start, 3), round(min(end + 0.25, limit) if k + 1 == len(blocks) else end, 3),
                       " ".join(w[0] for w in block), tuple((w[0], round(w[1], 3), round(w[2], 3)) for w in block)))
    return out


def apply(scene, width: int, height: int, sounds: Sequence[Sound], cues: Sequence[Cue], out: Union[str, Path],
          look: CaptionLook = CaptionLook(), loudness: float = -14.0, true_peak: float = -1.0):
    """Adds the sounds and the subtitles to `scene` and gives it the output that carries them (h264, the subtitles
    burned in). Returns the output element; encode the document with no `--path`, or its output is replaced."""
    assets = scene.find("assets") or scene.add_assets()
    if sounds:
        mix = scene.add_audioMix(sampleRate=48000, channels=2)
        mix.add_master(normalize="integrated", loudness=str(loudness), truePeak=str(true_peak), limiter=True)
        voices, under = [], []
        for k, s in enumerate(sounds):
            if s.role not in ROLES:
                raise ValueError(f"no sound role {s.role!r}; there are {', '.join(ROLES)}")
            assets.add_audio(id=f"sound-{k}", src=str(Path(s.path).resolve()))
            keys: dict[str, Any] = dict(id=f"track-{k}", asset=f"sound-{k}", role=s.role, start=round(s.at, 4))
            if s.gain:
                keys["gain"] = s.gain
            track = mix.add_audioTrack(**keys)
            if s.role == "dialogue":
                voices.append(track.id)
            elif s.role in ("music", "ambience"):
                under.append(track)
        for track in under if voices else ():
            track.duckUnder = " ".join(voices)          # music gives way to a voice
            track.duckAmount = -12
    output = scene.add_output(id="film", path=str(Path(out).resolve()), codec="h264", crf=17)
    if cues:
        k = width / 1080.0
        assets.add_font(id="subtitle-font", src=look.font, family="Subtitle", weight="700")
        block = look.max_lines * look.size * k * look.line_height + 2 * look.stroke_width * k
        track = (scene.find("captions") or scene.add_captions()).add_captionTrack(
            id="subtitles", language=look.language, preset=look.preset, mode="burn", style="subtitle-text",
            activeStyle="subtitle-active", maxCharsPerLine=look.max_chars, maxLines=look.max_lines,
            x="50%", y=f"{100 * (look.centre - block / 2 / height):.2f}%", width=f"{100 * look.width:.1f}%")
        styles = scene.find("styles") or scene.add_styles()
        styles.add_textStyle(id="subtitle-text", fontAsset="subtitle-font", size=round(look.size * k, 2), weight="700",
                             color=look.color, lineHeight=look.line_height, strokeColor=look.stroke,
                             strokeWidth=round(look.stroke_width * k, 2), strokePosition="outside")
        styles.add_textStyle(id="subtitle-active", basedOn="subtitle-text", color=look.active)
        for cue in sorted(cues, key=lambda c: c.start):
            element = track.add_cue(start=cue.start, end=cue.end, text=cue.text)
            for text, a, b in cue.words:
                element.add_word(start=a, end=b, text=text)
        output.burnCaptions = "subtitles"
    return output


def cut(picture: Union[str, Path], width: int, height: int, fps, seconds: float, sounds: Sequence[Sound],
        cues: Sequence[Cue], out: Union[str, Path], look: CaptionLook = CaptionLook()):
    """A scene of its own over a finished picture (a video file): the picture, the sounds, the subtitles. For a
    film drawn by another renderer. Returns the sr-core Scene, ready to package and encode."""
    from sr_core.scene import Scene
    scene = Scene(version="auto")
    scene.add_project(width=width, height=height, fps=str(fps), duration=round(seconds, 4), background="#000000")
    # the engine wants a video's size, rate and length stated: the picture was made at the film's own
    scene.add_assets().add_video(id="picture", src=str(Path(picture).resolve()), width=width, height=height,
                                 fps=str(fps), duration=round(seconds, 4))
    scene.add_composition().add_layer(id="picture-layer", asset="picture", x=0, y=0,     # a layer is placed by its top left corner
                                      boxWidth=width, boxHeight=height, fit="cover", mute=True)
    apply(scene, width, height, sounds, cues, out, look)
    return scene
