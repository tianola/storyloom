"""Reusable electronics models. Each builder returns a dict of named sub-assemblies
(empties carrying their parts), so a beat can pull the object apart, label a layer, or
push the camera inside without knowing how the model was made.

Units are arbitrary "table units": a chip package is 2-4 across, a graphics card ~9.
"""
import math
import random

import kit
from kit import placed


# ---------------------------------------------------------------------------
# Silicon die
# ---------------------------------------------------------------------------

def die(name, loc, w, d, *, h=0.06, seed=1, cells=(7, 5)):
    """A bare die with a visible floorplan: blocks of logic, memory strips, a pad ring."""
    x, y, z = loc
    body = kit.box(f"{name}-body", (x, y, z + h / 2), (w, d, h), kit.silicon(), bevel=0.006)
    rng = random.Random(seed)
    nx, ny = cells
    cw, cd = (w * 0.9) / nx, (d * 0.9) / ny
    blocks = []
    for i in range(nx):
        for j in range(ny):
            if rng.random() < 0.12:
                continue
            bx = x - w * 0.45 + (i + 0.5) * cw
            by = y - d * 0.45 + (j + 0.5) * cd
            blocks.append(placed((bx, by, z + h + 0.006),
                                 (cw * rng.uniform(0.62, 0.9), cd * rng.uniform(0.62, 0.9), 0.012)))
    plan = kit.boxes(f"{name}-floorplan", blocks, kit.circuit())
    pads = []
    for k in range(int(w / 0.09)):
        px = x - w / 2 + 0.05 + k * 0.09
        pads += [placed((px, y - d / 2 + 0.025, z + h + 0.004), (0.04, 0.03, 0.008)),
                 placed((px, y + d / 2 - 0.025, z + h + 0.004), (0.04, 0.03, 0.008))]
    ring = kit.boxes(f"{name}-pads", pads, kit.accent())
    return kit.group(name, (body, plan, ring))


# ---------------------------------------------------------------------------
# Leaded plastic package (the 1990s look: NV1, RIVA 128)
# ---------------------------------------------------------------------------

def qfp_chip(name="chip", size=2.4, leads_per_side=18, text="", seed=1):
    """Quad flat pack: black epoxy body, gull-wing leads, and inside it a die on a
    lead frame joined by bond wires. Parts: leads, frame, die, wires, body, marking."""
    s, half = size, size / 2
    body_h, z0 = 0.34, 0.16
    pitch = (s * 0.86) / leads_per_side
    leads, inner, wires = [], [], []
    die_w = s * 0.42
    for side in range(4):
        ang = side * math.pi / 2
        c, sn = math.cos(ang), math.sin(ang)
        for k in range(leads_per_side):
            t = (k + 0.5) * pitch - s * 0.43

            def at(out, z, _t=t):
                return (c * out - sn * _t, sn * out + c * _t, z)

            # shoulder, drop and foot of one gull-wing lead
            leads.append(placed(at(half + 0.10, z0 + body_h * 0.5), (0.22, pitch * 0.5, 0.035), ang))
            leads.append(placed(at(half + 0.215, z0 + body_h * 0.25), (0.035, pitch * 0.5, body_h * 0.5), ang))
            leads.append(placed(at(half + 0.31, 0.02), (0.22, pitch * 0.5, 0.035), ang))
            # inside the plastic every lead fans in toward the die, and a bond wire
            # finishes the path from the lead tip to a pad on the die edge
            zf = z0 + body_h * 0.5
            shrink = (die_w * 0.80) / half
            tip = at(die_w * 0.80, zf, t * shrink)
            inner.append((at(half - 0.02, zf), tip))
            spread = ((k + 0.5) / leads_per_side - 0.5) * die_w * 0.86
            pad = at(die_w / 2 - 0.03, zf + 0.075, spread)
            wires.append((pad, (tip[0], tip[1], zf + 0.02)))
    lead_ob = kit.boxes(f"{name}-leads", leads, kit.steel())
    frame_ob = kit.rods(f"{name}-leadframe", inner, pitch * 0.2, kit.steel())
    paddle = kit.box(f"{name}-paddle", (0, 0, z0 + body_h * 0.5 - 0.01), (die_w * 1.12, die_w * 1.12, 0.03),
                     kit.steel(), bevel=0.005)
    wire_ob = kit.rods(f"{name}-wires", wires, 0.007, kit.accent())
    die_grp = die(f"{name}-die", (0, 0, z0 + body_h * 0.5 + 0.005), die_w, die_w, seed=seed, cells=(6, 6))
    lower = kit.box(f"{name}-body-lower", (0, 0, z0 + body_h * 0.22), (s, s, body_h * 0.44), kit.epoxy(), bevel=0.03)
    upper = kit.box(f"{name}-body-upper", (0, 0, z0 + body_h * 0.80), (s, s, body_h * 0.40), kit.epoxy(), bevel=0.04)
    dot = kit.cyl(f"{name}-pin1", (-half * 0.78, -half * 0.78, z0 + body_h + 0.003), s * 0.035, 0.008,
                  kit.mid(), verts=24)
    marks = [dot]
    if text:
        marks.append(kit.flat_text(f"{name}-marking", text, (0, 0, z0 + body_h + 0.004), s * 0.17, kit.base()))
    return {
        "leads": kit.group(f"{name}-g-leads", (lead_ob, lower)),
        "frame": kit.group(f"{name}-g-frame", (frame_ob, paddle)),
        "die": die_grp,
        "wires": kit.group(f"{name}-g-wires", (wire_ob,)),
        "lid": kit.group(f"{name}-g-lid", (upper, *marks)),
        "top": z0 + body_h,
    }


