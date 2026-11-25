"""The cut list: what is on screen when, on one film clock, cut on the words.

Before v6 the picture was one visual per narration line, joined with a stream copy: a cut could only
fall on a sentence boundary and nothing could cross one. A cut list states shots instead. Each shot
starts at an *anchor* — a line, a word inside a line, or plain seconds — and runs to the next
shot's start, so the timeline is gap-free by construction and survives re-voicing: a new take moves
the words, the anchors re-resolve, and every cut lands on the same word again.

**One clock, rounded once.** Every time is seconds on the film clock, measured from the first
sample of the narration master. Frames are derived, `frame(t) = round(t * fps)`, and every shot
boundary is snapped to a whole frame once, here, never per segment: the per-segment rounding of the
old assembler drifted the picture 0.65 s behind the voice by the tenth minute (see
`assemble_episode.build_segments`). Python's `round` is used on purpose — it is the rounding
`build_segments` uses, so an old episode converted by `legacy.py` keeps its boundaries to the frame.

**Cuts on words lead them.** A cut anchored on a word lands `lead_frames` (2) before the word's
onset, so the picture arrives just ahead of the sound — the house rule for a cut on meaning — and
never earlier than the start of the word's own line.

**Transitions are centred on the cut.** A transition of `d` seconds at cut `t` is a piece of
`n = round(d * fps)` frames over `[frame(t) - n // 2, frame(t) - n // 2 + n)`; the outgoing shot's
segment stops and the incoming shot's segment starts at the piece's edges. Shots never overlap; only
the transition windows straddle the cut. The incoming source therefore owes `n // 2` frames of
material before its first visible frame: the resolver gives each source a *head* that long, which
is why a beat's in-point can be a few frames past zero. The outgoing source owes the rest past its
cut, which `source_seconds_needed` publishes for the renderers.

**Archive screen time** is `end - start`: the shot as the viewer sees it, half of each transition
included, because the windows are centred on the cuts that bound it.

A *resolved* cut is what the assembler reads: every shot with `start`, `end`, `source.in`/`out`,
overlays on the film clock and the lines it plays over. `validate` checks it against the contract;
`render_plan` turns it into the frame ranges ffmpeg is asked for.
"""
import json
import math
import re
from pathlib import Path

SCHEMA = "cutlist/1"
DEFAULT_LEAD_FRAMES = 2

# Transition kinds and the durations each may take, in seconds. A match is a matched-framing cut:
# a hard cut (0) or a very short dissolve, never long enough to read as a dissolve proper.
TRANSITIONS = {
    "cut": (0.0, 0.0),
    "dissolve": (0.2, 1.0),
    "dip": (0.3, 1.2),
    "match": (0.0, 0.3),
}
# Layers whose clips this pipeline draws at whatever length it is asked for, so a transition
# handle can always be met by asking for more. Everything else has a fixed length on disk.
GENERATED_KINDS = ("graphic", "black", "cards")
EPS = 1e-6


# --- the clock ---------------------------------------------------------------------------------

def frame(t, fps):
    """The frame a film time falls on: rounded once, the way `build_segments` rounds."""
    return round(t * fps)


def snap(t, fps):
    """A film time moved onto its frame, kept as seconds to six places."""
    return frame(t, fps) / fps


def words_from_alignment(path):
    """`[(word, start, end)]` relative to the line's own audio, from an ElevenLabs alignment.

    Bracketed directions (`[curious]`, `[sad]`) are performance notes, not words, and are skipped
    with whatever sits inside them.
    """
    a = json.loads(Path(path).read_text(encoding="utf-8"))["alignment"]
    chars = a["characters"]
    starts, ends = a["character_start_times_seconds"], a["character_end_times_seconds"]
    out, cur, start, end, depth = [], "", None, None, 0
    for ch, s, e in zip(chars, starts, ends):
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


