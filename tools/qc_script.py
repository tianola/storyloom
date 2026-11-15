"""Script gate: is the narration worth synthesising and rendering?

    python tools/qc_script.py --episode work/jensen-huang

Reads `<episode>/script/narration.md` (one utterance per non-empty line, ids u001, u002, ...) and
optionally:
  script/chapters.json   {"chapters": [{"title": "...", "from": "u001"}, ...]}
  script/claims.json     {"u005": ["c3", "c4"], "u001": "framing", ...}
  research/sources.md    the evidence table; a claim id counts only as a row whose status is verified

Every bound comes from the `script` block of workflow/style.json. Findings are `error` (exit 1) or
`warn`. A line is sourced when it cites at least one verified claim id, or is declared `"framing"`
(hook, transition or closing line that asserts nothing checkable). A line that touches a sensitive
subject must cite a claim even if it would otherwise be framing. The report is written to
`<episode>/qc/script-qc.json`.
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SYMBOLS = re.compile(r"[$%&@#=+*/<>~^]|\d")
SENTENCE = re.compile(r"(?<=[.!?])\s+")
MODEL_NAME = re.compile(r"\b[A-Z]{1,6}\d+[A-Za-z]*\b")
ABBREVIATION = re.compile(r"\b(?:Mr|Mrs|Ms|Dr|St|vs|etc|approx)\.", re.I)


def load_contract():
    return json.loads((ROOT / "workflow" / "style.json").read_text(encoding="utf-8"))


def read_script(episode):
    lines = (Path(episode) / "script" / "narration.md").read_text(encoding="utf-8").splitlines()
    return {f"u{i:03d}": text.strip() for i, text in enumerate([l for l in lines if l.strip()], 1)}


def verified_claims(episode):
    """Claim ids of rows in research/sources.md whose verification status says verified."""
    path = Path(episode) / "research" / "sources.md"
    ids = set()
    if not path.exists():
        return ids
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 8 and cells[0] and not set(cells[0]) <= set("-: ") and cells[0] != "Claim ID":
            if cells[7].lower().startswith("verified") and cells[2].startswith("http"):
                ids.add(cells[0])
    return ids


def spoken_seconds(text, wps):
    return len(text.split()) / wps


def check(episode, contract=None):
    """-> {"findings": [{severity, rule, line, message}], "stats": {...}}"""
    contract = contract or load_contract()
    cfg = contract["script"]
    episode = Path(episode)
    script = read_script(episode)
    wps = cfg["words_per_second"]
    findings = []

    def add(severity, rule, line, message):
        findings.append({"severity": severity, "rule": rule, "line": line, "message": message})

    words = sum(len(t.split()) for t in script.values())
    seconds = words / wps
    if seconds < cfg["min_seconds"]:
        add("error", "length", None, f"script runs about {seconds:.0f} s ({words} words); the target is "
            f"{cfg['min_seconds']}-{cfg['max_seconds']} s, so about {math.ceil(cfg['min_seconds'] * wps) - words} more words are needed")
    elif seconds > cfg["max_seconds"]:
        add("error", "length", None, f"script runs about {seconds:.0f} s ({words} words); the target is "
            f"{cfg['min_seconds']}-{cfg['max_seconds']} s")

    first = next(iter(script), None)
    if first:
        hook = SENTENCE.split(script[first])[0]
        hook_s = spoken_seconds(hook, wps)
        limit = cfg["hook_max_seconds"]
        if hook_s > limit:
            add("error", "hook", first, f"the opening sentence takes about {hook_s:.1f} s to say; the hook has to land "
                f"within {limit:.0f} s ({len(hook.split())} words, at most {int(limit * wps)})")

    chapters = []
    chapters_path = episode / "script" / "chapters.json"
    if chapters_path.exists():
        chapters = json.loads(chapters_path.read_text(encoding="utf-8")).get("chapters", [])
    if len(chapters) < cfg["chapter_min"]:
        add("error", "chapters", None, f"{len(chapters)} chapters declared in script/chapters.json; at least "
            f"{cfg['chapter_min']} are needed so the film has a shape")
    else:
        ids = list(script)
        starts = [ids.index(c["from"]) if c.get("from") in ids else -1 for c in chapters]
        if -1 in starts or starts != sorted(starts) or starts[0] != 0:
            add("error", "chapters", None, "chapters must start at the first line and name existing lines in order")
        else:
            bounds = starts + [len(ids)]
            lo, hi = cfg["chapter_seconds"]
            for k, chapter in enumerate(chapters):
                length = sum(len(script[i].split()) for i in ids[bounds[k]:bounds[k + 1]]) / wps
                if not lo <= length <= hi:
                    add("warn", "chapters", chapter["from"],
                        f"chapter '{chapter.get('title', k + 1)}' runs about {length:.0f} s; chapters of {lo}-{hi} s hold attention")

    for uid, text in script.items():
        for sentence in filter(None, SENTENCE.split(text)):
            n = len(sentence.split())
            if n > cfg["sentence_error_words"]:
                add("error", "sentence", uid, f"a sentence of {n} words cannot be spoken in one breath: \"{sentence[:60]}...\"")
            elif n > cfg["sentence_max_words"]:
                add("warn", "sentence", uid, f"a sentence of {n} words (limit {cfg['sentence_max_words']}): \"{sentence[:60]}...\"")
        models = MODEL_NAME.findall(text)
        if models:
            add("warn", "speech", uid, f"product names with digits {sorted(set(models))}: check how the voice reads them")
        bad = SYMBOLS.findall(MODEL_NAME.sub("", text)) or ABBREVIATION.findall(text)
        if bad:
            add("error", "speech", uid, f"write for the ear: spell out {sorted(set(bad))} (numbers, symbols and abbreviations are mis-read by the voice)")

    claims_path = episode / "script" / "claims.json"
    claims = json.loads(claims_path.read_text(encoding="utf-8")) if claims_path.exists() else {}
    known = verified_claims(episode)
    sensitive = [t for t in cfg["sensitive_terms"]]
    for uid, text in script.items():
        cited = claims.get(uid)
        framing = cited == "framing"
        ids = [] if framing or not cited else list(cited)
        verified = [c for c in ids if c in known]
        touches = [t for t in sensitive if re.search(rf"\b{re.escape(t)}\b", text, re.I)]
        if touches and not verified:
            add("error", "sensitive", uid, f"touches {touches} and cites no verified source; a claim about a living person's "
                f"private life needs a primary or tier-1 source: \"{text[:70]}...\"")
        elif not framing and not verified:
            why = "cites claims no verified source row backs" if ids else "cites no claim and is not declared framing"
            add("error", "unsourced", uid, f"{why}: \"{text[:70]}...\"")

    stats = {"lines": len(script), "words": words, "estimated_seconds": round(seconds), "chapters": len(chapters),
             "verified_claims": len(known)}
    return {"findings": findings, "stats": stats}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", type=Path, required=True)
    args = ap.parse_args(argv)
    episode = args.episode if args.episode.is_absolute() else ROOT / args.episode
    report = check(episode)
    out = episode / "qc"
    out.mkdir(exist_ok=True)
    (out / "script-qc.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    errors = [f for f in report["findings"] if f["severity"] == "error"]
    for f in report["findings"]:
        where = f["line"] or "script"
        print(f"{f['severity'].upper():5} {f['rule']:9} {where:5} {f['message']}")
    print(f"{report['stats']}\n{len(errors)} error(s), {len(report['findings']) - len(errors)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
