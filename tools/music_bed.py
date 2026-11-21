"""An original ambient bed, generated in code, laid a fixed distance under the narration.

Why synthesised: every asset that ships inside `media/` on this channel has to be Apache-2.0
(D-010, monetised uploads), and the free music libraries an earlier episode used are CC-BY at
best with no licence record in this repo. A bed built from oscillators is owned outright, needs no
ledger entry, and reproduces byte-for-byte from its seed — so a re-assemble never sounds different
from the take that was approved.

Why a loudness rule rather than a gain: `music_under_voice_db` is a distance in LUFS between two
signals, measured with the same ffmpeg pass the mux uses. A constant gain would sit too loud under
a quiet intro and too quiet under a shouted climax.

`amix` runs with `normalize=0`. Its default scales every input by 1/n, which is the level surprise
the production guide warns about; with normalisation off the graph delivers exactly the distances it
states.
"""
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for candidate in (str(ROOT), str(ROOT / "tools")):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from loudness import measure  # noqa: E402
from workflow.config import style_contract  # noqa: E402

SAMPLE_RATE = 48000
MUSIC_UNDER_VOICE_DB = style_contract(ROOT)["audio"]["music_under_voice_db"]
SEED = 7

# A i - VI - III - VII, each chord held long enough to read as one thought, cross-faded so a
# change is never a click. Kept in the low-mid register: nothing here competes with a voice.
CHORDS = ((110.00, (0, 3, 7, 12)),   # A minor
          (87.31, (0, 4, 7, 12)),    # F
          (130.81, (0, 4, 7, 11)),   # C
          (98.00, (0, 4, 7, 12)))    # G
HOLD_S = 48.0
CROSSFADE_S = 6.0
FADE_IN_S = 2.0
FADE_OUT_S = 3.0
PEAK = 0.6


def _voiced(t, root, intervals, detune_hz, rng):
    """Sum of slightly detuned sine pairs — the detuning is the chorus, no reverb needed."""
    out = np.zeros_like(t)
    for k, semi in enumerate(intervals):
        base = root * 2.0 ** (semi / 12.0)
        amp = 1.0 / (k + 1.6)
        for side in (-1.0, 1.0):
            f = base + side * detune_hz
            phase = rng.uniform(0.0, 2.0 * np.pi)
            out += amp * np.sin(2.0 * np.pi * f * t + phase)
    return out


def _air(n, rng, sample_rate):
    """Band-limited noise: the breath between the pads, kept off the voice's own register."""
    spec = np.fft.rfft(rng.standard_normal(n))
    freqs = np.fft.rfftfreq(n, 1.0 / sample_rate)
    spec[(freqs < 400.0) | (freqs > 2200.0)] *= 0.0
    return np.fft.irfft(spec, n=n)


def apply_drops(bed, drops, sample_rate, out_s=0.12, back_s=1.8):
    """Silence the bed over each (start_s, end_s): a quick fade out, then a slow return, so a
    line that breaks the story is heard with nothing under it."""
    n = len(bed)
    gain = np.ones(n)
    for start, end in drops:
        a, b = int(start * sample_rate), int(end * sample_rate)
        o, r = int(out_s * sample_rate), int(back_s * sample_rate)
        lo = max(0, a - o)
        gain[lo:a] = np.minimum(gain[lo:a], np.linspace(1.0, 0.0, a - lo)) if a > lo else gain[lo:a]
        gain[max(0, a):min(n, b)] = 0.0
        if b < n:
            m = min(n, b + r) - b
            gain[b:b + m] = np.minimum(gain[b:b + m], np.linspace(0.0, 1.0, r)[:m])
    return bed * gain[:, None]


