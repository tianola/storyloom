"""Stat cards: big_number, ratio_compare, bar_compare (full frame) and tally (overlay).

A stat is one claim and one number. These cards put the number at display size, the label at label
size, and nothing else on the frame except an optional source tag in the corner.
"""
from __future__ import annotations

import math

from .common import (Pen, Primitive, line_height, plate, reached, prog, run_width, source_tag, wrap)
from .spec import BOOL, BUILD, NUM, STR, build_window, obj

OVERLAY = {"tally"}


def _paper(spec, ctx):
    return ctx.solid("paper")


# --- big_number -----------------------------------------------------------------------------------
BIG_NUMBER = obj({
    "value": {"type": ["string", "number"]},
    "label": STR,
    "about": BOOL,
    "color": STR,
    "count_up": BOOL,
    "build": BUILD,
    "source": STR,
}, required=["value", "label"])


def _fmt(v):
    if not isinstance(v, (int, float)):
        return str(v)
    return f"{v:,.0f}" if float(v).is_integer() else f"{v:g}"


def _big_draw(img, spec, t, ctx):
    pen = Pen(img)
    alpha, e = ctx.appear(t, spec.get("build"))
    value = spec["value"]
    if spec.get("count_up") and isinstance(value, (int, float)):
        value = value * e
    text = _fmt(value)
    colour = ctx.col(spec.get("color", "ink"))
    num = ctx.fit("display", text, ctx.bw * 0.95)
    lab = ctx.font("label")
    lines = wrap(lab, spec["label"], ctx.bw * 0.85)
    about_h = line_height(lab) if spec.get("about") else 0
    total = about_h + line_height(num) + line_height(lab) * len(lines) + ctx.H * 0.02
    y = (ctx.box[1] + ctx.box[3] - total) / 2
    cx = ctx.W / 2
    if alpha > 0:
        if about_h:
            pen.text(cx, y, "about", lab, ctx.col("ink"), ax="m", alpha=alpha * 0.8)
            y += about_h
        pen.text(cx, y, text, num, colour, ax="m", alpha=alpha)
        y += line_height(num) + ctx.H * 0.02
        for ln in lines:
            pen.text(cx, y, ln, lab, ctx.col("ink"), ax="m", alpha=alpha)
            y += line_height(lab)
    if spec.get("source"):
        source_tag(pen, ctx, spec["source"], alpha=1.0 if alpha > 0 else 0.0)


big_number = Primitive("big_number", BIG_NUMBER, _paper, _big_draw, False)


# --- ratio_compare --------------------------------------------------------------------------------
_SIDE = {"type": "object", "additionalProperties": False, "required": ["value", "label"],
         "properties": {"value": STR, "label": STR, "color": STR}}
RATIO = obj({
    "a": _SIDE,
    "b": _SIDE,
    "about": BOOL,
    "source": STR,
    "build": {"type": "object", "additionalProperties": False,
              "properties": {"a": BUILD, "b": BUILD}},
}, required=["a", "b"])


def _ratio_draw(img, spec, t, ctx):
    pen = Pen(img)
    builds = spec.get("build") or {}
    sides = (("a", ctx.W * 0.25, builds.get("a", [0.0, 0.5]), "data_b"),
             ("b", ctx.W * 0.75, builds.get("b", [0.45, 0.5]), "data_a"))
    half = ctx.bw / 2 * 0.9
    lab = ctx.font("label")
    top, bottom = ctx.box[1], ctx.box[3]
    mid = (top + bottom) / 2
    pen.line([(ctx.W / 2, top + ctx.H * 0.12), (ctx.W / 2, bottom - ctx.H * 0.12)],
             ctx.col("ink"), ctx.stroke, alpha=0.25)
    for key, cx, build, default in sides:
        side = spec[key]
        alpha, _ = ctx.appear(t, build)
        if alpha <= 0:
            continue
        num = ctx.fit("display", side["value"], half)
        lines = wrap(lab, side["label"], half)
        about_h = line_height(lab) if spec.get("about") else 0
        total = about_h + line_height(num) + len(lines) * line_height(lab)
        y = mid - total / 2
        if about_h:
            pen.text(cx, y, "about", lab, ctx.col("ink"), ax="m", alpha=alpha * 0.8)
            y += about_h
        pen.text(cx, y, side["value"], num, ctx.col(side.get("color", default)), ax="m", alpha=alpha)
        y += line_height(num)
        for ln in lines:
            pen.text(cx, y, ln, lab, ctx.col("ink"), ax="m", alpha=alpha)
            y += line_height(lab)
    if spec.get("source"):
        source_tag(pen, ctx, spec["source"], alpha=1.0 if t >= 0 else 0.0)


