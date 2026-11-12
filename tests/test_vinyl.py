"""The vinyl people (characters.vinyl3d).

    SRLOCATIONS_PY -m pytest characters/tests -q              # everything (about 5 minutes)
    SRLOCATIONS_PY -m pytest characters/tests -q -m "not slow"   # the quick run
"""
import pytest

from characters import clip, film, motion, staging  # noqa: F401
from characters.poses import POSES  # noqa: F401

from helpers import ACTIONS, ALIGNMENT, drawn, one  # noqa: F401

def test_vinyl_people_are_in_the_cast_and_act():
    from characters import cloth, mascots3d as m, vinyl3d
    assert "officer" in film.CAST and "officer" in film.PEOPLE and "bear" in film.PLUSH
    can = film.can("officer")
    assert "wave" in can["actions"] and "wag" not in can["actions"] and "ears" not in can["moves"]
    for pose in POSES["officer"]:
        parts = m.figure("officer", pose).build()
        assert len(parts) > 40
        for part in parts:
            assert cloth.kind(part.material, part.name) in cloth.KINDS
    names = {p.name for p in m.figure("officer", "idle").build()}
    assert {"cap/crown", "cap/peak", "belt/belt", "radio/radio", "badge/badge", "shoe_l/shoe", "mouth/line"} <= names
    assert cloth.kind("vinyl.skin") == "vinyl" and cloth.kind("officer.gold") == "metal" and cloth.kind("vinyl.shoe") == "plastic"
    seated = m.figure("officer", "sit")
    low = min(p.bounds(p.transform)[0].y for p in seated.build() if not isinstance(p, m.Contact)) + seated.transform.position.y
    assert abs(low) < 0.005                                     # it rests on its seat: no gap, no sinking
    f = film.Film("toy", size=(320, 320), fps=12)
    o = f.add("officer", at=(0.5, 0, 0))
    b = f.add("bear", at=(-0.5, 0, 0))
    f.camera((0, 0.6, 6), look_at=(0, 0.4, 0))
    o.look(0.3, b).do(0.6, "wave").pose(2.0, "explain").go(3.0, (0.9, 0.3))
    f.perform(5.0)
    assert drawn(f, o, [k * 0.4 for k in range(12)]) > 400
    with pytest.raises(film.FilmError, match="cannot"):
        f.add("officer", name="second").do(1.0, "clap")         # a paw action is not a person's
