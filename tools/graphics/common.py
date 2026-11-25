"""Shared drawing kit: colour maths, easing, a pen that composites properly, and the Primitive wrapper.

Three rules keep every primitive honest and cheap:

* Static layers (background, mat, cards that never change) are drawn ONCE per render call and
  copied into each frame. A primitive supplies `static(spec, ctx)` and `draw(img, spec, t, ctx)`;
  `Primitive` wires them into `frame_at` and the generator `render`.
* Text is composited from a coverage mask onto a layer that already carries the right colour, so
  anti-aliased edges never pick up a dark fringe on a transparent overlay.
* Sizes come from the tokens as fractions of frame height; `Ctx.font` refuses a label or number
  below the mobile floor instead of quietly rendering something nobody can read on a phone.
"""
from __future__ import annotations

import math
from contextlib import contextmanager

from PIL import Image, ImageChops, ImageDraw, ImageFont

from .spec import BUILD, TYPE_OVERRIDE, build_window, validate  # noqa: F401  (re-exported)
from .tokens import load_tokens

_FONTS = {}


# --- colour --------------------------------------------------------------------------------------
def hex_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def luminance(rgb):
    """WCAG relative luminance of an sRGB triple."""
    def lin(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    """WCAG contrast ratio between two sRGB triples (1..21)."""
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def mix(a, b, f):
    return tuple(round(a[i] + (b[i] - a[i]) * f) for i in range(3))


# --- time ----------------------------------------------------------------------------------------
def clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def prog(t, at, dur):
    """0..1 progress of a window; a zero-length window is a step at `at`."""
    if dur <= 0:
        return 1.0 if t >= at - 1e-9 else 0.0
    return clamp((t - at) / dur)


def reached(t, at):
    """True from `at` on, tolerant of float noise so frame i/fps == at counts as arrived."""
    return t >= at - 1e-9


EASES = {
    "cubic_in": lambda x: x ** 3,
    "cubic_out": lambda x: 1 - (1 - x) ** 3,
    # a gentle overshoot (about 4%): a stamp or pin that lands rather than slides
    "back_out": lambda x: 1 + 2.2 * (x - 1) ** 3 + 1.2 * (x - 1) ** 2,
    "linear": lambda x: x,
}


def ease(tokens, role, x):
    """Apply the motion curve a token role (ease_in / ease_out / settle) names."""
    return EASES[tokens["motion"][role]](clamp(x))


# --- fonts and text ------------------------------------------------------------------------------
_KIND_FACE = {"display": "display", "number": "display", "label": "bold", "caption": "bold"}


def load_font(path, size):
    key = (path, int(size))
    if key not in _FONTS:
        _FONTS[key] = ImageFont.truetype(path, int(size))
    return _FONTS[key]


def run_width(font, s, tracking=0):
    if not tracking:
        return font.getlength(s)
    return sum(font.getlength(ch) + tracking for ch in s) - tracking if s else 0


def wrap(font, s, maxw, tracking=0):
    """Greedy word wrap; a single over-wide word stays whole on its own line."""
    lines, line = [], ""
    for word in str(s).split():
        trial = f"{line} {word}".strip()
        if line and run_width(font, trial, tracking) > maxw:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    return lines or [""]


# --- the canvas context -----------------------------------------------------------------------------
class Ctx:
    """Everything a primitive needs to size and place things on one canvas."""

    def __init__(self, canvas, tokens, spec=None):
        self.W, self.H = int(canvas[0]), int(canvas[1])
        self.canvas = (self.W, self.H)
        self.tokens = tokens
        self.mx = round(tokens["safe_margin_fraction"] * self.W)
        self.my = round(tokens["safe_margin_fraction"] * self.H)
        self.box = (self.mx, self.my, self.W - self.mx - 1, self.H - self.my - 1)
        self.cache = {}
        self.sizes = dict(tokens["type"])
        override = (spec or {}).get("type") if isinstance(spec, dict) else None
        if override:
            self.sizes.update(override)
        for kind, floor in tokens["mobile_floor"].items():
            if self.sizes[kind] + 1e-9 < floor:
                raise ValueError(f"type.{kind} {self.sizes[kind]} is below the mobile floor {floor}")
        self.stroke = max(1, round(tokens["stroke_fraction"] * self.H))
        self.radius = round(tokens["corner_radius_fraction"] * self.H)
        self.stagger = float(tokens["build_stagger_seconds"])

    # geometry
    @property
    def bw(self):
        return self.box[2] - self.box[0]

    @property
    def bh(self):
        return self.box[3] - self.box[1]

    def px(self, frac_h):
        return frac_h * self.H

    def fx(self, frac_w):
        return frac_w * self.W

    def place(self, w, h, where="center"):
        """Top-left of a w x h box placed at a named spot inside the safe box."""
        x0, y0, x1, y1 = self.box
        xs = {"left": x0, "center": (x0 + x1 - w) / 2, "right": x1 - w}
        ys = {"top": y0, "center": (y0 + y1 - h) / 2, "bottom": y1 - h}
        parts = where.split("-")
        v = next((p for p in parts if p in ("top", "bottom")), "center")
        hz = next((p for p in parts if p in ("left", "right")), "center")
        return xs[hz], ys[v]

    def clamp_box(self, x, y, w, h, pad=0):
        """Move a w x h box (top-left x, y) so it, plus `pad` all round, sits inside the safe box."""
        x0, y0, x1, y1 = self.box
        return (min(max(x, x0 + pad), x1 - w - pad), min(max(y, y0 + pad), y1 - h - pad))

    # colour
    def col(self, name):
        if isinstance(name, (tuple, list)):
            return tuple(name[:3])
        if name.startswith("#"):
            return hex_rgb(name)
        return hex_rgb(self.tokens["palette"][name])

    def text_on(self, bg):
        """Ink or paper, whichever reads better on `bg` (a palette name or rgb)."""
        rgb = self.col(bg)
        ink, paper = self.col("ink"), self.col("paper")
        return ink if contrast(ink, rgb) >= contrast(paper, rgb) else paper

    # type
    def size_px(self, kind):
        return max(1, round(self.sizes[kind] * self.H))

    def font(self, kind, px=None):
        floor = self.tokens["mobile_floor"].get(kind)
        size = self.size_px(kind) if px is None else round(px)
        if floor is not None and size < round(floor * self.H) - 0:
            raise ValueError(f"{kind} text at {size}px is below the mobile floor "
                             f"{round(floor * self.H)}px for a {self.H}px frame")
        return load_font(self.tokens["fonts_abs"][_KIND_FACE[kind]], size)

    def fit(self, kind, s, maxw, tracking=0):
        """The `kind` font, shrunk (never below its floor) until `s` fits in maxw on one line."""
        floor = self.tokens["mobile_floor"].get(kind)
        size = self.size_px(kind)
        lo = round(floor * self.H) if floor is not None else max(8, size // 2)
        while size > lo and run_width(load_font(self.tokens["fonts_abs"][_KIND_FACE[kind]], size),
                                      s, tracking) > maxw:
            size -= 1
        return self.font(kind, max(size, lo) if floor is not None else size)

    # time
    def appear(self, t, build, role="ease_out", floor=0.3):
        """(alpha, eased progress) for something that builds over `build`.

        Invisible before `at`, already visible (at `floor` strength) on the frame `at` lands, so a
        viewer never sees an element arrive a frame late; `build` None means "always there".
        """
        if build is None:
            return 1.0, 1.0
        at, dur = build_window(build)
        if not reached(t, at):
            return 0.0, 0.0
        e = ease(self.tokens, role, prog(t, at, dur))
        return floor + (1 - floor) * e, e

    # frames
    def blank(self):
        return Image.new("RGBA", self.canvas, (0, 0, 0, 0))

    def solid(self, name):
        return Image.new("RGBA", self.canvas, self.col(name) + (255,))


def line_height(font):
    asc, desc = font.getmetrics()
    return asc + desc


# --- the pen ---------------------------------------------------------------------------------------
class NullPen:
    def __getattr__(self, _):
        return lambda *a, **k: None


def _composite(dst, src, x, y):
    """alpha_composite with clipping, so a layer that pokes past the edge cannot raise."""
    x, y = int(x), int(y)
    sx, sy = max(0, -x), max(0, -y)
    ex, ey = min(src.width, dst.width - x), min(src.height, dst.height - y)
    if ex <= sx or ey <= sy:
        return
    piece = src.crop((sx, sy, ex, ey)) if (sx, sy, ex, ey) != (0, 0, src.width, src.height) else src
    dst.alpha_composite(piece, dest=(x + sx, y + sy))


class Pen:
    """Drawing in canvas coordinates onto an image whose (0,0) sits at `origin` on the canvas."""

    def __init__(self, img, origin=(0, 0)):
        self.img = img
        self.origin = (int(origin[0]), int(origin[1]))
        self.d = ImageDraw.Draw(img)

    def _p(self, pts):
        ox, oy = self.origin
        flat = list(pts)
        if flat and isinstance(flat[0], (tuple, list)):
            return [(p[0] - ox, p[1] - oy) for p in flat]
        return [flat[i] - (ox if i % 2 == 0 else oy) for i in range(len(flat))]

    @contextmanager
    def layer(self, box, alpha=1.0):
        """Draw on a transparent patch the size of `box`, then composite it at `alpha`."""
        if alpha <= 0.002:
            yield NullPen()
            return
        x0, y0 = math.floor(box[0]) - 1, math.floor(box[1]) - 1
        x1, y1 = math.ceil(box[2]) + 2, math.ceil(box[3]) + 2
        patch = Image.new("RGBA", (max(1, x1 - x0), max(1, y1 - y0)), (0, 0, 0, 0))
        yield Pen(patch, (x0, y0))
        if alpha < 0.998:
            a = patch.getchannel("A").point(lambda v: int(v * alpha + 0.5))
            patch.putalpha(a)
        _composite(self.img, patch, x0 - self.origin[0], y0 - self.origin[1])

    def _alpha(self, box, alpha, fn):
        if alpha >= 0.998:
            fn(self)
            return
        with self.layer(box, alpha) as sub:
            fn(sub)

    def rect(self, box, fill=None, outline=None, width=1, alpha=1.0):
        self._alpha(box, alpha, lambda p: p.d.rectangle(
            p._p(box), fill=_c(fill), outline=_c(outline), width=width))

    def rrect(self, box, radius, fill=None, outline=None, width=1, alpha=1.0):
        self._alpha(box, alpha, lambda p: p.d.rounded_rectangle(
            p._p(box), radius=radius, fill=_c(fill), outline=_c(outline), width=width))

    def ellipse(self, box, fill=None, outline=None, width=1, alpha=1.0):
        self._alpha(box, alpha, lambda p: p.d.ellipse(
            p._p(box), fill=_c(fill), outline=_c(outline), width=width))

    def polygon(self, pts, fill, alpha=1.0):
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        self._alpha((min(xs), min(ys), max(xs), max(ys)), alpha,
                    lambda p: p.d.polygon(p._p(pts), fill=_c(fill)))

    def line(self, pts, fill, width=2, alpha=1.0, round_ends=True):
        pts = [tuple(p) for p in pts]
        if len(pts) < 2:
            return
        w = max(1, round(width))
        pad = w
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        box = (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)

        def go(p):
            q = p._p(pts)
            p.d.line(q, fill=_c(fill), width=w, joint="curve")
            if round_ends and w > 2:
                r = w / 2
                for (x, y) in (q[0], q[-1]):
                    p.d.ellipse([x - r, y - r, x + r, y + r], fill=_c(fill))
        self._alpha(box, alpha, go)

    def text(self, x, y, s, font, fill, ax="l", ay="t", stroke=0, stroke_fill=None,
             alpha=1.0, tracking=0):
        """Draw `s`; (x, y) is the left/middle/right (ax) and top/middle/bottom (ay) of its line box.

        Returns the layout box (x0, y0, x1, y1) so callers can stack things under it.
        """
        asc, desc = font.getmetrics()
        w, h = run_width(font, s, tracking), asc + desc
        x0 = x - w * {"l": 0.0, "m": 0.5, "r": 1.0}[ax]
        y0 = y - h * {"t": 0.0, "m": 0.5, "b": 1.0}[ay]
        if alpha <= 0.002 or not s:
            return (x0, y0, x0 + w, y0 + h)
        pad = stroke + 2
        size = (int(math.ceil(w)) + 2 * pad, h + 2 * pad)

        def mask(sw):
            m = Image.new("L", size, 0)
            d = ImageDraw.Draw(m)
            if not tracking:
                d.text((pad, pad + asc), s, font=font, fill=255, anchor="ls",
                       stroke_width=sw, stroke_fill=255)
            else:
                cx = pad
                for ch in s:
                    d.text((cx, pad + asc), ch, font=font, fill=255, anchor="ls",
                           stroke_width=sw, stroke_fill=255)
                    cx += font.getlength(ch) + tracking
            return m

        runs = []
        if stroke:
            runs.append((mask(stroke), stroke_fill or (0, 0, 0)))
        runs.append((mask(0), fill))
        px, py = round(x0) - pad - self.origin[0], round(y0) - pad - self.origin[1]
        for m, colour in runs:
            if alpha < 0.998:
                m = m.point(lambda v: int(v * alpha + 0.5))
            patch = Image.new("RGBA", size, tuple(colour[:3]) + (0,))
            patch.putalpha(m)
            _composite(self.img, patch, px, py)
        return (x0, y0, x0 + w, y0 + h)


def _c(colour):
    if colour is None:
        return None
    colour = tuple(colour)
    return colour if len(colour) == 4 else colour + (255,)


# --- drawing helpers used by several families -------------------------------------------------------
def plate(pen, ctx, box, fill, alpha=1.0, outline=None, width=None):
    pen.rrect(box, ctx.radius, fill=fill, outline=outline, width=width or ctx.stroke, alpha=alpha)


def arrowhead(pen, tip, frm, size, colour, alpha=1.0):
    """A filled triangle with its point at `tip`, facing away from `frm`."""
    dx, dy = tip[0] - frm[0], tip[1] - frm[1]
    n = math.hypot(dx, dy) or 1.0
    ux, uy = dx / n, dy / n
    bx, by = tip[0] - ux * size, tip[1] - uy * size
    nx, ny = -uy * size * 0.55, ux * size * 0.55
    pen.polygon([tip, (bx + nx, by + ny), (bx - nx, by - ny)], colour, alpha)


def polyline_upto(points, fraction):
    """The leading `fraction` of a polyline by length, as (points, last_segment_from)."""
    if len(points) < 2:
        return list(points), None
    lengths = [math.dist(points[i], points[i + 1]) for i in range(len(points) - 1)]
    goal = sum(lengths) * clamp(fraction)
    out, walked = [tuple(points[0])], 0.0
    prev = tuple(points[0])
    for i, seg in enumerate(lengths):
        a, b = points[i], points[i + 1]
        if walked + seg >= goal:
            f = 0 if seg == 0 else (goal - walked) / seg
            tip = (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
            out.append(tip)
            return out, (a if f > 0 else prev)
        out.append(tuple(b))
        walked += seg
        prev = a
    return out, points[-2]


# --- the primitive wrapper -------------------------------------------------------------------------------
class Primitive:
    """A named primitive: SCHEMA + static layer + per-time draw, exposing render/frame_at.

    `static(spec, ctx)` returns the unchanging layer (an RGBA Image) or None for a transparent one.
    `draw(img, spec, t, ctx)` paints the time-varying part onto a copy of it. `check(spec, ctx)`
    may raise ValueError for rules a schema cannot express.
    """

    def __init__(self, name, schema, static, draw, overlay, check=None, wants_seconds=False):
        self.name, self.SCHEMA, self.OVERLAY = name, schema, overlay
        self._static, self._draw, self._check = static, draw, check
        self.wants_seconds = wants_seconds

    def __repr__(self):
        return f"<graphics primitive {self.name}>"

    def _prepare(self, spec, canvas, tokens):
        validate(spec, self.SCHEMA, self.name)
        tokens = tokens or load_tokens()
        ctx = Ctx(canvas, tokens, spec)
        if self._check:
            self._check(spec, ctx)
        base = self._static(spec, ctx) if self._static else None
        return ctx, (base if base is not None else ctx.blank())

    def frame_at(self, spec, t, canvas=(1920, 1080), tokens=None):
        ctx, base = self._prepare(spec, canvas, tokens)
        img = base.copy()
        self._draw(img, spec, float(t), ctx)
        return img

    def render(self, spec, seconds, canvas=(1920, 1080), fps=30, tokens=None):
        """Validate now, then return a generator of exactly round(seconds*fps) RGBA frames."""
        if self.wants_seconds and "seconds" not in spec:
            spec = {**spec, "seconds": float(seconds)}
        ctx, base = self._prepare(spec, canvas, tokens)
        count = int(round(seconds * fps))

        def frames():
            for i in range(count):
                img = base.copy()
                self._draw(img, spec, i / fps, ctx)
                yield img
        return frames()



def source_tag(pen, ctx, text, alpha=1.0):
    """A small provenance tag, bottom-right inside the safe box, on a paper plate."""
    font = ctx.font("caption")
    pad = round(font.size * 0.4)
    w = run_width(font, text) + 2 * pad
    h = line_height(font) + pad
    x1, y1 = ctx.box[2], ctx.box[3]
    box = (x1 - w, y1 - h, x1, y1)
    plate(pen, ctx, box, ctx.col("paper"), alpha=alpha * 0.94)
    pen.text(x1 - pad, y1 - h / 2, text, font, ctx.col("ink"), ax="r", ay="m", alpha=alpha)
    return box
