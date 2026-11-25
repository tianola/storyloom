"""Stats family: big_number, ratio_compare, bar_compare, tally (+ figure grid and timeline)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_graphics_support import SMALL, TOKENS, drawn_mask, has_ink, ink_bbox  # noqa: E402

import numpy as np  # noqa: E402

from tools.graphics import get  # noqa: E402
from tools.graphics.common import contrast, hex_rgb  # noqa: E402
from tools.graphics.presets import PRESETS  # noqa: E402

FULL = (1920, 1080)
TALLY = {"left": {"label": "First Clinic", "marks": 11, "per": 100},
         "right": {"label": "Second Clinic", "marks": 3, "per": 100},
         "build": {"left": [0.15, 0.7], "right": [0.5, 0.35]},
         "source": "1846 · Semmelweis 1861", "type": {"label": 0.06, "number": 0.1}}


def colour_pixels(img, name, box=None):
    a = np.asarray(img)
    hit = np.all(a[..., :3] == np.array(hex_rgb(TOKENS["palette"][name])), axis=-1) & (a[..., 3] > 200)
    if box:
        x0, y0, x1, y1 = box
        hit = hit[y0:y1, x0:x1]
    return int(hit.sum())


class Tally(unittest.TestCase):
    def test_the_brief_spec_works_and_has_both_groups_and_the_tag(self):
        img = get("tally").frame_at(TALLY, 2.0, FULL)
        self.assertTrue(has_ink(img))
        left = img.crop((0, 0, 960, 1080)).getchannel("A").getbbox()
        right = img.crop((960, 0, 1920, 1080)).getchannel("A").getbbox()
        self.assertIsNotNone(left)
        self.assertIsNotNone(right)
        self.assertGreater(right[2] + 960, 1700)  # tag sits bottom-right

    def test_first_mark_invisible_one_frame_before_at_and_visible_at_at(self):
        before = get("tally").frame_at(TALLY, 0.15 - 1 / 30, SMALL)
        at = get("tally").frame_at(TALLY, 0.15, SMALL)
        self.assertFalse(has_ink(before))
        self.assertGreater(colour_pixels(at, "data_b"), 0)

    def test_marks_arrive_one_by_one_and_right_group_waits_for_its_window(self):
        counts = [colour_pixels(get("tally").frame_at(TALLY, t, FULL), "data_b", (0, 0, 960, 1080))
                  for t in (0.15, 0.15 + 0.7 * 3 / 11 + 0.2, 0.15 + 0.7 * 7 / 11 + 0.2, 1.2)]
        self.assertTrue(all(b > a for a, b in zip(counts, counts[1:])), counts)
        early = get("tally").frame_at(TALLY, 0.3, FULL)
        self.assertIsNone(early.crop((960, 0, 1920, 930)).getchannel("A").getbbox())

    def test_count_text_reads_n_per_100_only_after_its_marks(self):
        mid = get("tally").frame_at(TALLY, 0.5, FULL)
        done = get("tally").frame_at(TALLY, 1.2, FULL)
        box = (96, 800, 960, 940)
        self.assertEqual(colour_pixels(mid, "data_b", box), 0)
        self.assertGreater(colour_pixels(done, "data_b", box), 500)

    def test_text_meets_mobile_floor_and_contrast(self):
        img = get("tally").frame_at(TALLY, 2.0, FULL)
        a = np.asarray(img.convert("RGB")).astype(int)
        plate = tuple(a[560, 130])
        ink = hex_rgb(TOKENS["palette"]["ink"])
        self.assertGreaterEqual(contrast(ink, plate), 4.5)
        # the label "First Clinic" is set at >= 0.06 H: its cap height is about 0.73 of the em
        region = a[520:620, 100:940]
        dark = np.nonzero(region.sum(axis=2) < 200)
        height = dark[0].max() - dark[0].min()
        self.assertGreaterEqual(height, 0.06 * 1080 * 0.7 * 0.95)

    def test_type_override_under_the_floor_is_refused(self):
        with self.assertRaises(ValueError):
            get("tally").frame_at({**TALLY, "type": {"label": 0.04, "number": 0.1}}, 1.0, SMALL)

    def test_bad_marks_refused(self):
        bad = {**TALLY, "left": {"label": "x", "marks": -1, "per": 100}}
        with self.assertRaises(ValueError):
            get("tally").frame_at(bad, 1.0, SMALL)


class FullFrameStats(unittest.TestCase):
    def test_ratio_preset_draws_both_ratios_in_order(self):
        prim, spec = PRESETS["ratio-1846"]
        self.assertEqual(prim, "ratio_compare")
        self.assertEqual(spec["a"]["value"], "1 in 9")
        self.assertEqual(spec["b"]["value"], "1 in 36")
        p = get("ratio_compare")
        early = p.frame_at(spec, 0.6, SMALL)
        late = p.frame_at(spec, 2.0, SMALL)
        self.assertGreater(colour_pixels(early, "data_b"), 0)
        self.assertEqual(colour_pixels(early, "data_a"), 0)
        self.assertGreater(colour_pixels(late, "data_a"), 0)

    def test_big_number_text_is_display_sized(self):
        img = get("big_number").frame_at({"value": "HEH", "label": "x"}, 1.0, FULL)
        a = np.asarray(img.convert("RGB")).astype(int)
        dark = np.nonzero(a.sum(axis=2) < 200)
        self.assertGreaterEqual(dark[0].max() - dark[0].min(), 0.10 * 1080 * 0.7)

    def test_bar_compare_bars_grow_to_scale(self):
        spec = {"bars": [{"label": "A", "value": 10, "color": "data_a"},
                         {"label": "B", "value": 5, "color": "data_b"}], "build": [0, 1]}
        img = get("bar_compare").frame_at(spec, 2.0, FULL)
        wa = ink_width(img, "data_a")
        wb = ink_width(img, "data_b")
        self.assertAlmostEqual(wb / wa, 0.5, delta=0.02)
        with self.assertRaises(ValueError):
            get("bar_compare").frame_at({"bars": []}, 0, SMALL)

    def test_big_number_count_up(self):
        spec = {"value": 100, "label": "x", "count_up": True, "build": [0, 1]}
        a = get("big_number").frame_at(spec, 0.4, SMALL).tobytes()
        b = get("big_number").frame_at(spec, 1.5, SMALL).tobytes()
        self.assertNotEqual(a, b)


def ink_width(img, name):
    a = np.asarray(img)
    hit = np.all(a[..., :3] == np.array(hex_rgb(TOKENS["palette"][name])), axis=-1)
    xs = np.nonzero(hit.any(axis=0))[0]
    return int(xs.max() - xs.min() + 1)


if __name__ == "__main__":
    unittest.main()
