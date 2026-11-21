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


SPEAKER_TAG = re.compile(r"^\[([a-z][a-z0-9-]{0,31})(?::(thought))?\]\s+")
DIRECTION = re.compile(r"\{([^{}]{1,60})\}\s*")
NARRATOR = "narrator"


def read_lines(episode):
    """{uid: {"speaker", "mode", "text", "directed"}}. A line may open with `[name]` (that character
    speaks on screen) or `[name:thought]` (inner voice); an untagged line is the narrator's.
    `{softly}`, `{desperate}` ... anywhere in a line are directions for an expressive voice: they are
    not spoken words, so `text` drops them and `directed` keeps them (as `[softly]`, the form
    ElevenLabs v3 reads)."""
    lines = (Path(episode) / "script" / "narration.md").read_text(encoding="utf-8").splitlines()
    out = {}
    for i, raw in enumerate([l for l in lines if l.strip()], 1):
        text = raw.strip()
        tag = SPEAKER_TAG.match(text)
        speaker, mode = (tag.group(1), tag.group(2) or "say") if tag else (NARRATOR, "say")
        body = text[tag.end():].strip() if tag else text
        out[f"u{i:03d}"] = {"speaker": speaker, "mode": mode, "text": DIRECTION.sub("", body).strip(),
                            "directed": DIRECTION.sub(lambda m: f"[{m.group(1).strip()}] ", body).strip()}
    return out


def read_script(episode):
    """{uid: spoken text}, speaker tags removed (every measure counts only the words heard)."""
    return {uid: line["text"] for uid, line in read_lines(episode).items()}


def read_cast(episode):
    path = Path(episode) / "script" / "cast.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


ENGLISH_VOICE = re.compile(r"[ab][fm]_[a-z0-9_]{1,31}|eleven:[A-Za-z0-9]{16,32}")   # Kokoro English or ElevenLabs


def check_cast(lines, cast, dramatisation, verified, add):
    """Characters who speak: each speaker is cast with an English voice, and every line put in a real
    person's mouth says what it rests on (verified claims) and that its words are imagined."""
    for name, entry in cast.items():
        if not isinstance(entry, dict) or not ENGLISH_VOICE.fullmatch(str(entry.get("voice", ""))):
            add("error", "cast", None, f"cast.json: {name} needs an English Kokoro voice (af_/am_/bf_/bm_) or eleven:<voice_id>")
    for uid, line in lines.items():
        who = line["speaker"]
        if who == NARRATOR:
            continue
        if who not in cast:
            add("error", "cast", uid, f"speaker {who!r} is not in script/cast.json")
            continue
        d = dramatisation.get(uid)
        if not isinstance(d, dict) or not str(d.get("note", "")).strip():
            add("error", "dramatisation", uid, f"{who} speaks; script/dramatisation.json must say what is imagined "
                "(note) and what it rests on (basis)")
            continue
        basis = d.get("basis") or []
        unbacked = [c for c in basis if c not in verified]
        if not basis or unbacked:
            add("error", "dramatisation", uid, "a dramatised line must rest on verified claims; "
                + (f"not verified: {unbacked}" if unbacked else "basis is empty"))


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


NUMBER = re.compile(r"\b(\d[\d,.]*|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|"
                    r"forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion|trillion|percent|"
                    r"half|third|quarter|dozens?)\b", re.I)


def story_shape(script, cfg):
    """Measured the same way the reference films were: numbers, turns and questions per sentence/minute."""
    rule = cfg["story"]
    turn = re.compile(r"\b(" + "|".join(re.escape(w) for w in rule["turn_words"]) + r")\b", re.I)
    sentences = [(uid, s) for uid, text in script.items() for s in SENTENCE.split(text) if s.strip()]
    minutes = sum(len(t.split()) for t in script.values()) / cfg["words_per_second"] / 60 or 1.0
    numeric = [bool(NUMBER.search(s)) for _, s in sentences]
    run, best, best_at, start = 0, 0, None, None
    for (uid, _), n in zip(sentences, numeric):
        if n:
            start = uid if run == 0 else start
            run += 1
            if run > best:
                best, best_at = run, start
        else:
            run = 0
    text = " ".join(script.values())
    return {"numeric_share": round(sum(numeric) / max(1, len(sentences)), 3), "numeric_run": best,
            "numeric_run_from": best_at, "turns_per_minute": round(len(turn.findall(text)) / minutes, 2),
            "questions_per_minute": round(sum(s.strip().endswith("?") for _, s in sentences) / minutes, 2)}


