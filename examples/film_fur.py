"""The same small film twice: our drawn look, and soft toys with real fur (Blender). Run with characters.SRLOCATIONS_PY.

    python examples/film_fur.py        -> examples/out/film-fur-paper.mp4, film-fur.mp4 and film-fur-strip.png
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # the folder that holds characters/
from characters import film  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"


def make() -> film.Film:
    f = film.Film("fur", size=(1080, 1080))
    bear = f.add("bear", "idle", at=(0.34, 0, 0))
    bunny = f.add("bunny", "idle", at=(-0.34, 0, 0))
    f.camera((0, 0.75, 5.2), look_at=(0, 0.42, 0), lens=70)
    bear.look(0.3, bunny).do(0.8, "wave")
    bunny.look(0.5, bear).do(1.4, "giggle")
    return f


print("wrote", make().render(OUT / "film-fur-paper.mp4", seconds=3))
f = make()
print("wrote", f.render(OUT / "film-fur.mp4", seconds=3, finish="fur"))
print("wrote", f.strip(OUT / "film-fur-strip.png", columns=6, rows=1))
