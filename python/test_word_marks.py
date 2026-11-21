"""Word marks: phonemes spoken in context are matched back to the words of the line."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import word_marks as W  # noqa: E402


class FakeTokenizer:
    """Each word 'phonemised' alone is its lowercase letters, which is enough to test the alignment."""
    def phonemize(self, word, lang):
        return "".join(c for c in word.lower() if c.isalpha())


class FakeEngine:
    tokenizer = FakeTokenizer()


def spoken(groups, step=0.1):
    """[(char, start, end)] for phoneme words separated by spaces, one step per char."""
    out, t = [], 0.0
    for gi, g in enumerate(groups):
        if gi:
            out.append((" ", t, t))
        for c in g:
            out.append((c, t, t + step))
            t += step
    return out


class Marks(unittest.TestCase):
    def test_words_spoken_separately_get_their_own_start(self):
        marks = W.word_marks(FakeEngine(), "Cat sat down.", spoken(["cat", "sat", "down"]))
        self.assertEqual([w for w, _, _ in marks], ["Cat", "sat", "down."])
        self.assertEqual([s for _, s, _ in marks], [0.0, 0.3, 0.6])

    def test_words_linked_in_context_still_split_where_their_sounds_start(self):
        # espeak speaks "that it" as one phoneme word; each text word still finds its first sound
        marks = W.word_marks(FakeEngine(), "so that it is", spoken(["so", "thatit", "is"]))
        self.assertEqual([round(s, 2) for _, s, _ in marks], [0.0, 0.2, 0.6, 0.8])

    def test_a_word_whose_sound_changed_in_context_sits_between_its_neighbours(self):
        marks = W.word_marks(FakeEngine(), "the cat", spoken(["ðə", "cat"]))
        self.assertEqual(marks[1][1], 0.2)
        self.assertLessEqual(marks[0][1], marks[1][1])
        self.assertTrue(all(e > s for _, s, e in marks))


class CaptionsUseMarks(unittest.TestCase):
    def test_marks_are_used_only_for_the_wav_and_text_they_were_read_from(self):
        import json
        import tempfile
        import wave
        import numpy as np
        import captions
        with tempfile.TemporaryDirectory() as tmp:
            ep = Path(tmp)
            (ep / "vo").mkdir()
            with wave.open(str(ep / "vo" / "u001.wav"), "wb") as w:
                w.setnchannels(1), w.setsampwidth(2), w.setframerate(24000)
                w.writeframes((np.sin(np.arange(24000) / 7.0) * 9000).astype(np.int16).tobytes())
            u = {"id": "u001", "file": "u001.wav", "text": "Two words."}
            marks = {"u001": {"wav": W.wav_print(ep / "vo" / "u001.wav"), "text": u["text"],
                              "words": [["Two", 0.1, 0.4], ["words.", 0.45, 0.9]]}}
            (ep / "vo" / "word_marks.json").write_text(json.dumps(marks), encoding="utf-8")
            self.assertEqual(captions.exact_marks(ep, u), [("Two", 0.1, 0.4), ("words.", 0.45, 0.9)])
            self.assertIsNone(captions.exact_marks(ep, {**u, "text": "Other words."}))
            marks["u001"]["wav"] = "stale"
            (ep / "vo" / "word_marks.json").write_text(json.dumps(marks), encoding="utf-8")
            self.assertIsNone(captions.exact_marks(ep, u))


if __name__ == "__main__":
    unittest.main()
