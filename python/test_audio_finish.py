"""Audio finishing: bounded levelling, transition sounds on the cuts, and the level ride that clears the gate."""
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import audio_finish as A  # noqa: E402

RATE = 24000


def tone(seconds, amp):
    t = np.arange(int(seconds * RATE)) / RATE
    return amp * np.sin(2 * np.pi * 180 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t))


class AudioFinish(unittest.TestCase):
    def test_gains_move_toward_the_median_and_are_bounded(self):
        gains = A.level_gains({"a": -22.0, "b": -20.0, "c": -40.0, "d": -21.0})
        self.assertAlmostEqual(gains["a"], 0.5, places=6)
        self.assertEqual(gains["c"], A.MAX_GAIN_DB)
        self.assertLess(gains["b"], 0)

    def test_whoosh_is_normalised_and_quiet_at_both_ends(self):
        w = A.whoosh(RATE, seed=1)
        self.assertAlmostEqual(float(np.abs(w).max()), 1.0, places=6)
        self.assertLess(abs(w[0]), 0.05)
        self.assertLess(abs(w[-1]), 0.05)

    def test_the_transition_track_puts_energy_at_the_cut_and_nowhere_else(self):
        track = A.transition_track(RATE, RATE * 10, [(5.0, "whoosh")], voice_rms=0.1)
        self.assertEqual(float(np.abs(track[:RATE * 4]).max()), 0.0)
        self.assertGreater(float(np.abs(track[int(4.5 * RATE):int(5.3 * RATE)]).max()), 0.0)
        voice_peak_equiv = 0.1 * 10 ** (-A.SFX_BELOW_VOICE_DB / 20) / 0.35
        self.assertLessEqual(float(np.abs(track).max()), voice_peak_equiv * 1.001)

    def test_cut_points_mark_beat_changes_and_archive_edges(self):
        manifest = {"sampleRate": RATE, "utterances": [{"id": f"u{i}", "startSample": i * RATE} for i in range(4)]}
        shots = {"u0": {"name": "a", "kind": "3d"}, "u1": {"name": "a", "kind": "3d"},
                 "u2": {"name": "b", "kind": "archive"}, "u3": {"name": "c", "kind": "3d"}}
        self.assertEqual(A.cut_points(manifest, shots), [(2.0, "thud"), (3.0, "thud")])
        shots["u3"] = {"name": "c", "kind": "archive"}
        self.assertEqual(A.cut_points(manifest, shots), [(2.0, "thud"), (3.0, "whoosh")])

    def test_the_level_ride_brings_a_step_inside_the_bound(self):
        voice = np.concatenate([tone(4, 0.05), tone(4, 0.12)])     # about +7.6 dB at 4 s
        cuts = [4.0]
        before = A.measure_cut_deltas(voice, RATE, cuts)[0]
        self.assertGreater(before, 5.0)
        ridden, after = A.ride_cuts(voice, RATE, cuts, bound=1.8)
        self.assertLessEqual(abs(after[0]), 1.8)
        self.assertEqual(len(ridden), len(voice))
        self.assertLessEqual(float(np.abs(ridden).max()), A.PEAK_CEILING + 1e-9)


if __name__ == "__main__":
    unittest.main()


class ThoughtTreatment(unittest.TestCase):
    def test_thought_is_quieter_and_duller_say_is_untouched(self):
        import audio_finish
        rate = 24000
        t = np.arange(rate) / rate
        tone = 0.3 * np.sin(2 * np.pi * 300 * t) + 0.3 * np.sin(2 * np.pi * 9000 * t)
        style = audio_finish.thought_style()
        out = audio_finish.treat_thought(tone, rate, style)
        self.assertEqual(len(out), len(tone))

        def band(x, hz):
            return abs(np.fft.rfft(x)[hz])
        self.assertLess(band(out, 9000) / band(out, 300), 0.7 * band(tone, 9000) / band(tone, 300))
        self.assertLess(band(out, 300), band(tone, 300))
        self.assertGreater(band(out, 300), 0.4 * band(tone, 300))
        self.assertIn("why", style)

    def test_level_utterances_treats_only_thought_lines(self):
        import tempfile
        from unittest import mock
        import audio_finish
        with tempfile.TemporaryDirectory() as tmp:
            vo = Path(tmp) / "vo"
            vo.mkdir()
            signal = (0.2 * np.sin(2 * np.pi * 9000 * np.arange(RATE) / RATE))
            for name in ("a.wav", "b.wav"):
                audio_finish.write_wav(vo / name, RATE, signal)
            manifest = {"utterances": [{"id": "a", "file": "a.wav", "mode": "say"},
                                       {"id": "b", "file": "b.wav", "mode": "thought"}]}
            with mock.patch.object(audio_finish.loudness, "measure", return_value={"input_i": -20.0}):
                audio_finish.level_utterances(tmp, manifest)
            from captions import read_wav
            a = read_wav(vo / "levelled" / "a.wav")[1]
            b = read_wav(vo / "levelled" / "b.wav")[1]
            self.assertLess(np.abs(b).max(), 0.5 * np.abs(a).max())
