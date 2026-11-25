"""Build the v6 directing proposal: the projected narration clock, cut.proposed.json and
storyboard.proposed.json, from the v5 voice (vo/manifest.json, vo/<id>.align.json) and the shot
design below. Reads only; writes only into this directory.

Clock: the v5 lines keep their audio. Two new lines (u003', u005') are estimated at the measured
narrator rate (2.88 words/s, v5 at speed 1.15) plus 0.3 s at each sentence end; a second,
conservative clock at 2.36 words/s (qc_script's estimate) is written alongside so the hook can be
checked against both. Cut times follow the section 10 schema of the approved plan: film clock in
seconds, one rounding (frame = round(t * fps)), a cut on a word lands 2 frames before the word.

    python work/semmelweis-pilot/directing/build_proposal.py
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EP = HERE.parent
ROOT = EP.parent.parent
sys.path.insert(0, str(ROOT))
from workflow.storyboard import load_catalog  # noqa: E402

FPS = 30
LEAD_FRAMES = 2
MEASURED_WPS = 2.88
CONSERVATIVE_WPS = 2.36
SENTENCE_PAUSE = 0.3
TAIL_BLACK = 1.0

NEW_LINES = {
    "u003": ("The hospital has two maternity clinics. In the first, one mother in nine dies. "
             "Yet in the second, it's one in thirty six.", ["c5", "c7"]),
    "u005": ("They take women in on alternate days.", ["c6"]),
}
# new id -> where its audio comes from (old v5 id) ; None = new line
ORDER = [("u001", "u001"), ("u002", "u002"), ("u003", None), ("u004", "u003"), ("u005", None),
         ("u006", "u005")] + [(f"u{i:03d}", f"u{i:03d}") for i in range(7, 30)]


def words_from_alignment(path):
    """[(word, start, end)] relative to the line's wav; bracketed directions are skipped."""
    a = json.loads(Path(path).read_text(encoding="utf-8"))["alignment"]
    chars, t0s, t1s = a["characters"], a["character_start_times_seconds"], a["character_end_times_seconds"]
    out, cur, start, end, depth = [], "", None, None, 0
    for ch, s, e in zip(chars, t0s, t1s):
        if ch == "[":
            depth += 1
            continue
        if ch == "]":
            depth = max(0, depth - 1)
            continue
        if depth:
            continue
        if ch.isspace():
            if cur:
                out.append((cur, start, end))
            cur, start = "", None
            continue
        if start is None:
            start = s
        cur += ch
        end = e
    if cur:
        out.append((cur, start, end))
    return out


def estimated_words(text, wps):
    out, t = [], 0.0
    for w in text.split():
        d = 1.0 / wps
        out.append((w, t, t + d))
        t += d + (SENTENCE_PAUSE if w[-1] in ".?!" else 0.0)
    return out, t


def build_clock(wps_new):
    manifest = json.loads((EP / "vo" / "manifest.json").read_text(encoding="utf-8"))
    rate = manifest["sampleRate"]
    old = {u["id"]: u for u in manifest["utterances"]}
    lines, t = [], 0.0
    for new_id, src in ORDER:
        if src is None:
            text, claims = NEW_LINES[new_id]
            words, dur = estimated_words(text, wps_new)
            voiced = False
        else:
            u = old[src]
            text = u["text"]
            dur = u["samples"] / rate
            words = words_from_alignment(EP / "vo" / f"{src}.align.json")
            claims = None
            voiced = True
        lines.append({"id": new_id, "audio_from": src, "voiced": voiced, "text": text,
                      "start": round(t, 3), "end": round(t + dur, 3),
                      "words": [{"w": w, "s": round(t + s, 3), "e": round(t + e, 3)} for w, s, e in words],
                      "claims": claims})
        t += dur
    return lines


def norm(w):
    return re.sub(r"[^a-z0-9']", "", w.lower())


