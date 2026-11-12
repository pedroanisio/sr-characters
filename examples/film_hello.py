"""The smallest film: two plush animals, a camera, some acting. Run with characters.SRLOCATIONS_PY.

    python examples/film_hello.py        -> examples/out/film-hello.png, .mp4 and -strip.png
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # the folder that holds characters/
from characters import film  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"

f = film.Film("hello", size=(1080, 1080))
bear = f.add("bear", "idle", at=(0.4, 0, 0))
bunny = f.add("bunny", "idle", at=(-0.4, 0, 0))
f.camera((0, 0.9, 12), look_at=(0, 0.4, 0), lens=110)

bear.look(0.5, bunny).do(1.0, "wave").do(3.0, "jump")
bunny.look(0.8, bear).do(1.6, "giggle").go(4.0, (-0.9, 0.3), style="hops")

print("wrote", f.still(OUT / "film-hello.png"))
print("wrote", f.render(OUT / "film-hello.mp4", seconds=6))
print("wrote", f.strip(OUT / "film-hello-strip.png"))
