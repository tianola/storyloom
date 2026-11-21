"""Characters: the little people (and one little word) who walk the viewer through a machine.

A storyboard does not need them to explain anything; they are there so the picture has someone in it.
Three kinds, all in one soft, rounded style so they sit together in a shot:

  person(...)   a small figure with a big head: a worker in a hard hat at a desk, or an explorer
                with a headlamp and a backpack. Poses: stand, point, sit, work, wait, sleep.
  token(...)    a round creature carrying one token of text on a name plate, and its id.
  truck(...)    a little delivery truck whose load is glowing blocks of numbers.

All are built in local space under one empty, facing -Y (towards the camera), one unit tall-ish at
scale 1, so a scene places them with a location, a facing angle and a scale.
"""
import math
import random

import bpy
from mathutils import Vector

import kit
import look
from kit import FPS

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2] / "pixel"))

SKIN = (0.66, 0.47, 0.35)
COOL_INK = (0.45, 0.85, 1.0)
OUTFITS = {
    "worker": {"body": (0.10, 0.22, 0.42), "hat": (0.95, 0.62, 0.06), "trim": (0.85, 0.85, 0.80)},
    "explorer": {"body": (0.20, 0.27, 0.13), "hat": (0.80, 0.72, 0.55), "trim": (0.45, 0.22, 0.08)},
}


def _mats(outfit):
    o = OUTFITS[outfit]
    return {
        "skin": kit.mat("ch-skin", SKIN, roughness=0.7),
        "body": kit.mat(f"ch-body-{outfit}", o["body"], roughness=0.75),
        "hat": kit.mat(f"ch-hat-{outfit}", o["hat"], roughness=0.45),
        "trim": kit.mat(f"ch-trim-{outfit}", o["trim"], roughness=0.7),
        "eye": kit.mat("ch-eye", (0.015, 0.015, 0.02), roughness=0.15),
        "shoe": kit.mat("ch-shoe", (0.04, 0.035, 0.03), roughness=0.6),
        "legs": kit.mat("ch-legs", (0.06, 0.065, 0.08), roughness=0.8),
    }


def _ball(name, loc, r, material, scale=(1, 1, 1), sub=3):
    ob = kit.ico(name, loc, r, material, subdivisions=sub, smooth=True)
    ob.scale = scale
    return ob


def _limb(name, points, r, material):
    """A bent arm or leg: rods between the points, a ball at every joint so it reads as one piece."""
    parts = []
    for i in range(len(points) - 1):
        parts.append(kit.soften(kit.rod(f"{name}-{i}", points[i], points[i + 1], r, material, verts=12)))
    for i, p in enumerate(points[1:-1]):
        parts.append(_ball(f"{name}-j{i}", p, r, material, sub=2))
    return parts


# arm poses in the torso's own space: (shoulder, elbow, hand) per side, x>0 is the figure's left
ARMS = {
    "stand": lambda sx: ((sx * 0.2, 0, 0.42), (sx * 0.26, 0.0, 0.2), (sx * 0.27, -0.02, 0.0)),
    "point": lambda sx: ((sx * 0.2, 0, 0.42), (sx * 0.4, -0.2, 0.56), (sx * 0.58, -0.38, 0.76)) if sx < 0
    else ((sx * 0.2, 0, 0.42), (sx * 0.26, 0.0, 0.2), (sx * 0.27, -0.02, 0.0)),
    "sit": lambda sx: ((sx * 0.2, 0, 0.42), (sx * 0.27, -0.08, 0.2), (sx * 0.2, -0.3, 0.12)),
    "work": lambda sx: ((sx * 0.2, 0, 0.42), (sx * 0.26, -0.14, 0.22), (sx * 0.14, -0.44, 0.26)),
    "wait": lambda sx: ((sx * 0.2, 0, 0.42), (sx * 0.2, -0.36, 0.2), (sx * 0.06, -0.22, 0.52)) if sx < 0
    else ((sx * 0.2, 0, 0.42), (sx * 0.26, -0.14, 0.22), (sx * 0.16, -0.44, 0.24)),
    "sleep": lambda sx: ((sx * 0.2, 0, 0.42), (sx * 0.3, -0.2, 0.46), (sx * 0.1, -0.24, 0.66)),
}
LEAN = {"stand": 0, "point": -4, "sit": 4, "work": 12, "wait": 18, "sleep": 58}


