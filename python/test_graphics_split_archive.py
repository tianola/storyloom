"""split layout/overlay and the archive mat / source card (incl. card_lines moved here)."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_graphics_support import ROOT, SMALL, TOKENS, drawn_mask, has_ink  # noqa: E402

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

sys.path.insert(0, str(ROOT / "tools"))
from tools.graphics import get  # noqa: E402
from tools.graphics.archive import card_lines, picture_rect  # noqa: E402
from tools.graphics.split import layout  # noqa: E402


class Split(unittest.TestCase):
    def test_layout_tiles_the_canvas_with_the_gap_between(self):
        for n, count in ((1, 1), (2, 2), (3, 3), (4, 4), (6, 6)):
            rects = layout(n, (1920, 1080), 10)
            self.assertEqual(len(rects), count)
            self.assertEqual(min(r[0] for r in rects), 0)
            self.assertEqual(max(r[2] for r in rects), 1920)
            self.assertEqual(max(r[3] for r in rects), 1080)
        a, b = layout(2, (1920, 1080), 10)
        self.assertEqual(b[0] - a[2], 10)
        with self.assertRaises(ValueError):
            layout(7)

    def test_overlay_draws_dividers_and_labels_only(self):
        spec = {"n": 2, "labels": ["First", "Second"]}
        img = get("split").frame_at(spec, 0.0, SMALL)
        a = np.asarray(img)
        self.assertGreater(a[:, SMALL[0] // 2, 3].min(), 0)  # divider runs the full height
        self.assertEqual(a[SMALL[1] // 2, 20, 3], 0)  # pane interior untouched
        self.assertTrue(drawn_mask(get("split").frame_at({**spec, "dividers": False}, 0, SMALL)).any())

    def test_more_labels_than_panes_refused(self):
        with self.assertRaises(ValueError):
            get("split").frame_at({"n": 1, "labels": ["a", "b"]}, 0, SMALL)


class ArchiveMat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.img = str(Path(cls.tmp.name) / "still.png")
        Image.new("RGB", (800, 600), (128, 128, 128)).save(cls.img)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_credit_pixels_are_on_the_mat_not_in_the_picture(self):
        spec = {"image": self.img, "credit": "Wellcome Collection / Public domain"}
        with_credit = get("archive_mat").frame_at(spec, 0.0, SMALL)
        without = get("archive_mat").frame_at({**spec, "credit": "x"}, 0.0, SMALL)
        x0, y0, x1, y1 = picture_rect(spec, SMALL)
        changed = np.any(np.asarray(with_credit) != np.asarray(without), axis=-1)
        self.assertTrue(changed.any())
        self.assertFalse(changed[y0:y1 + 1, x0:x1 + 1].any())
        ys, xs = np.nonzero(changed)
        self.assertGreater(ys.min(), y1)  # below the picture
        # and the picture area itself is the picture, not mat colour
        self.assertEqual(tuple(np.asarray(with_credit)[(y0 + y1) // 2, (x0 + x1) // 2][:3]) != tuple(
            int(TOKENS["palette"]["mat"][i:i + 2], 16) for i in (1, 3, 5)), True)

    def test_slow_push_scale_one_to_one_oh_six_over_the_shot(self):
        # a still with a distinct bright block near the left edge: the push crops it away
        im = Image.new("RGB", (800, 600), (60, 60, 60))
        im.paste((250, 250, 250), (0, 0, 20, 600))
        path = str(Path(self.tmp.name) / "edge.png")
        im.save(path)
        spec = {"image": path, "credit": "c", "seconds": 4.0}
        x0, y0, x1, y1 = picture_rect(spec, SMALL)
        first = np.asarray(get("archive_mat").frame_at(spec, 0.0, SMALL))[(y0 + y1) // 2, x0 + 1]
        last = np.asarray(get("archive_mat").frame_at(spec, 4.0, SMALL))[(y0 + y1) // 2, x0 + 1]
        self.assertGreater(int(first[0]), 200)  # edge block visible at the start
        self.assertLess(int(last[0]), 200)  # pushed out of frame at the end
        mid = get("archive_mat").frame_at(spec, 2.0, SMALL)
        self.assertNotEqual(mid.tobytes(), get("archive_mat").frame_at(spec, 0.0, SMALL).tobytes())

    def test_highlight_must_be_a_valid_fraction_box(self):
        with self.assertRaises(ValueError):
            get("archive_mat").frame_at({"image": self.img, "credit": "c", "highlight": [0.5, 0.5, 0.2, 0.9]}, 0, SMALL)

    def test_long_credit_wraps_inside_the_margin(self):
        spec = {"image": self.img, "credit": "A very long archive credit line / Some Institution, Department of Prints / Wikimedia Commons"}
        from test_graphics_support import ink_outside_margin
        self.assertEqual(ink_outside_margin(get("archive_mat").frame_at(spec, 0, SMALL), TOKENS["palette"]["mat"]), 0)


class SourceCard(unittest.TestCase):
    def test_credit_wrapped_inside_margins(self):
        from test_graphics_support import ink_outside_margin
        spec = {"credit": "Public domain / Wikimedia Commons, a scan of an 1850s print held by a library"}
        img = get("source_card").frame_at(spec, 0.0, SMALL)
        self.assertTrue(has_ink(img))
        self.assertEqual(ink_outside_margin(img), 0)

    def test_appears_at_its_time(self):
        spec = {"credit": "c", "at": 0.5}
        self.assertFalse(has_ink(get("source_card").frame_at(spec, 0.5 - 1 / 30, SMALL)))
        self.assertTrue(has_ink(get("source_card").frame_at(spec, 0.5, SMALL)))


class CardLines(unittest.TestCase):
    def test_moved_here_and_still_importable_from_archive_ingest(self):
        import archive_ingest as AI
        self.assertEqual(AI.card_lines("a / b, c", lambda s: len(s) <= 3), card_lines("a / b, c", lambda s: len(s) <= 3))


if __name__ == "__main__":
    unittest.main()
