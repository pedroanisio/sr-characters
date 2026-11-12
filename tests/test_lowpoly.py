"""The low-poly people (characters.lowpoly3d).

    SRLOCATIONS_PY -m pytest characters/tests/test_lowpoly.py -q
"""
import math

from characters import film
from characters.poses import POSES


def test_lowpoly_people_share_one_kit_and_pose():
    from characters import cloth, lowpoly3d as lp, mascots3d as m
    assert {"sergeant", "cook", "firefighter", "captain", "anchor"} <= set(lp.PEOPLE) <= set(film.PEOPLE)
    assert {lp.PEOPLE[k].body for k in lp.PEOPLE} == {"man", "woman", "tall"} <= set(lp.BODIES)      # three builds
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
    low = lp.PEOPLE["anchor"].shoe * lp.BODIES[lp.PEOPLE["anchor"].body].foot       # (and as much smaller as his build's feet are)
    for name in ("shoe_l/sole", "shoe_l/upper"):
        assert abs(tall("anchor", name) - low * tall("sergeant", name)) < 1e-4 and lp.PEOPLE["anchor"].shoe < 1.0
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


SUIT = {"jacket/coat", "jacket/lapel", "jacket/collar", "jacket/button", "jacket/flap", "jacket/seam",
        "shirt/front", "collar/band", "collar/wing", "tie/knot", "tie/blade", "cuff_l/cuff", "cuff_r/cuff",
        "sleeve_l/button", "sleeve_r/button"}


def test_a_suit_is_parts_that_dress_every_build_and_bare_headed_hair_has_a_top():
    """The anchor: the tall build in a suit, bare-headed. The suit's parts are there, each in the person's colour
    for it; the hair covers the top of the head, in two colours; those who wear a hat are as they were; and the
    same suit dresses the other build, with nothing written again."""
    from dataclasses import replace
    from characters import lowpoly3d as lp, mascots3d as m
    anchor = lp.PEOPLE["anchor"]
    parts = {p.name: p for p in m.figure("anchor", "idle").build() if not isinstance(p, m.Contact)}
    assert SUIT <= set(parts) and lp.OUTFITS[anchor.outfit] is lp._suit and anchor.body == "tall"
    wears = lambda *names: {parts[n].material for n in names}        # noqa: E731
    assert wears("jacket/coat", "jacket/lapel", "jacket/collar", "jacket/flap", "body/body", "sleeve_l/fore") == {anchor.top}
    assert wears("jacket/seam") == {anchor.trim} and wears("jacket/button") == {anchor.buttons}
    assert wears("shirt/front", "collar/band", "collar/wing", "cuff_l/cuff", "cuff_r/cuff") == {anchor.shirt}
    assert wears("tie/knot", "tie/blade") == {anchor.tie} and wears("leg_l/shin") == {anchor.bottom}
    assert not anchor.turn_ups and "leg_l/turn-up" not in parts          # his trousers have no turn-ups: they are a person's option
    # the jacket's body is one coat (written as parts one above the other): from a little over where the legs
    # part, over the hips and the trunk, up into the collar; its seam runs its whole length
    low = lambda name: min(p[1] for row in _corners(parts[name]) for p in row)       # noqa: E731
    top = lambda name: max(p[1] for row in _corners(parts[name]) for p in row)       # noqa: E731
    coat = [p[1] for part in m.figure("anchor", "idle").build() if getattr(part, "name", "") == "jacket/coat"
            for row in _corners(part) for p in row]
    assert low("hips/hips") + 0.02 < min(coat) < low("hips/hips") + 0.05 and max(coat) > top("body/body") - 0.02 > low("collar/band")
    assert low("jacket/seam") < min(coat) + 0.01 and top("jacket/seam") > max(coat) - 0.01
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
    assert SUIT | {"hair/top"} <= set(hers) and hers["jacket/coat"].radii[0] != parts["jacket/coat"].radii[0]


def _named(parts):
    """Parts by their name; a name that is drawn more than once (an eye, a brow, a painted line) keeps them all."""
    from characters import mascots3d as m
    named: dict = {}
    for part in parts:
        if not isinstance(part, m.Contact):
            named.setdefault(part.name, []).append(part)
    return named


def _is_drawn(part) -> bool:
    return "drawn" in getattr(part, "role", "").split()


