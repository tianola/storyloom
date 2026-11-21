"""Sound design read off the storyboard: what the picture does, the track does too.

    python tools/sound_design.py --episode work/X        # prints the events it would lay

The reference films are never silent under the voice: every cut lands on a small hit, a camera
move is carried by air, a part that switches on makes a sound, and each place has its own room
(fans in a server hall, water in a cooling loop). Before this module the track had one quiet
sweep per beat change, 24 dB under the voice, which is why the film sounded like a slideshow
with a narrator.

Everything is synthesised from noise and oscillators with fixed seeds, so it is owned outright
(see music_bed.py for why that matters) and a re-assemble reproduces the approved track exactly.
Levels and the scene-to-room map live in `audio.sound_design` in workflow/style.json.

Events come from data the pipeline already has:
  * manifest.json        - when each line starts (the beat clock)
  * shots.json           - which beat each line belongs to, and whether it is archive
  * storyboard.json      - each beat's shots (cuts and travelling moves), actions and cutting style
  * shot_lengths.json    - the length a beat was rendered at (shot starts <= 1 are fractions of it)
  * word_timing.json     - `word:` times
  * script/story.json    - the reversal line, where the music drops out
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from workflow import storyboard as timing  # noqa: E402  (the builder's own shot timing)
from workflow.config import style_contract  # noqa: E402


def rules():
    return style_contract(ROOT)["audio"]["sound_design"]


# ---------------------------------------------------------------- the beat clock

def beat_spans(manifest, shots):
    """[(name, kind, start_s, end_s)] in film order, one per beat (consecutive lines of a shot)."""
    rate = manifest["sampleRate"]
    spans = []
    for u in manifest["utterances"]:
        shot = shots[u["id"]]
        start, end = u["startSample"] / rate, u["endSample"] / rate
        if spans and spans[-1][0] == shot["name"]:
            spans[-1][3] = end
        else:
            spans.append([shot["name"], shot.get("kind", "3d"), start, end])
    return [tuple(s) for s in spans]


def beat_shots(spec, seconds, words=(), catalog=None):
    """[(start_s, travels)] for one beat, planned by the same rules the builder uses
    (workflow/storyboard.py); a scene's views come from the catalog, in the order it offers them."""
    shots = spec.get("shots")
    if not shots:
        scene = (catalog or {}).get(spec["scene"], {})
        views = scene.get("views") or ["wide", "close"]
        shots = timing.default_shots(views, scene.get("anchors", []), seconds, spec.get("cut", "travel"))
    planned = timing.shot_starts(shots, seconds, list(words))
    return sorted((s["start"], "to" in s) for s in planned)


def plan_events(episode):
    """-> {"cuts": [(t, kind)], "travels": [(t0, t1)], "actions": [t], "rooms": [(t0, t1, room)],
           "reversal": t | None} in film seconds."""
    episode = Path(episode)
    read = lambda name: json.loads((episode / name).read_text(encoding="utf-8"))
    manifest, shots = read("vo/manifest.json"), read("shots.json")
    board = read("storyboard.json")["beats"] if (episode / "storyboard.json").exists() else {}
    lengths = read("shot_lengths.json") if (episode / "shot_lengths.json").exists() else {}
    words = read("word_timing.json") if (episode / "word_timing.json").exists() else {}
    rooms_by_scene = rules()["rooms"]
    catalog = timing.load_catalog()
    ev = {"cuts": [], "travels": [], "actions": [], "rooms": [], "reversal": None}
    spans = beat_spans(manifest, shots)
    for i, (name, kind, t0, t1) in enumerate(spans):
        if i:
            prev_kind = spans[i - 1][1]
            ev["cuts"].append((t0, "thud" if (kind == "archive") != (prev_kind == "archive") else "whoosh"))
        spec = board.get(name)
        room = rooms_by_scene.get(spec["scene"], rooms_by_scene["_default"]) if spec else rooms_by_scene["_archive"]
        ev["rooms"].append((t0, t1, room))
        if not spec:
            continue
        rendered = float(lengths.get(name, t1 - t0))
        planned = beat_shots(spec, rendered, words.get(name, []), catalog)
        bounds = [s for s, _ in planned] + [rendered]
        for (s, travels), e in zip(planned, bounds[1:]):
            if s > 0.0 and t0 + s < t1 - 0.3:
                ev["cuts"].append((t0 + s, "hit"))
            if travels and e - s >= 2.0 and t0 + s < t1:
                ev["travels"].append((t0 + s, min(t1, t0 + e)))
        for action in spec.get("actions", []):
            t = timing.when(action.get("at"), rendered, words.get(name, []))
            if t is not None and t0 + t < t1:
                ev["actions"].append(t0 + t)
    story = episode / "script" / "story.json"
    if story.exists():
        r = json.loads(story.read_text(encoding="utf-8")).get("reversal")
        hit = next((u for u in manifest["utterances"] if u["id"] == r), None)
        if hit:
            ev["reversal"] = hit["startSample"] / manifest["sampleRate"]
    ev["cuts"].sort()
    return ev


