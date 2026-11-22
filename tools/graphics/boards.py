"""Investigation boards: paper cards pinned to a dark board, joined by string, crossed out when wrong.

`board` is the full-frame board; `board_card` is one card as an overlay (a single term pinned up
over footage). `export_card_textures` writes each board card as a PNG for a 3D board set, drawn by
the same routine so the 2D and 3D boards cannot drift apart.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from .common import Ctx, Pen, Primitive, ease, line_height, prog, reached, wrap
from .spec import BOOL, BUILD, NUM, STR, build_window, obj
from .tokens import load_tokens

OVERLAY = {"board_card"}

_CARD = {"type": "object", "additionalProperties": False, "required": ["id", "title", "x", "y"],
         "properties": {"id": STR, "title": STR, "x": NUM, "y": NUM, "pin": BOOL, "color": STR,
                        "build": BUILD, "remove": BUILD, "cross_out": BUILD}}
BOARD = obj({
    "cards": {"type": "array", "minItems": 1, "maxItems": 12, "items": _CARD},
    "strings": {"type": "array", "maxItems": 20, "items": {
        "type": "object", "additionalProperties": False, "required": ["from", "to"],
        "properties": {"from": STR, "to": STR, "build": BUILD, "color": STR}}},
}, required=["cards"])

CORNERS = ["top-left", "top-right", "bottom-left", "bottom-right"]
BOARD_CARD = obj({
    "title": STR,
    "pin": BOOL,
    "corner": {"type": "string", "enum": CORNERS},
    "place": STR,
    "build": BUILD,
}, required=["title"])


# --- the card itself -------------------------------------------------------------------------------
def card_geometry(ctx, title, width_frac=0.22):
    """(w, h, font, lines) for a card holding `title` at label size."""
    font = ctx.font("label")
    w = ctx.W * width_frac
    lines = wrap(font, title, w - ctx.W * 0.03)
    h = line_height(font) * len(lines) + ctx.H * 0.07
    return w, h, font, lines


def draw_card(pen, ctx, x, y, w, h, font, lines, alpha=1.0, fill="paper"):
    """Paper card with a soft drop shadow and its title in ink."""
    off = ctx.H * 0.006
    pen.rrect((x + off, y + off * 1.5, x + w + off, y + h + off * 1.5), ctx.radius,
              fill=(0, 0, 0), alpha=0.35 * alpha)
    pen.rrect((x, y, x + w, y + h), ctx.radius, fill=ctx.col(fill), alpha=alpha)
    ty = y + (h - line_height(font) * len(lines)) / 2
    ink = ctx.col("ink")
    for ln in lines:
        pen.text(x + w / 2, ty, ln, font, ink, ax="m", alpha=alpha)
        ty += line_height(font)


def draw_pin(pen, ctx, cx, cy, alpha=1.0):
    r = ctx.H * 0.016
    pen.ellipse((cx - r, cy - r + r * 0.25, cx + r, cy + r + r * 0.25), fill=(0, 0, 0), alpha=0.3 * alpha)
    pen.ellipse((cx - r, cy - r, cx + r, cy + r), fill=ctx.col("danger"), alpha=alpha)
    pen.ellipse((cx - r * 0.45, cy - r * 0.55, cx + r * 0.05, cy - r * 0.1), fill=(255, 255, 255), alpha=0.55 * alpha)


# --- board -----------------------------------------------------------------------------------------
def _board_layout(spec, ctx):
    """id -> (x, y, w, h, font, lines); x, y are the card's centre as fractions of the safe box."""
    out = {}
    for card in spec["cards"]:
        w, h, font, lines = card_geometry(ctx, card["title"])
        cx = ctx.box[0] + card["x"] * ctx.bw
        cy = ctx.box[1] + card["y"] * ctx.bh
        x, y = ctx.clamp_box(cx - w / 2, cy - h / 2, w, h)
        out[card["id"]] = (x, y, w, h, font, lines)
    return out


def _check_board(spec, ctx):
    ids = [c["id"] for c in spec["cards"]]
    if len(set(ids)) != len(ids):
        raise ValueError("board: card ids must be unique")
    for s in spec.get("strings", []):
        for end in (s["from"], s["to"]):
            if end not in ids:
                raise ValueError(f"board: string refers to unknown card {end!r}")