def test_a_person_picks_its_face_and_the_first_face_is_as_it_was():
    """Faces are a choice per person (Person.face, FACES): two people of one build can have different ones and a
    face goes on any build. With none, a person has the kit's first face on its build's own skull, as it was
    before there were others: the same measures, the same parts, a painted line for a mouth, bars for brows."""
    from dataclasses import replace
    from characters import lowpoly3d as lp, mascots3d as m
    assert all(p.face is None for k, p in lp.PEOPLE.items() if k != "anchor") and lp.Person("x", "X").face is None
    first = lp.FACE
    assert first == lp.Face() and first.skull is None and first.brows is None and first.lips is None
    assert (first.eye_x, first.eye_y, first.eye, first.iris, first.pupil, first.glint) == (0.37, 0.0, (0.016, 0.009), 0.0096, 0.0045, 0.0022)
    assert (first.eye_shape, first.lid, first.slant, first.wide, first.lash) == (lp.ALMOND, 0.0, 0.0, 1.32, (0.6, -0.2))
    assert (first.brow_at, first.brow_down, first.nose, first.nostril) == ((0.37 + 0.02, 0.3, 0.26), 1.0, lp.NOSE, 0.0)
    assert lp.NOSE == ((-0.037, 0.013, 0.004, 0.5), (-0.025, 0.021, 0.027, 0.4), (0.013, 0.006, 0.004, 0.8))
    assert (first.mouth_x, first.mouth_y) == (0.5, -0.58)
    assert (first.ear_back, first.ear_drop, first.ear_turn, first.ear, first.ear_out) == (0.008, 0.009, 32.0, 1.0, 0.001)
    near = lambda a, b: all(abs(x - y) < 1e-6 for x, y in zip(a, b))        # noqa: E731
    for who in ("sergeant", "captain"):
        parts = _named(m.figure(who, "idle").build())
        skull = lp.BODIES[lp.PEOPLE[who].body].skull
        assert parts["head/head"][0].samples == (10, len(skull.s) + 1)
        assert len(parts["hair/brow"]) == 4 and not any(_is_drawn(p) for p in parts["hair/brow"])      # two bars, each bent once
        assert len(parts["mouth/line"]) == 8 and {p.material for p in parts["mouth/line"]} == {"m.ink"}   # a painted line
        assert parts["nose/nose"][0].samples == (6, 4) and not {"mouth/upper", "mouth/lower", "nose/nostril", "eye-lid"} & set(parts)
        assert [len(parts[n]) for n in ("eye-lash", "eye-white", "eye", "eye-pupil", "eye-shine")] == [2] * 5
        # the sizes of what is drawn, as they were measured before a face was a choice
        assert near(parts["eye-white"][0].radii, (0.016, 0.0095, 0.001)) and near(parts["eye"][0].radii, (0.0096, 0.009, 0.001))
        assert near(parts["eye-lash"][0].radii, (0.017102, 0.0068, 0.001)) and near(parts["ear_1/ear"][0].radii, (0.006, 0.0235, 0.024))
        assert near(parts["nose/nose"][0].radii[:2], (0.021, 0.0255))
    head = _named(m.figure("sergeant", "idle").build())
    off = [tuple(round(c, 5) for c in (e.at.x - head["head/head"][0].at.x, e.at.y - head["head/head"][0].at.y)) for e in head["eye-white"]]
    assert off == [(-0.02749, 0.01812), (0.0276, 0.01718)]                  # where the sergeant's eyes are on his head
    # on a build with a smaller head the painted lines and the brows' bars are as much thinner, so the face looks the same
    _t, leave_t = _enlisted(replace(lp.PEOPLE["sergeant"], key="test-face-tall", name="Tall", body="tall"))
    try:
        small, size = _named(m.figure("test-face-tall", "idle").build()), lp.BODIES["tall"].head
        assert size < 1.0 and abs(head["mouth/line"][0].radii[1] - 0.0019) < 1e-9
        for name in ("mouth/line", "mouth/fold", "hair/brow"):
            assert abs(small[name][0].radii[1] - size * head[name][0].radii[1]) < 1e-9, name
        shut = lambda who: _named(m.figure(who, replace(POSES[who]["idle"], eyes="closed")).build())["eye/closed"][0].radii[1]     # noqa: E731
        assert abs(shut("sergeant") - 0.003) < 1e-9 and abs(shut("test-face-tall") - size * 0.003) < 1e-9
    finally:
        leave_t()
    # the same person with another face: only the head differs, and the face is the same on the other build
    lean = lp.FACES["lean"]
    _a, leave_a = _enlisted(replace(lp.PEOPLE["sergeant"], key="test-face", name="Face", face="lean"))
    _b, leave_b = _enlisted(replace(lp.PEOPLE["captain"], key="test-face-2", name="Face 2", face="lean"))
    try:
        a, b = _named(m.figure("test-face", "idle").build()), _named(m.figure("test-face-2", "idle").build())
        for parts, person in ((a, _a), (b, _b)):
            assert parts["head/head"][0].samples == (10, len(lean.skull.s) + 1)      # the face's own skull, on either build
            assert len(parts["hair/brow"]) == 2 and all(_is_drawn(p) for p in parts["hair/brow"])
            assert all(parts[n] and all(_is_drawn(q) for q in parts[n]) for n in ("mouth/line", "mouth/upper", "mouth/lower"))
            assert len(parts["nose/nostril"]) == 2 and parts["nose/nose"][0].samples[0] == 8
            assert not any(p.material == "m.ink" for found in parts.values() for p in found)       # nothing is painted
            assert {p.material for p in parts["mouth/line"]} == {lean.lips.ink} and parts["mouth/upper"][0].material == person.shade
        of_head = lambda n: n.split("/")[0] in ("head", "hair", "nose", "mouth") or n.startswith(("eye", "ear_"))   # noqa: E731
        assert {n: len(v) for n, v in a.items() if not of_head(n)} == {n: len(v) for n, v in head.items() if not of_head(n)}
        up = lambda parts, n: parts[n][0].at.y                                  # noqa: E731
        assert up(a, "eye-white") > up(head, "eye-white") + 0.005              # this face has its eyes higher on the head
        assert a["head/head"][0].radii[0] < head["head/head"][0].radii[0] - 0.004      # and is narrower
        assert b["hair/brow"][0].radii[1] < 0.8 * a["hair/brow"][0].radii[1]   # the build's own weight of brow: hers are finer
    finally:
        leave_a()
        leave_b()
    assert lp.PEOPLE["anchor"].face == "lean" and lp.PEOPLE["anchor"].hair_style == "swept" and set(lp.FACES) >= {"lean"}


