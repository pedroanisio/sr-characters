"""Sound and subtitles (characters.soundtrack, and Film.say / sound / music / subtitle).

    SRLOCATIONS_PY -m pytest characters/tests -q              # everything (about 5 minutes)
    SRLOCATIONS_PY -m pytest characters/tests -q -m "not slow"   # the quick run
"""
import pytest

from characters import clip, film, motion, staging  # noqa: F401
from characters.poses import POSES  # noqa: F401

from helpers import ACTIONS, ALIGNMENT, drawn, one  # noqa: F401

def test_a_spoken_take_becomes_subtitles():
    from characters import soundtrack
    words = soundtrack.words_of(ALIGNMENT, at=2.0)
    assert [w[0] for w in words] == ["ola", "bom", "dia"] and abs(words[0][1] - 2.0) < 1e-6 and words[-1][2] > words[-1][1]
    long = {"characters": list("E eu posso achar seu voto um desastre. Só não acho que isso me dê o direito de desejar que você se ferre.")}
    n = len(long["characters"])
    long["character_start_times_seconds"] = [0.05 * i for i in range(n)]
    long["character_end_times_seconds"] = [0.05 * i + 0.05 for i in range(n)]
    cues = soundtrack.cues_of(soundtrack.words_of(long, at=1.0))
    assert cues[0].text == "E eu posso achar seu voto um desastre."                 # cut at the sentence
    assert all(len(c.text) <= 48 for c in cues)                                     # two lines of 24 characters
    assert all(b.start >= a.end for a, b in zip(cues, cues[1:]))                    # one at a time
    assert all(c.end - c.start >= soundtrack.MIN_SECONDS - 1e-6 for c in cues[:-1])
    assert " ".join(c.text for c in cues) == "".join(long["characters"])            # nothing lost
    assert all(c.words and c.words[0][1] == c.start for c in cues)


def test_sound_and_subtitles_go_into_the_scene(tmp_path):
    import wave
    from characters import soundtrack
    from srlocations import Renderer, Styled
    voice = tmp_path / "voice.wav"
    with wave.open(str(voice), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000), w.writeframes(b"\0\0" * 16000)
    f = film.Film("heard", size=(540, 960), fps=12)
    cat = f.add("cat")
    f.camera((0, 0.5, 2), look_at=(0, 0.5, 0))
    cat.say(ALIGNMENT, at=0.3, audio=voice)
    f.music(voice, gain=-10).subtitle("fim", 1.6, 2.4)
    assert [s.role for s in f.sounds] == ["dialogue", "music"] and len(f.cues) == 2
    f.perform(2.5)
    scene = Renderer(collisions=False).compile(f.loc, f._shot, Styled(f.look(), width=540, height=960, fps=12))
    output = soundtrack.apply(scene, 540, 960, f.sounds, f.cues, tmp_path / "x.mp4")
    xml = scene.to_bytes(layout="pretty").decode()
    assert output.burnCaptions == "subtitles" and "<audioMix" in xml and xml.count("<audioTrack") == 2
    assert 'role="dialogue"' in xml and 'duckUnder="track-0"' in xml                # the music gives way to the voice
    assert xml.count("<cue ") == 2 and "<word " in xml and 'normalize="integrated"' in xml
    with pytest.raises(film.FilmError, match="no sound file"):
        f.sound(tmp_path / "missing.wav")
    with pytest.raises(film.FilmError, match="no sound role"):
        f.sound(voice, role="noise")


def test_a_finished_picture_gets_sound_and_subtitles(tmp_path):
    from characters import soundtrack
    scene = soundtrack.cut(tmp_path / "picture.mp4", 540, 960, 24, 3.0, [], [soundtrack.Cue(0.5, 1.5, "oi")], tmp_path / "out.mp4")
    xml = scene.to_bytes(layout="pretty").decode()
    # the engine refuses a video with no stated size, rate and length, and places a layer by its top left corner
    assert 'width="540"' in xml and 'height="960"' in xml and 'fps="24"' in xml and 'duration="3' in xml
    assert 'boxWidth="540"' in xml and 'fit="cover"' in xml and ' x="0"' in xml and ' y="0"' in xml
    assert 'burnCaptions="subtitles"' in xml
