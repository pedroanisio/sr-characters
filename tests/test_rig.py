"""The figure itself: limbs that read, feet that lift, the contact shadow.

    SRLOCATIONS_PY -m pytest characters/tests -q              # everything (about 5 minutes)
    SRLOCATIONS_PY -m pytest characters/tests -q -m "not slow"   # the quick run
"""
import pytest

from characters import clip, film, motion, staging  # noqa: F401
from characters.poses import POSES  # noqa: F401

from helpers import ACTIONS, ALIGNMENT, drawn, one  # noqa: F401

def test_contact_shadow_stays_on_the_ground():
    from characters import mascots3d as m

    def shadows(**fields):
        return [p for p in m.figure("bear", "idle", **fields).build() if isinstance(p, m.Contact)]

    resting, in_the_air = shadows(), shadows(hop=0.15)
    assert len(resting) == 2 and shadows(shadow=0) == []
    assert all(p.hulls(None) == [] for p in resting)                              # nothing collides with a shadow
    assert all(up.radii[0] < down.radii[0] for up, down in zip(in_the_air, resting))   # smaller off the ground
    assert all(abs(p.at.y + 0.15) < 0.01 for p in in_the_air)                     # and left on the ground, 15 cm below
    assert all(p.looks == (m.CONTACT_LOOK,) for p in resting)                     # only the plush look draws it


def test_arms_and_feet_read_as_limbs():
    from characters import mascots3d as m
    parts = {p.name: p for p in m.figure("bunny", "idle").build()}
    # an arm is its own ink group, paw included: a line runs round it where it lies over a body of its own colour
    assert {"arm_l/upper", "arm_l/fore", "arm_l/hand", "arm_r/upper", "arm_r/hand"} <= set(parts)
    assert not any(name.startswith("body/") and ("upper" in name or "hand" in name) for name in parts)
    spec = m.SPECS["bunny"]
    reach = (parts["arm_r/hand"].at - parts["arm_r/upper"].at).length
    assert spec.arm_r < 0.04 and spec.arm_r * spec.hand > spec.arm_r * 1.3 and reach > 0.04   # a slim arm, a paw wider than it

    def foot(**fields):
        return next(p for p in m.figure("bunny", "idle", **fields).build() if p.name == "foot_r/foot")

    down, up = foot(), foot(foot_right_up=0.04, foot_right_ahead=0.03)
    assert abs((up.at.y - down.at.y) - 0.04) < 1e-6 and up.at.z > down.at.z      # it leaves the ground and goes forward
    f, actor = one("bunny")
    actor.do(0.3, "kick")
    f.perform(2.5)
    track = f.loc.motion[id(actor.fig)]
    lifts = [(track.at(0.3 + k / 12)["foot_left_up"], track.at(0.3 + k / 12)["foot_right_up"]) for k in range(21)]   # on the keys
    assert max(a for a, _b in lifts) > 0.03 and max(b for _a, b in lifts) > 0.03          # each foot leaves the ground
    assert all(min(a, b) < 0.012 for a, b in lifts)                                       # one at a time: a march