def test_a_modelled_face_keeps_its_parts_in_every_mouth_and_eye():
    """The "lean" face (modelled lips, brows with an outline, eyes under a lid) in the shared vocabulary: every
    mouth, with the opening following `mouth_open`; every state of the eyes, lids coming down, a gaze each way;
    every brow. Its parts are there in each, drawn (nothing painted but a dizzy spiral), sound, and on the head."""
    from dataclasses import replace
    from characters import expression, lowpoly3d as lp, mascots3d as m
    _p, leave = _enlisted(replace(lp.PEOPLE["sergeant"], key="test-face", name="Face", face="lean"))
    try:
        idle = POSES["test-face"]["idle"]
        head = lambda fields=None, **face: _named(m.figure("test-face", replace(idle, **face), **(fields or {})).build())   # noqa: E731
        always = ("head/head", "ear_1/ear", "ear_-1/ear", "ear_1/hollow", "nose/nose")
        lips = ("mouth/line", "mouth/upper", "mouth/lower")
        centre = tuple(head()["head/head"][0].at)

        def sound(parts, what):
            assert all(len(parts.get(n, ())) == 1 for n in always) and all(parts.get(n) for n in lips), what
            assert len(parts["hair/brow"]) == 2 == len(parts["nose/nostril"]), what
            assert all(max(len(p.x), len(p.y), len(p.z)) < 2000 for found in parts.values() for p in found if _is_drawn(p)
                       and p.name.split("/")[0] in ("mouth", "nose", "hair", "head")), what       # the paper engine's limit is 2,048
            for name, found in parts.items():
                if name.split("/")[0] in ("mouth", "nose", "hair") or name.startswith("eye"):
                    for part in found:
                        assert _is_drawn(part) or name in ("eye-shine", "eye/spiral"), (what, name)
                        if _is_drawn(part):
                            assert all(math.isfinite(c) for row in _corners(part) for q in row for c in q), (what, name)
                            assert all(math.dist(q, centre) < 0.17 for row in _corners(part) for q in row), (what, name)
            return parts

        tall = lambda parts, name: parts[name][0].radii[1]       # noqa: E731
        closed = {}
        for mouth in expression.MOUTHS:
            for openness in (0.0, 0.5, 1.0):
                parts = sound(head(dict(mouth_open=openness), mouth=mouth), (mouth, openness))
                assert ("mouth/teeth" in parts) == (mouth in ("open", "yell") and openness > 0.3)
                if mouth not in ("open", "yell", "o"):
                    closed[mouth] = [[p.samples for p in parts[n]] for n in lips]
            if mouth in ("open", "yell", "o"):                   # the opening follows the voice
                sizes = [tall(head(dict(mouth_open=o), mouth=mouth), "mouth/line") for o in (0.0, 0.5, 1.0)]
                assert sizes[0] < sizes[1] < sizes[2] and sizes[2] > 2.5 * sizes[0]
        assert len(closed) == 5 and all(v == closed["smile"] for v in closed.values())      # the same strips, bent otherwise
        corner = lambda parts, side: max((q for row in _corners(parts["mouth/line"][0]) for q in row), key=lambda q: side * q[0])[1]   # noqa: E731
        smile, frown, smug = head(mouth="smile"), head(mouth="frown"), head(mouth="smug")
        assert corner(smile, 1) > corner(frown, 1) + 0.004 and corner(smile, -1) > corner(frown, -1) + 0.004
        assert corner(smug, 1) - corner(smug, -1) > 0.004 and corner(smile, 1) > corner(smile, -1)       # lopsided, the smile a little
        between = sound(head(dict(mouth_from="frown", mouth_mix=0.5), mouth="smile"), "becoming a smile")
        assert corner(frown, 1) < corner(between, 1) < corner(smile, 1)
        assert "mouth/fold" in smile and "mouth/fold" not in frown
        # eyes: open in four ways, with the lid at rest, part way down and nearly shut; then shut; then dizzy
        for eyes in ("normal", "wide", "squint", "half"):
            for lid in (0.0, 0.4, 0.8):
                parts = sound(head(dict(lid=lid), eyes=eyes), (eyes, lid))
                assert [len(parts[n]) for n in ("eye-lash", "eye-white")] == [2, 2], (eyes, lid)
        normal, wide, half = head(eyes="normal"), head(eyes="wide"), head(eyes="half")
        assert tall(wide, "eye-white") > tall(normal, "eye-white") > tall(half, "eye-white") and len(half["eye-lid"]) == 2
        assert len(normal["eye"]) == 2 == len(normal["eye-pupil"]) == len(normal["eye-shine"])
        assert tall(head(dict(lid=0.5)), "eye-white") < 0.7 * tall(normal, "eye-white")      # a blink on its way
        for shut in (head(eyes="closed"), head(dict(lid=1.0)), head(eyes="closed", mouth="frown")):
            sound(shut, "shut")
            assert len(shut["eye-lash"]) == 2 and not {"eye-white", "eye", "eye/closed"} & set(shut)
        assert "eye/spiral" in sound(head(eyes="spiral"), "spiral")
        iris = lambda parts: [(p.at.x, p.at.y) for p in parts["eye-pupil"]]      # noqa: E731
        left, right, up, down = (iris(sound(head(look=look), look)) for look in ((-1.0, 0.0), (1.0, 0.0), (0.0, 1.0), (0.0, -1.0)))
        assert all(b[0] - a[0] > 0.005 for a, b in zip(left, right)) and all(b[1] - a[1] > 0.002 for a, b in zip(down, up))
        # brows: each state is two strips; raised they are higher, and a brow that was not there grows in
        height = lambda parts: max(q[1] for p in parts["hair/brow"] for row in _corners(p) for q in row)      # noqa: E731
        for brows in ("none", "flat", "raised", "worried", "angry", "skeptic", "arched"):
            sound(head(brows=brows), brows)
        assert height(head(brows="raised")) > height(head(brows="flat")) + 0.004
        growing = sound(head(dict(brows_from="none", brow_mix=0.5), brows="flat"), "growing in")
        assert growing["hair/brow"][0].radii[1] < head(brows="flat")["hair/brow"][0].radii[1]
    finally:
        leave()


def test_a_hair_style_is_a_whole_head_of_hair_in_one_colour_or_two():
    """HAIR_TOPS holds tops for the build's own hair (a Loft: "brushed") and whole heads of hair (Hair: "swept"),
    which any bare-headed person wears, in one colour or with `temples` for its sides, on any build and face."""
    from dataclasses import replace
    from characters import lowpoly3d as lp, mascots3d as m
    swept = lp.HAIR_TOPS["swept"]
    assert isinstance(swept, lp.Hair) and isinstance(lp.HAIR_TOPS["brushed"], lp.Loft)
    assert swept.top.sides == 10 == len(swept.hem) and swept.sides.sides == 8 and lp.hair_planes(0.8) == lp.HAIR_SHAPE
    # it leaves a sideburn: its front is ahead of the ear above the ear's middle, and behind the ear below it
    ear_z = lp.HEAD[0][2] - lp.FACES["lean"].ear_back
    front = lambda y: max(z for x, z in swept.sides.ring(y) if x > 0.9 * swept.sides.at(y)[0])      # noqa: E731
    assert front(0.875) > ear_z + 0.025 and front(0.845) < ear_z
    for skull in (lp.SKULL, lp.FACES["lean"].skull):             # and stands out of either skull at the sides
        assert all(swept.sides.at(y)[0] > skull.at(y)[0] + 0.003 for y in (0.875, 0.9, 0.92))
    # behind, the top is outside the sides' hair all the way down its V, from the V's point up to the top's own back
    point = swept.top.s[0][0] + min(swept.hem)
    z0, y1, z1 = swept.sides.back(0.0, point, 0.004), swept.top.s[1][0], min(z for _x, z in swept.top.ring(swept.top.s[1][0]))
    assert all(z0 + (z1 - z0) * t < swept.sides.back(0.0, min(point + (y1 - point) * t, swept.sides.s[-1][0])) - 0.001 for t in (0.2, 0.4, 0.6, 0.8))
    anchor = lp.PEOPLE["anchor"]
    cases = [("one", replace(anchor, key="test-hair", name="Hair", hair_style="swept", temples=None, hair="lp.hair-black", face=None)),
             ("two", replace(anchor, key="test-hair", name="Hair", hair_style="swept", temples="lp.hair-grey", hair="lp.hair-dark", face="lean")),
             ("two", replace(anchor, key="test-hair", name="Hair", hair_style="swept", temples="lp.hair", hair="lp.hair-black", body="woman"))]
    for colours, person in cases:
        _p, leave = _enlisted(person)
        try:
            parts = _named(m.figure("test-hair", "idle").build())
            assert len(parts["hair/hair"]) == 1 <= len(parts["hair/top"]) and all(_is_drawn(q) for n in ("hair/hair", "hair/top") for q in parts[n])
            assert parts["hair/top"][0].material == person.hair and parts["hair/hair"][0].material == (person.temples or person.hair)
            assert (parts["hair/top"][0].material != parts["hair/hair"][0].material) == (colours == "two")
            rows = [row for i, piece in enumerate(parts["hair/top"]) for row in _corners(piece)[1 if i else 0:]]     # (a long shell is drawn in parts that share a ring)
            assert len(rows) == len(swept.top.s) + 2 and all(len(row) == 10 for row in rows)
            for end in (rows[0], rows[-1]):                      # closed above and below
                assert max(math.dist(q, end[0]) for q in end) < 1e-4
            top = lambda name: max(q[1] for piece in parts[name] for row in _corners(piece) for q in row)       # noqa: E731
            assert top("hair/top") > top("head/head") + 0.02 and top("hair/top") > top("hair/hair") + 0.03
            # its hem: highest over the forehead, and down the back of the head in a V whose point is in the middle
            hem = rows[1]
            point, brow = min(hem, key=lambda q: q[1]), max(hem, key=lambda q: q[1])
            middle = parts["head/head"][0].at
            assert abs(point[0] - middle.x) < 0.006 and point[2] < middle.z - 0.05 and brow[2] > middle.z + 0.03
            sides = sorted(q[1] for q in hem)
            assert sides[1] - point[1] > 0.02 and brow[1] - point[1] > 0.05
        finally:
            leave()
    # the style of the build's own hair still takes a top over it, and under a hat there is none
    _p, leave = _enlisted(replace(anchor, key="test-hair", name="Hair", hair_style="brushed", face=None))
    try:
        parts = _named(m.figure("test-hair", "idle").build())
        assert parts["hair/top"][0].samples[0] == 8 and parts["hair/hair"][0].samples == (8, len(lp.HAIR.s) + 1)
    finally:
        leave()
    assert "hair/top" not in _named(m.figure("sergeant", "idle").build())


