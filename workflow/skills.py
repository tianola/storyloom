"""The skill map: which installed skills answer which phase of an episode.

Twelve GitHub media repos were staged for this pipeline, and the user asked that the
workflow read them on every run «ώστε να είμαστε σίγουροι ότι θα λειτουργούν». Reading
a list is not proof, so this loader resolves every name it reads against the filesystem
and refuses the run when a skill the map depends on is not there.
"""

import json
from pathlib import Path

from workflow.config import EPISODE_PHASES

SKILLS_MAP_FILENAME = "skills.json"
REQUIRED_MAP_KEYS = ("name", "status", "provenance", "router", "phases", "rules",
                     "installed_unmapped")
REQUIRED_ENTRY_KEYS = ("skill", "origin", "use", "provides")
REQUIRED_PHASE_KEYS = ("note", "skills")
ORIGINS = ("vendor", "machine", "catalog")
USES = ("direct", "method-only")
SKILLS_ROOT = Path.home() / ".qoder" / "skills"
VENDOR_INDEX = Path.home() / ".qoder" / "skills-vendor" / "index.json"


def vendor_index(path: Path) -> dict:
    if not path.is_file():
        raise ValueError(
            f"{path} is missing - the router has nothing to search. "
            "Rebuild it with: python sync.py in ~/.qoder/skills-vendor")
    return {row["skill"]: row for row in json.loads(path.read_text(encoding="utf-8"))}


def skills_map(repo_root: Path, *, skills_root: Path | None = None,
               vendor_index_path: Path | None = None) -> dict:
    """The map, validated - every skill it names is reachable right now.

    `skills_root` and `vendor_index_path` exist so a test can prove the loader rejects a
    phantom skill without uninstalling anything real.
    """
    path = repo_root / "workflow" / SKILLS_MAP_FILENAME
    mapping = json.loads(path.read_text(encoding="utf-8"))

    missing = [key for key in REQUIRED_MAP_KEYS if not mapping.get(key)]
    if missing:
        raise ValueError(f"{path} is missing {missing}")
    absent_phases = [phase for phase in EPISODE_PHASES if phase not in mapping["phases"]]
    if absent_phases:
        raise ValueError(f"{path} has no entry for episode phase(s) {absent_phases}")

    root = SKILLS_ROOT if skills_root is None else Path(skills_root)
    index_path = VENDOR_INDEX if vendor_index_path is None else Path(vendor_index_path)
    catalog = None
    for phase, entry in mapping["phases"].items():
        absent = [key for key in REQUIRED_PHASE_KEYS if key not in entry]
        if absent:
            raise ValueError(f"{path}: phase {phase} is missing {absent}")
        for skill in entry["skills"]:
            _check_entry(skill, phase, path, root)
            if skill["origin"] == "catalog":
                catalog = vendor_index(index_path) if catalog is None else catalog
                _check_catalog_entry(skill, phase, catalog)

    script = Path(mapping["router"]["script"]).expanduser()
    if not script.is_file():
        raise ValueError(f"{path}: the router advertises {script}, which does not exist. "
                         "Reinstall the gh-media-catalog skill or fix the map.")
    return mapping


def _check_entry(skill: dict, phase: str, path: Path, root: Path) -> None:
    absent = [key for key in REQUIRED_ENTRY_KEYS if not str(skill.get(key, "")).strip()]
    if absent:
        raise ValueError(f"{path}: {phase}:{skill.get('skill')} is missing {absent}")
    origin = skill["origin"]
    if origin not in ORIGINS:
        raise ValueError(f"{path}: {phase}:{skill['skill']} has origin {origin!r}, "
                         f"expected one of {ORIGINS}")
    if skill["use"] not in USES:
        raise ValueError(f"{path}: {phase}:{skill['skill']} has use {skill['use']!r}, "
                         f"expected one of {USES}")
    if origin == "catalog":
        return
    installed = root / skill["skill"] / "SKILL.md"
    if not installed.is_file():
        raise ValueError(f"{path}: {phase} names {skill['skill']} ({origin}) but "
                         f"{installed} is not installed. Promote it with "
                         "python sync.py in ~/.qoder/skills-vendor.")


def _check_catalog_entry(skill: dict, phase: str, catalog: dict) -> None:
    row = catalog.get(skill["skill"])
    if row is None:
        raise ValueError(f"{phase}: {skill['skill']} is a catalog pointer but the vendor "
                         "index has no such skill - search.py --show would fail too.")
    if row["promoted"]:
        raise ValueError(f"{phase}: {skill['skill']} is written as catalog but it is "
                         "installed; give it origin vendor or drop the pointer.")
