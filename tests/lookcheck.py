"""Looks: a few reference stills of each family, and how a new render of the same still is compared with them.

    cd /home/dev/data/sr-data
    PY=/home/dev/src/viral-video-orchestrator/.venvs/srlocations/bin/python
    $PY characters/tests/lookcheck.py list                  # the stills, their finish, whether a reference exists
    $PY characters/tests/lookcheck.py check [name ...]      # render and compare; prints the scores, exit 1 if any differs
    $PY characters/tests/lookcheck.py accept [name ...]     # render and keep as the new reference (an intended change)

A name is a still's name, or any part of it or its finish: `accept lowpoly` takes the three low-poly people,
`check bear` the bear's two. With no name: all of them. `tests/test_looks.py` runs `check` as one test a still.

A still is one character in a pose, seen by a camera, in a finish (`LOOKS`). Its reference is
`tests/looks/<name>.png`, tracked by git. A comparison that fails writes the new render and a picture of the
difference to `tests/looks/new/` (not tracked): `<name>.png` and `<name>.diff.png`, which shows the reference, the
new render and where they differ (four times as bright), side by side.

**The score.** Both pictures are reduced to cells of CELL x CELL pixels (the mean colour of each: ffmpeg does it,
so this needs nothing the SDK's interpreter lacks). A cell's difference is its largest channel difference, in
levels of 255. Two numbers come out, and each has a limit a finish sets (`LIMITS`):

- `changed`: the share of the cells, in percent, that differ by more than TOLERANCE levels. A part that moved,
  vanished or changed colour changes cells by tens of levels; renderer noise does not reach the tolerance.
- `shift`: the mean difference over all cells, in levels. It catches what `changed` cannot: the whole picture
  a little lighter or of another tint, each cell under the tolerance.

**Measured** (2026-11-12, this host, Tesla P40; the numbers are above LIMITS below): the paper finish is the same
to the byte from run to run; Cycles is not (a third of a percent of the pixels differ by one level), and the limits
stand well over that noise and well under the smallest change tried.

**Always local.** A still is drawn on this machine: our engine's `render --frame` has no remote workers (only
`encode` reads SR_WORKERS), Blender runs here, and `render()` below takes SR_WORKERS and SR_WORKER_TOKEN out of
the environment while it draws, so nothing that starts under it can hand work to another machine, whose graphics
card draws outlines a little differently (36 to 39 dB).
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence, Union

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))          # the folder that holds characters/

REFERENCES = HERE / "looks"                        # <name>.png, tracked
NEW = REFERENCES / "new"                           # what a failed comparison leaves to look at, not tracked

CELL = 4            # pixels along the side of a cell
TOLERANCE = 10      # levels (of 255) a cell may differ by before it counts as changed


@dataclass(frozen=True)
class Look:
    """One still: who, in what pose, turned how, seen by what camera, drawn by which finish, at what size."""
    name: str
    who: str
    pose: Any = "idle"                            # a pose's name (or a Pose, for a trial)
    finish: str = "paper"
    size: tuple[int, int] = (480, 480)
    eye: tuple[float, float, float] = (0.0, 0.55, 5.0)
    look_at: tuple[float, float, float] = (0.0, 0.42, 0.0)
    lens: float = 100.0
    yaw: float = 0.0

    @property
    def reference(self) -> Path:
        return REFERENCES / f"{self.name}.png"


_PEOPLE = dict(size=(320, 480), eye=(0.0, 0.58, 6.0), look_at=(0.0, 0.56, 0.0), lens=118.0)   # lowpoly3d.proof's camera

# A handful a family, where a change would show: not every character. Add one here, then `accept <name>`.
LOOKS: tuple[Look, ...] = (
    Look("paper-bear-idle", "bear"),
    Look("paper-bear-sit-cuddle", "bear", "sit-cuddle"),                # seated, both paws at the chin
    Look("paper-bunny-yell", "bunny", "yell"),                          # long ears, brows, an open mouth
    Look("paper-bunny-sit-wonder", "bunny", "sit-wonder", yaw=-35),     # turned: the tail and the far ear
    Look("paper-bip-explain", "bip", "explain"),                        # a robot: screen face, gear, a raised arm
    Look("vinyl-officer-idle", "officer", finish="vinyl", yaw=-18,      # vinyl3d.proof's view
         eye=(0.0, 0.6, 3.5), look_at=(0.0, 0.45, 0.0), lens=70.0),
    Look("fur-bear-idle", "bear", finish="fur"),
    Look("lowpoly-sergeant-front", "sergeant", finish="lowpoly", **_PEOPLE),
    Look("lowpoly-cook-front", "cook", finish="lowpoly", **_PEOPLE),
    Look("lowpoly-captain-front", "captain", finish="lowpoly", **_PEOPLE),
)

# Run-to-run noise, measured 2026-11-12 on this host (Tesla P40, OptiX; CELL 4, TOLERANCE 10): each still drawn
# four times (paper: three), every run compared with the first.
#   finish     stills            changed %   shift (levels)    worst cell   per pixel, before the cells
#   paper      all five          0           0                 0            the files are the same to the byte
#   vinyl      officer           0           0.003 to 0.004    1            0.34% of pixels differ, by 1 level
#   fur        bear              0           0.003             1            0.33% of pixels differ, by 1 level
#   lowpoly    sergeant          0           0.000             0            a handful of pixels differ, by 1 level
# The smallest changes tried, against the same stills (a part moved, taken away or recoloured, in the process only):
#   paper      an ear turned 3 degrees     0.201       0.060       33
#   paper      the bear without its nose   0.201       0.108       130
#   vinyl      the officer without a badge 0.188       0.180       142
#   fur        an ear turned 10 degrees    0.229       0.119       57
#   fur        the bear without its nose   0.208       0.143       115
# So the limits: `changed` at most 0.02% (two cells of a 480 x 480 still; the noise reaches a tenth of TOLERANCE
# in its worst cell, and the smallest change tried is ten times the limit), `shift` at most 0.03 levels (seven
# times the Cycles noise, half the smallest change tried). The paper finish gets the same room though it needs none.
# They hold for this host's GPU: another card draws outlines a little differently (accept the references there).
# (changed %, shift) a new render may differ from its reference by, a finish
LIMITS: dict[str, tuple[float, float]] = {
    "paper": (0.02, 0.03), "vinyl": (0.02, 0.03), "fur": (0.02, 0.03), "lowpoly": (0.02, 0.03),
}
# about how long a still takes here, seconds, Blender's with its kernels already built (the first render after its
# cache is cleared takes about 2.5 minutes)
SECONDS = {"paper": 1, "vinyl": 5, "fur": 7, "lowpoly": 3}


@dataclass(frozen=True)
class Score:
    changed: float       # percent of the cells that differ by more than TOLERANCE
    shift: float         # mean difference of a cell, levels
    worst: int           # the largest difference of one cell, levels (told, not judged)

    def within(self, finish: str) -> bool:
        changed, shift = LIMITS[finish]
        return self.changed <= changed and self.shift <= shift

    def __str__(self) -> str:
        return f"changed {self.changed:.3f}% of the picture, shift {self.shift:.3f} levels (worst cell {self.worst})"


class LookError(Exception):
    """A still could not be drawn or compared; the message says why."""


def unavailable(look: Look) -> Optional[str]:
    """None when this still can be drawn here, else why not."""
    if look.finish == "paper":
        return None
    from characters import blender
    return blender.available()


def render(look: Look, out: Union[str, Path], **fields: Any) -> Path:
    """Draws the still to `out`, on this machine. `fields` are the figure's own (Film.add), for a trial."""
    from characters import film
    f = film.Film("look", size=look.size)
    f.add(look.who, look.pose, yaw=look.yaw, **fields)
    f.camera(look.eye, look_at=look.look_at, lens=look.lens)
    kept = {k: os.environ.pop(k) for k in ("SR_WORKERS", "SR_WORKER_TOKEN") if k in os.environ}   # never on a worker
    try:
        # quality stays a name: Film.still raises TypeError on a mapping (`quality in blender.QUALITY`), 2026-11-12
        return f.still(out, finish=look.finish)
    except film.FilmError as error:
        raise LookError(f"{look.name}: {error}") from error
    finally:
        os.environ.update(kept)


