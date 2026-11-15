"""Generic beat builder: renders any episode from its storyboard, with no episode-specific Python.

    blender -b -P tools/blender/storyboard_beats.py -- --episode work/jensen-huang
    blender -b -P tools/blender/storyboard_beats.py -- --episode work/jensen-huang --beat riva-chip --force
    blender -b -P tools/blender/storyboard_beats.py -- --episode work/jensen-huang --still 0.3 --still 0.8 --out qc/stills
    blender -b -P tools/blender/storyboard_beats.py -- --catalog out.json     # what the scene code really offers

Inputs, both under the episode folder:
  storyboard.json    {"beats": {name: {scene, params, shots, labels, actions, hud, counter}}}
  shot_lengths.json  {name: seconds}
Optional: word_timing.json {name: [{"word": "...", "start": seconds}]} resolves `word:<text>` times.

Times (`at`, `start`, `until`) are a fraction of the beat when <= 1.0 (and a float), seconds when
larger, or the string `word:<text>`. Validation lives in workflow/storyboard.py; this file trusts it
but still reports (never hides) anything that does not frame.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / "models"))

import kit  # noqa: E402
import look  # noqa: E402
import scenes  # noqa: E402
from kit import FPS  # noqa: E402

SHOT_SECONDS = 4.5          # a cut about this often unless the storyboard says otherwise
DRIFT_RADIUS = 0.94
DRIFT_AZIMUTH = 7.0
CLOSE_RADIUS = 4.6


def when(spec, seconds, words, default=None):
    """Resolve a time spec to seconds inside a beat of `seconds`."""
    if spec is None:
        return default
    if isinstance(spec, str):
        if spec.startswith("word:"):
            key = spec[5:].strip().lower()
            for w in words:
                if w["word"].strip(".,;:!?\"'").lower() == key:
                    return min(float(w["start"]), seconds - 0.5)
            print(f"    WORD '{key}' not in word timing; using the default time")
            return default
        raise ValueError(f"unknown time spec {spec!r}")
    spec = float(spec)
    return spec * seconds if spec <= 1.0 else min(spec, seconds - 0.5)


def plan_shots(scene, spec, seconds, words):
    """-> [{"start", "view"|"close", ...}] with a start for every shot, in time order."""
    sequence = list(scene.sequence)
    shots = spec.get("shots")
    if not shots:
        n = max(1, round(seconds / SHOT_SECONDS))
        shots = [{"view": sequence[i % len(sequence)]} for i in range(n)]
    out = []
    for i, shot in enumerate(shots):
        shot = dict(shot)
        start = when(shot.get("start"), seconds, words, default=None)
        shot["start"] = 0.0 if i == 0 else (start if start is not None else seconds * i / len(shots))
        out.append(shot)
    return out


def apply_forced(plan, forced, seconds):
    """Give each (start, anchor) its own close-up shot of ~2.4 s, then return to the view that was
    running; shots that began inside that stretch are dropped."""
    for start, anchor in sorted(forced):
        t0, t1 = max(0.0, start - 0.1), min(seconds, start + 2.3)
        cover = max((s for s in plan if s["start"] <= t1), key=lambda s: s["start"])
        back = {"view": cover.get("view"), "start": t1}
        plan = [s for s in plan if not (t0 < s["start"] <= t1)]
        if t0 <= 0.0:
            plan[0] = {"view": f"at:{anchor}", "start": 0.0}
        else:
            plan.append({"view": f"at:{anchor}", "start": t0})
        if t1 < seconds - 0.8 and not any(t1 < s["start"] < t1 + 0.8 for s in plan):
            plan.append(back)
        plan.sort(key=lambda s: s["start"])
    return plan


def view_to_shot(scene, shot, index, previous):
    """Turn a planned shot into the dict `look.shoot` takes, with a slow drift."""
    sign = 1.0 if index % 2 == 0 else -1.0
    name = shot.get("view", "")
    if name.startswith("at:"):
        pin = scene.pins[name[3:]]
        bpy.context.scene.frame_set(max(1, round((shot["start"] + 1.0) * FPS)))
        bpy.context.view_layer.update()
        target = tuple(pin.matrix_world.translation)
        base = previous or next(iter(scene.views.values()))
        radius, azimuth, height = CLOSE_RADIUS, base["azimuth"] + 18.0 * sign, target[2] + 2.2
    else:
        v = scene.views[name]
        target, radius, azimuth, height = v["target"], v["radius"], v["azimuth"], v["height"]
    return {"start": shot["start"], "target": tuple(target),
            "radius": (radius, radius * DRIFT_RADIUS),
            "azimuth": (azimuth, azimuth + DRIFT_AZIMUTH * sign),
            "height": (height, height)}, {"target": target, "radius": radius, "azimuth": azimuth, "height": height}


def ink(h):
    """Colour options of a HUD entry: {"color": "warm"|"cool"} makes it glow."""
    if h.get("color") == "warm":
        return {"color": look.WARM, "strength": 2.2}
    if h.get("color") == "cool":
        return {"color": look.COOL, "strength": 2.2}
    return {}


def build_beat(name, spec, seconds, words, forced=()):
    """forced: [(start_seconds, anchor)] — the shot running then becomes a close-up on that anchor."""
    frames = look.open_set(seconds)
    scene = scenes.SCENES[spec["scene"]](spec.get("params") or {}, seconds)
    plan = plan_shots(scene, spec, seconds, words)
    plan = apply_forced(plan, forced, seconds)
    shots, previous = [], None
    for i, shot in enumerate(plan):
        entry, previous = view_to_shot(scene, shot, i, previous)
        shots.append(entry)
    st = look.shoot(shots, lens=scene.lens, floor_z=scene.floor_z, floor_grid=scene.floor_grid, gain=scene.gain)
    st.offscreen = []

    overrides = {a["name"]: a for a in spec.get("actions", [])}
    for action, (fn, at, span) in scene.actions.items():
        t0 = when(overrides.get(action, {}).get("at"), seconds, words, default=at * seconds)
        t0 = max(0.0, min(t0, seconds - span))
        fn(t0, t0 + span)

    bounds = [(s["start"], plan[i + 1]["start"] if i + 1 < len(plan) else seconds) for i, s in enumerate(plan)]
    for label in spec.get("labels", []):
        start = when(label.get("at"), seconds, words, default=0.3 * seconds)
        end = next((e for s, e in bounds if s <= start < e), seconds)
        until = when(label.get("until"), seconds, words, default=end if end < seconds else None)
        pin = scene.pins.get(label["anchor"])
        if pin is None:
            st.problems.append(f"label '{label['text']}': scene '{spec['scene']}' has no anchor '{label['anchor']}'")
            continue
        if look.auto_tag(st, label["text"], pin, start=start, until=until) is None and "off screen" in st.problems[-1]:
            st.offscreen.append((start, label["anchor"]))

    for h in spec.get("hud", []):
        look.hud_text(st, h["text"], tuple(h["screen"]), size=h.get("size", 0.05),
                      start=when(h.get("at"), seconds, words, default=0.0),
                      until=when(h.get("until"), seconds, words, default=None), **ink(h))
        look.reserve(st, (h["screen"][0] - 0.18, h["screen"][1] - 0.06, h["screen"][0] + 0.18, h["screen"][1] + 0.06),
                     1, frames)
    c = spec.get("counter")
    if c:
        t0 = when(c.get("start"), seconds, words, default=0.0)
        t1 = when(c.get("end"), seconds, words, default=seconds)
        text = look.hud_text(st, c["template"].format(int(c["from"])), tuple(c["screen"]),
                             size=c.get("size", 0.07), start=t0, **ink(c))
        if c.get("curve") == "exp":
            value = lambda t: c["from"] * (c["to"] / c["from"]) ** t
        else:
            value = lambda t: c["from"] + (c["to"] - c["from"]) * t * t * (3 - 2 * t)
        look.counter(text, t0, t1, value, c["template"])
        look.reserve(st, (c["screen"][0] - 0.2, c["screen"][1] - 0.07, c["screen"][0] + 0.2, c["screen"][1] + 0.07),
                     1, frames)
    st.scene_set = scene
    return st


def build_beat_framed(name, spec, seconds, words):
    """Build a beat; where a label's anchor is off screen in its shot, cut to a close-up on it
    and build again (twice at most). Whatever still fails is left in `st.problems`."""
    forced = []
    for _ in range(3):
        st = build_beat(name, spec, seconds, words, forced)
        fresh = [f for f in st.offscreen if f not in forced]
        if not fresh:
            return st
        forced += fresh
    return st


def dump_catalog(path):
    """Build every scene with default parameters and write what it offers: the ground truth the
    data catalog (workflow/scenes.json) is compared with."""
    catalog_path = PROJECT_ROOT / "workflow" / "scenes.json"
    declared = json.loads(catalog_path.read_text(encoding="utf-8"))["scenes"] if catalog_path.exists() else {}
    out = {}
    for name, fn in scenes.SCENES.items():
        found = {"views": [], "anchors": set(), "actions": set()}
        for params in declared.get(name, {}).get("examples") or [{}]:
            look.open_set(6)
            s = fn(dict(params), 6)
            found["views"] += [v for v in s.views if v not in found["views"]]
            found["anchors"] |= set(s.pins)
            found["actions"] |= set(s.actions)
        out[name] = {"views": found["views"], "anchors": sorted(found["anchors"]), "actions": sorted(found["actions"])}
    Path(path).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"catalog of {len(out)} scenes -> {path}")


def configure_video(scene, out_path):
    scene.eevee.taa_render_samples = 24
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    scene.render.ffmpeg.audio_codec = "NONE"
    scene.render.filepath = str(out_path)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", type=Path)
    ap.add_argument("--catalog", type=Path, help="write the scene catalog the code offers and exit")
    ap.add_argument("--beat", action="append")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--still", type=float, action="append")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)

    if args.catalog:
        dump_catalog(args.catalog)
        return
    episode = args.episode if args.episode.is_absolute() else PROJECT_ROOT / args.episode
    board = json.loads((episode / "storyboard.json").read_text(encoding="utf-8"))["beats"]
    lengths = json.loads((episode / "shot_lengths.json").read_text(encoding="utf-8"))
    timing_path = episode / "word_timing.json"
    timing = json.loads(timing_path.read_text(encoding="utf-8")) if timing_path.exists() else {}

    sys.path.insert(0, str(PROJECT_ROOT))
    from workflow import storyboard as validator
    refused = validator.validate({"beats": board}, validator.load_catalog(), lengths)
    if refused:
        raise SystemExit("storyboard refused before any scene was built:
  " + "
  ".join(refused))

    names = args.beat or [n for n in board if n in lengths]
    unknown = [n for n in names if n not in board]
    if unknown:
        raise SystemExit(f"not in storyboard: {', '.join(unknown)}")
    out_dir = args.out or (episode / "renders" / "3d")
    if not out_dir.is_absolute():
        out_dir = PROJECT_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    for idx, name in enumerate(names):
        seconds = lengths[name]
        t0 = time.time()
        if args.still:
            st = build_beat_framed(name, board[name], seconds, timing.get(name, []))
            bpy.context.scene.render.resolution_percentage = 50
            for frac in args.still:
                frame = max(1, round(frac * seconds * FPS))
                kit.common.render_still(frame, out_dir / f"{name}-{round(frac * 100):03d}.png", samples=16)
            for line in st.problems:
                print(f"    FRAMING {name}: {line}")
            print(f"  [{idx + 1}/{len(names)}] {name} stills in {time.time() - t0:.1f}s")
            continue
        out_path = out_dir / f"{name}.mp4"
        if out_path.exists() and out_path.stat().st_size > 0 and not args.force:
            print(f"  [{idx + 1}/{len(names)}] {name} already rendered, skipping")
            continue
        print(f"  [{idx + 1}/{len(names)}] {name} ({seconds}s = {seconds * FPS} frames)...")
        st = build_beat_framed(name, board[name], seconds, timing.get(name, []))
        for line in st.problems:
            print(f"    FRAMING {name}: {line}")
        configure_video(bpy.context.scene, out_path)
        bpy.ops.render.render(animation=True)
        print(f"    done in {time.time() - t0:.1f}s")
    print(f"{len(names)} beats -> {out_dir}")


main()