def test_a_shell_is_drawn_corner_by_corner_whichever_way_round():
    """_shell: rings of points become a drawn part that closes on the middle of its first and last ring, and its
    faces look outward as a Loft's do whichever way round the rings were given."""
    from characters import lowpoly3d as lp, mascots3d as m
    fig = m.figure("sergeant", "idle")
    k = lp.Parts(fig, fig.frames(), lp.PEOPLE["sergeant"])
    rings = [[(0.02, y, 0.01 + 0.01 * y), (-0.02, y, 0.01), (-0.02, y, -0.01), (0.025, y + 0.004, -0.01)] for y in (0.0, 0.03, 0.05)]

    def held(grid):          # six times what the corners hold, counted the way they run
        vol = 0.0
        for lo, hi in zip(grid, grid[1:]):
            for i in range(len(lo)):
                j = (i + 1) % len(lo)
                for a, b, c in ((lo[i], lo[j], hi[j]), (lo[i], hi[j], hi[i])):
                    vol += a[0] * (b[1] * c[2] - b[2] * c[1]) + a[1] * (b[2] * c[0] - b[0] * c[2]) + a[2] * (b[0] * c[1] - b[1] * c[0])
        return vol

    lp._shell(k, _Still(), "test/shell", rings, "lp.navy")
    lp._shell(k, _Still(), "test/shell", [ring[::-1] for ring in rings], "lp.navy")
    one, other = k.made[-2:]
    assert one.role == "drawn" and one.samples == (4, 4) and one.u == (0, 4) and one.v == (0, 4)
    at = lambda part: [[tuple(c + o for c, o in zip(q, part.at)) for q in row] for row in _grid(part)]      # noqa: E731
    a, b = at(one), at(other)
    assert all(math.dist(q, a[0][0]) < 1e-4 for q in a[0]) and all(math.dist(q, a[-1][0]) < 1e-4 for q in a[-1])
    assert all(min(math.dist(q, c) for c in a[1]) < 1e-4 for q in rings[0]) and all(min(math.dist(q, c) for c in a[3]) < 1e-4 for q in rings[2])
    assert all(min(math.dist(q, c) for c in rb) < 1e-4 for ra, rb in zip(a, b) for q in ra)        # the same corners, either way round
    loft = lp.Loft([(0.0, 0.02, 0.01, 0.0), (0.05, 0.02, 0.01, 0.0)]).limb("test/loft", _Still(), "lp.navy", None)
    assert held(a) < 0 and held(b) < 0 and held(_grid(loft)) < 0
    # a shell with many rings and corners is drawn as parts that share a ring, none with a formula the paper engine refuses
    ring = lambda y: [(0.05 * math.cos(i) + 0.001 * i * y, y, 0.04 * math.sin(i) + 0.002 * i) for i in range(12)]      # noqa: E731
    lp._shell(k, _Still(), "test/long", [ring(0.01 * j) for j in range(9)], "lp.navy")
    long = [p for p in k.made if p.name == "test/long"]
    assert len(long) > 1 and all(max(len(p.x), len(p.y), len(p.z)) <= lp.SHELL_LONG for p in long)
    assert sum(p.samples[1] for p in long) == 10 and all(p.samples[0] == 12 for p in long)       # nine rings and two ends: ten bands
    for one, other in zip(long, long[1:]):
        assert all(math.dist(p, q) < 1e-4 for p, q in zip(at(one)[-1], at(other)[0]))               # where one ends the next begins


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


def _suited(who, pose="idle"):
    """The anchor's jacket on `who`'s build, in a pose: the Parts its body was drawn with, its Coat, and the parts
    the coat is made of (one above the other)."""
    from dataclasses import replace
    from characters import lowpoly3d as lp, mascots3d as m
    fig = m.figure(who, pose)
    k = lp.Parts(fig, fig.frames(), replace(lp.PEOPLE["anchor"], body=lp.PEOPLE[who].body))
    lp._body(k)
    before = len(k.made)
    return k, lp._coat(k, "lp.suit"), k.made[before:]


