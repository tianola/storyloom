"""Archive graphics: the still on its mat, and the credit line.

`card_lines` lives here (it used to live in tools/archive_ingest.py, which now imports it) because
the same wrapping rule serves the burned-in credit card and the credit set on the mat.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from .common import Pen, Primitive, clamp, line_height, mix, reached, run_width
from .spec import NUM, RECT, STR, obj

OVERLAY = {"source_card"}


def card_lines(text, fits):
    """The credit broken into lines that each pass `fits`, keeping its own phrases together.

    A credit line is written to be read whole, so it is only broken where it already pauses —
    after " / " (the source and the host), then after ", " — and only then between words. Found on
    the Semmelweis pilot: every one-line credit ran off the right edge ("… / Wikimedia Comm"), so
    the attribution the card exists to carry was the part that went missing. A single word wider
    than the canvas is left on its own line rather than cut, since a cut word is no credit either.
    """
    words = str(text).split()
    # Phrases end after a "/" token or a word ending in ",".
    phrases, current = [], []
    for word in words:
        current.append(word)
        if word == "/" or word.endswith(","):
            phrases.append(current)
            current = []
    if current:
        phrases.append(current)

    lines, line = [], []
    for phrase in phrases:
        if fits(" ".join(line + phrase)):
            line += phrase
            continue
        if line:
            lines.append(" ".join(line))
            line = []
        for word in phrase:  # only a phrase too wide on its own is broken between words
            if line and not fits(" ".join(line + [word])):
                lines.append(" ".join(line))
                line = []
            line.append(word)
    if line:
        lines.append(" ".join(line))
    return lines


# --- archive_mat -----------------------------------------------------------------------------------
ARCHIVE_MAT = obj({
    "image": STR,
    "credit": STR,
    "highlight": RECT,
    "seconds": NUM,
    "push": NUM,
}, required=["image", "credit"])

PUSH = 0.06  # scale 1.00 -> 1.06 over the shot


def _check_mat(spec, ctx):
    h = spec.get("highlight")
    if h and not (0 <= h[0] < h[2] <= 1 and 0 <= h[1] < h[3] <= 1):
        raise ValueError("archive_mat: highlight must be [x0, y0, x1, y1] in 0..1 with x0<x1, y0<y1")


def _plan(spec, ctx):
    """Picture rectangle and credit lines; the credit strip is reserved so it can never overlap."""
    cache = ctx.cache
    if "plan" in cache:
        return cache["plan"]
    with Image.open(spec["image"]) as im:
        iw, ih = im.size
    font = ctx.font("caption")
    lh = line_height(font)
    gap = round(ctx.H * 0.014)
    b = max(2, ctx.stroke)  # the border sits outside the picture, so it is reserved inside the margin
    maxw = ctx.bw
    for _ in range(3):
        lines = card_lines(spec["credit"], lambda s: run_width(font, s) <= maxw)
        strip = lh * len(lines)
        avail_h = ctx.bh - strip - gap - 2 * b
        scale = min((ctx.bw - 2 * b) / iw, avail_h / ih)
        pw, ph = max(1, round(iw * scale)), max(1, round(ih * scale))
        x0 = ctx.box[0] + (ctx.bw - pw) // 2
        new_max = ctx.box[2] - x0
        if new_max >= maxw - 1:
            break
        maxw = new_max
    group = ph + gap + strip
    y0 = ctx.box[1] + b + (ctx.bh - 2 * b - group) // 2
    plan = {"rect": (x0, y0, x0 + pw - 1, y0 + ph - 1), "lines": lines, "font": font,
            "credit_xy": (x0, y0 + ph + gap), "size": (pw, ph)}
    cache["plan"] = plan
    return plan


def picture_rect(spec, canvas=(1920, 1080), tokens=None):
    """(x0, y0, x1, y1) of the picture on the mat, inclusive pixels; the credit is outside it."""
    from .common import Ctx
    from .tokens import load_tokens
    ctx = Ctx(canvas, tokens or load_tokens(), spec)
    return _plan(spec, ctx)["rect"]


def _static(spec, ctx):
    img = ctx.solid("mat")
    pen = Pen(img)
    plan = _plan(spec, ctx)
    x0, y0, x1, y1 = plan["rect"]
    paper = ctx.col("paper")
    b = max(2, ctx.stroke)
    # thin paper-tone border, outside the picture
    pen.rect((x0 - b, y0 - b, x1 + b, y1 + b), outline=mix(paper, ctx.col("mat"), 0.45), width=b)
    cx, cy = plan["credit_xy"]
    for i, line in enumerate(plan["lines"]):
        pen.text(cx, cy + i * line_height(plan["font"]), line, plan["font"], paper)
    # source image, tinted slightly toward paper and kept at no more than twice the picture size
    pw, ph = plan["size"]
    with Image.open(spec["image"]) as im:
        src = im.convert("RGB")
    cap = (pw * 2, ph * 2)
    if src.width > cap[0] or src.height > cap[1]:
        src.thumbnail(cap, Image.LANCZOS)
    ctx.cache["src"] = Image.blend(src, Image.new("RGB", src.size, paper), 0.07)
    return img


def _draw_mat(img, spec, t, ctx):
    plan = _plan(spec, ctx)
    src = ctx.cache["src"]
    seconds = max(float(spec.get("seconds", 10.0)), 1e-6)
    p = clamp(t / seconds)
    p = p * p * (3 - 2 * p)
    s = 1.0 + spec.get("push", PUSH) * p
    ww, wh = 1.0 / s, 1.0 / s
    hl = spec.get("highlight")
    tx, ty = ((hl[0] + hl[2]) / 2, (hl[1] + hl[3]) / 2) if hl else (0.5, 0.5)
    cx = clamp(0.5 + (tx - 0.5) * p, ww / 2, 1 - ww / 2)
    cy = clamp(0.5 + (ty - 0.5) * p, wh / 2, 1 - wh / 2)
    box = ((cx - ww / 2) * src.width, (cy - wh / 2) * src.height,
           (cx + ww / 2) * src.width, (cy + wh / 2) * src.height)
    frame = src.resize(plan["size"], Image.BICUBIC, box=box)
    x0, y0 = plan["rect"][:2]
    img.paste(frame, (x0, y0))


archive_mat = Primitive("archive_mat", ARCHIVE_MAT, _static, _draw_mat, False, check=_check_mat,
                        wants_seconds=True)


# --- source_card -----------------------------------------------------------------------------------
SOURCE_CARD = obj({"credit": STR, "at": NUM}, required=["credit"])


def _draw_card(img, spec, t, ctx):
    if not reached(t, spec.get("at", 0.0)):
        return
    pen = Pen(img)
    font = ctx.font("caption")
    stroke = max(1, round(font.size * 0.06))
    room = ctx.bw - 2 * stroke
    lines = card_lines(spec["credit"], lambda s: run_width(font, s) <= room)
    lh = line_height(font)
    y = ctx.box[3] - lh * len(lines) - stroke
    for i, line in enumerate(lines):
        pen.text(ctx.box[0] + stroke, y + i * lh, line, font, ctx.col("paper"),
                 stroke=stroke, stroke_fill=ctx.col("ink"))


source_card = Primitive("source_card", SOURCE_CARD, None, _draw_card, True)

PRIMITIVES = {"archive_mat": archive_mat, "source_card": source_card}
