"""Low-poly people from a seed: `person(42)` is always the same new person, `person(43)` another.

The kit (characters.lowpoly3d) makes a person of named choices: a build, an outfit, a face, a hair style, colours,
and a few measures. This module draws those choices from a seed, so a crowd, an extra or a new recurring character
is one call, and what is drawn is only what the kit already has: nothing is modelled here.

    from characters import lowpoly_cast as cast
    p = cast.person(42)                           # everything drawn from the seed
    p = cast.person(42, outfit="suit")            # pinned: any field of lowpoly3d.Person; the rest is drawn
    p = cast.person("ana", body="woman", outfit="officer", top="lp.navy")
    film.add(p.key, "idle")                       # it is in the cast: poses, actions, speech, finish="lowpoly"
    people = cast.cast(7, 5, outfit="suit")       # five different people from one seed
    cast.vary("sergeant", 3)                      # the sergeant's uniform on somebody else
    cast.dismiss(p)                               # out of the cast again (an extra of one film)

What a seed decides, each from its own draw (pinning one changes none of the others):
  build (BODIES) and, within it, how thick the arms and legs are and how large the hands and feet (`vary`: 1 is up
  to about 7% either way, 0 leaves the build as it is); outfit (OUTFITS) and its colours (WARDROBE); skin, hair,
  eyes; hair style and grey temples, when the outfit leaves the head bare; face (FACES) and, within it, the size of
  the eyes and the ears, how far apart the eyes are and how wide the mouth; how heavy the brows are; the head's tilt.
The surface is the person's own as well: the finish breaks cloth into facets by the person's key, so two people in
the same uniform do not crease alike, and the same person creases the same in every film.

A seed is a recipe for today's kit: when the kit gains a build or a face, the same seed may draw it. To keep a
character for good, save what was drawn and read it back:

    cast.save(p, "anchor-2.json")                 # every choice, by name and number
    p = cast.load("anchor-2.json")                # the same person, whatever the kit has gained since

    PY=/home/dev/src/viral-video-orchestrator/.venvs/srlocations/bin/python
    $PY characters/lowpoly_cast.py sheet 7 6 out.png [outfit=suit body=woman ...]   # six people of seed 7, in a row
"""

from __future__ import annotations

import json
import random
import sys
import zlib
from dataclasses import asdict, fields, replace
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "characters"

from . import lowpoly3d as lp  # noqa: E402
from . import mascots3d as m  # noqa: E402

# colours a drawn person may have beyond the built-in cast's: skins with their shade (the hollow of an ear, a fold),
# hair, eyes, and the cloth of other uniforms and suits
COLOURS = {
    "lp.skin-fair": "#F4B98E", "lp.skin-fair-shade": "#D6976A", "lp.skin-olive": "#D9995F", "lp.skin-olive-shade": "#B67A46",
    "lp.skin-deep": "#8E5430", "lp.skin-deep-shade": "#6F3E22", "lp.skin-dark": "#693C22", "lp.skin-dark-shade": "#4F2B18",
    "lp.hair-brown": "#5B3A27", "lp.hair-auburn": "#7C3B21", "lp.hair-blond": "#C79A56", "lp.hair-white": "#D9D3CD",
    "lp.eye-hazel": "#6C4B22", "lp.eye-green": "#4E6A3B", "lp.eye-blue": "#3E5E86", "lp.eye-grey": "#5E656F",
    "lp.khaki": "#B7A174", "lp.khaki-dark": "#8B7850", "lp.olive": "#55693F", "lp.olive-dark": "#42522F",
    "lp.slate": "#6A7280", "lp.slate-dark": "#4B525E", "lp.sky": "#8DAED4", "lp.sky-dark": "#6C8DB4",
    "lp.charcoal": "#3B3D45", "lp.charcoal-dark": "#2C2E34", "lp.brown": "#5C4435", "lp.brown-dark": "#463327",
    "lp.grey": "#7B7F87", "lp.grey-dark": "#61656D", "lp.ink": "#27272C", "lp.ink-dark": "#1C1C20",
    "lp.blue": "#2D5DA8", "lp.green": "#2F7A55", "lp.wine": "#7A2233", "lp.mustard": "#D9A32B",
    "lp.tan": "#B8935A", "lp.tan-dark": "#8E6F40", "lp.amber": "#F2C230",
}
lp.COLOURS.update(COLOURS)
m.COLOURS.update(COLOURS)

