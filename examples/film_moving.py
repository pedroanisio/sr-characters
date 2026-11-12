"""Turning, going and sitting: two characters turn to each other, walk, run, sneak and skip, sit down and get up.

    PY=/home/dev/src/viral-video-orchestrator/.venvs/srlocations/bin/python
    python3 /home/dev/data/ai3d/scripts/gpu_guard.py -- $PY characters/examples/film_moving.py [SEED]
    -> characters/examples/out/film-moving-ways.mp4 and film-moving-ways-sheet.png
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from characters import film  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 1

f = film.Film("moving-ways", size=(1280, 720), fps=12)
bear = f.add("bear", "idle", at=(0.95, 0, 0))
bip = f.add("bip", "idle", at=(-0.95, 0, 0))
f.camera((0, 0.8, 10.5), look_at=(0, 0.4, 0), lens=110)
for k, (actor, other, side) in enumerate(((bear, bip, 1), (bip, bear, -1))):
    actor.turn(0.4, other)                                              # to face the other, and stay so
    actor.go(1.6, (side * 0.4, 0.0), style="walk", seed=SEED * 10 + k)
    actor.go(4.0, (side * 0.95, 0.0), style="run", seed=SEED * 10 + k)
    actor.go(5.6, (side * 0.5, 0.0), style="sneak", seed=SEED * 10 + k)
    actor.go(8.6, (side * 0.95, 0.0), style="skip", seed=SEED * 10 + k)
    actor.turn(10.6, 0.0)                                               # to the camera
    actor.sit(11.6, "sit-happy").stand(14.0).do(15.0, "wave", seed=SEED * 10 + k)
clip = f.render(str(OUT / "film-moving-ways.mp4"), seconds=17.0)

SHOTS = (("turn", 0.75), ("walk", 2.2), ("run", 4.25), ("sneak", 7.0), ("skip", 9.2), ("sit", 12.9), ("stand", 14.25))
tiles = []
for i, (name, t) in enumerate(SHOTS):
    tile = OUT / f".ways-{i}.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(clip), "-frames:v", "1", "-vf",
                    f"scale=640:-1,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='{name}'"
                    ":x=16:y=14:fontsize=26:fontcolor=0x141414", str(tile)], check=True)
    tiles.append(tile)
subprocess.run(["ffmpeg", "-v", "error", "-y", *[a for t in tiles for a in ("-i", str(t))], "-filter_complex",
                f"xstack=inputs={len(tiles)}:fill=0xF1F0EA:layout=" + "|".join(f"{640 * (k % 4)}_{360 * (k // 4)}" for k in range(len(tiles))),
                str(OUT / "film-moving-ways-sheet.png")], check=True)
for t in tiles:
    t.unlink()
print("wrote", clip, OUT / "film-moving-ways-sheet.png")