def test_a_coat_is_one_shell_that_the_chest_and_the_hips_carry_on_every_build():
    """A jacket's body: six rings, none of them level; it lies on the trunk it is measured on, which is drawn slimmer
    under it, and hangs off the hips, on every build; it is taken in at the waist and widest at the shoulders, and
    its hem is over where the legs part; the chest carries it from the waist up and the hips carry its skirt,
    whatever the trunk does; seated, the fronts of the skirt go forward over the lap and the back hangs where it
    did; and its facets are the same ones in every pose."""
    from characters import lowpoly3d as lp
    builds = {p.body: key for key, p in lp.PEOPLE.items()}
    assert set(builds) == set(lp.BODIES)
    for body, who in builds.items():
        k, coat, pieces = _suited(who)
        b = lp.BODIES[body]
        assert {p.name for p in pieces} == {"jacket/coat"} and len(coat.loft.s) == 6 == len(coat.rings)
        # one shell, written as parts one above the other: eight rows of fifteen corners (a point, the six rings, a
        # point), each part on from the ring the last ended on
        assert all(p.samples[0] == 15 for p in pieces) and sum(p.samples[1] for p in pieces) == 7
        grids = [_grid(p) for p in pieces]
        assert all(max(math.dist(p, end[0]) for p in end) < 1e-4 for end in (grids[0][0], grids[-1][-1]))      # closed at both ends
        for lower, upper in zip(pieces, pieces[1:]):
            assert max(math.dist(p, q) for p, q in zip(_corners(lower)[-1], _corners(upper)[0])) < 3e-5
        for ring in coat.rings[1:4]:                 # the pockets' line, the waist, the chest: no ring is a level line
            ys = sorted(p[1] for p in ring)
            assert ys[-1] - ys[0] > 0.015 and len({round(y, 3) for y in ys}) >= 8, body
        for lower, upper in zip(coat.rings[1:], coat.rings[2:]):      # and no two rings cross, however near they are
            assert min(b[1] - a[1] for a, b in zip(lower, upper)) > 0.01, body
        # it lies on the trunk (at its rings on it, between them never more than 2 mm inside it), and the trunk as
        # it is drawn under it is 9 mm slimmer: further in than any dent of the coat; it hangs off the hips
        for y, rx, rz, zc, *_ in b.trunk.s:
            if coat.hem < y < coat.loft.s[-1][0]:
                w, d, c, _f = coat.loft.at(y)
                assert w - rx > -0.0021 and (c + d) - (zc + rz) > -0.0021 and (zc - rz) - (c - d) > -0.0021, (body, y)
        for y, rx, rz, zc, *_ in b.pelvis.s:
            if coat.hem < y:
                w, d, c, _f = coat.loft.at(y)
                assert w - rx > 0.0045 and (c + d) - (zc + rz) > 0.0045 and (zc - rz) - (c - d) > 0.0045, (body, y)
        for y in (coat.waist, coat.loft.s[3][0], coat.loft.s[4][0]):
            assert abs(coat.loft.back(0.0, y) - b.trunk.back(0.0, y)) < 0.016 and coat.loft.front(0.0, y) - b.trunk.front(0.0, y) < 0.012
        drawn = next(p for p in k.made if p.name == "body/body")
        full = b.trunk.limb("body/body", k.chest, "lp.suit", None)
        assert abs(full.radii[0] - drawn.radii[0] - 0.009) < 1e-6 and drawn.material == lp.PEOPLE["anchor"].top
        wide = [s[1] for s in coat.loft.s]           # the hem, the pockets, the waist, the chest, the shoulders, the neck
        assert wide[2] < wide[1] < wide[0] and wide[2] < wide[3] < wide[4] > 2 * wide[5], (body, wide)
        assert b.pelvis.s[0][0] + 0.02 < coat.hem < coat.pocket < coat.waist                       # the hem is over where the legs part
        assert coat.waist == coat.loft.s[2][0] and coat.pocket == coat.loft.s[1][0] and coat.hem == coat.loft.s[0][0]
        # the trunk leans: the upper rings stay where the chest has them, the skirt's where the hips have them
        lean, leant, leaning = _suited(who, "dizzy")
        on_hips = lambda k_, c_, rings: [lp._into(k_.hips, k_.chest.point(p)) for ring in rings for p in ring]      # noqa: E731
        assert coat.rings[2:] == leant.rings[2:]
        assert max(math.dist(p, q) for p, q in zip(on_hips(k, coat, coat.rings[:2]), on_hips(lean, leant, leant.rings[:2]))) < 1e-6
        assert max(math.dist(p, q) for p, q in zip(coat.rings[0], leant.rings[0])) > 0.01, body      # (and it did lean)
        # seated: a thigh takes the front of the skirt with it; the back hangs where it did
        sat_k, sat, sitting = _suited(who, "sit")
        stood, seated = on_hips(k, coat, coat.rings[:1]), on_hips(sat_k, sat, sat.rings[:1])
        assert all(seated[i][2] - stood[i][2] > 0.05 and seated[i][1] - stood[i][1] > 0.04 for i in lp._FRONT), body
        assert all(math.dist(stood[i], seated[i]) < 1e-6 for i in (10, 11, lp._SEAM, 13, 14))
        roles = [p.role for p in pieces]             # the same facets in every pose, and no side cut where two parts meet
        assert roles == [p.role for p in leaning] == [p.role for p in sitting] and all("facet:100:7:" in r for r in roles)
        assert len({r.split(":")[3] for r in roles}) == 1 and max(int(w) for w in roles[0].split(":")[3].split(",")) < 145
        # what lies on its front lies on it: in the middle of the front, where lapels, a shirt's front and a tie are
        # laid on its loft, the coat as drawn (its corners off their rings) is never outside the loft, and within 2.5 mm
        for i in (2, 3, 7):
            edge = [ring[i] for ring in coat.rings[2:]]
            for (x0, y0, z0), (x1, y1, z1) in zip(edge, edge[1:]):
                for t in (0.0, 0.25, 0.5, 0.75, 1.0):
                    off = z0 + (z1 - z0) * t - coat.loft.ring(y0 + (y1 - y0) * t)[i][1]
                    assert -0.0025 < off < 1e-6, (body, i, off)


def test_a_skin_goes_through_the_corners_it_is_given():
    """`_skin` draws a part corner by corner: through the rings as they are given (not level, if they are not),
    closed on the points it is told, the same part whichever way round the rings run, and it tells the finish how
    its sides break. `_into` brings a place of the figure back into a carry's own space."""
    from characters import lowpoly3d as lp, mascots3d as m
    fig = m.figure("anchor", "idle")
    k = lp.Parts(fig, fig.frames(), lp.PEOPLE["anchor"])
    square = lambda y, r, lean=0.0: [(r, y + lean, r), (-r, y, r), (-r, y - lean, -r), (r, y, -r)]      # noqa: E731
    rings, ends = [square(0.0, 0.05), square(0.1, 0.06, 0.01), square(0.25, 0.04)], ((0.0, -0.001, 0.0), (0.0, 0.251, 0.01))
    lp._skin(k, _Still(), "test/skin", rings, "lp.navy", crease=8.0, facet=90.0, ends=ends)
    part = k.made[-1]
    rows = _corners(part)
    assert _is_drawn(part) and part.samples == (4, 4) and len(rows) == 5
    assert all(math.dist(p, q) < 3e-5 for ring, row in zip(rings, rows[1:-1]) for p, q in zip(ring, row))
    assert all(math.dist(p, end) < 3e-5 for row, end in ((rows[0], ends[0]), (rows[-1], ends[1])) for p in row)
    tag = next(t for t in part.role.split() if t.startswith("facet:")).split(":")
    assert tag[1:3] == ["90", "8"] and len(tag[3].split(",")) == 4 and [x == "0" for x in tag[4].split(",")] == [True, False, False, True]
    lp._skin(k, _Still(), "test/skin", [[ring[0], *ring[:0:-1]] for ring in rings], "lp.navy", crease=8.0, facet=90.0, ends=ends)
    assert (k.made[-1].x, k.made[-1].y, k.made[-1].z, k.made[-1].role) == (part.x, part.y, part.z, part.role)
    lp._skin(k, _Still(), "test/plain", rings, "lp.navy")                 # no crease: its corners and nothing more
    assert k.made[-1].role == "drawn" and all(math.dist(p, q) < 3e-5 for p, q in zip(_corners(k.made[-1])[-1], [(0.0, 0.25, 0.0)] * 4))
    for who in ("sergeant", "anchor"):               # every carry of every build: the hips, the chest, a sized head
        fig = m.figure(who, "explain")
        k = lp.Parts(fig, fig.frames(), lp.PEOPLE[who])
        for carry in (k.hips, k.chest, k.head):
            assert math.dist(lp._into(carry, carry.point((0.03, 0.9, 0.02))), (0.03, 0.9, 0.02)) < 1e-9