ratio_compare = Primitive("ratio_compare", RATIO, _paper, _ratio_draw, False)


# --- bar_compare ----------------------------------------------------------------------------------
BARS = obj({
    "bars": {"type": "array", "minItems": 1, "maxItems": 6, "items": {
        "type": "object", "additionalProperties": False, "required": ["label", "value"],
        "properties": {"label": STR, "value": NUM, "color": STR, "text": STR}}},
    "max": NUM,
    "unit": STR,
    "build": BUILD,
    "source": STR,
}, required=["bars"])


def _bars_draw(img, spec, t, ctx):
    pen = Pen(img)
    bars = spec["bars"]
    n = len(bars)
    vmax = float(spec.get("max") or max(b["value"] for b in bars) or 1.0)
    lab = ctx.font("label")
    unit = spec.get("unit", "")
    label_w = max(run_width(lab, b["label"]) for b in bars) + ctx.W * 0.02
    label_w = min(label_w, ctx.bw * 0.38)
    value_w = max(run_width(lab, b.get("text") or f"{_fmt(b['value'])}{unit}") for b in bars) + ctx.W * 0.015
    x0 = ctx.box[0] + label_w
    x1 = ctx.box[2] - value_w
    row = min(ctx.H * 0.16, (ctx.bh - ctx.H * 0.08) / n)
    top = (ctx.box[1] + ctx.box[3] - row * n) / 2
    at, dur = build_window(spec.get("build"), (0.0, 0.8))
    for i, b in enumerate(bars):
        cy = top + row * (i + 0.5)
        label_alpha = 1.0 if reached(t, at) else 0.0
        pen.text(x0 - ctx.W * 0.015, cy, b["label"], lab, ctx.col("ink"), ax="r", ay="m",
                 alpha=label_alpha)
        offset = (dur * 0.4) * (i / max(1, n - 1)) if n > 1 else 0.0
        p = prog(t, at + offset, dur * 0.6)
        eased = 1 - (1 - p) ** 3
        full = (x1 - x0) * min(1.0, b["value"] / vmax)
        thick = row * 0.55
        colour = ctx.col(b.get("color", "data_a" if i % 2 == 0 else "data_b"))
        if p > 0:
            pen.rect((x0, cy - thick / 2, x0 + max(2, full * eased), cy + thick / 2), fill=colour)
        if p >= 1.0:
            pen.text(x0 + full + ctx.W * 0.01, cy, b.get("text") or f"{_fmt(b['value'])}{unit}",
                     lab, ctx.col("ink"), ax="l", ay="m")
    pen.line([(x0, top - row * 0.1), (x0, top + row * n + row * 0.1)], ctx.col("ink"), ctx.stroke)
    if spec.get("source"):
        source_tag(pen, ctx, spec["source"])


bar_compare = Primitive("bar_compare", BARS, _paper, _bars_draw, False)


# --- tally ----------------------------------------------------------------------------------------
_TALLY_SIDE = {"type": "object", "additionalProperties": False, "required": ["label", "marks", "per"],
               "properties": {"label": STR, "marks": {"type": "integer", "minimum": 0},
                              "per": {"type": "integer", "minimum": 1}, "color": STR}}
TALLY = obj({
    "left": _TALLY_SIDE,
    "right": _TALLY_SIDE,
    "build": {"type": "object", "additionalProperties": False,
              "properties": {"left": BUILD, "right": BUILD}},
    "source": STR,
}, required=["left", "right"])

MARK_POP = 0.15  # seconds a mark takes to reach full length once it lands