def line_clock(manifest, vo_dir):
    """The narration as lines on the film clock, each with its words, from the voice on disk.

    Placed by the manifest's `startSample`/`endSample` at its own `sampleRate` (a running sum when
    a manifest predates those fields); words come from `vo/<id>.align.json` when it exists.
    """
    rate = int(manifest["sampleRate"])
    lines, clock = [], 0
    for u in manifest["utterances"]:
        begin = u.get("startSample", clock)
        clock = u.get("endSample", begin + u["samples"])
        start, end = begin / rate, clock / rate
        align = Path(vo_dir) / f"{u['id']}.align.json"
        words = words_from_alignment(align) if align.is_file() else []
        lines.append({"id": u["id"], "start": start, "end": end, "text": u.get("text", ""),
                      "words": [{"w": w, "s": start + s, "e": start + e} for w, s, e in words]})
    return lines


def _norm(word):
    return re.sub(r"[^a-z0-9']", "", word.lower().replace("’", "'"))


_WORD = re.compile(r"^word:(?P<w>[^@]+)@(?P<uid>u\d+)(?:#(?P<n>\d+))?(?P<end>:end)?$")
_LINE = re.compile(r"^line:(?P<uid>u\d+)(?P<end>:end)?$")


def resolve_anchor(anchor, lines_by_id, *, fps, lead_frames=DEFAULT_LEAD_FRAMES):
    """Seconds on the film clock for an anchor; an anchor that misses the voice is an error.

    `line:u004` / `line:u004:end` — a line's first or last sample.
    `word:which@u004` / `word:the@u014#2` / `word:six@u003:end` — the onset of the (nth) matching
    word, less the lead; or the end of that word, with no lead.
    A number — seconds, as given.
    """
    if isinstance(anchor, (int, float)):
        return float(anchor)
    m = _LINE.match(anchor)
    if m:
        line = _line(lines_by_id, m["uid"], anchor)
        return line["end"] if m["end"] else line["start"]
    m = _WORD.match(anchor)
    if not m:
        raise ValueError(f"anchor {anchor!r} is not line:uNNN[:end], word:<w>@uNNN[#n][:end] or seconds")
    line = _line(lines_by_id, m["uid"], anchor)
    target, nth = _norm(m["w"]), int(m["n"] or 1)
    hits = [w for w in line["words"] if _norm(w["w"]) == target]
    if len(hits) < nth:
        said = " ".join(w["w"] for w in line["words"]) or "(no alignment)"
        raise ValueError(f"anchor {anchor!r}: {m['w']!r} occurs {len(hits)}x in {m['uid']}, "
                         f"which says: {said}")
    word = hits[nth - 1]
    if m["end"]:
        return word["e"]
    return max(line["start"], word["s"] - lead_frames / fps)


def _line(lines_by_id, uid, anchor):
    if uid not in lines_by_id:
        raise ValueError(f"anchor {anchor!r} names {uid}, which is not in the narration")
    return lines_by_id[uid]


# --- resolving an authored cut -----------------------------------------------------------------

def _transition(shot):
    tr = shot.get("transition_in") or {"type": "cut", "dur": 0.0}
    return {"type": tr.get("type", "cut"), "dur": float(tr.get("dur", 0.0))}


def window_frames(dur, fps):
    """Frames in a transition window of `dur` seconds (0 for a cut)."""
    return int(round(dur * fps))


