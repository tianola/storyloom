"""The mux must deliver the loudness the contract names, without clipping on the way there.

The shipped Artemis II master measured **-25.3 LUFS** integrated with a **-3.4 dBFS** true peak.
The platform normalises playback to -14 LUFS, so the episode was 11.3 LU quiet and would be
gain-ridden by the player. The obvious fix — `volume=+11.3dB` — pushes that true peak to
+7.9 dBFS, which is clipping, so it is not available.

Two-pass `loudnorm` with `linear=true` reaches the target: the first pass measures, the second
applies it. Measured on the 2026-11-12 mix it did *not* come out as one clean gain — 11.29 dB was
owed and the peaks came up 5.4 dB, so ffmpeg limited dynamically to land -14.00 LUFS at all. That
is tolerated here because it held the level steady enough to keep the narration bed un-pumped, but
it means `linear=true` is a preference, not a ceiling guard, and the guard is the encode headroom
in `TruePeakCeilingIsEnforced` below.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import assemble_episode  # noqa: E402,F401  (importing the assembler still has to work)
import loudness  # noqa: E402
import qc_episode  # noqa: E402
from workflow.config import style_contract  # noqa: E402

qc_loudness = qc_episode.loudness
AUDIO = style_contract(ROOT)["audio"]

# The first-pass measurement of work/episode-artemis-ii/episode-artemis-ii.mp4, 2026-11-10.
# loudnorm reports these as strings, which is why the fixture holds strings.
MEASURED = {"input_i": "-25.3", "input_tp": "-3.4", "input_lra": "2.5",
            "input_thresh": "-35.6", "target_offset": "0.0"}


class LoudnormFilter(unittest.TestCase):
    def test_the_filter_asks_for_the_contract_target(self):
        af = loudness.loudnorm_filter(MEASURED, AUDIO)
        self.assertIn(f"I={AUDIO['integrated_lufs_target']}", af)
        self.assertIn(f"TP={AUDIO['true_peak_max_dbfs'] - AUDIO['encode_true_peak_headroom_db']}", af)
        self.assertIn(f"LRA={AUDIO['loudness_range_lu']}", af)

    def test_the_second_pass_is_linear_so_it_does_not_pump(self):
        self.assertIn("linear=true", loudness.loudnorm_filter(MEASURED, AUDIO))

    def test_the_measurement_is_carried_into_the_second_pass(self):
        af = loudness.loudnorm_filter(MEASURED, AUDIO)
        for key, value in (("measured_I", "-25.3"), ("measured_TP", "-3.4"),
                           ("measured_LRA", "2.5"), ("measured_thresh", "-35.6")):
            self.assertIn(f"{key}={value}", af)

    def test_the_output_is_resampled_after_loudnorm_not_before(self):
        af = loudness.loudnorm_filter(MEASURED, AUDIO)
        self.assertIn(f"aresample={AUDIO['sample_rate_min']}", af)
        self.assertLess(af.index("loudnorm"), af.index("aresample"),
                        "loudnorm resamples internally to 192 kHz and leaves it there; "
                        "aresample has to come after or the master ships at 192 kHz")

    def test_a_missing_measurement_raises_instead_of_guessing(self):
        with self.assertRaises(KeyError):
            loudness.loudnorm_filter({"input_i": "-25.3"}, AUDIO)

    def test_the_contract_carries_every_number_the_filter_needs(self):
        for key in ("integrated_lufs_target", "true_peak_max_dbfs", "loudness_range_lu",
                    "encode_true_peak_headroom_db", "channels_min", "sample_rate_min"):
            self.assertIn(key, AUDIO, key)


class TruePeakCeilingIsEnforced(unittest.TestCase):
    """The ceiling the gate reads is measured *after* the lossy encode, so it needs headroom.

    Measured on the 2026-11-12 1080p master, all three numbers with the gate's own ebur128
    measurer: the pre-mux mix sits at -25.29 LUFS / -6.41 dBFS true peak, `loudnorm` with the
    contract's own filter lands the PCM at **-14.00 LUFS / -1.00 dBFS** — the loudness half exact
    and the peak half sitting right on the ceiling with zero margin — and `aac -b:a 192k`, which is
    what `mux_final` ships, moves that to **-0.70 dBFS**. The master in `dist` measured -0.60. So
    the breach was never a mix decision: lossy encoding overshoots inter-sample peaks, and a
    delivery gain staged to the ceiling itself guarantees a breach. `loudnorm`'s TP= has to be set
    below the ceiling by a codec margin, and the only honest place to prove that is the encoded
    stream.
    """

    RATE = 48000
    SECONDS = 20.0

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="true-peak-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.src = self._fixture(Path(self.tmp) / "src.wav")

    def _fixture(self, path):
        """Filtered noise in a word/gap envelope with sparse plosive hits, seeded.

        A pure tone is the wrong fixture and was tried: with no dynamic range `loudnorm` can only
        cap its own linear gain, so the headroom appears to cost 2.1 LU of loudness and the test
        measures ffmpeg's behaviour on a signal no narration ever is. This lands at -27.0 LUFS with
        a -3.4 dBFS true peak over a 1.9 LU range against the real narration's -25.3 / -3.4 / 2.5 —
        quiet enough to owe a large delivery gain, peaky enough to threaten the ceiling.
        """
        rng = np.random.default_rng(7)
        n = int(self.RATE * self.SECONDS)
        t = np.arange(n, dtype=np.float64) / self.RATE
        kernel = np.hanning(60)
        band = np.convolve(rng.standard_normal(n), kernel / kernel.sum(), mode="same")
        envelope = np.zeros(n)
        word_s, gap_s = 0.26, 0.12
        pos = 0.0
        while pos < self.SECONDS:
            start = int(pos * self.RATE)
            stop = int(min(pos + word_s, self.SECONDS) * self.RATE)
            if stop > start:
                envelope[start:stop] = 0.75 + 0.25 * rng.random()
                attack = min(40, stop - start)
                envelope[start:start + attack] *= np.linspace(0.0, 1.0, attack)
            pos += word_s + gap_s
        voice = band * envelope * 0.28
        for hit in range(int(self.RATE), n, int(5.3 * self.RATE)):
            stop = min(hit + int(0.008 * self.RATE), n)
            voice[hit:stop] += (0.62 * np.linspace(1.0, 0.0, stop - hit)
                                * np.sin(2 * np.pi * 2600.0 * t[hit:stop]))
        pcm = np.clip(voice, -1.0, 1.0)
        stereo = np.repeat((pcm * 32767.0).astype("<i2")[:, None], 2, axis=1)
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(2)
            handle.setsampwidth(2)
            handle.setframerate(self.RATE)
            handle.writeframes(stereo.tobytes())
        return path

    def _measure(self, source, encoded):
        """Run the delivery chain exactly as mux_final does, then read back what it produced."""
        delivered = Path(self.tmp) / ("encoded.m4a" if encoded else "pcm.wav")
        audio_filter = loudness.loudnorm_filter(loudness.measure(source), AUDIO)
        codec = ["-c:a", "aac", "-b:a", "192k"] if encoded else ["-c:a", "pcm_s16le"]
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(source),
                        "-af", audio_filter, "-ar", str(self.RATE), "-ac", "2", *codec,
                        str(delivered)], check=True)
        return qc_loudness(delivered)

    def test_the_fixture_is_shaped_like_the_real_narration(self):
        integrated, peak, _ = qc_loudness(self.src)
        owed = AUDIO["integrated_lufs_target"] - integrated
        self.assertGreaterEqual(owed, 9.0, f"fixture needs only {owed:.1f} LU of delivery gain")
        self.assertGreaterEqual(peak, -8.0, f"fixture peaks too low to threaten the ceiling: {peak}")
        self.assertGreaterEqual(peak - integrated, 15.0,
                                "a narrow crest factor never forces the ceiling to bite")

    def test_the_pcm_lands_under_the_ceiling_by_the_stated_headroom(self):
        integrated, peak, _ = self._measure(self.src, encoded=False)
        margin = AUDIO["encode_true_peak_headroom_db"]
        self.assertLessEqual(peak, AUDIO["true_peak_max_dbfs"] - margin,
                             f"true peak {peak:.2f} dBFS leaves less than {margin} dB of "
                             "headroom for the lossy encode that follows")
        self.assertAlmostEqual(integrated, AUDIO["integrated_lufs_target"], delta=1.0,
                               msg="headroom bought by falling off the loudness target")

    def test_the_shipped_encode_stays_under_the_ceiling(self):
        integrated, peak, _ = self._measure(self.src, encoded=True)
        self.assertLessEqual(peak, AUDIO["true_peak_max_dbfs"],
                             f"true peak {peak:.2f} dBFS after aac: the gate reads the encoded "
                             "stream, so this is the number that has to hold")
        self.assertAlmostEqual(integrated, AUDIO["integrated_lufs_target"], delta=1.0)


if __name__ == "__main__":
    unittest.main()
