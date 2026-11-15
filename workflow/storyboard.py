"""Storyboard validation: the gate between a plan and Blender.

A storyboard says, per beat, which catalog scene to build and what to show in it. Everything
it names must exist in workflow/scenes.json, so a plan that would crash or mis-aim in Blender
is rejected here, with a message the planner can repair from.
"""
import json
from pathlib import Path

CATALOG_PATH = Path(__file__).with_name("scenes.json")
MAX_LABEL = 32
BEAT_KEYS = {"scene", "params", "shots", "labels", "actions", "hud", "counter", "note"}
TYPES = {"int": (int,), "number": (int, float), "string": (str,), "enum": (str,)}


def load_catalog(path=CATALOG_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8"))["scenes"]


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
            if isinstance(item, bool) or not isinstance(item, TYPES[base]):
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


def validate(storyboard, catalog=None, lengths=None):
    """-> list of error strings; empty means the storyboard may go to Blender."""
    catalog = catalog or load_catalog()
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
        for i, shot in enumerate(beat.get("shots") or []):
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
