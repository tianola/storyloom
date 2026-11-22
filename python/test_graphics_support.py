"""Shared helpers for the graphics tests (no tests of its own)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from tools.graphics.common import Ctx, hex_rgb  # noqa: E402
from tools.graphics.tokens import load_tokens  # noqa: E402

SMALL = (640, 360)
TOKENS = load_tokens()


def ctx_for(canvas=SMALL):
    return Ctx(canvas, TOKENS)


def margin_box(canvas=SMALL):
    c = ctx_for(canvas)
    return c.mx, c.my, canvas[0] - c.mx, canvas[1] - c.my  # exclusive right/bottom


def drawn_mask(img, bg=None):
    """Pixels that carry ink: alpha>0 for an overlay, != the background colour for an opaque frame."""
    a = np.asarray(img)
    if bg is None:
        return a[..., 3] > 0
    return np.any(a[..., :3] != np.array(hex_rgb(bg), dtype=np.uint8), axis=-1)


def ink_outside_margin(img, bg=None, canvas=SMALL):
    drawn = drawn_mask(img, bg)
    x0, y0, x1, y1 = margin_box(canvas)
    inside = np.zeros_like(drawn)
    inside[y0:y1, x0:x1] = True
    return int(np.count_nonzero(drawn & ~inside))


def ink_bbox(img, bg=None):
    ys, xs = np.nonzero(drawn_mask(img, bg))
    if not len(xs):
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def has_ink(img, bg=None):
    return bool(drawn_mask(img, bg).any())