def resolve(authored, lines):
    """Place every authored shot on the film clock and give each source its in-point.

    `authored` holds `fps`, `lead_frames`, `tail` (seconds of picture after the last line) and
    `shots`, each with a `start_anchor`, a `source` and optional `transition_in`, `overlays`
    (`at`/`until` in seconds from the shot's start; no `until` runs to the shot's end), `audio`,
    `speed`, `provenance` and whatever directing fields it carries, which pass through untouched.

    A source's in-point, when not given, is its place in the run of consecutive shots on the same
    source — two shots on one beat are two slices of one camera move — plus the head the run's
    first transition owes. The returned cut is a new object; the authored one is not modified.
    """
    fps = int(authored["fps"])
    lead = int(authored.get("lead_frames", DEFAULT_LEAD_FRAMES))
    by_id = {l["id"]: l for l in lines}
    duration = snap(lines[-1]["end"] + float(authored.get("tail", 0.0)), fps) if lines else 0.0

    starts = [snap(resolve_anchor(s["start_anchor"], by_id, fps=fps, lead_frames=lead), fps)
              for s in authored["shots"]]
    bad = [i for i in range(1, len(starts)) if starts[i] < starts[i - 1]]
    if bad:
        i = bad[0]
        raise ValueError(f"shots out of time order: shot {i + 1} ({authored['shots'][i]['start_anchor']!r}"
                         f" at {starts[i]:.3f}s) comes before shot {i} at {starts[i - 1]:.3f}s")

    shots, run_name, run_t0 = [], None, 0.0
    heads = {}
    for i, (a, t0) in enumerate(zip(authored["shots"], starts)):
        t1 = starts[i + 1] if i + 1 < len(starts) else duration
        source = dict(a["source"])
        tr = _transition(a)
        if source["name"] != run_name:
            run_name, run_t0 = source["name"], t0
            head = window_frames(tr["dur"], fps) // 2 / fps if tr["type"] != "cut" else 0.0
            heads[i] = head
        else:
            head = heads[max(k for k in heads if k <= i)]
        if "in" not in source:
            source["in"] = head + (t0 - run_t0)
        # a held move through several views: each waypoint reached at its own anchor (film clock)
        if source.get("via"):
            source["via"] = [{**w, "t": snap(resolve_anchor(w["at"], by_id, fps=fps, lead_frames=lead), fps)}
                             for w in source["via"]]
            ts = [t0] + [w["t"] for w in source["via"]]
            if any(b <= a for a, b in zip(ts, ts[1:])) or ts[-1] >= t1:
                raise ValueError(f"shot {i + 1}: its waypoints {[w['view'] for w in source['via']]} are not "
                                 f"in time order inside {t0:.2f}-{t1:.2f}s")
        # beat parameters that are moments in the film (a walk that starts on a word), as film times
        if source.get("at_params"):
            source["params_t"] = {k: snap(resolve_anchor(v, by_id, fps=fps, lead_frames=lead), fps)
                                  for k, v in source["at_params"].items()}
        source["out"] = source["in"] + (t1 - t0) * float(a.get("speed", 1.0))
        shot = {k: v for k, v in a.items() if k not in ("source", "overlays", "transition_in")}
        shot.update(id=a.get("id") or f"s{i + 1:02d}", start=t0, end=t1, source=source,
                    transition_in=tr, speed=float(a.get("speed", 1.0)),
                    overlays=[_place_overlay(o, t0, t1, fps) for o in a.get("overlays", [])],
                    lines=_lines_over(lines, t0, t1, lead, fps))
        shots.append(shot)

    out = {k: v for k, v in authored.items() if k != "shots"}
    out.update(schema=SCHEMA, fps=fps, lead_frames=lead, duration=duration, shots=shots)
    return out


def _place_overlay(o, t0, t1, fps):
    placed = {k: v for k, v in o.items() if k not in ("at", "until")}
    if "start" in o:                         # already on the film clock
        placed["start"], placed["end"] = o["start"], o.get("end", t1)
        return placed
    placed["start"] = snap(t0 + float(o.get("at", 0.0)), fps)
    until = o.get("until")
    placed["end"] = t1 if until is None else snap(t0 + float(until), fps)
    return placed


def _lines_over(lines, t0, t1, lead, fps):
    """The lines a shot plays over: the one under its first word, and every line starting inside it."""
    probe = t0 + (lead + 1) / fps
    hit = [l["id"] for l in lines if l["start"] <= probe < l["end"]]
    inside = [l["id"] for l in lines if probe < l["start"] < t1]
    return sorted(set(hit or [lines[-1]["id"]] if lines and t0 >= lines[-1]["start"] else hit) | set(inside))


# --- validation --------------------------------------------------------------------------------

def screen_seconds(shot):
    """How long a shot is on screen: between its cuts, half of each transition included."""
    return shot["end"] - shot["start"]


