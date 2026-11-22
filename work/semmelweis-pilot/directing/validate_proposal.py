"""Validate the v6 directing proposal (cut.proposed.json, storyboard.proposed.json,
narration.proposed.md) against the existing gates and the new requirements of the approved plan.

Reads only. Writes validation-report.md beside itself. Exit 1 if any check fails.

    python work/semmelweis-pilot/directing/validate_proposal.py
"""
import json
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
EP = HERE.parent
ROOT = EP.parent.parent
sys.path.insert(0, str(ROOT))
from workflow.storyboard import validate as validate_storyboard  # noqa: E402

CONTRACT = json.loads((ROOT / "workflow" / "style.json").read_text(encoding="utf-8"))
CUTS = CONTRACT["rhythm"]["cuts"]
ARCH_MAX = float(CONTRACT["archive_rhythm"]["max_archival_shot_seconds"]) \
    if "archive_rhythm" in CONTRACT else 6.0
STILL_MAX = 10.0
TRANSITIONS = {"cut": (0.0, 0.0), "dissolve": (0.2, 1.0), "dip": (0.3, 1.2), "match": (0.0, 0.3)}
PROVENANCE = {"archive", "reconstruction", "graphic-data", "graphic-schematic", "symbolic", "black"}
MUTE_FACTS = {
    "two clinics side by side": "two clinics side by side",
    "admission on alternate days": "alternate days",
    "who staffs each clinic": "who staffs each clinic",
    "the death difference": "the death difference",
    "street births are safer": "street births: rarely fever",
    "position changed nothing": "position changed nothing",
    "rerouting changed nothing": "rerouting changed nothing",
    "Kolletschka's cut": "the cut on Kolletschka's hand",
    "Kolletschka's death": "Kolletschka falls ill and dies",
    "same disease as the mothers": "same disease",
    "the chain, morgue to mother": "the chain: morgue to mother",
    "the bare hands": "the same bare hands",
}

results = []   # (section, name, ok, detail)


def check(section, name, ok, detail=""):
    results.append((section, name, bool(ok), detail))
    return ok


