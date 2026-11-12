"""Before and after for characters/motion.py: the same beats, keyed pose to pose (left) and acted by perform() (right).

    PY=/home/dev/src/viral-video-orchestrator/.venvs/srlocations/bin/python
    $PY examples/motion_demo.py bear           # examples/out/motion-demo-bear.mp4
    $PY examples/motion_demo.py bear 960 540   # a mascot or plush, and a size
"""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from srlocations import Renderer, Styled, portable  # noqa: E402

from characters import clip, dev3d, mascots3d, motion, plush3d  # noqa: E402,F401 (plush3d registers the plush family)
from characters.poses import POSES  # noqa: E402

BEATS = ((1.0, "ask"), (2.5, "explain"), (4.0, "shrug"), (5.3, "surprised"), (6.6, "idle"))
SECONDS = 8.0


def main() -> int:
    who = sys.argv[1] if len(sys.argv) > 1 else "bear"
    width, height = (int(a) for a in sys.argv[2:4]) if len(sys.argv) > 3 else (1280, 720)
    make = lambda **kw: mascots3d.figure(who, "idle", **kw)  # noqa: E731
    controls = lambda p: mascots3d.controls(who, p)  # noqa: E731
    look = mascots3d.LOOKS.get(who, dev3d.look)()
    loc = mascots3d._stage(f"motion-{who}")   # dev3d.stage plus the plush materials
    gap = 0.45
    # a camera on +z sees +x on its left: before on the left of the picture, after on the right
    old = loc.add(make(name="old", at=(gap, 0, 0), yaw=8))
    new = loc.add(make(name="new", at=(-gap, 0, 0), yaw=-8))
    top = old.height
    loc.shot("two", (0, top * 0.6, top * 2.7), (0, top * 0.5, 0), lens=40)
    for t, name in BEATS:                                   # before: one curve from key to key, the face as built
        loc.move(old, t, pose=controls(POSES[who][name]))
    motion.perform(loc, new, BEATS, end=SECONDS)            # after
    loc.move("two", SECONDS)
    renderer = Renderer(collisions=False)
    scene = renderer.compile(loc, "two", Styled(look, width=width, height=height, fps=24))
    dev3d.finish(scene, width, height)
    out = Path(__file__).resolve().parent / "out" / f"motion-demo-{who}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        document = clip.package(scene, Path(folder) / "demo.scene.xml", quiet=True)
        done = subprocess.run([str(renderer.engine), "encode", str(document), "--path", str(out), "--hw", "software",
                               "--parallel", str(clip.PARALLEL)],
                              text=True, capture_output=True)
    if done.returncode:
        raise SystemExit(done.stdout[-2000:] + done.stderr[-2000:])
    font = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    text = lambda label, x: (f"drawtext=fontfile={font}:text='{label}':x={x}-tw/2:y=h*0.91:fontsize=h/22:"
                             "fontcolor=0x222222")
    labelled = out.with_name(out.stem + "-labelled.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out), "-vf",
                    text("antes - pose a pose", "w*0.27") + "," + text("depois - motion.perform", "w*0.73"),
                    "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(labelled)], check=True)
    labelled.replace(out)
    print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