def resolve(lines_by_id, anchor):
    """anchor: ("u003",) line start | ("u003", "word") | ("u003", "word", n) | ("u003", "+", seconds)."""
    line = lines_by_id[anchor[0]]
    if len(anchor) == 1:
        return line["start"]
    if anchor[1] == "+":
        return line["start"] + anchor[2]
    target, nth = norm(anchor[1]), (anchor[2] if len(anchor) > 2 else 1)
    hits = [w for w in line["words"] if norm(w["w"]) == target]
    if len(hits) < nth:
        raise SystemExit(f"anchor {anchor} misses the alignment of {anchor[0]}: {[w['w'] for w in line['words']]}")
    return max(line["start"], hits[nth - 1]["s"] - LEAD_FRAMES / FPS)


def S(at, mode, kind, name, *, view=None, scene=None, move="lock", to=None, transition=("cut", 0.0),
      overlays=(), prov="reconstruction", claims=(), demonstrates=(), loop=None, role=None,
      host=None, to_build=(), note="", also=()):
    return dict(at=at, mode=mode, kind=kind, name=name, view=view, scene=scene, move=move, to=to, also=list(also),
                transition=transition, overlays=list(overlays), prov=prov, claims=list(claims),
                demonstrates=list(demonstrates), loop=loop, role=role, host=host,
                to_build=list(to_build), note=note)


TYPE = {"label": 0.06, "number": 0.10}   # mobile floors as fractions of frame height (plan section 9)


def O(graphic, at, until, spec=None, prov="graphic-data"):
    return dict(graphic=graphic, at=at, until=until, spec={**(spec or {}), "type": dict(TYPE)}, provenance=prov)


