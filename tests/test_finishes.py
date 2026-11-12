"""What another renderer needs: material kinds, the export, the finishes (characters.cloth, export, blender).

    SRLOCATIONS_PY -m pytest characters/tests -q              # everything (about 5 minutes)
    SRLOCATIONS_PY -m pytest characters/tests -q -m "not slow"   # the quick run
"""
import pytest

from characters import clip, film, motion, staging  # noqa: F401
from characters.poses import POSES  # noqa: F401

from helpers import ACTIONS, ALIGNMENT, drawn, one  # noqa: F401

def test_every_material_of_the_cast_has_a_kind():
    from characters import cloth, mascots3d as m
    kinds = set()
    for who in film.CAST:                                 # the plush family, its robots, the vinyl people
        for pose in ("idle", "yell", "dizzy", "sit"):
            for part in m.figure(who, pose).build():
                kinds.add(cloth.kind(part.material, part.name))        # raises for a material with no kind
    assert kinds <= set(cloth.KINDS) and {"fur", "felt", "stitch", "eye", "shine"} <= kinds
    assert cloth.kind("tiger.stripe", "tail/seg") == "fur" and cloth.kind("tiger.stripe", "stripe/line") == "stitch"
    assert cloth.pile("lion.mane") > cloth.pile("lion.fur")
    with pytest.raises(KeyError, match="has no kind"):
        cloth.kind("bear.sequins")


def test_export_gives_another_renderer_what_it_needs(tmp_path):
    import json
    from srlocations.nodes import Box
    f = film.Film("exported", size=(540, 960), fps=12)
    a = f.add("cat", at=(0.3, 0, 0))
    f.add("bear", at=(-0.3, 0, 0))
    f.prop(Box(size=(1.4, 0.1, 0.6), at=(0, -0.05, 0), material="plush.blush", name="floor"))
    f.camera((0, 0.8, 4), look_at=(0, 0.4, 0), lens=60)
    a.do(0.2, "wave").do(1.0, "wink")
    folder = f.export(tmp_path / "frames", seconds=2.0)
    meta = json.loads((folder / "export.json").read_text())
    assert meta["frames"] == 24 and meta["size"] == [540, 960] and meta["gate"] == "vertical"
    frames = [json.loads((folder / f"{k:04d}.json").read_text()) for k in range(24)]
    first = frames[0]
    ids = [p["id"] for p in first["parts"]]
    assert len(ids) == len(set(ids)) and "cat/head/head#1" in ids                 # one id a part
    assert {p["figure"] for p in first["parts"]} == {"cat", "bear"}
    assert all(len(p["verts"]) == 3 * p["nu"] * (p["nv"] + 1) for p in first["parts"])
    assert all(("pile" in p) == (p["kind"] == "fur") for p in first["parts"])
    assert not any("contact" in p["name"] for p in first["parts"])                 # a renderer with lights casts its own
    assert len(first["props"]) == 1 and len(first["props"][0]["verts"]) == 24
    assert first["camera"]["lens"] == 60 and 3.0 < first["camera"]["focus"] < 4.0  # on a face, not on the backdrop
    # a part keeps its id while it exists, so hairs grown on it stay put; the body's shape is the same grid throughout
    head = [next(p for p in fr["parts"] if p["id"] == "cat/head/head#1") for fr in frames]
    assert len({(p["nu"], p["nv"]) for p in head}) == 1
    assert head[0]["verts"] != head[8]["verts"]                                    # and it moves
    again = (folder / "0003.json").stat().st_mtime_ns
    f.export(tmp_path / "frames")
    assert (folder / "0003.json").stat().st_mtime_ns == again                      # frames already written are kept


def test_render_refuses_a_finish_it_does_not_have():
    f, actor = one("bear")
    with pytest.raises(film.FilmError, match="no finish"):
        f.render("x.mp4", seconds=1.0, finish="glass")
    with pytest.raises(film.FilmError, match="no quality"):
        f.render("x.mp4", finish="fur", quality="ultra")


def test_vinyl_finish_is_offered():
    from characters import blender
    assert {"fur", "terry", "vinyl"} <= set(blender.FINISHES)
    f, actor = one("officer")
    with pytest.raises(film.FilmError, match="no finish"):
        f.still("x.png", finish="glass")
