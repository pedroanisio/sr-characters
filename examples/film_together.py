"""Two at once, a thing that changes hands, and a robot's screen: a high five, a hug, a pat on the head, a gift
given, a tumble, one following another; a robot that glitches, shows pictures, switches off and comes back on.

    PY=/home/dev/src/viral-video-orchestrator/.venvs/srlocations/bin/python
    python3 /home/dev/data/ai3d/scripts/gpu_guard.py -- $PY characters/examples/film_together.py [SEED]
    -> characters/examples/out/film-together.mp4 and film-together-sheet.png
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from characters import film  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 1

f = film.Film("together", size=(1280, 720), fps=12)
bear = f.add("bear", "idle", at=(0.5, 0, 0))
bunny = f.add("bunny", "idle", at=(-0.18, 0, 0))
bip = f.add("bip", "idle", at=(-1.1, 0, 0))
f.camera((-0.2, 0.8, 10.5), look_at=(-0.2, 0.4, 0), lens=110)

f.high_five(0.5, bear, bunny, seed=SEED)
f.hug(2.6, bear, bunny, seed=SEED + 10)
f.pat(5.6, bear, bunny, seed=SEED + 20)
f.give(8.0, bear, bunny, "gift", seed=SEED + 30)        # the bear holds it from the start
bear.do(10.6, "fall", seed=SEED + 40)
bunny.go(13.4, (-0.18, 0.9), style="skip", seed=SEED)
bear.follow(13.0, bunny, seed=SEED + 1)

bip.do(0.6, "glitch", seed=SEED + 50)
bip.do(2.6, "screen-icon", icon="heart", at=bunny).do(5.0, "screen-icon", icon="question")
bip.power_down(7.4).power_up(10.0).do(12.2, "screen-icon", icon="exclaim")
clip = f.render(str(OUT / "film-together.mp4"), seconds=16.0)

SHOTS = (("high-five | glitch", 1.25), ("hug | heart", 3.9), ("pat | question", 6.5), ("give | off", 8.95),
         ("taken | coming on", 10.5), ("fall", 11.3), ("exclaim", 13.0), ("follow", 14.9))
tiles = []
for i, (name, t) in enumerate(SHOTS):
    tile = OUT / f".together-{i}.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(clip), "-frames:v", "1", "-vf",
                    f"scale=640:-1,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='{name}'"
                    ":x=16:y=14:fontsize=26:fontcolor=0x141414", str(tile)], check=True)
    tiles.append(tile)
subprocess.run(["ffmpeg", "-v", "error", "-y", *[a for t in tiles for a in ("-i", str(t))], "-filter_complex",
                f"xstack=inputs={len(tiles)}:fill=0xF1F0EA:layout=" + "|".join(f"{640 * (k % 4)}_{360 * (k // 4)}" for k in range(len(tiles))),
                str(OUT / "film-together-sheet.png")], check=True)
for t in tiles:
    t.unlink()
print("wrote", clip, OUT / "film-together-sheet.png")
