"""Compute scenes: what happens, physically, when a language model answers a question.

Built for the episode about a ChatGPT request, but each scene is parametric and knows nothing about
that episode: a chat window that writes one token at a time, the trip a request makes over radio and
fibre, a tokenizer, an embedding space, a transformer's stack of layers with attention, a mixture-of-
experts router, next-token scores, an accelerator package where memory feeds the multipliers, bars
that race, a number travelling a long wire, a high-bandwidth-memory stack taken apart, batching and
the KV cache, number widths, a rack of 72 GPUs, and the loop that carries the heat to a cooling tower.

Conventions are the ones in scenes.py: the picture plane is XZ, the camera looks along +Y from the -Y
side (azimuth near -90), text is laid flat on a plane facing -Y.

Where a scene shows numbers they are real or labelled by the storyboard: token ids come from OpenAI's
o200k tokenizer (the default sentence and its ids were produced with tiktoken), the GB200 NVL72 rack
has 18 compute trays of four GPUs and nine NVLink switch trays, a Blackwell package is two compute dies
with four HBM stacks beside each.
"""
import math
import random
import re

import bpy
from mathutils import Vector

import kit
import look
from kit import FPS, placed
from optics import (FACE, draw_curve, f, gone_at, haze, hidden_until, key_glow, polyline, text)

WARM = look.WARM
COOL = look.COOL
GREEN = (0.35, 1.0, 0.45)
COPPER = (0.42, 0.18, 0.06)
HUES = [(0.20, 0.72, 1.0), (1.0, 0.45, 0.10), (0.55, 1.0, 0.40), (0.85, 0.40, 1.0), (1.0, 0.85, 0.25)]

CAT_TOKENS = "Why| does| my| cat| sound| like| a| carb|ure|tt|or|?"
CAT_IDS = "13903|2226|922|9059|7351|1299|261|41933|627|1037|267|30"


def _split(value, default, sep="|"):
    raw = value if value not in (None, "") else default
    if isinstance(raw, list):
        return [str(x) for x in raw]
    return str(raw).split(sep)


def _width(s, size):
    """Rough advance of a string in Inter SemiBold at `size`."""
    return sum(0.24 if c in " .,'!|ilj" else 0.62 if c in "mwMW" else 0.55 if c.isupper() else 0.45 for c in s) * size


def flash(material, frames, high, low, length=3):
    """Key a light to `high` for `length` frames at each frame in `frames`, `low` between."""
    keys = [(1, low)]
    for fr in sorted(frames):
        keys += [(fr - 1, low), (fr, high), (fr + length, high), (fr + length + 2, low)]
    key_glow(material, keys)


def slide(ob, f0, f1, start, end):
    ob.location = start
    ob.keyframe_insert("location", frame=max(1, f0))
    ob.location = end
    ob.keyframe_insert("location", frame=max(f0 + 1, f1))


def constant(ob):
    if ob.animation_data and ob.animation_data.action:
        for fc in ob.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"


# ---------------------------------------------------------------------------
# 1. a chat window that writes one token at a time
# ---------------------------------------------------------------------------

def token_stream(p, sec):
    """A chat window: the question sits at the top, the answer arrives one token at a time with an uneven
    rhythm. With `fetch`, a strip under the window shows a memory block feeding a chip, one pulse per token."""
    from scenes import Set
    s = Set(sec)
    prompt = str(p.get("prompt") or "Why does my cat sound like a carburettor?")
    tokens = _split(p.get("answer"), "Cats| purr| by| rapidly| twitching| the| muscles| of| the| voice| box|,| so| the|"
                    " air| you| hear| rattles| through| about| twenty| five| times| a| second|.")
    if len(tokens) == 1 and " " in tokens[0].strip():
        # plain prose: stream it word by word (punctuation as its own piece) instead of popping in as one block
        tokens = re.findall(r" ?[^\s.,;:!?]+|[.,;:!?]", tokens[0])
    fetch = bool(p.get("fetch", False))
    panel = kit.box("panel", (0, 0.12, 2.6), (10.4, 0.14, 5.8), kit.mat("panel", (0.025, 0.03, 0.04), roughness=0.7), bevel=0.1)
    kit.box("panel-rim", (0, 0.2, 2.6), (10.6, 0.06, 6.0), look.neon("panel-rim", COOL, 0.35), bevel=0.1)
    bw = min(9.6, _width(prompt, 0.30) + 0.7)
    bubble = kit.box("bubble", (4.9 - bw / 2, -0.02, 4.75), (bw, 0.08, 0.66), kit.mat("bubble", (0.10, 0.13, 0.20), roughness=0.6), bevel=0.12)
    q = text("prompt", prompt, (4.9 - bw / 2, -0.09, 4.75), 0.30)
    size, x0, x1 = 0.34, -4.6, 4.6
    x, z = x0, 3.75
    placed_tokens = []
    ink = kit.mat("answer-ink", (0.93, 0.93, 0.90), emission=1.2)
    for k, tok in enumerate(tokens):
        word = tok.strip()
        lead = 0.28 * size if tok.startswith(" ") else 0.0
        ob = text(f"tok{k}", word, (x0, -0.07, z), size, ink, align="LEFT")
        ob["cut_ok"] = True            # a close-up on typed text may cut the words at its edges
        bpy.context.view_layer.update()
        # the glyphs' real advance, so pieces of one word (tw|itching) sit flush and spaces stay even
        w = ob.dimensions.x if ob.dimensions.x > 0 else _width(word, size)
        if x + lead + w > x1:
            x, z, lead = x0, z - 0.62, 0.0
        x += lead
        ob.location = (x, -0.07, z)
        placed_tokens.append((ob, x + w, z))
        x += w + 0.02 * size
    cursor = kit.box("cursor", (x0, -0.07, 3.75), (0.05, 0.02, 0.42), look.neon("cursor", COOL, 4.0), bevel=0)
    s.pin("prompt", (4.9 - bw * 0.2, -0.1, 4.95), bubble, hold=[bubble, q])
    s.pin("answer", (x0 + 0.6, -0.1, 3.95))
    s.pin("cursor", (x0 + 2.5, -0.1, 3.4))
    rng = random.Random(int(p.get("seed", 5)))
    mem_mat = chip_mat = None
    if fetch:
        mem_mat, chip_mat = look.neon("strip-mem", COOL, 0.6), look.neon("strip-chip", WARM, 0.3)
        kit.box("strip-mem", (-4.2, -0.4, -0.9), (1.4, 1.0, 0.9), mem_mat, bevel=0.05)
        kit.box("strip-chip", (4.2, -0.4, -0.9), (1.4, 1.0, 0.5), chip_mat, bevel=0.05)
        kit.box("strip-bus", (0, -0.4, -1.0), (7.0, 0.3, 0.06), kit.slate(), bevel=0)
        text("strip-mem-t", "memory", (-4.2, -0.95, -0.25), 0.22)
        text("strip-chip-t", "chip", (4.2, -0.95, -0.45), 0.22)
        s.pin("memory", (-4.2, -0.9, -0.5))
        s.pin("chip", (4.2, -0.9, -0.7))

    def type_(t0, t1):
        hidden_until(bubble, f(t0))
        hidden_until(q, f(t0))

    def stream(t0, t1):
        times, t = [], t0
        span = t1 - t0
        base = span / max(1, len(placed_tokens))
        for k in range(len(placed_tokens)):
            times.append(t)
            t += base * rng.uniform(0.55, 1.45) * (1.9 if rng.random() < 0.12 else 1.0)
        scale = span / max(1e-3, t - t0)
        times = [t0 + (x - t0) * scale for x in times]
        for (ob, xe, ze), tt in zip(placed_tokens, times):
            fr = f(tt)
            hidden_until(ob, fr)
            cursor.location = (xe + 0.08, -0.07, ze)
            cursor.keyframe_insert("location", frame=fr + 1)
        constant(cursor)
        if fetch:
            bead_mat = look.neon("bead", COOL, 9.0)
            frames = []
            for k, tt in enumerate(times):
                fr = f(tt)
                frames.append(fr)
                bead = kit.ico(f"bead{k}", (-3.4, -0.4, -0.9), 0.11, bead_mat, subdivisions=2, smooth=True)
                slide(bead, max(2, fr - 7), fr, (-3.4, -0.4, -0.9), (3.4, -0.4, -0.9))
                hidden_until(bead, max(2, fr - 7))
                gone_at(bead, fr, 2)
            flash(chip_mat, frames, 6.0, 0.3, 2)
    s.action("type", type_, at=0.0, span=0.4)
    s.action("stream", stream, at=0.12, span=max(1.5, sec * 0.8))
    s.view("wide", (0, 0, 1.9 if fetch else 2.6), 16.5 if fetch else 13.5, -90, 2.6 if fetch else 3.0)
    # the answer close enough to read, with the question wholly out of frame above it: at 5.6 the
    # frame's top edge sits under the bubble instead of slicing through it
    s.view("close", (-1.6, 0, 2.9), 5.6, -80, 3.5)
    if fetch:
        s.view("low", (0, 0, 0.6), 12.5, -92, 0.9)
    s.lens, s.floor_grid, s.floor_z = 40.0, 0, -1.6
    return s


# ---------------------------------------------------------------------------
# 2. the trip: radio to a mast, light down a fibre to a building
# ---------------------------------------------------------------------------