def person(name, loc, *, pose="stand", outfit="worker", facing=0.0, scale=1.0):
    """A small figure, about 1.25 units tall standing. Seated poses (sit, work, wait, sleep) put it on
    a stool whose top is at 0.42, ready for a desk top at 0.62 just in front of it (y from -0.2 to -0.8).
    Returns the group; `group["head"]` is the head, for a pin."""
    m = _mats(outfit)
    seated = pose in ("sit", "work", "wait", "sleep")
    hip = 0.44 if seated else 0.52
    parts = []
    for sx in (-1, 1):
        if seated:
            knee, ankle = (sx * 0.1, -0.3, hip), (sx * 0.1, -0.32, 0.08)
            parts += _limb(f"{name}-leg{sx}", [(sx * 0.1, 0, hip), knee, ankle], 0.065, m["legs"])
            shoe = (sx * 0.1, -0.38, 0.05)
        else:
            parts += _limb(f"{name}-leg{sx}", [(sx * 0.1, 0, hip), (sx * 0.1, 0, 0.08)], 0.07, m["legs"])
            shoe = (sx * 0.1, -0.05, 0.05)
        parts.append(_ball(f"{name}-shoe{sx}", shoe, 0.09, m["shoe"], scale=(0.8, 1.3, 0.55), sub=2))
    if seated:
        parts.append(kit.cyl(f"{name}-stool", (0, 0.04, 0.2), 0.2, 0.4, kit.steel(), verts=20, radius2=0.14))
        parts.append(kit.cyl(f"{name}-seat", (0, 0.04, hip - 0.05), 0.22, 0.05, kit.slate(), verts=24))

    upper = []
    torso = kit.cyl(f"{name}-torso", (0, 0, 0.24), 0.2, 0.5, m["body"], verts=24, radius2=0.16)
    upper += [torso, _ball(f"{name}-belly", (0, 0, 0.04), 0.2, m["body"], scale=(1, 0.85, 0.6))]
    upper.append(_ball(f"{name}-shoulders", (0, 0, 0.44), 0.18, m["body"], scale=(1.15, 0.85, 0.5)))
    head_z = 0.74
    head = _ball(f"{name}-head", (0, 0, head_z), 0.22, m["skin"], scale=(1, 0.95, 1.02))
    upper.append(head)
    # eyes: open dots, or closed lines when asleep
    for sx in (-1, 1):
        if pose == "sleep":
            lid = kit.box(f"{name}-lid{sx}", (sx * 0.075, -0.205, head_z - 0.01), (0.07, 0.02, 0.014), m["eye"], bevel=0.005)
            upper.append(lid)
        else:
            upper.append(_ball(f"{name}-eye{sx}", (sx * 0.075, -0.195, head_z - 0.005), 0.036, m["eye"],
                               scale=(1, 0.6, 1.25 if pose != "wait" else 0.7), sub=2))
    upper.append(kit.box(f"{name}-mouth", (0, -0.205, head_z - 0.09), (0.06 if pose != "point" else 0.08, 0.02, 0.014),
                         m["eye"], bevel=0.005))
    if outfit == "worker":
        upper.append(_ball(f"{name}-hat", (0, 0.01, head_z + 0.12), 0.225, m["hat"], scale=(1, 1, 0.7)))
        upper.append(kit.cyl(f"{name}-brim", (0, -0.02, head_z + 0.115), 0.25, 0.025, m["hat"], verts=32))
        upper.append(kit.box(f"{name}-strap", (0, 0.0, 0.3), (0.3, 0.02, 0.05), m["trim"], bevel=0.01))
    else:
        upper.append(_ball(f"{name}-hat", (0, 0.01, head_z + 0.12), 0.225, m["hat"], scale=(1, 1, 0.6)))
        upper.append(kit.cyl(f"{name}-brim", (0, 0, head_z + 0.115), 0.31, 0.025, m["hat"], verts=32))
        lamp = kit.cyl(f"{name}-lamp", (0, -0.235, head_z + 0.17), 0.045, 0.05, look.neon("ch-lamp", (1.0, 0.92, 0.7), 6.0),
                       rot=(math.pi / 2, 0, 0), verts=16)
        upper.append(lamp)
        upper.append(kit.box(f"{name}-pack", (0, 0.22, 0.28), (0.3, 0.16, 0.36), m["trim"], bevel=0.05))
        upper.append(kit.box(f"{name}-scarf", (0, -0.02, 0.5), (0.3, 0.3, 0.06), kit.mat("ch-scarf", (0.95, 0.45, 0.08), roughness=0.6), bevel=0.03))
    for sx in (-1, 1):
        sh, el, hand = ARMS[pose](sx)
        upper += _limb(f"{name}-arm{sx}", [sh, el, hand], 0.055, m["body"])
        upper.append(_ball(f"{name}-hand{sx}", hand, 0.065, m["skin"], sub=2))
    pivot = kit.group(f"{name}-upper", upper)
    pivot.location = (0, 0, hip)
    pivot.rotation_euler = (math.radians(LEAN[pose]), 0, 0)
    g = kit.group(name, parts + [pivot])
    g.location = loc
    g.rotation_euler = (0, 0, facing)
    g.scale = (scale, scale, scale)
    g["head"] = head.name
    return g


