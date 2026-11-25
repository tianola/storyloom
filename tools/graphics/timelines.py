"""A dated timeline: an axis, events that land on it, and a now-marker that moves along it."""
from __future__ import annotations

import math

from .common import Pen, Primitive, line_height, plate, reached, run_width, wrap
from .spec import BUILD, NUM, STR, build_window, obj

OVERLAY = set()

TIMELINE = obj({
    "start": NUM,
    "end": NUM,
    "step": NUM,
    "events": {"type": "array", "maxItems": 8, "items": {
        "type": "object", "additionalProperties": False, "required": ["date", "label"],
        "properties": {"date": NUM, "label": STR, "build": BUILD, "color": STR}}},
    "now": {"type": "object", "additionalProperties": False, "required": ["from", "to", "build"],
            "properties": {"from": NUM, "to": NUM, "build": BUILD, "label": STR}},
}, required=["start", "end"])


def _check(spec, ctx):
    if spec["end"] <= spec["start"]:
        raise ValueError("timeline: end must be after start")


def _x(spec, ctx, date):
    inner0, inner1 = ctx.box[0] + ctx.W * 0.05, ctx.box[2] - ctx.W * 0.05
    return inner0 + (date - spec["start"]) / (spec["end"] - spec["start"]) * (inner1 - inner0)


def _tick_step(spec, ctx, font):
    if spec.get("step"):
        return spec["step"]
    span = spec["end"] - spec["start"]
    need = run_width(font, "0000") * 1.8
    width = _x(spec, ctx, spec["end"]) - _x(spec, ctx, spec["start"])
    for step in (1, 2, 5, 10, 20, 25, 50, 100, 200, 500):
        if width / (span / step) >= need:
            return step
    return span


def _draw(img, spec, t, ctx):
    pen = Pen(img)
    lab = ctx.font("label")
    ink = ctx.col("ink")
    y = ctx.H * 0.56
    x0, x1 = _x(spec, ctx, spec["start"]), _x(spec, ctx, spec["end"])
    pen.line([(x0, y), (x1, y)], ink, max(3, ctx.stroke * 1.5))
    step = _tick_step(spec, ctx, lab)
    d = math.ceil(spec["start"] / step) * step
    while d <= spec["end"] + 1e-9:
        x = _x(spec, ctx, d)
        pen.line([(x, y - ctx.H * 0.012), (x, y + ctx.H * 0.012)], ink, ctx.stroke)
        pen.text(x, y + ctx.H * 0.025, f"{d:g}", lab, ink, ax="m", ay="t", alpha=0.8)
        d += step
    # events alternate above and below so neighbouring labels never share a row
    for i, ev in enumerate(spec.get("events", [])):
        at, dur = build_window(ev.get("build"), (0.0, 0.0))
        if not reached(t, at):
            continue
        x = _x(spec, ctx, ev["date"])
        colour = ctx.col(ev.get("color", "accent"))
        above = i % 2 == 0
        width = min(ctx.W * 0.26, ctx.bw * 0.3)
        lines = wrap(lab, ev["label"], width)
        h = line_height(lab) * len(lines) + ctx.H * 0.02
        w = max(run_width(lab, ln) for ln in lines) + ctx.W * 0.02
        bx = min(max(x - w / 2, ctx.box[0]), ctx.box[2] - w)
        by = y - ctx.H * 0.09 - h if above else y + ctx.H * 0.12
        pen.line([(x, y), (x, by + h if above else by)], colour, ctx.stroke * 1.5)
        plate(pen, ctx, (bx, by, bx + w, by + h), ctx.col("paper"), outline=colour, width=ctx.stroke)
        for j, ln in enumerate(lines):
            pen.text(bx + w / 2, by + ctx.H * 0.01 + j * line_height(lab), ln, lab, ink, ax="m")
        r = ctx.H * 0.016
        pen.ellipse((x - r, y - r, x + r, y + r), fill=colour)
    now = spec.get("now")
    if now:
        at, dur = build_window(now["build"])
        p = 0.0 if dur <= 0 else min(1.0, max(0.0, (t - at) / dur))
        p = p * p * (3 - 2 * p)
        if reached(t, at):
            d = now["from"] + (now["to"] - now["from"]) * p
            x = _x(spec, ctx, d)
            colour = ctx.col("danger")
            pen.line([(x, y - ctx.H * 0.16), (x, y + ctx.H * 0.02)], colour, ctx.stroke * 2)
            s = ctx.H * 0.03
            pen.polygon([(x, y), (x - s, y - s * 1.6), (x + s, y - s * 1.6)], colour)


timeline = Primitive("timeline", TIMELINE, lambda s, c: c.solid("paper"), _draw, False, check=_check)
PRIMITIVES = {"timeline": timeline}
