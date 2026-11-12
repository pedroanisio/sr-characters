"""The low-poly people (characters.lowpoly3d).

    SRLOCATIONS_PY -m pytest characters/tests/test_lowpoly.py -q
"""
import math

from characters import film
from characters.poses import POSES


def test_lowpoly_people_share_one_kit_and_pose():
    from characters import cloth, lowpoly3d as lp, mascots3d as m
    assert {"sergeant", "cook", "firefighter", "captain", "anchor"} <= set(lp.PEOPLE) <= set(film.PEOPLE)
    assert {lp.PEOPLE[k].body for k in lp.PEOPLE} == {"man", "woman"}          # two builds
    assert lp.PEOPLE["sergeant"].outfit == lp.PEOPLE["captain"].outfit          # one outfit on both
    for who in lp.PEOPLE:
        for pose in POSES[who]:
            parts = m.figure(who, pose).build()
            assert len(parts) > 40
            for part in parts:
                if not isinstance(part, m.Contact):
                    assert cloth.kind(part.material, part.name) in cloth.KINDS
        names = {p.name for p in m.figure(who, "idle").build()}
        assert {"body/body", "hips/hips", "head/head", "hair/hair", "nose/nose", "leg_l/thigh", "leg_r/shin"} <= names
    assert {"cap/crown", "badge/badge", "belt/belt", "radio/radio"} <= {p.name for p in m.figure("captain", "idle").build()}


def test_a_loft_says_where_its_facets_are():
    """What is placed on a loft lies on its facets: the helpers agree with the corners it draws."""
    from characters import lowpoly3d as lp
    for body in lp.BODIES.values():
        for loft in (body.trunk, body.pelvis, body.skull, body.belt):
            for y in (loft.s[0][0], (loft.s[0][0] + loft.s[-1][0]) / 2, loft.s[-1][0]):
                ring = loft.ring(y)
                rx, rz, zc, flat = loft.at(y)
                assert len(ring) == loft.sides and max(x for x, _ in ring) == rx and max(z for _, z in ring) == zc + rz
                assert abs(loft.front(0.0, y) - (zc + rz)) < 1e-9               # the flat front
                assert abs(loft.front(rx, y) - max(z for x, z in ring if x == rx)) < 1e-9     # where the front ends
                if not any(loft.o):                                             # an octagon: the end of its chamfer
                    assert loft.sides == 8 and abs(loft.front(rx, y) - (zc + flat * rz)) < 1e-9
                assert abs(loft.side(zc, y) - rx) < 1e-9                        # and its side
                assert abs(loft.back(0.0, y) - min(z for _, z in ring)) < 1e-9 and loft.back(0.0, y, 0.01) < loft.back(0.0, y)
                for deg in (0, 40, 75, 180, -40):                               # a thing hung on it touches a facet
                    (x, _y, z), yaw = loft.around(deg, y)
                    assert abs(math.atan2(x, z - zc) - math.radians(deg)) < 1e-6 or abs(abs(deg) - 180) < 1e-6
                    assert any(_on(x, z, a, b) for a, b in zip(ring, ring[1:] + ring[:1])), (deg, y)
        band = body.trunk.band(0.6, 0.63, 0.005)
        assert all(b[1] > body.trunk.at(b[0])[0] and b[2] > body.trunk.at(b[0])[1] for b in band.s)   # a band is outside
    limb = lp.TRUNK.limb("body/body", _Still(), "lp.navy", None)
    assert limb.role.split()[0] == "drawn" and limb.samples == (8, len(lp.TRUNK.s) + 1)
    assert {body.skull.sides for body in lp.BODIES.values()} == {10}             # a face has its own planes


def _grid(limb):
    """The corners a drawn limb is sampled at, row by row, as the exporter does."""
    from characters import export
    fx, fy, fz = (export._code(e) for e in (limb.x, limb.y, limb.z))
    nu, nv = limb.samples
    at = lambda i, j: {**export._ENV, "u": limb.u[0] + (limb.u[1] - limb.u[0]) * i / nu,       # noqa: E731
                       "v": limb.v[0] + (limb.v[1] - limb.v[0]) * j / nv}
    return [[(eval(fx, at(i, j)), eval(fy, at(i, j)), eval(fz, at(i, j))) for i in range(nu)] for j in range(nv + 1)]