def desk(name, loc, cells_material, facing=0.0, scale=1.0):
    """A worker's desk: a console whose top is a little grid of multiplier cells (they glow when busy)."""
    top = kit.box(f"{name}-top", (0, -0.5, 0.6), (0.9, 0.6, 0.05), kit.mat("ch-desk", (0.13, 0.15, 0.18), metallic=0.3, roughness=0.5), bevel=0.02)
    body = kit.box(f"{name}-body", (0, -0.5, 0.29), (0.86, 0.56, 0.58), kit.mat("ch-desk-body", (0.07, 0.08, 0.10), roughness=0.6), bevel=0.02)
    cells = kit.boxes(f"{name}-cells", [kit.placed((-0.33 + i * 0.095, -0.66 + j * 0.095, 0.63), (0.075, 0.075, 0.012))
                                        for i in range(8) for j in range(3)], cells_material)
    g = kit.group(name, [top, body, cells])
    g.location = loc
    g.rotation_euler = (0, 0, facing)
    g.scale = (scale, scale, scale)
    return g


def token(name, loc, word="cat", number="9059", *, color=(0.98, 0.52, 0.10), facing=0.0, scale=1.0, look_up=False):
    """A round creature carrying one token: the word on a name plate on its belly, its id under it."""
    body_m = kit.mat(f"ch-token-{name}", color, roughness=0.45, emission=0.12, emission_color=color)
    white = kit.mat("ch-white", (0.92, 0.91, 0.88), roughness=0.4)
    dark = kit.mat("ch-eye", (0.015, 0.015, 0.02), roughness=0.15)
    parts = [_ball(f"{name}-body", (0, 0, 0.55), 0.5, body_m, scale=(1, 0.92, 0.96), sub=4)]
    up = 0.06 if look_up else 0.0
    for sx in (-1, 1):
        parts.append(_ball(f"{name}-eyew{sx}", (sx * 0.17, -0.4, 0.72 + up), 0.13, white, sub=3))
        parts.append(_ball(f"{name}-pupil{sx}", (sx * 0.16, -0.51, 0.74 + up * 1.6), 0.065, dark, sub=2))
        parts.append(_ball(f"{name}-foot{sx}", (sx * 0.2, -0.08, 0.06), 0.13, body_m, scale=(1, 1.4, 0.55), sub=2))
        parts.append(_ball(f"{name}-ear{sx}", (sx * 0.3, 0.0, 1.0), 0.1, body_m, scale=(0.8, 0.6, 1.3), sub=2))
    parts.append(kit.box(f"{name}-smile", (0, -0.47, 0.56 + up), (0.12, 0.02, 0.02), dark, bevel=0.008))
    plate_w = max(0.42, 0.13 * len(word) + 0.14)
    glow = kit.mat("ch-plate-ink", (0.95, 0.95, 0.93), emission=1.6)
    parts.append(kit.box(f"{name}-plate", (0, -0.49, 0.33), (plate_w, 0.03, 0.26), kit.mat("ch-plate", (0.03, 0.035, 0.045), roughness=0.4), bevel=0.04))
    word_ob = kit.flat_text(f"{name}-word", word, (0, -0.51, 0.37), 0.16, glow, rot=(math.pi / 2, 0, 0))
    num_ob = kit.flat_text(f"{name}-id", number, (0, -0.51, 0.265), 0.08, kit.mat("ch-plate-num", COOL_INK, emission=1.4), rot=(math.pi / 2, 0, 0))
    parts += [word_ob, num_ob]
    g = kit.group(name, parts)
    g.location = loc
    g.rotation_euler = (0, 0, facing)
    g.scale = (scale, scale, scale)
    return g


