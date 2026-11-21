"""The music bed the contract already promises.

`workflow/style.json` carries `music_under_voice_db: -10.0` and the production guide names the
missing bed as one of the two reasons the episode still reads as a slideshow — but the assembler
had no music path at all. Two decisions the tests below pin:

1. **The bed is synthesised, not sourced.** Every asset that ships in `media/` on this channel has
   to be Apache-2.0 (D-010, monetised uploads), and the free music libraries the previous episode
   used are CC-BY or worse with no licence record in this repo. An original bed generated in code
   is owned outright, deterministic, and needs no licence ledger entry.
2. **"Under the voice" is a loudness statement, not a gain guess.** The offset is applied to
   *integrated LUFS*, measured with the same ffmpeg pass the mux already uses, so -10.0 LU means
   the same thing for a whispered intro and a shouted climax. The two silent-input cases make the
   measurement testable end to end: with the voice muted the output *is* the bed, so its LUFS can
   be asserted directly instead of trusting the arithmetic.

`amix` appears here with `normalize=0`. Its default scales every input by 1/n, which is what the
guide's "no amix" note was about; `normalize=0` keeps the levels the filter graph states.
"""
import subprocess
import sys
import unittest
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import loudness  # noqa: E402
import music_bed  # noqa: E402
from workflow.config import style_contract  # noqa: E402

AUDIO = style_contract(ROOT)["audio"]
SR = 48000


def write_wav(path, samples, sample_rate=SR):
    """16-bit PCM out of a float array shaped (n,) or (n, 2)."""
    a = np.asarray(samples)
    if a.ndim == 1:
        a = a[:, None]
    a = np.clip(a, -1.0, 1.0)
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(a.shape[1])
        fh.setsampwidth(2)
        fh.setframerate(sample_rate)
        fh.writeframes((a * 32767.0).astype("<i2").tobytes())
    return path


def lufs(path):
    """Integrated LUFS of one file, from loudnorm's own first pass."""
    return float(loudness.measure(path)["input_i"])


class Synthesis(unittest.TestCase):
    def test_the_bed_is_stereo_48k_and_the_length_asked_for(self):
        bed = music_bed.synthesize(6.0)
        self.assertEqual(bed.dtype, np.float32)
        self.assertEqual(bed.shape, (6 * SR, 2))

    def test_the_same_seed_builds_the_same_bytes(self):
        first = music_bed.synthesize(4.0, seed=7)
        second = music_bed.synthesize(4.0, seed=7)
        np.testing.assert_array_equal(first, second)
        self.assertFalse(np.array_equal(first, music_bed.synthesize(4.0, seed=8)))

    def test_no_sample_reaches_clipping(self):
        self.assertLess(float(np.max(np.abs(music_bed.synthesize(20.0)))), 1.0)

    def test_the_edges_fade_so_the_bed_does_not_click(self):
        bed = music_bed.synthesize(6.0)
        self.assertLess(float(np.max(np.abs(bed[: int(0.05 * SR)]))), 0.02)
        self.assertLess(float(np.max(np.abs(bed[-int(0.05 * SR):]))), 0.02)

    def test_the_bed_holds_energy_through_its_middle(self):
        """A bed that decays into silence is not a bed; it is a sting."""
        bed = music_bed.synthesize(60.0)
        rms = lambda s: float(np.sqrt(np.mean(np.square(s))))
        self.assertGreater(rms(bed[20 * SR:25 * SR]), 0.2 * rms(bed[:5 * SR]))


    def test_a_film_longer_than_the_chord_progression_still_has_music_under_it(self):
        """The four chords run ~200 s; past that the bed used to be air alone (-35 dB), so every
        longer episode shipped with nothing audible under the voice."""
        seconds = int(len(music_bed.CHORDS) * music_bed.HOLD_S) + 120
        bed = music_bed.synthesize(float(seconds), fade_end_s=float(seconds))
        rms = lambda s: float(np.sqrt(np.mean(np.square(s))))
        early = rms(bed[20 * SR:30 * SR])
        for start in range(30, seconds - 30, 30):
            self.assertGreater(rms(bed[start * SR:(start + 10) * SR]), 0.2 * early,
                               f"bed has gone quiet by {start}s")