def test_a_loft_takes_another_outline_than_the_octagon():
    """`profile` and a section's own corners give a loft fewer or more sides; what it draws, where things lie on
    it and what the finish is told of its sides all follow; `stagger` makes its rings zigzag."""
    from characters import lowpoly3d as lp
    sections = [(0.0, 0.05, 0.06, 0.0), (0.1, 0.06, 0.07, 0.01), (0.2, 0.05, 0.05, -0.01), (0.3, 0.04, 0.05, 0.0)]
    same = lambda a, b: all(abs(p[k] - q[k]) < 1e-6 for ra, rb in zip(a, b) for p, q in zip(ra, rb) for k in range(3))  # noqa: E731
    # the octagon given as a profile is the octagon
    assert same(_grid(lp.Loft(sections, 0.5).limb("a", _Still(), "lp.navy", None)),
                _grid(lp.Loft(sections, 0.5, profile=lp.Loft.octagon(0.5)).limb("a", _Still(), "lp.navy", None)))
    hexagon = lp.Loft(sections, 0.5, lp.CREASE, 80.0, profile=lp.HEX, stagger=0.01)
    limb = hexagon.limb("leg", _Still(), "lp.navy", None)
    assert hexagon.sides == 6 and limb.samples == (6, len(sections) + 1) and limb.u == (0, 6)
    tag = next(t for t in limb.role.split() if t.startswith("facet:")).split(":")
    assert len(tag[3].split(",")) == 6 and len(tag[4].split(",")) == len(sections) + 1       # six sides, the bands and two ends
    grid, mid = _grid(limb), sum(sections[i][0] for i in (0, -1)) / 2
    for j, section in enumerate(sections):
        ring, row = hexagon.ring(section[0]), grid[j + 1]
        assert all(abs(p[0] - x) < 1e-6 and abs(p[2] - z) < 1e-6 for p, (x, z) in zip(row, ring))   # its corners are its ring
        lifts = [round(p[1] + mid - section[0], 6) for p in row]
        assert lifts == ([0.0] * 6 if j in (0, len(sections) - 1) else [lifts[0], -lifts[0]] * 3) and abs(lifts[0]) in (0.0, 0.01)
    lift = lambda j: grid[j + 1][0][1] + mid - sections[j][0]            # noqa: E731
    assert abs(lift(1) + lift(2)) < 1e-6                                 # the next ring zigzags the other way
    y = 0.1
    ring = hexagon.ring(y)
    rx, rz, zc, _flat = hexagon.at(y)
    assert abs(hexagon.front(0.0, y) - (zc + rz)) < 1e-9 and abs(hexagon.side(zc, y) - rx) < 1e-9
    for deg in (0, 40, 90, 180, -40):
        (x, _y, z), _yaw = hexagon.around(deg, y)
        assert any(_on(x, z, a, b) for a, b in zip(ring, ring[1:] + ring[:1])), deg
    band = hexagon.band(0.05, 0.15, 0.004)
    assert band.sides == 6 and all(bx > x - 1e-9 for (bx, _), (x, _z) in zip(band.ring(y)[:1], ring[:1]))
    # a section with corners of its own: the outline changes along the part, each corner running straight
    cheeks = lp.Loft([(0.0, 0.05, 0.05, 0.0, lp.face_planes(0.5, 0.8, 0.8, 0.2)), (0.1, 0.05, 0.05, 0.0, lp.face_planes(0.1, 0.7, 0.9, 0.1))])
    assert cheeks.sides == 10 and abs(cheeks.shape(0.05)[2][0] - 0.3) < 1e-9
    assert abs(cheeks.front(0.05 * 0.75, 0.05) - 0.05 * 0.85) < 1e-9       # half way down the cheek's plane, half way up


def _on(x, z, a, b) -> bool:
    (ax, az), (bx, bz) = a, b
    cross = (bx - ax) * (z - az) - (bz - az) * (x - ax)
    inside = min(ax, bx) - 1e-9 <= x <= max(ax, bx) + 1e-9 and min(az, bz) - 1e-9 <= z <= max(az, bz) + 1e-9
    return abs(cross) < 1e-9 and inside


class _Still:
    """A carry that moves nothing."""

    def point(self, p):
        from srlocations.geometry import Vec3
        return Vec3(*p)

    def basis(self, b):
        return b