# ---------------------------------------------------------------- synthesis

def band(n, rng, lo, hi, rate, tilt=0.0):
    """Noise between lo and hi Hz with soft edges; tilt < 0 leans it towards the low end."""
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1.0 / rate)
    gain = 1.0 / (1.0 + (lo / np.maximum(f, 1.0)) ** 4) / (1.0 + (f / hi) ** 4)
    if tilt:
        gain = gain * (np.maximum(f, 20.0) / 1000.0) ** tilt
    out = np.fft.irfft(spec * gain, n=n)
    return out / (np.sqrt((out ** 2).mean()) or 1.0)


def slow_wobble(n, rng, rate, hz, depth):
    """A smooth random amplitude curve around 1 (wind gusts, fan beating)."""
    knots = max(4, int(n / rate * hz) + 3)
    curve = np.interp(np.arange(n), np.linspace(0, n, knots), rng.standard_normal(knots))
    return 1.0 + depth * np.tanh(curve)


def hit(rate, seed):
    """A short cut hit: a dull low knock under a soft tick, varied per cut."""
    rng = np.random.default_rng(seed)
    n = int(0.30 * rate)
    t = np.arange(n) / rate
    f0 = rng.uniform(70.0, 95.0)
    knock = np.sin(2 * np.pi * (f0 * t - 18.0 * t * t)) * np.exp(-t * 22.0)
    tick = band(n, rng, 1800.0, 7000.0, rate) * np.exp(-t * 90.0) * 0.35
    out = knock + tick
    return out / np.abs(out).max()


def whoosh(rate, seed, length=0.7):
    """Air past the lens, peaking at 70% of its length (the cut lands on the peak)."""
    rng = np.random.default_rng(seed)
    n = int(length * rate)
    t = np.linspace(0.0, 1.0, n)
    low, high = band(n, rng, 150.0, 900.0, rate), band(n, rng, 900.0, 5000.0, rate)
    bright = np.clip(t / 0.7, 0, 1) ** 2
    env = np.where(t < 0.7, np.clip(t / 0.7, 0, 1) ** 2, np.clip((1.0 - t) / 0.3, 0, 1) ** 1.5)
    out = (low * (1 - 0.6 * bright) + high * bright) * env
    return out / np.abs(out).max()


def thud(rate, length=0.45):
    """A soft low hit where the film changes source (3D to archive)."""
    t = np.arange(int(length * rate)) / rate
    return np.sin(2 * np.pi * (70.0 - 30.0 * t / length) * t) * np.exp(-t * 9.0)


def travel(rate, length, seed):
    """A camera move carried by air: a slow swell that peaks in the second half of the move."""
    rng = np.random.default_rng(seed)
    n = int(length * rate)
    t = np.linspace(0.0, 1.0, n)
    body = band(n, rng, 120.0, 1400.0, rate, tilt=-0.5) * slow_wobble(n, rng, rate, 1.5, 0.25)
    env = np.sin(np.pi * np.clip(t, 0, 1) ** 1.3) ** 2
    return body * env / 4.0


