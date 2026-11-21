"""Storyboard validation and timing: the gate between a plan and Blender.

A storyboard says, per beat, which catalog scene to build and what to show in it. Everything
it names must exist in workflow/scenes.json, so a plan that would crash or mis-aim in Blender
is rejected here, with a message the planner can repair from.

The timing rules (`when`, `default_shots`, `shot_starts`) live here too, without bpy, so the
Blender builder and the sound design read one definition of when each shot starts.
"""
import json
from pathlib import Path

CATALOG_PATH = Path(__file__).with_name("scenes.json")
MAX_LABEL = 32
BEAT_KEYS = {"scene", "params", "shots", "labels", "actions", "hud", "counter", "note", "cast", "cut"}
# how a beat without explicit shots is cut (default_shots below)
CUTS = {"travel", "montage", "steady"}
SHOT_SECONDS = 4.5          # cut "steady": a cut about this often
TRAVEL_SECONDS = 12.0       # cut "travel" (the default): one continuous camera move about this long
MONTAGE_LENGTHS = [1.4, 2.2, 1.2, 2.6, 1.6, 1.9]   # varied on purpose: uniform cut length is a slop tell
# pixel-art sprites a beat can stand in its set (tools/pixel/sprites.py)
CAST = {"explorer", "token", "dozing", "sleepy", "awake", "shocked", "bored", "asleep", "zzz", "mug", "truck"}
CAST_KEYS = {"who", "screen", "height", "shot", "hop", "walk", "flip", "word",
             # people who act and talk (tools/pixel/people.py, mirrored in workflow/sprites.json)
             "speaker", "pose", "face", "acts", "blink", "bust", "span"}
SHOT_KEYS = {"view", "to", "start", "glide", "move"}
MOVES = ("drift", "lock", "push", "pull")   # tools/blender/models/camera_plan.py
PEOPLE_PATH = Path(__file__).with_name("sprites.json")
LIP_MIN_HEIGHT = 0.18      # below this share of the frame a mouth is a pixel or two: it cannot be read


