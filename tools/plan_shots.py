"""Shot list: which narration line plays over which beat or archive shot -> `<episode>/shots.json`.

    python tools/plan_shots.py --episode work/X [--beat-seconds 14] [--force]

Needs `script/narration.md` and `vo/manifest.json` (for the length of each line). Optional author input:
  script/shots-hint.json   {"u004": "boarding-school_part1", ...}   a line that must play over an archive record
`archive.json` lists the archive records an episode has. A record with no hint is placed by the tool:
spread evenly over the film on the line nearest each slot, so the archive layer is present in every part
of the argument. The slots are sized from the profile floor (`archive.episode_profile.mix.min_share`).

All other lines are grouped into 3D beats of about --beat-seconds each (consecutive lines share a beat
name `beat-01`, `beat-02`, ...). A line already on an archive record never joins a 3D beat. The result
passes `workflow.episode` coverage (every utterance has a shot) by construction. An existing
shots.json is kept unless --force, so a hand-authored one is never overwritten.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def plan(utterances, records, hints, beat_seconds, min_share):
    """-> {uid: {"kind", "name", "title", "subtitle"}} for `utterances` [{id, seconds}] in order."""
    ids = [u["id"] for u in utterances]
    seconds = {u["id"]: u["seconds"] for u in utterances}
    total = sum(seconds.values())
    unknown = [uid for uid in hints if uid not in seconds]
    if unknown:
        raise ValueError(f"shots-hint.json names lines the script does not have: {unknown}")
    missing = [n for n in hints.values() if n not in records]
    if missing:
        raise ValueError(f"shots-hint.json names archive records archive.json does not have: {missing}")

    assigned = dict(hints)
    free = [n for n in records if n not in assigned.values()]
    # evenly spaced slots over the film, centred in each slice, on the nearest line not already taken
    starts, t = {}, 0.0
    for uid in ids:
        starts[uid] = t + seconds[uid] / 2
        t += seconds[uid]
    for k, name in enumerate(free):
        centre = (k + 0.5) * total / max(1, len(free))
        for uid in sorted((i for i in ids if i not in assigned), key=lambda i: abs(starts[i] - centre)):
            assigned[uid] = name
            break

    shots, beat, beat_len, count = {}, 0, 0.0, 0
    for uid in ids:
        if uid in assigned:
            shots[uid] = {"kind": "archive", "name": assigned[uid], "title": "", "subtitle": ""}
            beat_len = 0.0
            continue
        if beat == 0 or beat_len >= beat_seconds:
            beat, beat_len = beat + 1, 0.0
        beat_len += seconds[uid]
        shots[uid] = {"kind": "3d", "name": f"beat-{beat:02d}", "title": "", "subtitle": ""}
    share = sum(seconds[u] for u, s in shots.items() if s["kind"] == "archive") / total if total else 0.0
    return shots, share


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", type=Path, required=True)
    ap.add_argument("--beat-seconds", type=float, default=14.0)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    episode = args.episode if args.episode.is_absolute() else ROOT / args.episode
    out = episode / "shots.json"
    if out.exists() and not args.force:
        print(f"{out} exists; kept (use --force to replace)")
        return 0
    manifest = json.loads((episode / "vo" / "manifest.json").read_text(encoding="utf-8"))
    rate = manifest["sampleRate"]
    utterances = [{"id": u["id"], "seconds": u["samples"] / rate} for u in manifest["utterances"]]
    archive_path = episode / "archive.json"
    records = json.loads(archive_path.read_text(encoding="utf-8")) if archive_path.exists() else {}
    hints_path = episode / "script" / "shots-hint.json"
    hints = json.loads(hints_path.read_text(encoding="utf-8")) if hints_path.exists() else {}
    style = json.loads((ROOT / "workflow" / "style.json").read_text(encoding="utf-8"))
    floor = float(style["archive"]["episode_profile"]["mix"]["min_share"]["archive"])
    shots, share = plan(utterances, records, hints, args.beat_seconds, floor)
    out.write_text(json.dumps(shots, indent=2), encoding="utf-8")
    beats = len({s["name"] for s in shots.values() if s["kind"] == "3d"})
    print(f"shots.json: {len(shots)} lines, {beats} 3D beats, archive share {share:.0%} (floor {floor:.0%})")
    if records and share < floor:
        print(f"warning: archive share is under the {floor:.0%} floor; add archive records or hints")
    return 0


if __name__ == "__main__":
    sys.exit(main())