class OffsetMath(unittest.TestCase):
    def test_the_gain_moves_the_bed_to_the_contracted_offset(self):
        self.assertEqual(music_bed.bed_gain_db(voice_lufs=-25.3, bed_lufs=-30.0,
                                               offset_db=-10.0), -5.3)

    def test_a_bed_already_under_the_voice_is_turned_down_not_up(self):
        self.assertLess(music_bed.bed_gain_db(-14.0, -20.0, -10.0), 0.0)

    def test_the_default_offset_comes_from_the_contract(self):
        self.assertEqual(music_bed.MUSIC_UNDER_VOICE_DB, AUDIO["music_under_voice_db"])


class FadeClosesWhereTheNarrationDoes(unittest.TestCase):
    """Where the fade sits is a delivery question, not a shape question.

    `add_music_bed` generates the bed past the last word and then cuts the mix back with
    `-t voice_duration`, so every sample after the narration is discarded. Parked at the end of
    the generated file — which is where it was — the fade lands entirely inside that discarded
    tail, and the delivered episode stops the music at full level. Ruled 2026-11-12: the fade
    closes at the last word instead, so the bed audibly lets go while the narration finishes.
    """

    @classmethod
    def setUpClass(cls):
        cls.tmp = ROOT / "_scratch/music_bed_tests"
        cls.tmp.mkdir(parents=True, exist_ok=True)

    def test_the_bed_is_silent_from_the_moment_the_narration_ends(self):
        bed = music_bed.synthesize(12.0, fade_end_s=8.0)
        self.assertLess(float(np.max(np.abs(bed[int(8.0 * SR):]))), 1e-4)

    def test_the_bed_is_still_carrying_just_before_the_fade_opens(self):
        bed = music_bed.synthesize(12.0, fade_end_s=8.0)
        rms = lambda s: float(np.sqrt(np.mean(np.square(s))))
        before = rms(bed[int(4.0 * SR):int(4.5 * SR)])
        self.assertGreater(before, 0.05)
        self.assertLess(rms(bed[int(7.0 * SR):int(7.5 * SR)]), 0.5 * before)

    def test_a_bed_with_no_narration_end_fades_at_its_own_end(self):
        """The default is the old behaviour: a standalone bed keeps its outro at the file edge."""
        bed = music_bed.synthesize(12.0)
        self.assertGreater(float(np.max(np.abs(bed[int(8.0 * SR):10 * SR]))), 0.05)

    def test_the_generated_file_is_silent_across_the_tail_the_trim_discards(self):
        out = self.tmp / "bed-faded.wav"
        music_bed.write_bed(out, 12.0, fade_end_s=8.0)
        with wave.open(str(out)) as fh:
            pcm = np.frombuffer(fh.readframes(fh.getnframes()), dtype="<i2")
        self.assertEqual(float(np.max(np.abs(pcm.reshape(-1, 2)[int(8.0 * SR):]))), 0.0)