def fiber_trip(p, sec):
    """A phone sends radio waves to a mast; from there the request runs as light down an optical fibre
    to a data centre. With `markers`, distance ticks stand along the fibre."""
    from scenes import Set
    s = Set(sec)
    markers = bool(p.get("markers", False))
    kit.box("ground", (1.5, 0, -0.03), (28, 7, 0.06), kit.mat("trip-ground", (0.03, 0.035, 0.04), roughness=0.9), bevel=0)
    # phone on a small stand
    kit.box("phone", (-11.0, 0, 1.15), (0.55, 0.09, 1.1), kit.epoxy(), bevel=0.06)
    screen = kit.box("phone-screen", (-11.0, -0.05, 1.15), (0.47, 0.01, 0.98), look.neon("phone-screen", COOL, 1.6), bevel=0.04)
    kit.box("stand", (-11.0, 0.15, 0.3), (0.4, 0.4, 0.6), kit.slate(), bevel=0.03)
    # a lattice mast with three antenna panels
    steel = kit.steel()
    legs, braces = [], []
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        legs.append(((-7.5 + sx * 0.5, sy * 0.5, 0), (-7.5 + sx * 0.12, sy * 0.12, 5.2)))
    for k in range(8):
        z0, z1 = k * 0.65, (k + 1) * 0.65
        r0, r1 = 0.5 - 0.38 * z0 / 5.2, 0.5 - 0.38 * z1 / 5.2
        braces.append(((-7.5 - r0, -r0, z0), (-7.5 + r1, -r1, z1)))
        braces.append(((-7.5 + r0, -r0, z0), (-7.5 - r1, -r1, z1)))
    kit.rods("mast", legs + braces, 0.035, steel)
    for k, a in enumerate((0, 120, 240)):
        ang = math.radians(a - 90)
        kit.box(f"antenna{k}", (-7.5 + 0.28 * math.cos(ang), 0.28 * math.sin(ang), 4.9), (0.16, 0.06, 0.8), kit.base(), bevel=0.02).rotation_euler[2] = ang + math.pi / 2
    # the fibre: from the mast's foot along the ground to the building
    fibre = polyline("fibre", [(-7.5, 0, 0.06), (-4, 0.25, 0.06), (0, -0.2, 0.06), (4, 0.2, 0.06), (8.2, 0, 0.06)], 0.05,
                     look.neon("fibre", COOL, 0.25), resolution=3)
    # the data centre: a long low hall, louvres, rooftop units
    hall = kit.box("hall", (11.8, 0, 1.2), (7.0, 5.0, 2.4), kit.mid(), bevel=0.05)
    kit.boxes("louvres", [placed((8.27, y * 0.55, 1.0), (0.04, 0.42, 1.3)) for y in range(-3, 4)], kit.slate())
    kit.box("door", (8.27, 1.9, 0.6), (0.05, 0.7, 1.2), kit.slate(), bevel=0.01)
    units = []
    for i in range(5):
        for j in range(2):
            units.append(((9.4 + i * 1.2, -1.1 + j * 2.2, 2.6), 0.42, 0.25))
    kit.cylinders("roof-fans", units, kit.steel(), segments=24)
    kit.boxes("roof-units", [placed((9.4 + i * 1.2, -1.1 + j * 2.2, 2.48), (1.0, 1.0, 0.18)) for i in range(5) for j in range(2)], kit.slate())
    kit.box("window-strip", (11.8, -2.52, 1.9), (6.4, 0.03, 0.12), look.neon("window-strip", COOL, 1.2), bevel=0)
    tick_mat = kit.mat("tick", (0.9, 0.9, 0.88), emission=1.0)
    if markers:
        for k, label in enumerate(("0", "250 km", "500 km", "750 km", "1,000 km")):
            xk = -7.5 + k * 15.7 / 4
            kit.box(f"tick{k}", (xk, -0.5, 0.25), (0.05, 0.05, 0.5), tick_mat, bevel=0)
            text(f"tick-t{k}", label, (xk, -0.55, 0.75), 0.32)
    # close-ups hold the phone and the hall whole: at the fixed distance the phone was a small
    # light in a dark frame and the hall a blank wall (QC empty_shot, ask-chatgpt v5)
    s.pin("phone", (-11.0, -0.2, 1.9), screen, hold=[screen])
    s.pin("mast", (-7.5, -0.2, 5.0))
    s.pin("fibre", (-2.0, -0.2, 0.15))
    s.pin("building", (10.0, -2.5, 2.6), hall, hold=[hall])
    rng = random.Random(3)

    def pulses(name, t0, t1, outward, color):
        m = look.neon(name, color, 10.0)
        a, b = f(t0), f(t1)
        span = max(10, (b - a) // 2)
        for k in range(6):
            start = a + k * max(2, (b - a - span) // 6)
            bead = kit.ico(f"{name}{k}", (0, 0, 0.12), 0.12, m, subdivisions=2, smooth=True)
            x_from, x_to = (-7.5, 8.2) if outward else (8.2, -7.5)
            slide(bead, start, start + span, (x_from, rng.uniform(-0.05, 0.05), 0.12), (x_to, 0, 0.12))
            kit._linear(bead)
            hidden_until(bead, max(2, start))
            gone_at(bead, start + span, 2)

    def send(t0, t1):
        a = f(t0)
        for k in range(3):
            m = haze(f"radio{k}", COOL, 0.0)
            arc = kit.cyl(f"radio{k}", (-11.0, 0, 1.7), 0.3, 0.02, m, rot=(0, math.radians(90), 0), verts=48)
            arc.scale = (1, 1, 1)
            arc.keyframe_insert("scale", frame=a + k * 6)
            arc.scale = (14, 14, 1)
            arc.keyframe_insert("scale", frame=a + k * 6 + 30)
            key_glow(m, [(1, 0.0), (a + k * 6, 0.0), (a + k * 6 + 2, 0.5), (a + k * 6 + 30, 0.0)])
        key_glow(fibre.data.materials[0], [(1, 0.25), (a + 20, 0.25), (a + 26, 1.2)])
        pulses("out", t0 + 0.8, t1, True, COOL)

    def reply(t0, t1):
        pulses("back", t0, t1, False, WARM)
    s.action("send", send, at=0.05, span=max(2.5, min(sec * 0.6, 6.0)))
    s.action("reply", reply, at=0.7, span=max(1.5, min(sec * 0.28, 3.0)))
    s.view("wide", (2.0, 0, 1.2), 32.0, -94, 9.5)
    s.view("phone", (-9.5, 0, 2.0), 8.0, -68, 3.0)
    s.view("fibre", (0, 0, 0.3), 10.0, -122, 1.6)
    s.view("building", (10.5, 0, 1.4), 11.0, -62, 4.8)
    s.lens, s.floor_grid, s.floor_z = 40.0, 0, 0.0
    return s


# ---------------------------------------------------------------------------
# 3. a tokenizer
# ---------------------------------------------------------------------------

def tokenizer(p, sec):
    """A sentence breaks into tokens (whole words, fragments of rare words, punctuation); each token gets
    its id in the vocabulary, and each id picks out a column of numbers. Default ids are OpenAI's o200k."""
    from scenes import Set
    s = Set(sec)
    toks = _split(p.get("tokens"), CAT_TOKENS)
    ids = _split(p.get("ids"), CAT_IDS)
    sentence = "".join(toks)
    size = 0.40
    widths = [max(0.55, _width(t.strip() or "_", 0.34) + 0.32) for t in toks]
    gap = 0.16
    total = sum(widths) + gap * (len(widths) - 1)
    scale = min(1.0, 13.0 / total)
    widths = [w * scale for w in widths]
    gap *= scale
    total = sum(widths) + gap * (len(widths) - 1)
    full = text("sentence", sentence, (0, -0.05, 3.3), size * min(1.0, 13.0 / max(1e-3, _width(sentence, size))))
    tiles, labels, idtexts, columns, mats = [], [], [], [], []
    x = -total / 2
    rng = random.Random(9)
    for k, (tok, w) in enumerate(zip(toks, widths)):
        cx = x + w / 2
        m = look.neon(f"tile{k}", HUES[k % len(HUES)], 0.55, base=tuple(c * 0.18 for c in HUES[k % len(HUES)]))
        mats.append(m)
        tile = kit.box(f"tile{k}", (cx, 0, 3.3), (w, 0.3, 0.72), m, bevel=0.08)
        lab = text(f"tile-t{k}", tok.strip() or "_", (cx, -0.17, 3.3), 0.34 * scale)
        idt = text(f"id{k}", ids[k] if k < len(ids) else "", (cx, -0.05, 2.45), 0.27 * scale)
        lab["cut_ok"] = idt["cut_ok"] = True     # a row of pieces: a close-up on one may cut its neighbours
        cells = [placed((cx, 0, 1.95 - j * 0.2), (w * 0.55 * rng.uniform(0.35, 1.0), 0.12, 0.13)) for j in range(9)]
        col = kit.boxes(f"vector{k}", cells, look.neon("vector", COOL, 1.4))
        tiles.append(tile), labels.append(lab), idtexts.append(idt), columns.append(col)
        x += w + gap
    pick = min(3, len(toks) - 1)
    rare = next((k for k, t in enumerate(toks) if not t.startswith(" ") and k > 0 and t.strip().isalpha()), pick)
    s.pin("sentence", (0, -0.1, 3.75), full, hold=[full])
    # before the split the sentence is one line: a close-up then holds all of it (held_box skips
    # it once it is hidden, and the close-up keeps its fixed distance on the tile)
    s.pin("token", tuple(tiles[pick].location + Vector((0, -0.2, 0.4))), tiles[pick], hold=[full])
    s.pin("rare", tuple(tiles[rare].location + Vector((0, -0.2, 0.4))), tiles[rare])
    s.pin("id", (tiles[pick].location.x, -0.1, 2.55), hold=[idtexts[pick]])
    s.pin("vector", (tiles[pick].location.x, -0.1, 1.3))
    state = {"split": 10 ** 9}

    def split(t0, t1):
        a, b = f(t0), f(t1)
        state["split"] = a
        gone_at(full, a, 6)
        each = max(1, (b - a) // max(1, len(tiles)))
        for k, (tile, lab) in enumerate(zip(tiles, labels)):
            hidden_until(tile, a + 4 + k * each)
            hidden_until(lab, a + 4 + k * each)

    def number(t0, t1):
        a, b = f(t0), f(t1)
        each = max(1, (b - a) // max(1, len(idtexts)))
        for k, idt in enumerate(idtexts):
            hidden_until(idt, max(a, state["split"] + 8) + k * each)

    def embed(t0, t1):
        a, b = f(t0), f(t1)
        each = max(1, (b - a) // max(1, len(columns)))
        for k, col in enumerate(columns):
            hidden_until(col, a + k * each)
    s.action("split", split, at=0.12, span=1.6)
    s.action("number", number, at=0.42, span=1.8)
    s.action("embed", embed, at=0.7, span=1.6)
    s.view("wide", (0, 0, 2.4), 15.5, -90, 2.9)
    s.view("tokens", (0, 0, 3.0), 10.0, -84, 3.4)
    s.view("vector", (tiles[pick].location.x, 0, 2.0), 6.0, -76, 2.6)
    s.lens, s.floor_grid, s.floor_z = 40.0, 0, 0.0
    return s


# ---------------------------------------------------------------------------
# 4. an embedding space
# ---------------------------------------------------------------------------

EMBED_WORDS = {
    "cat": ((2.6, 1.0, 2.5), WARM), "dog": ((3.4, 1.6, 2.1), WARM), "tiger": ((2.2, 2.3, 3.5), WARM),
    "kitten": ((1.5, 0.6, 2.8), WARM), "carburettor": ((-3.4, -0.6, 0.6), COOL), "engine": ((-2.1, -1.9, 1.7), COOL),
    "piston": ((-3.7, -2.5, 2.4), COOL), "apple": ((0.2, 3.2, 0.8), GREEN), "banana": ((0.9, 3.6, 1.2), GREEN),
}


def embedding_space(p, sec):
    """A map turns into a space: on a flat map two numbers place a point; lifted, every word is a point
    whose coordinates are its list of numbers, and words with related meanings sit close together. More
    axes fan out to suggest the thousands of directions a real model uses."""
    from scenes import Set
    s = Set(sec)
    axis_mat = kit.mat("axis", (0.75, 0.77, 0.80), emission=0.6)
    ax = kit.rod("axis-x", (-5, 0, 0), (5, 0, 0), 0.025, axis_mat)
    ay = kit.rod("axis-y", (0, -4, 0), (0, 5, 0), 0.025, axis_mat)
    az = kit.rod("axis-z", (0, 0, 0), (0, 0, 4.6), 0.025, axis_mat)
    kit.boxes("map-grid", [placed((i, 0, 0.0), (0.012, 9, 0.004)) for i in range(-5, 6)]
              + [placed((0, j, 0.0), (10, 0.012, 0.004)) for j in range(-4, 6)], kit.mat("map-grid", (0.16, 0.18, 0.22), emission=0.2))
    rng = random.Random(4)
    extra_mat = haze("extra-axes", (0.6, 0.65, 0.8), 0.25)
    extra = []
    for k in range(14):
        d = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(0.1, 1))).normalized() * rng.uniform(3.0, 4.4)
        extra.append(((0, 0, 0), tuple(d)))
    extra_ob = kit.rods("extra-axes", extra, 0.012, extra_mat)
    points, names = {}, {}
    for word, (xyz, color) in EMBED_WORDS.items():
        m = look.neon(f"pt-{word}", color, 3.0)
        ob = kit.ico(f"pt-{word}", xyz, 0.13, m, subdivisions=2, smooth=True)
        lab = text(f"word-{word}", word, (xyz[0] + 0.25, xyz[1] - 0.05, xyz[2] + 0.18), 0.40, align="LEFT")
        lab.parent = ob
        lab.location = (0.25, -0.05, 0.18)
        points[word], names[word] = ob, lab
    s.pin("cat", (2.6, 0.8, 2.6), points["cat"])
    s.pin("dog", (3.2, 1.3, 2.1), points["dog"])
    s.pin("carburettor", (-3.0, -1.2, 1.0), points["carburettor"])
    s.pin("apple", (0.2, 3.0, 0.9), points["apple"])
    s.pin("origin", (0, -0.2, 0.1))
    arrow_mat = look.neon("arrow", WARM, 2.5)
    arrow = kit.rod("arrow", (0, 0, 0), (2.6, 1.0, 2.5), 0.035, arrow_mat)
    coords = text("coords", "0.021   -0.317   0.884   0.106   ...", (2.7, 0.2, 1.25), 0.30, align="LEFT")
    state = {"lift": None}

    def lift(t0, t1):
        a, b = f(t0), f(t1)
        state["lift"] = a
        for word, ob in points.items():
            x, y, z = ob.location
            ob.location = (x, y, 0.02)
            ob.keyframe_insert("location", frame=1)
            ob.keyframe_insert("location", frame=a)
            ob.location = (x, y, z)
            ob.keyframe_insert("location", frame=b)
        az.scale = (1, 1, 0.001)
        az.keyframe_insert("scale", frame=a)
        az.scale = (1, 1, 1)
        az.keyframe_insert("scale", frame=b)
        az.location = (0, 0, 0.002)
        az.keyframe_insert("location", frame=a)
        az.location = (0, 0, 2.3)
        az.keyframe_insert("location", frame=b)

    def dims(t0, t1):
        a = f(t0)
        key_glow(extra_mat, [(1, 0.0), (a, 0.0), (f(t1), 0.6)])

    def point(t0, t1):
        a, b = f(t0), f(t1)
        arrow.scale = (1, 1, 0.001)
        arrow.keyframe_insert("scale", frame=1)
        arrow.keyframe_insert("scale", frame=a)
        arrow.scale = (1, 1, 1)
        arrow.keyframe_insert("scale", frame=b)
        hidden_until(coords, b)
    s.action("lift", lift, at=0.12, span=2.0)
    s.action("dims", dims, at=0.35, span=1.5)
    s.action("point", point, at=0.6, span=1.2)
    s.view("wide", (0, 0.6, 1.6), 16.5, -102, 6.6)
    s.view("flat", (0, 0.5, 0.0), 6.0, -90, 13.0)
    s.view("animals", (2.6, 1.3, 2.5), 6.5, -78, 3.8)
    s.view("machines", (-2.9, -1.5, 1.2), 6.5, -112, 2.6)
    s.lens, s.floor_grid, s.floor_z = 40.0, 0, -0.6
    return s


# ---------------------------------------------------------------------------
# 5. the stack of layers, and attention
# ---------------------------------------------------------------------------

def model_layers(p, sec):
    """A model as a stack of layers, each a plane of weights. A token's list of numbers rises through
    every layer in turn (each lights as it passes); at one layer the token looks back at the tokens
    before it, and the brightest links show which ones matter (attention)."""
    from scenes import Set
    s = Set(sec)
    n = max(4, min(48, int(p.get("layers", 36))))
    gap = 0.2
    height = n * gap
    rng = random.Random(7)
    slabs, mats = [], []
    for k in range(n):
        m = look.neon(f"layer{k}", COOL, 0.12, base=(0.03, 0.04, 0.06))
        slabs.append(kit.box(f"layer{k}", (0, 0, 0.4 + k * gap), (6.0, 4.0, 0.045), m, bevel=0.01))
        mats.append(m)
    cell_sets = [[], [], []]
    for k in range(n):
        for i in range(22):
            for j in range(14):
                cell_sets[rng.choice((0, 0, 0, 1, 1, 2))].append(
                    placed((-2.7 + i * 0.257, -1.68 + j * 0.258, 0.43 + k * gap), (0.12, 0.12, 0.012)))
    for c, (cells, strength) in enumerate(zip(cell_sets, (0.25, 0.7, 1.6))):
        kit.boxes(f"weights{c}", cells, look.neon(f"weights{c}", (0.55, 0.75, 1.0), strength))
    token_mat = look.neon("token", WARM, 9.0)
    token = kit.ico("token", (0, -2.6, -0.2), 0.16, token_mat, subdivisions=3, smooth=True)
    mid = n // 2
    zl = 0.4 + mid * gap
    prev = []
    for k in range(6):
        prev.append(kit.ico(f"prev{k}", (-5.6 + k * 0.75, -2.6, zl), 0.12, look.neon(f"prev{k}", HUES[k % 5], 3.0), subdivisions=2, smooth=True))
    weights = [0.15, 0.9, 0.25, 0.1, 0.55, 0.3]
    links = []
    for k, (ob, w) in enumerate(zip(prev, weights)):
        a, b = Vector(ob.location), Vector((0, -2.6, zl))
        mid_pt = (a + b) / 2 + Vector((0, 0, 0.9 + 0.12 * k))
        m = haze(f"link{k}", WARM, 0.0)
        line = polyline(f"link{k}", [tuple(a), tuple((a + mid_pt) / 2 + Vector((0, 0, 0.25))), tuple(mid_pt),
                                     tuple((b + mid_pt) / 2 + Vector((0, 0, 0.25))), tuple(b)], 0.012 + 0.03 * w, m)
        links.append((line, m, w))
    s.pin("stack", (3.0, -2.0, 0.4 + height * 0.7))
    s.pin("layer", (2.8, -2.0, zl))
    s.pin("weights", (1.5, -1.6, 0.4 + (n - 1) * gap))
    s.pin("token", (0.2, -2.7, 0.1), token)
    s.pin("attention", (-2.0, -2.6, zl + 1.0))

    def pass_(t0, t1):
        a, b = f(t0), f(t1)
        slide(token, a, b, (0, -2.6, -0.2), (0, -2.6, height + 0.8))
        for k, m in enumerate(mats):
            fr = a + round((b - a) * (k + 1) / (n + 1))
            key_glow(m, [(1, 0.12), (fr - 2, 0.12), (fr, 2.6), (fr + 8, 0.12)])

    def attend(t0, t1):
        a, b = f(t0), f(t1)
        for k, (line, m, w) in enumerate(links):
            draw_curve(line, a + k * 3, a + k * 3 + 14)
            key_glow(m, [(1, 0.0), (a + k * 3, 0.0), (a + k * 3 + 6, 0.5 + 6 * w)])
    s.action("pass", pass_, at=0.08, span=max(2.0, min(sec * 0.5, 6.0)))
    s.action("attend", attend, at=0.6, span=1.6)
    s.view("wide", (0, 0, height * 0.5 + 0.4), 9.0 + height * 1.25, -104, height * 0.75 + 2.0)
    s.view("layer", (0.5, 0, zl), 7.5, -70, zl + 2.4)
    s.view("attention", (-2.2, -2.6, zl + 0.5), 7.0, -96, zl + 1.8)
    s.lens, s.floor_grid, s.floor_z = 40.0, 0, -0.4
    return s


# ---------------------------------------------------------------------------
# 6. a mixture of experts
# ---------------------------------------------------------------------------

def experts(p, sec):
    """One layer's experts: 128 small networks laid out in a grid; for each token a router picks four of
    them, and only those four light up and do any work."""
    from scenes import Set
    s = Set(sec)
    nx, ny = 16, 8
    count = max(8, min(256, int(p.get("experts", 128))))
    pick = max(1, min(8, int(p.get("pick", 4))))
    rng = random.Random(int(p.get("seed", 2)))
    blocks = []
    for k in range(count):
        i, j = k % nx, k // nx
        m = look.neon(f"expert{k}", WARM, 0.0, base=(0.035, 0.037, 0.045))
        ob = kit.box(f"expert{k}", (-4.5 + i * 0.6, -1.4 + j * 0.6, 0.25), (0.44, 0.44, 0.44), m, bevel=0.03)
        blocks.append((ob, m))
    router_mat = look.neon("router", COOL, 2.0)
    router = kit.ico("router", (0, -5.0, 2.2), 0.42, router_mat, subdivisions=1)
    router.scale = (1, 1, 1.4)
    token_mat = look.neon("e-token", COOL, 8.0)
    s.pin("router", (0.3, -5.2, 2.6), router)
    s.pin("expert", (-4.5 + 9 * 0.6, -1.6, 0.6))
    s.pin("grid", (4.4, -1.8, 0.5))
    s.pin("token", (-5.5, -5.2, 2.5))
    beams = []

    def route(t0, t1):
        a, b = f(t0), f(t1)
        tokens = max(1, int(p.get("tokens", 4)))
        each = max(18, (b - a) // tokens)
        lit = {k: [] for k in range(count)}
        for t in range(tokens):
            ta = a + t * each
            bead = kit.ico(f"etok{t}", (-6.5, -5.0, 2.2), 0.14, token_mat, subdivisions=2, smooth=True)
            slide(bead, ta, ta + 10, (-6.5, -5.0, 2.2), (0, -5.0, 2.2))
            hidden_until(bead, max(2, ta))
            gone_at(bead, ta + 11, 2)
            chosen = rng.sample(range(count), pick)
            for c in chosen:
                lit[c].append(ta + 12)
                m = haze(f"beam{t}-{c}", WARM, 0.0)
                ob, _ = blocks[c]
                beam = kit.rod(f"beam{t}-{c}", (0, -5.0, 2.2), tuple(ob.location), 0.02, m)
                key_glow(m, [(1, 0.0), (ta + 10, 0.0), (ta + 12, 1.6), (ta + each - 4, 1.6), (ta + each, 0.0)])
                beams.append(beam)
            key_glow(router_mat, [(ta + 9, 2.0), (ta + 11, 8.0), (ta + 16, 2.0)])
        for c, frames in lit.items():
            if frames:
                keys = [(1, 0.0)]
                for fr in frames:
                    keys += [(fr - 1, 0.0), (fr + 2, 9.0), (fr + each - 6, 9.0), (fr + each - 2, 0.0)]
                key_glow(blocks[c][1], keys)
    s.action("route", route, at=0.1, span=max(3.0, sec * 0.8))
    s.view("wide", (0, -1.5, 0.8), 16.5, -98, 9.0)
    s.view("router", (-0.4, -4.4, 1.8), 7.0, -72, 3.4)
    s.view("grid", (0, 0.2, 0.2), 9.5, -92, 7.5)
    s.lens, s.floor_grid, s.floor_z = 40.0, 1.0, 0.0
    return s


# ---------------------------------------------------------------------------
# 7. next-token scores
# ---------------------------------------------------------------------------

def next_token(p, sec):
    """The last layer gives every token in the vocabulary a score; the top few are drawn as bars, one is
    picked (usually a likely one), it joins the sentence, and the model runs again for the next."""
    from scenes import Set
    s = Set(sec)
    prefix = str(p.get("prefix") or "Cats purr by rapidly twitching")
    cands = [c.split(":") for c in _split(p.get("candidates"), " the:0.46| their:0.22| tiny:0.11| muscles:0.08| vocal:0.05")]
    follow = _split(p.get("next"), " muscles| of| the| voice| box")
    size = 0.40
    x_end = -5.8 + _width(prefix, size)
    sent = text("prefix", prefix, (-5.8, -0.05, 5.0), size, align="LEFT")
    model_mat = look.neon("model", COOL, 0.4, base=(0.04, 0.05, 0.07))
    model = kit.group("model", [kit.box(f"model{k}", (0, 0.4, 3.0 + k * 0.18), (2.2, 1.4, 0.12), model_mat, bevel=0.02) for k in range(4)])
    n = len(cands)
    gap = min(2.2, 11.0 / n)
    x0 = -(n - 1) * gap / 2
    bars = []
    top = 2.4
    for k, (tok, prob) in enumerate(cands):
        h = max(0.06, top * float(prob) / max(float(c[1]) for c in cands))
        chosen = k == int(p.get("choose", 0))
        m = look.neon(f"cand{k}", WARM if chosen else COOL, 1.2 if chosen else 0.7)
        bar = kit.box(f"cand{k}", (x0 + k * gap, 0, h / 2), (gap * 0.55, 0.5, h), m, bevel=0.02)
        lab = text(f"cand-t{k}", tok.strip(), (x0 + k * gap, -0.3, -0.35), 0.32)
        pct = text(f"cand-p{k}", f"{round(float(prob) * 100)}%", (x0 + k * gap, -0.3, h + 0.3), 0.26)
        bars.append((bar, h, lab, pct, m, chosen))
    s.pin("sentence", (-3.0, -0.1, 5.35), sent)
    s.pin("model", (0.8, -0.4, 3.4), model)
    choose = int(p.get("choose", 0))
    s.pin("chosen", (x0 + choose * gap, -0.4, bars[choose][1] + 0.3))
    s.pin("bars", (x0 + (n - 1) * gap, -0.4, 0.5))
    state = {"end": x_end}

    def score(t0, t1):
        a, b = f(t0), f(t1)
        flash(model_mat, [a], 4.0, 0.4, 6)
        each = max(1, (b - a) // n)
        for k, (bar, h, lab, pct, m, ch) in enumerate(bars):
            bar.scale[2] = 0.001
            bar.location[2] = 0.0
            bar.keyframe_insert("scale", frame=1)
            bar.keyframe_insert("location", frame=1)
            bar.keyframe_insert("scale", frame=a + k * each)
            bar.keyframe_insert("location", frame=a + k * each)
            bar.scale[2] = 1.0
            bar.location[2] = h / 2
            bar.keyframe_insert("scale", frame=a + k * each + 10)
            bar.keyframe_insert("location", frame=a + k * each + 10)
            hidden_until(lab, a + k * each)
            hidden_until(pct, a + k * each + 8)

    def pick_(t0, t1):
        a, b = f(t0), f(t1)
        bar, h, lab, pct, m, ch = bars[choose]
        flash(m, [a], 7.0, 1.2, 10)
        word = cands[choose][0]
        fly = text("picked", word.strip(), (bar.location.x, -0.3, -0.35), 0.32, kit.mat("picked-ink", WARM, emission=3.0), align="LEFT")
        lead = 0.12 if word.startswith(" ") else 0.0
        slide(fly, a + 4, b, (bar.location.x, -0.3, -0.35), (state["end"] + lead, -0.05, 5.0))
        fly.scale = (1, 1, 1)
        fly.keyframe_insert("scale", frame=a + 4)
        fly.scale = (size / 0.32,) * 3
        fly.keyframe_insert("scale", frame=b)
        hidden_until(fly, a + 4)
        state["end"] += lead + _width(word.strip(), size)

    def loop(t0, t1):
        a, b = f(t0), f(t1)
        each = max(8, (b - a) // max(1, len(follow)))
        frames = []
        for k, word in enumerate(follow):
            fr = a + k * each
            frames.append(fr)
            lead = 0.12 if word.startswith(" ") else 0.0
            ob = text(f"next{k}", word.strip(), (state["end"] + lead, -0.05, 5.0), size, align="LEFT")
            hidden_until(ob, fr + 4)
            state["end"] += lead + _width(word.strip(), size)
        flash(model_mat, frames, 4.0, 0.4, 4)
    s.action("score", score, at=0.08, span=1.4)
    s.action("pick", pick_, at=0.42, span=1.2)
    s.action("loop", loop, at=0.66, span=max(1.5, sec * 0.3))
    s.view("wide", (0, 0, 2.4), 15.0, -90, 3.2)
    s.view("bars", (0, 0, 1.1), 12.5, -90, 2.4)
    s.view("sentence", (-1.0, 0, 4.8), 9.0, -88, 5.2)
    s.lens, s.floor_grid, s.floor_z = 40.0, 1.0, -0.7
    return s


# ---------------------------------------------------------------------------
# 8. an accelerator package: memory feeding the multipliers
# ---------------------------------------------------------------------------

def _hbm(name, loc, w=1.0, d=1.1, layers=8, material=None):
    x, y, z = loc
    m = material or kit.circuit()
    parts = [kit.box(f"{name}-base", (x, y, z + 0.06), (w, d, 0.12), kit.silicon(), bevel=0.01)]
    cells = [placed((x, y, z + 0.17 + k * 0.075), (w * 0.98, d * 0.98, 0.055)) for k in range(layers)]
    parts.append(kit.boxes(f"{name}-dram", cells, m))
    return kit.group(name, parts)


def accelerator(p, sec):
    """A Blackwell-style package from above: two compute dies joined in the middle, four stacks of
    high-bandwidth memory beside each, all on one interposer. Weights stream from the stacks into the
    dies without pause. In `decode` mode the multipliers flash for an instant per token and then wait;
    in `prefill` and `batch` they stay busy."""
    from scenes import Set
    s = Set(sec)
    mode = p.get("mode", "decode")
    kit.box("substrate", (0, 0, 0.1), (13.0, 8.4, 0.2), kit.pcb(), bevel=0.04)
    kit.box("interposer", (0, 0, 0.25), (10.6, 6.6, 0.1), kit.silicon(), bevel=0.01)
    tiles_lit, tiles_rest = [], []
    rng = random.Random(6)
    for side in (-1, 1):
        cx = side * 1.45
        kit.box(f"die{side}", (cx, 0, 0.36), (2.7, 4.4, 0.12), kit.mat("die", (0.07, 0.08, 0.10), metallic=0.4, roughness=0.4), bevel=0.01)
        for i in range(10):
            for j in range(16):
                m = placed((cx - 1.17 + i * 0.26, -1.95 + j * 0.26, 0.43), (0.2, 0.2, 0.02))
                (tiles_lit if rng.random() < 0.35 else tiles_rest).append(m)
    lit_mat = look.neon("mult-lit", WARM, 0.05, base=(0.06, 0.05, 0.05))
    rest_mat = look.neon("mult-rest", WARM, 0.05, base=(0.06, 0.05, 0.05))
    kit.boxes("mult-lit", tiles_lit, lit_mat)
    kit.boxes("mult-rest", tiles_rest, rest_mat)
    kit.box("joint", (0, 0, 0.37), (0.12, 4.4, 0.1), look.neon("joint", COOL, 2.0), bevel=0)
    frames = s.frames
    for side in (-1, 1):
        for k, y in enumerate((-2.25, -0.75, 0.75, 2.25)):
            _hbm(f"hbm{side}{k}", (side * 4.25, y, 0.3))
            bus = kit.box(f"bus{side}{k}", (side * 3.2, y, 0.31), (1.0, 0.8, 0.03),
                          look.signal_material(f"bus{side}{k}", frames, axis="X", color=COOL, rest=0.15, peak=7.0,
                                               spacing=0.33, speed=1.2, lanes=12.0), bevel=0)
            if side > 0:
                bus.rotation_euler[2] = math.pi
    s.pin("memory", (-4.25, -2.6, 1.0))
    s.pin("compute", (-1.45, -2.4, 0.5))
    s.pin("bus", (-3.2, -0.95, 0.4))
    s.pin("joint", (0.0, -2.3, 0.5))
    s.pin("package", (5.5, -3.8, 0.3))

    def compute(t0, t1):
        a = f(t0)
        if mode == "decode":
            period = max(10, int(p.get("period", 0.6) * FPS))
            fl = list(range(a, frames, period))
            flash(lit_mat, fl, 12.0, 0.05, 1)
            flash(rest_mat, fl, 9.0, 0.05, 1)
        else:
            keys_l, keys_r = [(1, 0.05), (a, 0.05)], [(1, 0.05), (a, 0.05)]
            busy = 6.0 if mode == "prefill" else 4.0
            for fr in range(a + 2, frames, 3):
                keys_l.append((fr, busy * rng.uniform(0.6, 1.0)))
                keys_r.append((fr, busy * rng.uniform(0.4, 1.0) * (1.0 if mode == "prefill" else 0.8)))
            key_glow(lit_mat, keys_l)
            key_glow(rest_mat, keys_r)
    s.action("compute", compute, at=0.08, span=0.5)
    s.view("wide", (0, 0, 0.2), 15.5, -100, 10.0)
    s.view("memory", (-4.0, -0.8, 0.6), 5.4, -125, 3.0)
    s.view("compute", (-1.4, 0, 0.4), 5.4, -78, 4.2)
    s.view("bus", (-3.3, -0.75, 0.4), 3.6, -100, 1.7)
    s.lens, s.floor_grid, s.floor_z = 40.0, 0, 0.0
    return s


# ---------------------------------------------------------------------------
# 9. bars that race (or simply compare)
# ---------------------------------------------------------------------------

def compare(p, sec):
    """Horizontal bars, each with a label and its value. In `race` mode they all grow at the same speed,
    so the short one is done at once while the long one keeps going; in `grow` mode they rise together.
    A value written `lo-hi` draws a bar to `hi` with the span from `lo` in a lighter shade."""
    from scenes import Set
    s = Set(sec)
    items = [it.split(":") for it in _split(p.get("items"), "Multiply ten billion numbers:4:4 microseconds|"
                                                            "Fetch five gigabytes:625:over 600 microseconds")]
    mode = p.get("mode", "race")
    rows = []
    vmax = 0.0
    for it in items:
        lo, hi = (it[1].split("-") + [None])[:2]
        lo, hi = float(lo), float(hi) if hi else None
        vmax = max(vmax, hi or lo)
        rows.append((it[0], lo, hi, it[2] if len(it) > 2 else it[1]))
    width = 11.0
    n = len(rows)
    bars = []
    for k, (label, lo, hi, shown) in enumerate(rows):
        z = 0.9 + (n - 1 - k) * 1.7
        color = HUES[k % len(HUES)]
        text(f"label{k}", label, (-5.6, -0.3, z + 0.55), 0.34, align="LEFT")
        kit.box(f"track{k}", (-5.6 + width / 2, 0.05, z), (width, 0.3, 0.42), kit.mat("track", (0.05, 0.055, 0.065), roughness=0.8), bevel=0.04)
        segs = []
        for part, (v0, v1, strength) in enumerate(((0.0, lo, 1.6), (lo, hi, 0.5)) if hi else ((0.0, lo, 1.6),)):
            w = max(0.03, width * (v1 - v0) / vmax)
            bar = kit.box(f"bar{k}-{part}", (-5.6 + width * v0 / vmax + w / 2, -0.02, z), (w, 0.32, 0.44),
                          look.neon(f"bar{k}-{part}", color, strength), bevel=0.02)
            segs.append((bar, -5.6 + width * v0 / vmax, w))
        inside = (hi or lo) / vmax > 0.7
        dark = kit.mat("value-dark", (0.02, 0.02, 0.025), roughness=0.8)
        val = text(f"value{k}", shown, (-5.6 + width * (hi or lo) / vmax + (-0.25 if inside else 0.25), -0.35, z), 0.3,
                   dark if inside else None, align="RIGHT" if inside else "LEFT")
        bars.append((segs, val, hi or lo))
    s.pin("first", (-5.0, -0.2, 0.9 + (n - 1) * 1.7 + 0.5))
    s.pin("last", (-5.6 + width * bars[-1][2] / vmax, -0.2, 1.2))
    s.pin("end", (5.4, -0.2, 0.9))

    def run(t0, t1):
        a, b = f(t0), f(t1)
        for k, (segs, val, v) in enumerate(bars):
            done = a + round((b - a) * (v / vmax if mode == "race" else 1.0))
            done = max(done, a + 3)
            for bar, x_left, w in segs:
                bar.scale[0] = 0.001
                bar.location[0] = x_left
                bar.keyframe_insert("scale", frame=1)
                bar.keyframe_insert("location", frame=1)
                bar.keyframe_insert("scale", frame=a)
                bar.keyframe_insert("location", frame=a)
                bar.scale[0] = 1.0
                bar.location[0] = x_left + w / 2
                bar.keyframe_insert("scale", frame=done)
                bar.keyframe_insert("location", frame=done)
                if mode == "race":
                    kit._linear(bar)
            hidden_until(val, done)
    s.action("run", run, at=0.1, span=max(1.5, min(sec * 0.6, 6.0)))
    top = 0.9 + (n - 1) * 1.7
    s.view("wide", (0, 0, top / 2 + 0.7), 13.0 + n * 0.4, -90, top / 2 + 1.2)
    s.view("start", (-4.0, 0, top / 2 + 0.6), 6.5, -78, top / 2 + 1.3)
    s.lens, s.floor_grid, s.floor_z = 40.0, 0, 0.0
    return s


# ---------------------------------------------------------------------------
# 10. a number travelling a long wire
# ---------------------------------------------------------------------------

def wire_trip(p, sec):
    """A memory chip far away and a multiplier with a register beside it. A number fetched from memory
    crawls down a long wire that warms as it passes; a number from the register next door arrives at once."""
    from scenes import Set
    s = Set(sec)
    kit.box("memory", (-6.5, 0, 0.6), (2.0, 1.6, 1.2), kit.mat("dram", (0.06, 0.07, 0.09), metallic=0.4, roughness=0.45), bevel=0.05)
    kit.boxes("memory-rows", [placed((-6.5, -0.81, 0.25 + k * 0.14), (1.8, 0.02, 0.06)) for k in range(7)], kit.circuit())
    kit.box("mult", (5.4, 0, 0.45), (1.0, 1.0, 0.9), kit.mat("mult", (0.10, 0.10, 0.12), roughness=0.5), bevel=0.05)
    mult_glow = look.neon("mult-glow", WARM, 0.2)
    kit.box("mult-top", (5.4, 0, 0.92), (0.8, 0.8, 0.04), mult_glow, bevel=0)
    text("mult-x", "x", (5.4, -0.52, 0.5), 0.6)
    kit.box("register", (4.2, 0, 0.3), (0.5, 0.5, 0.6), kit.circuit(), bevel=0.03)
    wire_mat = look.neon("wire", (1.0, 0.42, 0.12), 0.0, base=(0.30, 0.12, 0.04))
    path = [(-5.5, 0, 0.5), (-3.5, 0, 0.5), (-3.0, 0, 2.2), (0.0, 0, 2.2), (0.6, 0, 0.5), (2.5, 0, 0.5), (3.0, 0, 1.4), (4.9, 0, 1.4), (4.9, 0, 0.9)]
    wire = polyline("wire", path, 0.05, wire_mat)
    polyline("short", [(4.45, 0, 0.45), (4.9, 0, 0.45)], 0.05, wire_mat)
    s.pin("memory", (-6.5, -0.9, 1.2))
    s.pin("multiplier", (5.4, -0.6, 1.0))
    s.pin("register", (4.2, -0.4, 0.6))
    s.pin("wire", (-1.5, -0.1, 2.3))
    bead_mat = look.neon("num", COOL, 9.0)
    pts = [Vector(q) for q in path]
    lengths = [0.0]
    for a_, b_ in zip(pts, pts[1:]):
        lengths.append(lengths[-1] + (b_ - a_).length)

    def along(t):
        d = t * lengths[-1]
        for k in range(len(pts) - 1):
            if d <= lengths[k + 1]:
                u = (d - lengths[k]) / max(1e-6, lengths[k + 1] - lengths[k])
                return pts[k].lerp(pts[k + 1], u)
        return pts[-1]

    def send(t0, t1):
        a, b = f(t0), f(t1)
        bead = kit.ico("num", tuple(pts[0]), 0.13, bead_mat, subdivisions=2, smooth=True)
        steps = 24
        for k in range(steps + 1):
            bead.location = along(k / steps)
            bead.keyframe_insert("location", frame=a + round((b - a) * k / steps))
        kit._linear(bead)
        hidden_until(bead, a)
        gone_at(bead, b, 2)
        key_glow(wire_mat, [(1, 0.0), (a, 0.0), ((a + b) // 2, 1.4), (b + 10, 0.6)])
        flash(mult_glow, [b], 8.0, 0.2, 4)

    def local(t0, t1):
        a = f(t0)
        bead = kit.ico("num-near", (4.45, 0, 0.45), 0.1, bead_mat, subdivisions=2, smooth=True)
        slide(bead, a, a + 4, (4.45, 0, 0.45), (4.9, 0, 0.45))
        hidden_until(bead, a)
        gone_at(bead, a + 4, 2)
        flash(mult_glow, [a + 4], 8.0, 0.2, 4)
    s.action("send", send, at=0.1, span=max(2.0, min(sec * 0.55, 6.0)))
    s.action("local", local, at=0.78, span=0.5)
    s.view("wide", (-0.6, 0, 1.1), 19.0, -92, 3.8)
    s.view("wire", (-1.5, 0, 1.6), 7.0, -70, 2.6)
    s.view("multiplier", (4.8, 0, 0.8), 4.5, -78, 2.0)
    s.lens, s.floor_grid, s.floor_z = 40.0, 1.0, 0.0
    return s


# ---------------------------------------------------------------------------
# 11. a high-bandwidth-memory stack taken apart
# ---------------------------------------------------------------------------

def hbm_stack(p, sec):
    """A memory stack beside a two-die GPU on a silicon interposer. The stack is a base logic die with
    eight DRAM dies on top, joined by microbumps and by through-silicon vias running straight down
    through every die; under the interposer's surface many short wires run to the GPU. `explode` lifts
    the dies apart, `signal` lights the vias and the wires."""
    from scenes import Set
    s = Set(sec)
    layers = max(4, min(16, int(p.get("layers", 8))))
    kit.box("interposer", (0.6, 0, 0.06), (10.0, 5.0, 0.12), kit.silicon(), bevel=0.01)
    kit.box("substrate", (0.6, 0, -0.12), (11.0, 6.0, 0.24), kit.pcb(), bevel=0.03)
    # the GPU: two dies and the joint between them
    for side in (-1, 1):
        kit.box(f"gpu{side}", (3.3 + side * 0.8, 0, 0.25), (1.5, 3.2, 0.26), kit.mat("gpu-die", (0.08, 0.09, 0.11), metallic=0.45, roughness=0.4), bevel=0.01)
    joint_mat = look.neon("joint", COOL, 1.5)
    kit.box("joint", (3.3, 0, 0.3), (0.08, 3.2, 0.2), joint_mat, bevel=0)
    # the hero stack
    sx, w, d = -1.4, 1.6, 1.4
    base = kit.box("base-die", (sx, -0.9, 0.2), (w, d, 0.14), kit.mat("logic-die", (0.16, 0.19, 0.25), metallic=0.5, roughness=0.4), bevel=0.005)
    dram_mat = kit.mat("dram-die", (0.24, 0.26, 0.31), metallic=0.5, roughness=0.4)
    drams, bumps = [], []
    z = 0.27
    for k in range(layers):
        z += 0.05
        bumps.append(kit.balls(f"bumps{k}", [(sx - w * 0.35 + i * w * 0.07, -0.9 - d * 0.3 + j * d * 0.12, z - 0.025)
                                            for i in range(11) for j in range(6)], 0.016, kit.steel()))
        drams.append(kit.box(f"dram{k}", (sx, -0.9, z + 0.04), (w, d, 0.08), dram_mat, bevel=0.004))
        z += 0.08
    top_z = z
    tsv_mat = look.neon("tsv", COOL, 0.3)
    tsv = kit.rods("tsv", [((sx - 0.3 + i * 0.12, -0.9 + j * 0.12, 0.14), (sx - 0.3 + i * 0.12, -0.9 + j * 0.12, top_z))
                           for i in range(6) for j in (-1, 0, 1)], 0.012, tsv_mat)
    # three more stacks for context
    for k, (x, y) in enumerate(((-1.4, 0.9), (-3.4, -0.9), (-3.4, 0.9))):
        _hbm(f"stack{k}", (x, y, 0.12), w=1.6, d=1.4, layers=layers)
    # the wires in the interposer, from the stack's base to the GPU edge
    wire_mat = look.neon("wires", WARM, 0.25)
    pairs = [((sx + w / 2, -0.9 - 0.6 + k * 0.04, 0.125), (3.3 - 1.55, -0.9 - 0.6 + k * 0.04, 0.125)) for k in range(30)]
    wires = kit.rods("wires", pairs, 0.008, wire_mat)
    s.pin("stack", (sx, -1.7, top_z + 0.1))
    s.pin("base", (sx + 0.7, -1.65, 0.2), base)
    s.pin("dram", (sx + 0.7, -1.65, top_z - 0.05), drams[-1])
    s.pin("tsv", (sx - 0.05, -1.05, (top_z + 0.14) / 2))
    s.pin("bumps", (sx + 0.6, -1.6, 0.33))
    s.pin("interposer", (-3.6, -2.55, 0.12))
    s.pin("wires", (0.9, -1.5, 0.14))
    s.pin("gpu", (3.3, -1.7, 0.4))
    s.pin("joint", (3.3, -1.0, 0.45))

    def explode(t0, t1):
        a, b = f(t0), f(t1)
        for k, (ob, bm) in enumerate(zip(drams, bumps)):
            for part in (ob, bm):
                kit.move(part, a + k, b + k, (0, 0, 0.12 * (k + 1)))
        tsv.keyframe_insert("scale", frame=a)
        tsv.scale = (1, 1, (top_z + 0.12 * layers - 0.14) / (top_z - 0.14))
        tsv.keyframe_insert("scale", frame=b + layers)
        tsv.location = (0, 0, 0.14 - 0.14 * tsv.scale[2])
        tsv.keyframe_insert("location", frame=b + layers)
        tsv.location = (0, 0, 0)
        tsv.keyframe_insert("location", frame=a)

    def signal(t0, t1):
        a = f(t0)
        keys, keys_w = [(1, 0.3), (a, 0.3)], [(1, 0.25), (a, 0.25)]
        for fr in range(a + 2, s.frames, 4):
            keys.append((fr, 6.0 if (fr // 4) % 2 else 2.0))
            keys_w.append((fr, 4.0 if (fr // 4) % 2 else 1.2))
        key_glow(tsv_mat, keys)
        key_glow(wire_mat, keys_w)
    s.action("explode", explode, at=0.2, span=1.8)
    s.action("signal", signal, at=0.45, span=0.5)
    s.view("wide", (0.3, 0, 0.6), 11.0, -108, 5.2)
    s.view("stack", (sx, -0.9, 1.0), 4.6, -112, 1.9)
    s.view("tsv", (sx, -0.9, 0.9), 2.8, -78, 1.25)
    s.view("wires", (0.6, -0.9, 0.2), 3.8, -96, 1.3)
    s.view("gpu", (3.3, 0, 0.3), 4.8, -66, 3.6)
    s.lens, s.floor_grid, s.floor_z = 40.0, 0, -0.24
    return s


# ---------------------------------------------------------------------------
# 12. batching and the KV cache
# ---------------------------------------------------------------------------

def batching(p, sec):
    """One fetch of the weights feeds many conversations at once: the weights flash, beams reach every
    conversation, and each gets its next token. In `single` mode only one conversation is served. In
    `cache` mode every conversation also keeps a growing column of notes, and the memory fills toward its
    limit."""
    from scenes import Set
    s = Set(sec)
    mode = p.get("mode", "batch")
    users = 1 if mode == "single" else max(2, min(12, int(p.get("users", 8))))
    w_mat = look.neon("weights", COOL, 0.6, base=(0.04, 0.05, 0.07))
    weights = kit.group("weights", [kit.box(f"w{k}", (0, 0, 4.4 + k * 0.2), (3.2, 2.0, 0.14), w_mat, bevel=0.02) for k in range(5)])
    kit.box("hbm", (-3.6, 0, 4.8), (1.4, 1.4, 1.2), kit.circuit(), bevel=0.04)
    lanes = []
    for k in range(users):
        ang = math.radians(90 + (k - (users - 1) / 2) * (110 / max(1, users - 1) if users > 1 else 0))
        cx, cy = 7.0 * math.cos(ang), 7.0 * math.sin(ang) - 1.0
        panel = kit.box(f"user{k}", (cx, cy, 1.2), (1.6, 0.12, 1.2), kit.mat("user-panel", (0.03, 0.035, 0.045), roughness=0.7), bevel=0.06)
        panel.rotation_euler[2] = ang + math.pi / 2
        lanes.append((panel, Vector((cx, cy, 1.2)), ang))
    s.pin("weights", (1.8, -1.1, 5.1), weights)
    s.pin("memory", (-3.6, -0.8, 5.5))
    s.pin("user", tuple(lanes[0][1] + Vector((0, -0.2, 0.8))))
    s.pin("cache", tuple(lanes[-1][1] + Vector((0, -0.2, 2.0))))
    s.pin("capacity", (8.6, -0.4, 4.6))
    cap_frame = cap_fill = None
    if mode == "cache":
        kit.box("cap-frame", (8.6, 0.0, 2.6), (0.7, 0.7, 4.2), haze("cap-frame", (0.7, 0.7, 0.8), 0.15), bevel=0.02)
        kit.box("cap-limit", (8.6, 0.0, 4.6), (0.9, 0.9, 0.04), look.neon("cap-limit", WARM, 4.0), bevel=0)
        cap_fill = kit.box("cap-fill", (8.6, 0.0, 0.5), (0.6, 0.6, 4.0), look.neon("cap-fill", COOL, 1.2), bevel=0.02)

    def share(t0, t1):
        a, b = f(t0), f(t1)
        cycles = max(2, int(p.get("cycles", 6)))
        each = max(10, (b - a) // cycles)
        tok_mat = look.neon("tok", WARM, 3.0)
        cache_mat = look.neon("cache", COOL, 1.6)
        fetch_mat = look.neon("fetch", COOL, 9.0)
        for c in range(cycles):
            ca = a + c * each
            bead = kit.ico(f"fetch{c}", (-2.8, 0, 4.8), 0.16, fetch_mat, subdivisions=2, smooth=True)
            slide(bead, ca, ca + 5, (-2.8, 0, 4.8), (-1.5, 0, 4.8))
            hidden_until(bead, max(2, ca))
            gone_at(bead, ca + 5, 2)
            key_glow(w_mat, [(ca + 4, 0.6), (ca + 6, 5.0), (ca + 12, 0.6)])
            for k, (panel, at, ang) in enumerate(lanes):
                m = haze(f"beam{c}-{k}", WARM, 0.0)
                kit.rod(f"beam{c}-{k}", (0, 0, 4.4), tuple(at + Vector((0, 0, 0.7))), 0.025, m)
                key_glow(m, [(1, 0.0), (ca + 6, 0.0), (ca + 8, 1.4), (ca + 14, 0.0)])
                side = Vector((math.cos(ang + math.pi / 2), math.sin(ang + math.pi / 2), 0))
                pos = at + side * (-0.6 + (c % 6) * 0.24) + Vector((0, 0, 0.25 - (c // 6) * 0.3)) - Vector((math.cos(ang), math.sin(ang), 0)) * 0.1
                t = kit.box(f"t{c}-{k}", tuple(pos), (0.18, 0.05, 0.18), tok_mat, bevel=0.01)
                t.rotation_euler[2] = ang + math.pi / 2
                hidden_until(t, ca + 9)
                if mode == "cache":
                    ck = kit.box(f"kv{c}-{k}", tuple(at + Vector((0, 0, 1.0 + c * 0.22)) + side * 0.95), (0.3, 0.3, 0.18), cache_mat, bevel=0.01)
                    hidden_until(ck, ca + 10)
        if mode == "cache":
            cap_fill.scale[2] = 0.05
            cap_fill.location[2] = 0.6
            cap_fill.keyframe_insert("scale", frame=a)
            cap_fill.keyframe_insert("location", frame=a)
            cap_fill.scale[2] = 1.0
            cap_fill.location[2] = 2.55
            cap_fill.keyframe_insert("scale", frame=b)
            cap_fill.keyframe_insert("location", frame=b)
    s.action("share", share, at=0.06, span=max(3.0, sec * 0.85))
    s.view("wide", (0, 2.0, 2.6), 18.0, -90, 9.0)
    s.view("weights", (-1.0, 0, 4.6), 7.0, -78, 6.2)
    s.view("users", (0, 5.0, 1.4), 9.5, -90, 4.2)
    if mode == "cache":
        s.view("cache", (4.0, 3.5, 2.2), 8.5, -110, 4.4)
    s.lens, s.floor_grid, s.floor_z = 40.0, 1.0, 0.0
    return s


# ---------------------------------------------------------------------------
# 13. number widths
# ---------------------------------------------------------------------------

def bit_width(p, sec):
    """One weight written with sixteen bits shrinks to four; below, a lane of fixed width carries numbers
    toward a chip, and at four bits each it carries four where it carried one."""
    from scenes import Set
    s = Set(sec)
    bits16 = "0011111101010000"   # 0.8125 in bfloat16
    cells = []
    for k, b in enumerate(bits16):
        m = look.neon(f"bit{k}", WARM if k < 4 else COOL, 1.4 if b == "1" else 0.35)
        ob = kit.box(f"bit{k}", (-3.75 + k * 0.5, 0, 3.2), (0.42, 0.3, 0.6), m, bevel=0.04)
        lab = text(f"bit-t{k}", b, (-3.75 + k * 0.5, -0.17, 3.2), 0.3)
        lab.parent = ob
        lab.location = (0, -0.17, 0)
        cells.append(ob)
    caption = text("caption16", "16 bits", (0, -0.05, 4.0), 0.36)
    caption4 = text("caption4", "4 bits", (0, -0.05, 4.0), 0.36)
    for lane, (z, n, w) in enumerate(((1.4, 4, 2.0), (0.3, 16, 0.5))):
        kit.box(f"lane{lane}", (0, 0.1, z), (12.0, 0.3, 0.7), kit.mat("lane", (0.05, 0.055, 0.065), roughness=0.8), bevel=0.03)
        text(f"lane-t{lane}", "16-bit numbers" if lane == 0 else "4-bit numbers", (-6.3, -0.05, z), 0.26, align="RIGHT")
    kit.box("chip", (6.8, 0, 0.85), (1.2, 1.0, 2.0), kit.mat("chip", (0.07, 0.08, 0.1), metallic=0.4, roughness=0.45), bevel=0.05)
    s.pin("number", (-3.0, -0.3, 3.6))
    s.pin("wide", (-2.0, -0.3, 1.8))
    s.pin("narrow", (-2.0, -0.3, 0.7))
    s.pin("chip", (6.8, -0.6, 1.9))

    def shrink(t0, t1):
        a, b = f(t0), f(t1)
        gone_at(caption, a, 4)
        hidden_until(caption4, b)
        for k, ob in enumerate(cells):
            if k >= 4:
                gone_at(ob, a + (15 - k), 6)
            else:
                kit.move(ob, a + 8, b, (3.0, 0, 0))

    def flow(t0, t1):
        a = f(t0)
        for lane, (z, n, w, color) in enumerate(((1.4, 1, 2.0, WARM), (0.3, 4, 0.5, COOL))):
            m = look.neon(f"pack{lane}", color, 2.0)
            period = 2.2 * FPS
            for rep in range(6):
                for k in range(n):
                    start = a + round(rep * period / 2)
                    ob = kit.box(f"pack{lane}-{rep}-{k}", (-5.8 + k * (w + 0.05), -0.05, z), (w * 0.92, 0.32, 0.5), m, bevel=0.02)
                    slide(ob, start, start + round(period), (-5.8 + w / 2 + k * (w + 0.05), -0.05, z), (6.0 + k * (w + 0.05), -0.05, z))
                    kit._linear(ob)
                    hidden_until(ob, max(2, start))
                    gone_at(ob, start + round(period), 2)
    s.action("shrink", shrink, at=0.12, span=1.6)
    s.action("flow", flow, at=0.45, span=1.0)
    s.view("wide", (-0.6, 0, 2.1), 16.5, -90, 3.2)
    s.view("number", (0, 0, 3.2), 7.5, -84, 3.6)
    s.view("lanes", (0, 0, 0.9), 8.5, -80, 2.0)
    s.lens, s.floor_grid, s.floor_z = 40.0, 0, -0.3
    return s


# ---------------------------------------------------------------------------
# 14. a rack of 72 GPUs
# ---------------------------------------------------------------------------

def gpu_rack(p, sec):
    """A rack-scale system laid out like NVIDIA's GB200 NVL72: power shelves top and bottom, ten compute
    trays above nine NVLink switch trays above eight more compute trays (18 trays of four GPUs), a spine
    of copper cables down the back, and liquid manifolds feeding a cold plate on every processor.
    `pull` slides one compute tray out, `link` lights the spine, `slice` lights the 72 GPUs in groups, and
    `cool` runs the coolant."""
    from scenes import Set
    s = Set(sec)
    W, D, U = 2.4, 3.0, 0.22
    layout = ["power"] * 4 + ["compute"] * 8 + ["switch"] * 9 + ["compute"] * 10 + ["power"] * 4
    z0 = 0.35
    frame_mat = kit.mat("rack-frame", (0.05, 0.055, 0.06), metallic=0.4, roughness=0.5)
    H = len(layout) * U
    for sx in (-1, 1):
        for sy in (-1, 1):
            kit.box(f"post{sx}{sy}", (sx * (W / 2 + 0.06), sy * (D / 2 - 0.05), z0 + H / 2), (0.1, 0.1, H + 0.3), frame_mat, bevel=0.01)
    kit.box("rack-top", (0, 0, z0 + H + 0.18), (W + 0.25, D, 0.08), frame_mat, bevel=0.01)
    kit.box("rack-base", (0, 0, z0 - 0.18), (W + 0.25, D, 0.12), frame_mat, bevel=0.01)
    tray_mat = kit.mat("tray", (0.16, 0.165, 0.17), metallic=0.5, roughness=0.45)
    switch_mat = kit.mat("switch", (0.09, 0.10, 0.11), metallic=0.4, roughness=0.5)
    power_mat = kit.mat("power", (0.12, 0.12, 0.125), metallic=0.4, roughness=0.5)
    gpu_mats = [look.neon(f"gpu-slice{k}", HUES[k % len(HUES)], 0.15) for k in range(6)]
    port_mat = look.neon("ports", (0.3, 1.0, 0.5), 0.8)
    trays, gpu_squares, ports, grilles = [], {k: [] for k in range(6)}, [], []
    hero = None
    ci = 0
    for k, kind in enumerate(layout):
        z = z0 + (k + 0.5) * U
        if kind == "compute":
            ob = kit.box(f"tray{k}", (0, 0, z), (W, D - 0.2, U * 0.9), tray_mat, bevel=0.01)
            trays.append(ob)
            for g in range(4):
                gpu_squares[(ci * 4 + g) // 12].append(placed((-0.75 + g * 0.5, -(D - 0.2) / 2 - 0.01, z), (0.3, 0.02, U * 0.45)))
            if ci == 13:
                hero = (ob, z)
            ci += 1
        elif kind == "switch":
            kit.box(f"switch{k}", (0, 0, z), (W, D - 0.2, U * 0.9), switch_mat, bevel=0.01)
            for i in range(16):
                ports.append(placed((-1.0 + i * 0.133, -(D - 0.2) / 2 - 0.01, z), (0.09, 0.02, U * 0.35)))
        else:
            kit.box(f"power{k}", (0, 0, z), (W, D - 0.2, U * 0.9), power_mat, bevel=0.01)
            for i in range(6):
                grilles.append(placed((-0.95 + i * 0.38, -(D - 0.2) / 2 - 0.01, z), (0.3, 0.02, U * 0.6)))
    for k, mats in gpu_squares.items():
        kit.boxes(f"gpus{k}", mats, gpu_mats[k])
    kit.boxes("ports", ports, port_mat)
    kit.boxes("grilles", grilles, kit.slate())
    # the spine: copper cable bundles down the back, from every tray to the switch trays
    spine_mat = look.neon("spine", (1.0, 0.42, 0.12), 0.12, base=(0.30, 0.12, 0.04))
    cables = []
    rng = random.Random(8)
    sw_lo = z0 + 8.5 * U
    sw_hi = z0 + 16.5 * U
    for k, kind in enumerate(layout):
        if kind != "compute":
            continue
        z = z0 + (k + 0.5) * U
        for c in range(12):
            x = -0.95 + c * 0.17 + rng.uniform(-0.03, 0.03)
            zt = rng.uniform(sw_lo, sw_hi)
            cables.append(((x, D / 2 - 0.05, z), (x, D / 2 + 0.08 + 0.01 * (c % 4), (z + zt) / 2)))
            cables.append(((x, D / 2 + 0.08 + 0.01 * (c % 4), (z + zt) / 2), (x, D / 2 - 0.05, zt)))
    spine = kit.rods("spine", cables, 0.008, spine_mat)
    # manifolds: supply (cool) and return (warm) down the back corners, a hose to every compute tray
    supply, ret = look.neon("supply", COOL, 0.6), look.neon("return", WARM, 0.6)
    kit.cyl("manifold-in", (-W / 2 + 0.12, D / 2 + 0.25, z0 + H / 2), 0.07, H, supply, verts=16)
    kit.cyl("manifold-out", (W / 2 - 0.12, D / 2 + 0.25, z0 + H / 2), 0.07, H, ret, verts=16)
    hoses_in, hoses_out = [], []
    for k, kind in enumerate(layout):
        if kind == "compute":
            z = z0 + (k + 0.5) * U
            hoses_in.append(((-W / 2 + 0.12, D / 2 + 0.25, z), (-W / 2 + 0.3, D / 2 - 0.05, z)))
            hoses_out.append(((W / 2 - 0.12, D / 2 + 0.25, z), (W / 2 - 0.3, D / 2 - 0.05, z)))
    kit.rods("hoses-in", hoses_in, 0.025, supply)
    kit.rods("hoses-out", hoses_out, 0.025, ret)
    # the hero tray's insides, revealed when it slides out: two boards, each with two GPUs and one CPU
    tray, tz = hero
    inside = []
    plate_mat = kit.mat("cold-plate", (0.62, 0.64, 0.68), metallic=0.6, roughness=0.3)
    for b, bx in enumerate((-0.58, 0.58)):
        inside.append(kit.box(f"board{b}", (bx, 0, tz + U * 0.48), (1.05, D - 0.4, 0.02), kit.pcb(), bevel=0))
        for g, gy in enumerate((-0.75, 0.15)):
            inside.append(kit.box(f"gpu{b}{g}", (bx, gy, tz + U * 0.52), (0.62, 0.62, 0.04), plate_mat, bevel=0.01))
        inside.append(kit.box(f"cpu{b}", (bx, 0.95, tz + U * 0.52), (0.42, 0.42, 0.04), plate_mat, bevel=0.01))
        inside.append(polyline(f"tube-in{b}", [(bx - 0.2, D / 2 - 0.25, tz + U * 0.6), (bx - 0.2, 0.15, tz + U * 0.6), (bx - 0.2, -0.75, tz + U * 0.6)], 0.022, supply))
        inside.append(polyline(f"tube-out{b}", [(bx + 0.2, -0.75, tz + U * 0.62), (bx + 0.2, 0.95, tz + U * 0.62), (bx + 0.2, D / 2 - 0.25, tz + U * 0.62)], 0.022, ret))
    lid = kit.box("tray-lid", (0, 0, tz + U * 0.47), (W, D - 0.2, 0.01), tray_mat, bevel=0)
    tray_parts = kit.group("hero-tray", [tray, lid] + inside)
    s.pin("compute", (W / 2, -(D / 2), z0 + 27.5 * U))
    s.pin("switch", (W / 2, -(D / 2), z0 + 16.5 * U))
    s.pin("power", (W / 2, -(D / 2), z0 + 1.5 * U))
    s.pin("spine", (0.4, D / 2 + 0.2, z0 + H * 0.5))
    s.pin("manifold", (W / 2 - 0.12, D / 2 + 0.3, z0 + H * 0.3))
    s.pin("tray", (W / 2 - 0.2, -(D / 2) - 0.1, tz), tray_parts)
    s.pin("gpu", (-0.58, -0.75, tz + U * 0.6), tray_parts)
    s.pin("coldplate", (0.58, 0.15, tz + U * 0.6), tray_parts)

    def pull(t0, t1):
        a, b = f(t0), f(t1)
        kit.move(tray_parts, a, b, (0, -2.4, 0))
        gone_at(lid, a + 2, 8)

    def link(t0, t1):
        a = f(t0)
        keys = [(1, 0.0), (a, 0.0)]
        for fr in range(a + 2, s.frames, 3):
            keys.append((fr, rng.uniform(0.15, 0.6)))
        key_glow(spine_mat, keys)
        flash(port_mat, list(range(a, s.frames, 5)), 3.0, 0.8, 1)

    def slice_(t0, t1):
        a, b = f(t0), f(t1)
        each = max(2, (b - a) // 6)
        for k, m in enumerate(gpu_mats):
            key_glow(m, [(1, 0.15), (a + k * each, 0.15), (a + k * each + 4, 6.0)])

    def cool(t0, t1):
        a = f(t0)
        for m, hi in ((supply, 3.0), (ret, 3.0)):
            keys = [(1, 0.6), (a, 0.6)]
            for fr in range(a + 3, s.frames, 6):
                keys += [(fr, hi), (fr + 3, hi * 0.5)]
            key_glow(m, keys)
    s.action("pull", pull, at=0.25, span=1.6)
    s.action("link", link, at=0.1, span=0.5)
    s.action("slice", slice_, at=0.5, span=2.0)
    s.action("cool", cool, at=0.05, span=0.5)
    zc = z0 + H / 2
    s.view("wide", (0, 0, zc), 19.5, -118, zc + 2.4)
    s.view("front", (0, 0, zc), 15.0, -92, zc + 0.6)
    s.view("back", (0, 0.5, zc), 9.0, 62, zc + 1.4)
    s.view("tray", (0, -2.0, tz), 5.0, -62, tz + 2.6)
    s.lens, s.floor_grid, s.floor_z = 40.0, 1.0, 0.0
    return s


# ---------------------------------------------------------------------------
# 15. where the heat goes
# ---------------------------------------------------------------------------

def heat_loop(p, sec):
    """A rack hands its heat to a coolant loop; a coolant distribution unit passes it to the facility
    water, which runs to a mechanical-draft cooling tower; there a little of the water evaporates and the
    vapour carries the heat into the sky."""
    from scenes import Set
    s = Set(sec)
    kit.box("rack", (-7.0, 0, 3.0), (2.4, 3.0, 6.0), kit.mat("rack-body", (0.08, 0.085, 0.09), metallic=0.4, roughness=0.5), bevel=0.04)
    kit.boxes("rack-fronts", [placed((-7.0, -1.52, 0.4 + k * 0.22), (2.2, 0.02, 0.14)) for k in range(25)], kit.mat("rack-front", (0.18, 0.19, 0.2), metallic=0.5, roughness=0.4))
    kit.box("cdu", (-2.0, 0, 1.2), (1.8, 1.6, 2.4), kit.mid(), bevel=0.05)
    supply, ret = look.neon("loop-cool", COOL, 1.0), look.neon("loop-warm", WARM, 1.0)
    pipes = [
        polyline("rack-in", [(-2.9, -0.3, 1.0), (-5.8, -0.3, 1.0)], 0.09, supply),
        polyline("rack-out", [(-5.8, 0.3, 1.6), (-2.9, 0.3, 1.6)], 0.09, ret),
        polyline("tower-out", [(-1.1, 0.3, 1.6), (3.2, 0.3, 1.6), (3.2, 0.3, 3.4), (4.0, 0.3, 3.4)], 0.11, ret),
        polyline("tower-in", [(4.0, -0.3, 0.5), (-1.1, -0.3, 0.5)], 0.11, supply),
    ]
    # the tower: a box with louvred sides, a fan deck and a fan stack
    tw = (6.5, 0, 0)
    kit.box("tower", (tw[0], 0, 2.0), (4.4, 4.4, 4.0), kit.mat("tower-body", (0.42, 0.44, 0.46), roughness=0.6), bevel=0.05)
    kit.boxes("louvres", [placed((tw[0], -2.22, 0.3 + k * 0.22), (4.2, 0.06, 0.08)) for k in range(7)], kit.slate())
    kit.cyl("fan-stack", (tw[0], 0, 4.6), 1.5, 1.2, kit.mat("fan-stack", (0.36, 0.38, 0.40), roughness=0.6), verts=48)
    fan = kit.group("fan", [kit.box(f"blade{k}", (0, 0, 0), (2.6, 0.3, 0.03), kit.slate(), bevel=0.01) for k in range(3)])
    for k, ch in enumerate(fan.children):
        ch.rotation_euler[2] = k * math.pi / 3
    fan.location = (tw[0], 0, 4.9)
    kit.spin(fan, s.frames, max(1, s.seconds * 2.5))
    rng = random.Random(12)
    vap_mat = haze("vapour", (0.85, 0.88, 0.95), 0.0)
    puffs = []
    for k in range(40):
        ob = kit.ico(f"puff{k}", (tw[0] + rng.uniform(-0.9, 0.9), rng.uniform(-0.9, 0.9), 5.3), rng.uniform(0.35, 0.7), vap_mat, subdivisions=2, smooth=True)
        puffs.append(ob)
    drops = kit.boxes("rain", [placed((tw[0] + rng.uniform(-1.8, 1.8), -2.3, rng.uniform(0.3, 1.8)), (0.02, 0.02, 0.18)) for _ in range(60)],
                      look.neon("rain", COOL, 0.8))
    s.pin("rack", (-6.0, -1.6, 5.5))
    s.pin("cdu", (-1.2, -0.9, 2.3))
    s.pin("tower", (8.5, -2.3, 3.6))
    s.pin("plume", (tw[0] + 0.6, -0.6, 7.0))
    s.pin("pipes", (1.0, -0.4, 0.6))

    def flow(t0, t1):
        a = f(t0)
        for m in (supply, ret):
            keys = [(1, 1.0), (a, 1.0)]
            for fr in range(a + 2, s.frames, 8):
                keys += [(fr, 4.0), (fr + 4, 1.5)]
            key_glow(m, keys)

    def evaporate(t0, t1):
        a = f(t0)
        key_glow(vap_mat, [(1, 0.0), (a, 0.0), (a + 20, 0.35)])
        cycle = 3 * FPS
        for k, ob in enumerate(puffs):
            start = a + (k * cycle) // len(puffs)
            x, y, z = ob.location
            for rep in range(0, s.frames // cycle + 2):
                f0 = start + rep * cycle
                ob.location = (x, y, 5.3)
                ob.scale = (0.4, 0.4, 0.4)
                ob.keyframe_insert("location", frame=f0)
                ob.keyframe_insert("scale", frame=f0)
                ob.location = (x + rng.uniform(0.5, 1.5), y + rng.uniform(-0.4, 0.4), 9.5)
                ob.scale = (1.6, 1.6, 1.6)
                ob.keyframe_insert("location", frame=f0 + cycle - 1)
                ob.keyframe_insert("scale", frame=f0 + cycle - 1)
            hidden_until(ob, max(2, start))
        drops.keyframe_insert("location", frame=a)
        drops.location = (0, 0, -0.25)
        drops.keyframe_insert("location", frame=a + 6)
        fc = drops.animation_data.action.fcurves
        for c in fc:
            c.modifiers.new("CYCLES")
    s.action("flow", flow, at=0.05, span=0.5)
    s.action("evaporate", evaporate, at=0.25, span=1.0)
    s.view("wide", (0, 0, 3.0), 23.0, -100, 8.0)
    s.view("rack", (-5.0, 0, 2.5), 8.5, -66, 4.0)
    s.view("tower", (6.5, 0, 4.5), 11.0, -112, 5.5)
    s.view("pipes", (-3.5, 0, 1.2), 5.5, -95, 2.3)
    s.lens, s.floor_grid, s.floor_z = 40.0, 1.0, 0.0
    return s


SCENES = {
    "token-stream": token_stream, "fiber-trip": fiber_trip, "tokenizer": tokenizer, "embedding-space": embedding_space,
    "model-layers": model_layers, "experts": experts, "next-token": next_token, "accelerator": accelerator,
    "compare": compare, "wire-trip": wire_trip, "hbm-stack": hbm_stack, "batching": batching, "bit-width": bit_width,
    "gpu-rack": gpu_rack, "heat-loop": heat_loop,
}