def test_the_export_keeps_a_drawn_part_as_it_is():
    from characters import export, lowpoly3d as lp
    f = film.Film("lowpoly-export", size=(160, 160), fps=12)
    f.add("sergeant", at=(0, 0, 0))
    f.camera((0, 0.6, 6), look_at=(0, 0.5, 0))
    f.perform(0.2)
    data = export.frame(f.loc.at(0.0), f._shot)
    drawn = [p for p in data["parts"] if p.get("drawn")]
    part = lambda name: next(p for p in drawn if p["name"] == name)      # noqa: E731
    body = part("body/body")
    assert body["nu"] == lp.TRUNK.sides == 8 and body["nv"] == len(lp.TRUNK.s) + 1
    # a part with another outline keeps its own number of sides, and tells the finish how wide each is
    assert part("leg_l/thigh")["nu"] == len(lp.HEX) == len(part("leg_l/thigh")["facet"]["sides"])
    assert part("head/head")["nu"] == lp.SKULL.sides
    assert all(p["nu"] in (6, 8, 10) for p in drawn)


def _corners(limb):
    """A drawn limb's corners where the figure has them, row by row."""
    r, at = limb.basis, limb.at
    return [[(at.x + r[0][0] * x + r[0][1] * y + r[0][2] * z, at.y + r[1][0] * x + r[1][1] * y + r[1][2] * z,
              at.z + r[2][0] * x + r[2][1] * y + r[2][2] * z) for x, y, z in row] for row in _grid(limb)]


def _along(limb):
    return tuple(limb.basis[i][1] for i in range(3))


HAND = ("hand", "thumb", "thumb-tip", *(f"{f}{tip}" for f in ("index", "middle", "ring", "little") for tip in ("", "-tip")))


def test_hands_and_boots_are_drawn_parts_on_every_build():
    """A hand is a palm, four fingers of two bones and a thumb; a boot a sole and an upper. They keep their corners,
    close at both ends, mirror from one side to the other, and are sized by the build."""
    from characters import lowpoly3d as lp, mascots3d as m
    built = {who: {p.name: p for p in m.figure(who, "idle").build() if not isinstance(p, m.Contact)} for who in lp.PEOPLE}
    for who, parts in built.items():
        person = lp.PEOPLE[who]
        for side in "lr":
            names = [f"arm_{side}/{n}" for n in HAND] + [f"shoe_{side}/sole", f"shoe_{side}/upper"]
            for name in names:
                limb = parts[name]
                assert limb.role.split() == ["drawn"], name
                rows = _corners(limb)
                assert len(rows) == limb.samples[1] + 1 >= 4
                for end in (rows[0], rows[-1]):                 # an end closes on a point (to 0.1 mm): nothing is left open
                    assert max(math.dist(p, end[0]) for p in end) < 1e-4, name
                assert max(math.dist(p, rows[1][0]) for p in rows[1]) > 0.01, name
            assert {parts[n].material for n in names[:len(HAND)]} == {person.skin}
            assert parts[f"shoe_{side}/sole"].material == person.sole and parts[f"shoe_{side}/upper"].material == person.shoes
            # standing, a boot lies flat on the ground and points forward: its toes are further from the ankle than its heel
            sole = [p for row in _corners(parts[f"shoe_{side}/sole"]) for p in row]
            upper = [p for row in _corners(parts[f"shoe_{side}/upper"]) for p in row]
            assert abs(min(p[1] for p in sole)) < 1e-5 and min(p[1] for p in upper) > 0.01
            high = 0.8 * max(p[1] for p in upper)                # (a boot's shaft is over 0.06; a dress shoe is lower)
            mid = sum(p[2] for p in upper if p[1] > high) / len([p for p in upper if p[1] > high])       # the shaft
            assert max(p[2] for p in sole) - mid > 2 * (mid - min(p[2] for p in sole)) > 0.05
        # the two sides mirror
        for n in (*HAND,):
            left = sorted((round(-x, 4), round(y, 4), round(z, 4)) for row in _corners(parts[f"arm_l/{n}"]) for x, y, z in row)
            right = sorted((round(x, 4), round(y, 4), round(z, 4)) for row in _corners(parts[f"arm_r/{n}"]) for x, y, z in row)
            assert all(math.dist(a, b) < 3e-4 for a, b in zip(left, right)), (who, n)
    # a person's own shoes: the soles take its colour, and a dress shoe is the boot, lower
    assert {lp.PEOPLE[who].sole for who in ("sergeant", "cook", "firefighter", "captain")} == {"lp.sole"} != {lp.PEOPLE["anchor"].sole}
    tall = lambda who, name: max(p[1] for row in _corners(built[who][name]) for p in row)        # noqa: E731
    for name in ("shoe_l/sole", "shoe_l/upper"):
        assert abs(tall("anchor", name) - lp.PEOPLE["anchor"].shoe * tall("sergeant", name)) < 1e-4 and lp.PEOPLE["anchor"].shoe < 1.0
    # sized by the build: the woman's hands and boots are the man's, smaller
    man, woman = built["sergeant"], built["captain"]
    assert lp.BODIES["woman"].hand < 1.0 > lp.BODIES["woman"].foot
    for name, k in (("arm_l/hand", lp.BODIES["woman"].hand), ("arm_r/middle-tip", lp.BODIES["woman"].hand),
                    ("shoe_l/sole", lp.BODIES["woman"].foot), ("shoe_r/upper", lp.BODIES["woman"].foot)):
        assert all(abs(a * k - b) < 1e-4 for a, b in zip(man[name].radii, woman[name].radii)), name


