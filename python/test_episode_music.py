"""The assembler has to actually lay the bed under the narration.

`music_bed` proves the maths in isolation; this file proves the two ways the wiring can lie:

- a bed shorter than the narration leaves the last minutes of the episode silent, which sounds
  like a machine fault rather than a mix decision, so the bed is built a few seconds past the
  last word and `-shortest` in the mux lands it on the picture;
- a mixed track that measures the same as the narration alone means the bed was generated and
  then ignored.
"""
import sys
import unittest
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import assemble_episode  # noqa: E402
import loudness  # noqa: E402
import music_bed  # noqa: E402
from workflow.config import style_contract  # noqa: E402

AUDIO = style_contract(ROOT)["audio"]
SR = 48000


def seconds_of(path):
    with wave.open(str(path)) as fh:
        return fh.getnframes() / fh.getframerate()


class BedInThePipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = ROOT / "_scratch/episode_music_tests"
        cls.tmp.mkdir(parents=True, exist_ok=True)
        t = np.arange(4 * SR) / SR
        voice = 0.35 * np.sin(2 * np.pi * 180 * t)
        cls.voice = cls.tmp / "voice.wav"
        with wave.open(str(cls.voice), "wb") as fh:
            fh.setnchannels(2)
            fh.setsampwidth(2)
            fh.setframerate(SR)
            fh.writeframes((np.stack([voice, voice], 1) * 32767).astype("<i2").tobytes())
        cls.bed = cls.tmp / "bed.wav"
        cls.mixed = cls.tmp / "voice-plus-bed.wav"

    def mixed_paths(self):
        return assemble_episode.add_music_bed(self.voice, self.bed, self.mixed)

    def test_the_bed_outruns_the_narration_so_the_tail_is_not_silent(self):
        self.mixed_paths()
        self.assertGreaterEqual(seconds_of(self.bed), seconds_of(self.voice) + 3.0)

    def test_the_bed_has_let_go_by_the_last_word(self):
        """The delivered mix is cut at `voice_duration`, so the outro has to be inside that cut.

        The generated bed runs 5 s past the narration and the fade used to sit in that tail, which
        the trim throws away — the episode stopped the music at full level. Ruled 2026-11-12: the
        fade closes at the last word, so the bed audibly lets go while the narration finishes.
        """
        self.mixed_paths()
        voice_end = seconds_of(self.voice)
        with wave.open(str(self.bed)) as fh:
            rate = fh.getframerate()
            pcm = np.frombuffer(fh.readframes(fh.getnframes()), dtype="<i2")
            samples = pcm.reshape(-1, 2).astype(np.float64) / 32768.0
        rms = lambda s: float(np.sqrt(np.mean(np.square(s)))) if len(s) else 0.0
        self.assertLess(rms(samples[int(voice_end * rate):]), 1e-6,
                        "the bed is still playing where the trim discards it")
        self.assertGreater(rms(samples[:int(voice_end * rate)]), 0.02,
                           "a bed that never played is not a bed that faded")

    def test_the_mixed_track_is_handed_back_for_the_mux(self):
        self.assertEqual(self.mixed_paths(), self.mixed)
        self.assertTrue(self.mixed.exists())

    def test_the_mixed_track_measures_the_bed_added_at_the_contracted_distance(self):
        voice_lufs = float(loudness.measure(self.voice)["input_i"])
        expected = voice_lufs + 10 * np.log10(1.0 + 10.0 ** (AUDIO["music_under_voice_db"] / 10))
        mixed_lufs = float(loudness.measure(self.mixed_paths())["input_i"])
        self.assertAlmostEqual(mixed_lufs, expected, delta=0.6,
                               msg=f"voice {voice_lufs} LUFS, mix {mixed_lufs} LUFS")

    def test_the_mux_filter_still_targets_the_contract_loudness_after_the_bed(self):
        """The delivery gain is measured on the mix, so the bed cannot move the master off -14."""
        measured = loudness.measure(self.mixed)
        self.assertIn(f"I={AUDIO['integrated_lufs_target']}",
                      loudness.loudnorm_filter(measured, AUDIO))


class LoudnessHelpersHaveOneHome(unittest.TestCase):
    def test_the_assembler_uses_the_shared_measurer_instead_of_its_own_copy(self):
        self.assertFalse(hasattr(assemble_episode, "measure_loudnorm"))
        self.assertIs(assemble_episode.loudness, loudness)


if __name__ == "__main__":
    unittest.main()
