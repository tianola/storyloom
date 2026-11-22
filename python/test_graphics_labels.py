"""labels family: plates, callout, lower third, underline, circle, date_stamp, day_labels."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_graphics_support import SMALL, TOKENS, has_ink, ink_bbox  # noqa: E402

import numpy as np  # noqa: E402

from tools.graphics import get  # noqa: E402
from tools.graphics.common import contrast, hex_rgb  # noqa: E402
from tools.graphics.labels import STAMP_PLATE, STAMP_TEXT  # noqa: E402

FULL = (1920, 1080)
P = {k: hex_rgb(v) for k, v in TOKENS["palette"].items()}


class Labels(unittest.TestCase):
    def test_label_text_height_meets_the_mobile_floor(self):
        img = get("label").frame_at({"text": "HEH", "build": [0, 0.01]}, 1.0, FULL)
        a = np.asarray(img.convert("RGB")).astype(int)
        dark = np.nonzero((a.sum(axis=2) < 200) & (np.asarray(img)[..., 3] > 0))
        self.assertGreaterEqual(dark[0].max() - dark[0].min(), 0.06 * 1080 * 0.7)

    def test_label_contrast_is_measured_from_the_pixels(self):
        img = get("label").frame_at({"text": "Vienna", "build": [0, 0.01]}, 1.0, FULL)
        a = np.asarray(img)
        box = ink_bbox(img)
        plate = tuple(int(v) for v in a[box[1] + 3, box[0] + 20][:3])
        text = tuple(int(v) for v in a[box[1]:box[3], box[0]:box[2], :3].reshape(-1, 3)[
            a[box[1]:box[3], box[0]:box[2], :3].reshape(-1, 3).sum(axis=1).argmin()])
        self.assertGreaterEqual(contrast(plate, text), 4.5)

    def test_plate_colour_picks_readable_text(self):
        for plate in ("paper", "ink", "danger", "cool", "mat"):
            img = get("label").frame_at({"text": "Ward", "color": plate, "build": [0, 0.01]}, 1.0, FULL)
            a = np.asarray(img)
            box = ink_bbox(img)
            flat = a[box[1]:box[3], box[0]:box[2], :3].reshape(-1, 3).astype(int)
            lum = flat.sum(axis=1)
            fg = tuple(flat[lum.argmax() if sum(P[plate]) < 384 else lum.argmin()])
            self.assertGreaterEqual(contrast(P[plate], fg), 4.5, plate)

    def test_label_visible_exactly_at_its_time(self):
        spec = {"text": "x", "build": [0.4, 0.2]}
        self.assertFalse(has_ink(get("label").frame_at(spec, 0.4 - 1 / 30, SMALL)))
        self.assertTrue(has_ink(get("label").frame_at(spec, 0.4, SMALL)))

    def test_callout_leader_reaches_the_target(self):
        spec = {"text": "Aisle", "target": [0.7, 0.6], "pos": [0.3, 0.2], "build": [0, 0.5]}
        a = get("callout").frame_at(spec, 0.25, SMALL)
        b = get("callout").frame_at(spec, 1.0, SMALL)
        self.assertLess(int(np.asarray(a)[..., 3].astype(bool).sum()), int(np.asarray(b)[..., 3].astype(bool).sum()))

    def test_lower_third_and_underline_and_circle_draw_progressively(self):
        for name, spec in (("underline", {"box": [0.2, 0.3, 0.8, 0.5], "build": [0, 1]}),
                           ("circle", {"center": [0.5, 0.5], "build": [0, 1]})):
            a = get(name).frame_at(spec, 0.3, SMALL)
            b = get(name).frame_at(spec, 1.5, SMALL)
            self.assertLess(int((np.asarray(a)[..., 3] > 0).sum()), int((np.asarray(b)[..., 3] > 0).sum()), name)
        self.assertTrue(has_ink(get("lower_third").frame_at({"title": "Ignaz", "subtitle": "Assistant"}, 1.0, SMALL)))


class DateStamp(unittest.TestCase):
    SPEC = {"text": "March 1847", "at": 0.4, "type": {"label": 0.06, "number": 0.1}}

    def test_invisible_one_frame_before_and_visible_at_at(self):
        self.assertFalse(has_ink(get("date_stamp").frame_at(self.SPEC, 0.4 - 1 / 30, SMALL)))
        self.assertTrue(has_ink(get("date_stamp").frame_at(self.SPEC, 0.4, SMALL)))

    def test_top_left_inside_margin_and_settles(self):
        a = get("date_stamp").frame_at(self.SPEC, 0.4, FULL)
        b = get("date_stamp").frame_at(self.SPEC, 1.5, FULL)
        ba, bb = ink_bbox(a), ink_bbox(b)
        self.assertGreaterEqual(bb[0], 96)
        self.assertGreaterEqual(bb[1], 54)
        self.assertLess(bb[2], 960)
        self.assertLess(bb[3], 400)
        self.assertNotEqual(ba[1], bb[1])  # it moved while settling
        self.assertGreaterEqual(ba[1], 54)

    def test_stamp_colours_meet_contrast(self):
        self.assertGreaterEqual(contrast(P[STAMP_TEXT], P[STAMP_PLATE]), 4.5)


class DayLabels(unittest.TestCase):
    SPEC = {"cycle": [["MON", "first"], ["TUE", "second"], ["WED", "first"]], "step": 0.8,
            "type": {"label": 0.06, "number": 0.1}}

    def _alpha_sum(self, img, x0, x1):
        return int(np.asarray(img)[:, x0:x1, 3].astype(int).sum())

    def test_active_clinic_is_bright_other_dimmed_and_they_alternate(self):
        w = SMALL[0]
        p = get("day_labels")
        t0 = p.frame_at(self.SPEC, 0.2, SMALL)      # MON -> first clinic (left)
        t1 = p.frame_at(self.SPEC, 1.0, SMALL)      # TUE -> second clinic (right)
        left0, right0 = self._alpha_sum(t0, 0, w // 2), self._alpha_sum(t0, w // 2, w)
        left1, right1 = self._alpha_sum(t1, 0, w // 2), self._alpha_sum(t1, w // 2, w)
        self.assertGreater(left0, 0)
        self.assertGreater(right0, 0)  # the other slot is dimmed, not gone
        self.assertGreater(left0, right0 * 1.5)
        self.assertGreater(right1, left1 * 1.5)

    def test_slots_sit_at_thirty_and_seventy_percent(self):
        img = get("day_labels").frame_at(self.SPEC, 0.2, FULL)
        a = np.asarray(img)[..., 3]
        for x in (0.3, 0.7):
            col = a[:, int(1920 * x)]
            self.assertGreater(int(col.max()), 0)
        xs = np.nonzero(a[:, :960].any(axis=0))[0]
        self.assertAlmostEqual((xs.min() + xs.max()) / 2 / 1920, 0.3, delta=0.01)
        top = np.nonzero(a.any(axis=1))[0].min()
        self.assertLess(top, 1080 * 0.15)

    def test_day_text_advances_each_step(self):
        p = get("day_labels")
        self.assertNotEqual(p.frame_at(self.SPEC, 0.79, SMALL).tobytes()[:0] or p.frame_at(self.SPEC, 0.3, SMALL).tobytes(),
                            p.frame_at(self.SPEC, 0.9, SMALL).tobytes())

    def test_bad_clinic_or_step_refused(self):
        with self.assertRaises(ValueError):
            get("day_labels").frame_at({"cycle": [["MON", "third"]], "step": 1}, 0, SMALL)
        with self.assertRaises(ValueError):
            get("day_labels").frame_at({"cycle": [["MON", "first"]], "step": 0}, 0, SMALL)


if __name__ == "__main__":
    unittest.main()
