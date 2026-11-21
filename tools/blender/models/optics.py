"""Optics scenes: light as a wave, how a lens rebuilds a pattern, and the parts of an EUV scanner.

Built for the episode that explains EUV lithography, but every scene is parametric and knows
nothing about that episode: a wave at a gap, a grating whose beams a lens catches or misses, the
resolution formula as three knobs, wavelengths side by side, a projector printing a mask onto a
wafer, a tin-droplet plasma source, a multilayer (Bragg) mirror, the mirror path through a
scanner, the scan itself, and photons landing at random on a grid.

Conventions are the ones in scenes.py: the picture plane is XZ, the camera looks along +Y from
the -Y side (azimuth near -90), text is laid flat on a plane facing -Y.
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

import kit
import look
from kit import FPS

EUV = (0.62, 0.30, 1.0)       # the violet the film uses for extreme ultraviolet
DUV = (0.25, 0.55, 1.0)
LASER = (1.0, 0.10, 0.04)
TIN = (0.70, 0.72, 0.76)
FACE = (math.radians(90), 0, 0)   # flat text facing the camera


def f(seconds):
    return max(1, round(seconds * FPS))


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def haze(name, color, strength=2.0):
    """Additive glow that lets what is behind it show through: beams, cones, plasma."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1.0)
    em.inputs["Strength"].default_value = strength
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(em.outputs[0], add.inputs[0])
    nt.links.new(tr.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs["Surface"])
    kit.common.set_transparent(m)
    return m


def key_glow(material, keys):
    """Key the strength of a `haze`, `look.neon` or `kit.glow` material: [(frame, strength)]."""
    nodes = material.node_tree.nodes
    if "Emission" in nodes:
        socket = nodes["Emission"].inputs["Strength"]
    else:
        socket = nodes["Principled BSDF"].inputs["Emission Strength"]
    for frame, value in sorted(keys):
        socket.default_value = value
        socket.keyframe_insert("default_value", frame=max(1, int(frame)))


def ray(name, radius, material, verts=12):
    """A unit-length bar from its origin along local -Z; scale Z is its length."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=verts, radius1=radius, radius2=radius, depth=1.0,
                          matrix=Matrix.Translation((0, 0, -0.5)))
    return kit._mesh_object(name, bm, material)


def aim_ray(ob, start, end):
    """Place a `ray` from `start` to `end`; returns its length."""
    a, b = Vector(start), Vector(end)
    d = b - a
    ob.location = a
    ob.rotation_euler = (-d).to_track_quat("Z", "Y").to_euler()
    ob.scale = (1, 1, d.length)
    return d.length


def grow_ray(ob, f0, f1):
    """Draw a placed ray out from its start between two frames."""
    length = ob.scale[2]
    ob.scale[2] = 0.0001
    ob.keyframe_insert("scale", frame=max(1, f0))
    ob.scale[2] = length
    ob.keyframe_insert("scale", frame=max(f0 + 1, f1))


def hidden_until(ob, frame):
    """Invisible (scale 0) until `frame`, then pops in over 6 frames."""
    kit.appear(ob, max(2, frame), max(2, frame) + 6)


def gone_at(ob, frame, span=6):
    full = tuple(ob.scale)
    ob.keyframe_insert("scale", frame=max(1, frame))
    ob.scale = (0.0001, 0.0001, 0.0001)
    ob.keyframe_insert("scale", frame=max(2, frame + span))
    ob.scale = full


def polyline(name, points, radius, material, resolution=2):
    """A bevelled poly curve through `points`; `bevel_factor_end` can be keyed to draw it."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    sp = cu.splines.new("POLY")
    sp.points.add(len(points) - 1)
    for i, p in enumerate(points):
        sp.points[i].co = (p[0], p[1], p[2], 1.0)
    cu.bevel_depth = radius
    cu.bevel_resolution = resolution
    cu.use_fill_caps = True
    cu.materials.append(material)
    return kit._link(bpy.data.objects.new(name, cu))


def draw_curve(ob, f0, f1):
    cu = ob.data
    cu.bevel_factor_end = 0.0
    cu.keyframe_insert("bevel_factor_end", frame=max(1, f0))
    cu.bevel_factor_end = 1.0
    cu.keyframe_insert("bevel_factor_end", frame=max(f0 + 1, f1))


def ink():
    return kit.mat("optics-ink", (0.95, 0.95, 0.93), emission=1.3)


def text(name, body, loc, size, material=None, align="CENTER"):
    return kit.flat_text(name, body, loc, size, material or ink(), rot=FACE, align=align)


def plate(name, loc, size, material, bevel=0.02):
    return kit.box(name, loc, size, material, bevel=bevel)


def mirror_mat():
    return kit.mat("optics-mirror", (0.62, 0.64, 0.70), metallic=0.6, roughness=0.3)


def mirror_at(name, centre, d_in, d_out, width=1.1, thick=0.14):
    """A small mirror at `centre` turned so a ray arriving along d_in leaves along d_out."""
    n = (Vector(d_out).normalized() - Vector(d_in).normalized()).normalized()
    ob = kit.box(name, (0, 0, 0), (width, 0.9, thick), mirror_mat(), bevel=0.03)
    ob.rotation_euler = n.to_track_quat("Z", "Y").to_euler()
    ob.location = Vector(centre) - n * (thick / 2)
    face = kit.box(name + "-face", (0, 0, 0), (width * 0.94, 0.84, 0.02), look.neon(name + "-glow", EUV, 0.35), bevel=0)
    face.rotation_euler = ob.rotation_euler
    face.location = Vector(centre) + n * 0.005
    return ob


# ---------------------------------------------------------------------------
# 1. a wave at a gap
# ---------------------------------------------------------------------------

def _half_ring(name, material, radius=1.0, width=0.07, segments=48):
    """A semicircular band in the XZ plane opening toward +X, centred on the origin."""
    bm = bmesh.new()
    verts = []
    for k in range(segments + 1):
        a = -math.pi / 2 + math.pi * k / segments
        for r in (radius - width / 2, radius + width / 2):
            verts.append(bm.verts.new((r * math.cos(a), 0.0, r * math.sin(a))))
    for k in range(segments):
        a0, a1, b0, b1 = verts[2 * k], verts[2 * k + 1], verts[2 * k + 2], verts[2 * k + 3]
        bm.faces.new((a0, b0, b1, a1))
    bmesh.ops.solidify(bm, geom=bm.faces[:], thickness=0.05)
    return kit._mesh_object(name, bm, material)


