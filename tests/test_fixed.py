"""A figure's fixed list of parts for a film (characters.fixed).

    SRLOCATIONS_PY -m pytest characters/tests -q              # everything (about 5 minutes)
    SRLOCATIONS_PY -m pytest characters/tests -q -m "not slow"   # the quick run
"""
import re

import pytest
from srlocations import Renderer
from srlocations import motion as moving
from srlocations.looks import Styled

from characters import clip, film, fixed, mascots3d

from helpers import ALIGNMENT

FPS = 24


def acted(who="bear", seconds=2.5):
    f = film.Film("fixed", size=(360, 640), fps=FPS)
    a = f.add(who, "idle", name="a")
    a.say(ALIGNMENT, 0.3, subtitles=False).do(0.4, "bounce").do(1.5, "wave")
    f.camera((0, 0.5, 2.4), (0, 0.3, 0))
    f.perform(seconds)
    f.settle()
    return f, a


def shapes(f):
    cut = moving.Clip(f.loc, f._shot, fps=FPS)
    index = f.loc.nodes.index(f.actors[0].fig)
    return [moving.shape(cut._walk(moment.nodes[index])) for moment in cut.moments]


@pytest.mark.parametrize("who", ["bear", "bip", "officer"])
def test_a_figure_that_acts_keeps_one_list_of_parts(who):
    f, a = acted(who)
    slots, most = f.parts["a"]
    assert slots >= most                                   # a place for every part, showing or not
    each = shapes(f)
    assert all(shape == each[0] for shape in each) and len(each[0]) == slots
    a.fig.fixed = None                                     # without it, the list changes as it blinks and talks
    each = shapes(f)
    assert sum(1 for x, y in zip(each, each[1:]) if x != y) > 3


def test_the_fixed_parts_are_where_and_as_big_as_the_drawn_ones():
    f, a = acted()
    for frame in (0, 11, 17, 29, 44):
        now = f.loc.at(frame / FPS).nodes[f.loc.nodes.index(a.fig)]
        with fixed.exact():
            drawn = now.build()
        fitted = [part for part in now.build() if max(part.radii) > 1e-3]      # those that are showing
        assert len(now.build()) == f.parts["a"][0] and len(fitted) == len(drawn)
        size = lambda part: (part.name, part.material, tuple(part.at), part.radii)   # noqa: E731
        assert sorted(map(size, fitted)) == sorted(map(size, drawn))
        for part in fitted:                                # the surface it is written with, scaled, is that size
            if not fixed._is_tube(part):
                reach = [max(abs(p[axis]) for p in fixed._points(part)) * part._scale[axis] for axis in range(3)]
                assert all(r <= part.radii[axis] * 1.03 + 1e-3 for axis, r in enumerate(reach)), part.name


def test_the_scene_holds_the_figure_once_and_keys_its_sizes(tmp_path):
    f, a = acted()
    scene = Renderer(collisions=False).compile(f.loc, f._shot, Styled(f.look(), width=360, height=640, fps=FPS))
    text = clip.package(scene, tmp_path / "f.scene.xml", quiet=True).read_text()
    bodies = re.findall(r'<object3D id="flat-a-body-body-\d+"[^>]*>', text)
    assert len(bodies) == 1 and "start=" not in bodies[0]              # one body for the whole film
    assert text.count('<animate property="scaleY">') > 20              # and sizes that change on every frame
    a.fig.fixed = None
    scene = Renderer(collisions=False).compile(f.loc, f._shot, Styled(f.look(), width=360, height=640, fps=FPS))
    old = clip.package(scene, tmp_path / "o.scene.xml", quiet=True).read_text()
    assert old.count("<object3D ") > 3 * text.count("<object3D ")      # written again at each change, before


def test_a_moment_the_film_was_not_settled_for_is_drawn_as_it_is():
    f, a = acted()
    other = mascots3d.figure("bear", "idle", name="a")
    other.fixed = a.fig.fixed
    other.item = "right:gift"                                           # a part the film never showed
    with fixed.exact():
        drawn = other.build()
    assert [p.name for p in other.build()] == [p.name for p in drawn]