def check_story(episode, script, chapters, cfg, add):
    """A film is a story the viewer follows, not a list of facts (`script.story` in style.json)."""
    rule = cfg["story"]
    shape = story_shape(script, cfg)
    if shape["numeric_share"] > rule["numeric_sentence_share_max"]:
        add("error", "story", None, f"{shape['numeric_share']:.0%} of sentences carry a number (reference films: at most "
            f"{rule['numeric_sentence_share_max']:.0%}); keep the numbers that change the story and turn the rest into a picture")
    if shape["numeric_run"] > rule["numeric_run_max"]:
        add("error", "story", shape["numeric_run_from"], f"{shape['numeric_run']} sentences in a row carry a number "
            f"(at most {rule['numeric_run_max']}): that stretch is a spec sheet; break it with what the numbers mean")
    elif shape["numeric_run"] > rule["numeric_run_warn"]:
        add("warn", "story", shape["numeric_run_from"], f"{shape['numeric_run']} numeric sentences in a row")
    if shape["turns_per_minute"] < rule["turns_per_minute_min"]:
        add("error", "story", None, f"the story turns {shape['turns_per_minute']} times a minute (but / problem / turns out ...; "
            f"reference films at least {rule['turns_per_minute_min']}): every step should break the last answer")
    if shape["questions_per_minute"] < rule["questions_per_minute_min"]:
        add("warn", "story", None, f"{shape['questions_per_minute']} questions a minute (reference films at least "
            f"{rule['questions_per_minute_min']}): ask what the viewer is wondering before answering it")

    path = Path(episode) / rule["story_file"]
    if not path.exists():
        add("error", "story", None, f"no {rule['story_file']}: declare the open question, its payoff, who the viewer "
            f"follows and the real people in the story ({rule['story_file_doc']})")
        return shape
    story = json.loads(path.read_text(encoding="utf-8"))
    ids = list(script)
    wps = cfg["words_per_second"]
    at = {}
    t = 0.0
    for uid in ids:
        at[uid] = t
        t += len(script[uid].split()) / wps
    q = story.get("question")
    if q not in script:
        add("error", "story", None, "story.json 'question' must name the line that opens the film's question")
    elif at[q] > rule["question_by_seconds"]:
        add("error", "story", q, f"the film's question opens at about {at[q]:.0f} s; it has to be open by "
            f"{rule['question_by_seconds']} s, inside the intro viewers decide on")
    p = story.get("payoff")
    if p not in script:
        add("error", "story", None, "story.json 'payoff' must name the line that answers the question")
    elif ids.index(p) < rule["payoff_after_fraction"] * len(ids):
        add("warn", "story", p, "the payoff comes before the last fifth of the film; what keeps the viewer after it?")
    follow = str(story.get("follow", "")).strip()
    if not follow:
        add("error", "story", None, "story.json 'follow' must say who or what the viewer follows through the film")
    elif chapters:
        starts = [ids.index(c["from"]) for c in chapters if c.get("from") in ids] + [len(ids)]
        spans = [ids[a:b] for a, b in zip(starts, starts[1:])]
        hit = sum(any(re.search(rf"\b{re.escape(follow)}\b", script[u], re.I) for u in span) for span in spans)
        if spans and hit / len(spans) < rule["follow_chapter_share_min"]:
            add("error", "story", None, f"'{follow}' appears in {hit} of {len(spans)} chapters; the thing the viewer "
                f"follows has to come back in at least {rule['follow_chapter_share_min']:.0%} of them")
    people = story.get("people") or []
    named = [person for person in people if person.get("line") in script
             and person.get("name") and person["name"].split()[-1].lower() in script[person["line"]].lower()]
    if len(named) < rule["people_min"]:
        add("error", "story", None, f"{len(named)} real people named in the story (need {rule['people_min']}, each "
            "with the line that names them): facts happen to someone; a film with nobody in it is a presentation")
    check_turn(story, script, ids, rule, add)
    check_hook(Path(episode), story, script, ids, at, rule, add)
    return shape