def find_arch_max():
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "max_archival_shot_seconds":
                    return float(v)
                r = walk(v)
                if r is not None:
                    return r
        return None
    return walk(CONTRACT) or 6.0


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--cut", type=Path, default=HERE / "cut.proposed.json")
    ap.add_argument("--report", type=Path, default=HERE / "validation-report.md")
    args = ap.parse_args()
    cut = json.loads(args.cut.read_text(encoding="utf-8"))
    board = json.loads((HERE / "storyboard.proposed.json").read_text(encoding="utf-8"))
    fps = cut["fps"]
    shots = cut["shots"]
    lines = {l["id"]: l for l in cut["lines"]}
    arch_max = find_arch_max()

    # ---------------------------------------------------------------- 1. hook
    tally = next(s for s in shots if any(o["graphic"] == "tally" for o in s["overlays"]))
    o = next(o for o in tally["overlays"] if o["graphic"] == "tally")
    built = o["start"] + max(a + d for a, d in o["spec"]["build"].values())
    check("Hook", "visual contrast complete by 15.0 s", built <= 15.0, f"tallies fully built at {built:.2f} s ({tally['id']})")
    for rate in ("measured", "conservative"):
        words = cut["words_new"]["u003"][rate]
        nine = next(w for w in words if w["w"].startswith("nine"))["e"]
        six = next(w for w in words if w["w"].startswith("six"))["e"]
        check("Hook", f"'one in nine' heard by 18 s ({rate})", nine <= 18.0, f"ends {nine:.2f} s")
        check("Hook", f"'one in thirty six' heard by 22 s ({rate})", six <= 22.0, f"ends {six:.2f} s")

    # ---------------------------------------------------------------- 2. curiosity loops
    def roles(loop):
        out = {}
        for s in shots:
            if s.get("loop") == loop and s.get("role"):
                out.setdefault(s["role"], []).append(s["id"])
            for a in s.get("also") or []:
                if a["loop"] == loop:
                    out.setdefault(a["role"], []).append(s["id"])
        return out
    for loop, name in (("A", "air"), ("B", "position"), ("C", "fear")):
        r = roles(loop)
        missing = [x for x in ("belief", "experiment", "result", "next") if x not in r]
        order_ok = not missing and min(r["belief"]) <= min(r["experiment"]) <= min(r["result"]) <= max(r["next"])
        check("Loops", f"Loop {loop} ({name}): belief, experiment, result, next question, in order",
              not missing and order_ok, f"missing {missing}" if missing else
              " / ".join(f"{k}: {','.join(v)}" for k, v in r.items()))
    clue = [s for s in shots if any("planted" in d for d in s["demonstrates"])]
    chain = [s for s in shots if any("the chain" in d for d in s["demonstrates"])]
    check("Loops", "Kolletschka answers the planted clue (clue shot before the chain shot)",
          clue and chain and clue[0]["start"] < chain[0]["start"],
          f"clue {clue[0]['id'] if clue else '-'} at {clue[0]['start'] if clue else '-'} s; "
          f"chain {chain[0]['id'] if chain else '-'} at {chain[0]['start'] if chain else '-'} s")

    # ---------------------------------------------------------------- 3. evidence board
    hosts = {}
    for s in shots:
        if s.get("host"):
            hosts.setdefault(s["host"]["id"], s["host"])
    check("Board", "five host moments H1-H5", sorted(hosts) == ["H1", "H2", "H3", "H4", "H5"], ", ".join(sorted(hosts)))
    fr = [h["framing"] for h in hosts.values()]
    it = [h["interaction"] for h in hosts.values()]
    pu = [h["purpose"] for h in hosts.values()]
    check("Board", "no two host moments share framing, interaction or purpose",
          len(set(fr)) == len(fr) and len(set(it)) == len(it) and len(set(pu)) == len(pu))
    check("Board", "H5 is on location, off the board", "on location" in hosts.get("H5", {}).get("framing", ""))
    board_inserts = [s for s in shots if s["source"].get("view", "").startswith("card-")]
    check("Board", "card inserts are short (<=1.5 s) and each different",
          all(s["end"] - s["start"] <= 1.5 for s in board_inserts)
          and len({s["source"]["view"] for s in board_inserts}) == len(board_inserts),
          ", ".join(f"{s['source']['view']} {s['end'] - s['start']:.2f}s" for s in board_inserts))

    # ---------------------------------------------------------------- 4. rhythm (existing thresholds)
    pics = [s for s in shots if s["source"]["kind"] != "black"]
    lengths = [s["end"] - s["start"] for s in pics]
    med = statistics.median(lengths)
    short = sum(x < CUTS["short_seconds"] for x in lengths) / len(lengths)
    held = max(pics, key=lambda s: s["end"] - s["start"])
    held_len = held["end"] - held["start"]
    check("Rhythm", f"median shot <= {CUTS['median_max_seconds']} s", med <= CUTS["median_max_seconds"], f"{med:.2f} s over {len(lengths)} shots")
    check("Rhythm", f"share under {CUTS['short_seconds']} s >= {CUTS['short_share_min']:.0%}", short >= CUTS["short_share_min"], f"{short:.0%}")
    check("Rhythm", f"one held MOVING shot >= {CUTS['held_shot_min_seconds']:.0f} s",
          held_len >= CUTS["held_shot_min_seconds"] and held["source"].get("to"),
          f"{held['id']} {held_len:.2f} s, travel {held['source'].get('view')} -> {held['source'].get('to')}")
    still = [s for s in pics if s["source"]["kind"] == "3d" and s["source"].get("view") and
             s["end"] - s["start"] > STILL_MAX and not s["source"].get("to")]
    locks = [s for s in pics if s["end"] - s["start"] > STILL_MAX and s["id"] != held["id"]]
    check("Rhythm", f"no other shot over {STILL_MAX:.0f} s (no static hold)", not locks and not still,
          ", ".join(s["id"] for s in locks) or "none")
    check("Rhythm", "every shot at least 2 frames", all(round((s["end"] - s["start"]) * fps) >= 2 for s in shots))

    # ---------------------------------------------------------------- 5. archive
    records = json.loads((EP / "archive.json").read_text(encoding="utf-8"))
    ledger = {r["id"]: r for r in json.loads((EP / "assets" / "archive-licence.json").read_text(encoding="utf-8"))}
    arch = [s for s in shots if s["source"]["kind"] == "archive"]
    for s in arch:
        name = s["source"]["name"]
        rec = records.get(name, {})
        n = s["end"] - s["start"]
        check("Archive", f"{name}: screen time <= {arch_max:g} s (transitions included)", n <= arch_max, f"{n:.2f} s")
        check("Archive", f"{name}: on the mat (credit off the picture)", s["source"].get("frame") == "archive_mat")
        row = ledger.get(rec.get("licence"))
        check("Archive", f"{name}: ledger row {rec.get('licence')} public domain",
              row and row.get("rights_basis") == "pd_expired", (row or {}).get("credit_line", "no row"))
    used = {records[s["source"]["name"]]["licence"] for s in arch}
    unused = sorted(set(ledger) - used)
    check("Archive", "(info) unused ledger rows", True, ", ".join(unused) or "none")
    portrait = next((s for s in arch if s["source"]["name"] == "semmelweis-portrait"), None)
    check("Archive", "the 1860 portrait is not under 'he's twenty eight' (u010)",
          portrait and "u010" not in portrait["lines"], f"on {portrait['lines'] if portrait else '-'}")

    # ---------------------------------------------------------------- 6. mute test
    for fact, needle in MUTE_FACTS.items():
        hit = [s["id"] for s in shots if any(needle in d for d in s["demonstrates"])]
        check("Mute test", f"shown, not only said: {fact}", hit, ", ".join(hit) or "no shot")

    # ---------------------------------------------------------------- 7. provenance & claims
    sources = (EP / "research" / "sources.md").read_text(encoding="utf-8")
    known = set(re.findall(r"^\|\s*(c\d+)\s*\|", sources, re.M))
    bad_prov = [s["id"] for s in shots if s["provenance"] not in PROVENANCE]
    check("Provenance", "every shot tagged", not bad_prov, ", ".join(bad_prov) or f"{len(shots)} shots")
    unknown = sorted({c for s in shots for c in s["claims"]} - known)
    check("Provenance", "every claim id exists in research/sources.md", not unknown, ", ".join(unknown) or "all known")
    symbolic = [s["id"] for s in shots if s["provenance"] == "symbolic"] + \
               [s["id"] + "(dip)" for s in shots if s["transition_in"]["type"] == "dip" and s["source"]["kind"] != "black"]
    check("Provenance", "at most 2 symbolic devices", len(symbolic) <= 2, ", ".join(symbolic))
    schematic_kinds = {"ward-plan-routes", "day_labels", "board_card", "map_plan"}
    data_kinds = {"tally", "ratio-1846", "date_stamp"}
    tagged = [(o["graphic"], o["provenance"]) for s in shots for o in s["overlays"]] + \
             [(s["source"]["name"], s["provenance"]) for s in shots if s["source"]["kind"] == "graphic"]
    wrong = [f"{g}={p}" for g, p in tagged
             if (g in schematic_kinds and p != "graphic-schematic") or (g in data_kinds and p != "graphic-data")
             or g not in schematic_kinds | data_kinds]
    check("Provenance", "schematics tagged schematic, data graphics tagged data", tagged and not wrong,
          ", ".join(wrong) or f"{len(tagged)} graphics")
    framing = {lid for lid, v in json.loads((EP / "script" / "claims.json").read_text(encoding="utf-8")).items() if v == "framing"}
    claim_lines = [lid for lid in lines if lid not in framing]
    shown = {lid for s in shots for lid in s["lines"]}
    check("Provenance", "every claim line has a shot over it", set(claim_lines) <= shown,
          ", ".join(sorted(set(claim_lines) - shown)) or f"{len(claim_lines)} lines")

    # ---------------------------------------------------------------- 8. mobile
    floors = {"label": 0.06, "number": 0.10}
    specs = [o["spec"] for s in shots for o in s["overlays"]] + [s["source"]["spec"] for s in shots if s["source"].get("spec")]
    small = [sp for sp in specs if any(sp.get("type", {}).get(k, 0) < v for k, v in floors.items())]
    check("Mobile", "graphic type >= 0.06 (labels) / 0.10 (numbers) of frame height", specs and not small,
          f"{len(specs)} graphic specs")

    # ---------------------------------------------------------------- 9. ending
    last = [s for s in shots if s["source"]["kind"] != "black"][-1]
    check("Ending", "the last picture is on the hands", "hands" in (last["source"].get("view") or ""),
          f"{last['id']} {last['source'].get('view')}")
    check("Ending", "no payoff shown (no basin, chlorine or washing in the last 4 shots)",
          not any(re.search(r"chlorine|washes|washing", s["note"], re.I) for s in shots[-4:]))

    # ---------------------------------------------------------------- 10. schema (section 10)
    gaps = [(a["id"], b["id"]) for a, b in zip(shots, shots[1:]) if abs(a["end"] - b["start"]) > 1e-6]
    check("Schema", "no gaps or overlaps (end == next start)", not gaps, str(gaps[:5]) if gaps else "contiguous")
    off = [s["id"] for s in shots if abs(s["start"] * fps - round(s["start"] * fps)) > 1e-3]
    check("Schema", "cut points on whole frames", not off, ", ".join(off) or "all")
    badtr = []
    for s in shots:
        t, d = s["transition_in"]["type"], s["transition_in"]["dur"]
        lo, hi = TRANSITIONS.get(t, (None, None))
        if lo is None or not (lo <= d <= hi):
            badtr.append(f"{s['id']} {t} {d}")
    check("Schema", "transition types and durations in range", not badtr, ", ".join(badtr) or "all")
    handles = [f"{s['id']} needs {s['transition_in']['dur'] / 2:.2f} s pre-roll in {s['source']['name']}"
               for s in shots if s["transition_in"]["dur"] > 0 and s["source"]["kind"] in ("3d", "archive")
               and s["source"]["in"] < s["transition_in"]["dur"] / 2]
    check("Schema", "(info) transition handles the renderers must add", True, "; ".join(handles) or "none needed")
    outside = [s["id"] for s in shots for o in s["overlays"] if not (s["start"] <= o["start"] < o["end"] <= s["end"])]
    check("Schema", "overlays sit inside their shot", not outside, ", ".join(outside) or "all")

    # ---------------------------------------------------------------- 11. script gate on the draft narration
    narr = (HERE / "narration.proposed.md").read_text(encoding="utf-8").splitlines()
    narr = [l for l in narr if l.strip()]
    check("Script", "draft narration has 29 lines and matches the cut's line texts",
          len(narr) == 29 and re.sub(r"\{[^}]*\}\s*", "", narr[2]).strip() == lines["u003"]["text"]
          and narr[4].strip() == lines["u005"]["text"], f"{len(narr)} lines")
    with tempfile.TemporaryDirectory() as tmp:
        ep = Path(tmp) / "ep"
        shutil.copytree(EP / "script", ep / "script")
        shutil.copytree(EP / "research", ep / "research")
        (ep / "script" / "narration.md").write_text("\n".join(narr) + "\n", encoding="utf-8")
        claims = json.loads((EP / "script" / "claims.json").read_text(encoding="utf-8"))
        claims.update({"u003": ["c5", "c7"], "u004": claims["u003"], "u005": ["c6"], "u006": claims["u005"]})
        (ep / "script" / "claims.json").write_text(json.dumps(claims), encoding="utf-8")
        story = json.loads((EP / "script" / "story.json").read_text(encoding="utf-8"))
        story["question"] = "u004"
        (ep / "script" / "story.json").write_text(json.dumps(story), encoding="utf-8")
        run = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "tools" / "qc_script.py"), "--episode", str(ep)],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
        report = json.loads((ep / "qc" / "script-qc.json").read_text(encoding="utf-8")) \
            if (ep / "qc" / "script-qc.json").exists() else None
    if report is None:
        check("Script", "qc_script ran on the draft", False, run.stdout[-400:] + run.stderr[-400:])
    else:
        errs = sorted({f["rule"] for f in report["findings"] if f["severity"] == "error"})
        st = report["stats"]
        check("Script", "qc_script: only the pilot's expected errors (length, story payoff)",
              set(errs) <= {"length", "story"} and all("payoff" in f["message"] for f in report["findings"]
                                                       if f["severity"] == "error" and f["rule"] == "story"),
              f"errors: {errs}")
        check("Script", "turns >= 1.4 a minute", st["turns_per_minute"] >= 1.4, f"{st['turns_per_minute']}")
        warns = [f"{f['rule']}: {f['message'][:90]}" for f in report["findings"] if f["severity"] != "error"]
        check("Script", "(info) qc_script warnings", True, "; ".join(warns) or "none")

    # ---------------------------------------------------------------- 12. planning gate on the proposed beats
    errors = validate_storyboard(board)
    to_build = {tb for s in shots for tb in s["to_build"]}
    def planned(e):
        return any(k in e for k in ("unknown scene 'board'", "unknown scene 'wing'")) or \
            any(re.search(rf"'{re.escape(v.split(' ', 1)[-1].split(' ')[0])}'", e) for v in to_build if v.startswith("view"))
    real = [e for e in errors if not planned(e)]
    check("Planning", "storyboard.validate on proposed beats: no errors beyond planned new scenes/views",
          not real, "; ".join(real[:6]) or f"{len(errors)} findings, all planned builds")

    # ---------------------------------------------------------------- report
    out = ["# Validation report: v6 directing proposal", "",
           f"Projected film: {cut['clock']['duration']:.2f} s, {len(shots)} shots "
           f"({len(pics)} pictures + black tail), {len(board['beats'])} 3D beats.", "",
           "| Section | Check | Result | Detail |", "|---|---|---|---|"]
    for sec, name, ok, detail in results:
        out.append(f"| {sec} | {name} | {'PASS' if ok else '**FAIL**'} | {str(detail).replace('|', '/')} |")
    failed = [r for r in results if not r[2]]
    out += ["", f"**{len(results) - len(failed)} of {len(results)} checks pass.**"]
    args.report.write_text("\n".join(out) + "\n", encoding="utf-8")
    for sec, name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  [{sec}] {name}  -- {detail}")
    print(f"\n{len(results) - len(failed)}/{len(results)} pass")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