def card_hold(shot, contract):
    """Seconds the source card stays up: the contract's hold, or the whole shot if shorter."""
    return min(float(contract["archive"]["source_card"]["seconds"]), screen_seconds(shot))


def _finding(code, shot, message):
    return {"code": code, "shot": shot.get("id") if shot else None, "message": message}


def validate(cut, contract, *, source_seconds=None):
    """Every way a resolved cut can be wrong, as findings `{code, shot, message}`; empty is clean.

    `source_seconds` optionally maps a source name to the seconds its file on disk holds, for the
    handle check on layers this run cannot simply render longer (an archival clip, a 3D beat
    already rendered).
    """
    fps = int(cut["fps"])
    shots = cut["shots"]
    out = []
    bound = float(contract["archive"]["archive_rhythm"]["max_archival_shot_seconds"])
    if not shots:
        return [_finding("empty", None, "the cut has no shots")]
    if abs(shots[0]["start"]) > EPS:
        out.append(_finding("gap", shots[0], f"the film starts at {shots[0]['start']:.3f}s, not 0"))
    if "duration" in cut and abs(shots[-1]["end"] - cut["duration"]) > EPS:
        out.append(_finding("gap" if shots[-1]["end"] < cut["duration"] else "overlap", shots[-1],
                            f"the last shot ends at {shots[-1]['end']:.3f}s, the film at {cut['duration']:.3f}s"))
    for a, b in zip(shots, shots[1:]):
        if b["start"] - a["end"] > EPS:
            out.append(_finding("gap", b, f"{a['end']:.3f}s to {b['start']:.3f}s is not covered"))
        elif a["end"] - b["start"] > EPS:
            out.append(_finding("overlap", b, f"{a['id']} runs to {a['end']:.3f}s past {b['id']}'s start"))

    for s in shots:
        for t in (s["start"], s["end"]):
            if abs(t * fps - round(t * fps)) > 1e-4:
                out.append(_finding("off_frame", s, f"{t}s is not on a frame at {fps} fps"))
        if frame(s["end"], fps) - frame(s["start"], fps) < 2:
            out.append(_finding("too_short", s, f"{s['id']} is {screen_seconds(s):.3f}s, under 2 frames"))
        if not s.get("provenance"):
            out.append(_finding("provenance", s, f"{s['id']} has no provenance tag"))
        kind = s["source"]["kind"]
        if kind == "archive":
            if screen_seconds(s) > bound + EPS:
                out.append(_finding("archive_long", s, f"{s['source']['name']} is on screen "
                                    f"{screen_seconds(s):.2f}s, over the {bound:.1f}s bound"))
            if abs(s.get("speed", 1.0) - 1.0) > EPS:
                out.append(_finding("archive_speed", s, "archival material is never retimed"))
        tr = s["transition_in"]
        lo_hi = TRANSITIONS.get(tr["type"])
        if lo_hi is None or not (lo_hi[0] - EPS <= tr["dur"] <= lo_hi[1] + EPS):
            out.append(_finding("transition", s, f"{tr['type']} of {tr['dur']}s is outside "
                                f"{TRANSITIONS.get(tr['type'], 'the known kinds')}"))
        for o in s.get("overlays", []):
            if o["start"] < s["start"] - EPS or o["end"] > s["end"] + EPS or o["end"] <= o["start"]:
                out.append(_finding("overlay_outside", s, f"{o.get('graphic')} at {o['start']:.3f}-"
                                    f"{o['end']:.3f}s is not inside {s['start']:.3f}-{s['end']:.3f}s"))

    runs, last = {}, None
    for s in shots:
        name = s["source"]["name"]
        if name != last:
            runs[name] = runs.get(name, 0) + 1
            if runs[name] == 2 and s["source"]["kind"] == "3d":
                out.append(_finding("beat_reused", s, f"3D beat {name} returns after another source; "
                                    "give the reprise its own beat name so its clock is its own"))
        last = name

    try:
        plan = render_plan(cut)
    except ValueError as e:
        out.append(_finding("transition_overlap", None, str(e)))
        plan = []
    for p in plan:
        if p["frames"][1] < p["frames"][0]:
            out.append(_finding("transition_overlap", None, f"{p.get('shot')} is eaten by its transitions"))
    if source_seconds:
        needed = source_seconds_needed(cut)
        kinds = {s["source"]["name"]: s["source"]["kind"] for s in shots}
        for name, need in needed.items():
            have = source_seconds.get(name)
            if have is not None and kinds.get(name) not in GENERATED_KINDS and need > have + EPS:
                out.append(_finding("handle", None, f"{name} holds {have:.3f}s but the cut reads it "
                                    f"to {need:.3f}s (transition handles included)"))
        for s in shots:
            if s["source"]["in"] < -EPS:
                out.append(_finding("handle", s, f"{s['id']} reads {s['source']['name']} before its start"))
    return out


