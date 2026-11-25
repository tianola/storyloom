"""Overlay labels: plates, callouts, lower thirds, underlines, circles, date stamps, day labels.

Everything here is transparent and sits inside the safe margin. Text goes on a plate whose colour
is chosen for contrast (`Ctx.text_on`), because the footage under an overlay is not ours to control.
"""
from __future__ import annotations

import math

from .common import (Pen, Primitive, clamp, ease, line_height, mix, plate, prog, reached,
                     run_width, wrap)
from .spec import BUILD, NUM, POINT, RECT, STR, build_window, obj

OVERLAY = {"label", "callout", "lower_third", "underline", "circle", "date_stamp", "day_labels"}

STAMP_TEXT, STAMP_PLATE = "danger", "paper"
SETTLE_PAD = 0.014  # fraction of frame height a settling element travels, reserved inside the margin


def _frac_point(ctx, p):
    return ctx.box[0] + p[0] * ctx.bw, ctx.box[1] + p[1] * ctx.bh


def _text_plate(pen, ctx, text, cx, cy, fill, alpha, maxw=None, dy=0.0, kind="label"):
    """A plate centred on (cx, cy) holding `text`; clamped into the safe box. Returns its box."""
    font = ctx.font(kind)
    pad = round(font.size * 0.4)
    room = (maxw or ctx.bw * 0.8) - 2 * pad
    lines = wrap(font, text, room)
    w = max(run_width(font, ln) for ln in lines) + 2 * pad
    h = line_height(font) * len(lines) + pad
    trav = ctx.H * SETTLE_PAD
    x, y = ctx.clamp_box(cx - w / 2, cy - h / 2, w, h, pad=trav)
    y += dy
    plate(pen, ctx, (x, y, x + w, y + h), ctx.col(fill), alpha=alpha * 0.95)
    colour = ctx.text_on(fill)
    for i, ln in enumerate(lines):
        pen.text(x + w / 2, y + pad / 2 + i * line_height(font), ln, font, colour, ax="m", alpha=alpha)
    return (x, y, x + w, y + h)


# --- label -------------------------------------------------------------------------------------------
LABEL = obj({"text": STR, "pos": POINT, "color": STR, "build": BUILD}, required=["text"])


def _label_draw(img, spec, t, ctx):
    alpha, e = ctx.appear(t, spec.get("build", [0.0, 0.3]), role="settle")
    if alpha <= 0:
        return
    cx, cy = _frac_point(ctx, spec.get("pos", [0.5, 0.88]))
    _text_plate(Pen(img), ctx, spec["text"], cx, cy, spec.get("color", "paper"), alpha,
                dy=(1 - e) * ctx.H * SETTLE_PAD)


label = Primitive("label", LABEL, None, _label_draw, True)


# --- callout -----------------------------------------------------------------------------------------
CALLOUT = obj({"text": STR, "target": POINT, "pos": POINT, "color": STR, "build": BUILD},
              required=["text", "target"])


def _callout_draw(img, spec, t, ctx):
    pen = Pen(img)
    build = spec.get("build", [0.0, 0.5])
    alpha, e = ctx.appear(t, build, floor=0.5)
    if alpha <= 0:
        return
    colour = ctx.col(spec.get("color", "accent"))
    r = ctx.H * 0.014
    tx, ty = _frac_point(ctx, spec["target"])
    tx = clamp(tx, ctx.box[0] + r * 2, ctx.box[2] - r * 2)
    ty = clamp(ty, ctx.box[1] + r * 2, ctx.box[3] - r * 2)
    cx, cy = _frac_point(ctx, spec.get("pos", [0.5, 0.15]))
    box = _text_plate(pen, ctx, spec["text"], cx, cy, "paper", alpha)
    # leader from the plate's nearest edge point to the target, drawn progressively
    sx = clamp(tx, box[0], box[2])
    sy = clamp(ty, box[1], box[3])
    if box[0] < tx < box[2] and box[1] < ty < box[3]:
        sy = box[3]
    ex, ey = sx + (tx - sx) * e, sy + (ty - sy) * e
    w = max(3, round(ctx.stroke * 1.4))
    pen.line([(sx, sy), (ex, ey)], colour, w)
    if e >= 0.98:
        pen.ellipse((tx - r, ty - r, tx + r, ty + r), outline=colour, width=w)