def test_a_hand_hangs_from_the_wrist_and_its_fingers_follow_it():
    """At rest the hand hangs nearer upright than the forearm that carries it, with the pose's turn of the wrist
    still on top; in every pose the fingers and the thumb run on from the hand, never back along it."""
    from characters import lowpoly3d as lp, mascots3d as m
    lean = lambda v: math.degrees(math.atan2(abs(v[0]), -v[1]))      # noqa: E731
    for who in ("sergeant", "captain"):
        fig = m.figure(who, "idle")
        parts = {p.name: p for p in fig.build() if not isinstance(p, m.Contact)}
        for side in "lr":
            assert lean(_along(parts[f"arm_{side}/fore"])) > 15.0
            assert lean(_along(parts[f"arm_{side}/hand"])) < lp.HAND_LEAN + 0.5
        fig.wrist_left = fig.wrist_right = 20.0
        turned = {p.name: p for p in fig.build() if not isinstance(p, m.Contact)}
        for side in "lr":                # the wrist turns about the figure's front-to-back axis: seen from the front
            a, b = _along(parts[f"arm_{side}/hand"]), _along(turned[f"arm_{side}/hand"])
            seen = lambda v: math.degrees(math.atan2(v[0], -v[1]))      # noqa: E731
            assert abs(abs(seen(a) - seen(b)) - 20.0) < 0.01 and abs(a[2] - b[2]) < 1e-9
        for pose in POSES[who]:
            parts = {p.name: p for p in m.figure(who, pose).build() if not isinstance(p, m.Contact)}
            for side in "lr":
                hand = _along(parts[f"arm_{side}/hand"])
                for n in HAND[1:]:
                    assert sum(x * y for x, y in zip(hand, _along(parts[f"arm_{side}/{n}"]))) > 0.0, (who, pose, side, n)


SUIT = {"jacket/skirt", "jacket/waist", "jacket/lapel", "jacket/collar", "jacket/button", "jacket/flap", "jacket/seam",
        "jacket/edge", "shirt/front", "collar/band", "collar/wing", "tie/knot", "tie/blade", "cuff_l/cuff", "cuff_r/cuff",
        "sleeve_l/button", "sleeve_r/button", "leg_l/turn-up", "leg_r/turn-up"}