def wave_slit(p, sec):
    """A wave meets a gap: through a wide gap it carries straight on, past a narrow one it spreads."""
    from scenes import Set
    s = Set(sec)
    mode = p.get("gap", "both")
    panels = {"both": [("wide", 3.6), ("narrow", -3.6)], "wide": [("wide", 0.0)], "narrow": [("narrow", 0.0)]}[mode]
    period = 0.40                     # seconds between crests: wavelength 0.88
    speed = 2.2                       # units per second
    left, right = -6.0, 6.0
    wall = kit.slate()
    for tag, z in panels:
        gap = 3.4 if tag == "wide" else 0.32     # about four wavelengths, and about a third of one
        h = 5.0
        kit.box(f"{tag}-board", (0, 0.35, z), (12.6, 0.1, h), kit.mat("optics-board", (0.015, 0.018, 0.026), roughness=0.9), bevel=0.02)
        top = (h / 2 - gap / 2)
        kit.box(f"{tag}-wall-up", (0, 0, z + gap / 2 + top / 2), (0.22, 0.5, top), wall, bevel=0.02)
        kit.box(f"{tag}-wall-dn", (0, 0, z - gap / 2 - top / 2), (0.22, 0.5, top), wall, bevel=0.02)
        s.pin(tag, (0.1, -0.3, z + gap / 2))
        n = int(sec / period) + 7
        for k in range(n):
            t_hit = (k - 5) * period            # when this crest reaches the wall
            t0 = t_hit - (0 - left) / speed      # when it entered on the left
            m = look.neon(f"{tag}-crest{k}", look.COOL, 2.2)
            bar = kit.box(f"{tag}-in{k}", (left, 0, z), (0.07, 0.25, h * 0.92), m, bevel=0)
            bar.keyframe_insert("location", frame=f(t0) if t0 > 0 else 1)
            if t0 < 0:
                bar.location[0] = left + (-t0) * speed
                bar.keyframe_insert("location", frame=1)
            bar.location[0] = 0.0
            bar.keyframe_insert("location", frame=max(2, f(t_hit)))
            for fc in bar.animation_data.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
            gone_at(bar, max(2, f(t_hit)), 1)
            # what leaves the gap
            t_end = t_hit + ((right if tag == "wide" else 3.4) / speed)
            mo = look.neon(f"{tag}-out{k}", look.COOL, 2.2)
            if tag == "narrow":
                out = _half_ring(f"{tag}-ring{k}", mo, radius=1.0, width=0.03)
                out.location = (0.12, 0, z)
                out.scale = (0.05, 1, 0.05)
                out.keyframe_insert("scale", frame=max(1, f(t_hit)))
                out.scale = (3.4, 1, 3.4)
                out.keyframe_insert("scale", frame=max(2, f(t_end)))
                key_glow(mo, [(f(t_hit), 2.6), (f(t_end), 0.5)])
            else:
                out = kit.box(f"{tag}-out{k}", (0.12, 0, z), (0.07, 0.25, gap * 0.95), mo, bevel=0)
                out.keyframe_insert("location", frame=max(1, f(t_hit)))
                out.location[0] = right
                out.keyframe_insert("location", frame=max(2, f(t_end)))
            for fc in out.animation_data.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
            if t_hit > 0:
                if tag == "narrow":
                    # the ring grows from the gap: invisible until the crest gets there, never a pop to full size
                    for frame in (1, max(1, f(t_hit) - 1)):
                        out.scale = (0.0001, 0.0001, 0.0001)
                        out.keyframe_insert("scale", frame=frame)
                    out.scale = (3.4, 1, 3.4)
                else:
                    hidden_until(out, f(t_hit))
            gone_at(out, f(t_end), 2)
        # above its board, clear of the crests, which would otherwise sweep across the words
        text(f"{tag}-word", "wide gap" if tag == "wide" else "narrow gap", (-4.2, -0.3, z + h / 2 + 0.45), 0.5)
    z_mid = sum(z for _, z in panels) / len(panels) + 0.25
    s.view("wide", (0, 0, z_mid), 31.0 if mode == "both" else 17.0, -90, z_mid + 0.6)
    s.view("gap", (1.4, 0, panels[-1][1]), 10.5, -84, panels[-1][1] + 0.4)
    s.lens, s.floor_grid, s.floor_z = 45.0, 0, -40.0
    return s


# ---------------------------------------------------------------------------
# 2. a grating's beams and the lens that catches or misses them
# ---------------------------------------------------------------------------

def grating_lens(p, sec):
    """A row of fine lines splits light into a fan of beams; a lens wide enough to catch them rebuilds
    the lines on the wafer, a lens that misses them leaves only an even glow."""
    from scenes import Set
    s = Set(sec)
    mode = p.get("mode", "catch")        # catch | miss | shorten | open
    colour = EUV if p.get("light", "euv") == "euv" else DUV
    z_mask, z_lens, z_wafer = 6.2, 2.6, 0.25
    wide_deg, narrow_deg = 34.0, 14.0
    small_r, large_r = 1.25, 2.6
    theta0 = narrow_deg if mode == "catch" else wide_deg
    theta1 = narrow_deg if mode in ("catch", "shorten") else wide_deg
    lens0 = large_r if mode == "catch" else small_r
    lens1 = large_r if mode in ("catch", "open") else small_r
    F = s.frames

    # mask: a dark plate with bright slits
    kit.box("mask", (0, 0, z_mask), (5.6, 1.6, 0.16), kit.slate(), bevel=0.03)
    slits = [kit.placed((x * 0.34, -0.02, z_mask), (0.12, 1.62, 0.18)) for x in range(-4, 5)]
    slit_mat = look.neon("slits", colour, 0.6)
    kit.boxes("slits", slits, slit_mat)
    # incoming light
    beam_in = kit.box("beam-in", (0, 0, z_mask + 2.0), (3.2, 1.2, 3.8), haze("in-haze", colour, 0.0), bevel=0)
    in_mat = beam_in.data.materials[0]
    # the stop with its hole, and the lens in it
    stop_mat = kit.mid()
    stops = []
    for side in (-1, 1):
        st = kit.box(f"stop{side}", (0, 0, z_lens), (6.0, 1.7, 0.12), stop_mat, bevel=0.02)
        stops.append((st, side))

    def place_stops(r, frame):
        for st, side in stops:
            st.location = (side * (r + 3.0), 0, z_lens)
            st.keyframe_insert("location", frame=frame)
    lens = kit.cyl("lens", (0, 0, z_lens), 1.0, 0.18, haze("lens-glass", (0.55, 0.80, 1.0), 0.25), verts=64)
    lens.scale = (lens0, 1.2, 1.0)
    lens.keyframe_insert("scale", frame=1)
    rim = kit.cyl("lens-rim", (0, 0, z_lens), 1.0, 0.22, kit.mid(), verts=64)
    rim.scale = (lens0 + 0.08, 1.25, 0.6)
    rim.keyframe_insert("scale", frame=1)
    place_stops(lens0, 1)
    # wafer
    kit.cyl("wafer", (0, 0, z_wafer - 0.08), 3.4, 0.16, kit.silicon(), verts=96)
    even = kit.box("even-glow", (0, 0, z_wafer + 0.01), (3.0, 1.4, 0.02), haze("even", colour, 0.0), bevel=0)
    even_mat = even.data.materials[0]
    lines_mat = look.neon("printed", colour, 0.0, base=(0.02, 0.02, 0.03))
    printed = kit.boxes("printed", [kit.placed((x * 0.30, 0, z_wafer + 0.02), (0.13, 1.3, 0.03)) for x in range(-4, 5)], lines_mat)
    printed.location = (0, 0, 0)

    # beams from the mask: straight, and one each side at theta
    beam_mats = {k: haze(f"beam{k}", colour, 0.0) for k in (-1, 0, 1)}
    pivot = Vector((0, 0, z_mask - 0.1))
    straight = ray("beam0", 0.32, beam_mats[0], verts=16)
    aim_ray(straight, pivot, (0, 0, z_lens))
    sides = {}
    for k in (-1, 1):
        r = ray(f"beam{k}", 0.30, beam_mats[k], verts=16)
        r.location = pivot
        sides[k] = r

    def set_side(theta_deg, frame):
        t = math.radians(theta_deg)
        for k, r in sides.items():
            r.rotation_euler = (0, -k * t, 0)
            r.scale = (1, 1, (z_mask - 0.1 - z_lens) / math.cos(t))
            r.keyframe_insert("rotation_euler", frame=frame)
            r.keyframe_insert("scale", frame=frame)
    set_side(theta0, 1)
    # after the lens: rays converge on the wafer (only when caught)
    conv_mat = haze("converge", colour, 0.0)
    converge = []
    for k in (-1, 0, 1):
        theta = narrow_deg if theta1 == narrow_deg else wide_deg
        x = k * (z_mask - 0.1 - z_lens) * math.tan(math.radians(theta))
        c = ray(f"conv{k}", 0.22, conv_mat, verts=12)
        aim_ray(c, (x, 0, z_lens), (0, 0, z_wafer + 0.05))
        converge.append(c)
    catch_end = theta1 == narrow_deg or lens1 == large_r

    s.pin("mask", (2.4, -0.8, z_mask + 0.1))
    s.pin("fan", (-(z_mask - z_lens) * 0.5 * math.tan(math.radians(theta0)), -0.3, (z_mask + z_lens) / 2))
    s.pin("lens", (lens0 * 0.8, -0.6, z_lens))
    s.pin("wafer", (2.6, -1.0, z_wafer))
    s.pin("straight", (0.2, -0.3, (z_mask + z_lens) / 2 + 0.6))

    def light(t0, t1):
        span = t1 - t0
        a = f(t0)
        key_glow(in_mat, [(1, 0.0), (a, 0.0), (a + 10, 0.3)])
        key_glow(slit_mat, [(1, 0.6), (a + 6, 4.0)])
        for k, m in beam_mats.items():
            key_glow(m, [(1, 0.0), (a + 10, 0.0), (a + 22, 1.1)])
        caught_now = mode == "catch"
        if mode == "miss":
            gone_at(printed, 1, 1)
        if caught_now:
            c0 = max(a + 22, f(t0 + span * 0.8))
            hidden_until(printed, c0 + 4)
            key_glow(conv_mat, [(1, 0.0), (c0, 0.0), (c0 + 12, 1.0)])
            key_glow(lines_mat, [(1, 0.0), (c0 + 6, 0.0), (c0 + 18, 5.0)])
        else:
            key_glow(even_mat, [(1, 0.0), (a + 22, 0.0), (a + 34, 1.2)])
        if mode in ("shorten", "open"):
            b0, b1 = f(t0 + span * 0.45), f(t0 + span * 0.85)
            if mode == "shorten":
                set_side(wide_deg, b0)
                set_side(narrow_deg, b1)
            else:
                for ob, r0, r1 in ((lens, lens0, lens1), (rim, lens0 + 0.08, lens1 + 0.08)):
                    ob.keyframe_insert("scale", frame=b0)
                    ob.scale[0] = r1
                    ob.keyframe_insert("scale", frame=b1)
                place_stops(lens0, b0)
                place_stops(lens1, b1)
            key_glow(conv_mat, [(1, 0.0), (b1 - 2, 0.0), (b1 + 10, 1.0)])
            key_glow(even_mat, [(b1 - 4, 1.2), (b1 + 12, 0.0)])
            key_glow(lines_mat, [(1, 0.0), (b1 + 2, 0.0), (b1 + 16, 5.0)])
            hidden_until(printed, b1)
    s.action("light", light, at=0.05, span=max(3.0, sec * 0.7) if mode != "miss" else 2.0)
    s.view("wide", (0, 0, 3.7), 22.0, -90, 5.0)
    s.view("lens", (0, 0, 1.8), 12.0, -78, 3.6)
    s.view("mask", (0, 0, 5.2), 11.0, -102, 7.0)
    s.lens, s.floor_grid, s.floor_z = 45.0, 1.0, -0.05
    return s


