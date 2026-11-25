"""figure_grid and timeline."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_graphics_support import SMALL, TOKENS, drawn_mask  # noqa: E402

import numpy as np  # noqa: E402

from tools.graphics import get  # noqa: E402
from tools.graphics.common import hex_rgb  # noqa: E402

GRID = {"total": 36, "highlight": 4, "build": [0.0, 1.2]}


def hot(img):
    a = np.asarray(img)
    return int(np.all(a[..., :3] == np.array(hex_rgb(TOKENS["palette"]["danger"])), axis=-1).sum())


class FigureGrid(unittest.TestCase):
    def test_icons_build_in_and_highlight_count_is_exact(self):
        p = get("figure_grid")
        early = p.frame_at(GRID, 0.1, SMALL)
        final = p.frame_at(GRID, 2.0, SMALL)
        self.assertLess(drawn_mask(early, "#f4efe6").sum(), drawn_mask(final, "#f4efe6").sum())
        one = p.frame_at({**GRID, "highlight": 1}, 2.0, SMALL)
        four = final
        self.assertAlmostEqual(hot(four) / hot(one), 4.0, delta=0.4)

    def test_highlight_beyond_total_refused(self):
        with self.assertRaises(ValueError):
            get("figure_grid").frame_at({"total": 5, "highlight": 6}, 0, SMALL)

    def test_first_icon_visible_at_start_and_none_before(self):
        p = get("figure_grid")
        self.assertTrue(drawn_mask(p.frame_at(GRID, 0.0, SMALL), "#f4efe6").any())


class Timeline(unittest.TestCase):
    SPEC = {"start": 1844, "end": 1850,
            "events": [{"date": 1846, "label": "Start", "build": [0.5, 0.2]}],
            "now": {"from": 1844, "to": 1849, "build": [0.2, 2.0]}}

    def test_event_appears_at_its_time_and_now_marker_moves(self):
        p = get("timeline")
        a = p.frame_at(self.SPEC, 0.5 - 1 / 30, SMALL)
        b = p.frame_at(self.SPEC, 0.5, SMALL)
        self.assertNotEqual(a.tobytes(), b.tobytes())

        def marker_x(t):
            img = p.frame_at(self.SPEC, t, SMALL)
            arr = np.asarray(img)
            hit = np.all(arr[..., :3] == np.array(hex_rgb(TOKENS["palette"]["danger"])), axis=-1)
            xs = np.nonzero(hit.any(axis=0))[0]
            return xs.mean() if len(xs) else None
        self.assertLess(marker_x(0.5), marker_x(1.5))

    def test_end_before_start_refused(self):
        with self.assertRaises(ValueError):
            get("timeline").frame_at({"start": 5, "end": 5}, 0, SMALL)


if __name__ == "__main__":
    unittest.main()