# ---------------------------------------------------------------------------
# Flip-chip ball grid array (GeForce era onward) and the multi-die AI package
# ---------------------------------------------------------------------------

def _substrate(name, size, z, balls_per_side):
    s = size
    sub = kit.box(f"{name}-substrate", (0, 0, z + 0.05), (s, s, 0.10), kit.pcb(), bevel=0.02)
    pitch = (s * 0.88) / balls_per_side
    pts = [(-s * 0.44 + (i + 0.5) * pitch, -s * 0.44 + (j + 0.5) * pitch, z - 0.02)
           for i in range(balls_per_side) for j in range(balls_per_side)]
    ball_ob = kit.balls(f"{name}-balls", pts, pitch * 0.30, kit.steel())
    return sub, ball_ob


def bga_chip(name="gpu", size=3.0, text="", balls_per_side=18, seed=3, lid=True):
    """Flip-chip package: solder balls, substrate, decoupling capacitors, die, heat spreader."""
    z = 0.12
    sub, ball_ob = _substrate(name, size, z, balls_per_side)
    die_w = size * 0.46
    die_grp = die(f"{name}-die", (0, 0, z + 0.10), die_w, die_w * 0.92, seed=seed, cells=(9, 7))
    caps = []
    rng = random.Random(seed)
    for side in range(4):
        ang = side * math.pi / 2
        c, sn = math.cos(ang), math.sin(ang)
        for k in range(7):
            t = (k - 3) * size * 0.085 + rng.uniform(-0.02, 0.02)
            out = size * 0.37
            caps.append(placed((c * out - sn * t, sn * out + c * t, z + 0.125), (0.07, 0.12, 0.05), ang))
    cap_ob = kit.boxes(f"{name}-caps", caps, kit.base())
    parts = {
        "balls": kit.group(f"{name}-g-balls", (ball_ob,)),
        "substrate": kit.group(f"{name}-g-substrate", (sub, cap_ob)),
        "die": die_grp,
        "top": z + 0.17,
    }
    if lid:
        lid_h = 0.14
        plate = kit.box(f"{name}-lid", (0, 0, z + 0.10 + 0.08 + lid_h / 2), (size * 0.70, size * 0.70, lid_h),
                        kit.steel(), bevel=0.035)
        marks = [plate]
        if text:
            marks.append(kit.flat_text(f"{name}-marking", text, (0, 0, z + 0.18 + lid_h + 0.004),
                                       size * 0.10, kit.slate()))
        parts["lid"] = kit.group(f"{name}-g-lid", marks)
        parts["top"] = z + 0.18 + lid_h
    return parts