def truck(name, loc, load_material, *, facing=0.0, scale=1.0):
    """A small flatbed truck, cab at +X, its load a stack of glowing blocks of numbers."""
    paint = kit.mat("ch-truck", (0.92, 0.92, 0.88), roughness=0.4)
    glass = kit.mat("ch-glass", (0.05, 0.08, 0.12), metallic=0.2, roughness=0.15)
    tyre = kit.mat("ch-tyre", (0.02, 0.02, 0.025), roughness=0.8)
    parts = [kit.box(f"{name}-chassis", (0, 0, 0.22), (1.5, 0.62, 0.12), kit.slate(), bevel=0.03),
             kit.box(f"{name}-cab", (0.55, 0, 0.5), (0.42, 0.6, 0.48), paint, bevel=0.08),
             kit.box(f"{name}-windscreen", (0.77, 0, 0.6), (0.02, 0.5, 0.2), glass, bevel=0.01),
             kit.box(f"{name}-bed", (-0.2, 0, 0.3), (1.0, 0.62, 0.05), paint, bevel=0.02)]
    blocks = [kit.placed((-0.52 + i * 0.22, -0.18 + j * 0.2, 0.42 + k * 0.17), (0.19, 0.17, 0.15))
              for i in range(4) for j in range(3) for k in range(2)]
    parts.append(kit.boxes(f"{name}-load", blocks, load_material))
    for x in (-0.45, 0.5):
        for y in (-0.33, 0.33):
            parts.append(kit.cyl(f"{name}-wheel{x}{y}", (x, y, 0.13), 0.13, 0.1, tyre, rot=(math.pi / 2, 0, 0), verts=20))
    g = kit.group(name, parts)
    g.location = loc
    g.rotation_euler = (0, 0, facing)
    g.scale = (scale, scale, scale)
    return g


def sprite_rows(key, word="cat"):
    """The hand-drawn pixel grids in tools/pixel/sprites.py, by name."""
    import sprites as sp
    table = {"asleep": sp.WORKER_ASLEEP, "bored": sp.WORKER_BORED, "dozing": sp.worker("dozing"),
             "sleepy": sp.worker("sleepy"), "awake": sp.worker("awake"), "shocked": sp.worker("shocked"),
             "explorer": sp.explorer(), "token": sp.token(word), "zzz": sp.ZZZ, "mug": sp.MUG,
             "truck": sp.TRUCK}
    return table[key]


def sprite_image(key, word="cat"):
    """Build the sprite as a Blender image, pixel for pixel (Blender has no imaging library)."""
    import sprites as sp
    name = f"spr-{key}-{word}"
    if name in bpy.data.images:
        return bpy.data.images[name]
    w, h, px = sp.pixels(sprite_rows(key, word))
    img = bpy.data.images.new(name, w, h, alpha=True)
    buf = [0.0] * (w * h * 4)
    for (x, y), (r, g, b) in px.items():
        i = ((h - 1 - y) * w + x) * 4
        buf[i:i + 4] = (r / 255, g / 255, b / 255, 1.0)
    img.pixels = buf
    return img


def billboard(name, key, loc, px, facing=0.0, word="cat"):
    """A pixel-art sprite standing in the 3D set: a plane facing -Y, its image sampled with no
    smoothing so every pixel stays a crisp square, lit by itself (flat, as pixel art is drawn).
    `key` names a sprite in tools/pixel/sprites.py; `loc` is its bottom centre, `px` the world size
    of one pixel (the same for every sprite in a shot, so all of them share one pixel grid)."""
    img = sprite_image(key, word)
    w, h = img.size
    m = bpy.data.materials.new(f"sprite-{name}")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Closest"
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 1.0
    clear = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    nt.links.new(tex.outputs["Alpha"], mix.inputs["Fac"])
    nt.links.new(clear.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    m.surface_render_method = "DITHERED"
    width, height = w * px, h * px
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(loc[0], loc[1], loc[2] + height / 2),
                                     rotation=(math.pi / 2, 0, facing))
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (width, height, 1)
    ob.data.materials.append(m)
    return ob


# ---------------------------------------------------------------------------
# actors: pixel people who walk, gesture and talk (tools/pixel/people.py)
# ---------------------------------------------------------------------------
# One atlas image per character and size holds every cell (column: mouth x eyes, row: pose x
# expression). The plane shows one cell at a time through a Mapping node whose Location is keyed
# with CONSTANT interpolation: two numbers per frame, no material swaps, no image sequences.

ACTORS = []          # every actor built in this beat, for the camera-dependent pass (finish_actors)


def atlas_image(key, size="figure"):
    import numpy as np
    import people
    from sprites import pixels
    name = f"atlas-{key}-{size}"
    if name in bpy.data.images:
        return bpy.data.images[name], people.atlas_layout(key, size)
    lay = people.atlas_layout(key, size)
    cw, ch = lay["w"], lay["h"]
    W, H = lay["cols"] * cw, lay["rows"] * ch
    buf = np.zeros((H, W, 4), dtype=np.float32)
    for (pose, expr), r in lay["row"].items():
        for (mouth, eyes), c in lay["col"].items():
            w, h, px = pixels(people.cell(key, pose, expr, mouth, eyes, size))
            y0 = (lay["rows"] - 1 - r) * ch          # rows counted from the bottom in Blender
            for (x, y), (cr, cg, cb) in px.items():
                buf[y0 + (h - 1 - y), c * cw + x] = (cr / 255, cg / 255, cb / 255, 1.0)
    img = bpy.data.images.new(name, W, H, alpha=True)
    # sRGB pixel values: let Blender treat them as colour data
    img.pixels.foreach_set(buf.reshape(-1))
    return img, lay