def synthesize(duration_s, seed=SEED, sample_rate=SAMPLE_RATE, fade_end_s=None, drops=()):
    """Stereo float32 bed of exactly `duration_s`, deterministic for a given seed.

    `fade_end_s` is where the outro closes; the tail after it is digital silence. Left unset the
    fade sits at the end of the file, which is right for a standalone bed and wrong inside the
    episode, where the assembler discards everything past the last word.
    """
    n = int(round(duration_s * sample_rate))
    t_all = np.arange(n) / sample_rate
    rng = np.random.default_rng(seed)
    left = np.zeros(n, dtype=np.float64)
    right = np.zeros(n, dtype=np.float64)

    index = -1
    while True:
        # the progression loops: a film longer than four holds would otherwise play air alone
        index += 1
        root, intervals = CHORDS[index % len(CHORDS)]
        start = int((index * HOLD_S) * sample_rate)
        if start >= n:
            break
        end = min(n, start + int((HOLD_S + CROSSFADE_S) * sample_rate))
        span = slice(start, end)
        env = np.ones(end - start, dtype=np.float64)
        fade = int(CROSSFADE_S * sample_rate)
        if end - start > fade:
            ramp = np.linspace(0.0, 1.0, fade)
            env[:fade] *= ramp
            env[-fade:] *= ramp[::-1]
        left[span] += env * _voiced(t_all[span], root, intervals, 0.07, rng)
        right[span] += env * _voiced(t_all[span], root, intervals, 0.11, rng)

    for channel in (left, right):
        channel *= 0.82 + 0.18 * np.sin(2.0 * np.pi * t_all / HOLD_S)

    air_a = _air(n, rng, sample_rate)
    air_b = _air(n, rng, sample_rate)
    left += 0.05 * air_a / (np.max(np.abs(air_a)) or 1.0)
    right += 0.05 * air_b / (np.max(np.abs(air_b)) or 1.0)

    bed = np.stack([left, right], axis=1)
    bed *= PEAK / max(1e-9, float(np.max(np.abs(bed))))

    fadeIn = int(FADE_IN_S * sample_rate)
    fadeOut = int(FADE_OUT_S * sample_rate)
    if n > fadeIn:
        bed[:fadeIn] *= np.linspace(0.0, 1.0, fadeIn)[:, None]
    fade_end = n if fade_end_s is None else min(n, int(round(fade_end_s * sample_rate)))
    closed = max(0, fade_end - fadeOut)
    if fade_end > closed:
        bed[closed:fade_end] *= np.linspace(1.0, 0.0, fade_end - closed)[:, None]
    bed[fade_end:] *= 0.0
    if drops:
        bed = apply_drops(bed, drops, sample_rate)
    return bed.astype(np.float32)


def write_bed(path, duration_s, fade_end_s=None, seed=SEED, sample_rate=SAMPLE_RATE, drops=()):
    """Render the bed to a 16-bit PCM file, creating its directory if needed."""
    import wave

    bed = synthesize(duration_s, seed=seed, sample_rate=sample_rate, fade_end_s=fade_end_s, drops=drops)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(bed, -1.0, 1.0) * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(2)
        fh.setsampwidth(2)
        fh.setframerate(sample_rate)
        fh.writeframes(pcm.tobytes())
    return Path(path)


def bed_gain_db(voice_lufs, bed_lufs, offset_db=MUSIC_UNDER_VOICE_DB):
    """The dB the bed must move by so it ends up `offset_db` under the voice."""
    return round((voice_lufs + offset_db) - bed_lufs, 2)


def gain_for(voice_path, bed_path, offset_db=MUSIC_UNDER_VOICE_DB):
    """dB the bed must move by to end up `offset_db` of LUFS under this narration."""
    voice = float(measure(voice_path)["input_i"])
    bed = float(measure(bed_path)["input_i"])
    return bed_gain_db(voice, bed, offset_db)


def apply_gain_db(src, gain_db, dst):
    """One file, moved by `gain_db`, resampled to the delivery format on the way out."""
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(src),
         "-af", f"volume={gain_db}dB,aresample=48000,"
                "aformat=sample_fmts=fltp:channel_layouts=stereo",
         "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(dst)],
        check=True)
    return Path(dst)