# ---------------------------------------------------------------------------
# 3. the resolution formula as three knobs
# ---------------------------------------------------------------------------

def formula(p, sec):
    """The resolution limit written out, smallest feature = k1 x wavelength / NA, with a knob under
    each term; the knob being talked about turns and its term lights up."""
    from scenes import Set
    s = Set(sec)
    hi = p.get("highlight", "all")
    z = 3.2
    dim = kit.mat("formula-dim", (0.55, 0.56, 0.58), emission=0.6)
    terms = {"cd": ("smallest feature", -3.5, z), "k1": ("k₁", 1.0, z + 0.75), "lambda": ("λ", 2.25, z + 0.75),
             "na": ("NA", 1.65, z - 0.75)}
    mats = {}
    for key, (body, x, zz) in terms.items():
        m = look.neon(f"term-{key}", look.WARM, 0.0, base=(0.85, 0.85, 0.83))
        mats[key] = m
        size = 0.5 if key == "cd" else 0.95
        text(f"term-{key}", body, (x, 0, zz), size, m)
        s.pin(key, (x, -0.1, zz + 0.5))
    text("equals", "=", (-0.65, 0, z), 0.9, dim)
    text("times", "·", (1.62, 0, z + 0.78), 0.9, dim)
    kit.box("fraction-bar", (1.62, 0, z), (2.6, 0.06, 0.07), kit.mat("formula-bar", (0.85, 0.85, 0.83), emission=1.0), bevel=0)
    names = {"k1": "cleverness", "lambda": "wavelength", "na": "lens opening"}
    knobs = {}
    for k, (key, label) in enumerate(names.items()):
        x = -3.2 + k * 3.2
        kit.cyl(f"knob-base{k}", (x, 0, 0.55), 0.62, 0.16, kit.slate(), rot=(math.radians(90), 0, 0), verts=40)
        knob = kit.cyl(f"knob{k}", (x, -0.12, 0.55), 0.46, 0.22, kit.mid(), rot=(math.radians(90), 0, 0), verts=32)
        needle = kit.box(f"needle{k}", (x, -0.26, 0.82), (0.07, 0.04, 0.4), mats[key], bevel=0)
        g = kit.group(f"knob-g{k}", (knob, needle))
        g.location = (x, 0, 0.55)
        for ob in (knob, needle):
            ob.location = Vector(ob.location) - Vector((x, 0, 0.55))
        knobs[key] = g
        text(f"knob-word{k}", label, (x, -0.02, -0.35), 0.28, dim)
        s.pin(f"knob-{key}", (x, -0.3, 1.2))
    order = ["na", "k1", "lambda"] if hi == "all" else ([hi] if hi in names else [])

    def light(t0, t1):
        for key, m in mats.items():
            key_glow(m, [(1, 0.0), (f(t0), 0.0), (f(t0) + 8, 0.6 if key == "cd" else 0.25)])
        each = (t1 - t0) / max(1, len(order))
        for k, key in enumerate(order):
            a, b = f(t0 + k * each), f(t0 + (k + 0.9) * each)
            key_glow(mats[key], [(a, 0.25), (a + 8, 3.2), (b, 3.2 if key == order[-1] else 1.2)])
            g = knobs[key]
            g.keyframe_insert("rotation_euler", frame=a)
            g.rotation_euler[1] = math.radians(-120)
            g.keyframe_insert("rotation_euler", frame=b)
    s.action("light", light, at=0.06, span=max(1.5, sec * 0.75))
    s.view("wide", (0, 0, 2.3), 16.5, -90, 3.0)
    s.view("terms", (-0.6, 0, z), 11.5, -86, z + 0.6)
    s.view("knobs", (0, 0, 1.2), 11.5, -96, 2.4)
    s.lens, s.floor_grid, s.gain = 45.0, 1.0, 1.4
    return s


# ---------------------------------------------------------------------------
# 4. wavelengths side by side, to scale
# ---------------------------------------------------------------------------

