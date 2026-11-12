"""One fixed list of parts for a figure that acts: it is written to the scene once, and its sizes are keyed.

The engine draws a film from objects whose position and rotation are keyed. srlocations writes a figure that way
as long as its parts stay the same ones (their names, classes and materials); when the list changes (a blink puts
a lid on the eye, an open mouth replaces the line) it writes the whole figure again as new objects, and it never
looks at a part's size: between two such changes a body that squashes, an arm that stretches or a mouth that
opens kept the size it had when the list last changed.

`settle(loc, figs, seconds, fps)` looks at each figure on every frame of the film once and gives it a `Fixed`:

- a **slot** for every part the figure shows at any moment. A part that is not showing on a frame stays in the
  list, shrunk to nothing inside the figure's largest part;
- each slot has one surface (the part as it was when first seen) and a **scale** along its own three axes for
  every frame, written as keys on the object (`scaleX`, `scaleY`, `scaleZ`), so sizes change on every frame;
- a part whose surface is not that slot's surface scaled (measured, to within `TOLERANCE` metres) gets a slot of
  its own. A tube's rounded ends are the one thing a scale does not keep: a tube is accepted while its ends would
  be wrong by less than `TUBE_TOLERANCE`.

From then on the figure's parts are those slots (`MascotFigure._parts` asks `Fixed.fit`). A moment the film was
not settled for (other keys added later, another figure state) falls back to the parts as they are drawn, which
is always right and only costs the rewriting. `characters.film.Film.perform()` settles its actors; a scene that
calls `motion.perform()` itself calls `fixed.settle()` after its last key.

The exporter for the other renderer (characters.export) and anything else that wants the parts as drawn asks for
them inside `with fixed.exact():`.
"""
from __future__ import annotations

import math
import re
from contextlib import contextmanager
from dataclasses import fields
from typing import Optional, Sequence

from srlocations.geometry import Vec3

TOLERANCE = 0.001        # m a part's surface may differ from its slot's surface scaled
TUBE_TOLERANCE = 0.004   # m a tube's rounded end may be longer or shorter than its radius
HIDDEN = 0.001           # the scale of a part that is not showing
_U, _V = (0.08, 0.31, 0.58, 0.86), (0.12, 0.5, 0.88)   # where a surface is measured, as shares of its u and v
_ENV = {"sin": lambda d: math.sin(math.radians(d)), "cos": lambda d: math.cos(math.radians(d)), "min": min, "max": max,
        "abs": abs, "pow": pow, "sign": lambda v: (v > 0) - (v < 0)}      # what the engine's surface expressions use
_CODES: dict[str, object] = {}
_NUMBER = re.compile(r"(?<![A-Za-z_])-?\d+(?:\.\d+)?(?:e-?\d+)?")
_EXACT = [0]
_TUBE: list = []


@contextmanager
def exact():
    """Inside it, a settled figure gives its parts as they are drawn (each with its own surface)."""
    _EXACT[0] += 1
    try:
        yield
    finally:
        _EXACT[0] -= 1


def wanted() -> bool:
    return not _EXACT[0]


def _form(expression: str) -> str:
    """An expression with its numbers left out: two parts of one form differ only in sizes."""
    return _NUMBER.sub("#", expression.replace(" ", ""))


def _is_tube(part) -> bool:
    if not _TUBE:
        from .kit import tube
        made = tube("t", Vec3(0, 0, 0), Vec3(0.1, 0, 0), 0.01, 0.008, "m")
        _TUBE.append((_form(made.x), _form(made.y), _form(made.z)))
    return (_form(part.x), _form(part.y), _form(part.z)) == _TUBE[0]


_MEASURED: dict[tuple, list] = {}


def _points(part) -> list[tuple[float, float, float]]:
    """The part's surface at a few fixed places, in its own frame (kept: most parts are the same on most frames)."""
    key = (part.x, part.y, part.z, tuple(part.u), tuple(part.v))
    if key not in _MEASURED:
        if len(_MEASURED) > 20000:
            _MEASURED.clear()
        _MEASURED[key] = _measure(part)
    return _MEASURED[key]