# ----------------------------------------------------------------------------------------------
# The shot design. Mode: F = Fern story, V = Veritasium investigation, A = archive, G = graphic.
# Beats: each contiguous run of 3D shots in one scene becomes one beat; inserts between runs start
# a new beat. View names not in the catalog are flagged to_build automatically.
# ----------------------------------------------------------------------------------------------
SHOTS = [
    # ---- Loop 0: the mystery -----------------------------------------------------------------
    S(("u001",), "F", "3d", None, scene="vienna", view="gate-approach", move="drift",
      note="dawn street; a woman in labour, held by a midwife, walks toward the hospital gate; her face, close",
      to_build=["view gate-approach", "staging labour-arrival (mother + midwife walk)"]),
    S(("u001", "arrives"), "F", "3d", None, scene="vienna", view="hospital", move="push",
      note="she looks up at the facade; low angle push on the hospital"),
    S(("u002",), "F", "3d", None, scene="vienna", view="court-low", move="drift", loop="0", role="belief",
      note="a top-hatted doctor in the court explains to a student, waving at the drain and the smoke",
      to_build=["staging doctor-explains (doctor + student, point at drain)"]),
    S(("u002", "Bad"), "F", "3d", None, scene="vienna", view="court", move="lock", loop="0", role="belief",
      demonstrates=["belief: bad air"], note="the foul drain and chimney smoke over the court: 'Bad air.'"),
    S(("u003",), "A", "archive", "akh-engraving", prov="archive", transition=("dissolve", 0.3),
      note="the real hospital: Schaffer engraving on the archive mat, slow push; credit on the mat"),
    S(("u003", "In"), "F", "3d", None, scene="vienna", view="doors", move="push", loop="0", role="anomaly",
      demonstrates=["two clinics side by side", "the death difference (tallies)"],
      overlays=[O("tally", 0.15, None, {"left": {"label": "First Clinic", "marks": 11, "per": 100},
                                         "right": {"label": "Second Clinic", "marks": 3, "per": 100},
                                         "build": {"left": [0.15, 0.7], "right": [0.5, 0.35]},
                                         "source": "1846 · Semmelweis 1861"})],
      note="both doors in one frame; under each a tally builds: 11 marks against 3 per 100 births"),
    S(("u003", "Yet"), "G", "graphic", "ratio-1846", prov="graphic-data", loop="0", role="anomaly",
      demonstrates=["the death difference (ratios)"],
      note="full-frame ratio_compare: 9 figures, 1 dark, 'about 1 in 9' | 36 figures, 1 dark, "
           "'about 1 in 36'; right side builds on 'thirty six'; tag '1846 figures · Semmelweis 1861'"),
    S(("u004",), "V", "3d", None, scene="board", view="h1-low34", move="push", loop="0", role="question",
      host={"id": "H1", "purpose": "turn the anomaly into a mystery", "framing": "3/4 low angle, medium-wide",
            "interaction": "door sketches with tallies; flips the calendar strip"},
      note="host at the board's edge; the two door sketches with tallies pinned"),
    S(("u004", "which"), "V", "3d", None, scene="board", view="h1-calendar", move="lock", loop="0", role="question",
      host={"id": "H1", "purpose": "turn the anomaly into a mystery", "framing": "insert, calendar strip",
            "interaction": "calendar strip flips day"},
      note="insert: his hand flips the calendar strip between the two doors"),
    S(("u005",), "F", "3d", None, scene="vienna", view="doors", move="lock", loop="0", role="clue",
      demonstrates=["admission on alternate days"],
      overlays=[O("day_labels", 0.1, None, {"cycle": [["MON", "first"], ["TUE", "second"], ["WED", "first"]],
                                            "step": 0.8}, prov="graphic-schematic")],
      note="the two doors; day labels alternate the open door; the queue of women moves door to door"),
    S(("u006",), "F", "3d", None, scene="vienna", view="first-door", move="drift", loop="0", role="clue",
      demonstrates=["who staffs each clinic", "students come from the anatomy wing (planted)"],
      note="matched framing A: doctors and students cross the court from the anatomy wing, aprons on, "
           "into the First Clinic (the planted clue; never pointed out)",
      to_build=["staging students-from-anatomy (group walks anatomy wing -> first door)"]),
    S(("u006", "midwives"), "F", "3d", None, scene="vienna", view="second-door", move="drift", loop="0", role="clue",
      demonstrates=["who staffs each clinic"],
      note="matched framing B: midwives in blue and white at the Second Clinic, same lens and angle",
      to_build=["view second-door matched to first-door (same lens/height/angle, mirrored)"]),
    S(("u007",), "F", "3d", None, scene="vienna", view="first-door", move="lock", loop="0", role="stakes",
      demonstrates=["women beg not to go to the First Clinic"],
      note="a woman kneels at the First Clinic door, pleading with the porter", to_build=["pose kneel", "actor porter"]),
    S(("u007", "anywhere"), "F", "3d", None, scene="vienna", view="at:first", move="push", loop="0", role="stakes",
      note="close on the mother (on screen before her line)"),
    S(("u009",), "F", "3d", None, scene="vienna", view="hospital", move="lock", note="'Same building.'"),
    S(("u009", "Same", 2), "F", "3d", None, scene="vienna", view="roofs", move="lock", note="'Same city.'"),
    S(("u009", "Same", 3), "F", "3d", None, scene="vienna", view="court-low", move="lock", note="'Same air.' smoke"),
    S(("u009", "So"), "V", "3d", None, scene="board", view="h2-close", move="push", loop="0", role="next",
      host={"id": "H2", "purpose": "hand the guess to the viewer", "framing": "tight close-up, board out of focus",
            "interaction": "holds a blank card and pencil out to the lens"},
      note="host close, eyes to lens; the blank card held out; holds into the start of u010"),
    # ---- Semmelweis -------------------------------------------------------------------------
    S(("u010",), "F", "3d", None, scene="ward", view="ward-door", move="drift",
      note="young Semmelweis (the 3D character) steps into the First Clinic ward"),
    S(("u010", "He's"), "F", "3d", None, scene="ward", view="semmelweis-close", move="push",
      note="his face, close: twenty-eight, new to the job", to_build=["view semmelweis-close"]),
    S(("u011",), "F", "3d", None, scene="vienna", view="desk", move="drift", note="night, his desk, his face"),
    S(("u011", "Only"), "F", "3d", None, scene="vienna", view="ledger", move="push", role="motif",
      demonstrates=["the deaths are counted (ledger motif)"],
      note="insert: the death ledger, a column of crosses (tally marks only, no legible text)",
      to_build=["prop death-ledger on the desk", "view ledger", "action tally (adds a cross)"]),
    S(("u012",), "V", "3d", None, scene="board", view="h3-top", move="lock", loop="A", role="plan",
      host={"id": "H3", "purpose": "lay out the investigation plan", "framing": "top-down on the desk, hands only",
            "interaction": "lays three cards: AIR, POSITION, FEAR"},
      note="top-down: his hands lay three cards in a row"),
    # ---- Loop A: air --------------------------------------------------------------------------
    S(("u013",), "V", "3d", None, scene="board", view="card-air", move="push", loop="A", role="belief",
      demonstrates=["belief: air"], note="insert 0.7 s: the AIR card pinned"),
    S(("u013", "Yet"), "F", "3d", None, scene="vienna", view="street-birth", move="push", loop="A", role="experiment",
      demonstrates=["street births: worse air"],
      note="the dirtiest air in Vienna: a woman gives birth on the cobbles outside the gate; a midwife "
           "kneels by her; carts pass",
      to_build=["pose give-birth", "staging street-birth", "view street-birth"]),
    S(("u013", "hardly"), "F", "3d", None, scene="vienna", view="ledger-street", move="lock", loop="A", role="result",
      demonstrates=["street births: rarely fever (empty column)"],
      note="the ledger: the street-births column stays empty while the First Clinic's fills",
      to_build=["view ledger-street (two columns)"]),
    # ---- Loop B: position ---------------------------------------------------------------------
    S(("u014",), "F", "3d", None, scene="vienna", view="first-door", move="push", loop="B", role="belief",
      demonstrates=["belief: position"], also=[{"loop": "A", "role": "next"}],
      overlays=[O("board_card", 0.35, None, {"title": "POSITION", "pin": True, "corner": "top-right"},
                  prov="graphic-schematic")],
      note="Loop A's next question, 'so it's something inside': follow a midwife through the First Clinic "
           "door as it shuts; the POSITION card slides in pinned at the corner (the board recurs as an "
           "overlay here, not a cutaway)"),
    S(("u014", "The"), "F", "3d", None, scene="ward", view="second-bed", move="lock", loop="B", role="belief",
      demonstrates=["Second Clinic: mothers on their side"],
      note="matched framing A: a Second Clinic mother lies on her side",
      to_build=["pose lie-side", "view second-bed (matched to ward-bed)"]),
    S(("u014", "so"), "F", "3d", None, scene="ward", view="ward-wide", move="push", loop="B", role="experiment",
      demonstrates=["First Clinic: mothers turned onto their side"],
      note="wide First Clinic: the mothers are turned onto their side; every bed now matches",
      to_build=["ward param lie: side (all patients)"]),
    S(("u015",), "F", "3d", None, scene="vienna", view="ledger", move="lock", loop="B", role="result",
      demonstrates=["position changed nothing (ledger same pace)"],
      also=[{"loop": "B", "role": "next"}],
      note="'Nothing changes.' a hand adds a cross to the ledger; the bell is HEARD under it (J-cut)"),
    # ---- Loop C: fear -------------------------------------------------------------------------
    S(("u016",), "V", "3d", None, scene="board", view="card-fear", move="push", loop="C", role="belief",
      demonstrates=["belief: fear"], note="insert 0.7 s: the FEAR card pinned"),
    S(("u016", "Whenever"), "F", "3d", None, scene="ward", view="ward-wide", move="drift", loop="C", role="belief",
      demonstrates=["the priest's procession through the ward"],
      note="the priest and the bell come down the aisle (existing bell action, route: aisle)"),
    S(("u016", "man"), "F", "3d", None, scene="ward", view="at:bell", move="lock", loop="C", role="belief",
      demonstrates=["mothers turn in fear"], note="the boy's bell, close; mothers turning toward it"),
    S(("u016", "bell"), "F", "3d", None, scene="ward", view="ward-door", move="lock", loop="C", role="belief",
      note="Semmelweis at his door, hearing it (on screen before his line)"),
    S(("u017", "strange"), "F", "3d", None, scene="ward", view="semmelweis-close", move="push", loop="C",
      role="belief", note="his face as the bell passes"),
    S(("u018",), "G", "graphic", "ward-plan-routes", prov="graphic-schematic", loop="C", role="experiment",
      demonstrates=["the route changed"],
      note="map_plan, labelled 'schematic': old route down the aisle (red) vs a quieter route (white)"),
    S(("u018", "long"), "F", "3d", None, scene="ward", view="ward-wide", move="lock", loop="C", role="experiment",
      demonstrates=["the priest comes quietly; mothers don't turn"],
      note="the priest by the quieter route, no bell; nobody turns", to_build=["bell params route/ring"]),
    S(("u018", "keep"), "F", "3d", None, scene="vienna", view="ledger", move="lock", loop="C", role="result",
      demonstrates=["rerouting changed nothing (ledger)"], note="the ledger: another cross"),
    S(("u019",), "V", "3d", None, scene="board", view="h4-ots", move="drift", loop="C", role="next",
      host={"id": "H4", "purpose": "the verdict: the void", "framing": "over the shoulder, behind the host",
            "interaction": "three struck cards; pulls the last down"},
      note="behind the host: AIR, POSITION, FEAR struck; he pulls the last one down; only the doors remain"),
    S(("u019", "wrong"), "V", "3d", None, scene="board", view="h4-turn", move="lock", loop="C", role="next",
      host={"id": "H4", "purpose": "the verdict: the void", "framing": "he turns to the lens, medium",
            "interaction": "turns to lens on 'wrong'"},
      note="he turns to the lens on 'wrong'"),
    # ---- The answer: Kolletschka ---------------------------------------------------------------
    S(("u020",), "F", "3d", None, scene="vienna", view="anatomy", move="drift", loop="K", role="answer",
      overlays=[O("date_stamp", 0.1, None, {"text": "March 1847"}, prov="graphic-data")],
      claims=["c21"], note="the dissecting room: Kolletschka lecturing at the table (existing staging)"),
    S(("u020", "Jakob"), "A", "archive", "kolletschka-portrait", prov="archive", loop="K", role="answer",
      note="his real portrait on the mat (Kriehuber 1844), through 'professor of forensic medicine'"),
    S(("u020", "is"), "F", "3d", None, scene="vienna", view="scalpel", move="push", loop="K", role="answer",
      demonstrates=["a student's scalpel at the autopsy"],
      note="a student's scalpel over the table, close", to_build=["prop scalpel", "view scalpel"]),
    S(("u020", "knife"), "F", "3d", None, scene="vienna", view="cut-hand", move="lock", loop="K", role="answer",
      demonstrates=["the cut on Kolletschka's hand"],
      note="the blade slips; a cut on his hand, a red drop", to_build=["action cut", "view cut-hand"]),
    S(("u020", "And"), "F", "3d", None, scene="vienna", view="sickbed", move="push", loop="K", role="answer",
      demonstrates=["Kolletschka falls ill and dies"],
      note="Kolletschka fevered in a sickbed; dip to black on 'he dies'",
      to_build=["pose sick", "set sickbed", "view sickbed"]),
    S(("u021",), "F", "3d", None, scene="wing", view="wing-table", to="wing-ward-bed", move="travel",
      transition=("dip", 0.8), loop="K", role="answer",
      demonstrates=["same disease: body then mother in one move", "the chain: morgue to mother, no break",
                    "the same bare hands"],
      host={"id": "H5", "purpose": "leave the board: the investigation enters the world",
            "framing": "on location in the corridor, inside the continuous shot",
            "interaction": "walks beside the students, turns to the lens"},
      note="THE HELD SHOT (one continuous move, about 23 s): under his thought the camera finds the covered "
           "body; doctors examine it ('the same disease'); it follows doctors and students from the table, "
           "out the door, down the corridor past the host (u023), in through the First Clinic door to a "
           "mother's bed; it ends pushing into the bare hands on 'With the same bare hands.'",
      to_build=["scene wing (anatomy + corridor + ward joined)", "views wing-table..wing-ward-bed",
                "explorer full figure on location", "close on hands at the end of the move"]),
    S(("u026",), "F", "3d", None, scene="ward", view="hands-window", move="push", loop="open", role="question",
      prov="symbolic", demonstrates=["the question: what are the hands carrying"],
      note="the hands frozen in silhouette against the window light; dust drifts in the beam; slow push",
      to_build=["sprite hands (large)", "view hands-window", "dust in window beam"]),
    S(("u027",), "F", "3d", None, scene="ward", view="semmelweis-hands", move="push", loop="open", role="question",
      note="Semmelweis looks down at his own hands", to_build=["view semmelweis-hands", "pose look-hands"]),
    S(("u028",), "A", "archive", "semmelweis-portrait", prov="archive", loop="open", role="teaser",
      note="his real portrait (after Doby, 1860; the older man) on the mat"),
    S(("u029",), "F", "3d", None, scene="ward", view="hands-door", move="push", loop="open", role="end",
      demonstrates=["the hands go on to the next mother"],
      note="the same unwashed hands push open the next ward door toward another mother; it swings shut",
      to_build=["view hands-door", "action door-swing"]),
    S(("u029", "+", 99), "F", "black", "black", prov="black", transition=("dip", 0.6), role="end",
      note="black tail"),
]

