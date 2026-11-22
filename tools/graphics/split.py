"""Split screens: pane geometry and the labels/dividers that go over them.

The video panes themselves are NOT drawn here. A split composes live footage, which is a job for
tools/compose; this module only answers "where do the panes go" (`layout`) and draws the
transparent overlay on top of them (`labels_overlay`, registered as the primitive `split`).
The dividers run the full height or width of the frame because they separate panes of video; they
are the one thing in this package allowed to touch the safe margin. Labels stay inside it.
"""
from __future__ import annotations

import math

from .common import Pen, Primitive, line_height, plate, run_width, wrap
from .spec import BOOL, NUM, STR, obj

OVERLAY = {"split"}

_COLUMNS = {1: 1, 2: 2, 3: 3, 4: 2, 5: 3, 6: 3}


def layout(n, canvas=(1920, 1080), gap=0):
    """Pane rectangles (x0, y0, x1, y1) in reading order for `n` panes filling the canvas.

    1-3 panes sit side by side; 4 is a 2x2 grid; 5-6 are 3 columns by 2 rows. `gap` is the pixel
    width of the divider between neighbouring panes; panes meet the frame edge with no margin.
    """
    if n not in _COLUMNS:
        raise ValueError(f"split supports 1 to 6 panes, not {n}")
    w, h = int(canvas[0]), int(canvas[1])
    cols = _COLUMNS[n]
    rows = math.ceil(n / cols)
    cw = (w - gap * (cols - 1)) / cols
    ch = (h - gap * (rows - 1)) / rows
    rects = []
    for i in range(n):
        r, c = divmod(i, cols)
        x0 = round(c * (cw + gap))
        y0 = round(r * (ch + gap))
        rects.append((x0, y0, round(x0 + cw) if c < cols - 1 else w,
                      round(y0 + ch) if r < rows - 1 else h))
    return rects


SPLIT = obj({
    "n": {"type": "integer", "minimum": 1, "maximum": 6},
    "labels": {"type": "array", "maxItems": 6, "items": STR},
    "gap": NUM,
    "dividers": BOOL,
}, required=["n"])


def _check(spec, ctx):
    if len(spec.get("labels", [])) > spec["n"]:
        raise ValueError("split: more labels than panes")


def _gap(spec, ctx):
    return max(2, round(spec.get("gap", 0.008) * ctx.H))


def _draw(img, spec, t, ctx):
    pen = Pen(img)
    gap = _gap(spec, ctx)
    rects = layout(spec["n"], ctx.canvas, gap)
    if spec.get("dividers", True):
        paper = ctx.col("paper")
        cols = _COLUMNS[spec["n"]]
        for a, b in zip(rects, rects[1:]):
            if b[0] > a[2]:
                pen.rect((a[2], 0, b[0] - 1, ctx.H - 1), fill=paper)
        rows = math.ceil(spec["n"] / cols)
        for r in range(1, rows):
            top = rects[r * cols][1]
            pen.rect((0, top - gap, ctx.W - 1, top - 1), fill=paper)
    font = ctx.font("label")
    ink, paper = ctx.col("ink"), ctx.col("paper")
    pad = round(font.size * 0.35)
    for rect, label in zip(rects, spec.get("labels", [])):
        if not label:
            continue
        room = min(rect[2], ctx.box[2]) - max(rect[0], ctx.box[0]) - 2 * pad - ctx.W * 0.01
        lines = wrap(font, label, room)
        w = max(run_width(font, ln) for ln in lines) + 2 * pad
        h = line_height(font) * len(lines) + pad
        x = max(rect[0], ctx.box[0]) + ctx.W * 0.005
        y = min(rect[3], ctx.box[3]) - h - ctx.H * 0.012
        plate(pen, ctx, (x, y, x + w, y + h), ink, alpha=0.82)
        for i, ln in enumerate(lines):
            pen.text(x + pad, y + pad / 2 + i * line_height(font), ln, font, paper)


labels_overlay = Primitive("split", SPLIT, None, _draw, True, check=_check)
labels_overlay.layout = layout
split = labels_overlay
PRIMITIVES = {"split": split}
