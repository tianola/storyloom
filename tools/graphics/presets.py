"""Named full-frame graphics an episode asks for by name: preset -> (primitive, spec)."""
from __future__ import annotations

import copy


def _ratio_1846():
    return "ratio_compare", {
        "a": {"value": "1 in 9", "label": "First Clinic"},
        "b": {"value": "1 in 36", "label": "Second Clinic"},
        "about": True,
        "source": "1846 · Semmelweis 1861",
        "build": {"a": [0.0, 0.5], "b": [0.9, 0.5]},
    }


def _ward_plan_routes():
    """A long ward, beds down both side walls, the old route up the aisle, a quieter one by the wall."""
    rooms = [{"rect": [0.0, 0.04, 1.0, 0.96]}]
    count, width, pitch = 14, 0.05, 0.0675
    for i in range(count):
        x = 0.05 + i * pitch
        rooms.append({"rect": [x, 0.09, x + width, 0.30], "minor": True})
        rooms.append({"rect": [x, 0.62, x + width, 0.83], "minor": True})
    return "map_plan", {
        "schematic": True,
        "rooms": rooms,
        "routes": [
            {"label": "old route", "color": "danger", "build": [0.3, 2.4],
             "points": [[0.03, 0.46], [0.97, 0.46]]},
            {"label": "quieter route", "color": "cool", "build": [3.0, 2.4],
             "points": [[0.03, 0.46], [0.03, 0.9], [0.97, 0.9]]},
        ],
    }


def _tally_clinics():
    return "tally", {
        "left": {"label": "First Clinic", "marks": 11, "per": 100},
        "right": {"label": "Second Clinic", "marks": 3, "per": 100},
        "build": {"left": [0.15, 0.7], "right": [0.5, 0.35]},
        "source": "1846 · Semmelweis 1861",
        "type": {"label": 0.06, "number": 0.1},
    }


_BUILDERS = {"ratio-1846": _ratio_1846, "ward-plan-routes": _ward_plan_routes,
             "tally-clinics": _tally_clinics}
PRESETS = {name: fn() for name, fn in _BUILDERS.items()}


def get_preset(name):
    """(primitive_name, spec) for a preset; the spec is a fresh copy you may edit."""
    if name not in PRESETS:
        raise KeyError(f"no graphics preset {name!r}; known: {sorted(PRESETS)}")
    prim, spec = PRESETS[name]
    return prim, copy.deepcopy(spec)