def check_hook(episode, story, script, ids, at, rule, add):
    """The opening has to grab: declared as a shock, a mystery, a contradiction or stakes, with
    the picture it opens on; no soft opener; a gap (a question or a contrast) opened within
    `hook.gap_by_seconds`; and a shocking fact has to be a sourced one."""
    cfg = rule["hook"]
    hook = story.get("hook") or {}
    first = ids[0]
    if hook.get("kind") not in cfg["kinds"] or not str(hook.get("image", "")).strip():
        add("error", "hook", first, f"story.json needs 'hook': {{'kind': one of {cfg['kinds']}, 'image': what the "
            "first shot shows}}: the first seconds decide whether anyone stays")
    opening = SENTENCE.split(script[first])[0].strip()
    soft = re.compile(r"^(" + "|".join(cfg["soft_openers"]) + r")\b", re.I)
    if soft.search(opening):
        add("error", "hook", first, f"the film opens with a soft opener ('{soft.search(opening).group(0)}'); open on "
            "the strange thing itself")
    gap = re.compile(r"\b(" + "|".join(re.escape(w) for w in cfg["gap_words"]) + r")\b", re.I)
    early = [u for u in ids if at[u] <= cfg["gap_by_seconds"]]
    if not any("?" in script[u] or gap.search(script[u]) for u in early):
        add("error", "hook", first, f"nothing in the first {cfg['gap_by_seconds']} s opens a gap (a question, or a "
            "contrast such as but / yet / still / nobody): give the viewer something they need closed")
    if hook.get("kind") == "shock":
        claims_path = episode / "script" / "claims.json"
        cited = json.loads(claims_path.read_text(encoding="utf-8")).get(first) if claims_path.exists() else None
        if not isinstance(cited, list) or not cited:
            add("error", "hook", first, "a shocking opening has to be true: the first line cites no verified claim")


def check_turn(story, script, ids, rule, add):
    """The film sets up the guess a viewer would make and later breaks it, instead of handing
    over the answer at the start: `guess` names the line that states the plausible wrong
    explanation, `reversal` the line that overturns it."""
    turn = re.compile(r"\b(" + "|".join(re.escape(w) for w in rule["turn_words"]) + r")\b", re.I)
    g, r = story.get("guess"), story.get("reversal")
    if g not in script or r not in script:
        add("error", "story", None, "story.json needs 'guess' (the line that states the explanation a viewer would "
            "assume) and 'reversal' (the line that breaks it): a film that states its answer up front is a lecture")
        return
    gi, ri = ids.index(g), ids.index(r)
    n = len(ids)
    if gi > rule["guess_by_fraction"] * n:
        add("error", "story", g, f"the guess is set up {gi / n:.0%} into the film; set it up in the first "
            f"{rule['guess_by_fraction']:.0%} so the viewer carries it")
    lo, hi = rule["reversal_window"]
    if ri <= gi:
        add("error", "story", r, "the reversal comes before the guess it is meant to break")
    elif not lo * n <= ri <= hi * n:
        add("error", "story", r, f"the reversal lands {ri / n:.0%} into the film; it belongs between {lo:.0%} and "
            f"{hi:.0%}, after the guess has been believed and with room left to rebuild the real answer")
    if not turn.search(script[r]):
        add("error", "story", r, "the reversal line has no turn in it (but / actually / wrong ...): say plainly "
            "that the guess was wrong")


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

    story_stats = check_story(episode, script, chapters, cfg, add)
    lines = read_lines(episode)
    if any(l["speaker"] != NARRATOR for l in lines.values()) or (episode / "script" / "cast.json").exists():
        d_path = episode / "script" / "dramatisation.json"
        dramatisation = json.loads(d_path.read_text(encoding="utf-8")) if d_path.exists() else {}
        check_cast(lines, read_cast(episode), dramatisation, known, add)

    stats = {"lines": len(script), "words": words, "estimated_seconds": round(seconds), "chapters": len(chapters),
             "verified_claims": len(known), **story_stats}
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
