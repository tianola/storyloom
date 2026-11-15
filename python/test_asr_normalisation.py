"""The WER normaliser must not charge a spelled-out number against a digit.

Measured 2026-11-12 21:25Z on the shipped Artemis II narration: `tools/asr_wer.py` reported WER
0.190 on u001 and 0.158 on u002 (overall 0.089 over 157 reference words, `--limit 4`). Diffing the
token lists showed the errors were number formats — the script text is what the TTS must speak,
"eight point eight million", and Whisper writes what it hears, "8.8 million". Nothing was
mispronounced, yet the tool cried wolf, and a tool that cries wolf gets ignored the one time a real
mispronunciation ships inside a five-hour render.

The behaviour the tool needs: a number is one thing, however either side spells it. So each maximal
run of numeric material collapses to a single `N` token on both sides. Counting still works — a
number the narrator skipped leaves the two token streams a run apart — while digit-vs-word stops
being an error. u002 goes to exactly 0.000 under this rule; u001 keeps one error, a date ordinal,
which is the documented limit asserted in `test_the_shipped_u001_pair_keeps_only_the_date_ordinal`.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from asr_wer import normalise, wer, words  # noqa: E402

# Verbatim from work/episode-artemis-ii/vo/manifest.json and from the transcript column of the
# 2026-11-12 run. Kept as literals so the regression test cannot drift with the episode directory.
U001_SCRIPT = ("On April first, twenty twenty-six, a rocket the height of a thirty-story building "
               "erupted from Kennedy Space Center. Four RS-25 engines fired together, producing "
               "eight point eight million pounds of thrust, and the Space Launch System began to rise.")
U001_HEARD = ("On April 1, 2026, a rocket the height of a 30-story building erupted from Kennedy "
              "Space Center. Four RS-25 engines fired together, producing 8.8 million pounds of "
              "thrust, and the Space Launch System began to rise.")
U002_SCRIPT = ("This was not just another rocket launch. This was the first time in fifty-four years "
               "that human beings were heading beyond low Earth orbit. The last time it happened, it "
               "was December nineteen seventy-two, Apollo seventeen.")
U002_HEARD = ("This was not just another rocket launch. This was the first time in 54 years that "
              "human beings were heading beyond low Earth orbit. The last time it happened, it was "
              "December 1972, Apollo 17.")


class NumberRunsCollapseToOneToken(unittest.TestCase):
    def test_a_year_spelled_for_tts_matches_whispers_digits(self):
        self.assertEqual(normalise("it was nineteen seventy two, Apollo seventeen"),
                         normalise("it was 1972, Apollo 17"))

    def test_a_decimal_matches_however_it_is_spoken(self):
        self.assertEqual(normalise("producing 8.8 million pounds of thrust"),
                         normalise("producing eight point eight million pounds of thrust"))

    def test_the_shipped_u002_pair_drops_from_the_measured_0158_to_zero(self):
        """The utterance that measured 0.158: every one of its errors was a number format."""
        self.assertAlmostEqual(wer(words(U002_SCRIPT), words(U002_HEARD)), 0.158, places=3)
        self.assertEqual(wer(normalise(U002_SCRIPT), normalise(U002_HEARD)), 0.0)

    def test_the_shipped_u001_pair_keeps_only_the_date_ordinal(self):
        """0.190 measured, 0.027 after the fix: one error survives, and it is the one we chose.

        The script says "April first" and Whisper writes the date as "April 1". Folding `first`
        into the numeric class would silence a word that carries real meaning everywhere else in a
        narration ("the first person of color to fly around the moon"), so ordinals stay words and
        this one substitution stays charged.
        """
        self.assertAlmostEqual(wer(words(U001_SCRIPT), words(U001_HEARD)), 0.190, places=3)
        self.assertAlmostEqual(wer(normalise(U001_SCRIPT), normalise(U001_HEARD)), 0.027, places=3)
        self.assertIn("first", normalise(U001_SCRIPT))
        self.assertNotIn("first", normalise(U001_HEARD))


class RealWordsStillCount(unittest.TestCase):
    """Collapsing numbers must not hide the failures the tool exists to catch."""

    def test_a_mangled_word_is_still_an_error(self):
        self.assertNotEqual(normalise("the most advanced crew vehicle"),
                            normalise("the most advance crew vehicle"))

    def test_a_dropped_number_is_still_counted(self):
        """The count of numeric runs survives, so a skipped figure stays visible."""
        self.assertEqual(len(normalise("four RS-25 engines fired")),
                         len(normalise("RS-25 engines fired")) + 1)

    def test_a_wrong_number_is_not_this_tools_job(self):
        """Documented limit, asserted so nobody reads more out of the number than it holds.

        "eight point eight million" and "nine million" both collapse to one run, so WER cannot
        tell them apart — and a base.en model digitising a spoken figure is not a reliable
        arithmetic source anyway. Numeric fidelity belongs to the claims ledger (D-002) and the
        fact-check pass, which read the script against the cited primary source.
        """
        self.assertEqual(normalise("8.8 million pounds"), normalise("nine million pounds"))


if __name__ == "__main__":
    unittest.main()