def _measure(part) -> list[tuple[float, float, float]]:
    codes = []
    for expression in (part.x, part.y, part.z):
        if expression not in _CODES:
            _CODES[expression] = compile(expression, "<surface>", "eval")
        codes.append(_CODES[expression])
    out = []
    for fu in _U:
        for fv in _V:
            scope = {**_ENV, "u": part.u[0] + (part.u[1] - part.u[0]) * fu, "v": part.v[0] + (part.v[1] - part.v[0]) * fv}
            out.append(tuple(eval(code, scope) for code in codes))
    return out


def _key(part) -> tuple:
    """What two parts must share to be one object in the scene, apart from where they are and how big."""
    return (part.name, type(part), part.material, tuple(part.samples), tuple(part.closed), tuple(part.u),
            tuple(part.v), part.inward, part.casts_shadow, tuple(part.looks), _form(part.x), _form(part.y),
            _form(part.z))


class Slot:
    """One object of the scene: the surface it is written with, and its scale on each frame of the film."""

    def __init__(self, part) -> None:
        self.part = part
        self.given = {f.name: getattr(part, f.name) for f in fields(part) if f.init}
        self.tube = _is_tube(part)
        self.points = None if self.tube else _points(part)
        self.column: list[tuple[float, float, float]] = []

    def scale(self, part) -> Optional[tuple[float, float, float]]:
        """The scale that makes this slot's surface into `part`'s, or None when no scale does."""
        if self.tube:
            ref, now = self.part.radii, part.radii
            if min(ref) <= 0:
                return None
            s = tuple(round(n / r, 4) for n, r in zip(now, ref))
            ends = max(abs(ref[1] * s[0] - now[1]), abs(ref[2] * s[0] - now[2]))   # an end is as long as the radius
            return s if ends <= TUBE_TOLERANCE else None
        if part.x == self.part.x and part.y == self.part.y and part.z == self.part.z:
            return (1.0, 1.0, 1.0)
        now, s = _points(part), []
        for axis in range(3):
            over = sum(p[axis] * p[axis] for p in self.points)
            s.append(round(sum(p[axis] * q[axis] for p, q in zip(self.points, now)) / over, 4) if over > 1e-12 else 1.0)
        for p, q in zip(self.points, now):
            if any(abs(p[axis] * s[axis] - q[axis]) > TOLERANCE for axis in range(3)):
                return None
        return tuple(s) if min(s) > 0 else None


class _Fitted:
    """Mixed into a part's class when it stands in a slot: it writes its scale, and that scale's keys."""

    def dress(self, element) -> None:
        super().dress(element)
        scale, column, fps = self._scale, self._column, self._fps
        for axis, value in zip("XYZ", scale):
            if value != 1.0:
                setattr(element, f"scale{axis}", value)
        if not column:
            return
        last = len(column) - 1
        for axis, name in enumerate(("scaleX", "scaleY", "scaleZ")):
            values = [each[axis] for each in column]
            if len(set(values)) > 1:
                animate = element.add_animate(property=name)
                for frame, value in enumerate(values):
                    if frame in (0, last) or value != values[frame - 1] or value != values[frame + 1]:
                        animate.add_key(time=frame / fps, value=str(value))


_CLASSES: dict[type, type] = {}


def _fitted(cls: type) -> type:
    if cls not in _CLASSES:
        _CLASSES[cls] = type(cls.__name__, (_Fitted, cls), {"__module__": cls.__module__})
    return _CLASSES[cls]