def test_a_round_button_a_flat_flap_and_a_closed_collar_are_asked_for_and_the_first_ones_are_as_they_were():
    """What the suit needed of the shared parts is a parameter each, and without it they draw what they drew: a
    button is a stud unless it is asked round (a disc of eight sides on the facet); a flap is as thick and as sunk
    as it was unless told; a collar's wings lie on the trunk, narrow at their top, unless given a coat to lie on
    and a wide top that starts lower."""
    from characters import lowpoly3d as lp, mascots3d as m
    fig = m.figure("anchor", "idle")
    k = lp.Parts(fig, fig.frames(), lp.PEOPLE["anchor"])
    wall = lp.Loft([(0.0, 0.05, 0.05, 0.0), (0.2, 0.05, 0.05, 0.0)])        # an upright front, 0.05 forward
    lp._button(k, _Still(), "test/button", wall, 0.0, 0.1, "lp.button", 0.01)
    assert not _is_drawn(k.made[-1]) and all(abs(a - b) < 1e-9 for a, b in zip(k.made[-1].radii, (0.01, 0.01, 0.007)))
    lp._button(k, _Still(), "test/button", wall, 0.0, 0.1, "lp.button", 0.01, 0.003, shape="round")
    disc = [p for row in _corners(k.made[-1])[1:-1] for p in row]
    assert _is_drawn(k.made[-1]) and len({(round(x, 4), round(y, 4)) for x, y, _z in disc}) == 8
    assert all(abs(math.hypot(x, y - 0.1) - 0.01 * math.hypot(1.0, 0.41)) < 1e-4 for x, y, _z in disc)
    assert abs(max(z for _x, _y, z in disc) - 0.056) < 1e-4 and abs(min(z for _x, _y, z in disc) - 0.05) < 1e-4
    depth = lambda: sorted({round(z, 4) for row in _corners(k.made[-1])[1:-1] for _x, _y, z in row})      # noqa: E731
    lp._flap(k, _Still(), wall, 0.0, 0.1, 0.03, "lp.navy")
    first = (k.made[-1].x, k.made[-1].y, k.made[-1].z, tuple(k.made[-1].at))
    assert depth() == [0.04, 0.056]
    lp._flap(k, _Still(), wall, 0.0, 0.1, 0.03, "lp.navy", thick=0.008, sink=0.002)
    assert (k.made[-1].x, k.made[-1].y, k.made[-1].z, tuple(k.made[-1].at)) == first
    lp._flap(k, _Still(), wall, 0.0, 0.1, 0.03, "lp.navy", thick=0.003, sink=0.0)
    assert depth() == [0.047, 0.053]
    # a collar: the wings as the officer wears them, and as a suit does, on its coat
    k, coat, _pieces = _suited("anchor")
    yn = k.b.trunk.s[-1][0]
    wing = lambda: [lp._into(k.chest, p) for row in _corners(k.made[-1])[1:-1] for p in row]      # noqa: E731
    across = lambda: max(p[0] for p in _grid(k.made[-1])[-2]) - min(p[0] for p in _grid(k.made[-1])[-2])      # noqa: E731  its top's width
    lp._open_collar(k)
    open_, narrow = wing(), across()
    lp._open_collar(k, on=coat.loft, top=0.017, rise=-0.016)
    closed, broad = wing(), across()
    high = lambda ps: max(p[1] for p in ps)      # noqa: E731  (a wing leans back with the chest: its top is a little under its length)
    assert yn - 0.004 < high(open_) < yn + 0.0045 and yn - 0.024 < high(closed) < yn - 0.012
    lp._open_collar(k, on=lp.Loft([(s[0], s[1] + 0.02, s[2] + 0.02, s[3]) for s in k.b.trunk.s]), top=0.017, rise=-0.016)
    assert abs(max(p[2] for p in wing()) - max(p[2] for p in closed) - 0.02) < 0.004      # they lie on what they are given
    assert abs(narrow - 0.01) < 1e-6 and abs(broad - 0.034) < 1e-6


def test_no_part_of_a_suited_person_has_a_formula_the_paper_engine_refuses(tmp_path):
    """The paper finish's engine takes no surface whose formula is longer than 2048 characters. Every part of a
    person in a suit stays under it, on every build, standing, leaning and seated (a coat is written as several
    parts for that), and the anchor is drawn in the paper finish. Turn-ups are a person's option: with them the
    trousers have a band at each hem, in their own cloth."""
    from dataclasses import replace
    from srlocations.templates import MAX_SURFACE_EXPRESSION
    from characters import lowpoly3d as lp, mascots3d as m
    assert lp._FORMULA < MAX_SURFACE_EXPRESSION
    anchor = lp.PEOPLE["anchor"]
    for body in lp.BODIES:
        person, leave = _enlisted(replace(anchor, key="suited", name="Suited", body=body, turn_ups=0.1))
        try:
            for pose in ("idle", "dizzy", "explain", "sit"):
                parts = [p for p in m.figure("suited", pose).build() if not isinstance(p, m.Contact)]
                for part in parts:
                    longest = max(len(part.x), len(part.y), len(part.z))
                    assert longest <= MAX_SURFACE_EXPRESSION, (body, pose, part.name, longest)
                    if part.name.split("/")[0] in ("jacket", "shirt", "tie", "collar", "cuff_l", "cuff_r"):
                        assert longest <= lp._FORMULA, (body, pose, part.name, longest)
                assert len([p for p in parts if p.name == "jacket/coat"]) > 1
                ups = [p for p in parts if p.name in ("leg_l/turn-up", "leg_r/turn-up")]
                assert len(ups) == 2 and {p.material for p in ups} == {person.bottom}
        finally:
            leave()
    f = film.Film("lowpoly-paper-suit", size=(120, 180))
    f.add("anchor", at=(0, 0, 0))
    f.camera((0, 0.6, 6), look_at=(0, 0.5, 0))
    assert f.still(tmp_path / "anchor.png").stat().st_size > 1000


