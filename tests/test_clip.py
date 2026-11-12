"""Scene files slimmed for the engine (characters.clip).

    SRLOCATIONS_PY -m pytest characters/tests -q              # everything (about 5 minutes)
    SRLOCATIONS_PY -m pytest characters/tests -q -m "not slow"   # the quick run
"""
import pytest

from characters import clip, film, motion, staging  # noqa: F401
from characters.poses import POSES  # noqa: F401

from helpers import ACTIONS, ALIGNMENT, drawn, one  # noqa: F401

def test_slim_keeps_the_motion_and_shrinks_the_file(tmp_path):
    keys = "".join(f'\n      <key time="{k / 24!r}" value="{k * 0.5:.4f}"/>' for k in range(49))          # a straight line
    bent = "".join(f'\n      <key time="{k / 24!r}" value="{(k % 7) * 0.31:.4f}"/>' for k in range(49))  # a zigzag
    held = "".join(f'\n      <key time="{k / 24!r}" value="{k:.1f}" interpolation="hold"/>' for k in range(9))
    doc = tmp_path / "t.scene.xml"
    doc.write_text(f'<scene>\n  <g>\n    <animate property="x">{keys}\n    </animate>\n'
                   f'    <animate property="y">{bent}\n    </animate>\n'
                   f'    <animate property="z">{held}\n    </animate>\n  </g>\n</scene>\n')
    before, after = clip.slim(doc)
    text = doc.read_text()
    x, y, z = (block.split("</animate>")[0] for block in text.split("<animate")[1:])
    assert after < before * 0.75
    assert x.count("<key") == 2 and 'time="0.0"' in x and 'time="2.0"' in x          # a line needs only its ends
    assert y.count("<key") == 14                                                 # the zigzag keeps its 14 corners
    assert z.count("<key") == 9 and z.count("hold") == 9                         # keys that name a curve are untouched
    assert "0.041666666666666664" not in x + y and "\n" in text                  # short times, a line per element
    assert clip.slim(doc)[1] == after                                            # and slimming again changes nothing


def test_slim_leaves_switch_times_alone(tmp_path):
    doc = tmp_path / "s.scene.xml"
    exact = repr(14 / 24)
    doc.write_text(f'<scene>\n  <object3D id="a" start="{exact}" end="{repr(41 / 24)}">\n    <animate property="x">'
                   f'<key time="{exact}" value="1.0"/><key time="{repr(15 / 24)}" value="2.0"/></animate>\n  </object3D>\n</scene>\n')
    clip.slim(doc)
    text = doc.read_text()
    # an object appears on the frame whose time its `start` is exactly (checked on engine 0.8.0): never rounded
    assert f'start="{exact}"' in text and f'end="{repr(41 / 24)}"' in text
