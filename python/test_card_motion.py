"""The animated cards must move, measured the same way the gate measures the master.

The shipped Artemis II cards were still PNGs held for 14.6 s and 16.9 s: 0.67 and 0.62 on the
gate's motion scale, against a grain floor of 0.62 — photographs with narration over them.
`assemble_episode.card_frame` replaced them with clips whose content arrives in stages under
one slow scan sweep. These tests render the real clips and measure them, because a card that
only *claims* to animate is exactly the defect class this repo keeps re-meeting.
"""
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import assemble_episode as A  # noqa: E402
import qc_episode as Q  # noqa: E402

CONTRACT = Q.style_contract(ROOT)

BAR = ("card", "bar-chart", "Mission Stats", "9 days | 700,237 mi | Lunar orbit")
PROCESS = ("card", "process", "All Systems Validated", "Ready for Artemis III")


class AnimatedCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.clips = {}
        for name, entry, dur in (("bar-chart", BAR, 14.6), ("process", PROCESS, 16.9)):
            path = Path(cls.tmp.name) / f"{name}.mp4"
            A.make_scene_card_clip(entry, path, dur)
            cls.clips[name] = (path, dur)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_open_window_of_both_cards_moves_past_the_still_bound(self):
        bound = CONTRACT["rhythm"]["motion_static_max"]
        for name, (path, dur) in self.clips.items():
            for w in (0.5, 1.0, dur * 0.3, dur * 0.5, dur * 0.7):
                with self.subTest(card=name, window=round(w, 1)):
                    self.assertGreaterEqual(
                        Q.motion(path, w, 1.0), bound,
                        f"{name} reads as a still at t={w:.1f}s")

    def test_the_tail_settles_on_purpose_rather_than_looping(self):
        # The last seconds hold: the reveal is finished and the sweep has left. That is a
        # deliberate settle of 2.5-3.0 s, far under the ten-second static limit — the rule is
        # about holds, not about the last breath of a shot.
        bound = CONTRACT["rhythm"]["motion_static_max"]
        for name, (path, dur) in self.clips.items():
            with self.subTest(card=name):
                self.assertLess(Q.motion(path, dur - 2.0, 1.0), bound)

    def test_the_clip_runs_exactly_as_long_as_it_was_asked(self):
        for name, (path, dur) in self.clips.items():
            with self.subTest(card=name):
                self.assertAlmostEqual(Q.probe(path)["duration"], dur, delta=0.1)

    def test_a_card_kind_with_no_animation_raises_instead_of_shipping_a_still(self):
        with self.assertRaises(ValueError):
            A.card_frame(("card", "comparison", "T", "S"), 1.0, 10.0)

    def test_the_still_fallback_is_the_settled_frame_without_the_sweep(self):
        out = Path(self.tmp.name) / "still.png"
        A.make_scene_card(BAR, out)
        settled = A.card_frame(BAR, 14.6, 14.6)
        self.assertEqual(settled.tobytes(),
                         Image.open(out).convert("RGB").tobytes())


if __name__ == "__main__":
    unittest.main()