# --- what to render ----------------------------------------------------------------------------

def _src_time(shot, f, fps):
    return shot["source"]["in"] + (f / fps - shot["start"]) * shot.get("speed", 1.0)


def _src_ref(shot, f, fps):
    s = shot["source"]
    return {"kind": s["kind"], "name": s["name"], "seek": _src_time(shot, f, fps), "shot": shot["id"]}


def render_plan(cut):
    """The film as abutting pieces of whole frames: shot segments and transition pieces.

    Each piece is `{kind: segment|transition, frames: (first, end)}`. A segment also names its
    shot, its source and the source time of its first frame (`seek`) and carries its overlays on
    segment-local frames; a transition names its `type` and both sides (`out`, `in`) with their
    own seeks. Raises ValueError if two transition windows collide.
    """
    fps = int(cut["fps"])
    shots = cut["shots"]
    windows = []                          # (first, end) of the transition into shot i, or None
    for s in shots:
        tr = s["transition_in"]
        n = window_frames(tr["dur"], fps) if tr["type"] != "cut" else 0
        if n == 0:
            windows.append(None)
            continue
        f = frame(s["start"], fps)
        windows.append((f - n // 2, f - n // 2 + n))

    plan = []
    for i, s in enumerate(shots):
        f0 = windows[i][1] if windows[i] else frame(s["start"], fps)
        nxt = windows[i + 1] if i + 1 < len(shots) else None
        f1 = nxt[0] if nxt else frame(s["end"], fps)
        if windows[i]:
            if i == 0:
                raise ValueError(f"{s['id']} opens the film with a transition from nothing")
            prev = shots[i - 1]
            if plan and plan[-1]["frames"][0] > windows[i][0]:
                raise ValueError(f"the transition into {s['id']} starts before {prev['id']}'s segment "
                                 "does: two transition windows overlap")
            plan.append({"kind": "transition", "type": s["transition_in"]["type"], "frames": windows[i],
                         "out": _src_ref(prev, windows[i][0], fps), "in": _src_ref(s, windows[i][0], fps),
                         "shot": s["id"]})
        if f1 < f0:
            raise ValueError(f"{s['id']} is eaten by its transitions ({f0} > {f1})")
        overlays = []
        for o in s.get("overlays", []):
            a, b = max(frame(o["start"], fps), f0), min(frame(o["end"], fps), f1)
            if b > a:
                overlays.append({**o, "frames": (a - f0, b - f0), "local": (frame(o["start"], fps), a)})
        plan.append({"kind": "segment", "frames": (f0, f1), "shot": s["id"], "source": s["source"],
                     "seek": _src_time(s, f0, fps), "speed": s.get("speed", 1.0), "overlays": overlays})
    return plan


def source_seconds_needed(cut):
    """Seconds of material each source must hold: the furthest any segment or transition reads it."""
    fps = int(cut["fps"])
    by_id = {s["id"]: s for s in cut["shots"]}
    need = {}

    def reach(name, t):
        need[name] = max(need.get(name, 0.0), t)

    for p in render_plan(cut):
        if p["kind"] == "segment":
            s = by_id[p["shot"]]
            reach(s["source"]["name"], _src_time(s, p["frames"][1], fps))
        else:
            out_shot = by_id[p["out"]["shot"]]
            reach(out_shot["source"]["name"], _src_time(out_shot, p["frames"][1], fps))
    return need


def beat_shots(cut):
    """The shots inside each 3D beat on the beat's own clock, for the storyboard the renderer reads.

    A beat's first shot starts at 0 (its head is just extra length at the front); every later shot
    starts at its in-point. A shot with a `to` view travels there and carries no `move`.
    """
    beats = {}
    for s in cut["shots"]:
        src = s["source"]
        if src["kind"] != "3d":
            continue
        entries = beats.setdefault(src["name"], [])
        start = 0.0 if not entries else src["in"]
        if src.get("via"):
            # one continuous move: a travel from each waypoint to the next, then the last view held
            points = [(src.get("view"), s["start"])] + [(w["view"], w["t"]) for w in src["via"]]
            for k, (view, t) in enumerate(points):
                entry = {"view": view, "start": start if k == 0 else src["in"] + (t - s["start"])}
                if k + 1 < len(points):
                    entry["to"] = points[k + 1][0]
                else:
                    entry["move"] = src.get("move", "push")
                entries.append(entry)
            continue
        entry = {"view": src.get("view"), "start": start}
        if src.get("to"):
            entry["to"] = src["to"]
        elif src.get("move"):
            entry["move"] = src["move"]
        if not entries or entries[-1] != entry:
            entries.append(entry)
    return beats


def beat_params(cut):
    """`{beat: {param: seconds on the beat's clock}}` for the `at_params` a cut's 3D shots carry."""
    out = {}
    for s in cut["shots"]:
        src = s["source"]
        if src["kind"] == "3d" and src.get("params_t"):
            origin = s["start"] - src["in"]
            out.setdefault(src["name"], {}).update({k: t - origin for k, t in src["params_t"].items()})
    return out


def audio_events(cut):
    """Sounds the cut schedules off its pictures: a J-cut is heard before its shot, an L-cut after."""
    events = []
    for s in cut["shots"]:
        audio = s.get("audio") or {}
        if "j_cut" in audio:
            j = audio["j_cut"]
            events.append({"sfx": j["sfx"], "at": round(s["start"] - float(j["lead"]), 6),
                           "shot": s["id"], "kind": "j_cut"})
        if "l_cut" in audio:
            l = audio["l_cut"]
            events.append({"sfx": l["sfx"], "at": s["start"],
                           "until": round(s["end"] + float(l["lag"]), 6), "shot": s["id"], "kind": "l_cut"})
    return events


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def episode_cut(episode):
    """An episode's cut.json resolved against its voice on disk, or None without a cut list.

    For the stages that run before the assembler publishes `cut.resolved.json` (captions, mouths,
    the storyboard check) and need to know where each beat sits on the film clock now.
    """
    episode = Path(episode)
    if not (episode / "cut.json").is_file():
        return None
    manifest = load(episode / "vo" / "manifest.json")
    return resolve(load(episode / "cut.json"), line_clock(manifest, episode / "vo"))


def beat_spans(cut):
    """`{beat: {origin, start, end, lines}}` for each 3D beat: where its own clock's 0 is on the film.

    `origin` is the film time of the beat's frame 0 (its first shot's start less that shot's
    in-point), so a beat-relative time `b` is film time `origin + b` — the conversion word timing and
    mouth timing need to place a word inside a render.
    """
    out = {}
    for s in cut["shots"]:
        src = s["source"]
        if src["kind"] != "3d":
            continue
        span = out.get(src["name"])
        if span is None:
            out[src["name"]] = {"origin": s["start"] - src["in"], "start": s["start"], "end": s["end"],
                                "lines": list(s.get("lines", []))}
        else:
            span["end"] = s["end"]
            span["lines"] += [l for l in s.get("lines", []) if l not in span["lines"]]
    return out
