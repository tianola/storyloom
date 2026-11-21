"""QC cut rhythm: an even pace fails, the reference shape (quick montage plus long holds) passes."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))
import qc_episode as Q  # noqa: E402
from workflow.config import style_contract  # noqa: E402

CONTRACT = style_contract(ROOT)


def cuts_from(lengths):
    out, t = [], 0.0
    for x in lengths[:-1]:
        t += x
        out.append(t)
    return out, sum(lengths)


class CutRhythm(unittest.TestCase):
    def test_an_even_five_second_pace_fails_all_three_ways(self):
        cuts, duration = cuts_from([5.5] * 100)
        codes = {f.code for f in Q.check_cut_rhythm(cuts, duration, CONTRACT)}
        self.assertEqual(codes, {"cut_rhythm_slow", "cut_rhythm_no_montage", "cut_rhythm_no_hold"})

    def test_montage_with_held_moves_passes(self):
        lengths = [0.8, 1.2, 1.0, 2.1, 1.4, 3.0, 2.5] * 20 + [45.0, 60.0, 30.0]
        cuts, duration = cuts_from(lengths)
        self.assertEqual(Q.check_cut_rhythm(cuts, duration, CONTRACT), [])

    def test_too_few_shots_to_judge_says_nothing(self):
        self.assertEqual(Q.check_cut_rhythm([], 50.0, CONTRACT), [])


if __name__ == "__main__":
    unittest.main()