def _enlisted(person):
    """A person put in the cast for one test (lowpoly3d.enlist), and what takes it out again."""
    from characters import lowpoly3d as lp, mascots3d as m

    def leave():
        for kept in (lp.PEOPLE, m.SPECS, m.NAMES, m.LOOKS, m.WHOLE, POSES):
            kept.pop(person.key, None)

    return lp.enlist(person), leave


def _built(who, pose="idle"):
    from characters import mascots3d as m
    return {p.name: p for p in m.figure(who, pose).build() if not isinstance(p, m.Contact)}


def test_a_person_enlisted_at_run_time_is_one_of_the_cast():
    """`enlist` is how the kit's own people are registered: a Person made later, on a build made later, draws all
    its parts in every pose; enlisting its key again replaces it."""
    from dataclasses import replace
    from characters import lowpoly3d as lp, mascots3d as m
    lp.BODIES["test-build"] = replace(lp.BODIES["woman"], hand=0.5)
    person, leave = _enlisted(replace(lp.PEOPLE["cook"], key="test-cook", name="Test cook", body="test-build"))
    try:
        assert lp.PEOPLE["test-cook"] is person and m.NAMES["test-cook"] == "Test cook" and m.WHOLE["test-cook"] is lp._whole
        assert m.SPECS["test-cook"].build is lp.BODIES["test-build"].build and m.SPECS["test-cook"].hand_length == lp.HAND_REACH * 0.5
        assert all(len(m.figure("test-cook", pose).build()) > 40 for pose in POSES["test-cook"])
        assert set(_built("test-cook")) == set(_built("cook"))
        small = _built("test-cook")["arm_l/hand"].radii
        lp.enlist(replace(person, body="man"))               # again, on another build: what was solved for the first is dropped
        assert m.SPECS["test-cook"].build is lp.BUILD and _built("test-cook")["arm_l/hand"].radii[0] > 1.9 * small[0]
        assert [p.radii for p in _built("test-cook").values()] == [p.radii for p in _built("cook").values()]
    finally:
        leave()
        del lp.BODIES["test-build"]
    assert "test-cook" not in lp.PEOPLE


def test_a_build_sizes_its_head_and_a_hat_follows_it():
    """Builds differ in the size of the head (Body.head, about the foot of the neck, carried Body.head_up higher):
    the skull, the ears, the hair, the face and whatever hat an outfit puts on it are that much smaller, places and
    sizes alike, with nothing asked of the outfit; the man's and the woman's are as they were drawn."""
    from dataclasses import replace
    from characters import lowpoly3d as lp, mascots3d as m
    man, tall = lp.BODIES["man"], lp.BODIES["tall"]
    assert (man.head, man.head_up, man.up) == (1.0, 0.0, 0.0) == (lp.BODIES["woman"].head, lp.BODIES["woman"].head_up, lp.BODIES["woman"].up)
    assert tall.head < 0.9 and tall.head_up > tall.up > 0.0
    assert man.reach_head == lp.REACH_HEAD and man.torso == lp.TORSO and man.on_head((0.01, 0.9, 0.02)) == (0.01, 0.9, 0.02)
    # what the gestures aim at follows the build: the same place on the head, and as much smaller
    (c, r), (tc, tr) = lp.REACH_HEAD, tall.reach_head
    assert all(abs(b - tall.head * a) < 1e-12 for a, b in zip(r, tr))
    assert abs(tc[1] - (lp.NECK_FOOT[1] + (c[1] - lp.NECK_FOOT[1]) * tall.head + tall.head_up)) < 1e-12
    # the sergeant's outfit, cap and all, on the tall build: one Person
    _person, leave = _enlisted(replace(lp.PEOPLE["sergeant"], key="test-tall", name="Tall", body="tall"))
    try:
        assert m.SPECS["test-tall"].head[:2] == tall.reach_head and m.SPECS["test-tall"].build is tall.build
        a, b = _built("sergeant"), _built("test-tall")
        assert set(a) == set(b)
        scale = lambda limb: [math.sqrt(sum(limb.basis[i][j] ** 2 for i in range(3))) for j in range(3)]     # noqa: E731
        on_head = ("head/head", "hair/hair", "ear_1/ear", "nose/nose", "eye-white", "cap/band", "cap/crown", "cap/peak", "cap/button", "badge/badge")
        for name in on_head:         # as much smaller; the size is in the part itself, and what carries it only turns it
            assert all(abs(q - tall.head * p) < 1e-9 for p, q in zip(a[name].radii, b[name].radii)), name
            assert b[name].x.startswith(f"{tall.head:.6f}*(") and not a[name].x.startswith(f"{tall.head:.6f}*("), name
        for name in (*on_head, "body/body", "hips/hips", "belt/belt", "collar/band", "leg_l/thigh", "arm_l/hand", "shoe_l/sole"):
            assert all(abs(s - 1.0) < 1e-9 for s in scale(a[name]) + scale(b[name])), name
        assert not b["body/body"].x.startswith(f"{tall.head:.6f}*(") and a["belt/belt"].radii[1] == b["belt/belt"].radii[1]
        # a part that asks the finish for facets tells it of sides and bands as much smaller
        tag = lambda limb: next(t for t in limb.role.split() if t.startswith("facet:")).split(":")      # noqa: E731
        was, now = tag(a["cap/crown"]), tag(b["cap/crown"])
        assert was[1:3] == now[1:3] and all(abs(float(q) - tall.head * float(p)) <= 0.5 for p, q in zip(was[3].split(","), now[3].split(",")))
        # the cap is where it was on the head: as far from the skull's own middle, times the head's size
        for name in ("cap/band", "cap/crown", "cap/peak", "hair/hair", "nose/nose"):
            far = [math.dist(tuple(parts[name].at), tuple(parts["head/head"].at)) for parts in (a, b)]
            assert abs(far[1] - tall.head * far[0]) < 1e-6, name
        top = lambda parts, name: max(p[1] for row in _corners(parts[name]) for p in row)       # noqa: E731
        low = lambda parts, name: min(p[1] for row in _corners(parts[name]) for p in row)       # noqa: E731
        tall_of = lambda parts, name: top(parts, name) - low(parts, name)                       # noqa: E731
        assert top(b, "cap/crown") > top(b, "head/head") and low(b, "head/head") < top(b, "collar/band") + 0.02
        assert 0.75 < tall_of(b, "head/head") / tall_of(a, "head/head") < 0.85
        # and it is drawn in every pose
        assert all(len(m.figure("test-tall", pose).build()) > 40 for pose in POSES["test-tall"])
    finally:
        leave()


