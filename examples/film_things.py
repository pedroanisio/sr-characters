"""With things, and two together: a throw and a catch, a handshake, reading, typing, a phone call (PART hands);
a block pushed and pulled, a crate carried, a long crate carried by two (PART loads).

    PY=/home/dev/src/viral-video-orchestrator/.venvs/srlocations/bin/python
    python3 /home/dev/data/ai3d/scripts/gpu_guard.py -- $PY characters/examples/film_things.py hands|loads [SEED]
    -> characters/examples/out/film-things-<part>.mp4 and film-things-<part>-sheet.png
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from characters import film  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
PART = sys.argv[1] if len(sys.argv) > 1 else "hands"
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 1

f = film.Film(f"things-{PART}", size=(1280, 720), fps=12)
shots = []
if PART == "hands":
    bear = f.add("bear", "idle", at=(0.62, 0, 0))
    bip = f.add("bip", "idle", at=(-0.62, 0, 0))
    f.camera((0, 0.8, 9.5), look_at=(0, 0.42, 0), lens=110)
    bear.turn(0.4, bip), bip.turn(0.4, bear)
    f.throw(1.5, bear, bip, "ball", seed=SEED)                 # over, and back again
    f.throw(4.5, bip, bear, "ball", seed=SEED + 2)
    shots += [("throw", 2.75), ("catch", 3.2), ("throw back", 5.75)]
    bear.hold(7.0, None)
    bear.go(7.2, (0.34, 0.0), style="walk"), bip.go(7.2, (-0.34, 0.0), style="walk")
    f.handshake(8.4, bear, bip, seed=SEED + 4)
    shots.append(("handshake", 9.5))
    bear.go(11.0, (0.62, 0.0), style="back-away"), bip.go(11.0, (-0.62, 0.0), style="back-away")
    bear.turn(12.4, 0.0), bip.turn(12.4, 0.0)                  # to the camera
    bear.hold(13.0, "book"), bip.hold(13.0, "phone", "left")
    bear.read(13.4, seed=SEED + 5), bip.phone(13.4, seed=SEED + 6)
    shots.append(("read / phone", 15.1))
    bear.hold(17.2, "phone"), bip.hold(17.2, "book")           # and the other way round
    bear.phone(17.6, seed=SEED + 9), bip.read(17.6, seed=SEED + 10)
    shots.append(("phone / read", 19.3))
    bear.hold(21.4, None), bip.hold(21.4, None)
    bear.do(21.8, "type", seed=SEED + 7), bip.do(21.8, "type", seed=SEED + 8)
    shots.append(("type", 23.2))
    END = 25.4
else:
    bear = f.add("bear", "idle", at=(1.1, 0, 0))
    bip = f.add("bip", "idle", at=(-1.1, 0, 0))
    f.camera((0, 0.85, 11.0), look_at=(0, 0.4, 0), lens=110)
    bear.turn(0.4, bip), bip.turn(0.4, bear)
    bear.hold(1.0, "block"), bip.hold(1.0, "crate")
    bear.push(1.6, (0.5, 0.0)), bip.carry(1.6, (-0.5, 0.0))
    shots += [("push", 3.0), ("carry", 3.2)]
    bear.pull(6.2, (1.1, 0.0)), bip.carry(6.2, (-1.1, 0.0), style="carry-back")
    shots += [("pull", 7.6), ("carry back", 7.9)]
    bear.hold(10.4, None), bip.hold(10.4, None)
    bear.go(10.8, (0.44, 0.0), style="walk"), bip.go(10.8, (-0.44, 0.0), style="walk")
    bear.hold(12.6, "long-crate")
    f.carry_together(13.6, bear, bip, (0.9, 0.9))
    shots.append(("carry together", 16.0))
    END = 20.0
clip = f.render(str(OUT / f"film-things-{PART}.mp4"), seconds=END)

tiles = []
for i, (name, at) in enumerate(shots):
    tile = OUT / f".things-{i}.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{at:.2f}", "-i", str(clip), "-frames:v", "1", "-vf",
                    f"scale=640:-1,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='{name}'"
                    ":x=16:y=14:fontsize=26:fontcolor=0x141414", str(tile)], check=True)
    tiles.append(tile)
subprocess.run(["ffmpeg", "-v", "error", "-y", *[a for t in tiles for a in ("-i", str(t))], "-filter_complex",
                f"xstack=inputs={len(tiles)}:fill=0xF1F0EA:layout=" + "|".join(f"{640 * (k % 4)}_{360 * (k // 4)}" for k in range(len(tiles))),
                str(OUT / f"film-things-{PART}-sheet.png")], check=True)
for tile in tiles:
    tile.unlink()
print("wrote", clip, OUT / f"film-things-{PART}-sheet.png")
