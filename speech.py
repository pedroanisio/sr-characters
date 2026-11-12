"""Lip sync: a `mouths` track for `characters.motion.perform()` from a voice's character timestamps.

`lipsync(alignment, at)` reads the letters as Portuguese sounds and gives [(time, mouth, openness)];
`characters.film.Actor.say()` is the usual way in. `characters.motion` re-exports every name of this module
(`motion.lipsync`), but a constant is changed here: set `speech.LIP_LEAD`, not `motion.LIP_LEAD`.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping, Optional, Union

LIP_RATE = 24.0      # mouth keys per second (perform(face_fps=24) shows them all while the body is keyed on twos)
LIP_LEAD = 0.085     # s the mouth shows a sound before it is heard (0.04 measured a frame late on ep01: 2 frames)
LIP_PAUSE = 0.15     # s of silence inside a take after which the mouth closes (shorter gaps hold the last shape)
LIP_SHUT = 0.09      # s the lips stay pressed on m, b, p at least (the closure the eye looks for)
LIP_ATTACK, LIP_RELEASE = 0.75, 0.55   # share of the way to its target the openness goes per key, opening / closing
_VOWELS = "aáàâãeéêiíoóôõuúy"


def _word_sounds(word: str) -> list[tuple[str, float]]:
    """(mouth, openness weight) per letter of one Brazilian Portuguese word, read as it sounds rather than spelled:
    vowels by height (a open, e and o mid, i a slit, u small and round), unstressed final e / o as i / u, a nasal
    vowel (before m/n that ends the syllable) less open, the u of que/qui/gue/gui silent, m b p shut, ch x j round
    the lips, lh nh spread them, any other consonant already on its way to the next vowel (or held from the last)."""
    w = word.lower()
    n = len(w)
    accented = any(c in "áàâãéêíóôõú" for c in w)
    out: list[Optional[tuple[str, float]]] = [None] * n
    for k, c in enumerate(w):
        nxt = w[k + 1] if k + 1 < n else ""
        after = w[k + 2] if k + 2 < n else ""
        final = k == n - 1 or (k == n - 2 and nxt == "s")
        nasal = nxt != "" and nxt in "mn" and (after == "" or after not in _VOWELS) and c in _VOWELS
        if c in "aáàâ":
            m = ("open", 1.0 if c in "áà" else 0.9)
        elif c == "ã":
            m = ("open", 0.6)
        elif c in "eéê":
            if c == "e" and (final and not accented and n > 1 or w == "e"):
                m = ("open", 0.32)                          # an unstressed final e is an i
            else:
                m = ("open", 0.8 if c == "é" else 0.6)
        elif c in "iíy":
            m = ("open", 0.35)
        elif c in "oóô":
            if c == "o" and final and not accented and n > 1:
                m = ("o", 0.45)                             # an unstressed final o is a u
            else:
                m = ("o", 0.95 if c == "ó" else 0.75)
        elif c == "õ":
            m = ("o", 0.55)
        elif c in "uú":
            if k > 0 and w[k - 1] in "qg" and nxt in "eéêií":
                m = None                                    # que, qui, gue, gui: the u is not heard
            else:
                m = ("o", 0.5)
        elif c in "mbp":
            prev = w[k - 1] if k else ""
            m = None if (c == "m" and prev in _VOWELS and (nxt == "" or nxt not in _VOWELS)) else ("flat", 0.0)
        elif c == "h" and k and w[k - 1] in "ln":
            m = ("open", 0.3)
        elif c == "h" and k and w[k - 1] == "c" or c in "xj":
            m = ("o", 0.4)
        else:
            m = None
        if m is not None and nasal and m[0] != "flat":
            m = (m[0], m[1] * 0.7)
        out[k] = m
    for k in range(n):                                      # consonants: toward the next vowel, else hold the last
        if out[k] is None:
            ahead = next((out[j] for j in range(k + 1, n) if out[j] and out[j][0] != "flat"), None)
            behind = next((out[j] for j in range(k - 1, -1, -1) if out[j] and out[j][0] != "flat"), None)
            shape = ahead or behind or ("flat", 0.0)
            out[k] = (shape[0], shape[1] * 0.45)
    return out  # type: ignore[return-value]


def _loudness(audio: Union[str, "Path"], offset: float):
    """A function of a second on the track's clock -> how loud the voice is there, 0..1: RMS over 40 ms of `audio`
    (the file starts at `offset` on that clock), in dB, between the quiet and loud ends of its own speech."""
    import array
    import subprocess
    rate = 8000
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(audio), "-ac", "1", "-ar", str(rate), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    x = array.array("h", raw)
    hop, half = rate // 100, rate // 50                      # a value every 10 ms, over +-20 ms
    db = []
    for c in range(0, len(x), hop):
        seg = x[max(0, c - half):c + half]
        db.append(10 * math.log10(sum(v * v for v in seg) / max(1, len(seg)) / 32768.0 ** 2 + 1e-10))
    voiced = sorted(v for v in db if v > -50)
    if not voiced:
        return lambda t: 0.0
    lo, hi = voiced[int(0.15 * (len(voiced) - 1))], voiced[int(0.97 * (len(voiced) - 1))]

    def at(t: float) -> float:
        k = int(round((t - offset) * 100))
        v = db[k] if 0 <= k < len(db) else -100.0
        return max(0.0, min(1.0, (v - lo) / max(1.0, hi - lo)))
    return at


def lipsync(alignment: Mapping[str, Any], at: float = 0.0, audio: Optional[Union[str, "Path"]] = None,
            audio_at: Optional[float] = None, rate: float = LIP_RATE) -> list[tuple[float, Optional[str], Optional[float]]]:
    """A `mouths` track for perform() [(time, mouth, openness)] from a voice's character timestamps (ElevenLabs
    `alignment`: `characters`, `character_start_times_seconds`, `character_end_times_seconds`), the take starting at
    `at` seconds. The letters, read as Portuguese sounds (`_word_sounds`), give the shape and how open it can be;
    `audio` (the voice; the file starts at `audio_at`, default `at`) gives how loud each moment is, so stressed
    syllables open wide and quick small words barely do. m, b, p shut the lips for LIP_SHUT at least. Keyed at `rate`,
    LIP_LEAD early, eased open and shut; a pause longer than LIP_PAUSE closes the mouth; after the take, None.
    Give it to perform(..., mouths=track, face_fps=rate)."""
    chars = alignment["characters"]
    starts, ends = alignment["character_start_times_seconds"], alignment["character_end_times_seconds"]
    spoken = [i for i, c in enumerate(chars) if c.isalpha()]
    if not spoken:
        return []
    sound: dict[int, tuple[str, float]] = {}
    word: list[int] = []
    for i in range(len(chars) + 1):                         # read word by word
        if i < len(chars) and chars[i].isalpha():
            word.append(i)
            continue
        if word:
            for j, m in zip(word, _word_sounds("".join(chars[j] for j in word))):
                sound[j] = m
        word = []
    shut = [(starts[i], max(ends[i], starts[i] + LIP_SHUT)) for i in spoken if sound[i][0] == "flat"]
    loud = _loudness(audio, at if audio_at is None else audio_at) if audio is not None else None
    first, last = starts[spoken[0]], ends[spoken[-1]]
    raw: list[tuple[float, str, float]] = []                   # (time, shape, how open) per key, before easing
    shape_was, opened_was = "flat", 0.0
    k = int(math.floor((at + first - LIP_LEAD) * rate))
    while True:
        t = k / rate
        u = t - at + LIP_LEAD                                  # the take's time this key shows
        if u >= last:
            break
        k += 1
        if u < first:
            continue
        i = next((j for j in spoken if starts[j] <= u < ends[j]), None)
        if any(a <= u < b for a, b in shut):
            target_shape, target = "flat", 0.0
        elif i is None:                                        # between letters: hold across a short gap
            before = max((j for j in spoken if ends[j] <= u), default=None, key=lambda j: ends[j])
            after = min((j for j in spoken if starts[j] > u), default=None, key=lambda j: starts[j])
            gap = (starts[after] if after is not None else last) - (ends[before] if before is not None else first)
            target_shape, target = (shape_was, opened_was * 0.7) if gap <= LIP_PAUSE else ("flat", 0.0)
        else:
            target_shape, weight = sound[i]
            level = 1.0 if loud is None else 0.3 + 0.7 * loud(at + u)   # how loud the sound this key shows is
            target = 0.0 if target_shape == "flat" else max(0.12, min(1.0, weight * level * 1.15))
        raw.append((t, target_shape, target))
        shape_was, opened_was = target_shape, target
    # an open shape (open / o) shown for a single key flickers: it takes its neighbours' shape (closures stay)
    for n in range(1, len(raw) - 1):
        t, sh, o = raw[n]
        if sh != "flat" and raw[n - 1][1] == raw[n + 1][1] != sh and raw[n - 1][1] != "flat":
            raw[n] = (t, raw[n - 1][1], o)
    track: list[tuple[float, Optional[str], Optional[float]]] = []
    shape, opened = "flat", 0.0
    for t, target_shape, target in raw:
        if target_shape == "flat":
            shape, opened = "flat", 0.0                        # the lips shut at once
        else:
            if shape == "flat":
                opened = 0.0
            shape = target_shape
            opened += (target - opened) * (LIP_ATTACK if target > opened else LIP_RELEASE)
        value = 0.0 if shape == "flat" else round(opened, 2)
        if not track or track[-1][1] != shape or abs((track[-1][2] or 0.0) - value) >= 0.04:
            track.append((round(t, 4), shape, value))
    track.append((round(at + last, 4), None, None))
    return track
