"""Planner: narration + scene catalog -> `<episode>/storyboard.json`, never an invalid one.

    python tools/plan_storyboard.py --episode work/X --brief
        writes storyboard-brief.md: everything an agent (or a person) needs to write storyboard.json
    python tools/plan_storyboard.py --episode work/X --ask-cmd "<command>"
        runs <command> with the prompt on stdin; it must print the storyboard JSON on stdout.
        An answer that fails validation is sent back with the errors, up to --repairs times.
    python tools/plan_storyboard.py --episode work/X --check
        validates the storyboard already on disk (the gate `storyboard_beats.py` also applies)

A storyboard that fails validation is written to `storyboard-rejected.json` with its errors and
the exit code is 1; `storyboard.json` is only ever replaced by one that passed, so a bad plan
cannot reach Blender.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(ROOT / "tools"))
from workflow import storyboard as sb  # noqa: E402

MAX_LABELS = 4


def beats_of(episode):
    """The 3D beats an episode needs a storyboard for: [{name, text, seconds}] in film order."""
    episode = Path(episode)
    lengths = json.loads((episode / "shot_lengths.json").read_text(encoding="utf-8"))
    manifest = json.loads((episode / "vo" / "manifest.json").read_text(encoding="utf-8"))
    said = {u["id"]: u["text"] for u in manifest["utterances"]}
    from edit import cutlist
    cut = cutlist.episode_cut(episode)
    if cut is not None:
        return [{"name": name, "text": " ".join(said.get(l, "") for l in span["lines"]),
                 "seconds": lengths.get(name)} for name, span in cutlist.beat_spans(cut).items()]
    shots = json.loads((episode / "shots.json").read_text(encoding="utf-8"))
    beats = {}
    for uid, shot in shots.items():
        if shot["kind"] != "3d":
            continue
        beat = beats.setdefault(shot["name"], {"name": shot["name"], "text": [], "seconds": lengths.get(shot["name"])})
        beat["text"].append(said.get(uid, ""))
    return [{**b, "text": " ".join(b["text"])} for b in beats.values()]


def archive_mix(episode, contract=None):
    """Planning-time share check: findings when the shot list gives archive too little screen time.

    Same numbers the QC gate uses (`workflow.archive.mix_findings`), applied to `shots.json` before
    anything is rendered, so a film that cannot meet the floor is refused at planning.
    Returns [(code, message)]; empty when the share and per-act floors are met."""
    from workflow import archive
    episode = Path(episode)
    doc = episode / "episode.json"
    if doc.is_file() and not json.loads(doc.read_text(encoding="utf-8")).get("archive", {}).get("enabled", True):
        return []          # an episode that declares itself 3D-only owes no archive share
    contract = contract or json.loads((ROOT / "workflow" / "style.json").read_text(encoding="utf-8"))
    from edit import cutlist
    cut = cutlist.episode_cut(episode)
    if cut is not None:
        timeline = [{"layer": s["source"]["kind"], "start": s["start"], "seconds": s["end"] - s["start"]}
                    for s in cut["shots"]]
        return [(f.code, f.message) for f in archive.mix_findings(timeline, contract, mode="warn")]
    shots = json.loads((episode / "shots.json").read_text(encoding="utf-8"))
    manifest = json.loads((episode / "vo" / "manifest.json").read_text(encoding="utf-8"))
    rate = manifest["sampleRate"]
    timeline = [{"layer": shots[u["id"]]["kind"], "start": u["startSample"] / rate,
                 "seconds": (u["endSample"] - u["startSample"]) / rate}
                for u in manifest["utterances"] if u["id"] in shots]
    return [(f.code, f.message) for f in archive.mix_findings(timeline, contract, mode="warn")]


def archive_evidence(episode):
    """Errors for archive shots that are texture rather than evidence (`archive.evidence`).

    Applies to any shots.json, hand-written or planned: the record must name a specific thing in
    `depicts`, and every line it plays under must say that name."""
    sys.path.insert(0, str(ROOT / "tools"))
    import plan_shots
    episode = Path(episode)
    path = episode / "archive.json"
    records = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    manifest = json.loads((episode / "vo" / "manifest.json").read_text(encoding="utf-8"))
    said = {u["id"]: u.get("text", "") for u in manifest["utterances"]}
    from edit import cutlist
    cut = cutlist.episode_cut(episode)
    if cut is not None:
        # a cut-list shot plays under the lines it spans; it is evidence if any of them names it
        said = {s["id"]: " ".join(said.get(l, "") for l in s.get("lines", [])) for s in cut["shots"]}
        shots = {s["id"]: {"kind": s["source"]["kind"], "name": s["source"]["name"]} for s in cut["shots"]}
    else:
        shots = json.loads((episode / "shots.json").read_text(encoding="utf-8"))
    rule = plan_shots.load_evidence_rule()
    errors, seen = [], set()
    for uid, shot in shots.items():
        if shot["kind"] != "archive":
            continue
        name = shot["name"]
        record = records.get(name)
        if record is None:
            continue                       # missing records are the ingest's finding, not this one
        if name not in seen:
            seen.add(name)
            errors += plan_shots.depicts_problems(name, record, rule)
        if not plan_shots.depicts_problems(name, record, rule) and not plan_shots.names_it(said.get(uid, ""), record, rule):
            errors.append(f"archive '{name}' plays under {uid}, which never names {record.get('depicts')}: "
                          f"\"{said.get(uid, '')[:80]}\"")
    return errors


def catalog_digest(catalog):
    lines = []
    for name, spec in sorted(catalog.items()):
        params = "; ".join(f"{k}: {p['type']}" + (f" in {p['values']}" if "values" in p else "") +
                           f" (default {json.dumps(p['default'])}) {p['doc']}" for k, p in spec["params"].items())
        lines.append(f"- {name}: {spec['description']}\n    params: {params or '(this scene takes none: leave out "params")'}\n"
                     f"    views: {', '.join(spec['views'])}\n    anchors: {', '.join(spec['anchors'])}\n"
                     f"    actions: {', '.join(spec['actions']) or '(this scene has none: leave out \"actions\")'}")
    return "\n".join(lines)


RULES = f"""Return ONE JSON object: {{"beats": {{"<beat name>": {{...}}, ...}}}}, one entry for every beat below and no other.
Each beat entry:
  "scene":   a scene name from the catalog
  "params":  optional, only parameters that scene declares
  "cut":     "travel" (default: one continuous camera move through the scene's views, no cuts) for explaining how
             something works; "montage" (quick 1-2.5 s cuts between views and close-ups) for the hook and moments of
             tension or surprise; "steady" (a cut every 4-5 s) rarely
  "shots":   optional [{{"view": "<view>" or "at:<anchor>", "to": "<view to travel to>", "start": seconds}}]; leave out to use "cut"
  "labels":  up to {MAX_LABELS} [{{"text": "<=32 chars", "anchor": "<anchor of that scene>", "at": fraction of the beat (0-1), or "word:<a word the narrator says>"}}]
  "actions": optional [{{"name": "<action of that scene>", "at": fraction or "word:<w>"}}]
  "hud":     optional [{{"text", "screen": [u, v], "at"}}] for text fixed to the screen
  "counter": optional {{"template": "${{:,}} billion", "from", "to", "screen": [u, v], "curve": "exp", "color": "warm"}}
Rules: this is a story, not a slide deck. Stay in a place while the story stays there: neighbouring beats about the
same thing reuse the same scene with a different view or action instead of jumping to a new diagram per sentence.
Put the cast in the scene doing something (walking to the thing, reacting, waiting) rather than standing beside it.
Text is rare: label only a thing the viewer could not otherwise name, tie it to its word with "word:", and leave
numbers to the narrator; at most {{text}} labels/HUD/counters a minute and at most {{charts}} chart beat in the film.
Never invent a number the narration does not say. Use only names that appear in the catalog."""


def rules_text():
    rule = json.loads((ROOT / "workflow" / "style.json").read_text(encoding="utf-8"))["storyboard"]
    return RULES.replace("{text}", str(rule["text_per_minute_max"])).replace("{charts}", str(rule["chart_beats_max"]))


def build_prompt(beats, catalog, errors=None, previous=None):
    parts = ["You plan the 3D pictures of a narrated documentary that tells a story.", rules_text(),
             "SCENE CATALOG\n" + catalog_digest(catalog),
             "BEATS (name, seconds on screen, narration)\n" +
             "\n".join(f"- {b['name']} ({b['seconds']} s): {b['text']}" for b in beats)]
    if errors:
        parts.append("YOUR PREVIOUS ANSWER WAS REJECTED:\n" + (json.dumps(previous)[:6000] if previous else "(not JSON)") +
                     "\nERRORS:\n" + "\n".join(f"- {e}" for e in errors[:40]) + "\nReturn the corrected full JSON.")
    return "\n\n".join(parts)


def extract_json(text):
    """The JSON object in a model answer: bare, or inside a code fence, or after some prose."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise
        return json.loads(text[start:end + 1])


def problems(board, beats, catalog):
    """Validator errors plus what only the planner knows: coverage and label budget."""
    lengths = {b["name"]: b["seconds"] for b in beats}
    errors = sb.validate(board, catalog, lengths)
    planned = set((board.get("beats") or {}) if isinstance(board, dict) else {})
    for name in lengths:
        if name not in planned:
            errors.append(f"beat '{name}' has no entry")
    for name in planned - set(lengths):
        errors.append(f"beat '{name}' is not a 3D beat of this episode")
    for name, beat in ((board.get("beats") or {}).items() if isinstance(board, dict) else []):
        if len(beat.get("labels") or []) > MAX_LABELS:
            errors.append(f"beat '{name}': at most {MAX_LABELS} labels")
    return errors + shape_problems(board, lengths)


def shape_problems(board, lengths, contract=None):
    """What makes a storyboard a slide deck: too much text, chart beats, one uniform cut."""
    rule = (contract or json.loads((ROOT / "workflow" / "style.json").read_text(encoding="utf-8")))["storyboard"]
    beats = (board.get("beats") or {}) if isinstance(board, dict) else {}
    if not beats:
        return []
    errors = []
    minutes = sum(float(lengths.get(n) or 0) for n in beats) / 60 or 1.0
    text = sum(len(b.get("labels") or []) + len(b.get("hud") or []) + (1 if b.get("counter") else 0) for b in beats.values())
    if text > max(2, rule["text_per_minute_max"] * minutes):
        errors.append(f"{text} pieces of on-screen text in {minutes:.1f} min of 3D ({text / minutes:.1f} a minute, at most "
                      f"{rule['text_per_minute_max']}): let the picture and the narrator carry it; keep only words the viewer must read")
    charts = [n for n, b in beats.items() if b.get("scene") in rule["chart_scenes"]]
    if len(charts) > rule["chart_beats_max"]:
        errors.append(f"{len(charts)} chart beats ({', '.join(charts)}), at most {rule['chart_beats_max']}: "
                      "show what the number means (a scene, a comparison the cast acts out) instead of a chart")
    def cut_of(name, b):
        return sb.cut_of(name, b, lengths)
    cuts = [cut_of(n, b) for n, b in beats.items()]
    if len(beats) >= 4 and cuts.count("montage") < rule["montage_beats_min"]:
        errors.append(f"no beat is cut as a montage (\"cut\": \"montage\"): the hook and the moments of tension need quick cuts")
    if len(beats) >= 4 and cuts.count("travel") / len(cuts) < rule["travel_beats_min_share"]:
        errors.append(f"{cuts.count('travel')} of {len(cuts)} beats are one continuous camera move (\"cut\": \"travel\", the default); "
                      f"at least {rule['travel_beats_min_share']:.0%} should be, so explanations hold instead of cutting every few seconds")
    return errors


def staging_advice_for(episode, board):
    """Advice (never errors) from the episode's line timing: who is in frame when they speak, shot-length
    floors, the narrator's spot. Needs mouth_timing.json and shot_lengths.json; quiet without them."""
    def load(name):
        path = Path(episode) / name
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    lines, lengths = load("mouth_timing.json"), load("shot_lengths.json")
    if lengths is None:
        return []
    return sb.staging_advice(board, lines or {}, lengths, load("word_timing.json") or {})


def plan(beats, catalog, ask, repairs=3):
    """-> (board or None, errors). `ask(prompt) -> text`. Repairs by sending the errors back."""
    board, errors = None, ["no answer"]
    best = (None, ["no answer"])
    for attempt in range(repairs + 1):
        answer = ask(build_prompt(beats, catalog, errors if attempt else None, board if attempt else None))
        try:
            found = extract_json(answer)
        except ValueError as exc:
            # keep the last board that was JSON: the repair prompt shows it again instead of
            # "(not JSON)", so one garbled answer does not throw away the work before it
            errors = [f"the answer is not JSON ({exc})"]
            continue
        board, errors = found, problems(found, beats, catalog)
        if not errors:
            return board, []
        if best[0] is None or len(errors) < len(best[1]):
            best = (board, errors)
    # a planner that never got there: hand back its closest attempt, not merely its last one
    return best if best[0] is not None else (board, errors)


def command_ask(command):
    def ask(prompt):
        run = subprocess.run(command, input=prompt, capture_output=True, text=True, shell=True,
                             encoding="utf-8", timeout=900)
        if run.returncode != 0:
            raise SystemExit(f"--ask-cmd failed ({run.returncode}): {run.stderr.strip()[:500]}")
        return run.stdout
    return ask


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", type=Path, required=True)
    ap.add_argument("--brief", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--ask-cmd")
    ap.add_argument("--repairs", type=int, default=3)
    args = ap.parse_args(argv)
    episode = args.episode if args.episode.is_absolute() else ROOT / args.episode
    catalog = sb.load_catalog()
    beats = beats_of(episode)

    if args.check:
        board = json.loads((episode / "storyboard.json").read_text(encoding="utf-8"))
        errors = problems(board, beats, catalog)
        mix = archive_mix(episode)
        errors += [f"archive mix: {message}" for code, message in mix]
        errors += [f"archive evidence: {e}" for e in archive_evidence(episode)]
        advice = [f"advice: {w}" for w in staging_advice_for(episode, board)]
        print("\n".join(errors + advice) or f"storyboard OK ({len(beats)} beats)")
        if advice and not errors:
            print(f"storyboard OK ({len(beats)} beats), {len(advice)} piece(s) of advice")
        return 1 if errors else 0
    if args.brief or not args.ask_cmd:
        path = episode / "storyboard-brief.md"
        path.write_text(build_prompt(beats, catalog) + f"\n\nWrite the answer to {episode / 'storyboard.json'}, "
                        f"then run: python tools/plan_storyboard.py --episode {args.episode} --check\n", encoding="utf-8")
        print(f"brief for {len(beats)} beats -> {path}")
        return 0

    board, errors = plan(beats, catalog, command_ask(args.ask_cmd), args.repairs)
    if errors:
        (episode / "storyboard-rejected.json").write_text(
            json.dumps({"errors": errors, "board": board}, indent=1), encoding="utf-8")
        print(f"storyboard rejected after {args.repairs} repairs; see storyboard-rejected.json\n" +
              "\n".join(errors[:20]))
        return 1
    tmp = episode / "storyboard.json.part"
    tmp.write_text(json.dumps(board, indent=1), encoding="utf-8")
    tmp.replace(episode / "storyboard.json")
    print(f"storyboard.json written ({len(beats)} beats)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