def pop(rate, seed):
    """Something switching on: a short pitched blip with a click on its front."""
    rng = np.random.default_rng(seed)
    n = int(0.16 * rate)
    t = np.arange(n) / rate
    f = rng.choice([523.25, 659.25, 783.99, 880.0])
    tone = np.sin(2 * np.pi * f * t * (1.0 - 0.6 * t)) * np.exp(-t * 32.0)
    click = band(n, rng, 2500.0, 9000.0, rate) * np.exp(-t * 400.0) * 0.4
    out = tone + click
    return out / np.abs(out).max()


def room(rate, length, kind, seed):
    """The sound of a place, at unit RMS."""
    rng = np.random.default_rng(seed)
    n = max(1, int(length * rate))
    t = np.arange(n) / rate
    if kind == "hum":            # a hall of fans and power supplies
        mains = sum(a * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28)) for f, a in ((100, 0.5), (150, 0.25), (300, 0.12)))
        out = band(n, rng, 180.0, 2600.0, rate, tilt=-0.6) * slow_wobble(n, rng, rate, 0.4, 0.15) + mains
    elif kind == "flow":         # liquid in pipes
        out = band(n, rng, 90.0, 900.0, rate, tilt=-0.4) * slow_wobble(n, rng, rate, 3.0, 0.35)
        out = out + 0.25 * band(n, rng, 1500.0, 5000.0, rate) * slow_wobble(n, rng, rate, 6.0, 0.6)
    elif kind == "air":          # outdoors, wind on a mast
        out = band(n, rng, 200.0, 2400.0, rate, tilt=-0.8) * slow_wobble(n, rng, rate, 0.3, 0.5)
    elif kind == "data":         # inside the machine: a faint shimmer and sparse ticks
        out = 0.5 * band(n, rng, 2500.0, 8000.0, rate) * slow_wobble(n, rng, rate, 0.5, 0.4)
        ticks = np.zeros(n)
        for at in rng.uniform(0, n, size=int(length * 5)).astype(int):
            m = min(n - at, int(0.004 * rate))
            ticks[at:at + m] += rng.uniform(1.5, 3.0) * np.exp(-np.arange(m) / (0.0008 * rate))
        out = out + ticks * band(n, rng, 2000.0, 8000.0, rate) * 0.6
    else:                        # "room": a quiet interior
        out = band(n, rng, 40.0, 400.0, rate, tilt=-1.0)
    return out / (np.sqrt((out ** 2).mean()) or 1.0)


def riser(rate, length=1.4, seed=99):
    """Tension into the reversal: noise climbing in pitch and level, cut dead at the line."""
    rng = np.random.default_rng(seed)
    n = int(length * rate)
    t = np.linspace(0.0, 1.0, n)
    low, high = band(n, rng, 200.0, 1200.0, rate), band(n, rng, 1200.0, 7000.0, rate)
    out = (low * (1 - t) + high * t) * t ** 2.5
    return out / np.abs(out).max()


def boom(rate, length=2.2):
    """The floor dropping out: a sub hit with a long tail."""
    t = np.arange(int(length * rate)) / rate
    return np.sin(2 * np.pi * (48.0 - 14.0 * t / length) * t) * np.exp(-t * 2.2)


def _lay(track, sound, at, rate, gain):
    start = int(at * rate)
    a, b = max(0, start), min(len(track), start + len(sound))
    if b > a:
        track[a:b] += gain * sound[a - start:b - start]


