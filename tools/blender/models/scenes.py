"""Parametric scenes: what a storyboard can ask for without anyone writing Blender code.

A scene is a function `(params, seconds) -> Set`. It builds its objects in the dark world
`look.open_set()` prepared and tells the storyboard builder three things about itself:

  views    named camera set-ups (target, radius, azimuth, height). The builder cuts between
           them inside one sentence; `at:<anchor>` is always available as a close-up.
  anchors  named points a tag can name. They are empties parented to the part they belong
           to, created while everything is still at rest, so a tag follows a part that an
           action later moves.
  actions  named moves (`open`, `grow`, `run`, ...) taking (start, end) in seconds. The
           builder runs each one once: when the storyboard says, or at its default time.

`workflow/scenes.json` describes the same catalog as data for the planner and the
validator; `python/test_scene_catalog.py` builds every scene and fails when the two differ.
"""
import math
import random

import bpy
from mathutils import Vector

import hardware
import kit
import look
import sets
from kit import FPS, placed


def f(seconds):
    return max(1, round(seconds * FPS))


class Set:
    def __init__(self, seconds):
        self.seconds = seconds
        self.frames = f(seconds)
        self.views = {}
        self.pins = {}
        self.holds = {}        # anchor -> the objects a close-up on it has to keep whole in frame
        self.actions = {}      # name -> (fn(t0, t1), default start fraction, default span seconds)
        self.sequence = []     # default order of views
        self.lens = 50.0
        self.floor_grid = 1.0
        self.floor_z = 0.0
        self.gain = 1.0

    def view(self, name, target, radius, azimuth, height):
        self.views[name] = {"target": tuple(target), "radius": radius, "azimuth": azimuth, "height": height}
        if name not in self.sequence:
            self.sequence.append(name)

    def pin(self, name, xyz, follow=None, hold=None):
        """An anchor labels and close-ups aim at. `hold` lists what a close-up on it must keep
        whole (a sentence, a title, a building); without it the close-up keeps its fixed distance."""
        e = kit._link(bpy.data.objects.new(f"pin-{name}", None))
        if follow is not None:
            bpy.context.view_layer.update()
            e.parent = follow
            e.location = Vector(xyz) - follow.matrix_world.translation
        else:
            e.location = xyz
        self.pins[name] = e
        if hold:
            self.holds[name] = list(hold)
        return e

    def action(self, name, fn, at=0.15, span=2.0):
        self.actions[name] = (fn, at, span)


def grow(ob, base_z, height, f0, f1):
    """Raise a bar from its base: scale and position keyed together."""
    ob.scale[2] = 0.001
    ob.location[2] = base_z
    ob.keyframe_insert("scale", frame=f0)
    ob.keyframe_insert("location", frame=f0)
    ob.scale[2] = 1.0
    ob.location[2] = base_z + height / 2
    ob.keyframe_insert("scale", frame=f1)
    ob.keyframe_insert("location", frame=f1)


def _jackets():
    return [kit.slate(), kit.mid(), kit.epoxy(), kit.mat("kit-denim", (0.10, 0.14, 0.22), roughness=0.8),
            kit.mat("kit-olive", (0.16, 0.17, 0.10), roughness=0.8), kit.mat("kit-rust", (0.24, 0.10, 0.07), roughness=0.8)]


def _heights(values, top):
    """Normalise numbers to bar heights; a non-positive or missing list becomes a doubling curve."""
    values = [float(v) for v in values] if values else [2 ** k for k in range(10)]
    peak = max(values) or 1.0
    return [max(0.04, top * v / peak) for v in values]


# ---------------------------------------------------------------------------
# Hardware
# ---------------------------------------------------------------------------

