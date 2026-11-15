"""Word timings and captions: placement is monotone, cues fit the screen, the soft stream is real."""
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import captions as C  # noqa: E402

TEXT = ("In nineteen ninety-three, at a modest booth inside a Denny's diner in San Jose, three engineers "
        "sketched out a bet on a wild idea: that computer screens would soon demand real time worlds.")


def words_of(text, start=0.0, end=12.0):
    return [{"uid": "u001", "word": w, "start": s, "end": e} for w, s, e in C.place_words(text, start, end)]


class Captions(unittest.TestCase):
    def test_words_are_ordered_inside_the_voiced_span(self):
        placed = C.place_words(TEXT, 0.5, 11.0)
        self.assertEqual(len(placed), len(TEXT.split()))
        self.assertAlmostEqual(placed[0][1], 0.5)
        self.assertAlmostEqual(placed[-1][2], 11.0, places=3)
        for (_, s, e), (_, s2, _) in zip(placed, placed[1:]):
            self.assertLess(s, e)
            self.assertLessEqual(e, s2 + 1e-9)

    def test_a_comma_leaves_a_longer_gap_than_a_plain_word(self):
        placed = C.place_words("alpha, beta gamma delta", 0.0, 4.0)
        gap_after_comma = placed[1][1] - placed[0][2]
        gap_plain = placed[2][1] - placed[1][2]
        self.assertGreater(gap_after_comma, gap_plain)

    def test_voiced_span_skips_silence_at_both_ends(self):
        rate = 24000
        tone = np.sin(2 * np.pi * 200 * np.arange(rate * 2) / rate) * 0.5
        samples = np.concatenate([np.zeros(rate // 2), tone, np.zeros(rate)])
        a, b = C.voiced_span(samples, rate)
        self.assertAlmostEqual(a, 0.5, delta=0.03)
        self.assertAlmostEqual(b, 2.5, delta=0.03)

    def test_cues_fit_two_short_lines_and_a_readable_time(self):
        cue_list = C.cues(words_of(TEXT * 3, 0.0, 30.0))
        self.assertGreater(len(cue_list), 3)
        for start, end, text in cue_list:
            lines = C.wrap(text)
            self.assertLessEqual(len(lines), 2)
            self.assertTrue(all(len(line) <= C.LINE_CHARS for line in lines), lines)
            self.assertGreaterEqual(end - start, C.MIN_CUE_S - 1e-6)
        for (_, e, _), (s, _, _) in zip(cue_list, cue_list[1:]):
            self.assertLessEqual(e, s + 1e-9, "cues must not overlap")

    def test_srt_and_vtt_stamps(self):
        self.assertEqual(C.stamp(3661.5), "01:01:01,500")
        self.assertEqual(C.stamp(1.25, comma=False), "00:00:01.250")
        with tempfile.TemporaryDirectory() as tmp:
            C.write_srt([(0.0, 2.0, "Hello there")], Path(tmp) / "a.srt")
            C.write_vtt([(0.0, 2.0, "Hello there")], Path(tmp) / "a.vtt")
            self.assertIn("1\n00:00:00,000 --> 00:00:02,000\nHello there", (Path(tmp) / "a.srt").read_text(encoding="utf-8"))
            self.assertTrue((Path(tmp) / "a.vtt").read_text(encoding="utf-8").startswith("WEBVTT"))

    def test_a_soft_subtitle_stream_is_attached(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=160x90:d=2",
                            "-f", "lavfi", "-i", "sine=d=2", "-shortest", "-c:v", "libx264", str(tmp / "m.mp4")], check=True)
            C.write_srt([(0.0, 1.5, "Hello there")], tmp / "c.srt")
            C.attach(tmp / "m.mp4", tmp / "c.srt", tmp / "o.mp4")
            probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "s", "-show_entries", "stream=codec_name",
                                    "-of", "csv=p=0", str(tmp / "o.mp4")], capture_output=True, text=True)
            self.assertEqual(probe.stdout.strip(), "mov_text")


if __name__ == "__main__":
    unittest.main()