SKINS = (("lp.skin", "lp.skin-shade"), ("lp.skin-fair", "lp.skin-fair-shade"), ("lp.skin-olive", "lp.skin-olive-shade"),
         ("lp.skin-tan", "lp.skin-tan-shade"), ("lp.skin-brown", "lp.skin-brown-shade"), ("lp.skin-deep", "lp.skin-deep-shade"),
         ("lp.skin-dark", "lp.skin-dark-shade"))
HAIRS = ("lp.hair", "lp.hair-black", "lp.hair-dark", "lp.hair-brown", "lp.hair-auburn", "lp.hair-blond", "lp.hair-grey",
         "lp.hair-white")
GREYS = ("lp.hair-grey", "lp.hair-white")          # hair that does not go grey at the temples: it is grey
EYES = ("lp.eye", "lp.eye-dark", "lp.eye-hazel", "lp.eye-green", "lp.eye-blue", "lp.eye-grey")
# What an outfit comes in, beyond the colours of the first person of the cast who wears it (which are always one
# of the choices): fields of lowpoly3d.Person. An outfit that is not listed keeps that person's colours.
WARDROBE = {
    "officer": (dict(top="lp.khaki", bottom="lp.khaki-dark", trim="lp.khaki-dark"),
                dict(top="lp.olive", bottom="lp.olive", trim="lp.olive-dark"),
                dict(top="lp.slate", bottom="lp.slate", trim="lp.slate-dark"),
                dict(top="lp.sky", bottom="lp.navy", trim="lp.sky-dark")),
    "cook": (dict(dark="lp.blue"), dict(dark="lp.green"), dict(top="lp.ink", buttons="lp.jacket", dark="lp.mustard")),
    "firefighter": (dict(top="lp.tan", bottom="lp.tan", trim="lp.lime"), dict(top="lp.ink", bottom="lp.ink", trim="lp.amber")),
    "suit": (dict(top="lp.charcoal", bottom="lp.charcoal", trim="lp.charcoal-dark", buttons="lp.charcoal-dark"),
             dict(top="lp.brown", bottom="lp.brown", trim="lp.brown-dark", buttons="lp.brown-dark"),
             dict(top="lp.grey", bottom="lp.grey", trim="lp.grey-dark", buttons="lp.grey-dark"),
             dict(top="lp.ink", bottom="lp.ink", trim="lp.ink-dark", buttons="lp.ink-dark")),
}
TIES = ("lp.orange", "lp.red", "lp.blue", "lp.green", "lp.wine", "lp.mustard")
SHOES = (("lp.shoe-brown", "lp.sole-brown"), ("lp.black", "lp.sole"))        # what a suit is worn with
TIED = ("suit",)                    # the outfits worn with a tie and dress shoes
# which faces a build may draw (None is the kit's first face on the build's own skull); a build that is not listed
# may draw any
FACES_FOR = {"woman": (None,)}
# how far a measure may leave the build's or the face's, at vary=1: (field, share either way)
BODY_VARY = (("arm", 0.07), ("leg", 0.05), ("hand", 0.06), ("foot", 0.05))
FACE_VARY = (("eye", 0.07), ("eye_x", 0.035), ("mouth_x", 0.08), ("ear", 0.08))

RECIPES: dict[str, dict] = {}       # key -> what was drawn for it (save / load)


def _rng(seed, what: str) -> random.Random:
    """The draw of one choice: its own, so that pinning or adding another choice does not change this one."""
    return random.Random(zlib.crc32(f"{seed}|{what}".encode()))


def _pick(seed, what: str, choices):
    choices = list(choices)
    return choices[_rng(seed, what).randrange(len(choices))]


def _near(seed, what: str, share: float) -> float:
    return round(1.0 + share * _rng(seed, what).uniform(-1.0, 1.0), 3)


