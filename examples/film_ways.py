"""More ways of going: on tiptoe, a march, a stagger, backing away, a run into a skid, a leap, a trip, a cartwheel,
a moonwalk and a step up on to a box.

    PY=/home/dev/src/viral-video-orchestrator/.venvs/srlocations/bin/python
    python3 /home/dev/data/ai3d/scripts/gpu_guard.py -- $PY characters/examples/film_ways.py [SEED]
    -> characters/examples/out/film-ways.mp4 and film-ways-sheet.png
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from srlocations.nodes import Box  # noqa: E402

from characters import film, motion  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 1
NEAR, FAR = 0.35, 1.15          # how far from the middle each one goes in and out (m)
# (way, where it ends, how long it is given, the share of it at which the sheet shows it)
WAYS = (("tiptoe", NEAR, 3.2, 0.5), ("back-away", FAR, 3.2, 0.5), ("march", NEAR, 2.6, 0.5),
        ("moonwalk", FAR, 3.2, 0.5), ("slide-stop", NEAR, 1.6, 0.38), ("cartwheel", FAR, 2.0, 0.42),
        ("trip", NEAR, 2.2, 0.36), ("leap", FAR, 1.6, 0.36), ("stagger", NEAR, 4.2, 0.5), ("climb-step", NEAR, 2.2, 1.6))
BOX, STEP = 0.42, 0.12          # how far behind each one its box is, and how high

f = film.Film("ways", size=(1280, 720), fps=12)
bear = f.add("bear", "idle", at=(FAR, 0, 0))
bip = f.add("bip", "idle", at=(-FAR, 0, 0))
f.camera((0, 0.85, 11.5), look_at=(0, 0.42, 0), lens=110)
for side in (1, -1):
    f.prop(Box(size=(0.34, STEP, 0.34), at=(side * NEAR, STEP / 2, -BOX), material="plush.blush", name=f"box{side}"))
shots, t = [], 0.4
for k, (actor, other, side) in enumerate(((bear, bip, 1), (bip, bear, -1))):
    actor.turn(0.4, other)                       # they face each other: in is forward, out is behind them
t = 1.4
for i, (way, x, seconds, show) in enumerate(WAYS):
    for k, (actor, side) in enumerate(((bear, 1), (bip, -1))):
        if way == "cartwheel":                   # to its side: it faces the camera for it, and the other after
            actor.turn(t - 0.9, 0.0, seconds=0.6)
            actor.go(t, (side * x, 0.0), style=way)
            actor.turn(t + 1.6, (0.0, 0.0), seconds=0.5)
        elif way == "climb-step":                # up on to the box behind it, round to the camera, a wave, and down again
            actor.climb(t, (side * x, -BOX), rise=STEP).turn(t + 1.7, 0.0).do(t + 2.5, "wave")
            actor.climb(t + 4.6, (side * x, 0.0), rise=-STEP)
        else:
            actor.go(t, (side * x, 0.0), style=way, seed=SEED * 10 + k)
    shots.append((way, t + show * (1.5 if way in motion.LEAPS else min(seconds, 2.6))))
    t += seconds + (1.4 if way == "cartwheel" else 0.5)
clip = f.render(str(OUT / "film-ways.mp4"), seconds=t + 5.0)

tiles = []
for i, (name, at) in enumerate(shots):
    tile = OUT / f".ways2-{i}.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{at:.2f}", "-i", str(clip), "-frames:v", "1", "-vf",
                    f"scale=640:-1,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='{name}'"
                    ":x=16:y=14:fontsize=26:fontcolor=0x141414", str(tile)], check=True)
    tiles.append(tile)
subprocess.run(["ffmpeg", "-v", "error", "-y", *[a for t in tiles for a in ("-i", str(t))], "-filter_complex",
                f"xstack=inputs={len(tiles)}:layout=" + "|".join(f"{640 * (k % 5)}_{360 * (k // 5)}" for k in range(len(tiles))),
                str(OUT / "film-ways-sheet.png")], check=True)
for tile in tiles:
    tile.unlink()
print("wrote", clip, OUT / "film-ways-sheet.png")