def _anchor(parts, world) -> tuple[Vec3, tuple]:
    """Where what is not showing is kept, in the figure's frame, and how it is turned: inside the largest part that
    is showing, on a coarse grid of the location and unturned there, so that it is keyed only when the figure has
    gone somewhere else (a body that breathes and sways does not move it)."""
    solid = [p for p in parts if not p.name.startswith("contact/")] or list(parts)    # not the shadow on the floor
    largest = max(solid, key=lambda p: p.radii[0] * p.radii[1] * p.radii[2])
    step = max(0.01, 0.5 * min(largest.radii))                 # the grid's corner nearest the centre is inside it
    centre = world.apply(largest.at)
    kept = Vec3(*(round(value / step) * step for value in centre))
    basis = tuple(tuple(world.basis[row][column] for row in range(3)) for column in range(3))   # the turn, undone
    return world.undo(kept), basis


class Fixed:
    """A figure's slots, in the order its parts were first drawn in."""

    def __init__(self, fps: float) -> None:
        self.fps = fps
        self.slots: list[Slot] = []
        self.by_key: dict[tuple, list[int]] = {}
        self.frames = 0

    def _assign(self, parts, grow: bool) -> Optional[list[tuple[int, tuple]]]:
        """Each part's slot and scale, in the parts' order; None when a part has no slot (and none may be added)."""
        used, out = set(), []
        for part in parts:
            key = _key(part)
            found = None
            for index in self.by_key.get(key, ()):
                if index in used:
                    continue
                s = self.slots[index].scale(part)
                if s is not None:
                    found = (index, s)
                    break
            if found is None:
                if not grow:
                    return None
                self.slots.append(Slot(part))
                self.by_key.setdefault(key, []).append(len(self.slots) - 1)
                found = (len(self.slots) - 1, (1.0, 1.0, 1.0))
            used.add(found[0])
            out.append(found)
        return out

    def see(self, parts) -> None:
        """Takes one more frame of the film: new slots for what it had not seen, and every slot's scale now."""
        now = dict(self._assign(parts, grow=True))
        for index, slot in enumerate(self.slots):
            slot.column += [(HIDDEN,) * 3] * (self.frames - len(slot.column))    # a slot first seen on this frame
            slot.column.append(now.get(index, (HIDDEN,) * 3))
        self.frames += 1

    def fit(self, parts, world) -> list:
        """The figure's parts as its slots: one object for each, here and at this size; the parts themselves when
        this moment has a part the film was not settled with. `world` is where the figure stands in the location."""
        assigned = self._assign(parts, grow=False)
        if assigned is None:
            return list(parts)
        placed = {index: (part, s) for part, (index, s) in zip(parts, assigned)}
        anchor, unturned = _anchor(parts, world)
        out = []
        for index, slot in enumerate(self.slots):
            if index in placed:
                part, s = placed[index]
                here = {"at": part.at, "basis": part.basis, "radii": part.radii}
            else:
                s = (HIDDEN,) * 3
                here = {"at": anchor, "basis": unturned, "radii": tuple(r * HIDDEN for r in slot.part.radii)}
            made = _fitted(type(slot.part))(**{**slot.given, **here})
            made._scale, made._fps = s, self.fps
            made._column = slot.column if s == slot.column[0] else None    # only the film's first frame carries the keys
            out.append(made)
        return out


def settle(loc, figs: Sequence, seconds: float, fps: float) -> dict[str, tuple[int, int]]:
    """Gives each figure its fixed list of parts for the film that `loc`'s keys make in `seconds` at `fps` (see the
    module's text). Call it after the last key. {figure name: (slots, most parts showing at once)}."""
    figs = [f for f in figs if hasattr(f, "fixed")]
    for fig in figs:
        fig.fixed = None
    made = {id(fig): Fixed(fps) for fig in figs}
    most = {id(fig): 0 for fig in figs}
    where = {id(fig): loc.nodes.index(fig) for fig in figs}
    for frame in range(int(round(seconds * fps)) + 1):
        now = loc.at(frame / fps)
        for fig in figs:
            parts = now.nodes[where[id(fig)]].build()
            made[id(fig)].see(parts)
            most[id(fig)] = max(most[id(fig)], len(parts))
    for fig in figs:
        fig.fixed = made[id(fig)]
    return {fig.name: (len(made[id(fig)].slots), most[id(fig)]) for fig in figs}