def _tally_layout(spec, ctx):
    """Plates, label rows, gate cells and count rows for both sides (pure geometry)."""
    gap = ctx.W * 0.02
    half_w = (ctx.bw - gap) / 2
    pad = ctx.H * 0.025
    lab, num = ctx.font("label"), ctx.font("number")
    tag_h = line_height(ctx.font("caption")) + round(ctx.font("caption").size * 0.4)
    inner_w = half_w - 2 * pad
    gates = max(math.ceil(spec["left"]["marks"] / 5), math.ceil(spec["right"]["marks"] / 5), 1)
    gh, gw = ctx.H * 0.12, ctx.H * 0.12 * 1.3
    gg = gw * 0.18
    while True:
        per_row = max(1, int((inner_w + gg) // (gw + gg)))
        rows = math.ceil(gates / per_row)
        if rows * (gh + gg) - gg <= ctx.H * 0.27 or gh < ctx.H * 0.03:
            break
        gh, gw, gg = gh * 0.9, gw * 0.9, gg * 0.9
    marks_h = rows * (gh + gg) - gg
    content_h = line_height(lab) + pad * 0.5 + marks_h + pad * 0.5 + line_height(num)
    plate_h = content_h + 2 * pad
    y1 = ctx.box[3] - tag_h - ctx.H * 0.015
    y0 = y1 - plate_h
    out = {}
    for key, x0 in (("left", ctx.box[0]), ("right", ctx.box[0] + half_w + gap)):
        side = spec[key]
        box = (x0, y0, x0 + half_w, y1)
        n_gates = math.ceil(side["marks"] / 5)
        cols = min(per_row, max(1, n_gates))
        grid_w = cols * gw + (cols - 1) * gg
        gx0 = x0 + (half_w - grid_w) / 2
        gy0 = y0 + pad + line_height(lab) + pad * 0.5
        out[key] = {"box": box, "pad": pad, "label_xy": (x0 + half_w / 2, y0 + pad),
                    "gate": (gx0, gy0, gw, gh, gg, per_row),
                    "count_xy": (x0 + half_w / 2, y1 - pad)}
    return out


def _gate_marks(index, gate):
    """Line segments (start, end) of mark number `index` (0-based) in grid `gate`."""
    gx0, gy0, gw, gh, gg, per_row = gate
    g, k = divmod(index, 5)
    r, c = divmod(g, per_row)
    ox = gx0 + c * (gw + gg)
    oy = gy0 + r * (gh + gg)
    if k < 4:
        x = ox + gw * (0.12 + 0.76 * k / 3.0)
        return (x, oy + gh), (x, oy)
    return (ox, oy + gh * 0.85), (ox + gw, oy + gh * 0.15)


def _tally_draw(img, spec, t, ctx):
    pen = Pen(img)
    layout = _tally_layout(spec, ctx)
    builds = spec.get("build") or {}
    lab, num = ctx.font("label"), ctx.font("number")
    ink = ctx.col("ink")
    first_at = None
    for key, default_color, default_build in (("left", "data_b", [0.0, 1.0]), ("right", "data_a", [0.5, 0.5])):
        side, geo = spec[key], layout[key]
        at, dur = build_window(builds.get(key), default_build)
        first_at = at if first_at is None else min(first_at, at)
        if not reached(t, at):
            continue
        plate(pen, ctx, geo["box"], ctx.col("paper"), alpha=0.94)
        pen.text(*geo["label_xy"], side["label"], ctx.fit("label", side["label"], geo["box"][2] - geo["box"][0] - 2 * geo["pad"]),
                 ink, ax="m", ay="t")
        colour = ctx.col(side.get("color", default_color))
        n = side["marks"]
        width = max(3, round(geo["gate"][3] * 0.07))
        for m in range(n):
            tm = at + dur * m / max(1, n)
            if not reached(t, tm):
                break
            f = 0.6 + 0.4 * min(1.0, max(0.0, (t - tm) / MARK_POP))
            (x0, y0), (x1, y1) = _gate_marks(m, geo["gate"])
            pen.line([(x0, y0), (x0 + (x1 - x0) * f, y0 + (y1 - y0) * f)], colour, width)
        if reached(t, at + dur):
            fade = min(1.0, 0.4 + 0.6 * (t - (at + dur)) / 0.2)
            number, tail = str(n), f" per {side['per']}"
            wn, wt = run_width(num, number), run_width(lab, tail)
            cx, by = geo["count_xy"]
            x = cx - (wn + wt) / 2
            asc_n = num.getmetrics()[0]
            baseline = by - num.getmetrics()[1]
            pen.text(x, baseline - asc_n, number, num, colour, ax="l", ay="t", alpha=fade)
            pen.text(x + wn, baseline - lab.getmetrics()[0], tail, lab, ink, ax="l", ay="t", alpha=fade)
    if spec.get("source") and first_at is not None and reached(t, first_at):
        source_tag(pen, ctx, spec["source"])


tally = Primitive("tally", TALLY, None, _tally_draw, True)

PRIMITIVES = {"big_number": big_number, "ratio_compare": ratio_compare,
              "bar_compare": bar_compare, "tally": tally}