def chip_teardown(p, sec):
    """A chip package that opens: quad flat pack, ball grid array, or a stacked AI package."""
    s = Set(sec)
    package = p.get("package", "qfp")
    text = p.get("text", "")
    if package == "qfp":
        chip = hardware.qfp_chip("chip", size=3.2, leads_per_side=24, text=text, seed=int(p.get("seed", 4)))
        top = chip["top"]
        s.pin("package", (1.25, -1.5, top), chip["lid"])
        s.pin("die", (0.3, -0.4, top - 0.03), chip["die"])
        s.pin("pins", (-1.2, -1.9, 0.08))

        def open_(t0, t1):
            span = t1 - t0
            kit.move(chip["lid"], f(t0), f(t0 + span * 0.7), (0, 0, 2.3))
            kit.move(chip["wires"], f(t0 + span * 0.4), f(t1), (0, 0, 0.55))
            kit.move(chip["die"], f(t0 + span * 0.4), f(t1), (0, 0, 0.55))
        s.view("wide", (0, 0, 1.15), 12.2, -107, 6.8)
        s.view("die", (0, 0, top + 0.55), 6.6, -72, top + 3.6)
        s.view("pins", (-0.9, -1.5, 0.3), 6.2, -128, 2.6)
        s.floor_grid = 0.8
    elif package == "bga":
        chip = hardware.bga_chip("chip", size=3.6, text=text)
        top = chip["top"]
        s.pin("lid", (1.2, -1.2, top), chip["lid"])
        s.pin("die", (0.3, -0.3, 0.42), chip["die"])
        s.pin("balls", (-1.6, -1.8, 0.06))

        def open_(t0, t1):
            kit.move(chip["lid"], f(t0), f(t1), (0, 0, 2.2))
        s.view("wide", (0, 0, 1.0), 12.5, -107, 6.6)
        s.view("die", (0, 0, 0.6), 6.2, -74, 4.0)
        s.view("balls", (-1.2, -1.4, 0.15), 6.0, -128, 1.6)
        s.floor_grid = 0.9
    else:
        pkg = hardware.ai_package("pkg")
        top = pkg["top"]
        mx, _ = pkg["memory_xy"]
        s.pin("lid", (1.4, -1.5, top), pkg["lid"])
        s.pin("logic", (0.0, -0.9, 0.38))
        s.pin("memory", (mx, -0.9, 0.30), pkg["memory"][-1])
        s.pin("interposer", (-1.55, -1.3, 0.30))

        def open_(t0, t1):
            span = t1 - t0
            kit.move(pkg["lid"], f(t0), f(t0 + span * 0.55), (0, 0, 2.6))
            for k, layer in enumerate(pkg["memory"]):
                kit.move(layer, f(t0 + span * 0.45 + k * 0.2), f(t1 + k * 0.2), (0, 0, 0.28 + k * 0.30))
        s.view("wide", (0, 0, 1.6), 13.6, -108, 7.5)
        s.view("memory", (mx, 0, 1.1), 7.0, -70, 4.4)
        s.view("logic", (0, -0.4, 0.5), 6.4, -122, 3.4)
    s.action("open", open_, at=0.14, span=3.2)
    return s


def graphics_card(p, sec):
    """A graphics card whose cooler lifts off to show the processor underneath."""
    s = Set(sec)
    card = hardware.graphics_card(chip_text=p.get("text", "GPU"))
    kit.spin(card["rotor"], s.frames, sec * 0.9)
    gx, gy, gz = card["gpu_xyz"]
    s.pin("cooler", (1.2, -1.5, 1.05), card["heatsink"])
    s.pin("gpu", (gx, gy, gz + 0.1))
    s.pin("connector", (-1.1, -2.55, 0.34))

    def open_(t0, t1):
        span = t1 - t0
        kit.move(card["fan"], f(t0), f(t0 + span * 0.75), (0, 0, 2.7))
        kit.move(card["heatsink"], f(t0 + span * 0.25), f(t1), (0, 0, 1.35))
    s.action("open", open_, at=0.18, span=3.0)
    s.view("wide", (0, -0.3, 1.5), 16.0, -108, 8.8)
    s.view("gpu", (gx, gy, gz), 7.2, -78, gz + 4.2)
    s.view("connector", (-1.0, -2.2, 0.3), 7.5, -112, 2.6)
    s.floor_grid = 1.2
    return s


def wafer(p, sec):
    """A silicon wafer on its chuck; one die lifts out of the grid."""
    s = Set(sec)
    kit.cyl("chuck", (0, 0, -0.14), 4.1, 0.28, kit.slate(), verts=96)
    w = hardware.wafer()
    hx, hy = w["hero_xy"]
    s.pin("wafer", (-2.6, -1.6, 0.08))
    s.pin("die", (hx, hy, 0.08), w["hero"])
    s.action("lift", lambda t0, t1: kit.move(w["hero"], f(t0), f(t1), (0, 0, 1.25)), at=0.25, span=3.0)
    s.view("wide", (0, 0, 0.5), 14.0, -110, 8.4)
    s.view("die", (hx, hy, 0.9), 6.0, -78, 4.2)
    return s


def cores_compare(p, sec):
    """Two processors side by side: a few big cores taking turns, many small ones at once."""
    s = Set(sec)
    F = s.frames
    for x, tag in ((-2.9, "few"), (2.9, "many")):
        kit.box(f"{tag}-substrate", (x, 0, 0.08), (4.6, 4.6, 0.16), kit.pcb(), bevel=0.03)
        kit.box(f"{tag}-die", (x, 0, 0.21), (4.0, 4.0, 0.10), kit.silicon(), bevel=0.01)
    step = F / 4
    for k, (cx, cy) in enumerate(((-1, 1), (1, 1), (-1, -1), (1, -1))):
        m = kit.glow(f"few-core{k}", 0.05)
        kit.box(f"few-core{k}", (-2.9 + cx * 0.95, cy * 0.95, 0.30), (1.6, 1.6, 0.09), m, bevel=0.03)
        kit.pulse(m, [(1, 0.05), (max(1, round(k * step)), 0.05), (round(k * step) + 6, 4.0),
                      (round((k + 1) * step) - 6, 4.0), (round((k + 1) * step), 0.6)])
    rows, cols, cell = 16, 16, 3.7 / 16
    for r in range(rows):
        m = kit.glow(f"many-row{r}", 0.05)
        cells = [placed((2.9 - 1.85 + (c + 0.5) * cell, -1.85 + (r + 0.5) * cell, 0.29),
                        (cell * 0.6, cell * 0.6, 0.07)) for c in range(cols)]
        kit.boxes(f"many-row{r}", cells, m)
        keys = [(1, 0.05)]
        for k in range(4):
            t0 = round(k * step) + 4 + r
            keys += [(max(2, t0 - 3), 0.5 if k else 0.05), (t0, 4.5), (t0 + 14, 4.5), (t0 + 26, 0.5)]
        kit.pulse(m, keys)
    s.pin("few", (-2.9, 2.0, 0.3))
    s.pin("many", (2.9, 2.0, 0.3))
    s.view("wide", (0, -0.2, 0.9), 14.5, -92, 9.3)
    s.view("few", (-2.9, 0, 0.3), 8.0, -76, 5.6)
    s.view("many", (2.9, 0, 0.3), 8.0, -104, 5.6)
    s.floor_grid = 1.1
    return s


