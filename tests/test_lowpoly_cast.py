"""Low-poly people drawn from a seed (characters.lowpoly_cast)."""

from __future__ import annotations

from dataclasses import asdict

import pytest

from characters import export, film, lowpoly3d as lp, lowpoly_cast as cast, mascots3d as m


@pytest.fixture(autouse=True)
def _only_here():
    """What a test draws leaves the cast with it: the other tests see the kit's own people."""
    yield
    for key in list(cast.RECIPES):
        cast.dismiss(key)
    assert not [k for k in lp.BODIES if "~" in k] and not [k for k in lp.FACES if "~" in k]


def _parts(f):
    f.camera((0, 0.6, 6), look_at=(0, 0.5, 0))
    f.perform(0.2)
    return export.frame(f.loc.at(0.0), f._shot)["parts"]


def _choices(person):
    return {k: v for k, v in cast.recipe(person).items() if k != "key"} | {
        "person": {k: v for k, v in cast.recipe(person)["person"].items() if k not in ("key", "name")}}


def test_a_seed_is_always_the_same_person_and_another_seed_another():
    a, b = cast.person(42, key="t-a"), cast.person(42, key="t-b")
    assert _choices(a) == _choices(b)
    assert {k: v for k, v in asdict(a).items() if k not in ("key", "name", "body", "face")} == {
        k: v for k, v in asdict(b).items() if k not in ("key", "name", "body", "face")}
    drawn = [cast.person(seed, key=f"t-{seed}") for seed in range(12)]
    looks = {(p.outfit, p.skin, p.hair, p.eyes, p.top, cast.recipe(p)["person"]["body"]) for p in drawn}
    assert len(looks) >= 10                                  # twelve seeds are not twelve times one person
    assert {p.outfit for p in drawn} <= set(lp.OUTFITS) and len({p.outfit for p in drawn}) >= 3
    assert cast.person("ana", key="t-ana").skin == cast.person("ana", key="t-ana2").skin      # a word is a seed too


def test_what_is_pinned_holds_and_changes_no_other_draw():
    free, pinned = cast.person(5, key="t-free"), cast.person(5, key="t-pin", hair="lp.hair-blond", body="woman")
    assert pinned.hair == "lp.hair-blond" and cast.recipe(pinned)["person"]["body"] == "woman"
    for field in ("outfit", "skin", "shade", "eyes", "top", "bottom", "tilt", "brow"):
        assert getattr(free, field) == getattr(pinned, field), field
    suit = cast.person(5, key="t-suit", outfit="suit")
    assert suit.outfit == "suit" and suit.hair_style in lp.HAIR_TOPS and suit.tie in cast.TIES
    assert cast.person(5, key="t-hat", outfit="officer").hair_style is None      # a head under a hat has no hair on top
    try:
        cast.person(5, key="t-bad", hat="red")
    except KeyError as e:
        assert "hat" in str(e)
    else:
        raise AssertionError("a field a person does not have was accepted")


def test_a_drawn_person_is_in_the_cast_with_a_build_of_its_own():
    p = cast.person(9, key="t-own", outfit="officer")
    base = lp.BODIES[cast.recipe(p)["person"]["body"]]
    own = lp.BODIES[p.body]
    assert p.key in lp.PEOPLE and p.key in film.CAST and m.SPECS[p.key].build == base.build
    assert own is not base and own.trunk is base.trunk       # the build's own tables; only its measures are scaled
    for field, share in cast.BODY_VARY:
        assert abs(getattr(own, field) / getattr(base, field) - 1.0) <= share + 1e-6
    still = cast.person(9, key="t-still", outfit="officer", vary=0)
    assert still.body == cast.recipe(still)["person"]["body"]                 # vary=0: the build as it is
    f = film.Film("t-cast", size=(160, 160), fps=12)
    f.add(p.key, "idle")
    f.add("sergeant", "explain", at=(0.6, 0, 0))
    mine = [x for x in _parts(f) if x["figure"] == p.key]
    assert len(mine) > 60 and all(x["colour"] for x in mine)                  # its colours are materials of the film


def test_a_persons_facets_are_its_own_in_every_film():
    cast.person(11, key="t-facets", outfit="officer")
    f = film.Film("t-facets", size=(160, 160), fps=12)
    f.add("t-facets", "idle", name="extra-1")
    f.add("sergeant", "idle", at=(0.6, 0, 0), name="extra-2")
    f.add("sergeant", "idle", at=(1.2, 0, 0))
    keys = {}
    for part in _parts(f):
        if "facet" in part:
            keys.setdefault(part["figure"], set()).add(part.get("facet", {}).get("key", "").split("/")[0])
    assert keys["extra-1"] == {"t-facets"}                   # by who it is, whatever the actor is called
    assert keys["extra-2"] == keys["sergeant"] == {"sergeant"}


def test_a_person_is_saved_and_read_back(tmp_path):
    p = cast.person(21, key="t-keep", outfit="suit")
    path = cast.save(p, tmp_path / "keep.json")
    before = (asdict(p), lp.BODIES[p.body], lp.FACES.get(p.face))
    cast.dismiss(p)
    assert p.key not in lp.PEOPLE and p.key not in film.CAST and p.body not in lp.BODIES
    again = cast.load(path)
    assert (asdict(again), lp.BODIES[again.body], lp.FACES.get(again.face)) == before
    assert again.key in lp.PEOPLE and m.figure(again.key, "idle").parts()
    with pytest.raises(film.FilmError):
        film.dismiss("sergeant")                             # the cast's own people stay
    with pytest.raises(film.FilmError):
        film.enlist("nobody")


def test_the_uniform_of_one_on_somebody_else():
    other = cast.vary("sergeant", 3)
    sergeant = lp.PEOPLE["sergeant"]
    assert other.key == "sergeant-3" and (other.outfit, other.top, other.bottom, other.trim) == (
        sergeant.outfit, sergeant.top, sergeant.bottom, sergeant.trim)
    assert cast.vary("sergeant", 4).skin != other.skin or cast.vary("sergeant", 4).hair != other.hair