def test_the_tall_build_stands_on_the_ground_with_its_hands_at_the_measured_height():
    """The third build, an adult as the anchor's sheet draws one (measured with characters/tools/lowpoly/sheet_match.py
    and its SHEETS["anchor"]): 1 m from its soles to the top of its hair, the legs parting at 0.45, the shoulders at
    0.76, an arm of 0.28 to the wrist; standing, its shoes are flat on the ground and its hands hang beside the
    thighs, the wrists at 0.50 and the fingertips at 0.39."""
    from dataclasses import replace
    from characters import lowpoly3d as lp, mascots3d as m
    tall = lp.BODIES["tall"]
    assert tall.build.height == 1.0 == lp.BODIES["man"].build.height
    _person, leave = _enlisted(replace(lp.PEOPLE["anchor"], key="test-adult", name="Adult", body="tall"))
    try:
        fig = m.figure("test-adult", "idle")
        parts = {p.name: p for p in fig.build() if not isinstance(p, m.Contact)}
        points = lambda name: [p for row in _corners(parts[name]) for p in row]          # noqa: E731
        for side in "lr":                                    # both shoes flat on the ground, the uppers clear of it
            assert abs(min(p[1] for p in points(f"shoe_{side}/sole"))) < 1e-5 and min(p[1] for p in points(f"shoe_{side}/upper")) > 0.005
        height = max(p[1] for p in points("hair/top"))
        assert abs(height - 1.0) < 0.012                     # the sheet's shares of the height are metres on it
        at = {name: fig.transform.apply(frame.position) for name, frame in fig.frames().items()}
        assert abs(at["right_upper_leg"].y - 0.50) < 0.01 and abs(at["right_upper_arm"].y - 0.763) < 0.01
        assert abs(abs(at["right_upper_arm"].x) - 0.098) < 0.005 and abs(at["neck"].y - 0.835) < 0.01
        arm = math.dist(tuple(at["right_upper_arm"]), tuple(at["right_lower_arm"])) + math.dist(tuple(at["right_lower_arm"]), tuple(at["right_hand"]))
        assert abs(arm - 0.28) < 0.006                       # the sheet's, from shoulder to wrist with the arms held out
        low = lambda name: min(p[1] for p in points(name))   # noqa: E731
        for side, s in (("left", "l"), ("right", "r")):
            assert abs(at[f"{side}_hand"].y - 0.496) < 0.01 and 0.13 < abs(at[f"{side}_hand"].x) < 0.17
            tips = min(low(f"arm_{s}/{n}") for n in HAND)
            assert 0.37 < tips < 0.41 and tips > at[f"{side}_lower_leg"].y + 0.08        # on the thigh, well over the knee
            assert at[f"{side}_lower_arm"].z > -0.06         # the elbow stays inside the back's outline
        # the legs part where the sheet's do, and the head is its share of the height
        assert abs(low("hips/hips") - 0.447) < 0.01
        chin = low("head/head")
        assert 0.13 < height - chin < 0.17 and abs(chin - 0.845) < 0.015
    finally:
        leave()


def test_a_hand_put_to_the_face_ends_on_it_on_every_build():
    """A person's hand is drawn on from the forearm (Spec.hand_length says how long it is), where a toy has a ball
    on its wrist. The gestures that put a hand to the face (mascots3d.gesture) place such a hand's wrist, on the
    figure as it stands, where the fingers end on the face: on each build the fingertips come to the chin and to the
    mouth (they stopped a hand's length in front of them); over the eyes and on the brow the fingers lie where the
    camera sees them on the eye and the brow, in front of the face and near it; and the two hands of a gesture
    made with both are each other's mirror."""
    from characters import lowpoly3d as lp, mascots3d as m
    from characters.doodle import Pose
    fingers = ("index", "middle", "ring", "little")
    (hx, hy, _hz), (rx, ry, _rz) = lp.HEAD
    people = ("sergeant", "captain", "anchor")
    assert {lp.PEOPLE[who].body for who in people} == {"man", "woman", "tall"}       # the three builds
    for who in people:
        person = lp.PEOPLE[who]
        face = lp.FACES[person.face] if person.face else lp.FACE
        assert m.SPECS[who].hand_length == lp.HAND_REACH * lp.BODIES[person.body].hand > 0.0
        for kind in ("chin", "lips", "eyes", "brow", "cuddle", "gasp"):
            arms = m.gesture(who, kind)
            fig = m.figure(who, Pose(joints=tuple(arms.items())))
            k = lp.Parts(fig, fig.frames(), person)
            skull = face.skull or k.b.skull
            chin = 0.5 * (face.mouth_y + (skull.s[0][0] - hy) / ry)      # between the mouth and the jaw's lowest row
            fx, fy = {"chin": (0.0, chin), "cuddle": (0.0, chin), "lips": (0.0, face.mouth_y), "gasp": (0.0, face.mouth_y),
                      "eyes": (face.eye_x, face.eye_y), "brow": (0.0, face.brow_at[1])}[kind]
            parts = {p.name: p for p in fig.build() if not isinstance(p, m.Contact)}
            both = kind in ("eyes", "cuddle", "gasp")
            for side, sx in ((("r", 1), ("l", -1)) if both else (("r", 1),)):
                x, y = hx + sx * fx * rx, hy + fy * ry
                mark = tuple(k.head.point((x, y, skull.front(x, y))))    # the place on the face, as the figure stands
                tips = [_corners(parts[f"arm_{side}/{f}-tip"])[-1][0] for f in fingers]
                corners = [p for f in fingers for n in (f, f"{f}-tip") for row in _corners(parts[f"arm_{side}/{n}"]) for p in row]
                near = min(math.dist(p, mark) for p in corners)
                if kind in ("eyes", "brow"):     # seen from the front the fingers are on the place; they are before it
                    over = [p for p in corners if math.hypot(p[0] - mark[0], p[1] - mark[1]) < 0.015]
                    assert over and min(p[2] for p in over) > mark[2] and near < 0.055, (who, kind, side, near)
                else:                            # a fingertip is at it (the middle of a tip's end; a finger is 2 cm thick)
                    tip = min(math.dist(t, mark) for t in tips)
                    assert tip < 0.04 and near < 0.03, (who, kind, side, tip, near)
            if both:
                assert all(abs(arms[n] - arms[n.replace("right_", "left_")]) < 0.01 for n in arms if n.startswith("right_")), (who, kind)
    # (only a figure with a hand length is placed so: the plush toys and the vinyl people have none)
    assert m.SPECS["bear"].hand_length == 0.0 == m.SPECS["officer"].hand_length
