"""The tests run from any folder, and the long ones are marked `slow` (leave them out with -m "not slow")."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # the folder that holds characters/
sys.path.insert(0, str(Path(__file__).resolve().parent))       # helpers.py

SLOW = ("test_every_pose_builds", "test_every_action_plays", "test_turning_going_and_sitting_down",
        "test_poses_gaze_travel_and_talk", "test_two_together_a_thing_held_and_a_robot_s_screen",
        "test_a_seed_varies_an_action_and_repeats")


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: plays every action or pose of the whole cast; minutes, not seconds")
    config.addinivalue_line("markers", "looks: renders a reference still again and compares it (test_looks.py); "
                                       "the Blender stills only run with -m looks or LOOKS=1")


def pytest_collection_modifyitems(items):
    for item in items:
        if item.originalname in SLOW or item.name.split("[")[0] in SLOW:
            item.add_marker(pytest.mark.slow)
