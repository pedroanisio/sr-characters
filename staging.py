"""Placing the 3D cast together: heads that touch never run into each other.

A plush head is a big ellipsoid, so two figures leaning together merge into one blob as soon as their heads overlap
(the ink then outlines them as one shape). `nuzzle()` slides one figure sideways until the two heads just touch;
`merged()` lists the pairs in a group whose heads still overlap, for a scene to check before it renders.

    a = loc.add(m.figure("bear", "sit-cuddle", name="bear", at=(0.3, 0, 0), roll=-6))
    b = loc.add(m.figure("bunny", "sit-chat", name="bunny", at=(-0.3, 0, 0), roll=6))
    staging.nuzzle(a, b)                 # b moves along x until its head rests against a's
    assert not staging.merged([a, b])
"""

from __future__ import annotations

import math
from itertools import combinations
from typing import Sequence

from srlocations.geometry import Vec3

_DIRS = [(math.sin(v) * math.cos(u), math.cos(v), math.sin(v) * math.sin(u))
         for v in (math.pi * (j + 0.5) / 14 for j in range(14)) for u in (2 * math.pi * i / 24 for i in range(24))]


def head(fig):
    """The figure's head as (its transform in the world, its radii). The head is the part "head/head", or the body
    of a mascot whose face is on its body."""
    parts = {p.name: p for p in fig.parts()}
    part = parts.get("head/head") or parts["body/body"]
    return fig.transform.then(part.transform), tuple(part.radii)


def depth(a, b, gap: float = 0.0) -> float:
    """How far a's and b's heads overlap: above 0 they run into each other (0.1 = a tenth of a radius deep), with
    each head taken `gap` metres bigger than it is."""
    (ta, ra), (tb, rb) = head(a), head(b)
    worst = -1.0
    for (t0, r0), (t1, r1) in (((ta, ra), (tb, rb)), ((tb, rb), (ta, ra))):
        grown = [r + gap for r in r1]
        for d in _DIRS:
            q = tuple(t1.undo(t0.apply(Vec3(d[0] * (r0[0] + gap), d[1] * (r0[1] + gap), d[2] * (r0[2] + gap)))))
            worst = max(worst, 1.0 - math.sqrt(sum((q[i] / grown[i]) ** 2 for i in range(3))))
    return worst


def nuzzle(a, b, gap: float = 0.004, axis: Sequence[float] = (1.0, 0.0, 0.0)) -> float:
    """Moves `b` along `axis` (x by default), away from or toward `a`, until their heads just touch with `gap` metres
    between them. Gives how far it moved. `a` stays where it is."""
    ax, start, origin = tuple(Vec3.of(axis)), tuple(Vec3.of(b.at)), tuple(Vec3.of(a.at))
    side = 1.0 if sum((start[i] - origin[i]) * ax[i] for i in range(3)) >= 0 else -1.0

    def put(shift: float) -> None:
        b.at = tuple(start[i] + side * shift * ax[i] for i in range(3))

    low, high = -2.0, 2.0          # shift toward a (they overlap) .. away from a (they are apart)
    put(high)
    if depth(a, b, gap / 2) > 0:
        raise ValueError("these heads overlap however far apart along that axis")
    for _ in range(40):
        middle = (low + high) / 2
        put(middle)
        if depth(a, b, gap / 2) > 0:
            low = middle
        else:
            high = middle
    put(high)
    return side * high


def merged(figs: Sequence, gap: float = 0.0) -> list[tuple[str, str, float]]:
    """The pairs of figures whose heads overlap: (name, name, how deep). Empty when every head is clear."""
    return [(a.name, b.name, round(depth(a, b, gap), 3)) for a, b in combinations(figs, 2) if depth(a, b, gap) > 0]


def _at(loc, fig, time: float):
    """The figure as the location's keys have it at `time`."""
    track = loc.motion.get(id(fig))
    return fig.posed({k: v for k, v in track.at(time).items() if k in ("pose", "at", "yaw", "roll", "squash", "hop", "step_x", "step_y", "step_z")}) if track else fig