def _template(outfit: str) -> lp.Person:
    """The first person of the built-in cast who wears `outfit`: what the outfit needs that is not a colour (how
    long its sleeves are, whether the head is bare) is read off them."""
    for p in lp.PEOPLE.values():
        if p.outfit == outfit and p.key not in RECIPES:
            return p
    return lp.Person(outfit, outfit.title(), outfit=outfit)


def _scaled(value, k: float):
    return tuple(round(x * k, 5) for x in value) if isinstance(value, tuple) else round(value * k, 5)


def _build(recipe: dict) -> lp.Person:
    """The person a recipe describes, in the cast: its own build and face (the base's, a little larger or smaller
    here and there) under its own key, then the person."""
    key, chosen = recipe["key"], dict(recipe["person"])
    body = recipe.get("body") or {}
    if any(v != 1.0 for v in body.values()):
        base = lp.BODIES[chosen["body"]]
        chosen["body"] = f"{chosen['body']}~{key}"
        lp.BODIES[chosen["body"]] = replace(base, **{f: _scaled(getattr(base, f), k) for f, k in body.items() if hasattr(base, f)})
    face = recipe.get("face") or {}
    if any(v != 1.0 for v in face.values()) and hasattr(lp, "FACES"):
        base = lp.FACES[chosen["face"]] if chosen.get("face") else lp.FACE
        chosen["face"] = f"{chosen.get('face') or 'first'}~{key}"
        lp.FACES[chosen["face"]] = replace(base, **{f: _scaled(getattr(base, f), k) for f, k in face.items() if hasattr(base, f)})
    known = {f.name for f in fields(lp.Person)}
    person = lp.Person(**{k: v for k, v in chosen.items() if k in known})
    RECIPES[key] = recipe
    return _enlist(person)


def _enlist(person: lp.Person) -> lp.Person:
    lp.enlist(person)
    from . import film              # (film imports the families: not at the top of this module)
    film.enlist(person.key)
    return person


def dismiss(who) -> None:
    """Takes a person of this module out of the cast again (a key or the Person), with its own build and face."""
    key = getattr(who, "key", who)
    RECIPES.pop(key)
    gone = lp.PEOPLE.pop(key)
    for table in (m.SPECS, m.NAMES, m.LOOKS, m.WHOLE, lp.POSES):
        table.pop(key, None)
    if gone.body.endswith(f"~{key}"):
        lp.BODIES.pop(gone.body, None)
    if getattr(gone, "face", None) and gone.face.endswith(f"~{key}"):
        lp.FACES.pop(gone.face, None)
    from . import film
    film.dismiss(key)


def person(seed, key: str | None = None, name: str | None = None, vary: float = 1.0, **fixed) -> lp.Person:
    """A person drawn from `seed` (a number or a word) and put in the cast under `key` (default "p-<seed>"): the
    same seed, the same person. `fixed` pins fields of lowpoly3d.Person (outfit="suit", body="woman",
    hair="lp.hair-blond", ...); what is not pinned is drawn. `vary` is how far its measures may leave its build's
    and its face's (1: a few per cent; 0: not at all)."""
    known = {f.name for f in fields(lp.Person)}
    unknown = set(fixed) - known
    if unknown:
        raise KeyError(f"a person has no {', '.join(sorted(unknown))}; it has {', '.join(sorted(known))}")
    key = key or f"p-{seed}"
    outfit = fixed.get("outfit") or _pick(seed, "outfit", sorted(lp.OUTFITS))
    if outfit not in lp.OUTFITS:
        raise KeyError(f"no outfit {outfit!r}; there is {', '.join(sorted(lp.OUTFITS))}")
    like = _template(outfit)
    chosen = {**asdict(like), "key": key, "name": name or key, "outfit": outfit}
    chosen["body"] = _pick(seed, "body", sorted(b for b in lp.BODIES if "~" not in b))
    chosen.update(_pick(seed, "wardrobe", ({}, *WARDROBE.get(outfit, ()))))
    chosen["skin"], chosen["shade"] = _pick(seed, "skin", SKINS)
    chosen["hair"] = _pick(seed, "hair", HAIRS)
    chosen["eyes"] = _pick(seed, "eyes", EYES)
    chosen["tilt"] = _pick(seed, "tilt", (-1.5, -1.0, 1.0, 1.5))
    chosen["brow"] = round(_rng(seed, "brow").uniform(0.85, 1.2), 2)
    if outfit in TIED:                # a tie of its own colour, and dress shoes
        chosen["tie"] = _pick(seed, "tie", TIES)
        chosen["shoes"], chosen["sole"] = _pick(seed, "shoes", SHOES)
    if like.hair_style:               # a bare head: a style of its own, and one in four is grey at the temples
        chosen["hair_style"] = _pick(seed, "hair-style", sorted(lp.HAIR_TOPS))
        chosen["temples"] = "lp.hair-grey" if _rng(seed, "temples").random() < 0.25 else None
    chosen.update(fixed)
    if chosen.get("temples") and chosen["hair"] in GREYS:
        chosen["temples"] = None
    if "face" in known and "face" not in fixed:
        faces = FACES_FOR.get(chosen["body"], (None, *sorted(f for f in getattr(lp, "FACES", {}) if "~" not in f)))
        chosen["face"] = _pick(seed, "face", faces)
    vary = max(0.0, float(vary))
    recipe = {"key": key, "seed": seed, "person": chosen,
              "body": {f: _near(seed, f"body.{f}", share * vary) for f, share in BODY_VARY},
              "face": {f: _near(seed, f"face.{f}", share * vary) for f, share in FACE_VARY}}
    return _build(recipe)


