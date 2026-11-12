"""A bottle popped, a toast, a drink: one opens the sparkling wine, three touch glasses, they drink.

    PY=/home/dev/src/viral-video-orchestrator/.venvs/srlocations/bin/python
    python3 /home/dev/data/ai3d/scripts/gpu_guard.py -- $PY characters/examples/film_cheers.py [SEED]
    -> characters/examples/out/film-cheers.mp4 and film-cheers-sheet.png
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from characters import film  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 1

f = film.Film("cheers", size=(1280, 720), fps=12)
bear = f.add("bear", "idle", at=(0.62, 0, 0))
cat = f.add("cat", "idle", at=(0.0, 0, 0.1))
bunny = f.add("bunny", "idle", at=(-0.62, 0, 0))
bip = f.add("bip", "idle", at=(-1.45, 0, 0), yaw=-25)
f.camera((-0.35, 0.8, 11.0), look_at=(-0.35, 0.42, 0), lens=110)

bip.pop_cork(0.5, seed=SEED)                         # it holds the bottle from the start
for k, actor in enumerate((bear, cat, bunny)):
    actor.look(0.4, bip).do(1.9, "surprise", seed=SEED + k).look(3.2, None)
bunny.hold(0.0, "mug", "right")                      # the bunny drinks beer; the others get a glass of wine
f.toast(3.8, bear, cat, bunny, seed=SEED + 10)
bear.drink(6.2, seed=SEED + 20)
cat.drink(6.5, seed=SEED + 21)
bunny.drink(6.8, seed=SEED + 22)
bip.do(6.4, "cheer", seed=SEED + 30)
clip = f.render(str(OUT / "film-cheers.mp4"), seconds=10.0)

SHOTS = (("bottle", 0.3), ("shake", 1.0), ("pop", 1.95), ("foam", 2.35), ("toast", 4.75), ("drink", 7.7), ("after", 9.6))
tiles = []
for i, (name, t) in enumerate(SHOTS):
    tile = OUT / f".cheers-{i}.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(clip), "-frames:v", "1", "-vf",
                    f"scale=640:-1,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='{name}'"
                    ":x=16:y=14:fontsize=26:fontcolor=0x141414", str(tile)], check=True)
    tiles.append(tile)
subprocess.run(["ffmpeg", "-v", "error", "-y", *[a for t in tiles for a in ("-i", str(t))], "-filter_complex",
                f"xstack=inputs={len(tiles)}:fill=0xF1F0EA:layout=" + "|".join(f"{640 * (k % 4)}_{360 * (k // 4)}" for k in range(len(tiles))),
                str(OUT / "film-cheers-sheet.png")], check=True)
for t in tiles:
    t.unlink()
print("wrote", clip, OUT / "film-cheers-sheet.png")