def merged_in_motion(loc, figs: Sequence, fps: float = 12, gap: float = 0.0) -> list[tuple[str, str, float, float]]:
    """The pairs whose heads overlap at any moment of the location's motion: (name, name, deepest, when). Acting
    turns and tilts heads, so two heads that only touch in the still can run into each other in the clip."""
    end = max((loc.motion[id(f)].end for f in figs if id(f) in loc.motion), default=0.0)
    worst: dict[tuple[str, str], tuple[float, float]] = {}
    for k in range(int(end * fps) + 1):
        t = k / fps
        now = [_at(loc, f, t) for f in figs]
        for a, b in combinations(now, 2):
            if sum((x - y) ** 2 for x, y in zip(tuple(Vec3.of(a.at)), tuple(Vec3.of(b.at)))) > 1.0:
                continue                                      # more than a metre apart: their heads cannot meet
            d = depth(a, b, gap)
            if d > 0 and d > worst.get((a.name, b.name), (0.0, 0.0))[0]:
                worst[(a.name, b.name)] = (d, t)
    return [(a, b, round(d, 3), round(t, 2)) for (a, b), (d, t) in worst.items()]


def clear_in_motion(loc, a, b, fps: float = 12, gap: float = 0.004, step: float = 0.008,
                    axis: Sequence[float] = (1.0, 0.0, 0.0)) -> float:
    """Moves `b` away from `a` along `axis`, a little at a time, until their heads never overlap during the
    location's motion (call it after motion.perform()). Gives how far it moved."""
    ax, origin = tuple(Vec3.of(axis)), tuple(Vec3.of(a.at))
    start = tuple(Vec3.of(b.at))
    side = 1.0 if sum((start[i] - origin[i]) * ax[i] for i in range(3)) >= 0 else -1.0
    moved = 0.0
    while merged_in_motion(loc, [a, b], fps, gap):
        moved += step
        if moved > 0.5:
            raise ValueError("these heads still overlap half a metre further apart")
        b.at = tuple(start[i] + side * moved * ax[i] for i in range(3))
    return side * moved


# ----------------------------------------------------------------------------- whole bodies (srlocations.collision)
def body_clash(a, b, allow: float = 0.0):
    """Where two figures' bodies run deepest into each other, beyond `allow` metres: (a's part, b's part, depth in
    m), or None when they are clear. Every part counts (ears, paws, tails, feet), as the convex shape srlocations
    gives it, which is a little bigger than a round part: two heads that just touch read as 1 to 2 cm deep."""
    from srlocations.collision import Body, deepest
    first, second = Body.of(a), Body.of(b)
    if first is None or second is None:
        return None
    clash = deepest(first, second, allow=allow)
    return None if clash is None else (clash.first.split("/", 1)[-1], clash.second.split("/", 1)[-1], clash.depth)


def bodies(figs: Sequence, allow: float = 0.02) -> list[tuple[str, str, str, str, float]]:
    """The pairs of figures whose bodies overlap by more than `allow`: (name, part, name, part, depth in m)."""
    out = []
    for a, b in combinations(figs, 2):
        clash = body_clash(a, b, allow)
        if clash:
            out.append((a.name, clash[0], b.name, clash[1], round(clash[2], 3)))
    return out


def bodies_in_motion(loc, figs: Sequence, fps: float = 6, allow: float = 0.02) -> list[tuple[str, str, str, str, float, float]]:
    """The pairs whose bodies overlap by more than `allow` at any moment of the location's motion, each at its
    worst: (name, part, name, part, depth in m, when in s). Sampled `fps` times a second (a figure crossing
    another takes far longer than a sixth of a second)."""
    from srlocations.collision import Body, deepest
    if len(figs) < 2:
        return []
    end = max((loc.motion[id(f)].end for f in figs if id(f) in loc.motion), default=0.0)
    worst: dict[tuple[str, str], tuple] = {}
    for k in range(int(end * fps) + 1):
        t = k / fps
        now = []
        for f in figs:
            track = loc.motion.get(id(f))
            posed = f.posed(dict(track.at(t))) if track else f
            now.append((f.name, Body.of(posed)))
        for (na, a), (nb, b) in combinations(now, 2):
            if a is None or b is None:
                continue
            clash = deepest(a, b, allow=allow)
            if clash and clash.depth > worst.get((na, nb), (0, 0, 0, 0, 0.0))[4]:
                worst[(na, nb)] = (na, clash.first.split("/", 1)[-1], nb, clash.second.split("/", 1)[-1],
                                   round(clash.depth, 3), round(t, 2))
    return sorted(worst.values(), key=lambda c: -c[4])

