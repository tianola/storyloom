"""Mouth timing: phoneme to shape, minimum holds, and times measured from the beat's first wav
(lead-in silence included), not from its first word."""
import json
import sys
import tempfile
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import lip_sync as L  # noqa: E402
from word_marks import wav_print  # noqa: E402


class Shapes(unittest.TestCase):
    def test_table(self):
        self.assertEqual([L.shape_of(p) for p in "mbpaɑəsˈ "], ["closed"] * 3 + ["open"] * 2 + ["half", "half", None, None])

    def test_runs_hold_at_least_two_frames(self):
        frames = ["rest", "half", "open", "open", "closed", "half", "half"]
        out = L.runs(frames)
        self.assertTrue(all(b - a >= 2 for _, a, b in out))
        self.assertEqual(out[0][1], 0)
        self.assertEqual(out[-1][2], len(frames))

    def test_pause_rests_the_mouth(self):
        frames = L.frames_from_phones([("a", 0.0, 0.2), ("a", 0.6, 0.8)])
        self.assertIn("rest", frames[int(0.3 * L.FPS):int(0.5 * L.FPS)])

    def test_word_fallback_opens_and_closes(self):
        frames = L.frames_from_words([("hello", 0.0, 0.4)])
        self.assertIn("open", frames)
        self.assertEqual(frames[-1], "rest")


def write_wav(path, seconds):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\x00\x00" * int(seconds * 24000))


class Build(unittest.TestCase):
    def test_origin_is_the_first_wav_of_the_beat_including_its_silence(self):
        with tempfile.TemporaryDirectory() as d:
            ep = Path(d)
            (ep / "vo").mkdir()
            write_wav(ep / "vo" / "u001.wav", 1.0)
            write_wav(ep / "vo" / "u002.wav", 1.0)
            manifest = {"sampleRate": 24000, "utterances": [
                {"id": "u001", "file": "u001.wav", "text": "Narrator here.", "samples": 24000, "startSample": 0},
                {"id": "u002", "file": "u002.wav", "text": "Mama.", "samples": 24000, "startSample": 24000,
                 "speaker": "semmelweis", "mode": "say"}]}
            (ep / "vo" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (ep / "shots.json").write_text(json.dumps({"u001": {"name": "b1"}, "u002": {"name": "b1"}}), encoding="utf-8")
            # the line's own wav has 0.25 s of silence before its first phoneme
            marks = {"u002": {"wav": wav_print(ep / "vo" / "u002.wav"), "text": "Mama.", "words": [["Mama.", 0.25, 0.65]],
                              "phones": [["m", 0.25, 0.35], ["a", 0.35, 0.45], ["m", 0.45, 0.55], ["a", 0.55, 0.65]]}}
            (ep / "vo" / "word_marks.json").write_text(json.dumps(marks), encoding="utf-8")
            out = L.build(ep, log=lambda *_: None)
            self.assertEqual(out["b1"][0]["speaker"], "narrator")      # untagged lines are the guide's
            line = out["b1"][1]
            self.assertEqual(line["start"], 1.0)
            first_open = next(v for v in line["visemes"] if v[0] != "rest")
            self.assertAlmostEqual(first_open[1], 1.25, delta=1 / L.FPS)   # within one frame

    def test_thought_lines_have_no_mouth(self):
        with tempfile.TemporaryDirectory() as d:
            ep = Path(d)
            (ep / "vo").mkdir()
            write_wav(ep / "vo" / "u001.wav", 0.5)
            manifest = {"sampleRate": 24000, "utterances": [
                {"id": "u001", "file": "u001.wav", "text": "Why?", "samples": 12000, "startSample": 0,
                 "speaker": "semmelweis", "mode": "thought"}]}
            (ep / "vo" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (ep / "shots.json").write_text(json.dumps({"u001": {"name": "b1"}}), encoding="utf-8")
            out = L.build(ep, log=lambda *_: None)
            self.assertEqual(out["b1"][0]["visemes"], [])
            self.assertEqual(out["b1"][0]["mode"], "thought")


if __name__ == "__main__":
    unittest.main()