# claims per new id (u007.. keep v5's)
def line_claims():
    old = json.loads((EP / "script" / "claims.json").read_text(encoding="utf-8"))
    out = {}
    for new_id, src in ORDER:
        if src is None:
            out[new_id] = NEW_LINES[new_id][1]
        else:
            v = old.get(src)
            out[new_id] = v if isinstance(v, list) else []
    return out


def main():
    lines = build_clock(MEASURED_WPS)
    cons = build_clock(CONSERVATIVE_WPS)
    by_id = {l["id"]: l for l in lines}
    claims = line_claims()
    catalog = load_catalog()
    end_of_film = lines[-1]["end"] + TAIL_BLACK

    starts = []
    for s in SHOTS:
        a = s["at"]
        if a[0] == "u029" and a[1:2] == ("+",):
            starts.append(lines[-1]["end"])
        else:
            starts.append(resolve(by_id, a))
    order = sorted(range(len(SHOTS)), key=lambda i: starts[i])
    if order != list(range(len(SHOTS))):
        bad = [(SHOTS[i]["at"], round(starts[i], 2)) for i in range(len(SHOTS))]
        raise SystemExit(f"shots out of time order: {bad}")

    def line_at(t):
        for l in lines:
            if l["start"] <= t < l["end"]:
                return l["id"]
        return lines[-1]["id"]

    shots, beat_runs, run = [], [], None
    for i, s in enumerate(SHOTS):
        t0 = round(round(starts[i] * FPS) / FPS, 6)
        t1 = round(round((starts[i + 1] if i + 1 < len(SHOTS) else end_of_film) * FPS) / FPS, 6)
        probe = t0 + (LEAD_FRAMES + 1) / FPS   # a cut leads its word by 2 frames; read the line it cuts for
        covered = sorted({line_at(probe)} | {l["id"] for l in lines if probe < l["start"] < t1})
        shot_claims = sorted(set(s["claims"]) | {c for lid in covered for c in claims.get(lid, [])})
        to_build = list(s["to_build"])
        source = {"kind": s["kind"], "name": s["name"]}
        if s["kind"] == "3d":
            scene = s["scene"]
            spec = catalog.get(scene)
            if spec is None and f"scene {scene}" not in " ".join(to_build):
                to_build.append(f"scene {scene}")
            v = s["view"]
            known = spec and ((v.startswith("at:") and v[3:] in spec["anchors"]) or v in spec["views"])
            if not known and not any(v in tb for tb in to_build):
                to_build.append(f"view {v}")
            if run is None or run["scene"] != scene or run["last"] != i - 1:
                run = {"scene": scene, "shots": [], "last": i, "t0": t0}
                beat_runs.append(run)
            run["last"] = i
            beat_name = f"v6-{len(beat_runs):02d}-{scene}"
            source.update(name=beat_name, view=v, **({"to": s["to"]} if s["to"] else {}))
            source["in"] = round(t0 - run["t0"], 6)
            run["shots"].append({"view": v, "start": source["in"], **({} if s["to"] else {"move": s["move"]}),
                                 **({"to": s["to"]} if s["to"] else {}), "note": s["note"]})
            run["name"] = beat_name
        else:
            source["in"] = 0.0
            if s["kind"] == "archive":
                source["frame"] = "archive_mat"      # still on the mat; credit on the mat, never on the picture
            if s["kind"] == "graphic":
                source["spec"] = {"type": dict(TYPE)}
        source["out"] = round(source["in"] + (t1 - t0), 6)
        tr_type, tr_dur = s["transition"]
        shot = {
            "id": f"s{i + 1:02d}", "start": t0, "end": t1,
            "start_anchor": ("line:" + s["at"][0]) if len(s["at"]) == 1 else
                            (f"word:{s['at'][1]}@{s['at'][0]}" + (f"#{s['at'][2]}" if len(s["at"]) > 2 and s["at"][1] != "+" else "")
                             if s["at"][1] != "+" else f"line:{s['at'][0]}:end"),
            "mode": s["mode"], "source": source, "speed": 1.0,
            "transition_in": {"type": tr_type, "dur": tr_dur},
            "overlays": [{"graphic": o["graphic"], "start": round(t0 + o["at"], 6),
                          "end": round((t0 + o["until"]) if o["until"] else t1, 6),
                          "spec": o["spec"], "provenance": o["provenance"]} for o in s["overlays"]],
            "audio": {"j_cut": {"sfx": "bell", "lead": 0.8}} if s["at"] == ("u015",) else {},
            "provenance": s["prov"], "claims": shot_claims, "lines": covered,
            "demonstrates": s["demonstrates"], "loop": s["loop"], "role": s["role"], "also": s["also"],
            "host": s["host"], "to_build": to_build, "note": s["note"],
        }
        shots.append(shot)

    cut = {"schema": "cutlist/1 (proposal)", "fps": FPS, "lead_frames": LEAD_FRAMES,
           "clock": {"basis": "v5 voice for kept lines; u003 and u005 estimated at "
                              f"{MEASURED_WPS} w/s + {SENTENCE_PAUSE} s per sentence end",
                     "duration": round(end_of_film, 3)},
           "lines": [{k: l[k] for k in ("id", "audio_from", "voiced", "text", "start", "end")} for l in lines],
           "lines_conservative": [{k: l[k] for k in ("id", "start", "end")} for l in cons],
           "words_new": {l["id"]: {"measured": l["words"], "conservative": c["words"]}
                         for l, c in zip(lines, cons) if not l["voiced"]},
           "shots": shots}
    (HERE / "cut.proposed.json").write_text(json.dumps(cut, indent=1, ensure_ascii=False), encoding="utf-8")

    beats = {}
    for r in beat_runs:
        b = {"scene": r["scene"], "shots": [{k: v for k, v in sh.items() if k != "note"} for sh in r["shots"]],
             "note": " | ".join(sh["note"] for sh in r["shots"])}
        beats[r["name"]] = b
    (HERE / "storyboard.proposed.json").write_text(
        json.dumps({"beats": beats}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(shots)} shots, {len(beats)} beats, film {end_of_film:.2f} s")


if __name__ == "__main__":
    main()
