"""board, board_card and the 3D card textures."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_graphics_support import SMALL, TOKENS, has_ink, ink_bbox  # noqa: E402

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from tools.graphics import get  # noqa: E402
from tools.graphics.boards import export_card_textures  # noqa: E402
from tools.graphics.common import hex_rgb  # noqa: E402

BOARD = {"cards": [{"id": "a", "title": "Fever", "x": 0.2, "y": 0.3, "build": [0.0, 0.3]},
                   {"id": "b", "title": "Hands", "x": 0.7, "y": 0.4, "build": [0.5, 0.3], "remove": [1.5, 0.3]},
                   {"id": "c", "title": "Miasma", "x": 0.4, "y": 0.8, "cross_out": [1.0, 0.4]}],
         "strings": [{"from": "a", "to": "b", "build": [0.8, 0.4]}]}
MAT = hex_rgb(TOKENS["palette"]["mat"])


def diff(a, b):
    return int(np.any(np.asarray(a) != np.asarray(b), axis=-1).sum())


class Board(unittest.TestCase):
    def test_cards_add_and_remove_over_time(self):
        p = get("board")
        before = p.frame_at(BOARD, 0.5 - 1 / 30, SMALL)
        at = p.frame_at(BOARD, 0.5, SMALL)
        self.assertGreater(diff(before, at), 50)
        shown = p.frame_at(BOARD, 1.4, SMALL)
        gone = p.frame_at(BOARD, 2.0, SMALL)
        self.assertGreater(diff(shown, gone), 50)

    def test_cross_out_draws_progressively(self):
        p = get("board")
        a, b = p.frame_at(BOARD, 1.1, SMALL), p.frame_at(BOARD, 1.6, SMALL)
        red = np.array(hex_rgb(TOKENS["palette"]["danger"]))
        n = lambda im: int(np.all(np.asarray(im)[..., :3] == red, axis=-1).sum())  # noqa: E731
        self.assertLess(n(a), n(b))

    def test_unknown_string_end_and_duplicate_ids_refused(self):
        with self.assertRaises(ValueError):
            get("board").frame_at({**BOARD, "strings": [{"from": "a", "to": "zzz"}]}, 0, SMALL)
        dup = {"cards": [{"id": "a", "title": "x", "x": 0.2, "y": 0.2}, {"id": "a", "title": "y", "x": 0.5, "y": 0.5}]}
        with self.assertRaises(ValueError):
            get("board").frame_at(dup, 0, SMALL)


class BoardCard(unittest.TestCase):
    SPEC = {"title": "POSITION", "pin": True, "corner": "top-right",
            "type": {"label": 0.06, "number": 0.1}}

    def test_pin_settles_into_the_requested_corner(self):
        p = get("board_card")
        red = np.array(hex_rgb(TOKENS["palette"]["danger"]))

        def pin_centre(corner, t):
            img = p.frame_at({**self.SPEC, "corner": corner}, t, SMALL)
            arr = np.asarray(img).astype(int)
            hit = (arr[..., 0] > 120) & (arr[..., 1] < 90) & (arr[..., 2] < 90) & (arr[..., 3] > 0)
            ys, xs = np.nonzero(hit)
            return xs.mean(), ys.mean(), ink_bbox(img)

        for corner in ("top-left", "top-right", "bottom-left", "bottom-right"):
            x, y, box = pin_centre(corner, 1.5)
            cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            self.assertEqual(x > cx, corner.endswith("right"), corner)
            self.assertEqual(y > cy, corner.startswith("bottom"), corner)
        x_early, _, _ = pin_centre("top-right", 0.2)
        x_late, _, _ = pin_centre("top-right", 1.5)
        self.assertFalse(np.isnan(x_early))
        self.assertGreater(abs(x_early - x_late), 5)

    def test_card_present_at_start_and_bad_corner_refused(self):
        self.assertTrue(has_ink(get("board_card").frame_at(self.SPEC, 0.0, SMALL)))
        with self.assertRaises(ValueError):
            get("board_card").frame_at({**self.SPEC, "corner": "middle"}, 0, SMALL)


class Textures(unittest.TestCase):
    def test_one_png_per_card_with_transparent_corners(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = export_card_textures(BOARD, tmp)
            self.assertEqual(sorted(p.name for p in paths), ["card_a.png", "card_b.png", "card_c.png"])
            for p in paths:
                im = Image.open(p)
                self.assertEqual(im.mode, "RGBA")
                self.assertEqual(im.getpixel((0, 0))[3], 0)
                self.assertGreater(im.width, 600)


if __name__ == "__main__":
    unittest.main()
