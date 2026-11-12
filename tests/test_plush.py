"""Smoke tests of the plush family and its SDK: nothing is rendered, so they run in seconds.

    /home/dev/src/viral-video-orchestrator/.venvs/srlocations/bin/python -m pytest characters/tests -q

They build every animal in every pose, play every action on every animal (standing and seated) and build the
figure at moments of the acting, so a change that breaks a drawing, a pose, an action or a keyed field shows here
and not in a render. They do not judge how anything looks.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # the folder that holds characters/
from characters import clip, film, motion, staging  # noqa: E402
from characters.poses import POSES  # noqa: E402

ACTIONS = film.can("bear")["actions"]     # what every character can play (a robot has "screen-icon" besides)
ALIGNMENT = {"characters": list("ola bom dia"),
             "character_start_times_seconds": [0.09 * i for i in range(11)],
             "character_end_times_seconds": [0.09 * i + 0.09 for i in range(11)]}


def drawn(f: film.Film, actor: film.Actor, times) -> int:
    """Builds the actor's figure as the film's keys have it at each time; gives how many parts it drew."""
    track = f.loc.motion[id(actor.fig)]
    parts = 0
    for t in times:
        parts += len(actor.fig.posed(dict(track.at(t))).build())
    return parts


def one(who: str, pose: str = "idle", fps: int = 12) -> tuple[film.Film, film.Actor]:
    f = film.Film("test", size=(320, 320), fps=fps)
    actor = f.add(who, pose)
    f.camera((0, 1, 10), look_at=(0, 0.4, 0), lens=80)
    return f, actor


def test_cast_is_the_plush_family():
    # the plush family (animals and robots) and, since 2026-11-11, the vinyl people beside it
    assert len(film.PLUSH) == 31 and "bear" in film.CAST and "treefrog" in film.CAST and "bip" in film.CAST
    assert set(film.CAST) == set(film.PLUSH) | set(film.PEOPLE)
    for gone in ("dev", "frog", "chick", "mouse"):
        assert gone not in film.CAST
        with pytest.raises(film.FilmError, match="removed from the cast"):
            film.Film("x").add(gone)


def _keys(seed=None, vary=None, acting=None):
    f, actor = one("bear")
    if acting is not None:
        actor.acting(vary=acting)
    actor.do(0.3, "wave", seed=seed, vary=vary).do(2.4, "wave", seed=seed, vary=vary)
    f.perform(4.6)
    track = f.loc.motion[id(actor.fig)]
    return [tuple(sorted((k, round(v, 3)) for k, v in track.at(t / 12).items() if isinstance(v, float)))
            for t in range(55)]


def test_a_seed_varies_an_action_and_repeats():
    plain = _keys()
    assert _keys() == plain and _keys(vary=0.0) == plain          # nothing asked: exactly as written, as before
    assert _keys(seed=3) == _keys(seed=3)                         # the same seed: the same playing
    assert _keys(seed=3) != plain and _keys(seed=3) != _keys(seed=4)
    assert _keys(seed=3, vary=0.0) == plain                       # a seed with no room to vary changes nothing
    varied = _keys(acting=0.15)                                   # the actor's own seed: its two waves differ
    assert varied != plain and varied == _keys(acting=0.15)
    assert varied[4:27] != varied[29:52]


@pytest.mark.parametrize("who", ("bear", "duck", "bip"))
def test_turning_going_and_sitting_down(who):
    f, actor = one(who)
    other = f.add("cat", "idle", at=(-0.9, 0, 0.4))
    actor.look(0.2, other).turn(0.4, 90).do(1.4, "spin").do(3.0, "dance", seconds=2.0, seed=5)
    for i, way in enumerate(("walk", "run", "sneak", "skip")):
        actor.go(5.2 + 3.0 * i, (0.5 if i % 2 == 0 else 0.0, 0.2), style=way, seed=i)
    actor.sit(17.5, "sit-happy").do(18.6, "kick").stand(20.0).do(21.0, "jump").turn(22.0, other)
    f.perform(23.5)
    track = f.loc.motion[id(actor.fig)]
    assert drawn(f, actor, [k * 0.31 for k in range(75)]) > 750
    assert abs(track.at(1.3)["yaw"] - 90.0) < 0.5                       # it turned, and stays turned
    assert abs(track.at(2.9)["yaw"] - 450.0) < 0.5                      # the spin went all the way round
    assert abs(track.at(1.4 + 0.65)["yaw"] - 270.0) < 60.0              # ... through the back
    assert max(track.at(18.6 + k * 0.05).get("hop", 0.0) for k in range(20)) < 0.01   # seated: no jump
    assert max(track.at(21.0 + k * 0.05).get("hop", 0.0) for k in range(22)) > 0.05   # up again: it jumps
    assert "ways" in film.can(who) and "sneak" in film.can(who)["ways"]
    with pytest.raises(film.FilmError, match="no way of going"):
        actor.go(30.0, (0, 0), style="fly")
    with pytest.raises(film.FilmError, match="seated pose"):
        actor.sit(31.0, "idle")


def test_two_together_a_thing_held_and_a_robot_s_screen():
    f = film.Film("test", size=(320, 320), fps=12)
    bear, bunny, bip = f.add("bear", "idle", at=(0.45, 0, 0)), f.add("bunny", "idle", at=(-0.2, 0, 0)), \
        f.add("bip", "idle", at=(-0.95, 0, 0))
    f.camera((0, 1, 10), look_at=(0, 0.4, 0), lens=80)
    f.high_five(0.5, bear, bunny, seed=1).hug(2.4, bear, bunny, seed=2).pat(5.4, bear, bunny, seed=3)
    f.give(8.0, bear, bunny, "gift", seed=4)
    bear.do(10.5, "fall", seed=5)
    bunny.go(11.0, (-0.2, 0.8), style="walk")
    bear.follow(10.9, bunny)
    bip.do(0.4, "glitch", seed=6).do(2.2, "screen-icon", icon="question").power_down(5.0).power_up(8.0)
    f.perform(13.5)
    tracks = {a.who: f.loc.motion[id(a.fig)] for a in (bear, bunny, bip)}
    for actor in (bear, bunny, bip):
        assert drawn(f, actor, [k * 0.29 for k in range(46)]) > 460
    assert tracks["bear"].at(7.9)["item"].endswith(":gift") and tracks["bear"].at(9.2)["item"] == ""   # it changed hands
    assert tracks["bunny"].at(7.9).get("item", "") == "" and tracks["bunny"].at(9.2)["item"].endswith(":gift")
    assert tracks["bear"].at(0.5 + 0.75)["arm_left"] > 1.0 or tracks["bear"].at(0.5 + 0.75)["arm_right"] > 1.0
    assert abs(tracks["bear"].at(13.4)["step_z"] - 0.8) < 0.5 and tracks["bear"].at(13.4)["step_z"] > 0.2   # it followed
    assert tracks["bip"].at(3.0)["icon"] == "question" and tracks["bip"].at(4.6)["icon"] == ""
    assert tracks["bip"].at(7.0)["power"] < 0.05 and tracks["bip"].at(11.0)["power"] > 0.95
    assert min(tracks["bip"].at(0.4 + k * 0.05)["power"] for k in range(28)) < 0.5                  # the glitch
    assert "screen-icon" in film.can("bip")["actions"] and "screen-icon" not in film.can("bear")["actions"]
    with pytest.raises(film.FilmError, match="no screen"):
        bear.power_down(20.0)
    with pytest.raises(film.FilmError, match="cannot"):
        bear.do(20.0, "screen-icon")
    with pytest.raises(film.FilmError, match="nothing called"):
        bear.hold(20.0, "piano")


def test_a_toast_a_drink_and_a_bottle_popped():
    f = film.Film("test", size=(320, 320), fps=12)
    bear, cat, bip = f.add("bear", "idle", at=(0.6, 0, 0)), f.add("cat", "idle", at=(0.0, 0, 0)), \
        f.add("bip", "idle", at=(-0.65, 0, 0))
    f.camera((0, 1, 10), look_at=(0, 0.4, 0), lens=80)
    bip.pop_cork(0.5, seed=1)
    f.toast(3.4, bear, cat, seed=2)
    bear.drink(5.6, seed=3)
    cat.hold(5.0, "mug", "left").drink(6.0)
    f.perform(9.5)
    tracks = {a.who: f.loc.motion[id(a.fig)] for a in (bear, cat, bip)}
    for actor in (bear, cat, bip):
        assert drawn(f, actor, [k * 0.23 for k in range(41)]) > 410
    assert tracks["bip"].at(0.4)["item"].endswith(":bottle") and tracks["bip"].at(3.2)["item"].endswith(":bottle-open")
    assert 0.2 < tracks["bip"].at(0.5 + 2.4 * 0.7)["pop"] < 0.8 and tracks["bip"].at(3.2)["pop"] == 0.0
    assert tracks["bear"].at(1.0)["item"].endswith(":glass") and tracks["cat"].at(5.5)["item"] == "left:mug"
    assert max(tracks["bear"].at(5.6 + k * 0.1)["item_tilt"] for k in range(26)) > 40          # the glass tips
    assert tracks["bear"].at(9.0)["item_tilt"] == 0.0
    with pytest.raises(film.FilmError, match="two or more"):
        f.toast(20.0, bear)
    with pytest.raises(film.FilmError, match="not a drink"):
        bear.drink(20.5, "gift") if bear.holds.clear() is None else None


@pytest.mark.parametrize("who", film.CAST)
def test_every_pose_builds(who):
    assert len(POSES[who]) >= 16
    for pose in POSES[who]:
        f, actor = one(who, pose)
        assert len(actor.fig.build()) > 10, f"{who} {pose} draws almost nothing"


@pytest.mark.parametrize("who", film.CAST)
def test_every_action_plays(who):
    for start_pose in ("idle", "sit"):
        # a dozen actions a film: the engine sorts a figure's keys again on every key, so one long film of
        # them all costs the square of its length
        mine = [a for a in ACTIONS if a in film.can(who)["actions"]]      # a vinyl person has no paw actions
        for first in range(0, len(mine), 12):
            batch = mine[first:first + 12]
            f, actor = one(who, start_pose)
            for i, action in enumerate(batch):
                actor.do(0.3 + 2.2 * i, action, side="left" if (first + i) % 2 else "right")
            seconds = 0.3 + 2.2 * len(batch)
            f.perform(seconds)
            times = [k * 0.37 for k in range(int(seconds / 0.37))]
            assert drawn(f, actor, times) > 10 * len(times)


@pytest.mark.parametrize("who", ("bear", "bunny", "fennec", "axolotl", "duck", "treefrog"))
def test_poses_gaze_travel_and_talk(who):
    f, actor = one(who, "idle", fps=24)
    other = f.add("cat", "sit", at=(-0.8, 0, 0))
    actor.look(0.3, other).pose(1.0, "cheerful").pose(2.0, "worried").look(2.5, (2.0, 1.5, 3.0)).look(3.2, None)
    actor.go(3.5, (0.6, 0.3)).go(5.6, (0.0, 0.0), style="hops").say(ALIGNMENT, at=6.2)
    f.perform(9.0)
    assert drawn(f, actor, [k * 0.21 for k in range(42)]) > 420
    track = f.loc.motion[id(actor.fig)]
    assert abs(track.at(5.5)["step_x"] - 0.6) < 0.02 and abs(track.at(5.5)["step_z"] - 0.3) < 0.02   # it arrived
    assert abs(track.at(8.9)["step_x"]) < 0.02                                                       # and came back
    assert max(track.at(5.6 + k * 0.02).get("hop", 0.0) for k in range(60)) > 0.02                   # off the ground
    assert any(track.at(6.2 + k / 24).get("mouth_open", 1.0) < 0.9 for k in range(30))               # the mouth works


def test_a_trip_cannot_start_before_the_last_one_ends():
    f, actor = one("bear")
    actor.go(1.0, (0.6, 0.3)).go(1.5, (0.0, 0.0))
    with pytest.raises(film.FilmError, match="before it has arrived"):
        f.perform(5.0)


def test_jump_leaves_the_ground_and_seated_does_not():
    f, actor = one("bear")
    actor.do(0.5, "jump")
    f.perform(2.5)
    track = f.loc.motion[id(actor.fig)]
    assert max(track.at(0.5 + k * 0.04)["hop"] for k in range(30)) > 0.12
    f, actor = one("bear", "sit")
    actor.do(0.5, "jump")
    f.perform(2.5)
    track = f.loc.motion[id(actor.fig)]
    assert max(track.at(0.5 + k * 0.04)["hop"] for k in range(30)) == 0.0


def test_heads_together_never_merge():
    f = film.Film("pair", size=(320, 320), fps=12)
    a = f.add("bear", "sit-cuddle", at=(0.27, 0, 0), lean=7)
    b = f.add("bunny", "sit-chat", at=(-0.27, 0, 0), lean=-7)
    f.together(a, b).camera((0, 1, 10), look_at=(0, 0.4, 0))
    a.look(0.5, b).do(1.0, "giggle").do(2.5, "shy")
    b.look(0.4, a).do(1.4, "nod").do(2.6, "wave", side="left")
    f.perform(5.0)
    assert staging.merged_in_motion(f.loc, [a.fig, b.fig], 12) == []


def test_overlapping_heads_are_refused():
    f = film.Film("clash", size=(320, 320))
    f.add("bear", at=(0.05, 0, 0))
    f.add("cat", at=(-0.05, 0, 0))
    f.camera((0, 1, 10), look_at=(0, 0.4, 0))
    with pytest.raises(film.FilmError, match="heads overlap"):
        f.perform(1.0)


def test_mistakes_say_what_there_is():
    f, actor = one("bear")
    for call, said in ((lambda: f.add("unicorn"), "no character"), (lambda: f.add("pig", "fly"), "has no pose"),
                       (lambda: actor.do(1, "moonwalk"), "cannot"), (lambda: actor.pose(1, "fly"), "has no pose"),
                       (lambda: actor.go(1, (0, 1), style="fly"), "no way of going"),
                       (lambda: f.add("bear"), "already"), (lambda: f.render("x.mp4"), "how long")):
        with pytest.raises(film.FilmError, match=said):
            call()
    with pytest.raises(film.FilmError, match="no camera"):
        g = film.Film("x")
        g.add("bear")
        g.perform(1.0)


def test_capabilities_are_the_same_for_the_whole_family():
    first = film.can("bear")
    for who in film.PLUSH:                 # the vinyl people have their own, smaller, set
        got = film.can(who)
        screen = set(getattr(film, "SCREEN_ONLY", ()))            # what only a robot's screen can play
        assert set(got["actions"]) - screen == set(first["actions"]) and got["moves"] == first["moves"]
        assert {"idle", "sit", "sit-happy", "sit-sleep"} <= set(got["poses"])
    assert set(first["actions"]) == (set(motion.ACTIONS) | set(motion.PAW_ACTIONS)) - set(getattr(film, "SCREEN_ONLY", ()))


def test_bodies_that_run_into_each_other_are_refused():
    def two(**options):
        f = film.Film("bodies", size=(320, 320), fps=12, **options)
        a = f.add("bear", at=(0.25, 0, 0))
        b = f.add("cat", at=(-0.25, 0, 0))         # heads clear of each other; paws that meet when both cheer
        f.camera((0, 1, 10), look_at=(0, 0.4, 0))
        a.do(0.3, "cheer")
        b.do(0.3, "cheer")
        return f

    with pytest.raises(film.FilmError, match="runs into another"):
        two(overlap=0.005).perform(2.5)            # a film that allows almost no contact refuses them
    f = two()
    f.perform(2.5)                                 # the default lets neighbours' paws cross, and says where
    assert f.contacts and all(depth <= f.overlap for *_names, depth, _when in f.contacts)


def test_it_lies_down_gets_up_and_wakes():
    from characters import mascots3d as m
    f = film.Film("lying", size=(320, 180), fps=12)
    bear = f.add("bear", "sit-sleep", at=(0.0, 0, 0))
    f.camera((0, 0.75, 9.0), look_at=(0, 0.42, 0), lens=110)
    bear.wake_up(0.5).stand(4.0).lie_down(5.0, "right").get_up(7.0)
    f.perform(9.0)
    track = f.loc.motion[id(bear.fig)]
    awake = track.at(3.5)["expression"]
    assert awake.eyes == "normal" and "sit" in awake.extras               # awake, and still on its seat
    lying = bear.fig.posed(dict(track.at(6.5)))
    assert abs(lying.roll) > 80 and lying.hop > 0.05                      # over on its side, resting on the ground
    shade = [p for p in lying.build() if isinstance(p, m.Contact)]
    assert shade and all(abs(lying.transform.apply(p.at).y) < 0.01 for p in shade)   # its shadow flat on the ground
    up = bear.fig.posed(dict(track.at(8.9)))
    assert abs(up.roll) < 1 and up.hop < 0.01
    high = [m.figure("bear", "idle", name="j").frames()["hips"].position.y]
    from dataclasses import replace as _replace
    high.append(_replace(m.figure("bear", "idle", name="j"), hop=0.25).frames()["hips"].position.y)
    assert abs(high[0] - high[1]) < 1e-6                                  # a jump lifts the figure once, not twice


def test_more_ways_of_going():
    f, actor = one("bear")
    ways = ("tiptoe", "march", "stagger", "trip", "slide-stop", "back-away", "moonwalk", "leap")
    for i, way in enumerate(ways):
        actor.go(1.0 + 4.0 * i, (0.6 if i % 2 == 0 else 0.0, 0.0), style=way, seed=i)
    late = 1.0 + 4.0 * len(ways)
    actor.go(late, (0.7, 0.0), style="cartwheel").climb(late + 3.0, (0.7, -0.3), rise=0.12)
    actor.climb(late + 6.0, (0.7, 0.0), rise=-0.12)
    f.perform(late + 9.0)
    track = f.loc.motion[id(actor.fig)]
    assert all(way in film.can("bear")["ways"] for way in (*ways, "cartwheel", "climb-step"))
    assert drawn(f, actor, [k * 0.37 for k in range(int((late + 9.0) / 0.37))]) > 900
    for i, way in enumerate(ways):                                       # each one arrives
        assert abs(track.at(1.0 + 4.0 * i + 3.9)["step_x"] - (0.6 if i % 2 == 0 else 0.0)) < 1e-6, way
    back = 1.0 + 4.0 * ways.index("back-away")
    assert max(abs(track.at(back + k * 0.1)["yaw"]) for k in range(30)) < 0.5       # backwards: it does not turn
    assert max(abs(track.at(1.0 + k * 0.1)["yaw"]) for k in range(20)) > 30.0       # forwards: it does
    leap = 1.0 + 4.0 * ways.index("leap")
    assert max(track.at(leap + k * 0.05)["hop"] for k in range(22)) > 0.2
    rolls = [track.at(late + k * 0.05)["roll"] for k in range(31)]
    assert min(rolls) < -350.0 and abs(track.at(late + 1.6)["roll"]) < 0.5           # all the way over, and up
    over = min(range(31), key=lambda k: abs(rolls[k] + 180.0))
    assert track.at(late + over * 0.05)["hop"] > 0.5                    # on its head: lifted, not in the ground
    assert abs(track.at(late + 5.0)["step_y"] - 0.12) < 1e-6            # up on the step, and it stays there
    assert abs(track.at(late + 8.5)["step_y"]) < 1e-6                   # ... until it steps down
    up = actor.fig.posed(dict(track.at(late + 5.0)))
    assert abs(up.transform.position.y - 0.12) < 0.02