def _read(path):
    """(rate, float64 samples [n, channels]) of a 16-bit PCM wav."""
    import wave
    with wave.open(str(path), "rb") as fh:
        rate, ch = fh.getframerate(), fh.getnchannels()
        data = np.frombuffer(fh.readframes(fh.getnframes()), dtype="<i2").astype(np.float64) / 32768.0
    return rate, data.reshape(-1, ch)


def duck_gain(voice, voice_rate, n_out, out_rate, duck):
    """Linear gain, one value per output sample: 1 in the pauses, pulled down while the voice is
    over `threshold`, by a compressor of `ratio` with a soft `knee` (dB), attack and release.

    Written here rather than with ffmpeg's sidechaincompress, which gave a different file on every
    run (its two inputs arrive in frames whose sizes depend on thread scheduling), and a bed that
    is not byte-identical cannot be re-assembled into the take that was approved."""
    hop = max(1, voice_rate // 100)                                   # 10 ms
    mono = voice.mean(axis=1) if voice.ndim > 1 else voice
    n = len(mono) // hop
    level = np.sqrt((mono[:n * hop].reshape(n, hop) ** 2).mean(axis=1)) + 1e-9
    env = np.empty(n)
    up = 1 - np.exp(-0.010 / (duck["attack_ms"] / 1000))
    down = 1 - np.exp(-0.010 / (duck["release_ms"] / 1000))
    e = 0.0
    for i, x in enumerate(level):
        e += (up if x > e else down) * (x - e)
        env[i] = e
    over = 20 * np.log10(env) - 20 * np.log10(duck["threshold"])
    k = duck["knee"] / 2
    slope = 1 - 1 / duck["ratio"]
    cut = np.where(over <= -k, 0.0, np.where(over >= k, over * slope, slope * (over + k) ** 2 / (4 * k)))
    times = (np.arange(n) + 0.5) * hop / voice_rate
    return 10 ** (-np.interp(np.arange(n_out) / out_rate, times, cut) / 20)


def mix_under(voice_path, bed_path, output_path, offset_db=MUSIC_UNDER_VOICE_DB, duck=None):
    """Sum voice and bed into one file, with the bed a stated LUFS distance under the voice.

    With `duck` (audio.ducking in the contract, the default) the bed is lifted by `lift_db` and
    taken back down while a line is spoken (`duck_gain`): the music keeps its distance under the
    words and rises in the pauses between them, the way an editor rides it, instead of holding
    one level for ten minutes.
    """
    gain = gain_for(voice_path, bed_path, offset_db)
    duck = style_contract(ROOT)["audio"].get("ducking") if duck is None else duck
    if duck:
        import wave
        bed_rate, bed = _read(bed_path)
        voice_rate, voice = _read(voice_path)
        bed = bed * (10 ** ((gain + duck["lift_db"]) / 20)) * duck_gain(voice, voice_rate, len(bed), bed_rate, duck)[:, None]
        ducked = Path(output_path).with_name(f"{Path(output_path).stem}-bed-ducked.wav")
        with wave.open(str(ducked), "wb") as fh:
            fh.setnchannels(bed.shape[1])
            fh.setsampwidth(2)
            fh.setframerate(bed_rate)
            fh.writeframes((np.clip(bed, -1.0, 1.0) * 32767.0).astype("<i2").tobytes())
        bed_path, gain = ducked, 0.0
    graph = (
        "[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a0];"
        f"[1:a]volume={gain}dB,aresample=48000,"
        "aformat=sample_fmts=fltp:channel_layouts=stereo[a1];"
        "[a0][a1]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[out]"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(voice_path), "-i", str(bed_path),
         "-filter_complex", graph, "-map", "[out]", "-ar", "48000", "-ac", "2",
         "-c:a", "pcm_s16le", str(output_path)],
        check=True)
    return Path(output_path)


if __name__ == "__main__":
    seconds = float(os.environ.get("ARTEMIS_BED_SECONDS", "60"))
    target = Path(os.environ.get("ARTEMIS_BED_OUT", "bed.wav"))
    print(write_bed(target, seconds))