def ai_package(name="ai", size=4.6):
    """A modern AI accelerator package: one large logic die flanked by stacks of
    high-bandwidth memory, all on a silicon interposer, on a substrate, under one lid.
    Parts: balls, substrate, interposer, logic, memory (list of layer groups), lid."""
    z = 0.12
    sub, ball_ob = _substrate(name, size, z, 26)
    inter = kit.box(f"{name}-interposer", (0, 0, z + 0.125), (size * 0.74, size * 0.62, 0.05),
                    kit.silicon(), bevel=0.008)
    zi = z + 0.15
    logic = die(f"{name}-logic", (0, 0, zi), size * 0.36, size * 0.50, seed=11, cells=(8, 12), h=0.07)
    layers = []
    n_layers = 5
    for layer in range(n_layers):
        slabs = []
        for side in (-1, 1):
            for k in range(4):
                y = (k - 1.5) * size * 0.13
                slabs.append(placed((side * size * 0.275, y, zi + 0.012 + layer * 0.022),
                                    (size * 0.12, size * 0.105, 0.018)))
        material = kit.accent() if layer == n_layers - 1 else kit.circuit()
        layers.append(kit.group(f"{name}-g-hbm{layer}",
                                (kit.boxes(f"{name}-hbm{layer}", slabs, material),)))
    lid_h = 0.16
    plate = kit.box(f"{name}-lid", (0, 0, zi + 0.14 + lid_h / 2), (size * 0.84, size * 0.72, lid_h),
                    kit.steel(), bevel=0.04)
    frame = kit.box(f"{name}-stiffener", (0, 0, z + 0.13), (size * 0.96, size * 0.96, 0.05), kit.steel(), bevel=0.01)
    return {
        "balls": kit.group(f"{name}-g-balls", (ball_ob,)),
        "substrate": kit.group(f"{name}-g-substrate", (sub,)),
        "interposer": kit.group(f"{name}-g-interposer", (inter,)),
        "logic": logic,
        "memory": layers,
        "lid": kit.group(f"{name}-g-lid", (plate,)),
        "stiffener": frame,
        "memory_xy": (size * 0.275, 0.0),
        "top": zi + 0.14 + lid_h,
    }


# ---------------------------------------------------------------------------
# Graphics card
# ---------------------------------------------------------------------------