def cast(seed, count: int, **fixed) -> list[lp.Person]:
    """`count` different people from one seed (person "<seed>/0", "<seed>/1", ...), with the same fields pinned."""
    return [person(f"{seed}/{i}", key=f"p-{seed}-{i}", **fixed) for i in range(count)]


def vary(who: str, seed, key: str | None = None, **fixed) -> lp.Person:
    """Somebody else in what `who` wears: the outfit and its colours are `who`'s, the person is drawn from `seed`."""
    like = lp.PEOPLE[who]
    cloth = {f: getattr(like, f) for f in ("outfit", "top", "bottom", "trim", "dark", "shoes", "sole", "shiny", "metal",
                                           "buttons", "shirt", "tie", "sleeve", "shoe") if hasattr(like, f)}
    return person(seed, key=key or f"{who}-{seed}", **{**cloth, **fixed})


def recipe(who) -> dict:
    """What was drawn for a person of this module (a key or the Person): every choice, by name and number."""
    return RECIPES[getattr(who, "key", who)]


def save(who, path) -> Path:
    path = Path(path)
    path.write_text(json.dumps(recipe(who), indent=1, sort_keys=True) + "\n")
    return path


def load(path) -> lp.Person:
    """The person saved there, in the cast again: the same choices, whatever the kit has gained since."""
    return _build(json.loads(Path(path).read_text()))


def sheet(people, out, pose: str = "idle", yaw: float = -12.0) -> Path:
    """The people side by side, in the low-poly finish (a picture `out`)."""
    from . import film
    people = [p if isinstance(p, str) else p.key for p in people]
    n = max(3, len(people))
    f = film.Film("lowpoly-cast", size=(300 * n, 620))
    for i, who in enumerate(people):
        f.add(who, pose, at=(((len(people) - 1) / 2 - i) * 0.5, 0, 0), yaw=yaw)      # the first on the picture's left
    f.camera((0.0, 0.6, 9.0), look_at=(0, 0.57, 0), lens=62 * 8 / n * 1.08)      # room for a tall hat on a tall build
    return f.still(out, finish="lowpoly", quality="standard")


if __name__ == "__main__":
    if sys.argv[1:2] == ["sheet"] and len(sys.argv) >= 3:
        args = [a for a in sys.argv[2:] if "=" not in a]
        pinned = dict(a.split("=", 1) for a in sys.argv[2:] if "=" in a)
        seed, count = args[0], int(args[1]) if len(args) > 1 else 6
        out = Path(args[2]) if len(args) > 2 else Path(__file__).resolve().parent / "examples" / "out" / f"lowpoly-cast-{seed}.png"
        made = cast(seed, count, **pinned)
        for p in made:
            r = recipe(p)["person"]
            print(p.key, r["body"], r["outfit"], r["skin"], r["hair"], r.get("face"), r.get("hair_style"))
        print("wrote", sheet(made, out))
    else:
        print(__doc__)
