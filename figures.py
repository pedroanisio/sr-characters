"""The base figure every family stands on, under a name that says so.

`MascotFigure` (a figure on the mannequin skeleton with an expression and the keyable channels the acting drives),
`Spec`, `SPECS`, `BUILDERS`, `WHOLE`, `figure()`, `gesture()`, `controls()`, `Carry`, `Contact`, `cast_stage()`.

The code is still in `mascots3d.py` (the file was the three old mascots' models; they were removed on 2026-11-11
and the base figure stayed). It has not been moved yet because other sessions are editing that file; this module is
the name to import in new code, and will hold the code once it can be moved.
"""
from .mascots3d import *  # noqa: F401,F403
from .mascots3d import _stage  # noqa: F401