def load_people(path=PEOPLE_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else {"characters": {}}
TYPES = {"int": (int,), "number": (int, float), "string": (str,), "enum": (str,), "bool": (bool,)}


def load_catalog(path=CATALOG_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8"))["scenes"]


def when(spec, seconds, words, default=None, warn=None):
    """Resolve a time spec to seconds inside a beat of `seconds`: a fraction when <= 1.0, seconds
    when larger, or `word:<text>` looked up in `words` ([{"word", "start"}])."""
    if spec is None:
        return default
    if isinstance(spec, str):
        if spec.startswith("word:"):
            key = spec[5:].strip().lower()
            for w in words:
                if w["word"].strip(".,;:!?\"'").lower() == key:
                    return min(float(w["start"]), seconds - 0.5)
            if warn:
                warn(f"    WORD '{key}' not in word timing; using the default time")
            return default
        raise ValueError(f"unknown time spec {spec!r}")
    spec = float(spec)
    return spec * seconds if spec <= 1.0 else min(spec, seconds - 0.5)


def default_shots(sequence, anchors, seconds, cut):
    """Shots for a beat that names none, by its cutting style (`cut` in the storyboard).

    travel  - no cuts: the camera moves continuously from view to view (a move every ~12 s).
              The reference films explain a mechanism in one held, moving shot of 20-170 s.
    montage - quick cuts of 1.2-2.6 s between views and close-ups on anchors: hooks, tension.
    steady  - the old cadence, a cut every ~4.5 s."""
    if cut == "montage":
        pool = list(sequence) + [f"at:{a}" for a in anchors]
        shots, t, i = [], 0.0, 0
        while t < seconds - 0.8:
            shots.append({"view": pool[(i * 3) % len(pool)], "start": t})
            t += MONTAGE_LENGTHS[i % len(MONTAGE_LENGTHS)]
            i += 1
        return shots
    if cut == "steady":
        n = max(1, round(seconds / SHOT_SECONDS))
        return [{"view": sequence[i % len(sequence)]} for i in range(n)]
    moves = max(1, round(seconds / TRAVEL_SECONDS))
    path = [sequence[i % len(sequence)] for i in range(moves + 1)]
    if len(sequence) == 1:
        return [{"view": sequence[0]}]
    return [{"view": path[i], "to": path[i + 1]} for i in range(moves)]


def shot_starts(shots, seconds, words, warn=None):
    """Copies of `shots`, each with a `start` in seconds: the first at 0, an unset one spaced evenly."""
    out = []
    for i, shot in enumerate(shots):
        shot = dict(shot)
        start = when(shot.get("start"), seconds, words, default=None, warn=warn)
        shot["start"] = 0.0 if i == 0 else (start if start is not None else seconds * i / len(shots))
        out.append(shot)
    return out


def cut_of(name, beat, lengths):
    """How a beat is cut: "travel" (a held camera move), "montage", or "explicit" (hand-cut)."""
    shots = beat.get("shots") or []
    if not shots:
        return beat.get("cut", "travel")
    # a beat is a held move when one travelling shot carries most of it, even if a couple of quick
    # cutaways open or close it (the references cut into and out of their long moves)
    sec = float(lengths.get(name) or 0)

    def at(v, i):
        if i == 0:
            return 0.0
        return float(v) * sec if isinstance(v, (int, float)) and v <= 1.0 else float(v) if isinstance(v, (int, float)) else None
    starts = [at(sh.get("start"), i) for i, sh in enumerate(shots)]
    if sec <= 0 or any(x is None for x in starts):
        return "travel" if len(shots) == 1 and "to" in shots[0] else "explicit"
    ends = starts[1:] + [sec]
    held = max((e - st for st, e, sh in zip(starts, ends, shots) if "to" in sh), default=0.0)
    if held >= 0.6 * sec:
        return "travel"
    # a hand-cut montage: several shots, the typical one no longer than the longest montage cut
    spans = sorted(e - st for st, e in zip(starts, ends))
    if len(spans) >= 4 and spans[len(spans) // 2] <= max(MONTAGE_LENGTHS):
        return "montage"
    return "explicit"


# staging floors (references/staging.md sections 2, 3, 7)
MIN_SHOT = 1.0             # a shot shorter than this is a flash, not a shot
NEW_PLACE_MIN_SHOT = 4.0   # the shot that opens a new place needs time to orient the viewer
QUICK_SHOT = 2.5
QUICK_RUN_MAX = 4          # more than this many quick shots in a row outside a montage is a slide-show
ENTRY_LEAD = 0.5           # a speaker is in frame this long before the first word


def _shot_spans(beat, seconds, words):
    """-> [(start, end)] of the beat's shots; a beat naming none is one shot."""
    shots = beat.get("shots") or []
    if not shots:
        return [(0.0, seconds)]
    starts = [sh["start"] for sh in shot_starts(shots, seconds, words)]
    return list(zip(starts, starts[1:] + [seconds]))


def _covers(c, spans, seconds, words, t0, t1):
    """True when cast entry `c` is on screen over [t0, t1] of its beat."""
    if "shot" in c:
        i = c["shot"]
        return 0 <= i < len(spans) and spans[i][0] <= t0 + 1e-6 and spans[i][1] >= t1 - 1e-6
    span = c.get("span")
    if span:
        a = when(span[0], seconds, words, default=0.0)
        b = when(span[1], seconds, words, default=seconds)
        return a <= t0 + 1e-6 and b >= t1 - 1e-6
    return True


def staging_advice(storyboard, lines_by_beat, lengths, words_by_beat=None):
    """Advice, never errors: who is on screen when they speak, shot-length floors, the narrator's spot.
    `lines_by_beat` is mouth_timing.json ({beat: [{"uid", "speaker", "mode", "start", "end"}]})."""
    beats = storyboard.get("beats") or {}
    words_by_beat = words_by_beat or {}
    out = []
    previous = None
    narrator_sides = {}
    for name, beat in beats.items():
        seconds = float(lengths.get(name) or 0)
        if seconds <= 0:
            continue
        where = f"beat '{name}'"
        words = words_by_beat.get(name, [])
        spans = _shot_spans(beat, seconds, words)
        cast = beat.get("cast") or []
        # a. a character who talks must already be in frame
        for line in lines_by_beat.get(name, []):
            if line.get("speaker") == "narrator" or line.get("mode") != "say":
                continue
            t1 = float(line["start"])
            t0 = max(0.0, t1 - ENTRY_LEAD)
            mine = [c for c in cast if c.get("speaker") == line["speaker"]]
            if not any(_covers(c, spans, seconds, words, t0, min(t1, seconds)) for c in mine):
                out.append(f"{where}: '{line['speaker']}' speaks at {t1:.1f}s ({line.get('uid', '?')}) but is not in frame "
                           f"from {t0:.1f}s; cast them in the shot that is on screen {ENTRY_LEAD}s before the line")
        # b. (a speaking cast member under LIP_MIN_HEIGHT is already warned by validate)
        # c. shot-length floors
        for i, (a, b) in enumerate(spans):
            if b - a < MIN_SHOT:
                out.append(f"{where}: shot {i + 1} is {b - a:.1f}s, under {MIN_SHOT:.0f}s; lengthen it or merge it")
        shots = beat.get("shots") or []
        if shots and not str(shots[0].get("view", "")).startswith("at:") and previous is not None:
            new_place = (beat.get("scene"), beat.get("params") or {}) != (previous.get("scene"), previous.get("params") or {})
            if new_place and spans[0][1] - spans[0][0] < NEW_PLACE_MIN_SHOT:
                out.append(f"{where}: the shot that opens a new place is {spans[0][1] - spans[0][0]:.1f}s; give it "
                           f"{NEW_PLACE_MIN_SHOT:.0f}s or more so the viewer can find their feet")
        if beat.get("cut") != "montage" and cut_of(name, beat, lengths) != "montage":
            run = 0
            for i, (a, b) in enumerate(spans):
                run = run + 1 if b - a < QUICK_SHOT else 0
                if run == QUICK_RUN_MAX + 1:
                    out.append(f"{where}: more than {QUICK_RUN_MAX} shots in a row under {QUICK_SHOT}s outside a montage "
                               f"(from shot {i + 1 - QUICK_RUN_MAX}); hold some, or mark the beat \"cut\": \"montage\"")
        # d. the narrator keeps one spot
        for c in cast:
            if c.get("speaker") == "narrator" and c.get("bust") and isinstance(c.get("screen"), list):
                narrator_sides.setdefault("left" if c["screen"][0] < 0.5 else "right", []).append(name)
        previous = beat
    if len(narrator_sides) > 1:
        out.append("the narrator bust sits on both sides of the frame (" + "; ".join(
            f"{side}: {', '.join(sorted(set(names)))}" for side, names in sorted(narrator_sides.items())) +
            "); give the narrator one fixed spot for the whole film")
    return out


def _time_ok(value):
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return value >= 0
    return isinstance(value, str) and value.startswith("word:") and len(value) > 5


def _param_errors(where, scene, params, spec):
    errors = []
    for key, value in params.items():
        decl = spec["params"].get(key)
        if decl is None:
            errors.append(f"{where}: scene '{scene}' has no parameter '{key}' "
                          f"(has: {', '.join(spec['params']) or 'none'})")
            continue
        kind = decl["type"]
        is_list = kind.endswith("[]")
        base = kind[:-2] if is_list else kind
        if is_list and not isinstance(value, list):
            errors.append(f"{where}: parameter '{key}' must be a list")
            continue
        for item in (value if is_list else [value]):
            # True is an int to Python; only a bool parameter may take one
            if (isinstance(item, bool) != (base == "bool")) or not isinstance(item, TYPES[base]):
                errors.append(f"{where}: parameter '{key}' must be {kind}, got {item!r}")
                break
            if base == "enum" and item not in decl["values"]:
                errors.append(f"{where}: parameter '{key}' must be one of {decl['values']}, got {item!r}")
        if is_list and "max_items" in decl and len(value) > decl["max_items"]:
            errors.append(f"{where}: parameter '{key}' takes at most {decl['max_items']} items")
        if not is_list and base in ("int", "number") and isinstance(value, (int, float)):
            if ("min" in decl and value < decl["min"]) or ("max" in decl and value > decl["max"]):
                errors.append(f"{where}: parameter '{key}' must be in {decl.get('min', '-')}..{decl.get('max', '-')}")
    return errors


def validate(storyboard, catalog=None, lengths=None, cast=None, warnings=None):
    """-> list of error strings; empty means the storyboard may go to Blender. `cast` is the
    episode's script/cast.json (who may speak); advice goes to the `warnings` list when given."""
    catalog = catalog or load_catalog()
    people = load_people()
    actors = people.get("characters", {})
    warnings = warnings if warnings is not None else []
    beats = storyboard.get("beats") if isinstance(storyboard, dict) else None
    if not isinstance(beats, dict) or not beats:
        return ["storyboard needs a non-empty 'beats' object"]
    errors = []
    for name, beat in beats.items():
        where = f"beat '{name}'"
        if lengths is not None and name not in lengths:
            errors.append(f"{where}: no length in shot_lengths.json")
        unknown = set(beat) - BEAT_KEYS
        if unknown:
            errors.append(f"{where}: unknown keys {sorted(unknown)}")
        scene = beat.get("scene")
        spec = catalog.get(scene)
        if spec is None:
            errors.append(f"{where}: unknown scene '{scene}' (catalog: {', '.join(sorted(catalog))})")
            continue
        errors += _param_errors(where, scene, beat.get("params") or {}, spec)
        if "cut" in beat and beat["cut"] not in CUTS:
            errors.append(f"{where}: cut must be one of {sorted(CUTS)}, got {beat['cut']!r}")
        for i, shot in enumerate(beat.get("shots") or []):
            if set(shot) - SHOT_KEYS:
                errors.append(f"{where}: shot {i + 1} has unknown keys {sorted(set(shot) - SHOT_KEYS)}")
            if "move" in shot and shot["move"] not in MOVES:
                errors.append(f"{where}: shot {i + 1} move must be one of {list(MOVES)}, got {shot['move']!r}")
            if "glide" in shot and (shot["glide"] != "log" or "to" not in shot):
                errors.append(f"{where}: shot {i + 1} glide must be 'log' on a travelling shot (one with 'to')")
            if "to" in shot and shot["to"] not in spec["views"]:
                errors.append(f"{where}: shot {i + 1} travels to unknown view '{shot['to']}' "
                              f"(views: {', '.join(spec['views'])})")
            view = shot.get("view", "")
            if view.startswith("at:"):
                if view[3:] not in spec["anchors"]:
                    errors.append(f"{where}: shot {i + 1} closes in on unknown anchor '{view[3:]}'")
            elif view not in spec["views"]:
                errors.append(f"{where}: shot {i + 1} uses unknown view '{view}' (views: {', '.join(spec['views'])})")
            if "start" in shot and not _time_ok(shot["start"]):
                errors.append(f"{where}: shot {i + 1} has a bad start {shot['start']!r}")
        for label in beat.get("labels") or []:
            text = label.get("text", "")
            if not text or len(text) > MAX_LABEL:
                errors.append(f"{where}: label text must be 1-{MAX_LABEL} characters: {text!r}")
            if label.get("anchor") not in spec["anchors"]:
                errors.append(f"{where}: label '{text}' names unknown anchor '{label.get('anchor')}' "
                              f"(anchors: {', '.join(spec['anchors'])})")
            for key in ("at", "until"):
                if key in label and not _time_ok(label[key]):
                    errors.append(f"{where}: label '{text}' has a bad {key} {label[key]!r}")
        for action in beat.get("actions") or []:
            if action.get("name") not in spec["actions"]:
                errors.append(f"{where}: unknown action '{action.get('name')}' "
                              f"(actions: {', '.join(spec['actions']) or 'none'})")
            if "at" in action and not _time_ok(action["at"]):
                errors.append(f"{where}: action '{action.get('name')}' has a bad at {action['at']!r}")
        shots = beat.get("shots") or []
        for c in beat.get("cast") or []:
            who = c.get("who")
            if who not in CAST and who not in actors:
                errors.append(f"{where}: cast '{who}' is not a sprite (sprites: {', '.join(sorted(CAST | set(actors)))})")
            errors += _actor_errors(where, c, actors.get(who), people, cast, warnings)
            if set(c) - CAST_KEYS:
                errors.append(f"{where}: cast '{who}' has unknown keys {sorted(set(c) - CAST_KEYS)}")
            screen = c.get("screen")
            if not (isinstance(screen, list) and len(screen) == 2
                    and all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in screen)):
                errors.append(f"{where}: cast '{who}' needs 'screen' [u, v] within 0..1")
            h = c.get("height", 0.25)
            if not isinstance(h, (int, float)) or not 0.02 <= h <= 0.9:
                errors.append(f"{where}: cast '{who}' height must be 0.02..0.9 of the frame")
            if "shot" in c and not (isinstance(c["shot"], int) and 0 <= c["shot"] < max(1, len(shots))):
                errors.append(f"{where}: cast '{who}' names shot {c['shot']!r}, the beat has {max(1, len(shots))}")
            walk = c.get("walk")
            if walk is not None and not (isinstance(walk, list) and len(walk) == 2
                                         and all(isinstance(v, (int, float)) and -1 <= v <= 1 for v in walk)):
                errors.append(f"{where}: cast '{who}' walk must be [du, dv] within -1..1")
        counter = beat.get("counter")
        for h in (beat.get("hud") or []) + ([counter] if counter else []):
            screen = h.get("screen")
            if not (isinstance(screen, list) and len(screen) == 2
                    and all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in screen)):
                errors.append(f"{where}: hud/counter 'screen' must be [u, v] within 0..1")
        if counter:
            for key in ("template", "from", "to"):
                if key not in counter:
                    errors.append(f"{where}: counter needs '{key}'")
            if counter.get("curve") == "exp" and not counter.get("from"):
                errors.append(f"{where}: an exponential counter needs a non-zero 'from'")
    return errors


def _actor_errors(where, c, actor, people, cast, warnings):
    """The keys only acting people have: pose, face, acts, speaker, bust, span."""
    who = c.get("who")
    acting = {"speaker", "pose", "face", "acts", "blink", "bust", "span"} & set(c)
    if actor is None:
        return [f"{where}: cast '{who}' is a plain sprite and cannot take {sorted(acting)}"] if acting else []
    errors = []
    bust = bool(c.get("bust"))
    if bust and not actor.get("bust"):
        errors.append(f"{where}: cast '{who}' has no bust (close-up) drawing")
    poses = people["bust_poses"] if bust else actor["poses"]
    for ch in [c] + list(c.get("acts") or []):
        if "pose" in ch and ch["pose"] not in poses:
            errors.append(f"{where}: cast '{who}' pose {ch['pose']!r} is not one of {poses}")
        if "face" in ch and ch["face"] not in people["expressions"]:
            errors.append(f"{where}: cast '{who}' face {ch['face']!r} is not one of {people['expressions']}")
    for a in c.get("acts") or []:
        if not isinstance(a, dict) or "at" not in a or not _time_ok(a["at"]) or not ({"pose", "face"} & set(a)):
            errors.append(f"{where}: cast '{who}' acts entries need 'at' and a 'pose' or 'face'")
    span = c.get("span")
    if span is not None:
        if "shot" in c:
            errors.append(f"{where}: cast '{who}' takes either 'shot' or 'span', not both")
        if not (isinstance(span, list) and len(span) == 2 and all(_time_ok(v) for v in span)):
            errors.append(f"{where}: cast '{who}' span must be [from, until] times")
    speaker = c.get("speaker")
    if speaker is not None:
        if cast is not None and speaker not in cast and speaker != "narrator":
            errors.append(f"{where}: cast '{who}' speaks as '{speaker}', who is not in script/cast.json")
        if c.get("height", 0.25) < LIP_MIN_HEIGHT:
            warnings.append(f"{where}: '{who}' talks at {c.get('height', 0.25):.0%} of the frame; below "
                            f"{LIP_MIN_HEIGHT:.0%} the lips do not read, so give it a gesture instead")
    return errors


def load_episode(episode_dir):
    """-> (storyboard, lengths) for an episode folder."""
    episode_dir = Path(episode_dir)
    board = json.loads((episode_dir / "storyboard.json").read_text(encoding="utf-8"))
    lengths = json.loads((episode_dir / "shot_lengths.json").read_text(encoding="utf-8"))
    return board, lengths


if __name__ == "__main__":
    import sys
    problems = validate(*load_episode(sys.argv[1]))
    print("\n".join(problems) or "storyboard OK")
    sys.exit(1 if problems else 0)
