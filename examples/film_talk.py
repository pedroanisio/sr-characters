"""A kitten says a real voice take: lip-sync, the voice and its subtitles, from the SDK alone.
Run with characters.SRLOCATIONS_PY.   python examples/film_talk.py [fur]   -> examples/out/film-talk.mp4
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # the folder that holds characters/
from characters import film  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
TAKE = Path(__file__).resolve().parents[2] / "microentrevistas" / "ep01" / "audio"   # an ElevenLabs take and its timestamps

f = film.Film("talk", size=(1080, 1920))
cat = f.add("cat")
f.camera((0, 0.48, 1.9), look_at=(0, 0.48, 0), lens=50)
cat.say(json.load(open(TAKE / "complemento.json")), at=0.5, audio=TAKE / "complemento.mp3").do(1.2, "palm").do(4.2, "nod")
if sys.argv[1:2] == ["fur"]:
    print("wrote", f.render(OUT / "film-talk-fur.mp4", seconds=6.5, finish="fur"))
else:
    print("wrote", f.render(OUT / "film-talk.mp4", seconds=6.5))