def _board_draw(img, spec, t, ctx):
    pen = Pen(img)
    geo = _board_layout(spec, ctx)

    def visibility(card):
        a, _ = ctx.appear(t, card.get("build"), role="settle", floor=0.5)
        rm = card.get("remove")
        if rm is not None:
            rat, rdur = build_window(rm)
            if reached(t, rat):
                a *= 1.0 - prog(t, rat, max(rdur, 1e-6))
        return a

    vis = {c["id"]: visibility(c) for c in spec["cards"]}
    for s in spec.get("strings", []):
        a, e = ctx.appear(t, s.get("build"), floor=0.0)
        if s.get("build") is not None and not reached(t, build_window(s["build"])[0]):
            continue
        va, vb = vis[s["from"]], vis[s["to"]]
        if min(va, vb) <= 0:
            continue
        pa = _pin_point(geo[s["from"]], ctx)
        pb = _pin_point(geo[s["to"]], ctx)
        end = (pa[0] + (pb[0] - pa[0]) * max(e, 0.02), pa[1] + (pb[1] - pa[1]) * max(e, 0.02))
        pen.line([pa, end], ctx.col(s.get("color", "danger")), max(3, ctx.stroke), alpha=min(va, vb))
    for card in spec["cards"]:
        a = vis[card["id"]]
        if a <= 0:
            continue
        x, y, w, h, font, lines = geo[card["id"]]
        drop = (1 - a) * ctx.H * 0.01 if card.get("build") else 0.0
        draw_card(pen, ctx, x, y + drop, w, h, font, lines, alpha=a, fill=card.get("color", "paper"))
        if card.get("pin", True):
            px, py = _pin_point(geo[card["id"]], ctx)
            draw_pin(pen, ctx, px, py + drop, alpha=a)
        if card.get("cross_out") is not None:
            at, dur = build_window(card["cross_out"])
            if reached(t, at):
                p = max(0.02, prog(t, at, dur))
                m = ctx.W * 0.012
                red = ctx.col("danger")
                w1 = max(6, round(ctx.H * 0.012))
                a1, b1 = (x + m, y + m), (x + w - m, y + h - m)
                first = min(1.0, p * 2)
                pen.line([a1, (a1[0] + (b1[0] - a1[0]) * first, a1[1] + (b1[1] - a1[1]) * first)], red, w1, alpha=a)
                if p > 0.5:
                    a2, b2 = (x + w - m, y + m), (x + m, y + h - m)
                    second = (p - 0.5) * 2
                    pen.line([a2, (a2[0] + (b2[0] - a2[0]) * second, a2[1] + (b2[1] - a2[1]) * second)], red, w1, alpha=a)


def _pin_point(geo, ctx):
    """Pins sit at the top centre of a board card, just inside the paper."""
    x, y, w, h = geo[:4]
    return (x + w / 2, y + ctx.H * 0.016)


board = Primitive("board", BOARD, lambda s, c: c.solid("mat"), _board_draw, False, check=_check_board)


# --- board_card ------------------------------------------------------------------------------------
def _card_box(spec, ctx):
    w, h, font, lines = card_geometry(ctx, spec["title"], 0.26)
    travel = ctx.H * 0.05
    # reserve the pin's travel inside the safe box so the pin never leaves the margins
    x, y = ctx.place(w, h, spec.get("place", "center"))
    x, y = ctx.clamp_box(x, y, w, h)
    ix0, iy0, ix1, iy1 = ctx.box
    x = min(max(x, ix0 + travel), ix1 - w - travel)
    y = min(max(y, iy0 + travel), iy1 - h - travel)
    return x, y, w, h, font, lines, travel


def _pin_corner(x, y, w, h, corner, inset):
    px = x + inset if corner.endswith("left") else x + w - inset
    py = y + inset if corner.startswith("top") else y + h - inset
    return px, py


def _board_card_draw(img, spec, t, ctx):
    pen = Pen(img)
    build = spec.get("build") or [0.0, 0.4]
    alpha, e = ctx.appear(t, build, role="settle", floor=0.6)
    if alpha <= 0:
        return
    x, y, w, h, font, lines, travel = _card_box(spec, ctx)
    draw_card(pen, ctx, x, y, w, h, font, lines, alpha=alpha)
    if spec.get("pin", True):
        corner = spec.get("corner", "top-right")
        inset = ctx.H * 0.03
        px, py = _pin_corner(x, y, w, h, corner, inset)
        # the pin slides in from outside the card's corner and settles with a small overshoot
        at, dur = build_window(build)
        k = ease(ctx.tokens, "settle", prog(t, at + dur * 0.5, max(dur, 1e-6) * 0.6))
        sx = travel * (-1 if corner.endswith("left") else 1)
        sy = travel * (-1 if corner.startswith("top") else 1)
        remaining = 1.0 - k
        draw_pin(pen, ctx, px + sx * remaining, py + sy * remaining, alpha=alpha)


def _check_card(spec, ctx):
    return None


board_card = Primitive("board_card", BOARD_CARD, None, _board_card_draw, True, check=_check_card)


# --- textures for a 3D board -------------------------------------------------------------------------
def export_card_textures(spec, out_dir, scale=2, canvas=(1920, 1080), tokens=None):
    """One PNG per card (transparent corners), at `scale` times the card's size on a 1080p board."""
    from .spec import validate
    validate(spec, BOARD, "board")
    tokens = tokens or load_tokens()
    ctx = Ctx((canvas[0] * scale, canvas[1] * scale), tokens, spec)
    _check_board(spec, ctx)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    pad = round(ctx.H * 0.012)
    for card in spec["cards"]:
        w, h, font, lines = card_geometry(ctx, card["title"])
        img = Image.new("RGBA", (round(w) + 2 * pad, round(h) + 2 * pad), (0, 0, 0, 0))
        pen = Pen(img, origin=(-pad, -pad))
        draw_card(pen, ctx, 0, 0, w, h, font, lines, fill=card.get("color", "paper"))
        path = out_dir / f"card_{card['id']}.png"
        img.save(path)
        paths.append(path)
    return paths


PRIMITIVES = {"board": board, "board_card": board_card}