class Mixing(unittest.TestCase):
    """Real ffmpeg, short fixtures.

    Muting one input looked like the obvious way to isolate the bed, and it is not: loudnorm
    reports digital silence as `-inf`, so the gain arithmetic that follows is meaningless rather
    than measurable. The honest version applies the same gain the mix applies, to the bed alone,
    and measures that.
    """

    @classmethod
    def setUpClass(cls):
        cls.tmp = ROOT / "_scratch/music_bed_tests"
        cls.tmp.mkdir(parents=True, exist_ok=True)
        t = np.arange(5 * SR) / SR
        voice = 0.35 * np.sin(2 * np.pi * 180 * t) * (1.0 + 0.5 * np.sin(2 * np.pi * 0.4 * t))
        cls.voice = write_wav(cls.tmp / "voice.wav", np.stack([voice, voice], 1))
        cls.bed = write_wav(cls.tmp / "bed.wav", music_bed.synthesize(5.0))

    def mixed(self, first, second, name="mixed"):
        out = self.tmp / f"{name}.wav"
        music_bed.mix_under(first, second, out)
        return out

    def test_the_gain_the_mix_applies_lands_the_bed_on_the_contracted_offset(self):
        voice_lufs = lufs(self.voice)
        gain = music_bed.gain_for(self.voice, self.bed)
        alone = self.tmp / "bed-at-gain.wav"
        music_bed.apply_gain_db(self.bed, gain, alone)
        self.assertAlmostEqual(lufs(alone), voice_lufs + AUDIO["music_under_voice_db"], delta=0.6,
                               msg=f"voice measured {voice_lufs} LUFS, gain {gain} dB")

    def test_the_bed_is_audible_in_the_mix_without_coming_near_the_voice(self):
        """The mix rises above the voice alone, and by less than a decibel.

        Decibel addition says a bed 10 LU under the voice lifts the sum by +0.41 dB, and
        this test used to assert that number. On the real 470 s narration the measured
        lift was +0.08 dB, because integrated loudness is *gated*: a bed parked at the
        threshold is largely not counted. The gate, not the level, was what the +0.41 was
        really measuring — so the assertion is now the bound that holds on both signals.
        """
        voice_lufs = lufs(self.voice)
        mixed_lufs = lufs(self.mixed(self.voice, self.bed))
        self.assertGreater(mixed_lufs, voice_lufs, "the bed contributed nothing to the mix")
        self.assertLess(mixed_lufs, voice_lufs + 1.0,
                        f"mix is {mixed_lufs - voice_lufs:+.2f} dB over the voice; a bed "
                        "10 LU down must not approach it")

    def test_the_mix_keeps_the_input_length_and_the_delivery_rate(self):
        out = self.mixed(self.voice, self.bed)
        with wave.open(str(out)) as fh:
            self.assertEqual(fh.getframerate(), SR)
            self.assertEqual(fh.getnchannels(), 2)
            self.assertAlmostEqual(fh.getnframes() / fh.getframerate(), 5.0, delta=0.1)

    def test_a_repeated_mix_is_byte_identical(self):
        first = self.mixed(self.voice, self.bed, "mix-a")
        second = self.mixed(self.voice, self.bed, "mix-b")
        self.assertEqual(first.read_bytes(), second.read_bytes())


class Ducking(unittest.TestCase):
    DUCK = {"lift_db": 5.0, "threshold": 0.03, "ratio": 2.5, "attack_ms": 40, "release_ms": 300, "knee": 3}

    def test_the_bed_is_pulled_down_while_the_voice_speaks_and_returns_in_the_pause(self):
        rate = 24000
        t = np.arange(4 * rate) / rate
        voice = 0.12 * np.sin(2 * np.pi * 200 * t) * (t < 2.0)          # two seconds of speech, then a pause
        g = music_bed.duck_gain(voice, rate, 4 * SR, SR, self.DUCK)
        cut_db = -20 * np.log10(g)
        self.assertGreater(cut_db[int(1.5 * SR)], 4.0)                    # well under the voice
        self.assertLess(cut_db[int(3.5 * SR)], 0.1)                       # back up 1.5 s into the pause
        self.assertTrue(np.all(np.diff(cut_db[int(2.05 * SR):int(3.0 * SR)]) <= 1e-9))   # released, not jumped

    def test_the_gain_is_the_same_every_time(self):
        rate = 24000
        voice = np.random.default_rng(3).standard_normal(2 * rate) * 0.05
        a = music_bed.duck_gain(voice, rate, 2 * SR, SR, self.DUCK)
        self.assertTrue(np.array_equal(a, music_bed.duck_gain(voice, rate, 2 * SR, SR, self.DUCK)))


if __name__ == "__main__":
    unittest.main()
