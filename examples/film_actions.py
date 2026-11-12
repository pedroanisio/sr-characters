"""A set of actions, one after another, on a plush animal and a robot: the clip, and a sheet of each action at
its height.

    PY=/home/dev/src/viral-video-orchestrator/.venvs/srlocations/bin/python
    python3 /home/dev/data/ai3d/scripts/gpu_guard.py -- $PY characters/examples/film_actions.py SET [SEED]
    -> characters/examples/out/film-<set>.mp4 and film-<set>-sheet.png

SET is talking, reactions, everyday, moving, signs, strong, daily or arms. Every action is played with a seed of its own (the bear's and the robot's
differ), so no two are alike; another SEED (default 1) gives another take of the whole clip.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from characters import film, motion  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
SETS = {
    "talking": ("point-at", "tada", "beat", "think", "idea", "shrug", "no-no", "come-here", "listen", "whisper"),
    "reactions": ("laugh", "cry", "sigh", "yawn", "shiver", "flinch", "cower", "huff", "stomp", "puff"),
    "everyday": ("sneeze", "oh-no", "look-around", "double-take", "peek", "nod-off", "love", "bow", "stretch",
                 "crouch"),
    "moving": ("spin", "dance", "tap-foot", "wobble"),
    "signs": ("count", "facepalm", "chin-rub", "thumbs-up", "salute", "shush", "air-quotes", "present", "stop",
              "so-so"),
    "daily": ("scratch-head", "hiccup", "cough", "rub-eyes", "wake-up", "lie-down", "get-up", "check-wrist", "dust-off",
              "tummy-rub"),
    # hands at rest, held out, and up at the face and the head: the arm should look the same arm in all of them
    "arms": ("nod", "wave", "present", "think", "facepalm", "scratch-head", "cough", "salute", "tummy-rub", "cheer"),
    "strong": ("gasp", "cheer-jump", "facepalm-double", "eye-roll", "gulp", "relief", "tantrum", "faint", "blush-hide",
               "startle-jump"),
}
HEIGHT = {"sneeze": 0.67, "double-take": 0.75, "nod-off": 0.62, "eye-roll": 0.47, "relief": 0.3, "startle-jump": 0.3,
          "faint": 0.6, "wake-up": 0.62, "lie-down": 0.8, "get-up": 0.2}   # where an action is at its height, if not half way
SET = sys.argv[1] if len(sys.argv) > 1 else "talking"
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 1
NAMES = SETS[SET]
GAP = 3.9 if SET == "strong" else 2.9

f = film.Film(SET, size=(1280, 720), fps=12)
bear = f.add("bear", "idle", at=(0.42, 0, 0))
bip = f.add("bip", "idle", at=(-0.42, 0, 0))
f.camera((0, 0.75, 9.0), look_at=(0, 0.42, 0), lens=110)
for i, name in enumerate(NAMES):
    t = 0.4 + GAP * i
    if name in ("lie-down", "get-up"):                   # not actions: the actors' own methods; each lies away
        if name == "lie-down":                           # from the other, and is up again in the next slot
            bear.lie_down(t, "right"), bip.lie_down(t, "left")
        else:
            bear.get_up(t), bip.get_up(t)
        continue
    if name == "faint":                                  # each goes over away from the other
        bear.do(t, name, side="right", seed=SEED * 100 + i)
        bip.do(t, name, side="left", seed=SEED * 100 + 50 + i)
        continue
    bear.do(t, name, at=bip, seed=SEED * 100 + i)        # turned to the other: the arm on that side, and
    bip.do(t, name, at=bear, seed=SEED * 100 + 50 + i)   # "point-at" points there; each with a seed of its own
clip = f.render(str(OUT / f"film-{SET}.mp4"), seconds=0.4 + GAP * len(NAMES))

tiles = []
for i, name in enumerate(NAMES):      # a frame of each action at its height, with its name
    t = 0.4 + GAP * i + (motion.ACTIONS[name].seconds if name in motion.ACTIONS else 2.4) * HEIGHT.get(name, 0.5)
    tile = OUT / f".{SET}-{i}.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(clip), "-frames:v", "1", "-vf",
                    f"scale=640:-1,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='{name}'"
                    ":x=16:y=14:fontsize=26:fontcolor=0x141414", str(tile)], check=True)
    tiles.append(tile)
subprocess.run(["ffmpeg", "-v", "error", "-y", *[a for t in tiles for a in ("-i", str(t))], "-filter_complex",
                f"xstack=inputs={len(tiles)}:layout=" + "|".join(f"{640 * (k % 5)}_{360 * (k // 5)}" for k in range(len(tiles))),
                str(OUT / f"film-{SET}-sheet.png")], check=True)
for t in tiles:
    t.unlink()
print("wrote", clip, OUT / f"film-{SET}-sheet.png")