def room_impulse(rate, rt60, predelay_ms, seed=77):
    """A small room's response: a short gap, then noise decaying 60 dB over `rt60`, darker as it
    dies (the high end is absorbed first)."""
    rng = np.random.default_rng(seed)
    n = int(rt60 * rate)
    t = np.arange(n) / rate
    tail = rng.standard_normal(n) * 10 ** (-3 * t / rt60)
    tail = np.convolve(tail, np.ones(4) / 4, mode="same") * (t / rt60) + tail * (1 - t / rt60)
    ir = np.concatenate([np.zeros(int(predelay_ms / 1000 * rate)), tail])
    return ir / np.sqrt((ir ** 2).sum())


def reverb(x, rate, cfg):
    """`x` with a share `wet` of it sent through a synthetic room, by block FFT convolution."""
    ir = room_impulse(rate, cfg["rt60_s"], cfg["predelay_ms"])
    block = 1 << 17
    size = 1 << int(np.ceil(np.log2(block + len(ir) - 1)))
    spec_ir = np.fft.rfft(ir, size)
    wet = np.zeros(len(x) + len(ir))
    for a in range(0, len(x), block):
        seg = x[a:a + block]
        if not seg.any():
            continue
        out = np.fft.irfft(np.fft.rfft(seg, size) * spec_ir, size)[:len(seg) + len(ir) - 1]
        wet[a:a + len(out)] += out
    return x + cfg["wet"] * wet[:len(x)]


def design_track(rate, total, ev, voice_rms):
    """One mono track with every event laid at its level (dB under the voice's RMS). Rooms stay
    dry (they are already the sound of a place); everything else gets a short room reverb."""
    lv = rules()["levels_db_under_voice"]
    g = lambda key: voice_rms * 10 ** (-lv[key] / 20)
    rooms = np.zeros(total)
    track = np.zeros(total)
    fade = int(0.35 * rate)
    for i, (t0, t1, kind) in enumerate(ev["rooms"]):
        n = int((t1 - t0) * rate) + 2 * fade
        bed = room(rate, n / rate, kind, seed=1000 + i)
        env = np.ones(len(bed))
        env[:fade] = np.linspace(0, 1, fade)
        env[-fade:] = np.linspace(1, 0, fade)
        trim = rules()["room_trim_db"].get(kind, 0.0)
        _lay(rooms, bed * env, t0 - fade / rate, rate, g("room") * 10 ** (trim / 20))
    for i, (t0, t1) in enumerate(ev["travels"]):
        _lay(track, travel(rate, t1 - t0, seed=2000 + i), t0, rate, g("travel"))
    last = -9.0
    for i, (t, kind) in enumerate(ev["cuts"]):
        if kind == "hit" and t - last < 0.25:
            continue
        last = t
        if kind == "whoosh":
            _lay(track, whoosh(rate, seed=3000 + i), t - 0.49, rate, g("whoosh"))
        elif kind == "thud":
            _lay(track, thud(rate), t, rate, g("thud"))
        else:
            _lay(track, hit(rate, seed=4000 + i), t - 0.004, rate, g("hit"))
    for i, t in enumerate(ev["actions"]):
        _lay(track, pop(rate, seed=5000 + i), t, rate, g("action"))
    r = ev.get("reversal")
    if r is not None:
        s = riser(rate)
        _lay(track, s, r - len(s) / rate, rate, g("riser"))
        _lay(track, boom(rate), r, rate, g("boom"))
    space = rules().get("reverb")
    return rooms + (reverb(track, rate, space) if space else track)


def music_drops(ev):
    """[(start_s, end_s)] where the music bed falls silent: from just before the reversal line
    to a few seconds into it, so the line that breaks the guess is heard on its own."""
    r = ev.get("reversal")
    if r is None:
        return []
    d = rules()["reversal_music_drop_seconds"]
    return [(max(0.0, r - 1.4), r + d)]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", type=Path, required=True)
    args = ap.parse_args(argv)
    ev = plan_events(args.episode)
    print(f"{len(ev['cuts'])} cuts ({sum(k == 'hit' for _, k in ev['cuts'])} inside beats), "
          f"{len(ev['travels'])} travelling moves, {len(ev['actions'])} actions, {len(ev['rooms'])} rooms, "
          f"reversal at {ev['reversal']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