def actor(name, key, loc, height, *, size="figure", pose="stand", expression="neutral", tint=1.0,
          track=True, shadow=True):
    """A pixel person standing at `loc` (bottom centre), `height` world units tall (the whole cell,
    outline included), turning to face the camera. Returns the plane; key its look with `key_cell`."""
    img, lay = atlas_image(key, size)
    m = bpy.data.materials.new(f"actor-{name}")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    uv = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.name = "cell"
    mp.vector_type = "POINT"
    mp.inputs["Scale"].default_value = (1 / lay["cols"], 1 / lay["rows"], 1)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Closest"
    tex.extension = "CLIP"
    em = nt.nodes.new("ShaderNodeEmission")
    em.name = "glow"
    em.inputs["Strength"].default_value = tint
    clear = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(uv.outputs["UV"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    nt.links.new(tex.outputs["Alpha"], mix.inputs["Fac"])
    nt.links.new(clear.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    m.surface_render_method = "DITHERED"
    width = height * lay["w"] / lay["h"]
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(loc[0], loc[1], loc[2] + height / 2),
                                     rotation=(math.pi / 2, 0, 0))
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (width, height, 1)
    ob.data.materials.append(m)
    ob.visible_shadow = False
    ob["actor_key"], ob["actor_size"] = key, size
    ob["walks"] = []
    if track:
        ob["track"] = True
    if shadow:
        # a soft dark blot under the feet, so the figure stands on the ground instead of floating
        sm = bpy.data.materials.new(f"shadow-{name}")
        sm.use_nodes = True
        snt = sm.node_tree
        snt.nodes.clear()
        so = snt.nodes.new("ShaderNodeOutputMaterial")
        grad = snt.nodes.new("ShaderNodeTexGradient")
        grad.gradient_type = "SPHERICAL"
        gco = snt.nodes.new("ShaderNodeTexCoord")
        gmp = snt.nodes.new("ShaderNodeMapping")
        gmp.inputs["Scale"].default_value = (2.0, 2.0, 1.0)
        gmp.inputs["Location"].default_value = (0.0, 0.0, 0.0)
        tr = snt.nodes.new("ShaderNodeBsdfTransparent")
        dark = snt.nodes.new("ShaderNodeBackground")
        dark.inputs["Color"].default_value = (0, 0, 0, 1)
        mx = snt.nodes.new("ShaderNodeMixShader")
        ramp = snt.nodes.new("ShaderNodeMath")
        ramp.operation = "MULTIPLY"
        ramp.inputs[1].default_value = 0.55
        snt.links.new(gco.outputs["Object"], gmp.inputs["Vector"])
        snt.links.new(gmp.outputs["Vector"], grad.inputs["Vector"])
        snt.links.new(grad.outputs["Fac"], ramp.inputs[0])
        snt.links.new(ramp.outputs[0], mx.inputs["Fac"])
        snt.links.new(tr.outputs[0], mx.inputs[1])
        snt.links.new(dark.outputs[0], mx.inputs[2])
        snt.links.new(mx.outputs[0], so.inputs["Surface"])
        sm.surface_render_method = "DITHERED"
        bpy.ops.mesh.primitive_plane_add(size=1.0, location=(loc[0], loc[1], loc[2] + 0.01))
        sh = bpy.context.active_object
        sh.name = f"{name}-shadow"
        sh.scale = (width * 0.9, width * 0.45, 1)
        sh.data.materials.append(sm)
        sh.visible_shadow = False
        sh.parent = ob
        sh.matrix_parent_inverse = ob.matrix_world.inverted()
        ob["shadow"] = sh.name
    key_cell(ob, 1, pose=pose, expression=expression)
    ACTORS.append(ob)
    return ob


def _cell_xy(ob, pose, expression, mouth, eyes):
    import people
    lay = people.atlas_layout(ob["actor_key"], ob["actor_size"])
    poses = people.poses_of(ob["actor_key"], ob["actor_size"])
    pose = pose if pose in poses else "stand"
    col = lay["col"][(mouth, eyes)]
    row = lay["row"][(pose, expression)]
    return col / lay["cols"], (lay["rows"] - 1 - row) / lay["rows"]


EVENTS = {}         # actor name -> [(frame, seq, {part: value})]; compiled into keys by compile_cells


def key_cell(ob, frame, *, pose=None, expression=None, mouth=None, eyes=None):
    """From `frame` on, change the named parts (pose, expression, mouth, eyes); the others keep
    whatever they are at that moment. Calls may come in any order (a walk, then the talking over
    it): they are recorded here and turned into keys once, in time order, by compile_cells."""
    change = {k: v for k, v in (("pose", pose), ("expression", expression), ("mouth", mouth), ("eyes", eyes))
              if v is not None}
    ev = EVENTS.setdefault(ob.name, [])
    ev.append((max(1, int(frame)), len(ev), change))


def compile_cells(ob):
    state = {"pose": "stand", "expression": "neutral", "mouth": "rest", "eyes": "open"}
    sock = ob.data.materials[0].node_tree.nodes["cell"].inputs["Location"]
    last = None
    for frame in sorted({f for f, _, _ in EVENTS.get(ob.name, [])}):
        for _, _, change in sorted(e for e in EVENTS[ob.name] if e[0] == frame):
            state.update(change)
        xy = _cell_xy(ob, state["pose"], state["expression"], state["mouth"], state["eyes"])
        if xy != last:
            sock.default_value = (xy[0], xy[1], 0)
            sock.keyframe_insert("default_value", frame=frame)
            last = xy
    _constant(ob.data.materials[0].node_tree)


def _constant(id_data):
    ad = id_data.animation_data
    if ad and ad.action:
        for fc in ad.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"


def tint(ob, frame, strength):
    """Brightness of the sprite from `frame`: a figure in a dark street is dim, under a lamp bright."""
    sock = ob.data.materials[0].node_tree.nodes["glow"].inputs["Strength"]
    sock.default_value = strength
    sock.keyframe_insert("default_value", frame=max(1, int(frame)))


def walk(ob, points, f0, f1, *, steps_per_second=2.2):
    """Walk through world `points` (list of xyz, feet height) between two frames, at even speed,
    cycling the walk poses; the facing is set later from the camera (finish_actors)."""
    pts = [Vector(p) for p in points]
    lens = [(b - a).length for a, b in zip(pts, pts[1:])]
    total = sum(lens) or 1.0
    lift = Vector((0, 0, ob.scale[1] / 2))
    frame, done = f0, 0.0
    for (a, b), L in zip(zip(pts, pts[1:]), lens):
        done += L
        g1 = f0 + (f1 - f0) * done / total
        ob.location = a + lift
        ob.keyframe_insert("location", frame=round(frame))
        ob.location = b + lift
        ob.keyframe_insert("location", frame=round(g1))
        ob["walks"] = list(ob["walks"]) + [[round(frame), round(g1), b.x - a.x, b.y - a.y]]
        frame = g1
    for fc in ob.animation_data.action.fcurves:
        if fc.data_path == "location":
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
    step = max(3, round(FPS / (steps_per_second * 2)))
    cycle = ["walk1", "walk2", "walk3", "walk4"]
    for i, fr in enumerate(range(f0, f1, step)):
        key_cell(ob, fr, pose=cycle[i % 4])
    key_cell(ob, f1, pose="stand")


def talk(ob, visemes, beat_frames, *, t_from=0.0, t_to=None, fps=FPS):
    """Key the mouth from lip-sync shapes [[shape, t0, t1]] (beat seconds) inside [t_from, t_to]."""
    last = None
    for shape, a, b in visemes:
        if t_to is not None and a >= t_to or b <= t_from:
            continue
        fr = max(1, min(beat_frames, round(a * fps) + 1))
        if shape != last:
            key_cell(ob, fr, mouth=shape)
            last = shape
    if last and last != "rest":
        key_cell(ob, max(1, min(beat_frames, round(visemes[-1][2] * fps) + 1)), mouth="rest")


def blinks(ob, frames, seed):
    """Blink every 2.5-5.5 s, three frames closed, seeded so a re-render is identical."""
    rnd = random.Random(seed)
    fr = rnd.randint(int(FPS * 0.8), int(FPS * 3))
    while fr < frames - 4:
        key_cell(ob, fr, eyes="blink")
        key_cell(ob, fr + 3, eyes="open")
        fr += rnd.randint(int(FPS * 2.5), int(FPS * 5.5))


def finish_actors(cam):
    """After the camera exists: every actor turns to face it (yaw only) and walks the way it moves
    on screen (a figure going left is mirrored)."""
    scene = bpy.context.scene
    for ob in ACTORS:
        if ob.name not in bpy.data.objects:
            continue
        compile_cells(ob)
        if ob.get("track"):
            c = ob.constraints.new("LOCKED_TRACK")
            c.target = cam
            c.track_axis = "TRACK_Z"
            c.lock_axis = "LOCK_Y"
        base = abs(ob.scale[0])
        for f0, f1, dx, dy in ob.get("walks", []):
            f0, f1 = int(f0), int(f1)
            scene.frame_set(max(1, (f0 + f1) // 2))
            right = cam.matrix_world.to_quaternion() @ Vector((1, 0, 0))
            sign = 1 if Vector((dx, dy, 0)).dot(right) >= 0 else -1
            ob.scale[0] = base * sign
            ob.keyframe_insert("scale", frame=max(1, f0))
            for fc in ob.animation_data.action.fcurves:
                if fc.data_path == "scale":
                    for kp in fc.keyframe_points:
                        kp.interpolation = "CONSTANT"
    ACTORS.clear()
    EVENTS.clear()


def face_light(name, target, dist):
    """A soft warm light from the front and above, so faces read on the dark stage."""
    tx, ty, tz = target
    return look.soft_light(name, (tx + 0.5 * dist, ty - dist, tz + 0.8 * dist), target, 3.0 * dist ** 2,
                           (1.0, 0.86, 0.72), size=dist * 0.6)


def zzz(name, loc, size, material):
    """Three letters z rising from a sleeper's head, for a picture of waiting."""
    obs = []
    for k in range(3):
        obs.append(kit.flat_text(f"{name}{k}", "z", (loc[0] + 0.12 * k * size / 0.2, loc[1], loc[2] + 0.14 * k * size / 0.2),
                                 size * (0.7 + 0.2 * k), material, rot=(math.pi / 2, 0, 0)))
        obs[-1]["cut_ok"] = True       # decoration, not something to read: the frame may cut it
    return obs


# ---------------------------------------------------------------------------
# scenes
# ---------------------------------------------------------------------------

PX = 0.055      # one sprite pixel, in the factory's units
TINTS = [(0.2, 0.62, 0.56), (0.95, 0.45, 0.4), (0.55, 0.45, 0.9), (0.35, 0.65, 0.95), (0.95, 0.7, 0.35), (0.5, 0.8, 0.4)]


def chip_factory(p, sec):
    """Inside a chip, drawn as a factory floor: rows of workers at desks of multipliers, a memory
    tower far off to the left and a road between them. In `decode` the truck brings one load of
    weights, the desks light for an instant, and everyone goes back to sleep."""
    from compute import _hbm, WARM, COOL
    from optics import ink, key_glow
    from scenes import Set
    s = Set(sec)
    kit.box("die-floor", (0, 1.0, -0.06), (22.0, 12.0, 0.12), kit.mat("die", (0.07, 0.08, 0.10), metallic=0.4, roughness=0.4), bevel=0.02)
    grid = kit.mat("die-lines", (0.12, 0.14, 0.17), metallic=0.4, roughness=0.4)
    kit.boxes("die-grid", [kit.placed((-10.5 + i * 1.0, 1.0, 0.002), (0.02, 12.0, 0.004)) for i in range(22)]
              + [kit.placed((0, -4.5 + j * 1.0, 0.002), (22.0, 0.02, 0.004)) for j in range(12)], grid)
    cells = look.neon("desk-cells", WARM, 0.5, base=(0.06, 0.05, 0.05))
    poses = (p.get("poses") or "sleep|wait|sleep|sleep|sleep|sleep|wait|sleep|sleep|wait|sleep|sleep").split("|")
    mix = p.get("workers", "mixed")
    busy = bool(p.get("busy", False))
    if busy:
        poses = ["work"]
    rng = random.Random(int(p.get("seed", 3)))
    kinds = ["pixel"] * 6 + ["toy"] * 6       # half and half, scattered at random
    rng.shuffle(kinds)
    heads = []
    k = 0
    for row, y in enumerate((-0.6, 1.5, 3.6)):
        for x in (-0.6, 1.5, 3.6, 5.7):
            pose = poses[k % len(poses)]
            desk(f"desk{k}", (x, y, 0), cells)
            kind = kinds[k] if mix == "mixed" else mix
            if kind == "toy":
                import character_styles as cs
                role = {"sleep": "sleeper", "wait": "bored"}.get(pose, "worker")
                g = cs.vinyl_person(f"worker{k}", role, color=TINTS[k % len(TINTS)], loc=(x, y + 0.12, 0.0), scale=1.12)
                if role == "sleeper":
                    g.rotation_euler[0] = math.radians(16)
                    zzz(f"z{k}-", (x + 0.25, y - 0.5, 1.45), 0.16, ink())
            elif kind == "pixel":
                face = {"wait": "bored", "sleep": "dozing", "work": "awake"}.get(pose, "sleepy")
                billboard(f"worker{k}", face, (x, y + 0.05, 0.12), PX)
                if pose == "sleep":
                    billboard(f"z{k}", "zzz", (x + 0.36, y + 0.04, 1.3), PX * 0.6)
            else:
                person(f"worker{k}", (x, y, 0), pose=pose, outfit="worker")
                if pose == "sleep":
                    zzz(f"z{k}-", (x + 0.2, y - 0.62, 1.12), 0.16, ink())
            heads.append((x, y, pose))
            k += 1
    # the memory tower and the road
    tower = _hbm("memory", (-8.0, 1.0, 0.0), w=2.6, d=2.6, layers=8)
    tower.scale = (1, 1, 3.2)
    frames = s.frames
    road = kit.box("road", (-4.6, -0.6, 0.02), (6.2, 1.1, 0.04),
                   look.signal_material("road", frames, axis="X", color=COOL, rest=0.12, peak=2.0,
                                        spacing=0.6, speed=0.4, lanes=3.0), bevel=0)
    del road
    for x in (-1.7,):
        kit.box("gate-l", (x, -1.25, 0.6), (0.18, 0.18, 1.2), kit.silicon(), bevel=0.02)
        kit.box("gate-r", (x, 0.05, 0.6), (0.18, 0.18, 1.2), kit.silicon(), bevel=0.02)
        kit.box("gate-top", (x, -0.6, 1.25), (0.22, 1.5, 0.14), look.neon("gate", COOL, 1.2), bevel=0.02)
    load = look.neon("load", COOL, 0.9, base=(0.05, 0.2, 0.25))
    face_light("workers-key", (1.5, -0.6, 0.9), 4.0)
    lorry = truck("truck", (float(p.get("truck_x", -4.2)), -0.6, 0.0), load, scale=0.9)
    if busy:
        rng2 = random.Random(9)
        keys = [(1, 0.5)] + [(fr, rng2.uniform(5.0, 9.0)) for fr in range(2, s.frames + 1, 3)]
        key_glow(cells, keys)
    if p.get("guides", False):
        billboard("explorer", "explorer", (-3.7, -1.05, 0.0), PX)
        billboard("token", "token", (-2.6, -1.1, 0.0), PX, word=p.get("word", "cat"))
    s.pin("memory", (-6.6, -0.4, 3.2))
    s.pin("truck", (float(p.get("truck_x", -4.2)), -0.9, 1.0), lorry)
    s.pin("workers", (1.5, -1.3, 1.2))
    s.pin("desk", (-0.6, -1.0, 0.65))

    def deliver(t0, t1):
        a, b = f(t0), f(t1)
        slide(lorry, a, b, (-6.6, -0.6, 0.0), (-2.6, -0.6, 0.0))
        flash(cells, [b + 2], 9.0, 0.5, 2)
    s.action("deliver", deliver, at=0.2, span=3.0)
    s.view("wide", (0.0, 1.0, 0.6), 15.0, -104, 6.5)
    s.view("workers", (1.5, -0.6, 0.8), 4.2, -86, 1.45)
    s.view("road", (-4.6, -0.6, 0.6), 5.6, -112, 2.0)
    s.lens, s.floor_grid, s.floor_z = 40.0, 0, -0.12
    return s


def guide(p, sec):
    """The explorer and the token, standing on a GPU package beside a memory stack: someone the size
    of a fingernail's grain to point at things. The set is the `hbm-stack` scene."""
    from compute import hbm_stack
    s = hbm_stack(p, sec)
    person("explorer", (-0.15, -2.0, 0.12), pose="point", outfit="explorer", facing=math.radians(-10), scale=0.42)
    face_light("guide-key", (0.1, -2.0, 0.4), 2.2)
    token("token", (0.4, -2.05, 0.12), p.get("word", "cat"), p.get("number", "9059"), facing=math.radians(-12),
          scale=0.34, look_up=True)
    s.pin("explorer", (-0.15, -2.1, 0.75))
    s.pin("token", (0.4, -2.1, 0.5))
    s.view("guide", (-0.5, -1.7, 0.55), 3.6, -98, 0.95)
    s.view("pair", (0.1, -2.0, 0.35), 2.2, -86, 0.55)
    return s


def f(seconds):
    from scenes import f as frames_of
    return frames_of(seconds)


def slide(ob, f0, f1, start, end):
    from compute import slide as _slide
    _slide(ob, f0, f1, start, end)


def flash(material, frames, high, low, length=3):
    from compute import flash as _flash
    _flash(material, frames, high, low, length)


SCENES = {"chip-factory": chip_factory}