callout = Primitive("callout", CALLOUT, None, _callout_draw, True)


# --- lower_third -------------------------------------------------------------------------------------
LOWER_THIRD = obj({"title": STR, "subtitle": STR, "build": BUILD}, required=["title"])


def _lower_draw(img, spec, t, ctx):
    alpha, e = ctx.appear(t, spec.get("build", [0.0, 0.4]), role="settle")
    if alpha <= 0:
        return
    pen = Pen(img)
    font = ctx.font("label")
    pad = round(font.size * 0.45)
    bar = max(6, round(ctx.W * 0.006))
    lines = [(spec["title"], 1.0)] + ([(spec["subtitle"], 0.75)] if spec.get("subtitle") else [])
    w = max(run_width(font, s) for s, _ in lines) + 2 * pad + bar
    w = min(w, ctx.bw)
    h = line_height(font) * len(lines) + pad
    x = ctx.box[0]
    y = ctx.box[3] - h - ctx.H * 0.04
    slide = min((1 - e) * ctx.W * 0.03, ctx.box[2] - (x + w))
    x += max(0.0, slide)
    plate(pen, ctx, (x, y, x + w, y + h), ctx.col("paper"), alpha=alpha * 0.95)
    pen.rect((x, y + ctx.radius * 0.5, x + bar, y + h - ctx.radius * 0.5), fill=ctx.col("accent"), alpha=alpha)
    ink = ctx.col("ink")
    for i, (s, a) in enumerate(lines):
        pen.text(x + bar + pad, y + pad / 2 + i * line_height(font), s, font, ink, alpha=alpha * a)


lower_third = Primitive("lower_third", LOWER_THIRD, None, _lower_draw, True)


# --- underline ---------------------------------------------------------------------------------------
UNDERLINE = obj({"box": RECT, "color": STR, "build": BUILD}, required=["box"])


def _underline_draw(img, spec, t, ctx):
    build = spec.get("build", [0.0, 0.4])
    at, dur = build_window(build)
    if not reached(t, at):
        return
    p = max(0.03, prog(t, at, dur))
    p = 1 - (1 - p) ** 3
    x0, y0 = _frac_point(ctx, spec["box"][:2])
    x1, y1 = _frac_point(ctx, spec["box"][2:])
    w = max(5, round(ctx.H * 0.009))
    y = min(y1 + ctx.H * 0.012, ctx.box[3] - w)
    Pen(img).line([(x0 + w, y), (x0 + w + (x1 - x0 - 2 * w) * p, y)], ctx.col(spec.get("color", "accent")), w)


underline = Primitive("underline", UNDERLINE, None, _underline_draw, True)


# --- circle ------------------------------------------------------------------------------------------
CIRCLE = obj({"center": POINT, "rx": NUM, "ry": NUM, "color": STR, "build": BUILD}, required=["center"])


def _circle_draw(img, spec, t, ctx):
    build = spec.get("build", [0.0, 0.6])
    at, dur = build_window(build)
    if not reached(t, at):
        return
    p = max(0.03, prog(t, at, dur))
    p = 1 - (1 - p) ** 3
    w = max(5, round(ctx.H * 0.009))
    cx, cy = _frac_point(ctx, spec["center"])
    rx = spec.get("rx", 0.12) * ctx.bw
    ry = spec.get("ry", 0.2) * ctx.bh
    rx = min(rx, (ctx.bw / 2) - w)
    ry = min(ry, (ctx.bh / 2) - w)
    cx = clamp(cx, ctx.box[0] + rx + w, ctx.box[2] - rx - w)
    cy = clamp(cy, ctx.box[1] + ry + w, ctx.box[3] - ry - w)
    sweep = math.radians(380) * p
    n = max(2, int(sweep / math.radians(4)))
    pts = [(cx + rx * math.cos(-math.pi / 2 + sweep * i / n),
            cy + ry * math.sin(-math.pi / 2 + sweep * i / n)) for i in range(n + 1)]
    Pen(img).line(pts, ctx.col(spec.get("color", "danger")), w)


circle = Primitive("circle", CIRCLE, None, _circle_draw, True)


