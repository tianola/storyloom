import json
import os
from collections.abc import Mapping
from pathlib import Path

EPISODE_PHASES = ("research", "story", "script", "assets", "vo", "motion", "edit", "qc", "dist")


def blender_executable(repo_root: Path, environ: Mapping[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    override = env.get("BLENDER_EXE")
    if override:
        return Path(override)

    config_path = repo_root / "workflow/blender.json"
    if config_path.exists():
        production = json.loads(config_path.read_text(encoding="utf-8"))["production"]
        return repo_root / production

    return repo_root / "tools/blender-4.1.0-windows-x64/blender.exe"


REQUIRED_STYLE_KEYS = ("palette", "materials", "lighting", "camera", "transition",
                       "scene_template", "rhythm", "canvas", "audio", "qc", "voice", "cadence",
                       # The archival layer is part of the house style from here on, for every
                       # episode. Left out, a call site that reads contract["archive"] only fails
                       # when it happens to run, and the episode that ships is silently 3D-only.
                       "archive")


PATTERNS_FILENAME = "patterns.json"
REQUIRED_PATTERN_KEYS = ("context", "task", "rules", "output", "input")
PATTERN_IDS = ("photo-teardown", "product-viewer", "how-it-works", "data-city", "print-maker", "mini-world")


def pattern_library(repo_root: Path) -> dict:
    """The six presentation patterns as data, for whoever writes the next beat brief.

    They arrived as a screenshot, which is a rule nobody can read twice. Each pattern
    carries the obligation it implies for an episode, so a beat about a mechanism has
    to open the mechanism the way the pattern says, not only show its outside.
    """
    path = repo_root / "workflow" / PATTERNS_FILENAME
    library = json.loads(path.read_text(encoding="utf-8"))
    patterns = library.get("patterns", [])
    ids = [p.get("id") for p in patterns]
    missing_ids = [pid for pid in PATTERN_IDS if pid not in ids]
    if missing_ids:
        raise ValueError(f"{path} is missing patterns {missing_ids}")
    for pattern in patterns:
        absent = [key for key in REQUIRED_PATTERN_KEYS if not str(pattern.get(key, "")).strip()]
        if absent:
            raise ValueError(f"pattern {pattern.get('id')} is missing {absent} in {path}")
    return library


def style_contract(repo_root: Path) -> dict:
    """The house style as data, for a beat builder to read before it places anything.

    Artemis II relit eighteen beats because the lighting rule existed only in whoever had
    written the last one. A builder that reads this file cannot repeat that mistake, and
    `python/test_style_contract.py` fails if the file and `techniques/lighting.py` drift.
    """
    path = repo_root / "workflow/style.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    missing = [key for key in REQUIRED_STYLE_KEYS if key not in contract]
    if missing:
        raise ValueError(f"{path} is missing {missing}")
    return contract
