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
from workflow import storyboard as sb  # noqa: E402

MAX_LABELS = 4


def beats_of(episode):
    """The 3D beats an episode needs a storyboard for: [{name, text, seconds}] in film order."""
    episode = Path(episode)
    shots = json.loads((episode / "shots.json").read_text(encoding="utf-8"))
    lengths = json.loads((episode / "shot_lengths.json").read_text(encoding="utf-8"))
    manifest = json.loads((episode / "vo" / "manifest.json").read_text(encoding="utf-8"))
    said = {u["id"]: u["text"] for u in manifest["utterances"]}
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
    contract = contract or json.loads((ROOT / "workflow" / "style.json").read_text(encoding="utf-8"))
    shots = json.loads((episode / "shots.json").read_text(encoding="utf-8"))
    manifest = json.loads((episode / "vo" / "manifest.json").read_text(encoding="utf-8"))
    rate = manifest["sampleRate"]
    timeline = [{"layer": shots[u["id"]]["kind"], "start": u["startSample"] / rate,
                 "seconds": (u["endSample"] - u["startSample"]) / rate}
                for u in manifest["utterances"] if u["id"] in shots]
    return [(f.code, f.message) for f in archive.mix_findings(timeline, contract, mode="warn")]


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
  "shots":   optional [{{"view": "<view of that scene>" or "at:<anchor>", "start": seconds}}]; leave out for the default (a cut every 4-5 s)
  "labels":  up to {MAX_LABELS} [{{"text": "<=32 chars", "anchor": "<anchor of that scene>", "at": fraction of the beat (0-1), or "word:<a word the narrator says>"}}]
  "actions": optional [{{"name": "<action of that scene>", "at": fraction or "word:<w>"}}]
  "hud":     optional [{{"text", "screen": [u, v], "at"}}] for text fixed to the screen
  "counter": optional {{"template": "${{:,}} billion", "from", "to", "screen": [u, v], "curve": "exp", "color": "warm"}}
Rules: pick the scene whose picture the sentence is about, not a decorative one; tag only things the narrator names;
tie a label to the word it explains with "word:"; vary scenes between neighbouring beats; never invent a number
the narration does not say. Use only names that appear in the catalog."""


def build_prompt(beats, catalog, errors=None, previous=None):
    parts = ["You plan the 3D pictures of a narrated explainer video.", RULES,
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
    return errors


def plan(beats, catalog, ask, repairs=3):
    """-> (board or None, errors). `ask(prompt) -> text`. Repairs by sending the errors back."""
    board, errors = None, ["no answer"]
    for attempt in range(repairs + 1):
        answer = ask(build_prompt(beats, catalog, errors if attempt else None, board if attempt else None))
        try:
            board = extract_json(answer)
        except ValueError as exc:
            board, errors = None, [f"the answer is not JSON ({exc})"]
            continue
        errors = problems(board, beats, catalog)
        if not errors:
            return board, []
    return board, errors


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
        print("\n".join(errors) or f"storyboard OK ({len(beats)} beats)")
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
