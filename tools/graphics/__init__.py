"""Project-wide 2D graphics: tokens, a primitive contract, and one family module per kind of card.

    from tools.graphics import get, PRIMITIVES
    frames = get("tally").render(spec, seconds=3, canvas=(1920, 1080), fps=30)   # a generator

`PRIMITIVES` maps a primitive name to a module-like object exposing `render`, `frame_at`, `SCHEMA`
and `OVERLAY`. Several primitives share a family module (stats.py holds four), so the registry value
is the Primitive object each family builds, which is what a module would expose if there were one
per name. See docs/graphics.md.
"""
from . import archive, boards, grids, labels, maps, split, stats, timelines
from .presets import PRESETS, get_preset

_FAMILIES = [stats, grids, timelines, maps, boards, split, archive, labels]
PRIMITIVES = {}
OVERLAY = set()
for _m in _FAMILIES:
    PRIMITIVES.update(_m.PRIMITIVES)
    OVERLAY |= set(_m.OVERLAY)


def get(name):
    try:
        return PRIMITIVES[name]
    except KeyError:
        raise KeyError(f"no graphics primitive {name!r}; known: {sorted(PRIMITIVES)}") from None