def wavelengths(p, sec):
    """Waves drawn to scale, one above another: the longest on top, the shortest at the bottom."""
    from scenes import Set
    s = Set(sec)
    values = [float(v) for v in p.get("values", [436, 365, 248, 193, 13.5])][:6]
    names = [str(v) for v in p.get("names", [])]
    longest = max(values)
    width, amp = 9.0, 0.32
    n = len(values)
    def hue(v):
        if v > 400:
            return (1.0, 0.55, 0.15)
        if v > 300:
            return (0.85, 0.85, 0.30)
        if v > 220:
            return (0.35, 0.80, 1.0)
        if v > 100:
            return (0.30, 0.55, 1.0)
        return EUV
    curves = []
    for k, v in enumerate(values):
        z = 0.8 + (n - 1 - k) * 1.15
        lam = 2.6 * v / longest
        steps = max(60, int(width / lam * 14))
        a_k = amp if lam > 0.3 else 0.13
        pts = [(-4.0 + width * i / steps, 0, z + a_k * math.sin(2 * math.pi * (width * i / steps) / lam)) for i in range(steps + 1)]
        c = polyline(f"wave{k}", pts, 0.035 if lam > 0.3 else 0.012, look.neon(f"wave{k}", hue(v), 3.0))
        curves.append(c)
        label = names[k] if k < len(names) else (f"{v:g} nm")
        # the name sits above the start of its wave, inside the frame of both views
        text(f"wave-label{k}", label, (-4.0, 0, z + a_k + 0.32), 0.3, align="LEFT")
        s.pin(f"wave{k + 1}", (5.0, -0.1, z))

    def draw(t0, t1):
        each = (t1 - t0) / n
        for k, c in enumerate(curves):
            draw_curve(c, f(t0 + k * each), f(t0 + k * each + max(0.6, each * 0.9)))
    s.action("draw", draw, at=0.05, span=max(2.0, sec * 0.6))
    # framing from the 45 mm lens: tan(half fov) is 0.40 across and 0.225 up a 16:9 frame
    low, high = 0.8 - amp - 0.2, 0.8 + (n - 1) * 1.15 + amp + 0.75
    mid = (low + high) / 2
    reach = max((width / 2 + 0.7) / 0.40, ((high - low) / 2 + 0.3) / 0.225)
    s.view("wide", (0.5, 0, mid), reach, -90, mid + 0.4)
    # the close-up keeps every wave and its name, over the left third, where the cycles can be counted
    s.view("short", (-1.4, 0, mid), max(6.0, ((high - low) / 2 + 0.3) / 0.225), -84, mid + 0.5)
    s.lens, s.floor_grid, s.floor_z = 45.0, 0, -40.0
    return s


# ---------------------------------------------------------------------------
# 5. a projector printing a mask onto a wafer
# ---------------------------------------------------------------------------

