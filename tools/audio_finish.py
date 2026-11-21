"""Narration finishing: per-sentence loudness levelling and synthesised transition sounds.

    python tools/audio_finish.py --episode work/X          # writes vo/levelled/*.wav and full-audio-finished.wav

The voice is synthesised sentence by sentence, and sentences come out at different levels (a short
line can sit several LU away from a long one). Because the film cuts on sentences, that step in
level lands exactly on the cut, which `qc_episode` reports as `cut_loudness_jump`. Levelling gives
every utterance the same integrated loudness (the episode median) with a bounded gain, keeping each
file's exact length so the timeline does not move.

Effects are laid by tools/sound_design.py, read off the storyboard (hits, air on moves, actions,
rooms, the reversal). The single sweep per beat change below (`transition_track`, 24 dB under
the voice) is only the fallback for an episode with no storyboard.json. Everything is synthesised,
so nothing licensed enters the master.
"""
import argparse
import json
import sys
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

import loudness  # noqa: E402
from captions import read_wav  # noqa: E402

MAX_GAIN_DB = 9.0
PEAK_CEILING = 0.89           # about -1 dBFS
SFX_BELOW_VOICE_DB = 24.0
WHOOSH_SECONDS = 0.7


def write_wav(path, rate, samples):
    pcm = (np.clip(samples, -1.0, 1.0) * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


def level_gains(measured, max_gain=MAX_GAIN_DB):
    """{uid: gain dB} moving each utterance's loudness to the episode median, bounded."""
    target = float(np.median(list(measured.values())))
    return {uid: float(np.clip(target - value, -max_gain, max_gain)) for uid, value in measured.items()}


def thought_style(path=None):
    """The inner-voice treatment amounts, from workflow/style.json (`audio.thought`)."""
    path = Path(path) if path else ROOT / "workflow" / "style.json"
    return json.loads(path.read_text(encoding="utf-8"))["audio"]["thought"]


def treat_thought(samples, rate, style=None):
    """Inner voice: gain_db under the levelled line, a one-pole low-pass at lowpass_hz (applied twice,
    12 dB/oct) and one very quiet short slap. Same length as the input."""
    style = style or thought_style()
    x = np.asarray(samples, dtype=np.float64)
    alpha = 1.0 - np.exp(-2.0 * np.pi * float(style["lowpass_hz"]) / rate)
    for _ in range(2):
        y = np.empty_like(x)
        acc = 0.0
        for i in range(len(x)):
            acc += alpha * (x[i] - acc)
            y[i] = acc
        x = y
    delay = int(float(style.get("slap_ms", 0)) * rate / 1000)
    if delay > 0 and delay < len(x):
        slap = np.zeros_like(x)
        slap[delay:] = x[:-delay] * 10 ** (float(style.get("slap_db", -18.0)) / 20)
        x = x + slap
    return x * 10 ** (float(style["gain_db"]) / 20)


def level_utterances(episode, manifest):
    """-> {uid: {"before_lufs", "gain_db"}}; writes `vo/levelled/<file>` and returns the gains."""
    vo = Path(episode) / "vo"
    out = vo / "levelled"
    out.mkdir(exist_ok=True)
    measured = {u["id"]: float(loudness.measure(vo / u["file"])["input_i"]) for u in manifest["utterances"]}
    gains = level_gains(measured)
    for u in manifest["utterances"]:
        rate, samples = read_wav(vo / u["file"])
        gain = 10 ** (gains[u["id"]] / 20)
        peak = float(np.abs(samples).max()) or 1.0
        gain = min(gain, PEAK_CEILING / peak)
        leveled = samples * gain
        if u.get("mode") == "thought":
            leveled = treat_thought(leveled, rate)
        write_wav(out / u["file"], rate, leveled)
    return {uid: {"before_lufs": round(measured[uid], 2), "gain_db": round(gains[uid], 2)} for uid in measured}


def whoosh(rate, seed, length=WHOOSH_SECONDS):
    """A rising-then-falling noise sweep, peaking at 70% of its length (the cut lands on the peak)."""
    n = int(length * rate)
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(n)
    t = np.linspace(0.0, 1.0, n)
    cutoff = 300.0 + 5200.0 * np.sin(np.pi * np.clip(t / 0.7, 0, 1) * 0.5) ** 2
    alpha = 1.0 - np.exp(-2.0 * np.pi * cutoff / rate)
    out = np.empty(n)
    y = 0.0
    for i in range(n):
        y += alpha[i] * (noise[i] - y)
        out[i] = y
    rise = np.clip(t / 0.7, 0, 1) ** 2
    fall = np.clip((1.0 - t) / 0.3, 0, 1) ** 1.5
    env = np.where(t < 0.7, rise, fall)
    out = out * env
    return out / (np.abs(out).max() or 1.0)


def thud(rate, length=0.35):
    """A soft low hit, used where the film changes source (3D to archive)."""
    t = np.arange(int(length * rate)) / rate
    return np.sin(2 * np.pi * (70.0 - 30.0 * t / length) * t) * np.exp(-t * 11.0)


def transition_track(rate, total_samples, cuts, voice_rms):
    """A mono track with one sound per cut: [(seconds, "whoosh"|"thud"), ...]."""
    track = np.zeros(total_samples)
    for i, (when, kind) in enumerate(cuts):
        sound = whoosh(rate, seed=i + 1) if kind == "whoosh" else thud(rate)
        peak_at = int(0.7 * WHOOSH_SECONDS * rate) if kind == "whoosh" else 0
        start = int(when * rate) - peak_at
        a, b = max(0, start), min(total_samples, start + len(sound))
        if b > a:
            track[a:b] += sound[a - start:b - start]
    gain = voice_rms * 10 ** (-SFX_BELOW_VOICE_DB / 20) / 0.35
    return track * gain


def cut_points(manifest, shots):
    """[(seconds, kind)] at each utterance whose beat differs from the previous one."""
    cuts, previous = [], None
    for u in manifest["utterances"]:
        shot = shots[u["id"]]
        if previous is not None and shot["name"] != previous["name"]:
            archive_edge = (shot["kind"] == "archive") != (previous["kind"] == "archive")
            cuts.append((u["startSample"] / manifest["sampleRate"], "thud" if archive_edge else "whoosh"))
        previous = shot
    return cuts


def _smooth(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def measure_cut_deltas(voice, rate, cuts, window=1.0):
    """LU the voice moves across each cut, measured the way qc_episode measures it (`window` seconds a side)."""
    import tempfile
    import qc_episode
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, t in enumerate(cuts):
            levels = []
            for side, start in (("a", t - window), ("b", t)):
                a, b = max(0, int(start * rate)), min(len(voice), int((start + window) * rate))
                path = Path(tmp) / f"{i}{side}.wav"
                write_wav(path, rate, voice[a:b])
                levels.append(qc_episode.loudness(path)[0])
            out.append(levels[1] - levels[0])
    return out


def ride_cuts(voice, rate, cuts, bound, iterations=4, reach=1.6, limit_db=8.0):
    """The editor's level ride: where the voice steps by more than `bound` LU across a cut, lift the
    tail of the sentence before it and ease down the start of the sentence after, half each, and
    measure again. Returns (voice, [final deltas]). Gain is smooth (no click) and bounded."""
    gain_db = np.zeros(len(voice))
    t_axis = np.arange(len(voice)) / rate
    current = voice
    deltas = measure_cut_deltas(current, rate, cuts)
    for _ in range(iterations):
        if all(abs(d) <= bound for d in deltas):
            break
        for t, d in zip(cuts, deltas):
            if abs(d) <= bound:
                continue
            amount = (abs(d) - bound * 0.5) / 2.0 * np.sign(d)
            gain_db += amount * _smooth((t_axis - (t - reach)) / reach) * (t_axis < t)
            gain_db -= amount * (1.0 - _smooth((t_axis - t) / reach)) * (t_axis >= t) * (t_axis < t + reach)
        gain_db = np.clip(gain_db, -limit_db, limit_db)
        current = voice * 10 ** (gain_db / 20)
        peak = float(np.abs(current).max())
        if peak > PEAK_CEILING:
            current = current * (PEAK_CEILING / peak)
        deltas = measure_cut_deltas(current, rate, cuts)
    return current, deltas


def finish_voice(episode, manifest, shots=None, sound=True):
    """Level every sentence, lay transition sounds under the cuts, write one file for the mix.

    Returns (path, report). The result has exactly the samples of the original concatenation.
    """
    episode = Path(episode)
    report = level_utterances(episode, manifest)
    rate = manifest["sampleRate"]
    parts = [read_wav(episode / "vo" / "levelled" / u["file"])[1] for u in manifest["utterances"]]
    voice = np.concatenate(parts)
    mixed = voice.copy()
    if shots:
        import qc_episode
        bound = float(qc_episode.style_contract(ROOT)["archive"]["cohesion"]["loudness_delta_across_cuts_max_lu"])
        archive_cuts = [t for t, kind in cut_points(manifest, shots) if kind == "thud"]
        mixed, deltas = ride_cuts(mixed, rate, archive_cuts, bound * 0.6)
        report["_ride"] = {"cuts": archive_cuts, "deltas_lu": [round(d, 2) for d in deltas]}
        voice = mixed.copy()
    if sound and shots:
        rms = float(np.sqrt((voice ** 2).mean())) or 0.05
        if (episode / "storyboard.json").exists():
            # the full design: hits on every cut, air on moves, actions, rooms, the reversal
            import sound_design
            events = sound_design.plan_events(episode)
            mixed = mixed + sound_design.design_track(rate, len(voice), events, rms)
            report["_sound"] = {"cuts": len(events["cuts"]), "travels": len(events["travels"]),
                                "actions": len(events["actions"]), "reversal": events["reversal"],
                                "music_drops": sound_design.music_drops(events)}
        else:
            mixed = mixed + transition_track(rate, len(voice), cut_points(manifest, shots), rms)
        peak = float(np.abs(mixed).max())
        if peak > PEAK_CEILING:
            mixed *= PEAK_CEILING / peak
    path = episode / "vo" / "full-audio-finished.wav"
    write_wav(path, rate, mixed)
    (episode / "vo" / "levelling.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return path, report


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", type=Path, required=True)
    ap.add_argument("--no-sound", action="store_true")
    args = ap.parse_args(argv)
    episode = args.episode if args.episode.is_absolute() else ROOT / args.episode
    manifest = json.loads((episode / "vo" / "manifest.json").read_text(encoding="utf-8"))
    shots = json.loads((episode / "shots.json").read_text(encoding="utf-8"))
    path, report = finish_voice(episode, manifest, shots, sound=not args.no_sound)
    spread = [r["before_lufs"] for k, r in report.items() if not k.startswith("_")]
    print(f"levelled {len(spread)} utterances (before: {min(spread):.1f}..{max(spread):.1f} LUFS) -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