# --- date_stamp --------------------------------------------------------------------------------------
DATE_STAMP = obj({"text": STR, "at": NUM}, required=["text"])
STAMP_SETTLE = 0.25


def _stamp_draw(img, spec, t, ctx):
    at = spec.get("at", 0.2)
    if not reached(t, at):
        return
    pen = Pen(img)
    font = ctx.font("label")
    tracking = round(font.size * 0.06)
    text = spec["text"].upper()
    pad = round(font.size * 0.45)
    w = run_width(font, text, tracking) + 2 * pad
    h = line_height(font) + pad
    trav = ctx.H * SETTLE_PAD
    e = ease(ctx.tokens, "settle", prog(t, at, STAMP_SETTLE))
    x, y = ctx.box[0] + 0, ctx.box[1] + trav + (e - 1) * trav
    border = max(3, round(ctx.H * 0.005))
    plate(pen, ctx, (x, y, x + w, y + h), ctx.col(STAMP_PLATE))
    pen.rrect((x + border * 1.5, y + border * 1.5, x + w - border * 1.5, y + h - border * 1.5),
              max(1, ctx.radius - 2), outline=ctx.col(STAMP_TEXT), width=border)
    pen.text(x + w / 2, y + h / 2, text, font, ctx.col(STAMP_TEXT), ax="m", ay="m", tracking=tracking)


date_stamp = Primitive("date_stamp", DATE_STAMP, None, _stamp_draw, True)


# --- day_labels --------------------------------------------------------------------------------------
DAY_LABELS = obj({
    "cycle": {"type": "array", "minItems": 1, "maxItems": 14, "items": {
        "type": "array", "minItems": 2, "maxItems": 2,
        "items": {"type": "string"}}},
    "step": NUM,
    "clinics": {"type": "object", "additionalProperties": False,
                "properties": {"first": STR, "second": STR}},
}, required=["cycle", "step"])
SLOT_X = {"first": 0.3, "second": 0.7}


def _check_days(spec, ctx):
    if spec["step"] <= 0:
        raise ValueError("day_labels: step must be above 0 seconds")
    for day, clinic in spec["cycle"]:
        if clinic not in SLOT_X:
            raise ValueError(f"day_labels: clinic must be 'first' or 'second', got {clinic!r}")


def _days_draw(img, spec, t, ctx):
    pen = Pen(img)
    step = spec["step"]
    cycle = spec["cycle"]
    names = {"first": "First Clinic", "second": "Second Clinic", **spec.get("clinics", {})}
    idx = min(int(t / step + 1e-9), len(cycle) - 1)
    lab, num = ctx.font("label"), ctx.font("number")
    pad = round(ctx.H * 0.022)
    w = ctx.W * 0.36
    h = pad * 2 + line_height(lab) + line_height(num)
    trav = ctx.H * SETTLE_PAD
    y0 = ctx.box[1] + trav * 2
    last = {"first": None, "second": None}
    for k in range(idx + 1):
        last[cycle[k][1]] = (cycle[k][0], k)
    active = cycle[idx][1]
    for slot, fx in SLOT_X.items():
        is_active = slot == active
        a = 1.0 if is_active else 0.4
        x = ctx.W * fx - w / 2
        shown = last[slot]
        dy = 0.0
        if is_active and shown:
            e = ease(ctx.tokens, "settle", prog(t, shown[1] * step, 0.25))
            dy = (e - 1) * trav
        plate(pen, ctx, (x, y0 + dy, x + w, y0 + dy + h), ctx.col("paper"), alpha=0.95 * a)
        font = ctx.fit("label", names[slot], w - 2 * pad)
        pen.text(x + w / 2, y0 + dy + pad, names[slot], font, ctx.col("ink"), ax="m", alpha=a)
        if shown:
            pen.text(x + w / 2, y0 + dy + pad + line_height(lab), shown[0].upper(), num,
                     ctx.col("danger" if is_active else "ink"), ax="m", alpha=a)


day_labels = Primitive("day_labels", DAY_LABELS, None, _days_draw, True, check=_check_days)

PRIMITIVES = {p.name: p for p in (label, callout, lower_third, underline, circle, date_stamp, day_labels)}
