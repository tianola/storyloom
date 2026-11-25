"""The graphics tokens: one block in workflow/style.json, read through the style contract.

An episode `look` may replace palette entries and nothing else. Type scale, margins and motion are
house rules; letting a look change them is how two episodes of one series stop looking like it.
"""
from __future__ import annotations

import copy
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workflow.capabilities import resolve_path  # noqa: E402
from workflow.config import style_contract  # noqa: E402

PALETTE_KEYS = ("ink", "paper", "accent", "warm", "cool", "data_a", "data_b", "danger", "mat")
REQUIRED = ("palette", "type", "mobile_floor", "stroke_fraction", "corner_radius_fraction",
            "safe_margin_fraction", "motion", "build_stagger_seconds", "fonts")
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_CACHE = {}


def _block(root: Path):
    """The parsed graphics block, re-read only when style.json changes on disk."""
    path = root / "workflow/style.json"
    stamp = (str(path), path.stat().st_mtime_ns)
    if stamp not in _CACHE:
        _CACHE.clear()
        _CACHE[stamp] = style_contract(root).get("graphics")
    return _CACHE[stamp]


def load_tokens(root=None, overrides=None) -> dict:
    """The graphics block as a plain dict, fonts resolved to absolute paths under `fonts_abs`.

    `overrides` is an episode look: {"palette": {name: "#rrggbb"}}. Any other key, or a palette
    name the block does not define, raises ValueError.
    """
    root = Path(root) if root else ROOT
    block = _block(root)
    if not block:
        raise ValueError(f"{root / 'workflow/style.json'} has no 'graphics' block")
    tokens = copy.deepcopy(block)
    missing = [k for k in REQUIRED if k not in tokens]
    if missing:
        raise ValueError(f"graphics block is missing {missing}")
    for name in PALETTE_KEYS:
        if name not in tokens["palette"]:
            raise ValueError(f"graphics.palette is missing {name!r}")
    if overrides:
        extra = sorted(k for k in overrides if k != "palette")
        if extra:
            raise ValueError(f"a look may override the palette only, not {extra}")
        for name, value in (overrides.get("palette") or {}).items():
            if name not in tokens["palette"]:
                raise ValueError(f"look names palette entry {name!r}, which the tokens do not define")
            if not isinstance(value, str) or not _HEX.match(value):
                raise ValueError(f"palette {name!r} must be a #rrggbb string, got {value!r}")
            tokens["palette"][name] = value
    tokens["fonts_abs"] = {k: str(resolve_path(root, v)) for k, v in tokens["fonts"].items()}
    return tokens