def test_a_suit_is_parts_that_dress_every_build_and_bare_headed_hair_has_a_top():
    """The anchor: the man's build in a suit, bare-headed. The suit's parts are there, each in the person's colour
    for it; the hair covers the top of the head, in two colours; those who wear a hat are as they were; and the
    same suit dresses the other build, with nothing written again."""
    from dataclasses import replace
    from characters import lowpoly3d as lp, mascots3d as m
    anchor = lp.PEOPLE["anchor"]
    parts = {p.name: p for p in m.figure("anchor", "idle").build() if not isinstance(p, m.Contact)}
    assert SUIT <= set(parts) and lp.OUTFITS[anchor.outfit] is lp._suit and anchor.body == "man"
    wears = lambda *names: {parts[n].material for n in names}        # noqa: E731
    assert wears("jacket/skirt", "jacket/waist", "jacket/lapel", "jacket/collar", "jacket/flap", "body/body", "sleeve_l/fore") == {anchor.top}
    assert wears("shirt/front", "collar/band", "collar/wing", "cuff_l/cuff", "cuff_r/cuff") == {anchor.shirt}
    assert wears("tie/knot", "tie/blade") == {anchor.tie} and wears("leg_l/turn-up", "leg_l/shin") == {anchor.bottom}
    # the skirt hangs over the hips to under where the legs part, and the jacket runs on from it to the chest
    low = lambda name: min(p[1] for row in _corners(parts[name]) for p in row)       # noqa: E731
    top = lambda name: max(p[1] for row in _corners(parts[name]) for p in row)       # noqa: E731
    assert low("jacket/skirt") < low("hips/hips") and top("jacket/skirt") > low("jacket/waist") and top("jacket/waist") > 0.6
    # a cuff shows past the end of its sleeve, and is slimmer than it
    assert top("cuff_l/cuff") > low("sleeve_l/fore") > low("cuff_l/cuff")
    # the jacket's collar goes round the back of the neck, outside the shirt's, which shows over it; it is open in front
    front = lambda name: max(p[2] for row in _corners(parts[name]) for p in row)     # noqa: E731
    back = lambda name: min(p[2] for row in _corners(parts[name]) for p in row)      # noqa: E731
    assert back("jacket/collar") < back("collar/band") and front("jacket/collar") < front("collar/band")
    assert top("collar/band") > top("jacket/collar")
    # bare-headed: hair over the crown in the hair's colour, the back and the sides in the temples'
    assert wears("hair/top") == {anchor.hair} and wears("hair/hair") == {anchor.temples} and anchor.temples != anchor.hair
    assert top("hair/top") > top("head/head") + 0.01 and set(lp.HAIR_TOPS) >= {anchor.hair_style}
    for who in ("sergeant", "cook", "firefighter", "captain"):        # under a hat: the build's hair, in one colour
        person = lp.PEOPLE[who]
        worn = {p.name: p for p in m.figure(who, "idle").build() if not isinstance(p, m.Contact)}
        assert person.hair_style is None and person.temples is None and "hair/top" not in worn
        # (a collar's band and wings are the officer's too, and the cook's jacket has buttons)
        assert not (SUIT - {"collar/band", "collar/wing", "jacket/button"}) & set(worn)
        assert worn["hair/hair"].material == person.hair and person.brow == 1.0 == person.shoe
    # the same suit and the same hair on the woman's build (she is not in the cast: a Person is all it takes)
    fig = m.figure("captain", "idle")
    k = lp.Parts(fig, fig.frames(), replace(anchor, body="woman"))
    lp._body(k)
    lp.OUTFITS["suit"](k)
    hers = {p.name: p for p in k.made}
    assert SUIT | {"hair/top"} <= set(hers) and hers["jacket/skirt"].radii[0] != parts["jacket/skirt"].radii[0]


def test_a_panel_lies_on_the_part_it_is_laid_on():
    """A lapel, a shirt's front, a tie's blade, a seam: at every corner that shows it is proud of the part by what
    was asked, on the front or the back; it has a row at each of the part's sections and bends at its corner."""
    from characters import lowpoly3d as lp, mascots3d as m
    fig = m.figure("anchor", "idle")
    k = lp.Parts(fig, fig.frames(), lp.PEOPLE["anchor"])
    for back, surface, out in ((False, lp.TRUNK.front, 1.0), (True, lp.TRUNK.back, -1.0)):
        lp._panel(k, _Still(), "test/panel", lp.TRUNK, [(0.6, -0.02, 0.1), (0.7, 0.0, 0.11)], "lp.navy", proud=0.005, deep=0.007, back=back)
        rows = _corners(k.made[-1])
        assert all(math.dist(p, end[0]) < 1e-4 for end in (rows[0], rows[-1]) for p in end)       # closed on a point
        own = rows[1:-1]
        heights = [0.6, *(s[0] for s in lp.TRUNK.s if 0.6 < s[0] < 0.7), 0.7]
        assert len(own) == len(heights) and all(abs(row[0][1] - y) < 1e-4 for row, y in zip(own, heights))
        for row in own:
            off = sorted(round(out * (z - surface(x, y)), 4) for x, y, z in row)
            assert off == [-0.007, -0.007, 0.005, 0.005, 0.005, 0.005], off
        flat = lp.TRUNK.at(0.6)[0] * lp.TRUNK.at(0.6)[3]                    # where the trunk's flat front (and back) ends
        assert any(abs(x - flat) < 1e-4 for x, _y, _z in own[0])
