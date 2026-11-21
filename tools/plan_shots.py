"""Shot list: which narration line plays over which beat or archive shot -> `<episode>/shots.json`.

    python tools/plan_shots.py --episode work/X [--beat-seconds 14] [--force]

Needs `script/narration.md` and `vo/manifest.json` (for the length of each line). Optional author input:
  script/shots-hint.json   {"u004": "boarding-school_part1", ...}   a line that must play over an archive record
`archive.json` lists the archive records an episode has. Archive is evidence, not texture
(`archive.evidence` in workflow/style.json): every record says in `depicts` which specific named thing
it shows, and it may only play under a line that names it. A record with no hint goes on the first free
line that names it; a record no line names is left out and reported. There is no share to fill.

All other lines are grouped into 3D beats of about --beat-seconds each (consecutive lines share a beat
name `beat-01`, `beat-02`, ...). A line already on an archive record never joins a 3D beat. The result
passes `workflow.episode` coverage (every utterance has a shot) by construction. An existing
shots.json is kept unless --force, so a hand-authored one is never overwritten.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load_evidence_rule():
    return json.loads((ROOT / "workflow" / "style.json").read_text(encoding="utf-8"))["archive"]["evidence"]


def _norm(text):
    return " " + re.sub(r"[^a-z0-9]+", " ", text.lower()).strip() + " "


def depicts_problems(name, record, rule):
    """Why a record cannot be evidence: no `depicts`, or only category nouns in it."""
    names = record.get(rule["depicts_field"])
    if not isinstance(names, list) or not names or not all(isinstance(n, str) for n in names):
        return [f"archive record '{name}' has no '{rule['depicts_field']}' list: say which specific "
                "named thing it shows (a person, event, product model, document or named place)"]
    generic = {_norm(t) for t in rule["generic_terms"]}
    specific = [n for n in names if _norm(n) not in generic and len(n.strip()) >= rule["min_name_chars"]]
    if not specific:
        return [f"archive record '{name}' depicts only category nouns {names}: that is stock footage, "
                "not evidence; name the specific thing or drop the clip"]
    return []


def names_it(text, record, rule):
    """True when the line says one of the record's specific names."""
    generic = {_norm(t) for t in rule["generic_terms"]}
    line = _norm(text)
    return any(_norm(n) in line for n in record.get(rule["depicts_field"]) or [] if _norm(n) not in generic)


def plan(utterances, records, hints, beat_seconds, rule=None):
    """-> (shots, share, unused) for `utterances` [{id, seconds, text}] in order.

    shots: {uid: {"kind", "name", "title", "subtitle"}}; unused: records no line names."""
    rule = rule or load_evidence_rule()
    ids = [u["id"] for u in utterances]
    seconds = {u["id"]: u["seconds"] for u in utterances}
    text = {u["id"]: u.get("text", "") for u in utterances}
    total = sum(seconds.values())
    unknown = [uid for uid in hints if uid not in seconds]
    if unknown:
        raise ValueError(f"shots-hint.json names lines the script does not have: {unknown}")
    missing = [n for n in hints.values() if n not in records]
    if missing:
        raise ValueError(f"shots-hint.json names archive records archive.json does not have: {missing}")
    errors = [p for n, r in records.items() for p in depicts_problems(n, r, rule)]
    errors += [f"shots-hint.json puts '{n}' under {uid}, which never names {records[n].get(rule['depicts_field'])}: "
               f"\"{text[uid][:80]}\"" for uid, n in hints.items()
               if not depicts_problems(n, records[n], rule) and not names_it(text[uid], records[n], rule)]
    if errors:
        raise ValueError("archive is evidence, not texture:\n  " + "\n  ".join(errors))

    assigned = dict(hints)
    unused = []
    for name in (n for n in records if n not in assigned.values()):
        line = next((uid for uid in ids if uid not in assigned and names_it(text[uid], records[name], rule)), None)
        if line is None:
            unused.append(name)
        else:
            assigned[line] = name

    shots, beat, beat_len, count = {}, 0, 0.0, 0
    for uid in ids:
        if uid in assigned:
            shots[uid] = {"kind": "archive", "name": assigned[uid], "title": "", "subtitle": ""}
            beat_len = beat_seconds     # the next 3D line opens a new beat: a beat never straddles a cutaway
            continue
        if beat == 0 or beat_len >= beat_seconds:
            beat, beat_len = beat + 1, 0.0
        beat_len += seconds[uid]
        shots[uid] = {"kind": "3d", "name": f"beat-{beat:02d}", "title": "", "subtitle": ""}
    share = sum(seconds[u] for u, s in shots.items() if s["kind"] == "archive") / total if total else 0.0
    return shots, share, unused


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
    utterances = [{"id": u["id"], "seconds": u["samples"] / rate, "text": u.get("text", "")}
                  for u in manifest["utterances"]]
    archive_path = episode / "archive.json"
    records = json.loads(archive_path.read_text(encoding="utf-8")) if archive_path.exists() else {}
    hints_path = episode / "script" / "shots-hint.json"
    hints = json.loads(hints_path.read_text(encoding="utf-8")) if hints_path.exists() else {}
    try:
        shots, share, unused = plan(utterances, records, hints, args.beat_seconds)
    except ValueError as exc:
        print(exc)
        return 1
    out.write_text(json.dumps(shots, indent=2), encoding="utf-8")
    beats = len({s["name"] for s in shots.values() if s["kind"] == "3d"})
    print(f"shots.json: {len(shots)} lines, {beats} 3D beats, archive share {share:.0%}")
    if unused:
        print(f"not placed (no line names what they show): {', '.join(unused)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
