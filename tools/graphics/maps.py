"""map_plan: rooms as rectangles, routes as polylines that draw themselves, always tagged SCHEMATIC.

The tag is not optional. A drawn plan of a real ward reads as measurement; a viewer who is not told
it is a sketch will take every proportion in it as fact. So the spec must say `schematic: true`,
and the tag is painted whatever else the spec holds.
"""
from __future__ import annotations

import math

from .common import (Pen, Primitive, arrowhead, line_height, plate, polyline_upto, prog, reached,
                     run_width, wrap)
from .spec import BOOL, BUILD, NUM, POINT, RECT, STR, build_window, obj

OVERLAY = set()

MAP_PLAN = obj({
    "schematic": BOOL,
    "rooms": {"type": "array", "maxItems": 200, "items": {
        "type": "object", "additionalProperties": False, "required": ["rect"],
        "properties": {"rect": RECT, "label": STR, "fill": STR, "minor": BOOL}}},
    "routes": {"type": "array", "maxItems": 8, "items": {
        "type": "object", "additionalProperties": False, "required": ["points", "build"],
        "properties": {"points": {"type": "array", "minItems": 2, "items": POINT},
                       "build": BUILD, "color": STR, "label": STR, "dashed": BOOL}}},
}, required=["schematic"])


def _check(spec, ctx):
    if spec.get("schematic") is not True:
        raise ValueError("map_plan: `schematic` must be true. A plan is a sketch, and it is always "
                         "tagged as one; refusing to draw it as if it were a measurement")


def _area(ctx, spec):
    """Where the plan itself goes: the safe box minus the legend strip along the bottom."""
    legend = ctx.H * 0.13
    return (ctx.box[0], ctx.box[1], ctx.box[2], ctx.box[3] - legend)


def _pt(area, p):
    return (area[0] + p[0] * (area[2] - area[0]), area[1] + p[1] * (area[3] - area[1]))


def _static(spec, ctx):
    img = ctx.solid("paper")
    pen = Pen(img)
    area = _area(ctx, spec)
    ink = ctx.col("ink")
    lab = ctx.font("label")
    soft = tuple(round(ink[i] * 0.12 + ctx.col("paper")[i] * 0.88) for i in range(3))
    for room in spec.get("rooms", []):
        x0, y0 = _pt(area, room["rect"][:2])
        x1, y1 = _pt(area, room["rect"][2:])
        fill = ctx.col(room["fill"]) if room.get("fill") else (ctx.col("paper") if room.get("minor") else soft)
        width = max(1, ctx.stroke // 2) if room.get("minor") else ctx.stroke
        pen.rect((x0, y0, x1, y1), fill=fill, outline=ink, width=width)
        if room.get("label"):
            font = ctx.fit("label", room["label"], (x1 - x0) * 0.9)
            lines = wrap(font, room["label"], (x1 - x0) * 0.92)
            ty = (y0 + y1) / 2 - line_height(font) * len(lines) / 2
            for ln in lines:
                pen.text((x0 + x1) / 2, ty, ln, font, ink, ax="m")
                ty += line_height(font)
    # the SCHEMATIC tag: always, bottom-right, in the label face on an ink plate
    tag = ctx.font("label")
    text = "SCHEMATIC"
    pad = round(tag.size * 0.3)
    w, h = run_width(tag, text, tracking=3) + 2 * pad, line_height(tag) + pad
    box = (ctx.box[2] - w, ctx.box[3] - h, ctx.box[2], ctx.box[3])
    plate(pen, ctx, box, ink)
    pen.text(ctx.box[2] - pad, ctx.box[3] - h / 2, text, tag, ctx.col("paper"), ax="r", ay="m", tracking=3)
    # legend for labelled routes, bottom-left
    x = ctx.box[0] + max(6, ctx.stroke * 2)
    ly = ctx.box[3] - h / 2
    for route in spec.get("routes", []):
        if not route.get("label"):
            continue
        colour = ctx.col(route.get("color", "danger"))
        pen.line([(x, ly), (x + ctx.W * 0.04, ly)], colour, max(6, ctx.stroke * 2))
        x += ctx.W * 0.05
        pen.text(x, ly, route["label"], lab, ink, ax="l", ay="m")
        x += run_width(lab, route["label"]) + ctx.W * 0.035
    return img


def _draw(img, spec, t, ctx):
    pen = Pen(img)
    area = _area(ctx, spec)
    for route in spec.get("routes", []):
        at, dur = build_window(route["build"])
        if not reached(t, at):
            continue
        colour = ctx.col(route.get("color", "danger"))
        pts = [_pt(area, p) for p in route["points"]]
        frac = 1.0 if dur <= 0 else prog(t, at, dur)
        frac = max(frac, 0.02)
        drawn, back = polyline_upto(pts, frac)
        width = max(6, round(ctx.H * 0.011))
        if route.get("dashed"):
            _dashed(pen, drawn, colour, width, ctx.H * 0.03)
        else:
            pen.line(drawn, colour, width)
        if back is not None and len(drawn) >= 2:
            arrowhead(pen, drawn[-1], back if back != drawn[-1] else drawn[-2], width * 3.2, colour)


def _dashed(pen, pts, colour, width, dash):
    for a, b in zip(pts, pts[1:]):
        length = math.dist(a, b)
        n = max(1, int(length // (dash * 2)))
        for i in range(n + 1):
            s, e = i * dash * 2, min(length, i * dash * 2 + dash)
            if s >= length:
                break
            f0, f1 = s / length, e / length
            pen.line([(a[0] + (b[0] - a[0]) * f0, a[1] + (b[1] - a[1]) * f0),
                      (a[0] + (b[0] - a[0]) * f1, a[1] + (b[1] - a[1]) * f1)], colour, width)


map_plan = Primitive("map_plan", MAP_PLAN, _static, _draw, False, check=_check)
PRIMITIVES = {"map_plan": map_plan}
