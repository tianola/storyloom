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

    def test_bool_params_take_only_true_or_false(self):
        board = {"beats": {"b": {"scene": "fiber-trip", "params": {"markers": True}}}}
        self.assertEqual(storyboard.validate(board), [])
        board["beats"]["b"]["params"]["markers"] = 1
        self.assertTrue(any("must be bool" in e for e in storyboard.validate(board)))
        # and an int parameter still refuses True, which Python counts as 1
        board = {"beats": {"b": {"scene": "experts", "params": {"pick": True}}}}
        self.assertTrue(any("must be int" in e for e in storyboard.validate(board)))

    def test_cast_must_name_a_sprite_and_a_screen_point(self):
        self.assertEqual(broken(cast=[{"who": "token", "screen": [0.2, 0.8], "hop": True}]), [])
        self.assertTrue(any("not a sprite" in e for e in broken(cast=[{"who": "dragon", "screen": [0.2, 0.8]}])))
        self.assertTrue(any("'screen'" in e for e in broken(cast=[{"who": "token", "screen": [2, 0]}])))
        self.assertTrue(any("names shot" in e for e in broken(cast=[{"who": "token", "screen": [0.5, 0.5], "shot": 5}])))

    def test_bad_time_and_screen(self):
        self.assertTrue(any("bad at" in e for e in broken(labels=[{"text": "T", "anchor": "die", "at": "soon"}])))
        self.assertTrue(any("screen" in e for e in broken(hud=[{"text": "x", "screen": [2, 0]}])))

    def test_extras_value_is_checked(self):
        self.assertEqual(broken(extras="none"), [])
        self.assertTrue(any("extras" in e for e in broken(extras="some")))

    def test_3d_cast_advice_small_people_and_pixel_extras(self):
        cast = [{"who": "mother", "screen": [0.5, 0.95], "height": 0.3, "render": "3d"}]
        board = copy.deepcopy(GOOD)
        board["beats"]["b"]["cast"] = cast
        warnings = []
        self.assertEqual(storyboard.validate(board, warnings=warnings), [])
        self.assertTrue(any("reads as a doll" in w for w in warnings))
        self.assertTrue(any("extras" in w for w in warnings))
        cast[0]["height"] = 0.6
        board["beats"]["b"]["extras"] = "none"
        warnings = []
        storyboard.validate(board, warnings=warnings)
        self.assertFalse(any("doll" in w or "extras" in w for w in warnings))

    def test_missing_length(self):
        self.assertTrue(any("shot_lengths" in e for e in storyboard.validate(GOOD, lengths={})))


if __name__ == "__main__":
    unittest.main()


class StagingAdvice(unittest.TestCase):
    LINES = {"b": [{"uid": "u1", "speaker": "mother", "mode": "say", "start": 6.0, "end": 8.0}]}

    def board(self, **beat):
        beat.setdefault("scene", "vienna")
        return {"beats": {"b": beat}}

    def advice(self, board, lines=None, secs=12, **kw):
        return storyboard.staging_advice(board, self.LINES if lines is None else lines, {"b": secs, **kw})

    def test_speaker_must_be_in_frame_before_line(self):
        shots = [{"view": "roofs", "start": 0.0}, {"view": "market", "start": 5.0}]
        mother = {"who": "mother", "speaker": "mother", "screen": [0.4, 1.0], "height": 0.6}
        bad = self.advice(self.board(shots=shots, cast=[dict(mother, shot=0)]))
        self.assertTrue(any("'mother' speaks" in w for w in bad), bad)
        self.assertFalse(self.advice(self.board(shots=shots, cast=[dict(mother, shot=1)])))
        self.assertFalse(self.advice(self.board(shots=shots, cast=[mother])))
        late = self.advice(self.board(shots=shots, cast=[dict(mother, span=[5.8, 9.0])]))
        self.assertTrue(any("not in frame" in w for w in late))
        self.assertFalse(self.advice(self.board(shots=shots, cast=[dict(mother, span=[5.0, 9.0])])))
        # thought lines and the narrator are not checked
        lines = {"b": [{"uid": "u", "speaker": "mother", "mode": "thought", "start": 6.0, "end": 8.0}]}
        self.assertFalse(self.advice(self.board(shots=shots, cast=[]), lines))

    def test_short_shots(self):
        shots = [{"view": "roofs", "start": 0.0}, {"view": "market", "start": 5.0}, {"view": "roofs", "start": 5.6}]
        self.assertTrue(any("under 1s" in w for w in self.advice(self.board(shots=shots), {})))

    def test_new_place_needs_four_seconds(self):
        board = {"beats": {"a": {"scene": "asylum", "shots": [{"view": "street"}]},
                           "b": {"scene": "vienna", "shots": [{"view": "roofs"}, {"view": "market", "start": 2.5}]}}}
        advice = storyboard.staging_advice(board, {}, {"a": 10, "b": 10})
        self.assertEqual(len([w for w in advice if "new place" in w]), 1)
        board["beats"]["b"]["shots"][0] = {"view": "at:lantern"}
        self.assertFalse([w for w in storyboard.staging_advice(board, {}, {"a": 10, "b": 10}) if "new place" in w])

    def test_quick_run_outside_montage(self):
        shots = [{"view": "roofs", "start": 2.0 * i} for i in range(5)] + [{"view": "market", "start": 10.0 + 4.0 * i} for i in range(6)]
        advice = self.advice(self.board(shots=shots), {}, secs=34)
        self.assertTrue(any("in a row" in w for w in advice), advice)
        self.assertFalse(self.advice(self.board(shots=shots, cut="montage"), {}, secs=34))

    def test_narrator_one_side(self):
        def narrator(x):
            return {"who": "explorer", "speaker": "narrator", "bust": True, "screen": [x, 1.0]}
        board = {"beats": {"a": {"scene": "vienna", "cast": [narrator(0.7)]},
                           "b": {"scene": "vienna", "cast": [narrator(0.3)]}}}
        self.assertTrue(any("narrator bust" in w for w in storyboard.staging_advice(board, {}, {"a": 8, "b": 8})))
        board["beats"]["b"]["cast"] = [narrator(0.8)]
        self.assertFalse(storyboard.staging_advice(board, {}, {"a": 8, "b": 8}))
