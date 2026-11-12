"""What each material of the cast is made of, for a renderer that draws cloth (characters/blender).

In the paper look a material is a name and a colour. A renderer with real fur has to know more: which parts are
furry cloth, which are felt sewn on, which are thread, which is the bead of an eye. `kind(material, part)` says it,
from the material's name (and, where one material does two jobs, the part that wears it). Every material the cast
uses has a kind: tests/test_plush.py refuses a new one that has none.
"""
from __future__ import annotations

KINDS = ("fur", "felt", "stitch", "eye", "shine", "metal", "plastic", "glow", "gloss", "contact", "vinyl", "satin")

# by the whole name, first
EXACT = {
    "plush.eye": "eye", "m.white": "shine", "m.ink": "stitch", "plush.stitch": "stitch", "m.sweat": "gloss",
    "m.mouth": "felt", "m.tongue": "felt", "plush.blush": "felt", "plush.pad": "felt",
    "plush.contact": "contact", "plush.contact-soft": "contact", "robot.metal": "metal", "robot.screen": "plastic",
    "robot.dark": "plastic",
    # vinyl people (characters.vinyl3d): moulded vinyl, glossy black shoes and leather, metal badges
    "vinyl.shoe": "plastic", "officer.black": "plastic", "officer.gold": "metal", "officer.buckle": "metal",
    "lp.gold": "metal", "lp.steel": "metal", "lp.iris": "eye", "lp.white": "shine",
    "lp.patent": "satin",      # a cap's peak: matte with a soft light on it (the low-poly finish; vinyl in the others)
}
# then by how the name starts: a whole family in one material
PREFIX = {"vinyl.": "vinyl", "officer.": "vinyl", "lp.": "vinyl"}      # lp.: low-poly people (characters.lowpoly3d)
# then by the last word of the name
SUFFIX = {
    # furry cloth: the body's, and the patches sewn on in other colours
    "fur": "fur", "light": "fur", "limb": "fur", "belly": "fur", "head": "fur", "mane": "fur", "ring": "fur",
    "tip": "fur", "black": "fur", "patch": "fur", "white": "fur", "stripe": "fur",
    # flat felt and stuffed cloth with no pile
    "inner": "felt", "nose": "felt", "nostril": "felt", "snout": "felt", "collar": "felt", "bow": "felt",
    "petal": "felt", "heart": "felt", "bloom": "felt", "stem": "felt", "gill": "felt", "horn": "felt",
    "wing": "felt", "beak": "felt", "bill": "felt", "shell": "felt", "band": "felt", "bean": "felt",
    "crease": "stitch", "steam": "felt",
    "bell": "metal",
    # the robots
    "accent": "plastic", "blue": "plastic", "green": "plastic", "red": "plastic", "yellow": "plastic",
    "ray": "plastic", "led": "glow",
}
STROKES = ("stripe", "whisker", "brow", "mouth", "eye", "stitch")   # parts drawn as thread, whatever their colour

PILE = 0.0075                              # m: how long the fur's pile is
PILES = {"mane": 0.014}                    # by the last word of the material's name


def kind(material: str, part: str = "") -> str:
    """What `material` is on a part named `part` ("stripe/line", "tail/seg", ...): one of KINDS."""
    if material in EXACT:
        return EXACT[material]
    for start, found in PREFIX.items():
        if material.startswith(start):
            return found
    found = SUFFIX.get(material.rsplit(".", 1)[-1])
    if found is None:
        raise KeyError(f"material {material!r} has no kind: add it to characters/cloth.py (EXACT or SUFFIX)")
    if found == "fur" and part.split("/", 1)[0] in STROKES:
        return "stitch"                    # the same colour, as a line of thread (a forehead stripe)
    return found


def pile(material: str) -> float:
    """The length of the pile on a furry material, in metres."""
    return PILES.get(material.rsplit(".", 1)[-1], PILE)
