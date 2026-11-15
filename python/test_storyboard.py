"""Storyboard validator: Jensen's storyboard passes; each kind of mistake is named."""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from workflow import storyboard  # noqa: E402

GOOD = {"beats": {"b": {"scene": "chip-teardown", "params": {"package": "qfp"},
                        "shots": [{"view": "wide"}, {"view": "at:die", "start": 4}],
                        "labels": [{"text": "Die", "anchor": "die", "at": "word:silicon"}],
                        "actions": [{"name": "open", "at": 0.2}]}}}


def broken(**changes):
    board = copy.deepcopy(GOOD)
    board["beats"]["b"].update(changes)
    return storyboard.validate(board)


class StoryboardValidation(unittest.TestCase):
    def test_jensen_storyboard_is_valid(self):
        board, lengths = storyboard.load_episode(ROOT / "work" / "jensen-huang")
        self.assertEqual(storyboard.validate(board, lengths=lengths), [])

    def test_good_board_passes(self):
        self.assertEqual(storyboard.validate(GOOD), [])

    def test_unknown_scene(self):
        self.assertIn("unknown scene 'nope'", broken(scene="nope")[0])

    def test_unknown_anchor_view_action_param(self):
        self.assertTrue(any("unknown anchor 'x'" in e for e in broken(labels=[{"text": "T", "anchor": "x"}])))
        self.assertTrue(any("unknown view 'x'" in e for e in broken(shots=[{"view": "x"}])))
        self.assertTrue(any("unknown action 'x'" in e for e in broken(actions=[{"name": "x"}])))
        self.assertTrue(any("no parameter 'x'" in e for e in broken(params={"x": 1})))

    def test_bad_param_value_and_label_length(self):
        self.assertTrue(any("one of" in e for e in broken(params={"package": "zzz"})))
        self.assertTrue(any("1-32" in e for e in broken(labels=[{"text": "x" * 40, "anchor": "die"}])))

    def test_bad_time_and_screen(self):
        self.assertTrue(any("bad at" in e for e in broken(labels=[{"text": "T", "anchor": "die", "at": "soon"}])))
        self.assertTrue(any("screen" in e for e in broken(hud=[{"text": "x", "screen": [2, 0]}])))

    def test_missing_length(self):
        self.assertTrue(any("shot_lengths" in e for e in storyboard.validate(GOOD, lengths={})))


if __name__ == "__main__":
    unittest.main()