def litho_exposure(p, sec):
    """Light through a mask, shrunk four times by the optics, prints the pattern into the resist on a wafer."""
    from scenes import Set
    s = Set(sec)
    colour = EUV if p.get("light", "duv") == "euv" else DUV
    z_lamp, z_mask, z_lens, z_wafer = 9.0, 7.0, 4.0, 0.3
    lamp = kit.cyl("lamp", (0, 0, z_lamp), 1.6, 0.2, look.neon("lamp", colour, 0.2), verts=48)
    lamp_mat = lamp.data.materials[0]
    kit.box("mask", (0, 0, z_mask), (4.2, 4.2, 0.12), kit.slate(), bevel=0.03)
    pattern = [kit.placed((x * 0.42, y * 0.9, z_mask + 0.07), (0.16, 0.7, 0.02)) for x in range(-4, 5) for y in (-1, 0, 1)]
    pat_mat = look.neon("mask-pattern", colour, 0.3)
    kit.boxes("mask-pattern", pattern, pat_mat)
    kit.cyl("lens", (0, 0, z_lens), 1.5, 0.5, haze("lens-glass", (0.55, 0.80, 1.0), 0.22), verts=64)
    kit.cyl("lens-rim", (0, 0, z_lens), 1.62, 0.3, kit.mid(), verts=64)
    kit.cyl("wafer", (0, 0, z_wafer - 0.1), 3.6, 0.2, kit.silicon(), verts=96)
    resist = kit.cyl("resist", (0, 0, z_wafer + 0.02), 3.55, 0.05, kit.mat("resist", (0.16, 0.09, 0.03), roughness=0.5), verts=96)
    printed_mat = look.neon("printed", colour, 0.0, base=(0.02, 0.02, 0.03))
    printed = [kit.placed((x * 0.105, y * 0.225, z_wafer + 0.06), (0.04, 0.175, 0.01)) for x in range(-4, 5) for y in (-1, 0, 1)]
    kit.boxes("printed", printed, printed_mat)
    cone_mat = haze("cone", colour, 0.0)
    top_cone = kit.cyl("cone-top", (0, 0, (z_mask + z_lens) / 2), 2.0, z_mask - z_lens, cone_mat, verts=48, radius2=1.4)
    top_cone.scale = (1, 1, 1)
    low_cone = kit.cyl("cone-low", (0, 0, (z_lens + z_wafer) / 2), 0.55, z_lens - z_wafer, cone_mat, verts=48, radius2=1.3)
    shaft = kit.cyl("shaft", (0, 0, (z_lamp + z_mask) / 2), 1.6, z_lamp - z_mask, haze("shaft", colour, 0.0), verts=48)
    shaft_mat = shaft.data.materials[0]
    s.pin("light", (1.4, -0.6, z_lamp))
    s.pin("mask", (2.0, -1.6, z_mask))
    s.pin("lens", (1.4, -0.6, z_lens))
    s.pin("resist", (3.0, -1.4, z_wafer + 0.05))
    s.pin("pattern", (0.4, -0.3, z_wafer + 0.06))

    def expose(t0, t1):
        a, b = f(t0), f(t1)
        key_glow(lamp_mat, [(1, 0.2), (a, 0.2), (a + 8, 6.0)])
        key_glow(shaft_mat, [(1, 0.0), (a + 4, 0.0), (a + 14, 0.16)])
        key_glow(pat_mat, [(1, 0.3), (a + 8, 0.3), (a + 16, 4.0)])
        key_glow(cone_mat, [(1, 0.0), (a + 12, 0.0), (a + 24, 0.16)])
        key_glow(printed_mat, [(1, 0.0), ((a + b) // 2, 0.0), (b, 6.0)])
    s.action("expose", expose, at=0.08, span=max(2.0, min(5.0, sec * 0.5)))
    s.view("wide", (0, 0, 4.6), 23.0, -96, 7.4)
    s.view("wafer", (0, 0, 0.8), 9.5, -80, 4.6)
    s.view("mask", (0, 0, 7.4), 10.5, -100, 10.2)
    s.lens, s.floor_grid, s.floor_z = 42.0, 1.2, 0.0
    return s


# ---------------------------------------------------------------------------
# 6. the tin-droplet plasma source
# ---------------------------------------------------------------------------

def _shell(name, radius, material, open_toward=(1, 0, 0), depth=0.55, thick=0.12):
    """A shallow spherical cap (the collector), its hollow side facing `open_toward`."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=128, v_segments=64, radius=radius)
    cut = [v for v in bm.verts if v.co.z > -radius * (1 - depth)]
    bmesh.ops.delete(bm, geom=cut, context="VERTS")
    bmesh.ops.solidify(bm, geom=bm.faces[:], thickness=thick)
    # a polished mirror: smooth across the bowl, sharp only at the rim where the shell turns over
    ob = kit.soften(kit._mesh_object(name, bm, material), angle=60.0)
    ob.rotation_euler = (-Vector(open_toward)).to_track_quat("-Z", "Y").to_euler()
    return ob


def tin_source(p, sec):
    """The laser-produced-plasma source as it is laid out in a production EUV scanner: a generator
    fires molten tin droplets horizontally across the vessel to a catcher; the CO2 laser comes up
    through the hole in the centre of the collector, a weak pulse flattens a droplet into a disc,
    the main pulse turns the disc into plasma, and the ellipsoidal collector, facing up, focuses the
    light to the intermediate focus above it. Droplets are drawn far larger than their 30 um."""
    from scenes import Set
    s = Set(sec)
    F = s.frames
    hit = Vector((0, 0, 4.0))                  # the primary focus of the collector, where droplets are hit
    focus = Vector((0, 0, 10.6))               # the intermediate focus, the light's exit from the source
    tin = kit.mat("tin", TIN, metallic=0.6, roughness=0.3, emission=0.35, emission_color=(1.0, 0.85, 0.65))
    # vessel floor ring, droplet generator (left) and catcher (right)
    kit.cyl("generator", (-6.4, 0, hit.z), 0.45, 1.6, kit.steel(), rot=(0, math.radians(90), 0), verts=24)
    kit.cyl("nozzle", (-5.45, 0, hit.z), 0.18, 0.4, kit.steel(), rot=(0, math.radians(90), 0), verts=16, radius2=0.06)
    kit.cyl("catcher", (6.2, 0, hit.z), 0.55, 1.2, kit.slate(), rot=(0, math.radians(90), 0), verts=24)
    # the stream: one mesh of droplets sliding one spacing to the right per cycle, forever
    spacing, speed = 0.62, 1.6
    drops = kit.balls("stream", [(-5.2 + k * spacing, 0, hit.z) for k in range(19)], 0.07, tin,
                      subdivisions=3, smooth=True)   # molten tin: surface tension makes each a sphere
    drops.keyframe_insert("location", frame=1)
    drops.location[0] = spacing
    drops.keyframe_insert("location", frame=1 + round(spacing / speed * FPS))
    for fc in drops.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
        fc.modifiers.new("CYCLES")
    # the hero droplet, held at the hit point for the close-up
    hero = kit.ico("hero", tuple(hit), 0.16, kit.mat("tin-hero", (0.85, 0.86, 0.9), metallic=0.3, roughness=0.3, emission=1.2,
                                                    emission_color=(0.9, 0.85, 0.8)), subdivisions=3, smooth=True)
    # collector: below the hit point, its hollow side up, a hole in its centre for the laser
    coll_mat = kit.mat("collector", (0.55, 0.57, 0.66), metallic=0.6, roughness=0.25)
    coll = _shell("collector", 3.0, coll_mat, open_toward=(0, 0, 1), depth=0.42)
    apex = hit - Vector((0, 0, 2.6))
    coll.location = apex + Vector((0, 0, 3.0))
    kit.cyl("collector-hole", tuple(apex + Vector((0, 0, 0.02))), 0.32, 0.08, kit.epoxy(), verts=24)
    # the CO2 laser comes up from below, through the hole
    pre_mat, main_mat = haze("pre-pulse", LASER, 0.0), haze("main-pulse", LASER, 0.0)
    pre = ray("pre", 0.05, pre_mat)
    aim_ray(pre, apex - Vector((0, 0, 3.2)), hit)
    main = ray("main", 0.13, main_mat)
    aim_ray(main, apex - Vector((0, 0, 3.2)), hit)
    # plasma and its light
    plasma_mat = haze("plasma", EUV, 0.0)
    plasma = kit.ico("plasma", tuple(hit), 0.5, plasma_mat, subdivisions=5, smooth=True)
    core_mat = look.neon("plasma-core", (0.9, 0.8, 1.0), 0.0)
    core = kit.ico("plasma-core", tuple(hit), 0.18, core_mat, subdivisions=4, smooth=True)
    cone_mat = haze("euv-cone", EUV, 0.0)
    rim_z = apex.z + 3.0 * 0.42
    rim_r = math.sqrt(3.0 ** 2 - (3.0 * 0.58) ** 2)
    length = focus.z - rim_z
    kit.cyl("euv-cone", (0, 0, rim_z + length / 2), rim_r * 0.96, length, cone_mat, verts=48, radius2=0.03)
    focus_mat = look.neon("focus", EUV, 0.0)
    kit.ico("focus", tuple(focus), 0.12, focus_mat, subdivisions=2)
    s.pin("droplet", tuple(hit + Vector((0.2, -0.3, 0.3))))
    s.pin("nozzle", (-5.6, -0.4, hit.z + 0.4))
    s.pin("catcher", (6.0, -0.5, hit.z + 0.5))
    s.pin("laser", tuple(apex + Vector((0.1, -0.2, -1.6))))
    s.pin("collector", (rim_r * 0.7, -1.4, rim_z - 0.2))
    s.pin("plasma", tuple(hit + Vector((0.2, -0.4, 0.4))))
    s.pin("focus", tuple(focus + Vector((0, -0.2, 0.2))))

    state = {}

    def pre_pulse(p0):
        key_glow(pre_mat, [(1, 0.0), (p0 - 1, 0.0), (p0, 6.0), (p0 + 4, 6.0), (p0 + 7, 0.0)])
        hero.scale = (1.0, 1.0, 1.0)
        hero.keyframe_insert("scale", frame=max(1, p0 + 2))
        hero.scale = (3.2, 3.2, 0.32)          # a disc facing the laser, which comes from below
        hero.keyframe_insert("scale", frame=p0 + 14)

    def flatten(t0, t1):
        state["p0"] = f(t0)
        pre_pulse(state["p0"])

    def ignite(t0, t1):
        p1 = max(16, f(t0))
        if state.get("p0", 10 ** 9) > p1 - 16:
            # the storyboard lit the plasma before (or without) the flattening pulse: flatten just before
            hero.animation_data_clear()
            pre_mat.node_tree.animation_data_clear()
            pre_pulse(p1 - 15)
        key_glow(main_mat, [(1, 0.0), (p1 - 1, 0.0), (p1, 12.0), (p1 + 4, 12.0), (p1 + 8, 0.0)])
        gone_at(hero, p1 + 1, 2)
        hidden_until(core, p1)
        plasma.scale = (0.2, 0.2, 0.2)
        plasma.keyframe_insert("scale", frame=p1)
        plasma.scale = (1.0, 1.0, 1.0)
        plasma.keyframe_insert("scale", frame=p1 + 8)
        key_glow(plasma_mat, [(1, 0.0), (p1, 0.0), (p1 + 2, 9.0), (p1 + 20, 3.0)])
        key_glow(core_mat, [(1, 0.0), (p1, 0.0), (p1 + 2, 30.0), (p1 + 20, 8.0)])
        key_glow(cone_mat, [(1, 0.0), (p1 + 2, 0.0), (p1 + 14, 0.055)])
        key_glow(focus_mat, [(1, 0.0), (p1 + 6, 0.0), (p1 + 16, 12.0)])
        # after the first, it keeps happening: a flicker as fast as the frame rate allows
        keys_p, keys_c, keys_m = [], [], []
        frame = p1 + 24
        on = True
        while frame < F:
            keys_p.append((frame, 4.0 if on else 1.6))
            keys_c.append((frame, 14.0 if on else 4.0))
            keys_m.append((frame, 4.0 if on else 0.0))
            on = not on
            frame += 2
        key_glow(plasma_mat, keys_p)
        key_glow(core_mat, keys_c)
        key_glow(main_mat, keys_m)
    s.action("flatten", flatten, at=0.15, span=0.6)
    s.action("ignite", ignite, at=0.45, span=0.6)
    s.view("wide", (0, 0, 5.4), 25.0, -92, 7.0)
    s.view("droplet", tuple(hit), 5.2, -72, hit.z + 1.1)
    s.view("collector", (0, 0, 2.6), 10.5, -100, 8.0)
    s.lens, s.floor_grid, s.floor_z, s.gain = 45.0, 0, -6.0, 1.2
    return s


# ---------------------------------------------------------------------------
# 7. a multilayer (Bragg) mirror
# ---------------------------------------------------------------------------

def bragg_mirror(p, sec):
    """A cut through a multilayer mirror: every boundary reflects a weak wave, all of them leave in
    step, and together they make one strong reflection."""
    from scenes import Set
    s = Set(sec)
    pairs = max(3, min(12, int(p.get("pairs", 8))))
    lam = 0.9
    angle = math.radians(20)            # from the surface normal
    period = lam / (2 * math.cos(angle))    # every boundary pair adds exactly one wavelength of path
    width = 9.0
    moly = kit.mat("molybdenum", (0.10, 0.11, 0.13), metallic=0.6, roughness=0.35)
    sili = kit.mat("silicon-layer", (0.62, 0.66, 0.74), metallic=0.1, roughness=0.5, emission=0.25)
    top = 3.6
    kit.box("substrate", (0, 0, top - pairs * period - 0.6), (width, 1.2, 1.2), kit.slate(), bevel=0.02)
    boundaries = []
    for k in range(pairs):
        z = top - k * period
        kit.box(f"si{k}", (0, 0, z - period * 0.3), (width, 1.2, period * 0.6), sili, bevel=0)
        kit.box(f"mo{k}", (0, 0, z - period * 0.8), (width, 1.2, period * 0.4), moly, bevel=0)
        boundaries.append(z)
    d_in = Vector((math.sin(angle), 0, -math.cos(angle)))
    d_out = Vector((math.sin(angle), 0, math.cos(angle)))
    entry_x = -1.6
    in_mat = look.neon("incoming", EUV, 2.6)
    # the incoming wave: a sine along d_in ending at the first boundary
    def sine(start, direction, length, amp, phase, steps=120):
        side = Vector((direction.z, 0, -direction.x))
        return [tuple(start + direction * (length * i / steps) + side * amp * math.sin(2 * math.pi * (length * i / steps) / lam + phase))
                for i in range(steps + 1)]
    hit0 = Vector((entry_x, -0.62, top))
    start = hit0 - d_in * 5.0
    incoming = polyline("incoming", sine(start, d_in, 5.0, 0.16, 0.0), 0.03, in_mat)
    straight_in = ray("in-ray", 0.03, look.neon("in-ray", EUV, 1.2))
    aim_ray(straight_in, start + Vector((0, 0.05, 0)), hit0 + Vector((0, 0.05, 0)))
    # the path inside the stack, and one weak reflection at each boundary
    partial = []
    for k, z in enumerate(boundaries):
        x = entry_x + (top - z) * math.tan(angle)
        p0 = Vector((x, -0.62, z))
        # phase chosen so crests line up across the parallel waves: it depends on where along d_out they sit
        phase = -2 * math.pi * (p0.dot(d_out)) / lam
        m = look.neon(f"echo{k}", EUV, 0.0)
        c = polyline(f"echo{k}", sine(p0, d_out, 5.0 + (top - z) / math.cos(angle), 0.06, phase), 0.018, m)
        partial.append((c, m))
    inside = ray("inside", 0.02, look.neon("inside", EUV, 0.8))
    aim_ray(inside, hit0, Vector((entry_x + (top - boundaries[-1]) * math.tan(angle), -0.62, boundaries[-1])))
    strong_mat = look.neon("strong", EUV, 0.0)
    out0 = hit0 + d_out * 5.6
    strong = polyline("strong", sine(out0, d_out, 3.4, 0.30, -2 * math.pi * out0.dot(d_out) / lam), 0.05, strong_mat)
    s.pin("incoming", tuple(start + d_in * 1.5 + Vector((0, -0.1, 0))))
    s.pin("layers", (3.2, -0.7, top - pairs * period / 2))
    s.pin("molybdenum", (-3.6, -0.7, top - period * 0.8))
    s.pin("silicon", (-3.0, -0.7, top - period * 1.3))
    s.pin("reflected", tuple(out0 + d_out * 1.5 + Vector((0, -0.1, 0))))

    def reflect(t0, t1):
        a, b = f(t0), f(t1)
        draw_curve(incoming, 1, a)
        each = max(4, (b - a) // (len(partial) + 2))
        for k, (c, m) in enumerate(partial):
            fk = a + k * each
            key_glow(m, [(1, 0.0), (fk, 0.0), (fk + 4, 2.2)])
            draw_curve(c, fk, fk + each * 2)
        fs = a + len(partial) * each
        draw_curve(strong, fs, fs + each * 2)
        key_glow(strong_mat, [(1, 0.0), (fs, 0.0), (fs + 8, 5.0)])
    s.action("reflect", reflect, at=0.1, span=max(3.0, sec * 0.6))
    s.view("wide", (0.8, 0, 4.4), 19.0, -90, 4.8)
    s.view("layers", (-1.4, 0, top - 0.8), 7.0, -80, top + 0.4)
    s.lens, s.floor_grid, s.floor_z = 45.0, 0, -40.0
    return s


# ---------------------------------------------------------------------------
# 8. the light path through a scanner
# ---------------------------------------------------------------------------

LIGHT_PATH = [  # (name, point) in order; the mask is lit at about 6 degrees, as in a real scanner
    ("source", (-8.4, 0, 1.8)), ("collector", (-9.6, 0, 1.8)), ("focus", (-5.2, 0, 3.6)),
    ("illuminator1", (-3.4, 0, 1.4)), ("illuminator2", (-2.0, 0, 5.0)), ("illuminator3", (-2.8, 0, 7.4)),
    ("illuminator4", (-0.40, 0, 5.6)), ("mask", (0.0, 0, 9.4)),
    ("projection1", (0.42, 0, 5.4)), ("projection2", (2.6, 0, 7.9)), ("projection3", (4.0, 0, 5.0)),
    ("projection4", (2.0, 0, 3.6)), ("projection5", (4.6, 0, 2.6)), ("projection6", (2.4, 0, 1.6)),
    ("wafer", (3.2, 0, 0.3)),
]


def light_path(p, sec):
    """The route the light takes: source, collector, illuminator mirrors, the mask, six projection
    mirrors, the wafer. Each bounce keeps about seventy percent, so the beam fades as it goes."""
    from scenes import Set
    s = Set(sec)
    keep = float(p.get("keep", 0.7))
    pts = [Vector(pt) for _, pt in LIGHT_PATH]
    names = [n for n, _ in LIGHT_PATH]
    # source vessel and plasma
    kit.ico("plasma", tuple(pts[0]), 0.22, look.neon("plasma", (0.9, 0.8, 1.0), 14.0), subdivisions=2, smooth=True)
    coll = _shell("collector", 2.0, kit.mat("collector", (0.55, 0.57, 0.66), metallic=0.6, roughness=0.25), open_toward=(1, 0, 0.35))
    coll.location = pts[1]
    # mirrors at each bounce
    segs = []
    bounces = 0
    for k in range(1, len(pts)):
        a, b = pts[k - 1], pts[k]
        strength = 3.2 * (keep ** bounces)
        m = haze(f"seg{k}", EUV, strength)
        r = ray(f"seg{k}", 0.09 if k > 1 else 0.16, m, verts=12)
        aim_ray(r, a, b)
        segs.append((r, m, strength))
        if names[k].startswith(("illuminator", "projection")):
            mirror_at(names[k], b, b - a, pts[k + 1] - b, width=1.2)
            bounces += 1
        if names[k] == "collector":
            bounces += 1
    # the mask (pattern side down) and the wafer
    mask = kit.box("mask-plate", (pts[7].x, 0, pts[7].z + 0.12), (2.6, 2.0, 0.24), kit.slate(), bevel=0.03)
    kit.boxes("mask-lines", [kit.placed((pts[7].x + x * 0.22, -0.0, pts[7].z - 0.005), (0.1, 1.8, 0.02)) for x in range(-5, 6)],
              look.neon("mask-lines", EUV, 0.8))
    kit.cyl("wafer", (pts[-1].x, 0, pts[-1].z - 0.1), 2.0, 0.16, kit.silicon(), verts=96)
    kit.box("vacuum", (-2.0, 0.9, 4.8), (17.0, 0.1, 10.4), kit.mat("vacuum-wall", (0.02, 0.025, 0.035), roughness=0.9), bevel=0.02)
    # anchors
    s.pin("source", tuple(pts[0] + Vector((0.2, -0.4, 0.5))))
    s.pin("collector", tuple(pts[1] + Vector((0, -1.0, 1.4))))
    s.pin("illuminator", tuple(pts[4] + Vector((0, -0.5, 0.3))))
    s.pin("mask", tuple(pts[7] + Vector((1.0, -0.8, 0.3))))
    s.pin("projection", tuple(pts[10] + Vector((0.3, -0.5, 0.3))))
    s.pin("wafer", tuple(pts[-1] + Vector((1.4, -1.0, 0.1))))

    def travel(t0, t1):
        a, b = f(t0), f(t1)
        each = max(3, (b - a) // len(segs))
        for k, (r, m, strength) in enumerate(segs):
            grow_ray(r, a + k * each, a + (k + 1) * each)
    s.action("travel", travel, at=0.05, span=max(3.0, sec * 0.7))
    s.view("wide", (-1.6, 0, 4.7), 27.5, -90, 5.4)
    s.view("source", (-7.8, 0, 2.6), 8.0, -110, 4.2)
    s.view("projection", (2.8, 0, 4.6), 10.0, -76, 6.0)
    s.view("mask", (0.2, 0, 8.6), 7.5, -100, 9.6)
    s.lens, s.floor_grid, s.floor_z = 40.0, 1.4, -0.2
    return s


# ---------------------------------------------------------------------------
# 9. the scan: mask and wafer moving opposite ways through a slit
# ---------------------------------------------------------------------------

def _arc_band(name, radius, chord, width, z, material, segments=24):
    """A thin curved band in the XY plane, convex toward +X: the ring-field slit of an EUV scanner."""
    half = math.asin(min(0.99, chord / 2 / radius))
    bm = bmesh.new()
    rows = []
    for k in range(segments + 1):
        a = -half + 2 * half * k / segments
        rows.append([bm.verts.new((r * math.cos(a) - radius, r * math.sin(a), z)) for r in (radius - width / 2, radius + width / 2)])
    for k in range(segments):
        bm.faces.new((rows[k][0], rows[k + 1][0], rows[k + 1][1], rows[k][1]))
    bmesh.ops.solidify(bm, geom=bm.faces[:], thickness=0.02)
    return kit._mesh_object(name, bm, material)


def scanner(p, sec):
    """A step-and-scan exposure as it happens in an EUV scanner. The mask (four times the field) and the
    wafer move in opposite directions, the mask four times faster, through a fixed, curved slit of
    light; the projection optics sit between them. After each field the wafer steps sideways to the
    next one and the scan runs back the other way. Fields are 26 x 33 mm on a 300 mm wafer."""
    from scenes import Set
    s = Set(sec)
    z_mask, z_wafer = 6.6, 0.4
    ratio = 4.0
    unit = 3.0 / 150.0                 # scene units per millimetre: the wafer is 300 mm across
    fw, fd = 33 * unit, 26 * unit      # field length along the scan (x) and across it (y)
    # the mask stage above, the projection optics in the middle, the wafer stage below
    kit.box("mask-stage", (0, 0, z_mask + 0.38), (16.0, 3.4, 0.25), kit.slate(), bevel=0.04)
    mask = kit.box("mask", (0, 0, z_mask), (fw * ratio, fd * ratio, 0.16), kit.mid(), bevel=0.03)
    mlines = kit.boxes("mask-lines", [kit.placed((x * 0.22, 0, z_mask - 0.09), (0.08, fd * ratio * 0.9, 0.02)) for x in range(-5, 6)],
                       look.neon("mask-lines", EUV, 1.6))
    mask_g = kit.group("mask-g", (mask, mlines))
    kit.cyl("optics-housing", (0, 0, 3.4), 1.7, 3.4, kit.mat("housing", (0.07, 0.075, 0.085), metallic=0.4, roughness=0.5), verts=48)
    kit.cyl("optics-ring-top", (0, 0, 5.12), 1.78, 0.08, kit.mid(), verts=48)
    kit.cyl("optics-ring-low", (0, 0, 1.68), 1.78, 0.08, kit.mid(), verts=48)
    kit.box("wafer-stage", (0, 0, z_wafer - 0.35), (12.0, 7.6, 0.3), kit.slate(), bevel=0.04)
    wafer = kit.cyl("wafer", (0, 0, z_wafer - 0.08), 3.0, 0.16, kit.silicon(), verts=96)
    fields = []
    grid_mat = kit.mat("field-outline", (0.20, 0.22, 0.26), roughness=0.6)
    bgs = []
    cols, rows = 9, 11
    for c in range(cols):
        for r in range(rows):
            x, y = (c - (cols - 1) / 2) * (fw + 0.015), (r - (rows - 1) / 2) * (fd + 0.015)
            corners = [(x + sx * fw / 2, y + sy * fd / 2) for sx in (-1, 1) for sy in (-1, 1)]
            if max(math.hypot(cx, cy) for cx, cy in corners) > 2.92:
                continue
            bgs.append(kit.box(f"field-bg{c}-{r}", (x, y, z_wafer + 0.005), (fw, fd, 0.01), grid_mat, bevel=0))
            m = look.neon(f"field{c}-{r}", EUV, 0.0, base=(0.02, 0.02, 0.03))
            done = kit.box(f"field{c}-{r}", (x, y, z_wafer + 0.015), (fw, fd, 0.012), m, bevel=0)
            fields.append((c, r, x, y, done, m))
    wafer_g = kit.group("wafer-g", [wafer] + [q[4] for q in fields] + bgs)
    # the slit: fixed in space, curved, as wide as a field; lit on the mask and imaged on the wafer
    slit_mat = look.neon("slit", EUV, 6.0)
    _arc_band("slit-mask", 0.9 * ratio, fd * ratio, 0.10 * ratio, z_mask - 0.12, slit_mat)
    _arc_band("slit-wafer", 0.9, fd, 0.06, z_wafer + 0.03, slit_mat)
    beam_mat = haze("slit-beams", EUV, 0.35)
    up = ray("beam-in", 0.10, beam_mat)
    aim_ray(up, (-0.6, 0, 5.2), (-0.0, 0, z_mask - 0.12))       # into the mask at a few degrees
    down = ray("beam-out", 0.10, beam_mat)
    aim_ray(down, (0.0, 0, z_mask - 0.12), (0.5, 0, 5.2))
    low = ray("beam-wafer", 0.07, beam_mat)
    aim_ray(low, (0, 0, 1.68), (0, 0, z_wafer + 0.04))
    s.pin("mask", (2.6, -1.6, z_mask + 0.2))
    s.pin("slit", (0.1, -0.6, z_wafer + 0.06))
    s.pin("optics", (1.6, -1.2, 3.8))
    s.pin("wafer", (2.4, -2.4, z_wafer))
    s.pin("field", (0.0, -0.3, z_wafer + 0.05))

    def scan(t0, t1):
        a, b = f(t0), f(t1)
        order = sorted(fields, key=lambda q: (q[0], q[1] if q[0] % 2 == 0 else -q[1]))
        start = min(range(len(order)), key=lambda i: math.hypot(order[i][2], order[i][3]))
        order = order[start:] + order[:start]           # begin near the middle of the wafer, where the camera is
        sweep, step = 20, 8
        frame = a
        direction = 1
        for c, r, x, y, done, m in order:
            if frame + sweep >= b:
                break
            wafer_g.location = (-x - direction * fw / 2, -y, 0)
            wafer_g.keyframe_insert("location", frame=frame)
            mask_g.location = (direction * fw / 2 * ratio, 0, 0)
            mask_g.keyframe_insert("location", frame=frame)
            wafer_g.location = (-x + direction * fw / 2, -y, 0)
            wafer_g.keyframe_insert("location", frame=frame + sweep)
            mask_g.location = (-direction * fw / 2 * ratio, 0, 0)
            mask_g.keyframe_insert("location", frame=frame + sweep)
            key_glow(m, [(1, 0.0), (frame, 0.0), (frame + sweep, 1.4)])
            frame += sweep + step
            direction = -direction
        for ob in (wafer_g, mask_g):
            if ob.animation_data and ob.animation_data.action:
                for fc in ob.animation_data.action.fcurves:
                    for kp in fc.keyframe_points:
                        kp.interpolation = "LINEAR"
    s.action("scan", scan, at=0.04, span=max(3.0, sec * 0.92))
    s.view("wide", (0, 0, 3.5), 20.0, -100, 8.0)
    s.view("wafer", (0, 0, 0.5), 7.0, -80, 4.2)
    s.view("mask", (0, 0, 6.4), 9.0, -100, 5.2)
    s.lens, s.floor_grid, s.floor_z = 42.0, 1.2, 0.0
    return s


# ---------------------------------------------------------------------------
# 10. photons landing at random
# ---------------------------------------------------------------------------

def photon_rain(p, sec):
    """Photons fall at random on a grid of resist; each square brightens with what it caught. With few
    photons per square the counts are uneven, and the printed line comes out ragged."""
    from scenes import Set
    s = Set(sec)
    few = p.get("photons", "few") == "few"
    per_tile = 16.0 if few else 60.0      # absorbed photons per square, EUV and deep UV
    n = 14
    cell = 0.42
    rng = random.Random(int(p.get("seed", 11)))
    line_cols = range(5, 9)                       # the open line in the mask
    tiles = {}
    board = kit.box("board", (0, 0, -0.06), (n * cell + 0.3, n * cell + 0.3, 0.1), kit.slate(), bevel=0.02)
    for i in range(n):
        for j in range(n):
            m = look.neon(f"tile{i}-{j}", EUV, 0.0, base=(0.05, 0.05, 0.07))
            ob = kit.box(f"tile{i}-{j}", ((i - n / 2 + 0.5) * cell, (j - n / 2 + 0.5) * cell, 0.02), (cell * 0.92, cell * 0.92, 0.04), m, bevel=0)
            tiles[(i, j)] = (ob, m)
    # the mask over the board: dark bars everywhere except the line
    kit.box("mask-left", ((-n / 2 + 2.5) * cell, 0, 3.4), (5 * cell, n * cell, 0.08), kit.mat("mask-dark", (0.03, 0.03, 0.04), roughness=0.7), bevel=0)
    kit.box("mask-right", ((n / 2 - 2.5) * cell, 0, 3.4), (5 * cell, n * cell, 0.08), kit.mat("mask-dark", (0.03, 0.03, 0.04), roughness=0.7), bevel=0)
    text("label", "few photons" if few else "many photons", (0, -n * cell / 2 - 0.4, 3.9), 0.35)
    s.pin("line", (0.2, -n * cell / 2 + 0.4, 0.1))
    s.pin("tile", ((7 - n / 2 + 0.5) * cell, (-n / 2 + 2.5) * cell, 0.1))
    s.pin("mask", ((-n / 2 + 1.5) * cell, -n * cell / 2 + 0.3, 3.45))
    photon_mat = look.neon("photon", EUV, 8.0)

    def rain(t0, t1):
        a, b = f(t0), f(t1)
        counts = {k: 0 for k in tiles}
        keys = {k: [(1, 0.0)] for k in tiles}
        batches = max(1, (b - a) // 3)
        expected = per_tile * len(line_cols) * n
        per_batch = expected / batches
        fall = 18
        for k in range(batches):
            land = a + k * 3 + fall
            if land >= s.frames - 2:
                break
            hits = []
            for _ in range(int(per_batch) + (1 if rng.random() < per_batch % 1 else 0)):
                i = rng.choice(list(line_cols))
                j = rng.randrange(n)
                hits.append((i, j))
            if not hits:
                continue
            pts = [((i - n / 2 + 0.5) * cell + rng.uniform(-0.15, 0.15), (j - n / 2 + 0.5) * cell + rng.uniform(-0.15, 0.15), 3.3)
                   for i, j in hits]
            batch = kit.balls(f"photons{k}", pts, 0.035, photon_mat)
            batch.keyframe_insert("location", frame=max(1, land - fall))
            batch.location[2] = -3.28
            batch.keyframe_insert("location", frame=land)
            hidden_until(batch, max(2, land - fall))
            gone_at(batch, land, 1)
            for hit in hits:
                counts[hit] += 1
                keys[hit].append((land, 0.0))
        for key, (ob, m) in tiles.items():
            if len(keys[key]) == 1:
                continue
            running, out = 0, [(1, 0.0)]
            for frame, _ in keys[key][1:]:
                running += 1
                out.append((frame, min(6.0, 1.6 * running / per_tile)))
            key_glow(m, out)
        s._counts = counts
    s.action("rain", rain, at=0.04, span=max(2.5, min(sec * 0.62, 7.0)))

    def develop(t0, t1):
        a = f(t0)
        counts = getattr(s, "_counts", {})
        for key, (ob, m) in tiles.items():
            c = counts.get(key, 0)
            if key[0] not in line_cols:
                continue
            printed = c >= per_tile * 0.6
            ob.keyframe_insert("location", frame=a)
            ob.location[2] = 0.12 if printed else -0.01
            ob.keyframe_insert("location", frame=a + 10)
            key_glow(m, [(a, min(6.0, 1.6 * c / per_tile)), (a + 10, 3.0 if printed else 0.05)])
    s.action("develop", develop, at=0.72, span=1.0)
    s.view("wide", (0, 0, 1.0), 11.5, -100, 7.4)
    s.view("close", (0.4, 0, 0.1), 5.2, -84, 2.8)
    s.lens, s.floor_grid, s.floor_z = 42.0, 1.0, -0.12
    return s


SCENES = {
    "wave-slit": wave_slit, "grating-lens": grating_lens, "formula": formula, "wavelengths": wavelengths,
    "litho-exposure": litho_exposure, "tin-source": tin_source, "bragg-mirror": bragg_mirror,
    "light-path": light_path, "scanner": scanner, "photon-rain": photon_rain,
}
