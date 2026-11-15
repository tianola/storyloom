import json
import re
import shutil
from pathlib import Path

from workflow.archive import paths as archive_paths
from workflow.capabilities import (
    CAPABILITIES_FILENAME, format_findings, preflight, required_failures,
)
from workflow.config import (
    EPISODE_PHASES, PATTERNS_FILENAME, pattern_library, style_contract,
)
from workflow.episode import rollout_seed
from workflow.skills import SKILLS_MAP_FILENAME, skills_map

SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
PHASES = EPISODE_PHASES
TEMPLATES = {"sources.md": "research", "beat-sheet.md": "story", "narration.md": "script"}
COPIED = (PATTERNS_FILENAME, SKILLS_MAP_FILENAME, CAPABILITIES_FILENAME)


def init_episode(root: Path, slug: str, title: str, *, host=None) -> Path:
    if not SLUG.fullmatch(slug):
        raise ValueError("slug must be lowercase kebab-case")
    if not title.strip():
        raise ValueError("title is required")
    repo_root = Path(__file__).resolve().parents[1]
    # Validated before the directory exists: an episode built against a half-written
    # pattern library or a skill map naming tools that are not installed would carry
    # the gap into every beat brief made from it.
    pattern_library(repo_root)
    skills_map(repo_root)
    # The archival layer is seeded from the contract's own paths, so a renamed archival file
    # moves the seed with it instead of leaving the validator reading a name nobody wrote.
    archival = archive_paths(style_contract(repo_root))
    # And so would a machine that cannot run the stages. A build is hours long and the
    # cost of discovering a missing binary at the encode is the whole of it, so the
    # preflight is a stop, not a warning: no directory, no episode, nothing to salvage.
    failures = required_failures(preflight(repo_root, host=host))
    if failures:
        raise ValueError("preflight refused this episode - required capabilities unavailable: "
                         + ", ".join(sorted({finding.capability for finding in failures}))
                         + "\n" + format_findings(failures))
    episode = Path(root) / slug
    episode.mkdir(parents=True, exist_ok=False)
    for phase in PHASES:
        (episode / phase).mkdir()
    for filename in COPIED:
        shutil.copyfile(repo_root / "workflow" / filename, episode / filename)
    (episode / "episode.json").write_text(json.dumps({
        "slug": slug, "title": title.strip(), "language": "English",
        "workflow_version": 3, "duration_target_seconds": [600, 900],
        "archive": {"enabled": True},
        # Declared empty rather than guessed: the three values name the script that draws this film's
        # beats, the luma table its QC compares against and the beats a bare `finish` re-cuts, and a
        # seed copying them from the last episode would render that film into this one. The queue
        # refuses the empty state by key, so the author is told to fill them in.
        "rollout": rollout_seed()
    }, indent=2) + "\n", encoding="utf-8")
    (episode / "assets/license-manifest.json").write_text("[]\n", encoding="utf-8")
    # Two empty files rather than none. An episode that has not chosen its archival shots yet
    # and an episode whose record file went missing are different states, and only a file on
    # disk tells them apart; the mix rule reads the first as a finding and the second as a gap.
    (episode / archival["records_filename"]).write_text("{}\n", encoding="utf-8")
    ledger_path = episode / archival["ledger_filename"]
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text("[]\n", encoding="utf-8")
    template_root = Path(__file__).with_name("templates")
    for filename, phase in TEMPLATES.items():
        shutil.copyfile(template_root / filename, episode / phase / filename)
    return episode


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Initialize a documentary episode workflow.")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--title", required=True)
    args = parser.parse_args()
    init_episode(args.root, args.slug, args.title)