def _run(command: Sequence[str]) -> bytes:
    done = subprocess.run(list(command), capture_output=True)
    if done.returncode:
        raise LookError(f"{command[0]} failed: {done.stderr.decode(errors='replace')[-600:]}")
    return done.stdout


def size_of(picture: Union[str, Path]) -> tuple[int, int]:
    """(width, height) of a PNG, from its header."""
    with open(picture, "rb") as file:
        head = file.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        raise LookError(f"{picture} is not a PNG")
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def cells(picture: Union[str, Path]) -> tuple[int, int, bytes]:
    """The picture as cells of CELL x CELL pixels: (columns, rows, their mean colours as RGB bytes)."""
    width, height = size_of(picture)
    columns, rows = max(1, width // CELL), max(1, height // CELL)
    data = _run(["ffmpeg", "-v", "error", "-i", str(picture), "-vf", f"scale={columns}:{rows}:flags=area",
                 "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
    if len(data) != 3 * columns * rows:
        raise LookError(f"{picture}: read {len(data)} bytes for {columns} x {rows} cells")
    return columns, rows, data


def compare(new: Union[str, Path], reference: Union[str, Path]) -> Score:
    """How far `new` is from `reference` (see the module's text). Pictures of different sizes are refused."""
    if size_of(new) != size_of(reference):
        raise LookError(f"{new} is {size_of(new)} and {reference} is {size_of(reference)}: not the same still")
    columns, rows, a = cells(new)
    _c, _r, b = cells(reference)
    count = columns * rows
    over = total = worst = 0
    for k in range(0, 3 * count, 3):
        d = max(abs(a[k] - b[k]), abs(a[k + 1] - b[k + 1]), abs(a[k + 2] - b[k + 2]))
        total += d
        if d > TOLERANCE:
            over += 1
        if d > worst:
            worst = d
    return Score(100.0 * over / count, total / count, worst)


def difference(new: Union[str, Path], reference: Union[str, Path], out: Union[str, Path]) -> Path:
    """A picture for a person: the reference, the new render, and where they differ (four times as bright)."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    _run(["ffmpeg", "-v", "error", "-y", "-i", str(reference), "-i", str(new), "-filter_complex",
          "[0]format=rgb24,split[r][r2];[1]format=rgb24,split[n][n2];"
          "[r2][n2]blend=all_mode=difference,lutrgb=r='min(val*4,255)':g='min(val*4,255)':b='min(val*4,255)'[d];"
          "[r][n][d]hstack=inputs=3", "-frames:v", "1", str(out)])
    return out


@dataclass(frozen=True)
class Result:
    look: Look
    score: Optional[Score]
    ok: bool
    message: str
    seconds: float


def check(look: Look, folder: Union[str, Path, None] = None, **fields: Any) -> Result:
    """Draws the still again and compares it with its reference. A still that differs is left in `folder`
    (default `NEW`) with a picture of the difference, and the message says where."""
    began = time.time()
    folder = Path(folder) if folder else NEW
    if not look.reference.exists():
        return Result(look, None, False, f"{look.name}: no reference {look.reference}; make it with "
                      f"`lookcheck.py accept {look.name}`", 0.0)
    new = render(look, folder / f"{look.name}.png", **fields)
    score = compare(new, look.reference)
    changed, shift = LIMITS[look.finish]
    took = time.time() - began
    if score.within(look.finish):
        new.unlink()
        (folder / f"{look.name}.diff.png").unlink(missing_ok=True)
        return Result(look, score, True, f"{look.name}: {score}", took)
    diff = difference(new, look.reference, folder / f"{look.name}.diff.png")
    return Result(look, score, False,
                  f"{look.name} no longer looks like its reference: {score}; the {look.finish} finish allows "
                  f"changed {changed:g}% and shift {shift:g}.\n"
                  f"  reference   {look.reference}\n  new render  {new}\n"
                  f"  difference  {diff}  (reference | new | difference x4)\n"
                  f"If the change is meant: {sys.executable} {Path(__file__).resolve()} accept {look.name}",
                  took)


def accept(look: Look) -> Path:
    """Draws the still and keeps it as the reference."""
    REFERENCES.mkdir(parents=True, exist_ok=True)
    fresh = render(look, NEW / f"{look.name}.accepted.png")
    # the reference is kept without an alpha channel and well packed: it is opaque, and git holds every version
    _run(["ffmpeg", "-v", "error", "-y", "-i", str(fresh), "-frames:v", "1", "-pix_fmt", "rgb24",
          "-compression_level", "9", "-pred", "mixed", str(look.reference)])
    fresh.unlink()
    for left in (NEW / f"{look.name}.png", NEW / f"{look.name}.diff.png"):
        left.unlink(missing_ok=True)
    return look.reference


def chosen(names: Sequence[str]) -> list[Look]:
    """The stills whose name or finish holds any of `names`; all of them for no name."""
    if not names:
        return list(LOOKS)
    picked = [look for look in LOOKS if any(n in look.name or n == look.finish for n in names)]
    missing = [n for n in names if not any(n in look.name or n == look.finish for look in LOOKS)]
    if missing:
        raise LookError(f"no still called {', '.join(missing)}; there are {', '.join(look.name for look in LOOKS)}")
    return picked


def main(argv: Sequence[str]) -> int:
    if not argv or argv[0] not in ("list", "check", "accept"):
        print(__doc__)
        return 2
    try:
        looks = chosen(argv[1:])
    except LookError as error:
        print(error)
        return 2
    if argv[0] == "list":
        for look in looks:
            print(f"{look.name:28} {look.finish:8} {look.size[0]}x{look.size[1]}  "
                  f"{'reference' if look.reference.exists() else 'NO REFERENCE'}")
        return 0
    bad = 0
    for look in looks:
        why = unavailable(look)
        if why:
            print(f"{look.name}: skipped, {why}", flush=True)
            continue
        began = time.time()
        try:
            if argv[0] == "accept":
                print(f"{look.name}: accepted, {accept(look)} ({time.time() - began:.0f} s)", flush=True)
            else:
                result = check(look)
                bad += not result.ok
                print(("ok    " if result.ok else "DIFFERS ") + result.message + f" ({result.seconds:.0f} s)", flush=True)
        except LookError as error:
            bad += 1
            print(f"FAILED {error}", flush=True)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
