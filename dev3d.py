"""The old name of `characters.kit` (this file was Dev's model; Dev was removed on 2026-11-11 and the drawing kit
moved to `kit.py`). Everything is imported from there, under the old private names too, so nothing that says
`from .dev3d import ...` or `dev3d.finish(...)` changes. New code imports `characters.kit`."""
from .kit import *  # noqa: F401,F403
from .kit import _basis, _cross, _grid, _n, _scaled, _unit  # noqa: F401