def server_racks(p, sec):
    """A row of server racks; one drawer slides out to show what is inside."""
    s = Set(sec)
    count = max(1, min(5, int(p.get("count", 3))))
    pull = min(count - 1, int(p.get("pull", count // 2)))
    drawer = None
    for k in range(count):
        x = (k - (count - 1) / 2) * 2.7
        rack = hardware.server_rack(f"rack{k}", pull=4 if k == pull else None)
        for part in (rack["frame"], rack["drawer"]):
            if part is not None:
                part.location = (x, 0, 0)
        if rack["drawer"] is not None:
            drawer, dx = rack["drawer"], x
        height = rack["height"]
    s.pin("drawer", (dx, -0.1, 2.75), drawer)
    s.pin("racks", ((count - 1) / 2 * 2.7 + 0.8, -1.5, height))
    s.action("open", lambda t0, t1: kit.move(drawer, f(t0), f(t1), (0, -2.3, 0)), at=0.14, span=2.2)
    s.view("wide", (0, -0.8, 2.5), 11.0 + count, -113, 4.6)
    s.view("drawer", (dx, -1.8, 2.7), 7.0, -98, 4.6)
    s.lens, s.floor_grid = 42.0, 1.2
    return s


# ---------------------------------------------------------------------------
# Structure and process
# ---------------------------------------------------------------------------

def layer_stack(p, sec):
    """Named slabs dropping onto each other, bottom first; one can be the highlighted layer."""
    s = Set(sec)
    layers = [str(x) for x in p.get("layers", ["Hardware", "Platform", "Applications"])][:5]
    highlight = p.get("highlight", layers[0])
    z0 = 0.5
    if p.get("base", "chip") == "chip":
        hardware.bga_chip("base", size=3.6, text="")
        s.pin("base", (1.8, -1.8, 0.4))
        z0 = 1.75
    ink, lit = kit.slate(), kit.mat("stack-ink", (0.95, 0.95, 0.93), emission=1.3)
    groups = []
    for k, text in enumerate(layers):
        z = z0 + k * 1.1
        hot = text == highlight or highlight == k + 1
        slab = kit.box(f"layer{k}", (0, 0, z), (4.6, 4.6, 0.46), kit.accent() if hot else kit.slate(), bevel=0.05)
        word = kit.flat_text(f"text{k}", text, (0, -2.305, z), 0.34, ink if hot else lit, rot=(math.radians(90), 0, 0))
        g = kit.group(f"g{k}", (slab, word))
        s.pin(f"layer{k + 1}", (2.3, -2.3, z), g)
        g.location = (0, 0, 5.0)
        groups.append(g)

    def stack(t0, t1):
        each = (t1 - t0) / len(groups)
        for k, g in enumerate(groups):
            a = t0 + k * each
            kit.move(g, f(a), f(a + each * 0.8), (0, 0, -5.0))
            kit.appear(g, f(a), f(a + 0.3))
    s.action("stack", stack, at=0.08, span=min(sec * 0.55, 1.6 * len(groups)))
    top = z0 + (len(layers) - 1) * 1.1
    s.view("wide", (0.4, 0, top / 2 + 0.4), 13.5 + len(layers), -95, top / 2 + 3.6)
    s.view("top", (0, -0.6, top), 8.0, -76, top + 2.2)
    s.floor_grid = 1.2
    return s


def neural_network(p, sec):
    """A feed-forward network; signals sweep through it layer by layer."""
    s = Set(sec)
    layers = tuple(int(n) for n in p.get("layers", (4, 6, 6, 6, 3)))[:7]
    net = sets.neural_network(layers=layers)
    F = s.frames
    waves = max(2, round(sec / 3.5))
    for li, m in enumerate(net["layers"]):
        keys = [(1, 0.15)]
        for wave in range(waves):
            t0 = round(wave * F / waves) + 6 + li * 9
            keys += [(max(2, t0 - 5), 0.4 if wave else 0.15), (t0, 6.0), (t0 + 10, 6.0), (t0 + 24, 0.8)]
        kit.pulse(m, keys)
    pos = net["positions"]
    s.pin("input", pos[0][-1])
    s.pin("hidden", pos[len(pos) // 2][-1])
    s.pin("output", pos[-1][-1])
    mid_z = 0.9 + (max(layers) - 1) / 2
    s.view("wide", (0, 0, mid_z), 16.6, -91, mid_z + 0.5)
    s.view("input", (pos[0][0][0] + 1.2, 0, mid_z), 9.0, -116, mid_z + 0.8)
    s.view("output", (pos[-1][0][0] - 1.2, 0, mid_z), 9.0, -66, mid_z + 0.8)
    s.lens, s.floor_grid = 45.0, 1.3
    return s


def flow_diagram(p, sec):
    """Boxes in a row joined by traces carrying light: how one stage feeds the next."""
    s = Set(sec)
    nodes = [str(x) for x in p.get("nodes", ["Input", "Process", "Output"])][:6]
    n = len(nodes)
    gap = 3.4
    x0 = -(n - 1) * gap / 2
    lit = kit.mat("flow-ink", (0.95, 0.95, 0.93), emission=1.3)
    mats = []
    for k, text in enumerate(nodes):
        x = x0 + k * gap
        m = kit.glow(f"flow-node{k}", 0.08)
        mats.append(m)
        kit.box(f"node{k}", (x, 0, 1.0), (2.0, 1.2, 1.3), kit.slate(), bevel=0.06)
        kit.box(f"node-cap{k}", (x, 0, 1.69), (2.0, 1.2, 0.08), m, bevel=0.02)
        kit.flat_text(f"node-text{k}", text, (x, -0.605, 1.0), min(0.34, 3.2 / max(4, len(text)) * 0.5), lit,
                      rot=(math.radians(90), 0, 0))
        s.pin(f"node{k + 1}", (x, -0.6, 1.72))
    trace = look.signal_material("flow-trace", s.frames, axis="X", spacing=1.1, speed=1.6, lanes=6.0)
    for k in range(n - 1):
        x = x0 + k * gap + gap / 2
        kit.box(f"trace{k}", (x, 0, 1.0), (gap - 2.0, 0.5, 0.06), trace, bevel=0)

    def run(t0, t1):
        each = (t1 - t0) / n
        for k, m in enumerate(mats):
            a = f(t0 + k * each)
            kit.pulse(m, [(1, 0.08), (max(2, a - 4), 0.08), (a + 6, 5.0)])
    s.action("run", run, at=0.1, span=min(sec * 0.6, 1.4 * n))
    s.view("wide", (0, 0, 1.0), 8.5 + n * 2.2, -93, 3.4)
    s.view("first", (x0 + 0.6, 0, 1.2), 7.4, -112, 2.9)
    s.view("last", (-x0 - 0.6, 0, 1.2), 7.4, -70, 2.9)
    s.lens = 45.0
    return s


def timeline(p, sec):
    """Years along a rail; each marker lights as the story reaches it."""
    s = Set(sec)
    events = [str(e) for e in p.get("events", ["1993", "1999", "2006", "2012", "2024"])][:8]
    n = len(events)
    gap = 3.0
    x0 = -(n - 1) * gap / 2
    kit.box("rail", (0, 0, 0.12), ((n - 1) * gap + 2.4, 0.16, 0.08), kit.mid(), bevel=0.02)
    lit = kit.mat("timeline-ink", (0.95, 0.95, 0.93), emission=1.3)
    mats = []
    for k, text in enumerate(events):
        x = x0 + k * gap
        m = kit.glow(f"year{k}", 0.08)
        mats.append(m)
        kit.cyl(f"post{k}", (x, 0, 0.75), 0.06, 1.3, kit.mid(), verts=16)
        kit.ico(f"bead{k}", (x, 0, 1.5), 0.26, m, subdivisions=2)
        kit.flat_text(f"year-text{k}", text, (x, -0.02, 2.25), 0.52, lit, rot=(math.radians(90), 0, 0))
        s.pin(f"event{k + 1}", (x, 0, 1.5))

    def run(t0, t1):
        each = (t1 - t0) / n
        for k, m in enumerate(mats):
            a = f(t0 + k * each)
            kit.pulse(m, [(1, 0.08), (max(2, a - 4), 0.08), (a + 6, 6.0)])
    s.action("run", run, at=0.08, span=sec * 0.7)
    s.view("wide", (0, 0, 1.4), 7.5 + n * 2.3, -92, 3.2)
    s.view("start", (x0 + 1.2, 0, 1.5), 8.0, -114, 2.8)
    s.view("end", (-x0 - 1.2, 0, 1.5), 8.0, -68, 2.8)
    s.lens = 45.0
    return s


def scale_compare(p, sec):
    """One block beside many: how much more, counted out in cubes."""
    s = Set(sec)
    many = max(2, min(1024, int(p.get("many", 100))))
    side = math.ceil(math.sqrt(many))
    cell = 5.0 / side
    kit.box("one", (-4.2, 0, 0.25 + cell * 0.4), (cell * 0.8, cell * 0.8, cell * 0.8), kit.accent(), bevel=0.01)
    rows = []
    for r in range(side):
        cells = [placed((1.0 + (c + 0.5) * cell, -2.5 + (r + 0.5) * cell, 0.25 + cell * 0.4), (cell * 0.8,) * 3)
                 for c in range(side) if r * side + c < many]
        if cells:
            rows.append(kit.boxes(f"many-row{r}", cells, look.neon("many-cubes", look.WARM, 1.2)))
    s.pin("one", (-4.2, 0, 0.3 + cell * 0.8))
    s.pin("many", (3.5, -2.5, 0.3 + cell * 0.8))

    def fill(t0, t1):
        each = (t1 - t0) / len(rows)
        for r, ob in enumerate(rows):
            kit.appear(ob, f(t0 + r * each), f(t0 + r * each + 0.25))
    s.action("fill", fill, at=0.2, span=sec * 0.45)
    s.view("wide", (0, 0, 0.6), 15.5, -96, 8.6)
    s.view("many", (3.5, 0, 0.5), 9.0, -74, 6.0)
    return s


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

def bar_chart(p, sec):
    """Columns rising left to right; the last one is the point of the sentence."""
    s = Set(sec)
    heights = _heights(p.get("values"), 4.6)[:16]
    n = len(heights)
    gap = min(1.1, 13.0 / n)
    x0 = -(n - 1) * gap / 2
    bars = []
    for k, h in enumerate(heights):
        last = k == n - 1
        col = kit.box(f"bar{k}", (x0 + k * gap, 0, 0), (gap * 0.68, gap * 0.68, h),
                      look.neon("bar-now", look.WARM, 1.6) if last else kit.mid(), bevel=0.02)
        col.scale[2] = 0.001
        bars.append((col, h))
    kit.boxes("axis", [placed((0, -0.55, 0.01), (n * gap + 0.9, 0.03, 0.02))], kit.accent())
    s.pin("first", (x0, -0.4, 0.12))
    s.pin("last", (-x0, -0.4, heights[-1]))

    def grow_(t0, t1):
        each = (t1 - t0) / n
        for k, (col, h) in enumerate(bars):
            grow(col, 0.0, h, f(t0 + k * each), f(t0 + k * each + max(0.5, each * 1.6)))
    s.action("grow", grow_, at=0.06, span=sec * 0.6)
    s.view("wide", (0.3, 0, 2.3), 17.5, -99, 5.0)
    s.view("last", (-x0 - 0.6, 0, heights[-1] * 0.55), 9.5, -76, heights[-1] * 0.55 + 1.6)
    s.lens, s.floor_grid = 45.0, 1.2
    return s


def line_chart(p, sec):
    """A line drawn across a dark board, optionally over a row of bars."""
    s = Set(sec)
    ys = [float(v) for v in p.get("points", [9, 8.4, 8.7, 7.2, 7.5, 6.0, 6.3, 4.8, 5.1, 3.6, 3.9, 2.6])][:24]
    lo, hi = min(ys), max(ys)
    span = (hi - lo) or 1.0
    n = len(ys)
    pts = [(-4.8 + 9.6 * k / (n - 1), 1.25 + 3.05 * (y - lo) / span) for k, y in enumerate(ys)]
    kit.box("board", (0, 1.2, 2.6), (11.0, 0.16, 5.0), kit.epoxy(), bevel=0.04)
    kit.boxes("gridlines", [placed((0, 1.11, 0.9 + k * 0.85), (10.2, 0.02, 0.012)) for k in range(5)], kit.mid())
    line_mat = look.neon("chart-line", look.COOL, 3.0)
    segs = [kit.rod(f"seg{k}", (pts[k][0], 1.08, pts[k][1]), (pts[k + 1][0], 1.08, pts[k + 1][1]), 0.045, line_mat)
            for k in range(n - 1)]
    bars = []
    for k, v in enumerate(_heights(p.get("bars"), 1.35) if p.get("bars") else []):
        m = len(p["bars"])
        bar = kit.box(f"under{k}", (-4.5 + 9.0 * k / max(1, m - 1), 1.06, 0.2), (min(0.5, 6.0 / m), 0.06, v),
                      look.neon("chart-bars", look.WARM, 1.1), bevel=0)
        bar.scale[2] = 0.001
        bars.append((bar, v))
    s.pin("line_start", (pts[0][0], 1.0, pts[0][1]))
    s.pin("line_end", (pts[-1][0], 1.0, pts[-1][1]))
    if bars:
        s.pin("bars", (4.5, 1.0, 0.9))

    def draw(t0, t1):
        each = (t1 - t0) / len(segs)
        for k, seg in enumerate(segs):
            kit.appear(seg, f(t0 + k * each), f(t0 + k * each + 0.3))
        for k, (bar, h) in enumerate(bars):
            a = t0 + k * (t1 - t0) / len(bars)
            grow(bar, 0.2, h, f(a), f(a + 0.6))
    s.action("draw", draw, at=0.06, span=sec * 0.6)
    s.view("wide", (0, 0.6, 2.4), 14.0, -93, 3.3)
    s.view("end", (3.4, 0.9, pts[-1][1]), 7.5, -74, pts[-1][1] + 0.6)
    s.lens, s.floor_grid, s.gain = 45.0, 1.1, 1.6
    return s


def presenter_screen(p, sec):
    """A figure on a stage in front of a screen with a rising chart behind them."""
    s = Set(sec)
    kit.cyl("stage", (0, 0, 0.09), 3.4, 0.18, kit.slate(), verts=64)
    kit.cyl("stage-rim", (0, 0, 0.02), 3.5, 0.04, kit.accent(), verts=64)
    sets.figure("presenter", (-1.3, -0.6, 0.18), facing=math.radians(12), jacket=kit.epoxy(), scale=1.7)
    kit.box("screen", (1.6, 1.9, 2.5), (6.4, 0.16, 3.7), kit.epoxy(), bevel=0.03)
    kit.box("screen-face", (1.6, 1.81, 2.5), (6.1, 0.02, 3.4), kit.mat("kit-screen", (0.02, 0.028, 0.04), roughness=0.5),
            bevel=0)
    heights = _heights(p.get("values", [1, 1.3, 1.1, 2, 3.4, 6.2, 13, 27.5]), 2.75)[:10]
    n = len(heights)
    bars = []
    for k, h in enumerate(heights):
        bar = kit.box(f"bar{k}", (-0.85 + k * 4.9 / max(1, n - 1), 1.77, 1.05), (min(0.44, 3.4 / n), 0.05, h),
                      kit.glow("bar-hot", 2.2) if k == n - 1 else kit.mid(), bevel=0)
        bar.scale[2] = 0.001
        bars.append((bar, h))
    kit.boxes("screen-axis", [placed((1.6, 1.78, 1.02), (5.6, 0.03, 0.02))], kit.base())
    s.pin("presenter", (-1.3, -0.6, 3.5))
    s.pin("peak", (4.05, 1.72, 1.05 + heights[-1]))

    def grow_(t0, t1):
        each = (t1 - t0) / n
        for k, (bar, h) in enumerate(bars):
            grow(bar, 1.05, h, f(t0 + k * each), f(t0 + k * each + 0.8))
    s.action("grow", grow_, at=0.05, span=min(sec * 0.5, 4.5))
    s.view("wide", (0.9, 0.4, 2.1), 12.5, -98, 2.6)
    s.view("presenter", (-1.3, -0.4, 2.7), 6.4, -118, 2.9)
    s.view("screen", (2.2, 1.6, 2.5), 7.6, -84, 2.7)
    s.lens, s.gain = 45.0, 2.6
    return s


# ---------------------------------------------------------------------------
# People and places
# ---------------------------------------------------------------------------

def people_row(p, sec):
    """One to six figures standing on a plinth: founders, a team, rivals."""
    s = Set(sec)
    count = max(1, min(6, int(p.get("count", 3))))
    lead = int(p.get("lead", (count + 1) // 2))
    width = max(3.3, count * 1.0 + 0.6)
    kit.cyl("plinth", (0, 0, 0.07), width, 0.14, kit.slate(), verts=64)
    kit.cyl("plinth-rim", (0, 0, 0.02), width + 0.1, 0.04, kit.accent(), verts=64)
    jackets = _jackets()
    for k in range(count):
        x = (k - (count - 1) / 2) * 1.75
        y = -0.25 if k + 1 == lead else 0.25
        sets.figure(f"person{k}", (x, y, 0.14), jacket=jackets[(k + (0 if k + 1 != lead else 2)) % len(jackets)],
                    scale=1.45)
        s.pin(f"person{k + 1}", (x, y, 3.05))
    s.view("wide", (0, 0, 1.55), 8.0 + count * 0.9, -96, 2.7)
    s.view("lead", ((lead - 1 - (count - 1) / 2) * 1.75, 0, 2.1), 5.6, -74, 2.6)
    s.lens, s.floor_grid, s.gain = 45.0, 0.9, 2.6
    return s


def meeting_table(p, sec):
    """A diner booth with people around a table and an idea sketched on a napkin."""
    s = Set(sec)
    booth = sets.diner_booth()
    seats = [((-0.65, 1.22, 0.0), 0.0), ((0.65, 1.22, 0.0), 0.0), ((-0.1, -1.22, 0.0), math.pi),
             ((0.9, -1.22, 0.0), math.pi)]
    jackets = _jackets()
    for k in range(max(1, min(4, int(p.get("count", 3))))):
        loc, facing = seats[k]
        sets.figure(f"guest{k}", loc, facing=facing, seated=True, jacket=jackets[k])
    s.pin("table", booth["napkin_xyz"])

    def idea(t0, t1):
        kit.pulse(booth["sketch_ink"], [(1, 0.0), (f(t0), 0.0), (f(t1), 5.0)])
    s.action("idea", idea, at=0.45, span=1.6)
    s.view("wide", (0.1, 0, 0.95), 6.5, 221, 2.8)
    s.view("table", (0.0, 0.0, 0.9), 3.4, 196, 2.3)
    s.lens, s.floor_grid, s.gain = 40.0, 0.8, 3.2
    return s


def org_radial(p, sec):
    """One figure at the centre, everyone else in rings around it, each linked straight in."""
    s = Set(sec)
    rings = [int(c) for c in p.get("rings", (16, 26, 18))][:4]
    kit.cyl("centre-plinth", (0, 0, 0.22), 0.62, 0.44, kit.accent(), verts=40)
    kit.ico("centre-head", (0, 0, 0.86), 0.34, kit.accent(), subdivisions=1)
    groups = []
    for ri, count in enumerate(rings):
        radius = 3.1 + ri * 2.0
        seats, heads, links = [], [], []
        for k in range(count):
            a = k * 2 * math.pi / count + ri * 0.31
            x, y = math.cos(a) * radius, math.sin(a) * radius
            seats.append(((x, y, 0.13), 0.30, 0.26))
            heads.append((x, y, 0.52))
            links.append(((x * 0.13, y * 0.13, 0.05), (x, y, 0.05)))
        parts = (kit.cylinders(f"ring{ri}-seats", seats, kit.base(), segments=20),
                 kit.balls(f"ring{ri}-heads", heads, 0.20, kit.base()),
                 kit.rods(f"ring{ri}-links", links, 0.018, kit.accent()))
        groups.append(kit.group(f"ring{ri}", parts))
    outer = 3.1 + (len(rings) - 1) * 2.0
    s.pin("centre", (0, 0, 1.2))
    s.pin("ring", (3.1 + min(1, len(rings) - 1) * 2.0, -0.4, 0.75))
    s.pin("links", (-1.4, -0.9, 0.08))

    def spread(t0, t1):
        each = (t1 - t0) / len(groups)
        for ri, g in enumerate(groups):
            kit.appear(g, f(t0 + ri * each), f(t0 + ri * each + 0.9))
    s.action("spread", spread, at=0.1, span=min(sec * 0.5, 5.4))
    s.view("wide", (0, 0, 0.9), outer * 2.5, -104, outer * 1.5)
    s.view("centre", (0, 0, 0.7), outer * 1.15, -76, outer * 0.55)
    s.floor_grid = 1.1
    return s


def campus(p, sec):
    """A low headquarters building among trees, seen from the air."""
    s = Set(sec)
    b = sets.campus_building()
    s.pin("building", (0, 0, b["roof_z"]))
    s.view("wide", (0, 0, 1.4), 24.5, -101, 11.5)
    s.view("low", (0, 0, 1.6), 19.0, -72, 4.6)
    s.lens, s.floor_grid, s.gain = 40.0, 2.0, 3.0
    return s


# ---------------------------------------------------------------------------
# Paper
# ---------------------------------------------------------------------------

def pages(p, sec):
    """Front pages drifting past in the dark: attention, with nothing legible to quote."""
    s = Set(sec)
    sheets = [(-4.6, 2.2, 2.9, 0.20), (-1.9, 0.6, 2.2, -0.12), (0.9, 2.8, 3.1, 0.10), (3.4, 0.2, 2.5, -0.22),
              (5.6, 2.4, 2.0, 0.16), (-6.4, -0.4, 1.9, 0.30), (1.6, -1.4, 1.7, -0.06)]
    for k, (x, y, z, yaw) in enumerate(sheets[:max(2, min(7, int(p.get("count", 7))))]):
        page = kit.box(f"page{k}", (0, 0, 0), (2.3, 0.03, 3.1), kit.base(), bevel=0)
        ink = [placed((0, -0.02, 1.15), (1.9, 0.01, 0.30))]
        ink += [placed((-0.5, -0.02, 0.62 - r * 0.17), (0.86, 0.01, 0.06)) for r in range(11)]
        ink += [placed((0.5, -0.02, 0.62 - r * 0.17), (0.86, 0.01, 0.06)) for r in range(4)]
        ink.append(placed((0.5, -0.02, -0.72), (0.86, 0.01, 1.0)))
        text = kit.boxes(f"ink{k}", ink, kit.epoxy())
        g = kit.group(f"sheet{k}", (page, text))
        g.location = (x, y, z)
        g.rotation_euler = (0, 0, yaw)
        kit.move(g, 1, s.frames, (0.9 if k % 2 else -0.9, 0, 0.35 if k % 3 else -0.3))
    s.pin("front", (1.6, -1.4, 3.1))
    s.view("wide", (0, 0, 2.4), 13.0, -90, 2.8)
    s.view("close", (1.2, -0.6, 2.2), 7.0, -108, 2.4)
    s.lens, s.floor_grid, s.gain = 45.0, 1.1, 2.2
    return s


def document(p, sec):
    """One sheet of paper with a short title and a line that gets marked."""
    s = Set(sec)
    lines = max(6, min(16, int(p.get("lines", 12))))
    mark = max(1, min(lines, int(p.get("mark", lines // 2))))
    tilt = math.radians(-14)
    paper = kit.box("paper", (0, 0, 0), (4.4, 0.04, 6.0), kit.base(), bevel=0)
    parts = [paper]
    ink_mat = kit.epoxy()
    title = " ".join(str(p.get("title", "")).split())[:60]
    title_obs = []
    if title:
        # a real title is quoted whole: wrap it onto two lines and shrink it to fit the sheet, never cut it
        rows_t = [title]
        if len(title) > 22:
            words = title.split()
            cut = min(range(1, len(words)), key=lambda k: abs(len(" ".join(words[:k])) - len(title) / 2), default=1)
            rows_t = [" ".join(words[:cut]), " ".join(words[cut:])]
        size = min(0.34, 3.9 / (0.56 * max(len(r) for r in rows_t)))
        for k, row in enumerate(rows_t):
            z = 2.35 + (0.25 if len(rows_t) == 2 else 0.0) - k * size * 1.45
            title_obs.append(kit.flat_text(f"title{k}", row, (0, -0.03, z), size, ink_mat, rot=(math.radians(90), 0, 0)))
            parts.append(title_obs[-1])
    else:
        parts.append(kit.boxes("title-bar", [placed((-0.6, -0.025, 2.35), (2.6, 0.01, 0.26))], ink_mat))
    rng = random.Random(7)
    rows = []
    for r in range(lines):
        z = 1.7 - r * (3.9 / lines)
        w = 3.6 * (0.62 + 0.38 * rng.random()) if r != mark - 1 else 3.3
        rows.append(placed((-1.8 + w / 2, -0.025, z), (w, 0.01, 0.09)))
        if r == mark - 1:
            mark_z, mark_w = z, w
    parts.append(kit.boxes("lines", rows, ink_mat))
    marker = kit.box("marker", (-1.8, -0.035, mark_z), (mark_w + 0.2, 0.012, 0.26), look.neon("marker", look.WARM, 1.4),
                     bevel=0)
    marker.scale[0] = 0.001
    parts.append(marker)
    # never rendered: the region a close-up on the mark holds (the line and a little paper around
    # it), so it frames the line instead of slicing through the title above it
    hold = kit.box("mark-hold", (0, -0.03, mark_z - 0.3), (3.4, 0.01, 1.0), ink_mat, bevel=0)
    hold.hide_render = True
    hold["hold_box"] = True
    parts.append(hold)
    g = kit.group("sheet", parts)
    g.location = (0, 0, 3.4)
    g.rotation_euler = (tilt, 0, 0)
    bpy.context.view_layer.update()
    s.pin("title", (0.9, -0.6, 5.7), hold=title_obs or None)
    s.pin("mark", (0.6, -0.1, 3.4 + mark_z), hold=[hold])

    def mark_(t0, t1):
        marker.keyframe_insert("scale", frame=f(t0))
        marker.keyframe_insert("location", frame=f(t0))
        marker.scale[0] = 1.0
        marker.location[0] = -1.8 + (mark_w + 0.2) / 2
        marker.keyframe_insert("scale", frame=f(t1))
        marker.keyframe_insert("location", frame=f(t1))
    s.action("mark", mark_, at=0.4, span=1.2)
    s.view("wide", (0, 0, 3.4), 14.0, -96, 3.9)   # far enough to hold the whole sheet, title included
    s.view("mark", (0.2, -0.2, 3.4 + mark_z), 5.6, -80, 3.6 + mark_z)
    s.lens, s.gain = 45.0, 2.0
    return s


# ---------------------------------------------------------------------------
# Abstract
# ---------------------------------------------------------------------------

def statement(p, sec):
    """A field of posts moving like a slow wave: the backdrop for a line that carries no object."""
    s = Set(sec)
    n = 26
    warm = p.get("mood", "cool") == "warm"
    for r in range(n):
        m = look.neon(f"field-row{r}", look.WARM if warm else look.COOL, 0.2)
        cells = [placed(((c - n / 2) * 0.55, (r - n / 2) * 0.55, 0.3), (0.16, 0.16, 0.6)) for c in range(n)]
        row = kit.boxes(f"field{r}", cells, m)
        keys, mkeys = [], []
        steps = max(2, round(sec / 1.5))
        for k in range(steps + 1):
            phase = math.sin(k * 1.9 + r * 0.42)
            frame = max(1, round(k * s.frames / steps))
            row.scale[2] = 1.0 + 0.9 * phase
            row.keyframe_insert("scale", frame=frame)
            mkeys.append((frame, 0.25 + 1.6 * max(0.0, phase)))
        kit.pulse(m, mkeys)
    s.pin("centre", (0, 0, 0.9))
    s.view("wide", (0, 0, 0.4), 13.0, -96, 4.2)
    s.view("low", (0, 0, 0.5), 8.5, -70, 1.9)
    s.floor_grid = 0
    return s


SCENES = {
    "chip-teardown": chip_teardown, "graphics-card": graphics_card, "wafer": wafer,
    "cores-compare": cores_compare, "server-racks": server_racks,
    "layer-stack": layer_stack, "neural-network": neural_network, "flow-diagram": flow_diagram,
    "timeline": timeline, "scale-compare": scale_compare,
    "bar-chart": bar_chart, "line-chart": line_chart, "presenter-screen": presenter_screen,
    "people-row": people_row, "meeting-table": meeting_table, "org-radial": org_radial, "campus": campus,
    "pages": pages, "document": document, "statement": statement,
}


# optics scenes (wave, lens, mirror, scanner...) live in their own module
import optics  # noqa: E402
SCENES.update(optics.SCENES)
# compute scenes (tokens, layers, memory, racks, cooling) live in their own module too
import compute  # noqa: E402
SCENES.update(compute.SCENES)
import characters  # noqa: E402
SCENES.update(characters.SCENES)
# living places (a town, a hospital, an asylum) with pixel people, lit by the time of day
import world  # noqa: E402
SCENES.update(world.SCENES)
