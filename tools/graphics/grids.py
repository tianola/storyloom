"""Figure grids: N little people, K of them highlighted, building in one by one."""
from __future__ import annotations

import math

from .common import Pen, Primitive, line_height, reached
from .spec import BUILD, STR, build_window, obj

OVERLAY = set()

FIGURE_GRID = obj({
    "total": {"type": "integer", "minimum": 1, "maximum": 400},
    "highlight": {"type": "integer", "minimum": 0},
    "columns": {"type": "integer", "minimum": 1},
    "label": STR,
    "color": STR,
    "build": BUILD,
    "source": STR,
}, required=["total", "highlight"])


def _check(spec, ctx):
    if spec["highlight"] > spec["total"]:
        raise ValueError(f"figure_grid: highlight {spec['highlight']} exceeds total {spec['total']}")


def _person(pen, cx, top, w, h, colour):
    """Head (ellipse) over a rounded-rectangle torso: the whole glyph fits in w x h."""
    head = w * 0.52
    pen.ellipse((cx - head / 2, top, cx + head / 2, top + head), fill=colour)
    body_top = top + head + h * 0.04
    pen.rrect((cx - w / 2, body_top, cx + w / 2, top + h), w * 0.32, fill=colour)


def _layout(spec, ctx):
    n = spec["total"]
    label_h = line_height(ctx.font("label")) * 1.4 if spec.get("label") else 0
    area_w = ctx.bw
    area_h = ctx.bh - label_h - (ctx.H * 0.08 if spec.get("source") else 0)
    cols = spec.get("columns")
    if not cols:
        best = None
        for c in range(1, n + 1):
            rows = math.ceil(n / c)
            cell = min(area_w / c, area_h / (rows * 1.45))
            if best is None or cell > best[0]:
                best = (cell, c)
        cols = best[1]
    rows = math.ceil(n / cols)
    cell_w = min(area_w / cols, area_h / (rows * 1.45))
    cell_h = cell_w * 1.45
    gw, gh = cols * cell_w, rows * cell_h
    x0 = (ctx.box[0] + ctx.box[2] - gw) / 2
    y0 = ctx.box[1] + label_h + (area_h - gh) / 2
    return cols, cell_w, cell_h, x0, y0, label_h


def _draw(img, spec, t, ctx):
    from .stats import source_tag
    pen = Pen(img)
    cols, cw, ch, x0, y0, label_h = _layout(spec, ctx)
    at, dur = build_window(spec.get("build"), (0.0, 1.0))
    n, k = spec["total"], spec["highlight"]
    base = ctx.col("ink")
    base = tuple(round(base[i] * 0.35 + ctx.col("paper")[i] * 0.65) for i in range(3))
    hot = ctx.col(spec.get("color", "danger"))
    gw, gh = cw * 0.56, ch * 0.78
    for i in range(n):
        ti = at + dur * i / max(1, n)
        if not reached(t, ti):
            break
        r, c = divmod(i, cols)
        cx = x0 + (c + 0.5) * cw
        top = y0 + r * ch + (ch - gh) / 2
        _person(pen, cx, top, gw, gh, hot if i < k else base)
    if spec.get("label"):
        lab = ctx.font("label")
        pen.text(ctx.W / 2, ctx.box[1], spec["label"], lab, ctx.col("ink"), ax="m", ay="t")
    if spec.get("source"):
        source_tag(pen, ctx, spec["source"])


figure_grid = Primitive("figure_grid", FIGURE_GRID, lambda s, c: c.solid("paper"), _draw, False, check=_check)
PRIMITIVES = {"figure_grid": figure_grid}