def graphics_card(name="card", length=9.0, depth=4.2, chip_text="GPU"):
    """An add-in graphics card. Parts: board (PCB, connector, bracket, memory, power
    parts), gpu (the packaged chip), heatsink, fan (hub + blades, ready to spin)."""
    L, D = length, depth
    zb = 0.30
    board = kit.box(f"{name}-pcb", (0, 0, zb), (L, D, 0.07), kit.pcb(), bevel=0.01)
    # edge connector: a tab with gold fingers along the lower edge
    tab = kit.box(f"{name}-tab", (-L * 0.12, -D / 2 - 0.22, zb), (L * 0.52, 0.44, 0.07), kit.pcb(), bevel=0.005)
    fingers = [placed((-L * 0.12 - L * 0.25 + (k + 0.5) * (L * 0.5 / 44), -D / 2 - 0.25, zb + 0.038),
                      (L * 0.5 / 44 * 0.6, 0.34, 0.008)) for k in range(44)]
    finger_ob = kit.boxes(f"{name}-fingers", fingers, kit.accent())
    # mounting bracket with video ports
    bracket = kit.box(f"{name}-bracket", (-L / 2 - 0.04, 0.15, zb + 0.55), (0.06, D + 0.9, 1.5), kit.steel(), bevel=0.01)
    ports = kit.boxes(f"{name}-ports", [
        placed((-L / 2 - 0.09, -0.9, zb + 0.45), (0.10, 1.0, 0.36)),
        placed((-L / 2 - 0.09, 0.75, zb + 0.45), (0.10, 0.9, 0.36))], kit.slate())
    # memory chips beside the GPU, capacitors and chokes toward the far end
    mem = [placed((-0.2 + 1.75 * sx, 0.1 + (k - 1.5) * 0.62, zb + 0.085), (0.42, 0.50, 0.10))
           for sx in (-1, 1) for k in range(4)]
    mem_ob = kit.boxes(f"{name}-memory", mem, kit.epoxy())
    cans = [((L * 0.30 + (i % 4) * 0.36, -D * 0.33 + (i // 4) * 0.42, zb + 0.24), 0.13, 0.40) for i in range(12)]
    can_ob = kit.cylinders(f"{name}-capacitors", cans, kit.base(), segments=20)
    chokes = kit.boxes(f"{name}-chokes", [placed((L * 0.30 + k * 0.48, D * 0.22, zb + 0.16), (0.36, 0.36, 0.26))
                                           for k in range(3)], kit.mid())
    traces = kit.boxes(f"{name}-traces", [
        placed((-L * 0.12 + (k - 8) * 0.14, -D * 0.30, zb + 0.037), (0.035, D * 0.34, 0.004)) for k in range(17)],
        kit.mat("kit-trace", (0.06, 0.15, 0.13), roughness=0.5))
    gpu = bga_chip(f"{name}-gpu", size=1.7, balls_per_side=12, text=chip_text, seed=5)
    gpu_grp = kit.group(f"{name}-g-gpu", (gpu["balls"], gpu["substrate"], gpu["die"], gpu["lid"]))
    gpu_grp.location = (-0.2, 0.1, zb + 0.0)

    # heatsink: base plate plus a field of fins, with a round well for the fan
    zs = zb + 0.52
    hs_base = kit.box(f"{name}-hs-base", (-0.2, 0.1, zs), (3.3, 3.3, 0.12), kit.steel(), bevel=0.01)
    fins = []
    for k in range(27):
        x = -0.2 - 1.6 + k * (3.2 / 26)
        r = abs(x + 0.2)
        gap = math.sqrt(max(0.0, 1.18 ** 2 - r ** 2))
        for sgn in (-1, 1):
            lo, hi = (gap, 1.62) if gap < 1.62 else (None, None)
            if lo is None:
                continue
            fins.append(placed((x, 0.1 + sgn * (lo + hi) / 2, zs + 0.37), (0.045, hi - lo, 0.62)))
    fin_ob = kit.boxes(f"{name}-hs-fins", fins, kit.steel())
    hub = kit.cyl(f"{name}-fan-hub", (0, 0, 0.30), 0.40, 0.34, kit.slate(), verts=32)
    cap = kit.cyl(f"{name}-fan-cap", (0, 0, 0.475), 0.24, 0.015, kit.accent(), verts=32)
    blades = []
    for k in range(9):
        a = k * 2 * math.pi / 9
        blade = kit.box(f"{name}-blade{k}", (math.cos(a) * 0.72, math.sin(a) * 0.72, 0.28), (0.70, 0.30, 0.03),
                        kit.slate(), bevel=0.01)
        blade.rotation_euler = (math.radians(24), 0, a + math.radians(18))
        blades.append(blade)
    rotor = kit.group(f"{name}-rotor", (hub, cap, *blades))
    rotor.location = (-0.2, 0.1, zs + 0.06)
    return {
        "board": kit.group(f"{name}-g-board", (board, tab, finger_ob, bracket, ports, mem_ob, can_ob, chokes, traces)),
        "gpu": gpu_grp,
        "heatsink": kit.group(f"{name}-g-heatsink", (hs_base, fin_ob)),
        "fan": kit.group(f"{name}-g-fan", (rotor,)),
        "rotor": rotor,
        "gpu_xyz": (-0.2, 0.1, zb + 0.45),
        "top": zs + 0.7,
    }


# ---------------------------------------------------------------------------
# Wafer
# ---------------------------------------------------------------------------

def wafer(name="wafer", radius=3.6, die_size=0.52, lift=(1, 0)):
    """A patterned silicon wafer. Every die is a separate cell; the one at grid position
    `lift` is its own object so a beat can raise it out. Parts: disc, dies, hero."""
    disc = kit.cyl(f"{name}-disc", (0, 0, 0.03), radius, 0.06, kit.silicon(), verts=96)
    pitch = die_size * 1.09
    n = int(radius / pitch) + 1
    cells, hero_xy = [], (lift[0] * pitch, lift[1] * pitch)
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            x, y = i * pitch, j * pitch
            if math.hypot(abs(x) + die_size / 2, abs(y) + die_size / 2) > radius * 0.97:
                continue
            if (i, j) == tuple(lift):
                continue
            cells.append(placed((x, y, 0.066), (die_size, die_size, 0.012)))
    dies = kit.boxes(f"{name}-dies", cells, kit.circuit())
    # the hero die carries a real floorplan
    hero = die(f"{name}-hero", (hero_xy[0], hero_xy[1], 0.058), die_size, die_size, h=0.02, seed=7, cells=(5, 5))
    return {"disc": kit.group(f"{name}-g-disc", (disc, dies)), "hero": hero, "hero_xy": hero_xy}


# ---------------------------------------------------------------------------
# Server rack
# ---------------------------------------------------------------------------

def server_rack(name="rack", units=8, width=2.2, depth=3.0, unit_h=0.52, pull=None):
    """A rack of GPU servers. Unit `pull` (index) is returned as its own group, with
    eight accelerator cards inside it, so a beat can slide it out. Parts: frame, units,
    drawer (or None)."""
    H = units * unit_h + 0.3
    posts = [placed((sx * width / 2, sy * depth / 2, H / 2), (0.10, 0.10, H)) for sx in (-1, 1) for sy in (-1, 1)]
    posts += [placed((0, sy * depth / 2, z), (width, 0.10, 0.10)) for sy in (-1, 1) for z in (0.05, H - 0.05)]
    posts += [placed((sx * width / 2, 0, z), (0.10, depth, 0.10)) for sx in (-1, 1) for z in (0.05, H - 0.05)]
    frame = kit.boxes(f"{name}-frame", posts, kit.slate())
    side = kit.boxes(f"{name}-sides", [placed((sx * (width / 2 - 0.02), 0, H / 2), (0.02, depth - 0.2, H - 0.2))
                                        for sx in (-1, 1)], kit.slate())
    fixed, drawer = [], None
    for u in range(units):
        z = 0.15 + (u + 0.5) * unit_h
        w = width - 0.16
        chassis = kit.box(f"{name}-u{u}", (0, 0, z), (w, depth - 0.1, unit_h * 0.9), kit.mid(), bevel=0.012)
        yf = -depth / 2 + 0.04
        slots = [placed((-w * 0.42 + k * (w * 0.6 / 17), yf, z), (w * 0.6 / 17 * 0.45, 0.02, unit_h * 0.6))
                 for k in range(18)]
        grille = kit.boxes(f"{name}-u{u}-grille", slots, kit.epoxy())
        leds = kit.boxes(f"{name}-u{u}-leds", [placed((w * 0.30 + k * 0.09, yf, z + unit_h * 0.2), (0.04, 0.02, 0.04))
                                                for k in range(4)], kit.glow(f"{name}-led{u}", 3.0))
        handles = kit.boxes(f"{name}-u{u}-handles", [placed((sx * w * 0.46, yf - 0.03, z), (0.03, 0.06, unit_h * 0.5))
                                                      for sx in (-1, 1)], kit.steel())
        parts = [chassis, grille, leds, handles]
        if u == pull:
            cards = [placed((-w * 0.38 + k * (w * 0.76 / 7), 0.1, z + unit_h * 0.47), (0.09, depth * 0.62, 0.06))
                     for k in range(8)]
            parts.append(kit.boxes(f"{name}-u{u}-cards", cards, kit.accent()))
            drawer = kit.group(f"{name}-g-drawer", parts)
        else:
            fixed += parts
    return {"frame": kit.group(f"{name}-g-frame", (frame, side, *fixed)), "drawer": drawer, "height": H}


# ---------------------------------------------------------------------------
# Die at close range: a field of cores joined by signal traces
# ---------------------------------------------------------------------------

def core_city(name, center, width, n=32, waves=8, core_mats=None, trace_x=None, trace_y=None):
    """The surface of a GPU die, built to be flown over.

    n x n cores of slightly different heights stand on a dark die, with a lane of trace
    between every row and column. Cores are split into `waves` diagonal groups, one
    object and one material each, so a beat can sweep work across the whole die; the
    traces take two materials (one per direction) so signals can run along them.
    Returns the per-wave objects and the top height.
    """
    rng = random.Random(21)
    cx, cy, z = center
    pitch = width / n
    kit.box(f"{name}-die", (cx, cy, z - pitch * 0.5), (width * 1.06, width * 1.06, pitch), kit.slate(), bevel=0)
    groups = [[] for _ in range(waves)]
    for i in range(n):
        for j in range(n):
            h = pitch * rng.uniform(0.35, 0.95)
            x = cx - width / 2 + (i + 0.5) * pitch
            y = cy - width / 2 + (j + 0.5) * pitch
            groups[(i + j) % waves].append(placed((x, y, z + h / 2), (pitch * 0.62, pitch * 0.62, h)))
    objects = [kit.boxes(f"{name}-cores{w}", cells, core_mats[w] if core_mats else kit.circuit())
               for w, cells in enumerate(groups)]
    lane_w, lane_h = pitch * 0.10, pitch * 0.05
    xs = [placed((cx, cy - width / 2 + j * pitch, z + lane_h / 2), (width, lane_w, lane_h)) for j in range(n + 1)]
    ys = [placed((cx - width / 2 + i * pitch, cy, z + lane_h / 2), (lane_w, width, lane_h)) for i in range(n + 1)]
    kit.boxes(f"{name}-traces-x", xs, trace_x or kit.accent())
    kit.boxes(f"{name}-traces-y", ys, trace_y or kit.accent())
    pads = []
    for k in range(n * 2):
        t = -width / 2 + (k + 0.5) * width / (n * 2)
        for sx, sy in ((t, -width * 0.515), (t, width * 0.515), (-width * 0.515, t), (width * 0.515, t)):
            pads.append(placed((cx + sx, cy + sy, z + lane_h), (pitch * 0.28, pitch * 0.28, lane_h * 2)))
    kit.boxes(f"{name}-pads", pads, kit.accent())
    return {"cores": objects, "pitch": pitch, "top": z + pitch}
