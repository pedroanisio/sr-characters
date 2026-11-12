"""Looks: each reference still (tests/looks/<name>.png) is rendered again and compared by number (tests/lookcheck.py).

    SRLOCATIONS_PY -m pytest characters/tests/test_looks.py -q              # the paper stills: about 1 s each
    SRLOCATIONS_PY -m pytest characters/tests/test_looks.py -q -m looks     # all: the Blender ones too (GPU, 3 to 9 s
                                                                           # each once Blender's kernels are built)
    LOOKS=1 SRLOCATIONS_PY -m pytest characters/tests -q                    # the same, inside any other run
    SRLOCATIONS_PY characters/tests/lookcheck.py accept [name ...]          # an intended change: new references

A still that differs fails with its name, the score, the limit and the paths of the new render and of a picture
of the difference (tests/looks/new/). Everything is drawn on this machine, never on a render worker.
"""
import dataclasses
import os

import pytest

import lookcheck
from characters import film, mascots3d  # noqa: F401  (film loads every family: their poses and colours)
from characters.poses import POSES

pytestmark = pytest.mark.looks


def _asked(config) -> bool:
    """Were the slow stills asked for: `-m looks` (any expression naming the marker) or LOOKS=1."""
    return "looks" in (config.getoption("markexpr") or "") or os.environ.get("LOOKS", "") not in ("", "0")


@pytest.mark.parametrize("look", lookcheck.LOOKS, ids=lambda look: look.name)
def test_look(look, request):
    if look.finish != "paper" and not _asked(request.config):
        pytest.skip(f"a Blender still (about {lookcheck.SECONDS[look.finish]} s on the GPU): run with -m looks or LOOKS=1")
    why = lookcheck.unavailable(look)
    if why:
        pytest.skip(why)
    result = lookcheck.check(look)
    if not result.ok:
        pytest.fail(result.message, pytrace=False)


def test_every_reference_belongs_to_a_still():
    names = {look.name for look in lookcheck.LOOKS}
    assert len(names) == len(lookcheck.LOOKS)
    assert {p.stem for p in lookcheck.REFERENCES.glob("*.png")} == names        # none missing, none left over
    assert {look.finish for look in lookcheck.LOOKS} <= set(lookcheck.LIMITS)
    for look in lookcheck.LOOKS:
        assert lookcheck.size_of(look.reference) == look.size and max(look.size) <= 480


def test_a_still_is_drawn_here_and_never_on_a_render_worker(tmp_path, monkeypatch):
    """Another machine's graphics card draws outlines a little differently: whatever the environment names as
    render workers, nothing started while a still is drawn is told of them, and the environment is given back."""
    import subprocess
    monkeypatch.setenv("SR_WORKERS", "192.0.2.1:9")
    monkeypatch.setenv("SR_WORKER_TOKEN", "not-a-token")
    told, run = [], subprocess.run

    def spy(command, *args, **kwargs):
        env = kwargs.get("env") or os.environ
        told.append((str(command[0]).rsplit("/", 1)[-1], "SR_WORKERS" in env or "SR_WORKER_TOKEN" in env))
        return run(command, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", spy)
    look = lookcheck.chosen(["paper-bear-idle"])[0]
    lookcheck.render(look, tmp_path / "still.png")
    assert told and not any(knows for _name, knows in told), told               # the engine was started, unaware
    assert os.environ["SR_WORKERS"] == "192.0.2.1:9" and os.environ["SR_WORKER_TOKEN"] == "not-a-token"
    assert lookcheck.compare(tmp_path / "still.png", look.reference).within("paper")


def test_the_comparison_notices_a_part_that_moved_vanished_or_changed_colour(request, tmp_path, monkeypatch):
    """The limits are worth something: three small changes to the bear, made here only, each fail; the bear as
    it is passes twice."""
    if not _asked(request.config):
        pytest.skip("five more paper stills: run with -m looks or LOOKS=1")
    look = lookcheck.chosen(["paper-bear-idle"])[0]
    for _ in range(2):
        same = lookcheck.check(look, tmp_path)
        assert same.ok and same.score.changed == 0.0, same.message

    moved = lookcheck.check(look, tmp_path, ear_left=3.0)                        # an ear turned three degrees
    assert not moved.ok and moved.score.changed > 5 * lookcheck.LIMITS["paper"][0], moved.message
    assert (tmp_path / f"{look.name}.png").exists() and (tmp_path / f"{look.name}.diff.png").exists()
    for said in (look.name, "changed", "shift", str(look.reference), f"{look.name}.diff.png", "accept"):
        assert said in moved.message

    build = mascots3d.MascotFigure.build
    with monkeypatch.context() as patch:                                         # the bear without its nose
        patch.setattr(mascots3d.MascotFigure, "build", lambda self: [p for p in build(self) if p.name != "nose/nose"])
        gone = lookcheck.check(look, tmp_path)
    assert not gone.ok and gone.score.changed > 5 * lookcheck.LIMITS["paper"][0], gone.message

    with monkeypatch.context() as patch:                                         # a blue bow tie for the red one
        patch.setitem(mascots3d.COLOURS, "bear.bow", "#5B8FD0")
        dyed = lookcheck.check(look, tmp_path)
    assert not dyed.ok and dyed.score.changed > 5 * lookcheck.LIMITS["paper"][0], dyed.message

    tilted = dataclasses.replace(POSES["bear"]["idle"], tilt=POSES["bear"]["idle"].tilt + 2.0)
    leant = lookcheck.check(dataclasses.replace(look, pose=tilted), tmp_path)    # the head two degrees over
    assert not leant.ok and leant.score.shift > 10 * lookcheck.LIMITS["paper"][1], leant.message
    assert lookcheck.check(look, tmp_path).ok                                    # and nothing was left changed
