"""Living places: a town at dusk, a hospital, an asylum gate. Story scenes, not diagrams.

Everything is built from boxes and prisms merged per material (a town of sixty houses is a few
dozen objects), lit by the time of day instead of the studio rig (`s.lighting = "world"`):

  sky_world(time)   gradient sky, horizon glow, stars at night; `"dusk>night"` darkens over the beat
  sky_lights(...)   a low sun or a cool moon, and a faint fill so shadows are not black

What happens in a place is scheduled by `world_plan` (no bpy, unit-tested): which windows light and
when, who walks where. Pixel people come from `characters.actor`.

Scenes: vienna (the town and the Allgemeines Krankenhaus at the end of the main street),
asylum (1865: the gate at night and a cell), ward (1846: the First Clinic's long ward).

Each scene takes `assets` (default true): CC0 Poly Haven textures tinted into the palette, a soft HDRI
for lighting, and a few glTF props (models/assets.py). `{"assets": false}` is the plain look.
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

import assets
import characters
import kit
import look
import world_plan as plan
from kit import FPS, placed

PERSON_H = 1.85          # a figure cell's world height (the person inside it is about 1.65 m)


def frames(seconds):
    return max(1, round(seconds * FPS))


# ---------------------------------------------------------------------------
# sky and light by time of day
# ---------------------------------------------------------------------------

TIMES = {
    #        zenith                 horizon               sun colour          sun   fill  windows
    "night": ((0.002, 0.004, 0.012), (0.010, 0.018, 0.040), (0.55, 0.66, 1.0), 0.25, 0.010, 1.0),
    "dusk":  ((0.010, 0.016, 0.050), (0.55, 0.20, 0.07), (1.0, 0.48, 0.22), 1.6, 0.030, 0.6),
    "dawn":  ((0.030, 0.050, 0.120), (0.65, 0.38, 0.28), (1.0, 0.70, 0.50), 2.2, 0.050, 0.2),
    "day":   ((0.22, 0.42, 0.80), (0.72, 0.80, 0.90), (0.92, 0.95, 1.0), 3.5, 0.080, 0.0),
}


def _times(time):
    a, _, b = time.partition(">")
    return a, (b or a)


def sky_world(time, seconds):
    """A gradient sky; `a>b` fades from one time to the other across the beat."""
    t0, t1 = _times(time)
    world = bpy.data.worlds.new(f"sky-{time}")
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes["Background"]
    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(coord.outputs["Generated"], sep.inputs["Vector"])
    up = nt.nodes.new("ShaderNodeMath")
    up.operation = "MAXIMUM"
    up.inputs[1].default_value = 0.0
    nt.links.new(sep.outputs["Z"], up.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.name = "sky"
    nt.links.new(up.outputs[0], ramp.inputs["Fac"])
    lo, hi = ramp.color_ramp.elements
    lo.position, hi.position = 0.0, 0.35
    # stars: a sparse voronoi speckle in the upper sky, visible only when it is dark
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 140.0
    nt.links.new(coord.outputs["Generated"], vor.inputs["Vector"])
    star = nt.nodes.new("ShaderNodeMath")
    star.operation = "LESS_THAN"
    star.inputs[1].default_value = 0.035
    nt.links.new(vor.outputs["Distance"], star.inputs[0])
    gate = nt.nodes.new("ShaderNodeMath")
    gate.operation = "MULTIPLY"
    gate.name = "stars"
    nt.links.new(star.outputs[0], gate.inputs[0])
    hiz = nt.nodes.new("ShaderNodeMath")
    hiz.operation = "GREATER_THAN"
    hiz.inputs[1].default_value = 0.12
    nt.links.new(up.outputs[0], hiz.inputs[0])
    both = nt.nodes.new("ShaderNodeMath")
    both.operation = "MULTIPLY"
    nt.links.new(gate.outputs[0], both.inputs[0])
    nt.links.new(hiz.outputs[0], both.inputs[1])
    add = nt.nodes.new("ShaderNodeMixRGB")
    add.blend_type = "ADD"
    add.inputs["Color2"].default_value = (0.5, 0.55, 0.7, 1)
    nt.links.new(both.outputs[0], add.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], add.inputs["Color1"])
    nt.links.new(add.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.0
    n = frames(seconds)
    for fr, tod in ((1, t0), (n, t1)):
        zen, hor = TIMES[tod][0], TIMES[tod][1]
        lo.color = (*hor, 1)
        hi.color = (*zen, 1)
        lo.keyframe_insert("color", frame=fr)
        hi.keyframe_insert("color", frame=fr)
        gate.inputs[1].default_value = 1.0 if tod == "night" else (0.25 if tod == "dusk" else 0.0)
        gate.inputs[1].keyframe_insert("default_value", frame=fr)
    bpy.context.scene.world = world
    return world


def sky_lights(time, seconds, centre, half, sun_azimuth=200.0):
    """A sun (or the moon) low over the town, keyed from one time to the other, and a soft fill."""
    t0, t1 = _times(time)
    data = bpy.data.lights.new("sun", "SUN")
    data.angle = math.radians(2.0)
    sun = bpy.data.objects.new("sun", data)
    kit._link(sun)
    elev = {"night": 35.0, "dusk": 6.0, "dawn": 9.0, "day": 42.0}
    n = frames(seconds)
    for fr, tod in ((1, t0), (n, t1)):
        e = math.radians(elev[tod])
        a = math.radians(sun_azimuth if tod != "dawn" else sun_azimuth + 160)
        sun.rotation_euler = (math.pi / 2 - e, 0, a + math.pi / 2)
        sun.keyframe_insert("rotation_euler", frame=fr)
        data.color = TIMES[tod][2]
        data.energy = TIMES[tod][3]
        data.keyframe_insert("color", frame=fr)
        data.keyframe_insert("energy", frame=fr)
    fill = kit.common.add_area_light("sky-fill", tuple(Vector(centre) + Vector((0, 0, half * 1.5))),
                                     TIMES[t0][4] * 40 * half ** 2, color=(0.55, 0.65, 1.0), size=half * 3)
    fill.data.keyframe_insert("energy", frame=1)
    fill.data.energy = TIMES[t1][4] * 40 * half ** 2
    fill.data.keyframe_insert("energy", frame=n)
    bpy.context.scene.view_settings.exposure = 0.6
    return sun


# ---------------------------------------------------------------------------
# materials
# ---------------------------------------------------------------------------

PLASTER = [(0.62, 0.53, 0.38), (0.70, 0.50, 0.16), (0.58, 0.40, 0.34), (0.50, 0.50, 0.46),
           (0.44, 0.50, 0.38), (0.66, 0.60, 0.50)]
ROOFS = [(0.20, 0.07, 0.045), (0.13, 0.13, 0.15), (0.26, 0.11, 0.06)]


def cobbles(name="cobbles", scale=2.6):
    """Stone setts with dark joints and a damp sheen: Voronoi cells, bumped at the joints."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    co = nt.nodes.new("ShaderNodeTexCoord")
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.feature = "DISTANCE_TO_EDGE"
    vor.inputs["Scale"].default_value = scale
    nt.links.new(co.outputs["Object"], vor.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0.02, 0.02, 0.02, 1)
    ramp.color_ramp.elements[1].position = 0.06
    ramp.color_ramp.elements[1].color = (0.16, 0.15, 0.14, 1)
    nt.links.new(vor.outputs["Distance"], ramp.inputs["Fac"])
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.8
    nt.links.new(co.outputs["Object"], noise.inputs["Vector"])
    mul = nt.nodes.new("ShaderNodeMixRGB")
    mul.blend_type = "MULTIPLY"
    mul.inputs["Fac"].default_value = 0.5
    nt.links.new(ramp.outputs["Color"], mul.inputs["Color1"])
    nt.links.new(noise.outputs["Color"], mul.inputs["Color2"])
    nt.links.new(mul.outputs["Color"], b.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.6
    nt.links.new(vor.outputs["Distance"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = 0.42
    return m


def window_light(name, strength=7.0, color=(1.0, 0.62, 0.28)):
    return look.neon(name, color, strength, base=(0.3, 0.2, 0.1))


def smoke_mat():
    m = bpy.data.materials.new("smoke")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.35, 0.36, 0.40, 1)
    b.inputs["Alpha"].default_value = 0.22
    b.inputs["Roughness"].default_value = 1.0
    m.surface_render_method = "DITHERED"
    return m


# ---------------------------------------------------------------------------
# building blocks
# ---------------------------------------------------------------------------

def _roof_prisms(name, roofs, material):
    """roofs: [(cx, cy, w, d, z0, h, along_x)] gabled roofs as one mesh."""
    bm = bmesh.new()
    for cx, cy, w, d, z0, h, along_x in roofs:
        if along_x:
            pts = [(-w / 2, -d / 2, 0), (w / 2, -d / 2, 0), (w / 2, d / 2, 0), (-w / 2, d / 2, 0),
                   (-w / 2, 0, h), (w / 2, 0, h)]
        else:
            pts = [(-w / 2, -d / 2, 0), (w / 2, -d / 2, 0), (w / 2, d / 2, 0), (-w / 2, d / 2, 0),
                   (0, -d / 2, h), (0, d / 2, h)]
        v = [bm.verts.new((cx + x, cy + y, z0 + z)) for x, y, z in pts]
        if along_x:
            faces = [(v[0], v[1], v[5], v[4]), (v[2], v[3], v[4], v[5]), (v[0], v[4], v[3]), (v[1], v[2], v[5]),
                     (v[0], v[3], v[2], v[1])]
        else:
            faces = [(v[1], v[2], v[5], v[4]), (v[3], v[0], v[4], v[5]), (v[0], v[1], v[4]), (v[2], v[3], v[5]),
                     (v[0], v[3], v[2], v[1])]
        for fc in faces:
            bm.faces.new(fc)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return kit._mesh_object(name, bm, material)


# the rooms behind lit windows: warm back walls that glow a little (the lamp's light on them), a
# lamp that is a small bright source, dark furniture, curtains. All merged into one object per lit
# storey with a slot per material, so a town of rooms stays a few hundred objects.
ROOM_WALLS = [(0.55, 0.30, 0.12), (0.52, 0.40, 0.18), (0.40, 0.30, 0.22), (0.45, 0.22, 0.14)]
CURTAINS = [(0.40, 0.07, 0.07), (0.10, 0.22, 0.16), (0.75, 0.62, 0.38)]
DARK_WOOD = (0.035, 0.022, 0.014)
POCKET = 0.7             # how deep the wall is hollowed behind every window


def room_material(key):
    """Material for a room part key: wall0.., curtain0.., lamp, dark, pane."""
    if key.startswith("wall"):
        c = ROOM_WALLS[int(key[4:])]
        return kit.mat(f"room-{key}", c, roughness=0.9, emission=0.9, emission_color=c)
    if key.startswith("curtain"):
        c = CURTAINS[int(key[7:])]
        return kit.mat(f"room-{key}", c, roughness=0.95, emission=0.25, emission_color=c)
    if key == "lamp":
        return look.neon("room-lamp", (1.0, 0.66, 0.28), 14.0, base=(0.5, 0.35, 0.15))
    if key == "dark":
        return kit.mat("room-dark", DARK_WOOD, roughness=0.8)
    if key == "pane":
        return window_pane()
    raise KeyError(key)


def window_pane(name="window-pane"):
    """A lit pane is dim warm glass you can see through: low emission, mostly transparent."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.25, 0.17, 0.08, 1)
    b.inputs["Roughness"].default_value = 0.15
    b.inputs["Emission Color"].default_value = (1.0, 0.62, 0.28, 1)
    b.inputs["Emission Strength"].default_value = 0.35
    b.inputs["Alpha"].default_value = 0.22
    m.surface_render_method = "DITHERED"
    return m


def room_parts(rnd, wx, front, out, z):
    """One room behind a window, as {material key: [matrices]}: a back wall, a lamp off-centre, one
    or two dark furniture silhouettes, curtains on about half. Local to the pocket (POCKET deep)."""
    P = {}

    def put(key, loc, size):
        P.setdefault(key, []).append(placed(loc, size))

    def at(dx, t, dz):                                  # t: depth behind the glass, dx: along the wall
        return (wx + dx, front - out * t, z + dz)

    put(f"wall{rnd.randrange(len(ROOM_WALLS))}", at(0, POCKET - 0.04, 0), (0.98, 0.04, 1.58))
    side = rnd.choice((-1, 1))
    put("lamp", at(side * rnd.uniform(0.18, 0.32), rnd.uniform(0.3, 0.5), rnd.uniform(-0.1, 0.5)), (0.12, 0.12, 0.14))
    for kind in rnd.sample(("shelf", "wardrobe", "frame", "table"), rnd.choice((1, 2))):
        dx = -side * rnd.uniform(0.0, 0.25)
        if kind == "shelf":
            for dz in (-0.25, 0.15):
                put("dark", at(dx, 0.55, dz), (0.7, 0.14, 0.05))
            put("dark", at(dx, 0.55, -0.05), (0.05, 0.14, 0.8))
        elif kind == "wardrobe":
            put("dark", at(dx, 0.5, -0.12), (0.46, 0.3, 1.3))
        elif kind == "frame":
            put("dark", at(dx, POCKET - 0.09, rnd.uniform(0.2, 0.45)), (0.3, 0.03, 0.4))
        else:
            put("dark", at(dx, 0.45, -0.45), (0.7, 0.35, 0.05))
            put("dark", at(dx, 0.45, -0.66), (0.06, 0.3, 0.36))
    if rnd.random() < 0.5:
        c = rnd.randrange(len(CURTAINS))
        for sd in (-1, 1):
            put(f"curtain{c}", at(sd * 0.4, 0.07, 0.0), (0.18, 0.05, 1.46))
    return P


class Town:
    """Collects the boxes of every house by material, then makes one object per material."""

    def __init__(self):
        self.parts = {}
        self.roofs = {}
        self.chimneys = []
        self.lit = []            # (object, house index) lit window groups
        self.mats = {}
        self.glass_by = {}       # (house, storey) -> dark glass matrices
        self.rooms = {}          # (house, storey) -> {room material key: [matrices]} the rooms behind the glass
        self.windows = {}        # (house, storey) -> [(x, front, out, z)] every window of that storey
        self.shutters = {}       # (house, storey) -> (colour, [(x, front, out, z)]) decided once lit/unlit is known

    def mat(self, key, color, rough=0.75):
        if key not in self.mats:
            self.mats[key] = kit.mat(f"town-{key}", color, roughness=rough)
        return self.mats[key]

    def add(self, key, color, matrix, rough=0.75):
        self.mat(key, color, rough)
        self.parts.setdefault(key, []).append(matrix)

    def build(self):
        for key, mats in self.parts.items():
            ob = kit.boxes(f"town-{key}", mats, self.mats[key])
            if key.startswith(("awning", "canvas")):
                ob.data.materials[0].use_backface_culling = False
        for key, roofs in self.roofs.items():
            _roof_prisms(f"roofs-{key}", roofs, self.mat(key, ROOFS[int(key[-1])], 0.8))


SHUTTERS = [(0.10, 0.20, 0.12), (0.28, 0.13, 0.07), (0.14, 0.16, 0.22), (0.32, 0.27, 0.16)]
AWNINGS = [(0.50, 0.09, 0.07), (0.10, 0.24, 0.16), (0.14, 0.17, 0.34), (0.45, 0.30, 0.08)]


def tilted(loc, size, angle_x):
    """A box matrix tipped about x (an awning sloping down from the wall)."""
    return Matrix.Translation(loc) @ Matrix.Rotation(angle_x, 4, "X") @ Matrix.Diagonal((*size, 1.0))


def house(town, i, x, y, w, d, storeys, facing, rnd, glass, lit_sets, shop=False):
    """One townhouse: plastered body, cornice, gabled roof along the street, a chimney or two, a
    door, windows on the street front. Window panes lit at night are collected per storey in
    `lit_sets[(i, storey)]`, so each storey can come on at its own moment. The front is dressed
    so it reads as a lived-in house close up: plinth, corner pilasters, window heads, glazing
    bars, shutters on some houses, now and then a balcony; on the main street a shop with an
    awning and a signboard (`shop`)."""
    colour = PLASTER[rnd.randrange(len(PLASTER))]
    h = storeys * 3.2 + 0.6
    wall_key, pockets = f"wall{PLASTER.index(colour)}", []
    front = y + facing * d / 2
    town.add("trim", (0.72, 0.68, 0.6), placed((x, front + facing * 0.08, h - 0.25), (w + 0.2, 0.3, 0.35)))
    town.add("trim", (0.72, 0.68, 0.6), placed((x, front + facing * 0.06, 3.4), (w, 0.2, 0.16)))
    town.add("plinth", (0.24, 0.22, 0.20), placed((x, front + facing * 0.06, 0.45), (w, 0.14, 0.9)))
    for side in (-1, 1):
        town.add("trim", (0.72, 0.68, 0.6), placed((x + side * (w / 2 - 0.22), front + facing * 0.07, h / 2),
                                                   (0.42, 0.14, h)))
    shutters = SHUTTERS[rnd.randrange(len(SHUTTERS))] if rnd.random() < 0.55 else None
    balcony = rnd.random() < 0.3 and storeys >= 3
    roof_kind = rnd.randrange(len(ROOFS))
    town.roofs.setdefault(f"roof{roof_kind}", []).append((x, y, w + 0.4, d + 0.4, h, 2.2 + rnd.random() * 1.4, True))
    for k in range(rnd.choice((1, 1, 2))):
        cx = x + (rnd.random() - 0.5) * w * 0.6
        cy = y - facing * d * 0.15
        ch = h + 2.4
        town.add("chimney", (0.30, 0.20, 0.16), placed((cx, cy, ch), (0.55, 0.55, 2.0)))
        town.add("trim", (0.72, 0.68, 0.6), placed((cx, cy, ch + 1.05), (0.72, 0.72, 0.12)))     # the cap
        town.add("chimney", (0.30, 0.20, 0.16), placed((cx + 0.12, cy, ch + 1.22), (0.14, 0.14, 0.24)))  # a pot
        town.chimneys.append((cx, cy, ch + 1.0))
    bays = max(2, int(w // 2.4))
    door_bay = rnd.randrange(bays)
    out = facing                                   # the street side
    for s in range(storeys):
        z = 1.7 + s * 3.2 + (0.4 if s else 0)
        for b in range(bays):
            wx = x - w / 2 + (b + 0.5) * w / bays
            if s == 0 and b == door_bay:
                town.add("door", (0.16, 0.08, 0.04), placed((wx, front + out * 0.05, 1.25), (1.2, 0.12, 2.5)))
                town.add("trim", (0.72, 0.68, 0.6), placed((wx, front + out * 0.1, 2.62), (1.5, 0.2, 0.22)))
                # a panelled door in a stone frame, with a fanlight over it
                for side in (-1, 1):
                    town.add("trim", (0.72, 0.68, 0.6), placed((wx + side * 0.68, front + out * 0.09, 1.25), (0.16, 0.18, 2.5)))
                    for zz, hh in ((0.6, 0.8), (1.55, 0.8)):
                        town.add("doorpanel", (0.21, 0.11, 0.055),
                                 placed((wx + side * 0.28, front + out * 0.12, zz), (0.42, 0.03, hh)))
                town.add("bars", (0.09, 0.07, 0.05), placed((wx, front + out * 0.12, 2.3), (1.1, 0.03, 0.04)))
                town.add("step", (0.42, 0.40, 0.36), placed((wx, front + out * 0.3, 0.08), (1.5, 0.6, 0.16)))
                if shop:
                    awning = AWNINGS[rnd.randrange(len(AWNINGS))]
                    for k in range(6):                     # striped canvas, sloping down to the street
                        key = f"awning{AWNINGS.index(awning)}" if k % 2 == 0 else "canvas"
                        colour = awning if k % 2 == 0 else (0.78, 0.72, 0.6)
                        town.add(key, colour, tilted((wx - 1.5 + 0.5 * (k + 0.5), front + out * 0.75, 3.0),
                                                     (0.5, 1.5, 0.05), -out * 0.45), rough=0.9)
                    town.add("sign", (0.10, 0.06, 0.035), placed((wx, front + out * 0.1, 3.75), (2.0, 0.1, 0.5)))
                    town.add("gilt", (0.62, 0.46, 0.16), placed((wx, front + out * 0.16, 3.75), (1.4, 0.03, 0.14)))
                continue
            m = placed((wx, front + out * 0.04, z), (0.95, 0.1, 1.55))
            town.glass_by.setdefault((i, s), []).append(m)
            # the wall is hollow behind the glass, so a lit window has a room in it
            ys = sorted((front - out * POCKET, front + out * 0.01))
            pockets.append(((wx - 0.5, ys[0], z - 0.8), (wx + 0.5, ys[1], z + 0.8)))
            town.windows.setdefault((i, s), []).append((wx, front, out, z))
            for k, ms in room_parts(random.Random(i * 7919 + s * 131 + b), wx, front, out, z).items():
                town.rooms.setdefault((i, s), {}).setdefault(k, []).extend(ms)
            lit_sets.setdefault((i, s), []).append(placed((wx, front + out * 0.07, z), (0.85, 0.06, 1.45)))
            town.add("sill", (0.75, 0.72, 0.66), placed((wx, front + out * 0.12, z - 0.85), (1.15, 0.22, 0.1)))
            town.add("sill", (0.75, 0.72, 0.66), placed((wx, front + out * 0.1, z + 0.92), (1.3, 0.18, 0.2)))
            for side in (-1, 1):         # the jambs: the window sits in a frame, not on the plaster
                town.add("sill", (0.75, 0.72, 0.66), placed((wx + side * 0.55, front + out * 0.09, z), (0.14, 0.16, 1.72)))
            # glazing bars over the pane (they also cross a lit window, as they would)
            town.add("bars", (0.09, 0.07, 0.05), placed((wx, front + out * 0.115, z), (0.06, 0.03, 1.45)))
            town.add("bars", (0.09, 0.07, 0.05), placed((wx, front + out * 0.115, z + 0.22), (0.85, 0.03, 0.06)))
            if shutters:                 # open or closed is decided once the lit storeys are known
                town.shutters.setdefault((i, s), (shutters, []))[1].append((wx, front, out, z))
            if balcony and s == 1 and b == bays // 2:
                town.add("trim", (0.72, 0.68, 0.6), placed((wx, front + out * 0.55, z - 0.86), (1.8, 1.1, 0.14)))
                town.add("iron", (0.05, 0.05, 0.055), placed((wx, front + out * 1.05, z - 0.3), (1.8, 0.05, 0.06)))
                for k in range(7):
                    town.add("iron", (0.05, 0.05, 0.055),
                             placed((wx - 0.84 + 0.28 * k, front + out * 1.05, z - 0.55), (0.04, 0.04, 0.5)))
    pieces = [((x - w / 2, y - d / 2, 0.0), (x + w / 2, y + d / 2, h))]
    for pocket in pockets:
        pieces = [q for pc in pieces for q in subtract(*pc, *pocket)]
    for lo, hi in pieces:
        town.add(wall_key, colour, placed(tuple((a + b) / 2 for a, b in zip(lo, hi)),
                                          tuple(b - a for a, b in zip(lo, hi))))


def dress_shutters(town, lit_keys, rnd, closed=0.3):
    """Shutters stand open beside every window, except that 30% of the windows that never light
    have them closed across the glass (people who have gone to bed)."""
    for key, (colour, wins) in town.shutters.items():
        name = f"shutter{SHUTTERS.index(colour)}"
        for wx, front, out, z in wins:
            if key not in lit_keys and rnd.random() < closed:
                for side in (-1, 1):
                    town.add(name, colour, placed((wx + side * 0.26, front + out * 0.13, z), (0.5, 0.06, 1.6)))
            else:
                for side in (-1, 1):
                    town.add(name, colour, placed((wx + side * 0.87, front + out * 0.12, z), (0.5, 0.06, 1.6)))


def multi_object(name, groups):
    """One object, one material slot per group: groups = [(material, [matrices])]."""
    bm = bmesh.new()
    spans = []
    for material, mats in groups:
        start = len(bm.faces)
        for m in mats:
            bmesh.ops.create_cube(bm, size=1.0, matrix=m)
        spans.append((start, len(bm.faces)))
    bm.faces.ensure_lookup_table()
    for slot, (a, b) in enumerate(spans):
        for f in range(a, b):
            bm.faces[f].material_index = slot
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = kit._link(bpy.data.objects.new(name, me))
    for material, _ in groups:
        ob.data.materials.append(material)
    return ob


def switch_off(ob, on_frame, off_frame=None, total=None):
    """The opposite of `switch`: visible until `on_frame`, hidden while lit, visible again from `off_frame`."""
    ob.hide_render = on_frame <= 1
    ob.keyframe_insert("hide_render", frame=1)
    if on_frame > 1:
        ob.hide_render = True
        ob.keyframe_insert("hide_render", frame=on_frame)
    if off_frame and (total is None or off_frame < total):
        ob.hide_render = False
        ob.keyframe_insert("hide_render", frame=off_frame)
    ob.hide_render = False


def silhouette(name, key_loc, legs, on, off, n):
    """A person crossing the room behind a lit window, a flat dark shape (legs, torso, shoulders,
    head). `key_loc` = (x, front, out, z); legs [(t0, t1, direction)] slide it across the pocket,
    out of sight into the wall at either end."""
    wx, front, out, z = key_loc
    y = front - out * 0.35
    ob = kit.boxes(name, [placed((wx, y, z - 0.52), (0.3, 0.1, 0.6)), placed((wx, y, z + 0.02), (0.4, 0.1, 0.5)),
                          placed((wx, y, z + 0.3), (0.52, 0.1, 0.12)), placed((wx, y, z + 0.47), (0.17, 0.1, 0.2))],
                   room_material("dark"))
    keys = [(1, -0.95 * legs[0][2], "CONSTANT")]
    for t0, t1, d in legs:
        f0 = max(frames(t0), keys[-1][0] + 1)
        keys += [(f0, -0.95 * d, "LINEAR"), (max(frames(t1), f0 + 1), 0.95 * d, "CONSTANT")]
    for fr, dx, _ in keys:
        ob.location = (dx, 0, 0)
        ob.keyframe_insert("location", frame=fr)
    for fc in ob.animation_data.action.fcurves:
        if fc.data_path == "location":
            for kp, (_, _, how) in zip(fc.keyframe_points, keys):
                kp.interpolation = how
    ob.location = (0, 0, 0)
    switch(ob, frames(on), frames(off) if off else None, n)
    return ob


def town_layout(seed):
    """Houses along a main street (x, y in [-4, 4]) and two back streets, as (x, y, w, d, storeys,
    facing). The hospital stands across the east end of the main street."""
    rnd = random.Random(seed)
    # (lower y edge, depth, facing): both sides of the main street (y -4..4), and the far sides of
    # the two back streets (y 14..24 and -24..-14), whose near sides are the backs of the first rows
    rows = [(4, 10, -1), (-14, 10, 1), (24, 10, -1), (-34, 10, 1)]
    out = []
    for y0, d, facing in rows:
        x = -70.0
        while x < 34:
            w = rnd.choice((7.0, 8.0, 9.0, 10.0, 11.0))
            if x + w > 36:
                break
            storeys = rnd.choice((2, 3, 3, 4)) if abs(y0) < 10 else rnd.choice((2, 3, 3))
            out.append((x + w / 2, y0 + d / 2, w, d, storeys, facing))
            x += w
    return out


def subtract(lo, hi, clo, chi):
    """Axis-aligned box (lo, hi) minus the box (clo, chi): up to six boxes, as (lo, hi) pairs."""
    clo = tuple(max(a, c) for a, c in zip(lo, clo))
    chi = tuple(min(b, c) for b, c in zip(hi, chi))
    if any(a >= b for a, b in zip(clo, chi)):
        return [(lo, hi)]
    out = []
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    if clo[0] > x0: out.append(((x0, y0, z0), (clo[0], y1, z1)))
    if chi[0] < x1: out.append(((chi[0], y0, z0), (x1, y1, z1)))
    if clo[1] > y0: out.append(((clo[0], y0, z0), (chi[0], clo[1], z1)))
    if chi[1] < y1: out.append(((clo[0], chi[1], z0), (chi[0], y1, z1)))
    if clo[2] > z0: out.append(((clo[0], clo[1], z0), (chi[0], chi[1], clo[2])))
    if chi[2] < z1: out.append(((clo[0], clo[1], chi[2]), (chi[0], chi[1], z1)))
    return out


def hospital(s, glass, lit, x0=40.0, half_y=26.0, depth=12.0, length=50.0, storeys=3, room=None, use_assets=False):
    """The general hospital: four long wings of plain plaster round a courtyard, a gate in the
    west front facing the town. Returns the window anchor (a lit room where a man works late)."""
    wall = kit.mat("akh-wall", (0.62, 0.58, 0.48), roughness=0.85)
    roof = kit.mat("akh-roof", (0.12, 0.12, 0.14), roughness=0.8)
    trim = kit.mat("akh-trim", (0.70, 0.67, 0.58), roughness=0.8)
    h = storeys * 4.2
    wings = [  # (cx, cy, w along x, d along y)
        (x0 + depth / 2, 0, depth, 2 * half_y),
        (x0 + length - depth / 2, 0, depth, 2 * half_y),
        (x0 + length / 2, -half_y + depth / 2, length, depth),
        (x0 + length / 2, half_y - depth / 2, length, depth)]
    body = []
    for k, (cx, cy, w, d) in enumerate(wings):
        lo, hi = (cx - w / 2, cy - d / 2, 0.0), (cx + w / 2, cy + d / 2, h)
        parts = [(lo, hi)]
        if k == 0 and room:
            # hollow out the lit room behind one window of the west front, and wall it back in
            # around a window opening, so the camera can look inside
            ry, rz = room
            cut = ((x0, ry - 2.0, rz - 2.05), (x0 + 3.4, ry + 2.0, rz + 2.15))
            parts = subtract(lo, hi, *cut)
            parts += [((x0, ry - 2.0, rz - 2.05), (x0 + 0.3, ry - 0.55, rz + 2.15)),
                      ((x0, ry + 0.55, rz - 2.05), (x0 + 0.3, ry + 2.0, rz + 2.15)),
                      ((x0, ry - 0.55, rz - 2.05), (x0 + 0.3, ry + 0.55, rz - 1.0)),
                      ((x0, ry - 0.55, rz + 1.0), (x0 + 0.3, ry + 0.55, rz + 2.15))]
        for a, b in parts:
            body.append(placed(tuple((p + q) / 2 for p, q in zip(a, b)), tuple(q - p for p, q in zip(a, b))))
    kit.boxes("akh", body, wall)
    if use_assets:           # a herringbone brick floor across the courtyard (textured by assets.upgrade_materials)
        kit.box("akh-court", (x0 + length / 2, 0, 0.004), (length - 2 * depth, 2 * (half_y - depth), 0.008),
                kit.mat("akh-court", (0.34, 0.27, 0.22), roughness=0.9), bevel=0)
    kit.boxes("akh-cornice", [placed((cx, cy, h - 0.2), (w + 0.4, d + 0.4, 0.4)) for cx, cy, w, d in wings], trim)
    _roof_prisms("akh-roofs", [(cx, cy, w + 0.6, d + 0.6, h, 3.2, w > d) for cx, cy, w, d in wings], roof)
    # windows of the west front (towards the town) and of the courtyard side of the west wing
    surrounds = []
    for face_x, facing in ((x0, -1), (x0 + depth, 1)):
        for st in range(storeys):
            z = 2.0 + st * 4.2
            for yy in range(-24, 25, 3):
                if face_x == x0 and abs(yy) < 3:
                    continue                      # the gate
                if room and face_x == x0 and yy == room[0] and abs(z - room[1]) < 1.0:
                    continue                      # the open window of the lit room
                if facing > 0 and st == 0 and abs(yy) == 6:
                    continue                      # the two clinic doors on the courtyard
                m = placed((face_x + facing * 0.05, yy, z), (0.1, 1.1, 2.0))
                glass.append(m)
                lit.append(((st, yy, facing), placed((face_x + facing * 0.08, yy, z), (0.06, 1.0, 1.9))))
                surrounds.append((face_x, facing, yy, z))
    # each window gets a stone surround standing proud of the plaster (jambs, a head with a small cornice,
    # a sill), and a painted wooden frame with a cross of glazing bars over the glass, so the front reads as
    # windows in a wall rather than dark tiles on it; a string course marks each floor and a plinth the base
    frame_parts, bar_parts = [], []
    for face_x, facing, yy, z in surrounds:
        out = face_x + facing * 0.09
        frame_parts += [placed((out, yy - 0.66, z), (0.18, 0.2, 2.3)),
                        placed((out, yy + 0.66, z), (0.18, 0.2, 2.3)),
                        placed((out, yy, z + 1.2), (0.18, 1.52, 0.22)),
                        placed((face_x + facing * 0.14, yy, z + 1.36), (0.28, 1.72, 0.1)),
                        placed((face_x + facing * 0.12, yy, z - 1.12), (0.24, 1.5, 0.1))]
        bar = face_x + facing * 0.13
        bar_parts += [placed((bar, yy, z), (0.03, 0.06, 1.95)),
                      placed((bar, yy, z + 0.35), (0.03, 1.08, 0.05)),
                      placed((bar, yy, z - 0.45), (0.03, 1.08, 0.05)),
                      placed((bar, yy - 0.53, z), (0.03, 0.06, 1.98)),
                      placed((bar, yy + 0.53, z), (0.03, 0.06, 1.98)),
                      placed((bar, yy, z + 0.97), (0.03, 1.1, 0.06)),
                      placed((bar, yy, z - 0.97), (0.03, 1.1, 0.06))]
    kit.boxes("akh-window-stone", frame_parts, trim)
    kit.boxes("akh-window-bars", bar_parts, kit.mat("akh-window-wood", (0.20, 0.16, 0.12), roughness=0.55))
    courses = []
    for face_x, facing in ((x0, -1), (x0 + depth, 1)):
        span = 2 * half_y if facing < 0 else 2 * (half_y - depth)
        for st in range(1, storeys):
            courses.append(placed((face_x + facing * 0.06, 0, st * 4.2 - 0.6), (0.12, span, 0.2)))
        # the plinth stops at the openings: the gate in the west front, the two clinic doors in the court
        gaps = [(-2.5, 2.5)] if facing < 0 else [(-7.3, -4.7), (4.7, 7.3)]
        y = -span / 2
        for g0, g1 in gaps + [(span / 2, span / 2)]:
            if g0 > y:
                courses.append(placed((face_x + facing * 0.05, (y + g0) / 2, 0.3), (0.1, g0 - y, 0.6)))
            y = g1
    kit.boxes("akh-courses", courses, kit.mat("akh-plinth", (0.50, 0.47, 0.40), roughness=0.9))
    # the gate: a dark arch in the west front
    kit.boxes("akh-gate", [placed((x0 - 0.1, 0, 2.2), (0.3, 4.0, 4.4))], kit.mat("akh-gate", (0.05, 0.04, 0.035)))
    kit.boxes("akh-gate-trim", [placed((x0 - 0.2, 0, 4.6), (0.4, 5.0, 0.5))], trim)
    # the gate's two oak leaves, panelled, with a wicket in one, and stone piers either side
    gate_panels = [placed((x0 - 0.27, side * 1.0, z), (0.04, 1.6, h))
                   for side in (-1, 1) for z, h in ((0.75, 1.1), (2.15, 1.3), (3.5, 1.0))]
    kit.boxes("akh-gate-leaves", [placed((x0 - 0.25, side * 1.0, 2.2), (0.04, 1.96, 4.36)) for side in (-1, 1)],
              kit.mat("door-wood", (0.13, 0.07, 0.035), roughness=0.6))
    kit.boxes("akh-gate-panels", gate_panels, kit.mat("door-panel", (0.17, 0.09, 0.045), roughness=0.55))
    kit.boxes("akh-gate-piers", [placed((x0 - 0.2, side * 2.25, 2.2), (0.4, 0.5, 4.4)) for side in (-1, 1)], trim)
    return h


def room_behind(name, centre, facing, lamp_color=(1.0, 0.6, 0.25), use_assets=False):
    """A small lit room behind an open window (the camera can look in): back wall, desk, an oil
    lamp, a ledger. `facing` -1 means the window looks towards -x."""
    cx, cy, cz = centre
    back = cx - facing * 3.2
    wall = kit.mat(f"{name}-wall", (0.55, 0.42, 0.28), roughness=0.9)
    wood = kit.mat(f"{name}-wood", (0.16, 0.08, 0.04), roughness=0.6)
    paper = kit.mat(f"{name}-paper", (0.8, 0.76, 0.66), roughness=0.9)
    kit.boxes(f"{name}-walls", [placed((back, cy, cz), (0.2, 4.0, 4.2)),
                                placed((cx - facing * 1.6, cy - 2.0, cz), (3.2, 0.2, 4.2)),
                                placed((cx - facing * 1.6, cy + 2.0, cz), (3.2, 0.2, 4.2)),
                                placed((cx - facing * 1.6, cy, cz - 2.0), (3.2, 4.0, 0.2)),
                                placed((cx - facing * 1.6, cy, cz + 2.1), (3.2, 4.0, 0.2))], wall)
    desk_x = cx - facing * 1.0
    kit.boxes(f"{name}-desk", [placed((desk_x, cy + 0.3, cz - 1.2), (0.9, 1.8, 0.08)),
                               placed((desk_x, cy + 0.3, cz - 1.55), (0.8, 1.6, 0.7))], wood)
    kit.boxes(f"{name}-ledger", [placed((desk_x, cy + 0.1, cz - 1.13), (0.45, 0.6, 0.06))], paper)
    desk_top = cz - 1.16
    oil = use_assets and assets.prop("vintage_oil_lamp", (desk_x + facing * 0.1, cy + 0.9, desk_top), 0.0,
                                     height=0.34, name=f"{name}-oil-lamp")
    lamp = kit.ico(f"{name}-lamp", (desk_x + facing * 0.1, cy + 0.9, cz - 0.95), 0.05 if oil else 0.12,
                   look.neon(f"{name}-flame", lamp_color, 18.0), subdivisions=2, smooth=True)
    light = bpy.data.lights.new(f"{name}-lamp", "POINT")
    light.energy = 60.0
    light.color = lamp_color
    light.shadow_soft_size = 0.2
    lo = bpy.data.objects.new(f"{name}-lamp-light", light)
    kit._link(lo)
    lo.location = (desk_x + facing * 0.2, cy + 0.9, cz - 0.7)
    # a room someone lives in: books on a shelf, papers everywhere, a candle, a picture, curtains
    floor = cz - 1.9
    shelf_x0, shelf_x1 = cx - facing * 1.0, cx - facing * 3.0
    sx, sw = (shelf_x0 + shelf_x1) / 2, abs(shelf_x1 - shelf_x0)
    kit.boxes(f"{name}-shelf", [placed((sx, cy + 1.75, floor + 0.2 + 0.75 * k), (sw, 0.4, 0.05)) for k in range(5)]
              + [placed((sx + d * sw / 2, cy + 1.75, floor + 1.6), (0.05, 0.4, 3.2)) for d in (-1, 1)], wood)
    rnd = random.Random(17)
    book_cols = [(0.35, 0.08, 0.06), (0.10, 0.18, 0.12), (0.30, 0.22, 0.10), (0.12, 0.12, 0.22)]
    books = {c: [] for c in range(4)}
    for k in range(4):
        z = floor + 0.2 + 0.75 * k + 0.03
        bx = sx - sw / 2 + 0.1
        while bx < sx + sw / 2 - 0.15:
            bw, bh = 0.05 + 0.06 * rnd.random(), 0.42 + 0.22 * rnd.random()
            books[rnd.randrange(4)].append(placed((bx + bw / 2, cy + 1.75, z + bh / 2), (bw, 0.28, bh)))
            bx += bw + 0.01 + (0.25 if rnd.random() < 0.08 else 0)
    for c, mats in books.items():
        kit.boxes(f"{name}-books{c}", mats, kit.mat(f"{name}-book{c}", book_cols[c], roughness=0.8))
    kit.boxes(f"{name}-papers", [placed((desk_x + (rnd.random() - 0.5) * 0.5, cy + 0.3 + (rnd.random() - 0.5) * 1.2,
                                         cz - 1.155 + 0.004 * k), (0.32, 0.42, 0.005), rnd.random() * 1.2)
                                 for k in range(9)], paper)
    kit.cylinders(f"{name}-inkwell", [((desk_x + facing * 0.15, cy - 0.35, cz - 1.1), 0.05, 0.08)],
                  kit.mat(f"{name}-ink", (0.02, 0.02, 0.03), roughness=0.2))
    if not (use_assets and assets.prop("wooden_candlestick", (desk_x - facing * 0.2, cy - 0.55, desk_top), 0.0,
                                       height=0.24, name=f"{name}-candlestick")):
        kit.cylinders(f"{name}-candle", [((desk_x - facing * 0.2, cy - 0.55, cz - 1.05), 0.03, 0.22)], paper)
    if use_assets:           # a worn bookcase against the side wall, front to the room
        assets.prop("wooden_bookshelf_worn", (cx - facing * 1.0, cy - 1.6, floor), math.pi,
                    height=2.06, name=f"{name}-bookcase")
    kit.ico(f"{name}-candle-flame", (desk_x - facing * 0.2, cy - 0.55, cz - 0.9), 0.025,
            look.neon(f"{name}-candle-flame", lamp_color, 30.0), subdivisions=1)
    kit.boxes(f"{name}-chair", [placed((desk_x - facing * 0.6, cy - 0.2, floor + 0.45), (0.45, 0.45, 0.05)),
                                placed((desk_x - facing * 0.82, cy - 0.2, floor + 0.85), (0.05, 0.45, 0.8))], wood)
    kit.boxes(f"{name}-bed", [placed((back + facing * 0.6, cy - 1.3, floor + 0.3), (1.1, 1.3, 0.5))],
              kit.mat(f"{name}-blanket", (0.32, 0.12, 0.10), roughness=0.95))
    kit.boxes(f"{name}-picture", [placed((back + facing * 0.12, cy - 0.3, cz + 0.5), (0.04, 0.9, 0.7))], wood)
    kit.boxes(f"{name}-canvas", [placed((back + facing * 0.15, cy - 0.3, cz + 0.5), (0.02, 0.75, 0.55))],
              kit.mat(f"{name}-paint", (0.25, 0.3, 0.2), roughness=0.9))
    kit.boxes(f"{name}-curtains", [placed((cx - facing * 0.4, cy + d * 0.75, cz + 0.1), (0.06, 0.4, 2.1)) for d in (-1, 1)],
              kit.mat(f"{name}-curtain", (0.34, 0.08, 0.08), roughness=0.95))
    return Vector((desk_x - facing * 0.55, cy - 0.2, cz - 2.0))     # where the writer sits


def street_lamps(xs, ys, z=0.0):
    """Lanterns on posts along the street. Returns [(glass object, light, x)] for the lamplighter."""
    post = kit.mat("lamp-post", (0.04, 0.04, 0.045), roughness=0.5)
    out = []
    posts = []
    for x in xs:
        for y in ys:
            posts.append(placed((x, y, z + 1.6), (0.12, 0.12, 3.2)))
            posts.append(placed((x, y, z + 3.25), (0.36, 0.36, 0.08)))
            m = look.neon(f"lantern-{x:.0f}-{y:.0f}", (1.0, 0.66, 0.30), 0.0, base=(0.25, 0.2, 0.12))
            g = kit.box(f"lantern-{x:.0f}-{y:.0f}", (x, y, z + 3.55), (0.32, 0.32, 0.5), m, bevel=0)
            data = bpy.data.lights.new(f"lamp-{x:.0f}-{y:.0f}", "POINT")
            data.energy = 0.0
            data.color = (1.0, 0.62, 0.28)
            data.shadow_soft_size = 0.15
            data.use_shadow = False
            lo = bpy.data.objects.new(data.name, data)
            kit._link(lo)
            lo.location = (x, y, z + 3.4)
            out.append((m, data, x))
    kit.boxes("lamp-posts", posts, post)
    return out


def light_up(mat, data, frame, strength=9.0, energy=120.0, off_frame=None):
    b = mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
    b.default_value = 0.0
    b.keyframe_insert("default_value", frame=max(1, frame - 3))
    data.energy = 0.0
    data.keyframe_insert("energy", frame=max(1, frame - 3))
    b.default_value = strength
    b.keyframe_insert("default_value", frame=frame)
    data.energy = energy
    data.keyframe_insert("energy", frame=frame)


def switch(ob, on_frame, off_frame=None, total=None):
    """Show `ob` from `on_frame` (hidden before); hide it again from `off_frame`."""
    ob.hide_render = True
    ob.keyframe_insert("hide_render", frame=1)
    if on_frame <= 1:
        ob.hide_render = False
        ob.keyframe_insert("hide_render", frame=1)
    else:
        ob.hide_render = False
        ob.keyframe_insert("hide_render", frame=on_frame)
    if off_frame and (total is None or off_frame < total):
        ob.hide_render = True
        ob.keyframe_insert("hide_render", frame=off_frame)
    ob.hide_render = False


def smoke(chimneys, n_frames, rnd, per=3):
    """Puffs rising from chimneys: soft translucent balls that drift, grow and loop."""
    m = smoke_mat()
    period = int(FPS * 6)
    for i, (x, y, z) in enumerate(chimneys):
        for k in range(per):
            ob = kit.ico(f"smoke-{i}-{k}", (x, y, z), 0.5, m, subdivisions=2, smooth=True)
            ob.visible_shadow = False
            offset = int(period * k / per) + rnd.randrange(period // per)
            for start in range(-offset, n_frames + period, period):
                for t, (dz, sc) in ((0.0, (0.0, 0.3)), (1.0, (5.0, 2.2))):
                    fr = start + int(t * period)
                    ob.location = (x + 1.6 * t, y + 0.6 * t, z + dz)
                    ob.scale = (sc, sc, sc)
                    ob.keyframe_insert("location", frame=fr)
                    ob.keyframe_insert("scale", frame=fr)
            kit._linear(ob)


# ---------------------------------------------------------------------------
# street life: things and people that make a place lived in
# ---------------------------------------------------------------------------

def wheels(name, items, material, segments=14):
    """items: [(loc, radius, width)] wheels with their axles along y."""
    bm = bmesh.new()
    for loc, r, wdt in items:
        m = Matrix.Translation(loc) @ Matrix.Rotation(math.pi / 2, 4, "X")
        bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=r, radius2=r, depth=wdt, matrix=m)
    return kit._mesh_object(name, bm, material)


def _mats():
    return {"wood": kit.mat("prop-wood", (0.20, 0.11, 0.05), roughness=0.7),
            "dark": kit.mat("prop-dark", (0.05, 0.04, 0.035), roughness=0.6),
            "sack": kit.mat("prop-sack", (0.42, 0.33, 0.20), roughness=0.95),
            "iron": kit.mat("prop-iron", (0.06, 0.06, 0.065), roughness=0.5),
            "stone": kit.mat("prop-stone", (0.38, 0.36, 0.32), roughness=0.9)}


def handcart(name, at, mats, load=True):
    """A two-wheeled handcart (bed, sides, shafts, sacks), as an empty its parts hang from, so it
    can be pushed along a street. Its front points to +x."""
    root = kit._link(bpy.data.objects.new(name, None))
    root.location = at
    parts = [kit.boxes(f"{name}-bed", [placed((0, 0, 0.75), (1.7, 1.0, 0.08)), placed((0, 0.5, 0.95), (1.7, 0.06, 0.35)),
                                       placed((0, -0.5, 0.95), (1.7, 0.06, 0.35)), placed((-0.85, 0, 0.95), (0.06, 1.0, 0.35)),
                                       placed((1.45, 0.38, 0.8), (1.3, 0.06, 0.06)), placed((1.45, -0.38, 0.8), (1.3, 0.06, 0.06))],
                       mats["wood"]),
             wheels(f"{name}-wheels", [((0.1, 0.58, 0.45), 0.45, 0.08), ((0.1, -0.58, 0.45), 0.45, 0.08)], mats["dark"])]
    if load:
        parts.append(kit.balls(f"{name}-sacks", [(-0.4, -0.2, 1.05), (0.15, 0.2, 1.05), (-0.2, 0.25, 1.15)], 0.32,
                               mats["sack"], subdivisions=2, smooth=True))
    for p in parts:
        p.parent = root
    return root


def push(cart, path, f0, f1, ahead=2.3):
    """Move a cart along a walker's path, `ahead` metres in front of them, turned the way they go."""
    pts = [Vector(p) for p in path]
    lens = [(b - a).length for a, b in zip(pts, pts[1:])]
    total = sum(lens) or 1.0
    done, frame = 0.0, f0
    for (a, b), L in zip(zip(pts, pts[1:]), lens):
        d = (b - a).normalized() if L else Vector((1, 0, 0))
        g1 = f0 + (f1 - f0) * (done + L) / total
        cart.rotation_euler = (0, 0, math.atan2(-d.y, -d.x))     # shafts towards the one pushing
        for fr, p in ((frame, a), (g1, b)):
            cart.location = p + d * ahead
            cart.keyframe_insert("location", frame=round(fr))
            cart.keyframe_insert("rotation_euler", frame=round(fr))
        done += L
        frame = g1
    kit._linear(cart)


def stall(name, at, mats, rnd, canopy=(0.50, 0.09, 0.07), use_assets=False):
    """A market stall: trestle table with apples, cabbages and loaves, four posts, a striped canopy.
    `at` is the front centre; the stall stands with its back to the houses (towards -y)."""
    x, y, _ = at
    stripe = kit.mat(f"{name}-stripe", canopy, roughness=0.9)
    plain = kit.mat("stall-canvas", (0.80, 0.74, 0.62), roughness=0.9)
    for m in (stripe, plain):
        m.use_backface_culling = False
    kit.boxes(f"{name}-frame", [placed((x, y, 0.85), (2.4, 1.0, 0.08)), placed((x, y, 0.42), (2.2, 0.9, 0.06))]
              + [placed((x + dx, y + dy, 1.25), (0.08, 0.08, 2.5)) for dx in (-1.15, 1.15) for dy in (-0.45, 0.45)],
              mats["wood"])
    kit.boxes(f"{name}-canopy-a", [tilted((x - 1.2 + 0.4 * (k + 0.5), y - 0.05, 2.55), (0.4, 1.4, 0.04), 0.25)
                                   for k in range(0, 6, 2)], stripe)
    kit.boxes(f"{name}-canopy-b", [tilted((x - 1.2 + 0.4 * (k + 0.5), y - 0.05, 2.55), (0.4, 1.4, 0.04), 0.25)
                                   for k in range(1, 6, 2)], plain)
    goods = {"apples": ((0.55, 0.08, 0.05), 0.09), "cabbages": ((0.22, 0.38, 0.12), 0.16),
             "pears": ((0.62, 0.55, 0.15), 0.09)}
    for g, (colour, r) in goods.items():
        cx = x + {"apples": -0.7, "cabbages": 0.0, "pears": 0.7}[g]
        pts = [(cx + (rnd.random() - 0.5) * 0.55, y + (rnd.random() - 0.5) * 0.6, 0.9 + r + 0.05 * rnd.random())
               for _ in range(9 if r < 0.1 else 5)]
        kit.balls(f"{name}-{g}", pts, r, kit.mat(f"goods-{g}", colour, roughness=0.6), subdivisions=2, smooth=True)
    # wicker baskets and a crate on the ground in front (the boxes stay when the models are missing)
    if not (use_assets and all(assets.prop(m, loc, rot, height=h, name=f"{name}-{m}")
                               for m, loc, rot, h in (
                ("wicker_basket_01", (x - 0.9, y + 0.75, 0.0), 0.4, 0.22),
                ("wicker_basket_01", (x + 0.8, y + 0.8, 0.0), 2.2, 0.2),
                ("wooden_crate_01", (x, y + 1.0, 0.0), 0.1, 0.36)))):
        kit.boxes(f"{name}-baskets", [placed((x - 0.9, y + 0.75, 0.2), (0.5, 0.4, 0.4)),
                                      placed((x + 0.8, y + 0.8, 0.18), (0.45, 0.4, 0.36))], mats["sack"])
    return (x, y - 0.75, 0)                    # where the seller stands


def clutter(name, spots, mats, rnd):
    """Barrels, crates and sacks by the doors: spots [(x, y)]."""
    barrels, crates, sacks = [], [], []
    for x, y in spots:
        kind = rnd.random()
        if kind < 0.45:
            barrels.append(((x, y, 0.42), 0.3, 0.84))
            if rnd.random() < 0.5:
                barrels.append(((x + 0.62, y + 0.05, 0.42), 0.3, 0.84))
        elif kind < 0.8:
            crates.append(placed((x, y, 0.3), (0.6, 0.6, 0.6), rnd.random() * 0.4))
            if rnd.random() < 0.6:
                crates.append(placed((x + 0.05, y, 0.85), (0.5, 0.5, 0.5), rnd.random() * 0.5))
        else:
            sacks += [(x, y, 0.3), (x + 0.45, y + 0.1, 0.28)]
    if barrels:
        kit.cylinders(f"{name}-barrels", barrels, mats["wood"])
    if crates:
        kit.boxes(f"{name}-crates", crates, mats["wood"])
    if sacks:
        kit.balls(f"{name}-sacks", sacks, 0.3, mats["sack"], subdivisions=2, smooth=True)


def pump(name, at, mats):
    """A cast-iron street pump over a stone trough."""
    x, y, _ = at
    kit.boxes(f"{name}-trough", [placed((x, y, 0.3), (1.4, 0.6, 0.6))], mats["stone"])
    kit.cylinders(f"{name}-post", [((x, y + 0.45, 0.8), 0.14, 1.6), ((x, y + 0.45, 1.7), 0.2, 0.2)], mats["iron"])
    kit.boxes(f"{name}-spout", [placed((x, y + 0.2, 1.25), (0.08, 0.4, 0.08))], mats["iron"])


def trees(name, spots, rnd):
    """Bare-ish town trees: trunk and a few lumpy crowns (dark leaves for evening)."""
    bark = kit.mat("tree-bark", (0.09, 0.06, 0.04), roughness=0.9)
    leaf = kit.mat("tree-leaf", (0.07, 0.12, 0.05), roughness=0.85)
    kit.cylinders(f"{name}-trunks", [((x, y, 1.6), 0.18, 3.2) for x, y in spots], bark)
    crowns = []
    for x, y in spots:
        for _ in range(3):
            crowns.append((x + (rnd.random() - 0.5) * 1.2, y + (rnd.random() - 0.5) * 1.2, 3.8 + rnd.random() * 1.2))
    kit.balls(f"{name}-crowns", crowns, 1.1, leaf, subdivisions=1)


def laundry(name, lines, rnd):
    """Washing hung across a back street: lines [((x, y0), (x, y1), z)]."""
    rope = kit.mat("laundry-rope", (0.3, 0.28, 0.24))
    kit.rods(f"{name}-ropes", [((x0, y0, z), (x1, y1, z)) for (x0, y0), (x1, y1), z in lines], 0.015, rope)
    cloths = {c: [] for c in range(4)}
    colours = [(0.75, 0.72, 0.66), (0.42, 0.12, 0.10), (0.18, 0.24, 0.42), (0.62, 0.56, 0.38)]
    for (x0, y0), (x1, y1), z in lines:
        n = 4 + rnd.randrange(4)
        for k in range(n):
            f = (k + 0.5 + 0.3 * (rnd.random() - 0.5)) / n
            w, h = 0.4 + 0.4 * rnd.random(), 0.5 + 0.5 * rnd.random()
            cloths[rnd.randrange(4)].append(placed((x0 + (x1 - x0) * f, y0 + (y1 - y0) * f, z - h / 2),
                                                   (0.04, w, h)))
    for c, mats in cloths.items():
        if mats:
            kit.boxes(f"{name}-cloth{c}", mats, kit.mat(f"cloth{c}", colours[c], roughness=0.95))


def birds(name, n_frames, rnd, count=9, start=(-80.0, 30.0, 28.0), end=(60.0, -20.0, 34.0)):
    """A flock crossing the sky over the roofs, each bird bobbing on its own."""
    m = kit.mat("bird", (0.03, 0.03, 0.035))
    for k in range(count):
        off = Vector(((rnd.random() - 0.5) * 8, (rnd.random() - 0.5) * 8, (rnd.random() - 0.5) * 3))
        ob = kit.boxes(f"{name}-{k}", [Matrix.Translation((-0.25, 0, 0)) @ Matrix.Rotation(0.35, 4, "Y")
                                       @ Matrix.Diagonal((0.55, 0.12, 0.03, 1)),
                                       Matrix.Translation((0.25, 0, 0)) @ Matrix.Rotation(-0.35, 4, "Y")
                                       @ Matrix.Diagonal((0.55, 0.12, 0.03, 1))], m)
        ob.visible_shadow = False
        a, b = Vector(start) + off, Vector(end) + off
        steps = 8
        for i in range(steps + 1):
            t = i / steps
            ob.location = a.lerp(b, t) + Vector((0, 0, 0.6 * math.sin(t * 9 + k)))
            ob.keyframe_insert("location", frame=1 + round(t * n_frames))
            ob.scale = (1, 1, 1 if i % 2 else -1)                    # wings up, wings down
            ob.keyframe_insert("scale", frame=1 + round(t * n_frames))
        kit._linear(ob)


def chatter_keys(obs, turns, n, rnd):
    """Key a standing group's talk: the talker gestures and moves their lips, the others listen."""
    times = [t for t, _ in turns] + [n / FPS]
    for (t, k), t_next in zip(turns, times[1:]):
        f0, f1 = frames(t), frames(t_next)
        for i, ob in enumerate(obs):
            characters.key_cell(ob, f0, pose=("talk" if rnd.random() < 0.7 else "point") if i == k else "stand",
                                expression=rnd.choice(("smile", "neutral", "smile", "worried")) if i == k else None,
                                mouth="rest")
        fr = f0 + 2
        while fr < f1 - 3:
            characters.key_cell(obs[k], fr, mouth=rnd.choice(("half", "open", "closed", "half", "wide")))
            fr += rnd.randint(3, 6)
        characters.key_cell(obs[k], max(f0 + 1, f1 - 2), mouth="rest")


def groups(prefix, specs, n, seed, tint):
    """Place standing groups from world_plan.street_groups and key their conversation."""
    rnd = random.Random(seed)
    for g, spec in enumerate(specs):
        obs = []
        for i, (who, at) in enumerate(zip(spec["who"], spec["at"])):
            ob = characters.actor(f"{prefix}-{g}-{i}", who, at, PERSON_H, tint=tint)
            characters.blinks(ob, n, seed + 300 + 10 * g + i)
            obs.append(ob)
        chatter_keys(obs, spec["turns"], n, rnd)


# ---------------------------------------------------------------------------
# scenes
# ---------------------------------------------------------------------------

def clinic_doors(s, n, seconds, seed, time):
    """Two doors on the courtyard side of the west wing (x = 52): the First Clinic (y = -6) and the
    Second (y = +6), each under a lantern. Women queue at the second; at the first, students come
    and go. The woman who pleads at the first door is a storyboard cast member, not built here."""
    wood = kit.mat("door-wood", (0.13, 0.07, 0.035), roughness=0.6)
    stone = kit.mat("door-stone", (0.55, 0.52, 0.45), roughness=0.85)
    for y in (-6.0, 6.0):
        kit.boxes(f"clinic-door{y:+.0f}", [placed((52.08, y, 1.4), (0.16, 1.8, 2.8))], wood)
        kit.boxes(f"clinic-frame{y:+.0f}", [placed((52.12, y, 2.95), (0.24, 2.4, 0.3)),
                                            placed((52.12, y - 1.05, 1.4), (0.24, 0.3, 2.8)),
                                            placed((52.12, y + 1.05, 1.4), (0.24, 0.3, 2.8)),
                                            placed((52.6, y, 0.08), (1.0, 2.4, 0.16))], stone)
        # a two-leaf panelled door: three raised panels a leaf, the meeting stile, iron ring handles, and
        # a keystone and cornice over the frame
        panels = [placed((52.17, y + side * 0.45, z), (0.03, 0.62, h))
                  for side in (-1, 1) for z, h in ((0.55, 0.7), (1.45, 0.8), (2.35, 0.6))]
        kit.boxes(f"clinic-panels{y:+.0f}", panels, kit.mat("door-panel", (0.17, 0.09, 0.045), roughness=0.55))
        kit.boxes(f"clinic-stile{y:+.0f}", [placed((52.17, y, 1.4), (0.04, 0.05, 2.8))],
                  kit.mat("door-seam", (0.03, 0.02, 0.012), roughness=0.7))
        iron = kit.mat("door-iron", (0.06, 0.06, 0.065), roughness=0.35)
        kit.cylinders(f"clinic-knobs{y:+.0f}", [((52.2, y + dy, 1.25), 0.05, 0.06) for dy in (-0.12, 0.12)], iron)
        kit.boxes(f"clinic-head{y:+.0f}", [placed((52.2, y, 3.18), (0.32, 2.8, 0.16)),
                                           placed((52.2, y, 2.98), (0.3, 0.34, 0.42))], stone)
        m = look.neon(f"door-lamp{y:+.0f}", (1.0, 0.64, 0.30), 8.0)
        kit.box(f"door-lamp{y:+.0f}", (52.35, y + 1.6, 3.1), (0.28, 0.28, 0.4), m, bevel=0)
        data = bpy.data.lights.new(f"door-light{y:+.0f}", "POINT")
        data.energy = 140.0
        data.color = (1.0, 0.62, 0.3)
        data.use_shadow = False
        lo = bpy.data.objects.new(data.name, data)
        kit._link(lo)
        lo.location = (53.2, y + 1.4, 3.0)
    s.pin("first", (52.2, -6.0, 1.5))
    s.pin("second", (52.2, 6.0, 1.5))
    rnd = random.Random(seed + 5)
    # the court itself: cobbles, a pump, benches, two trees, a parked cart
    kit.box("court-floor", (65.0, 0.0, 0.006), (26.0, 28.0, 0.012), cobbles("court-cobbles", 3.2), bevel=0)
    mats = _mats()
    pump("court-pump", (66.0, 0.0, 0), mats)
    kit.boxes("court-benches", [placed((60.0, sy * 10.5, 0.45), (2.2, 0.5, 0.08)) for sy in (-1, 1)]
              + [placed((60.0 + dx, sy * 10.5, 0.22), (0.1, 0.45, 0.44)) for sy in (-1, 1) for dx in (-0.9, 0.9)],
              mats["wood"])
    trees("court-trees", [(71.0, -9.0), (71.0, 9.0), (59.0, 12.0)], rnd)
    cart = handcart("court-cart", (74.0, 4.0, 0), mats)
    cart.rotation_euler = (0, 0, 2.6)
    clutter("court-clutter", [(76.5, -12.5), (76.5, 12.0), (53.2, 12.5)], mats, rnd)
    # an orderly pair carrying a covered stretcher across the court towards the First Clinic
    sheet = kit.mat("stretcher-sheet", (0.72, 0.70, 0.64), roughness=0.9)
    stretcher = kit.box("stretcher", (75.0, -11.0, 0.95), (2.0, 0.6, 0.2), sheet, bevel=0.05)
    f0, f1 = max(1, int(n * 0.05)), max(2, int(n * 0.85))
    for k, dx in enumerate((-1.25, 1.25)):
        ob = characters.actor(f"orderly-{k}", "townsman", (75.0 + dx, -11.0, 0), PERSON_H, tint=0.95)
        characters.walk(ob, [(75.0 + dx, -11.0, 0), (55.5 + dx, -7.8, 0)], f0, f1)
        characters.blinks(ob, n, seed + 80 + k)
    stretcher.keyframe_insert("location", frame=f0)
    stretcher.location = (55.5, -7.8, 0.95)
    stretcher.keyframe_insert("location", frame=f1)
    kit._linear(stretcher)
    # students talking by the First Clinic, a midwife crossing between the doors
    groups("court-talk", [{"who": ["student", "doctor", "student"],
                           "at": [(55.0, -9.6, 0), (55.8, -10.3, 0), (54.6, -10.6, 0)],
                           "turns": plan.chatter(seconds, seed=seed + 7, people=3)}], n, seed + 9, 0.95)
    nurse = characters.actor("court-midwife", "midwife", (54.2, 4.2, 0), PERSON_H, tint=0.95)
    characters.walk(nurse, [(54.2, 4.2, 0), (54.6, -3.8, 0)], max(1, int(n * 0.1)), max(2, int(n * 0.55)))
    characters.walk(nurse, [(54.6, -3.8, 0), (57.5, -2.0, 0)], max(3, int(n * 0.6)), max(4, int(n * 0.95)))
    characters.blinks(nurse, n, seed + 88)
    # the queue at the Second Clinic: mothers waiting, a midwife at the door
    for k in range(8):
        y = 6.0 + 0.2 * (rnd.random() - 0.5)
        x = 53.6 + 1.15 * k
        who = "mother" if k else "midwife"
        ob = characters.actor(f"queue-{k}", who, (x, y + (0.4 if k % 2 else -0.3), 0), PERSON_H,
                              expression="worried" if who == "mother" else "neutral", tint=0.95)
        characters.blinks(ob, n, seed + 50 + k)
        if who == "midwife":
            characters.key_cell(ob, max(1, n // 3), pose="talk")
            characters.key_cell(ob, max(1, n // 3 + int(FPS * 1.5)), pose="stand")
    # students crossing the court from the dissecting room to the First Clinic
    for k in range(2):
        ob = characters.actor(f"student-{k}", "student", (64.0 + 2 * k, -10.0 + k, 0), PERSON_H, tint=0.95)
        characters.walk(ob, [(64.0 + 2 * k, -10.0 + k, 0), (54.6 + 0.9 * k, -8.2 + 0.5 * k, 0)],
                        max(1, int(n * 0.15)), max(2, int(n * 0.8)))
        characters.blinks(ob, n, seed + 60 + k)
    # light in the court
    warm = time.split(">")[-1] in ("dawn", "dusk")
    fill = kit.common.add_area_light("court-fill", (64, 4, 14), 260.0, color=(1.0, 0.8, 0.62) if warm else (0.6, 0.68, 0.9),
                                     size=10)
    kit.common.aim(fill, (54, 0, 0))


def _body_height(u, v):
    """How far a body lying on its back (head toward -u) lifts a sheet above the table at (u, v), metres."""
    def ell(cu, cv, ru, rv, hz):
        q = 1.0 - ((u - cu) / ru) ** 2 - ((v - cv) / rv) ** 2
        return hz * math.sqrt(q) if q > 0 else 0.0
    h = max(ell(-0.80, 0.0, 0.12, 0.10, 0.20),          # head
            ell(-0.36, 0.0, 0.30, 0.21, 0.21),          # chest
            ell(0.02, 0.0, 0.20, 0.19, 0.17),           # hips
            ell(-0.58, 0.0, 0.07, 0.07, 0.11))          # neck
    for side in (-1, 1):
        h = max(h, ell(-0.30, side * 0.25, 0.30, 0.055, 0.09))    # arms along the sides
        if 0.08 < u < 0.86:
            h = max(h, ell(u, side * 0.09, 1.0, 0.075, 0.12 - 0.05 * (u - 0.08)))   # legs, thinner to the ankle
        h = max(h, ell(0.90, side * 0.09, 0.05, 0.06, 0.19))      # feet, toes up
    return h


def sheet_over_body(name, centre, top, material, half_len=1.13, half_w=0.66, table_half_w=0.45):
    """A sheet laid over a body on a table: it rests on the head, chest, hands and feet, tents across the
    hollows between them, crumples a little, and falls straight down over the table's long edges in soft
    folds. One subdivided mesh, not a box."""
    import bmesh
    cx, cy = centre
    nu, nv = 90, 44
    us = [-half_len + 2 * half_len * i / (nu - 1) for i in range(nu)]
    vs = [-half_w + 2 * half_w * j / (nv - 1) for j in range(nv)]
    over = lambda v: abs(v) <= table_half_w
    base = [[_body_height(u, v) if over(v) else -1.0 for v in vs] for u in us]
    z = [[max(0.0, b) for b in row] for row in base]
    # relax: the cloth spans the gaps, never sinking below what it rests on
    for _ in range(60):
        nz = [row[:] for row in z]
        for i in range(1, nu - 1):
            for j in range(1, nv - 1):
                if not over(vs[j]):
                    continue
                avg = (z[i - 1][j] + z[i + 1][j] + z[i][j - 1] + z[i][j + 1]) / 4
                nz[i][j] = max(base[i][j], 0.6 * avg + 0.4 * z[i][j]) if base[i][j] >= 0 else avg
        z = nz
    rnd = random.Random(23)
    phase = [rnd.uniform(0, 6.3) for _ in range(4)]
    verts = []
    for i, u in enumerate(us):
        for j, v in enumerate(vs):
            if over(v):
                crumple = 0.006 * math.sin(u * 23 + phase[0]) * math.sin(v * 17 + phase[1])
                verts.append((cx + u, cy + v, top + 0.004 + z[i][j] + crumple * min(1.0, z[i][j] * 12)))
            else:
                # past the edge the cloth hangs: the distance past the edge becomes depth below it, with folds
                past = abs(v) - table_half_w
                side = 1 if v > 0 else -1
                ripple = 0.018 * math.sin(u * 13 + phase[2]) + 0.008 * math.sin(u * 31 + phase[3])
                verts.append((cx + u, cy + side * (table_half_w + 0.012 + ripple * min(1.0, past * 6)),
                              top + 0.004 - past * (1.0 + 0.15 * math.sin(u * 7 + phase[1]))))
    faces = [(i * nv + j, (i + 1) * nv + j, (i + 1) * nv + j + 1, i * nv + j + 1)
             for i in range(nu - 1) for j in range(nv - 1)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    for p in mesh.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, mesh)
    kit._link(ob)
    ob.data.materials.append(material)
    sol = ob.modifiers.new("thickness", "SOLIDIFY")
    sol.thickness = 0.004
    sub = ob.modifiers.new("smooth", "SUBSURF")
    sub.levels = 1
    sub.render_levels = 2
    # a hand slipped out from under the sheet, hanging over the table's edge below the cloth by the hip
    skin = kit.mat(f"{name}-hand", (0.50, 0.44, 0.39), roughness=0.6)
    hx, hy = cx - 0.05, cy - table_half_w - 0.035
    kit.boxes(f"{name}-hand", [placed((hx, hy, top - 0.17), (0.075, 0.03, 0.12)),
                               placed((hx, hy + 0.004, top - 0.08), (0.06, 0.035, 0.1))]
              + [placed((hx - 0.027 + 0.018 * k, hy, top - 0.27 + 0.01 * abs(k - 1.5)), (0.014, 0.016, 0.075))
                 for k in range(4)], skin)
    return ob


def anatomy(s, n, seed, x0=200.0, use_assets=False, people=True, west_door=False, roof=False):
    """The dissecting room, apart from the town: a long table with a body under a sheet, a lamp
    over it, a professor (Kolletschka) and students around it (`people`). `west_door` opens the
    west wall onto the corridor the `wing` scene joins to the ward. `roof` closes the top: without
    it the room is open to the sky, and under a dusk world the sky floods the floor white."""
    wall = kit.mat("anat-wall", (0.45, 0.42, 0.36), roughness=0.9)
    wood = kit.mat("anat-wood", (0.14, 0.08, 0.04), roughness=0.6)
    sheet = kit.mat("anat-sheet", (0.62, 0.60, 0.56), roughness=0.9)
    west = [((x0 - 7.15, -4, 0), (x0 - 6.85, 4, 6))]
    if west_door:
        west = subtract(west[0][0], west[0][1], (x0 - 8, -0.75, -1), (x0 - 6, 0.75, 2.5))
    kit.boxes("anat-room", [placed((x0, 4.0, 3.0), (14, 0.3, 6)), placed((x0 + 7, 0, 3.0), (0.3, 8, 6))]
              + [placed(tuple((a + b) / 2 for a, b in zip(lo, hi)), tuple(b - a for a, b in zip(lo, hi)))
                 for lo, hi in west]
              + ([placed((x0, 0.0, 6.0), (14, 8, 0.2))] if roof else []), wall)
    kit.boxes("anat-table", [placed((x0, 0.6, 0.85), (2.4, 0.9, 0.08)), placed((x0 - 1.0, 0.6, 0.42), (0.1, 0.7, 0.84)),
                             placed((x0 + 1.0, 0.6, 0.42), (0.1, 0.7, 0.84))], wood)
    # a herringbone brick floor of its own (the walls are stone), dark oak panelling to chest height with a
    # rail on the back and east walls, and a table with an apron rather than a slab on two boards
    kit.box("anat-floor", (x0, 0, -0.02), (14, 8, 0.04), kit.mat("anat-floor", (0.30, 0.24, 0.19), roughness=0.9),
            bevel=0)
    panel = kit.mat("anat-panel", (0.10, 0.06, 0.035), roughness=0.55)
    kit.boxes("anat-wainscot", [placed((x0, 3.82, 0.6), (14, 0.06, 1.2)), placed((x0 + 6.82, 0, 0.6), (0.06, 8, 1.2)),
                                placed((x0, 3.78, 1.22), (14, 0.12, 0.06)), placed((x0 + 6.78, 0, 1.22), (0.12, 8, 0.06)),
                                placed((x0, 3.79, 0.06), (14, 0.1, 0.12)), placed((x0 + 6.79, 0, 0.06), (0.1, 8, 0.12))],
              panel)
    kit.boxes("anat-apron", [placed((x0, 0.6, 0.74), (2.3, 0.8, 0.14))]
              + [placed((x0 + dx, 0.6 + dy, 0.37), (0.08, 0.08, 0.74)) for dx in (-1.05, 1.05) for dy in (-0.33, 0.33)],
              wood)
    body = sheet_over_body("anat-body", (x0, 0.6), 0.89, sheet)
    m = look.neon("anat-lamp", (1.0, 0.7, 0.4), 10.0)
    kit.box("anat-lampshade", (x0, 0.6, 3.2), (0.5, 0.5, 0.25), m, bevel=0)
    data = bpy.data.lights.new("anat-light", "POINT")
    data.energy = 350.0
    data.color = (1.0, 0.75, 0.5)
    data.shadow_soft_size = 0.3
    lo = bpy.data.objects.new("anat-light", data)
    kit._link(lo)
    lo.location = (x0, 0.6, 3.0)
    win = look.neon("anat-window", (0.6, 0.7, 0.9), 1.5)
    kit.boxes("anat-windows", [placed((x0 + dx, 3.84, 3.6), (1.4, 0.05, 2.0)) for dx in (-4, 0, 4)], win)
    # a working room: jars on shelves along the back wall, a basin, instruments, a second lamp
    rnd = random.Random(seed + 40)
    kit.boxes("anat-shelves", [placed((x0 + sx, 3.65, 0.9 + 0.7 * k), (3.2, 0.5, 0.05)) for sx in (-4.2, 4.2) for k in range(3)],
              wood)
    jar_glass = kit.mat("anat-jar", (0.62, 0.55, 0.22), roughness=0.15)
    jars = [((x0 + sx - 1.4 + 0.42 * j + 0.1 * rnd.random(), 3.6, 0.9 + 0.7 * k + 0.2), 0.12 + 0.04 * rnd.random(), 0.36)
            for sx in (-4.2, 4.2) for k in range(3) for j in range(7) if rnd.random() < 0.75]
    kit.cylinders("anat-jars", jars, jar_glass)
    if use_assets:           # two painted shelf units between the jar shelves, a vase on each
        for sx in (-1.3, 1.3):
            if assets.prop("painted_wooden_shelves", (x0 + sx, 3.55, 0.0), 0.0, height=1.12, name=f"anat-shelves-{sx:+.1f}"):
                assets.prop("ceramic_vase_01", (x0 + sx, 3.55, 1.12), 0.0, height=0.32, name=f"anat-vase-{sx:+.1f}")
    kit.cylinders("anat-basin", [((x0 + 5.6, -2.6, 0.45), 0.08, 0.9), ((x0 + 5.6, -2.6, 0.95), 0.45, 0.12)],
                  kit.mat("anat-basin", (0.5, 0.5, 0.48), roughness=0.4))
    kit.boxes("anat-tray", [placed((x0 + 1.6, -0.3, 0.75), (0.7, 0.45, 0.04)),
                            placed((x0 + 1.6, -0.3, 0.37), (0.06, 0.06, 0.74))],
              kit.mat("anat-steel", (0.45, 0.46, 0.48), metallic=0.6, roughness=0.35))
    kit.boxes("anat-door", [placed((x0 + 6.84, -1.5, 1.2), (0.1, 1.3, 2.4))], wood)
    # a student's scalpel at the sheet's edge; `slip` moves it and a drop of blood spreads on the sheet
    steel = kit.mat("anat-blade", (0.62, 0.63, 0.66), metallic=0.8, roughness=0.25)
    scalpel = kit.boxes("anat-scalpel", [placed((x0 + 0.55, 0.3, 0.905), (0.16, 0.012, 0.006), 0.35),
                                         placed((x0 + 0.42, 0.25, 0.905), (0.14, 0.018, 0.012), 0.35)], steel)
    blood = kit.mat("anat-blood", (0.32, 0.02, 0.02), roughness=0.35)
    drop = kit.cylinders("anat-drop", [((x0 + 0.62, 0.22, 0.897), 0.03, 0.004)], blood, segments=20)
    drop.scale = (0.001, 0.001, 1.0)
    s.pin("scalpel", (x0 + 0.5, 0.3, 0.91))

    def act_slip(t0, t1):
        f0, f1 = frames(t0), max(frames(t0) + 3, frames(t0 + 0.25))
        kit.move(scalpel, f0, f1, (0.07, -0.05, 0.0))
        drop.scale = (0.001, 0.001, 1.0)
        drop.keyframe_insert("scale", frame=f1)
        drop.scale = (1.0, 1.0, 1.0)
        drop.keyframe_insert("scale", frame=max(f1 + 2, frames(t1)))

    if getattr(s, "slip", False):           # registered only when asked: every action runs once
        s.action("slip", act_slip, at=0.4, span=0.6)
    if not people:
        s.pin("table", (x0, 0.6, 1.0), hold=[body])
        s.pin("jars", (x0 - 4.2, 3.6, 1.8))
        return body
    people = [("kolletschka", -1.6, 1.5, "talk"), ("student", 0.0, 1.9, "stand"), ("student", 1.5, 1.6, "stand"),
              ("student", -0.6, 2.7, "stand"), ("student", -2.4, 0.2, "stand"), ("doctor", 2.6, 0.4, "stand")]
    obs = []
    for k, (who, dx, dy, pose) in enumerate(people):
        ob = characters.actor(f"anat-{k}", who, (x0 + dx, dy, 0), PERSON_H, pose=pose, tint=1.0)
        characters.blinks(ob, n, seed + 70 + k)
        obs.append(ob)
    # the professor lectures and points; students lean in, one looks shocked; two more come in late
    k_ob = obs[0]
    t = 0
    while t < n - FPS:
        characters.key_cell(k_ob, max(1, t), pose=rnd.choice(("talk", "point", "talk")))
        fr = t + 2
        while fr < t + int(FPS * 1.6):
            characters.key_cell(k_ob, fr, mouth=rnd.choice(("half", "open", "closed", "wide")))
            fr += rnd.randint(3, 6)
        characters.key_cell(k_ob, t + int(FPS * 1.6), mouth="rest")
        t += int(FPS * (1.8 + rnd.random()))
    for k, ob in enumerate(obs[1:], 1):
        fr = int(FPS * (1 + 2.5 * rnd.random()))
        while fr < n - FPS:
            characters.key_cell(ob, fr, expression=rnd.choice(("neutral", "worried", "shocked", "neutral")),
                                pose=rnd.choice(("stand", "stand", "point")))
            fr += int(FPS * (2 + 3 * rnd.random()))
    for k in range(2):
        late = characters.actor(f"anat-late-{k}", "student", (x0 + 6.4, -1.5 + 0.6 * k, 0), PERSON_H, tint=1.0)
        characters.walk(late, [(x0 + 6.4, -1.5 + 0.6 * k, 0), (x0 + 3.0 + 0.8 * k, 1.9 + 0.5 * k, 0)],
                        max(1, int(n * (0.15 + 0.2 * k))), max(2, int(n * (0.45 + 0.2 * k))))
        characters.blinks(late, n, seed + 90 + k)
    s.pin("table", (x0, 0.6, 1.0), hold=[body])
    s.pin("jars", (x0 - 4.2, 3.6, 1.8))


def vienna(p, seconds):
    """A town of plastered houses on cobbled streets, and the general hospital across the end of
    the main street. `time`: dusk | night | dawn | "dusk>night". Windows come on house by house
    (`lit` share), the lamplighter lights the street lamps, people walk and greet."""
    from scenes import Set
    s = Set(seconds)
    s.lighting = "world"
    s.lens = 40.0
    n = s.frames
    time = p.get("time", "dusk>night")
    seed = int(p.get("seed", 7))
    use_assets = bool(p.get("assets", True))
    rnd = random.Random(seed)
    ground = kit.mat("ground-earth", (0.06, 0.055, 0.05), roughness=0.95)
    kit.box("ground", (10, 0, -0.05), (400, 300, 0.1), ground, bevel=0)
    street = cobbles()
    kit.boxes("streets", [placed((-15, 0, 0.005), (110, 8, 0.01)), placed((-15, 19, 0.005), (110, 10, 0.01)),
                          placed((-15, -19, 0.005), (110, 10, 0.01)), placed((37, 0, 0.005), (8, 80, 0.01))], street)
    kit.boxes("kerbs", [placed((-15, sy * 4.1, 0.08), (110, 0.25, 0.16)) for sy in (-1, 1)],
              kit.mat("kerb", (0.25, 0.24, 0.22), roughness=0.8))
    town, glass, lit_sets = Town(), [], {}
    houses = town_layout(seed)
    for i, (x, y, w, d, storeys, facing) in enumerate(houses):
        house(town, i, x, y, w, d, storeys, facing, rnd, glass, lit_sets, shop=abs(y) < 12 and rnd.random() < 0.5)
    # which storeys light, and when: dusk brings them on, a few go dark again later
    schedule = plan.window_schedule(sorted(lit_sets), seconds, share=float(p.get("lit", 0.6)), seed=seed,
                                    start=float(p.get("lights_from", 0.05)), end=float(p.get("lights_until", 0.6)))
    dress_shutters(town, set(schedule), random.Random(seed + 31))
    town.build()
    # the street is lived in: a market, carts, barrels by the doors, a pump, trees by the hospital,
    # washing across the back streets, birds over the roofs
    mats = _mats()
    sellers = [stall(f"stall-{k}", (x, -3.0, 0), mats, rnd, AWNINGS[k % len(AWNINGS)], use_assets=use_assets)
               for k, x in enumerate((-31.0, -28.2, -19.0))]
    if use_assets:           # a cluster of barrels at the market's west end (clear of the clutter spots)
        assets.prop("wooden_barrels_01", (-35.5, -3.4, 0.0), 0.3, height=0.92, name="market-barrels")
    clutter("street-clutter", [(-50 + 6.5 * k + rnd.random() * 2, rnd.choice((-3.6, 3.6))) for k in range(13)
                               if not -33 < -50 + 6.5 * k < -16], mats, rnd)
    pump("street-pump", (-6.0, 3.2, 0), mats)
    parked = handcart("parked-cart", (-41.0, 3.1, 0), mats)
    parked.rotation_euler = (0, 0, 0.25)
    trees("akh-trees", [(38.2, sy * y) for sy in (-1, 1) for y in (9.0, 15.0, 21.0, 27.0)], rnd)
    laundry("laundry", [((x, 14.1), (x + 1.0, 23.9), 6.8 + rnd.random()) for x in (-52, -37, -21, -6, 9)]
            + [((x, -14.1), (x - 0.8, -23.9), 6.6 + rnd.random()) for x in (-45, -28, -12, 3)], rnd)
    if p.get("birds", True):
        birds("birds", n, rnd)
    akh_glass, akh_lit = [], []
    # the lit room looks down the main street (y = -3, just beside the gate), so the descent from
    # the sky to its window flies along the street between the rooftops, never through a house
    room_y, room_z = -3, 2.0 + 4.2
    akh_h = hospital(s, akh_glass, akh_lit, room=(room_y, room_z), use_assets=use_assets)
    # dark glass: one object for every window that never lights (and the hospital's); a storey that
    # lights has its own dark glass, shown only while the storey is dark, so the room behind shows
    dark = kit.mat("glass", (0.015, 0.018, 0.024), roughness=0.25)
    never = [m for key, ms in town.glass_by.items() if key not in schedule for m in ms]
    kit.boxes("glass", never + akh_glass, dark)
    warm = window_light("window-warm")
    # a lit storey = a dim warm pane over a room (back wall, lamp, furniture, curtains), one object
    for key, (on, off) in schedule.items():
        room = town.rooms.get(key, {})
        slots = [(room_material("pane"), lit_sets[key])] + [(room_material(k), ms) for k, ms in sorted(room.items())]
        switch(multi_object(f"lit-{key[0]}-{key[1]}", slots), frames(on), frames(off) if off else None, n)
        switch_off(kit.boxes(f"dark-{key[0]}-{key[1]}", town.glass_by[key], dark), frames(on),
                   frames(off) if off else None, n)
    # one in six lit rooms has someone crossing it, once or twice
    for key, legs in plan.window_lives(sorted(schedule), seconds, seed, schedule=schedule).items():
        wins = town.windows[key]
        silhouette(f"life-{key[0]}-{key[1]}", wins[random.Random(seed + key[0] * 31 + key[1]).randrange(len(wins))],
                   legs, schedule[key][0], schedule[key][1], n)
    # the hospital: some wards lit all evening; the open window of the assistant's room is pinned
    akh_on = [m for (st, yy, fc), m in akh_lit if (st, yy, fc) != (1, room_y, -1) and rnd.random() < 0.45]
    kit.boxes("akh-lit", akh_on, warm)
    seat = room_behind("room", (40.0, room_y, room_z), -1, use_assets=use_assets)
    s.pin("window", (39.9, room_y, room_z + 0.2))
    s.pin("hospital", (40.0, 0.0, akh_h * 0.6))
    lamps = street_lamps([x for x in range(-60, 36, 12)], [-4.6, 4.6])
    order = plan.lamplighter_order([x for _, _, x in lamps], seconds,
                                   start=float(p.get("lamps_from", 0.08)), end=float(p.get("lamps_until", 0.55)))
    for (m, data, x), t in zip(sorted(lamps, key=lambda l: l[2]), order):
        light_up(m, data, frames(t))
    if p.get("smoke", True):
        smoke(town.chimneys[::3], n, rnd)
    s.sky = sky_world(time, seconds)
    sky_lights(time, seconds, (0, 0, 0), 60.0)
    # people of the street: walkers (some pushing carts), sellers at the stalls, neighbours talking
    tint = float(p.get("tint", 0.55))
    people = plan.street_people(seconds, seed=seed, count=int(p.get("walkers", 8)), lanes=(-2.2, -0.9, 0.9, 2.2))
    carts = 0
    for k, w in enumerate(people):
        first = w["legs"][0][0][0]
        ob = characters.actor(f"walker-{k}", w["who"], first, PERSON_H, tint=tint)
        pushing = k >= 2 and k % 5 == 3 and w["who"] in ("townsman", "baker") and carts < 3
        cart = handcart(f"cart-{k}", first, mats, load=True) if pushing else None
        carts += bool(cart)
        for path, t0, t1 in w["legs"]:
            if t1 - t0 > 0.3:
                characters.walk(ob, path, frames(t0), frames(t1))
                if cart:
                    push(cart, path, frames(t0), frames(t1))
        characters.blinks(ob, n, seed + k)
        if w.get("greet"):
            characters.key_cell(ob, frames(w["greet"]), pose="tip-hat", expression="smile")
            characters.key_cell(ob, frames(w["greet"] + 1.3), pose="stand", expression="neutral")
    for k, at in enumerate(sellers):
        seller = characters.actor(f"seller-{k}", ("baker", "townswoman", "townsman")[k], at, PERSON_H, tint=tint)
        characters.blinks(seller, n, seed + 200 + k)
        buyer = characters.actor(f"buyer-{k}", ("townswoman", "midwife", "townswoman")[k],
                                 (at[0] + 0.5, at[1] + 2.0, 0), PERSON_H, tint=tint)
        characters.blinks(buyer, n, seed + 210 + k)
        chatter_keys([seller, buyer], plan.chatter(seconds, seed=seed + 220 + k, people=2), n, random.Random(seed + k))
    groups("street-talk", plan.street_groups(seconds, seed=seed, count=int(p.get("groups", 3)), sides=(3.3,)),
           n, seed + 230, tint)
    # the lamplighter walks the main street ahead of the lamps
    if order:
        path = [(x - 1.2, -3.6, 0) for x in sorted(x for _, _, x in lamps)[::2]]
        lam = characters.actor("lamplighter", "lamplighter", path[0], PERSON_H, tint=float(p.get("tint", 0.55)))
        characters.walk(lam, path, frames(order[0]) - 10, frames(order[-1]))
    # Semmelweis at his desk behind the window, writing, looking up now and then
    writer = characters.actor("writer", "semmelweis", tuple(seat), PERSON_H, pose="wash", tint=1.1)
    characters.blinks(writer, n, seed + 99)
    for t in range(0, int(seconds), 4):
        characters.key_cell(writer, frames(t + 2.5), expression="worried")
        characters.key_cell(writer, frames(t + 3.6), expression="sad")
    s.pins["writer"] = writer
    clinic_doors(s, n, seconds, seed, time)
    s.slip = bool(p.get("slip", False))
    anatomy(s, n, seed, use_assets=use_assets, people=bool(p.get("anatomy_people", True)))
    # views (azimuth: the camera's side of the target; height is absolute)
    s.view("aerial", (39.4, room_y, room_z - 0.6), 130.0, 180, 62.0)
    s.view("roofs", (-10, -3, 9.0), 14.0, 230, 14.5)
    s.view("street", (-8, 0, 1.6), 16.0, 180, 2.3)
    s.view("hospital", (40, 0, 6.0), 34.0, 185, 12.0)
    s.view("window", (39.4, room_y, room_z - 0.6), 3.2, 180, room_z + 0.1)
    s.view("court", (54, 0, 2.0), 15.0, 0, 3.2)
    s.view("doors", (53.0, 0, 2.0), 21.0, 10, 4.2)
    # the camera stands further back (radius 7.5) so the courtyard floor in front of the doors is in frame
    s.view("first-door", (52.6, -6.0, 1.5), 7.5, 25, 1.8)
    # matched to first-door: the same lens, height and distance, mirrored about the court's axis
    s.view("second-door", (52.6, 6.0, 1.5), 7.5, -25, 1.8)
    s.view("anatomy", (200, 0, 1.3), 6.5, -110, 3.0)
    # from up the street (azimuth near the street view's 180), so a move between the two never
    # swings the camera through the house fronts
    s.view("market", (-24.0, -3.0, 1.3), 7.0, 152, 2.1)
    s.view("street-low", (-22.0, 0.0, 1.3), 13.0, 192, 0.9)
    s.view("room", (42.6, room_y, room_z - 0.6), 2.1, 180, room_z - 0.1)
    s.view("desk", (41.0, room_y + 0.1, room_z - 0.85), 1.7, 172, room_z - 0.35)
    s.view("court-wide", (62.0, 0.0, 1.6), 11.0, 20, 4.5)
    s.view("pump", (66.0, 0.0, 1.0), 5.5, 200, 1.7)
    s.view("court-low", (57.0, -7.5, 1.2), 7.0, -35, 1.3)
    # the court from its middle, looking at the First Clinic's door: the benches and pump behind the camera
    s.view("court-near", (54.0, -4.0, 1.3), 7.0, 10, 1.6)
    s.view("anatomy-close", (200.0, 0.8, 1.2), 3.4, -100, 1.9)
    s.view("jars", (195.8, 3.6, 1.8), 2.6, -90, 1.9)
    # v6: the gate at dawn from the street, a birth on the cobbles just outside it, the scalpel
    s.view("gate-approach", (35.0, -1.5, 1.3), 9.0, 182, 1.25)
    s.view("street-birth", (33.4, -2.8, 0.5), 3.4, 205, 0.95)
    s.view("scalpel", (200.5, 0.3, 0.9), 0.9, -105, 1.33)
    s.view("cut-hand", (200.6, 0.24, 0.9), 0.55, -80, 1.18)
    s.floor_grid = 0

    def act_greet(t0, t1):
        pass

    s.action("greet", act_greet, at=0.5, span=1.0)
    if use_assets:
        assets.scene_hdri("street", time, n)
        assets.upgrade_materials()
    return s


def asylum(p, seconds):
    """1865, night: a high wall, an arched gate under a lantern, guards bringing a man in; inside, a
    cell with a barred window and a door that shuts. What happens there is heard and seen as
    shadows on the wall, never shown."""
    from scenes import Set
    s = Set(seconds)
    s.lighting = "world"
    s.lens = 45.0
    n = s.frames
    use_assets = bool(p.get("assets", True))
    wall = kit.mat("asy-wall", (0.36, 0.34, 0.30), roughness=0.9)
    dark = kit.mat("asy-dark", (0.02, 0.018, 0.016))
    iron = kit.mat("asy-iron", (0.05, 0.05, 0.055), roughness=0.5)
    wood = kit.mat("asy-wood", (0.12, 0.07, 0.04), roughness=0.7)
    kit.box("ground", (0, 0, -0.05), (120, 120, 0.1), cobbles("asy-cobbles", 3.0), bevel=0)
    # the outer wall with its gate (at y = 0, facing -y), and the building behind
    kit.boxes("asy-wall", [placed((-9, 0, 2.5), (14, 0.8, 5)), placed((9, 0, 2.5), (14, 0.8, 5)),
                           placed((0, 0, 5.4), (4.4, 0.8, 1.2))], wall)
    kit.boxes("asy-building", [placed((0, 14, 6), (40, 10, 12))], wall)
    kit.boxes("asy-gate", [placed((-1.05, -0.05, 2.4), (2.0, 0.2, 4.8))], wood)        # one leaf open
    leaf = kit.box("asy-gate-leaf", (1.05, -0.05, 2.4), (2.0, 0.2, 4.8), wood, bevel=0)
    glass = []
    for x in range(-16, 17, 4):
        for z in (3.0, 7.0, 10.0):
            glass.append(placed((x, 8.95, z), (1.0, 0.1, 1.6)))
    kit.boxes("asy-windows", glass, dark)
    # dress the wall and the house so they read as masonry, not boxes: a coping along the wall top, piers
    # every few metres and a plinth on the street side, a stone surround with a keystone round the gate,
    # panels and iron straps on its leaves; on the building a cornice, a hipped roof with chimneys, and
    # every window barred, with a sill and a stone head
    stone = kit.mat("asy-stone", (0.46, 0.43, 0.38), roughness=0.85)
    iron_bar = kit.mat("asy-bars", (0.04, 0.04, 0.045), roughness=0.45)
    coping = [placed((side * 9, 0, 5.12), (14.3, 1.0, 0.24)) for side in (-1, 1)] + [placed((0, 0, 6.1), (4.7, 1.0, 0.2))]
    piers = [placed((x, -0.5, 2.45), (0.55, 0.3, 4.9)) for x in (-15.5, -12.0, -8.5, -5.0, 5.0, 8.5, 12.0, 15.5)]
    plinth = [placed((side * 9, -0.46, 0.35), (14, 0.16, 0.7)) for side in (-1, 1)]
    surround = [placed((side * 2.45, -0.5, 2.6), (0.8, 0.3, 5.2)) for side in (-1, 1)]
    surround += [placed((0, -0.5, 5.05), (5.7, 0.32, 0.5)), placed((0, -0.6, 5.0), (0.45, 0.3, 0.7))]
    kit.boxes("asy-masonry", coping + piers + plinth + surround, stone)
    leaf_panels = [placed((dx, -0.17, z), (0.8, 0.03, h)) for dx in (-1.05,) for z, h in ((0.9, 1.2), (2.4, 1.2), (3.9, 1.3))]
    kit.boxes("asy-gate-panels", leaf_panels, kit.mat("asy-gate-panel", (0.15, 0.085, 0.045), roughness=0.6))
    kit.boxes("asy-gate-straps", [placed((-1.05, -0.19, z), (1.9, 0.02, 0.08)) for z in (0.6, 2.4, 4.2)], iron_bar)
    moving = kit.boxes("asy-leaf-straps", [placed((1.05, -0.17, z), (1.9, 0.02, 0.08)) for z in (0.6, 2.4, 4.2)], iron_bar)
    bpy.context.view_layer.update()
    moving.parent = leaf                               # the open leaf swings shut with its straps on
    moving.matrix_parent_inverse = leaf.matrix_world.inverted()
    win_dress, win_bars = [], []
    for x in range(-16, 17, 4):
        for z in (3.0, 7.0, 10.0):
            win_dress += [placed((x, 8.85, z - 0.9), (1.4, 0.3, 0.12)), placed((x, 8.88, z + 0.92), (1.4, 0.24, 0.24)),
                          placed((x - 0.6, 8.9, z), (0.18, 0.2, 1.8)), placed((x + 0.6, 8.9, z), (0.18, 0.2, 1.8))]
            win_bars += [placed((x - 0.3 + 0.2 * k, 8.86, z), (0.035, 0.035, 1.6)) for k in range(4)]
            win_bars += [placed((x, 8.86, z + dz), (1.0, 0.035, 0.035)) for dz in (-0.4, 0.4)]
    win_dress += [placed((0, 8.8, 11.8), (40.6, 0.5, 0.4)), placed((0, 8.85, 4.95), (40.2, 0.3, 0.18))]
    kit.boxes("asy-building-stone", win_dress, stone)
    kit.boxes("asy-building-bars", win_bars, iron_bar)
    _roof_prisms("asy-roof", [(0, 14, 40.8, 10.8, 12.0, 3.4, True)], kit.mat("asy-roof", (0.16, 0.15, 0.17), roughness=0.8))
    kit.boxes("asy-chimneys", [placed((x, 14.5, 14.6), (0.7, 0.7, 2.4)) for x in (-12, -3, 7, 15)]
              + [placed((x, 14.5, 15.85), (0.9, 0.9, 0.15)) for x in (-12, -3, 7, 15)], stone)
    lantern_m = look.neon("asy-lantern", (1.0, 0.62, 0.28), 5.0)
    # the lantern over the gate: the glTF lantern with a small emissive flame inside it
    # (the box is the lantern itself when the model is missing)
    if use_assets and assets.prop("Lantern_01", (0, -0.7, 4.12), 0.0, height=0.58, name="asy-lantern-model"):
        kit.box("asy-lantern", (0, -0.7, 4.32), (0.12, 0.12, 0.14), lantern_m, bevel=0)
    else:
        kit.box("asy-lantern", (0, -0.7, 4.4), (0.4, 0.4, 0.55), lantern_m, bevel=0)
    data = bpy.data.lights.new("asy-lantern", "POINT")
    data.energy = 400.0
    data.color = (1.0, 0.6, 0.28)
    data.shadow_soft_size = 0.05
    lo = bpy.data.objects.new("asy-lantern-light", data)
    kit._link(lo)
    lo.location = (0, -1.3, 4.0)
    # flicker
    rnd = random.Random(3)
    for fr in range(1, n + 1, 4):
        data.energy = 400.0 * (0.85 + 0.3 * rnd.random())
        data.keyframe_insert("energy", frame=fr)
    # the cell (off to the side of the yard, its own little set)
    cx = 30.0
    # the back wall has a real opening, so the moon is seen through the bars and its light falls in
    back = subtract((cx - 4, 2.85, 0), (cx + 4, 3.15, 5), (cx - 0.75, 2.8, 2.9), (cx + 0.75, 3.2, 4.3))
    kit.boxes("cell", [placed(tuple((a + b) / 2 for a, b in zip(lo, hi)), tuple(b - a for a, b in zip(lo, hi)))
                       for lo, hi in back]
              + [placed((cx - 4, 0, 2.5), (0.3, 6, 5)), placed((cx + 4, 0, 2.5), (0.3, 6, 5)),
                 placed((cx, 0, -0.02), (8, 6, 0.04)), placed((cx, 0, 5.05), (8, 6.3, 0.1))], wall)
    bars = [placed((cx - 0.6 + 0.3 * k, 3.0, 3.6), (0.06, 0.2, 1.4)) for k in range(5)]
    bars += [placed((cx, 3.0, 3.6 + dz), (1.5, 0.2, 0.06)) for dz in (-0.35, 0.35)]
    kit.boxes("cell-bars", bars, iron)
    moon = look.neon("cell-moon", (0.55, 0.66, 1.0), 6.0)
    kit.box("cell-sky", (cx, 3.9, 3.6), (2.2, 0.05, 2.0), moon, bevel=0)
    # the moon's shaft through the window onto the floor, and what is in the cell
    beam = bpy.data.materials.new("cell-beam")
    beam.use_nodes = True
    bb = beam.node_tree.nodes["Principled BSDF"]
    bb.inputs["Base Color"].default_value = (0.5, 0.6, 1.0, 1)
    bb.inputs["Emission Color"].default_value = (0.5, 0.6, 1.0, 1)
    bb.inputs["Emission Strength"].default_value = 0.6
    bb.inputs["Alpha"].default_value = 0.07
    beam.surface_render_method = "BLENDED"       # smooth haze; dithered alpha this thin reads as grain
    shaft = kit.rods("cell-shaft", [((cx, 3.0, 3.6), (cx - 0.3, -0.4, 0.05))], 0.6, beam)
    shaft.visible_shadow = False
    straw = kit.mat("cell-straw", (0.42, 0.34, 0.16), roughness=1.0)
    kit.boxes("cell-straw", [placed((cx - 1.3, 1.3, 0.1), (1.1, 2.1, 0.2), 0.08)], straw)
    if not (use_assets and assets.prop("wooden_bucket_01", (cx + 2.9, 2.3, 0.0), 0.0, height=0.45, name="cell-bucket-model")):
        kit.cylinders("cell-bucket", [((cx + 2.9, 2.3, 0.25), 0.25, 0.5)], wood)
    kit.boxes("cell-stool", [placed((cx + 2.0, 0.8, 0.45), (0.5, 0.5, 0.06))]
              + [placed((cx + 2.0 + dx, 0.8 + dy, 0.22), (0.05, 0.05, 0.44)) for dx in (-0.2, 0.2) for dy in (-0.2, 0.2)],
              wood)
    kit.cylinders("cell-bowl", [((cx + 2.0, 0.8, 0.52), 0.12, 0.07)], kit.mat("cell-tin", (0.3, 0.3, 0.32), roughness=0.4))
    kit.rods("cell-chain", [((cx - 3.83, 1.6 + 0.12 * k, 1.4 - 0.12 * (k % 2)), (cx - 3.83, 1.72 + 0.12 * k, 1.4 - 0.12 * ((k + 1) % 2)))
                            for k in range(8)], 0.025, iron)
    door = kit.box("cell-door", (cx + 2.2, -3.0, 1.2), (1.4, 0.15, 2.4), wood, bevel=0)
    mdata = bpy.data.lights.new("cell-moonlight", "SPOT")
    mdata.energy = 420.0            # the moon through the bars, not a flash: the bars must still read
    mdata.color = (0.55, 0.66, 1.0)
    mdata.spot_size = math.radians(35)
    mdata.shadow_soft_size = 0.05
    ml = bpy.data.objects.new("cell-moonlight", mdata)
    kit._link(ml)
    ml.location = (cx, 5.5, 6.5)          # through the window opening (z 2.9-4.3 at y 3) onto the floor
    kit.common.aim(ml, (cx - 0.3, -0.4, 0.0))
    bpy.data.objects["cell-sky"].visible_shadow = False
    s.sky = sky_world("night", seconds)
    sky_lights("night", seconds, (0, 0, 0), 30.0)
    # the guards bring him in: two guards either side, walking from the street into the gate
    t_in, t_out = float(p.get("drag_from", 0.12)) * seconds, float(p.get("drag_until", 0.55)) * seconds
    who = [("guard", -0.9), ("semmelweis-out", 0.0), ("guard", 0.9)]
    for k, (key, dx) in enumerate(who):
        ob = characters.actor(f"asy-{k}", key, (dx, -9.0, 0), PERSON_H, tint=0.9, shadow=False)
        ob.visible_shadow = True          # their shadows fall on the wall: that is the picture
        characters.walk(ob, [(dx, -9.0, 0), (dx * 0.6, -1.0, 0), (dx * 0.6, 3.0, 0)],
                        frames(t_in), frames(t_out), steps_per_second=1.6)
        if key != "guard":
            characters.key_cell(ob, frames(t_in) + 1, expression="angry")
    s.pin("gate", (0, 0, 2.4))
    s.pin("lantern", (0, -0.7, 4.4))
    s.pin("window", (cx, 2.9, 3.6))
    s.pin("door", (cx + 2.2, -3.0, 1.2))
    # the man in the cell, on the floor under the window
    prisoner = characters.actor("prisoner", "semmelweis", (cx - 1.0, 1.0, 0), PERSON_H, pose="hands-head",
                                expression="sad", tint=0.7)
    characters.blinks(prisoner, n, 11)
    s.view("street", (0, -2, 2.4), 18.0, 250, 2.0)
    s.view("gate", (0, 0, 3.2), 12.0, 265, 1.8)
    # eye level in front of the gate: a medium shot of someone standing there, the lit gate behind
    s.view("gate-near", (-0.1, -6.8, 1.4), 3.4, 265, 1.6)
    s.view("cell", (cx, 1.0, 1.6), 7.0, 265, 2.2)
    s.view("bars", (cx, 3.0, 3.5), 2.6, 255, 2.4)
    s.view("cell-close", (cx - 1.0, 1.0, 1.0), 3.6, 235, 1.5)

    def shut(t0, t1):
        f0, f1 = frames(t0), frames(t1)
        door.keyframe_insert("rotation_euler", frame=f0)
        door.rotation_euler = (0, 0, -math.radians(80))
        door.keyframe_insert("rotation_euler", frame=f0 - 1 if f0 > 1 else 1)
        door.rotation_euler = (0, 0, 0)
        door.keyframe_insert("rotation_euler", frame=f1)
        leaf.keyframe_insert("rotation_euler", frame=f0)
        leaf.rotation_euler = (0, 0, math.radians(70))
        leaf.keyframe_insert("rotation_euler", frame=1)
        leaf.rotation_euler = (0, 0, 0)
        leaf.keyframe_insert("rotation_euler", frame=f1)

    s.action("door-shut", shut, at=0.6, span=0.6)
    s.floor_grid = 0
    if p.get("night_key"):
        # a night that reads on a phone: a cold moon from high behind the camera's left as the fill, the
        # lantern warmer and stronger as the key on the gate and on whoever stands in front of it, and a
        # little more exposure; the cell keeps its own moonlight through the bars
        moon_d = bpy.data.lights.new("asy-moon", "SUN")
        moon_d.energy = 0.9
        moon_d.color = (0.62, 0.72, 1.0)
        moon_d.angle = math.radians(1.5)
        mo = kit._link(bpy.data.objects.new("asy-moon", moon_d))
        mo.rotation_euler = (math.radians(55), 0.0, math.radians(-35))
        for fc in (data.animation_data.action.fcurves if data.animation_data and data.animation_data.action else []):
            for kp in fc.keyframe_points:
                kp.co[1] *= 1.6
                kp.handle_left[1] *= 1.6
                kp.handle_right[1] *= 1.6
        kd = bpy.data.lights.new("asy-gate-key", "AREA")
        kd.energy = 150.0
        kd.color = (1.0, 0.7, 0.42)
        kd.size = 1.5
        ko = kit._link(bpy.data.objects.new("asy-gate-key", kd))
        ko.location = (-2.5, -4.5, 3.2)
        kit.common.aim(ko, (0.5, -1.5, 1.4))
        bpy.context.scene.view_settings.exposure = 0.55
    if use_assets:
        assets.scene_hdri("asylum", "night", n)          # none: the night stays dark
        assets.upgrade_materials()
    return s


# ---------------------------------------------------------------------------
# the ward
# ---------------------------------------------------------------------------

WARD_L, WARD_HW, WARD_H = 24.0, 4.0, 5.0         # length (x), half width (y), height
WARD_BEDS_X = [5.5 + 2.8 * i for i in range(7)]  # two rows of seven, heads to the long walls
WARD_WINDOWS_X = [6.9 + 2.8 * j for j in range(6)]
WARD_EMPTY = {(1, 3), (-1, 1), (1, 6)}           # (row, index) of the beds nobody lies in
WARD_BELL_BED = (1, 2)                           # the bed the priest comes to
WARD_TINT = {"day": 1.0, "dawn": 0.9, "dusk": 0.75, "night": 0.6}
# per time of day: window light (energy each, colour), ceiling fill energy, oil lamp energy
WARD_LIGHT = {"day": (450.0, (0.82, 0.90, 1.0), 220.0, 14.0), "dawn": (220.0, (1.0, 0.82, 0.70), 140.0, 40.0),
              "dusk": (100.0, (1.0, 0.60, 0.35), 60.0, 70.0), "night": (14.0, (0.50, 0.62, 1.0), 18.0, 90.0)}


def _speak(ob, f0, f1, rnd, pose="talk"):
    """The mouth moves from f0 to f1 (a few lip shapes), then back to rest and standing."""
    characters.key_cell(ob, f0, pose=pose, mouth="rest")
    fr = f0 + 2
    while fr < f1 - 3:
        characters.key_cell(ob, fr, mouth=rnd.choice(("half", "open", "closed", "half", "wide")))
        fr += rnd.randint(3, 6)
    characters.key_cell(ob, max(f0 + 1, f1 - 2), mouth="rest", pose="stand")


def ward(p, seconds):
    """1846, the First Obstetric Clinic: a long whitewashed ward (24 x 8 x 5 m, x along the ward, the
    door end at x = 0) with a beamed ceiling, tall windows on the +y wall, two rows of seven iron
    beds (a `patient` sprite on most), night tables, a crucifix on the far wall, a wash stand with a
    basin (water and a towel, nothing more: no chlorine yet), a linen cupboard, and by the door a
    table with the register and an oil lamp. A doctor and students examine at one bed, a midwife goes
    from bed to bed, a woman in labour is held up by a midwife. Action `bell`: the priest, with the
    viaticum, and the altar boy ringing a bell come in at the far door and walk the aisle to a bed.
    `time`: dawn | day | dusk | night (or `a>b`). `flicker`: the oil lamps waver (default) or burn steady;
    a held shot that must stay one shot (the wing) asks for steady, because a 20% step every 0.17 s
    reads as a cut to the scene detector and as a flash to the eye."""
    from scenes import Set
    s = Set(seconds)
    s.lighting = "world"
    s.lens = 30.0
    n = s.frames
    time = p.get("time", "day")
    t0_, t1_ = _times(time)
    # at 1080p the default shadow pool overflows in these rooms (2075/2048 pages): shadows drop out for
    # about a third of the frames. A 1024 pool renders the same frames with no overflow (measured).
    bpy.context.scene.eevee.shadow_pool_size = "1024"
    seed = int(p.get("seed", 5))
    use_assets = bool(p.get("assets", True))
    rnd = random.Random(seed)
    tint = WARD_TINT[t0_]
    L, HW, H = WARD_L, WARD_HW, WARD_H
    T = 0.4
    M = {
        "wall": kit.mat("ward-wall", (0.80, 0.78, 0.71), roughness=0.95),
        "dado": kit.mat("ward-dado", (0.40, 0.45, 0.40), roughness=0.9),
        "floor": kit.mat("ward-floor", (0.27, 0.18, 0.11), roughness=0.85),
        "seams": kit.mat("ward-seams", (0.07, 0.045, 0.03), roughness=0.9),
        "worn": kit.mat("ward-worn", (0.40, 0.29, 0.19), roughness=0.8),
        "stain": kit.mat("ward-stain", (0.14, 0.09, 0.06), roughness=0.7),
        "beam": kit.mat("ward-beam", (0.15, 0.09, 0.05), roughness=0.75),
        "wood": kit.mat("ward-wood", (0.20, 0.11, 0.055), roughness=0.7),
        "dark": kit.mat("ward-dark", (0.09, 0.05, 0.03), roughness=0.7),
        "iron": kit.mat("ward-iron", (0.05, 0.05, 0.055), roughness=0.5),
        "straw": kit.mat("ward-straw", (0.50, 0.40, 0.18), roughness=1.0),
        "linen": kit.mat("ward-linen", (0.74, 0.72, 0.66), roughness=0.95),
        "blanket": kit.mat("ward-blanket", (0.58, 0.57, 0.54), roughness=0.95),
        "paper": kit.mat("ward-paper", (0.80, 0.76, 0.66), roughness=0.9),
        "pale": kit.mat("ward-pale", (0.78, 0.72, 0.62), roughness=0.8),
        "corridor": kit.mat("ward-corridor", (0.30, 0.22, 0.14), roughness=0.9, emission=0.25,
                            emission_color=(0.5, 0.32, 0.16)),
    }
    tin = kit.mat("ward-tin", (0.50, 0.51, 0.53), metallic=0.5, roughness=0.4)
    brass = kit.mat("ward-brass", (0.55, 0.40, 0.12), metallic=0.5, roughness=0.4)
    P = {k: [] for k in M}

    def put(key, loc, size, rot=0.0):
        P[key].append(placed(loc, size, rot))

    kit.box("ward-ground", (12, 0, -0.1), (120, 80, 0.2), kit.mat("ward-outside", (0.10, 0.12, 0.08), roughness=1.0),
            bevel=0)
    # --- the shell: floor, ceiling, four walls with their openings ------------------------------------
    put("floor", (L / 2, 0, -0.05), (L + 0.8, 2 * HW + 0.8, 0.1))
    put("wall", (L / 2, 0, H + 0.1), (L + 0.8, 2 * HW + 0.8, 0.2))
    put("wall", (-T / 2, 0, H / 2), (T, 2 * HW + 0.8, H))
    end = subtract((L, -HW - T, 0), (L + T, HW + T, H), (L - 1, -0.7, -1), (L + 1, 0.7, 2.4))
    south = subtract((-T, -HW - T, 0), (L + T, -HW, H), (1.2, -HW - 1, -1), (2.8, -HW + 1, 2.3))
    north = [((-T, HW, 0), (L + T, HW + T, H))]
    for wx in WARD_WINDOWS_X:
        cut = ((wx - 0.55, HW - 1, 1.3), (wx + 0.55, HW + 1, 4.2))
        north = [q for lo, hi in north for q in subtract(lo, hi, *cut)]
    for lo, hi in end + south + north:
        put("wall", tuple((a + b) / 2 for a, b in zip(lo, hi)), tuple(b - a for a, b in zip(lo, hi)))
    # window frames: a mullion and a transom in each opening, and a stone sill
    for wx in WARD_WINDOWS_X:
        put("wood", (wx, HW + 0.12, 2.75), (0.05, 0.06, 2.9))
        put("wood", (wx, HW + 0.12, 2.9), (1.1, 0.06, 0.05))
        for dx in (-0.55, 0.55):
            put("wood", (wx + dx, HW + 0.12, 2.75), (0.07, 0.1, 2.9))
        put("pale", (wx, HW - 0.02, 1.27), (1.3, 0.3, 0.06))
    # a dado along the long walls, a worn plank floor, beams across the ceiling
    for sy in (-1, 1):
        put("dado", (L / 2, sy * (HW - 0.015), 0.45), (L, 0.03, 0.9))
    for k in range(34):
        put("seams", (L / 2, -HW + 0.12 + 0.24 * k, 0.002), (L, 0.012, 0.004))
    put("worn", (L / 2, 0.0, 0.004), (L - 3.0, 1.7, 0.004))                # the path worn down the aisle
    put("worn", (2.4, -1.4, 0.005), (3.4, 3.0, 0.004))                      # and in front of the door
    for k in range(6):
        put("stain", (rnd.uniform(2, 22), rnd.uniform(-1.6, 1.6), 0.006),
            (rnd.uniform(0.3, 0.7), rnd.uniform(0.3, 0.6), 0.004), rnd.random() * 3)
    for x in range(3, 24, 3):
        put("beam", (x, 0, H - 0.2), (0.32, 2 * HW, 0.36))
    put("beam", (L / 2, 0, H - 0.1), (L, 0.28, 0.2))
    # --- beds, night tables, their things -----------------------------------------------------------------
    cups, jugs, beds = [], [], []
    for row in (1, -1):
        for i, x in enumerate(WARD_BEDS_X):
            h = row
            yc = h * 2.85
            for dx in (-0.42, 0.42):
                put("iron", (x + dx, h * 3.9, 0.55), (0.04, 0.04, 1.1))
                put("iron", (x + dx, h * 1.9, 0.4), (0.04, 0.04, 0.8))
                put("iron", (x + dx, yc, 0.5), (0.03, 1.95, 0.05))
            for z in (1.05, 0.75):
                put("iron", (x, h * 3.9, z), (0.88, 0.03, 0.04))
            put("iron", (x, h * 1.9, 0.75), (0.88, 0.03, 0.04))
            put("straw", (x, yc, 0.52), (0.8, 1.9, 0.12))
            occupied = (row, i) not in WARD_EMPTY
            if not occupied:                                          # stripped: a pillow and folded linen
                put("linen", (x, h * 3.55, 0.62), (0.5, 0.3, 0.1))
                put("blanket", (x, h * 2.2, 0.64), (0.7, 0.45, 0.14))
            if not (use_assets and assets.prop("painted_wooden_nightstand", (x + 0.72, h * 3.7, 0.0),
                                               math.pi if h < 0 else 0.0, height=0.7,
                                               name=f"ward-nightstand-{row:+d}-{i}")):
                put("wood", (x + 0.72, h * 3.7, 0.35), (0.4, 0.4, 0.7))
            if (i + (row > 0)) % 4 != 3:
                cups.append(((x + 0.65, h * 3.7, 0.74), 0.035, 0.09))
                if i % 2 == 0:
                    jugs.append(((x + 0.8, h * 3.75, 0.8), 0.06, 0.2))
            beds.append((row, i, x, yc, occupied))
    # --- crucifix, cupboard, wash stand, table with the register ----------------------------------------------
    put("dark", (L - 0.07, 0, 3.7), (0.05, 0.14, 1.1))
    put("dark", (L - 0.07, 0, 4.05), (0.05, 0.7, 0.14))
    put("pale", (L - 0.1, 0, 3.8), (0.04, 0.12, 0.5))
    put("wood", (L - 0.4, -2.8, 1.05), (0.5, 1.3, 2.1))                    # the linen cupboard
    put("dark", (L - 0.66, -2.8, 1.05), (0.02, 0.03, 2.0))
    for k in range(4):
        put("linen", (L - 0.4, -2.8 + 0.1 * (k % 2), 2.2 + 0.09 * k), (0.4, 0.8, 0.08))
    put("wood", (0.45, -3.0, 0.84), (0.55, 0.9, 0.05))                     # the wash stand
    for dy in (-0.4, 0.4):
        put("wood", (0.45, -3.0 + dy, 0.42), (0.5, 0.05, 0.84))
    put("wood", (0.45, -3.0, 0.3), (0.5, 0.8, 0.04))
    put("linen", (0.2, -2.55, 0.62), (0.04, 0.25, 0.45))                   # a towel over the side
    put("wood", (3.7, -HW + 0.4, 0.78), (1.0, 0.55, 0.05))                 # the table by the door
    for dx in (-0.45, 0.45):
        for dy in (-0.22, 0.22):
            put("wood", (3.7 + dx, -HW + 0.4 + dy, 0.38), (0.05, 0.05, 0.76))
    put("dark", (3.55, -HW + 0.4, 0.83), (0.42, 0.3, 0.04))                # the register
    put("paper", (3.55, -HW + 0.4, 0.865), (0.4, 0.28, 0.03))
    put("wood", (3.7, -HW + 1.05, 0.45), (0.42, 0.42, 0.05))               # the chair
    put("wood", (3.7, -HW + 1.26, 0.85), (0.42, 0.05, 0.8))
    for dx in (-0.18, 0.18):
        put("wood", (3.7 + dx, -HW + 1.05, 0.22), (0.04, 0.04, 0.44))
    # the corridor behind each door, so an opening is a passage and not the sky; `through` leaves the
    # far door open onto the real corridor the `wing` scene builds behind it
    through = bool(p.get("through", False))
    flicker = bool(p.get("flicker", True))
    put("corridor", (2.0, -HW - 1.3, 1.2), (2.4, 0.1, 2.4))
    if not through:
        put("corridor", (L + 1.3, 0.0, 1.2), (0.1, 2.4, 2.4))
    put("dark", (2.55, -HW + 0.54, 1.15), (1.2, 0.06, 2.3), math.radians(115))   # the corridor door, ajar
    if not through:
        put("dark", (L - 0.69, -0.58, 1.15), (1.4, 0.06, 2.3), math.radians(170))    # the far door, ajar
    else:
        put("dark", (L - 0.69, -1.25, 1.15), (1.4, 0.06, 2.3), math.radians(100))    # the far door, wide open
    for key, mats in P.items():
        if mats:
            kit.boxes(f"ward-{key}", mats, M[key])
    kit.cylinders("ward-cups", cups, tin)
    kit.cylinders("ward-jugs", jugs, kit.mat("ward-jug", (0.55, 0.52, 0.46), roughness=0.5))
    kit.cylinders("ward-basin", [((0.45, -3.0, 0.92), 0.22, 0.1)], tin)
    kit.cylinders("ward-ewer", [((0.45, -3.25, 0.98), 0.07, 0.24)], kit.mat("ward-ewer", (0.62, 0.60, 0.55), roughness=0.4))
    kit.cylinders("ward-ink", [((3.95, -HW + 0.4, 0.86), 0.03, 0.06)], kit.mat("ward-inkpot", (0.02, 0.02, 0.03), roughness=0.2))
    # --- practical lights: oil lamps (the register's always, more as the day goes) --------------------------
    lamp_t = "night" if "night" in (t0_, t1_) else t1_
    lamp_at = [(3.9, -HW + 0.4, 0.89)]
    lamp_at += {"night": [(WARD_BEDS_X[1] + 0.8, 3.7, 0.9), (WARD_BEDS_X[3] + 0.8, -3.7, 0.9),
                          (WARD_BEDS_X[5] + 0.8, 3.7, 0.9), (WARD_BEDS_X[6] + 0.8, -3.7, 0.9)],
                "dusk": [(WARD_BEDS_X[2] + 0.8, 3.7, 0.9), (WARD_BEDS_X[5] + 0.8, -3.7, 0.9)],
                "dawn": [(WARD_BEDS_X[4] + 0.8, 3.7, 0.9)]}.get(lamp_t, [])
    flame = look.neon("ward-flame", (1.0, 0.66, 0.28), 16.0, base=(0.5, 0.35, 0.15))
    for k, (x, y, z) in enumerate(lamp_at):
        kit.cylinders(f"ward-lampbase{k}", [((x, y, z - 0.05), 0.05, 0.1)], brass)
        kit.ico(f"ward-lamp{k}", (x, y, z + 0.04), 0.035, flame, subdivisions=1)
        data = bpy.data.lights.new(f"ward-lamp{k}", "POINT")
        data.color = (1.0, 0.62, 0.30)
        data.shadow_soft_size = 0.12
        data.use_shadow = k == 0
        lo = bpy.data.objects.new(data.name, data)
        kit._link(lo)
        lo.location = (x, y * 0.97, z + 0.12)
        base_e = WARD_LIGHT[t0_][3] if k == 0 else WARD_LIGHT[lamp_t][3]
        for fr in range(1, n + 1, 5):                                  # a flame never holds still
            wobble = 0.85 + 0.3 * rnd.random()                         # drawn either way: same scene
            if flicker:
                data.energy = base_e * wobble
                data.keyframe_insert("energy", frame=fr)
        if not flicker:
            data.energy = base_e
    # --- daylight: sun through the windows, an area light in each, soft fill under the beams -----------------
    s.sky = sky_world(time, seconds)
    sky_lights(time, seconds, (L / 2, 0, 0), 12.0, sun_azimuth=110.0)
    win_lights, fills = [], []
    for j, wx in enumerate(WARD_WINDOWS_X):
        wl = kit.common.add_area_light(f"ward-window{j}", (wx, HW + 0.7, 3.0), WARD_LIGHT[t0_][0],
                                       color=WARD_LIGHT[t0_][1], size=1.4)
        kit.common.aim(wl, (wx - 0.5, 0.0, 0.7))
        win_lights.append(wl)
    for k, x in enumerate((3.5, 9.5, 15.5, 21.0)):
        fl = kit.common.add_area_light(f"ward-fill{k}", (x, 0.0, H - 0.5), WARD_LIGHT[t0_][2],
                                       color=(1.0, 0.92, 0.82), size=3.0)
        kit.common.aim(fl, (x, 0.0, 0.0))
        fills.append(fl)
    for fr, tod in ((1, t0_), (n, t1_)):
        for ob in win_lights:
            ob.data.energy = WARD_LIGHT[tod][0]
            ob.data.color = WARD_LIGHT[tod][1]
            ob.data.keyframe_insert("energy", frame=fr)
            ob.data.keyframe_insert("color", frame=fr)
        for ob in fills:
            ob.data.energy = WARD_LIGHT[tod][2]
            ob.data.keyframe_insert("energy", frame=fr)
    # --- the patients ----------------------------------------------------------------------------------
    exprs = ("neutral", "worried", "sad", "neutral", "worried", "smile", "neutral")
    patients = {}
    # how the mothers lie: `lie` "back" (the First Clinic's way) or "side" (the midwives' way, every
    # bed), and `side_bed` [row, index] for one bed already on her side when the rest are not
    import people as _people
    side_pose = "lie-side" if "lie-side" in _people.BED_POSES else "lie-turn"
    lie_all = p.get("lie", "back")
    side_one = tuple(p.get("side_bed") or ())
    for row, i, x, yc, occupied in beds:
        if not occupied:
            continue
        base = rnd.choice(exprs)
        start_pose = side_pose if lie_all == "side" or (row, i) == side_one else "lie"
        ob = characters.actor(f"patient-{row:+d}-{i}", "patient", (x, yc, 0.36), 1.06, size="bed", pose=start_pose,
                              expression=base, tint=tint, shadow=False)
        if row < 0:
            ob.scale[0] = -ob.scale[0]                              # her head to the wall on this side too
        characters.blinks(ob, n, seed + 400 + 7 * i + (row > 0))
        fr = frames(rnd.uniform(2.0, 6.0))
        while fr < n - FPS:                                         # restless now and then
            characters.key_cell(ob, fr, expression=rnd.choice(exprs))
            fr += frames(rnd.uniform(4.0, 9.0))
        patients[(row, i)] = (ob, x, base)
        ob["start_pose"] = start_pose
    # --- people with tasks -------------------------------------------------------------------------------------
    ex_x, ex_y = WARD_BEDS_X[0], -2.85                                # the examined bed
    groups("ward-exam", [{"who": ["doctor", "student", "student", "student"],
                          "at": [(ex_x + 1.05, ex_y + 0.25, 0), (ex_x + 1.4, ex_y - 0.45, 0),
                                 (ex_x - 0.95, ex_y + 0.3, 0), (ex_x - 1.05, ex_y - 0.5, 0)],
                          "turns": plan.chatter(seconds, seed=seed + 11, people=4)}], n, seed + 12, tint)
    # the midwife between the beds: walks, stops, talks to a patient, walks on
    # she starts 7 m into the room: from (3.0, 0.8) she walked straight across the lens of every
    # door-end view (ward-wide and ward-aisle stand at x 1.2-1.5) and filled the frame for 2 s
    mw = characters.actor("ward-midwife", "midwife", (9.0, 1.2, 0), PERSON_H, tint=tint)
    for a, b, u0, u1 in (((9.0, 1.2, 0), (7.0, -1.25, 0), 0.04, 0.22), ((7.0, -1.25, 0), (17.5, -1.25, 0), 0.40, 0.62),
                         ((17.5, -1.25, 0), (19.8, 1.3, 0), 0.80, 0.90)):
        characters.walk(mw, [a, b], frames(u0 * seconds), max(frames(u0 * seconds) + 2, frames(u1 * seconds)))
    mrnd = random.Random(seed + 21)
    for u0, u1 in ((0.22, 0.38), (0.62, 0.78), (0.90, 0.99)):
        _speak(mw, frames(u0 * seconds), frames(u1 * seconds), mrnd)
    characters.blinks(mw, n, seed + 22)
    # a woman in labour, held up by a second midwife (at the aisle's edge, off the priest's line)
    mother = characters.actor("ward-mother", "mother", (13.2, -1.0, 0), PERSON_H, pose="plead",
                              expression="worried", tint=tint)
    helper = characters.actor("ward-helper", "midwife", (13.95, -0.85, 0), PERSON_H, tint=tint)
    characters.blinks(mother, n, seed + 31)
    characters.blinks(helper, n, seed + 32)
    t = 1.0
    while t < seconds - 1:
        characters.key_cell(mother, frames(t), pose=mrnd.choice(("plead", "plead", "stand")),
                            expression=mrnd.choice(("worried", "shocked", "sad", "worried")))
        t += mrnd.uniform(2.0, 4.0)
    t = 0.8
    while t < seconds - 2:
        _speak(helper, frames(t), frames(t + mrnd.uniform(1.2, 2.4)), mrnd)
        t += mrnd.uniform(3.5, 6.0)
    # the priest with the viaticum and the altar boy with his bell (their walk is keyed in `bell`)
    priest = characters.actor("ward-priest", "priest", (23.0, 0.0, 0), PERSON_H, tint=tint)
    boy = characters.actor("ward-acolyte", "acolyte", (21.6, 0.2, 0), PERSON_H, tint=tint)
    characters.blinks(priest, n, seed + 41)
    characters.blinks(boy, n, seed + 42)
    # --- anchors and views --------------------------------------------------------------------------------------
    s.pin("door", (1.8, -3.0, 1.1))
    s.pin("ledger", (3.55, -HW + 0.4, 0.95))
    s.pin("bed", (ex_x, ex_y, 0.8))
    s.pin("basin", (0.45, -3.0, 0.95))
    s.pin("bell", (21.6, 0.2, 1.0), follow=boy)
    # camera = target + radius * (cos az, sin az); every position stays inside the room
    s.view("ward-wide", (13.0, 0.0, 1.5), 11.8, 180, 1.6)
    s.view("ward-aisle", (14.0, -0.5, 1.0), 12.5, 185, 0.95)
    s.view("ward-bed", (ex_x, ex_y, 0.9), 3.7, 133, 1.5)
    s.view("ward-door", (2.9, -3.4, 1.2), 4.8, 80, 1.5)
    s.view("ward-priest", (13.5, 0.5, 1.2), 6.5, 180, 1.4)
    # v6: the Second Clinic's bed matched to ward-bed (same lens, height and distance, mirrored), a
    # close on whoever stands at the door, the hands against the window light, the next door
    s.view("second-bed", (WARD_BEDS_X[1], 2.85, 0.9), 3.7, -133, 1.5)
    s.view("semmelweis-close", (2.9, -3.0, 1.55), 2.2, 75, 1.6)
    s.view("hands-window", (WARD_WINDOWS_X[2], HW - 0.9, 1.45), 1.6, -100, 1.45)
    s.view("semmelweis-hands", (4.2, -2.2, 1.35), 1.9, 70, 1.55)
    s.view("hands-door", (2.0, -HW + 0.6, 1.2), 2.4, 95, 1.35)
    s.view("sickbed", (WARD_BEDS_X[3], 2.85, 0.75), 2.6, -120, 1.45)
    s.pin("window", (WARD_WINDOWS_X[2], HW - 0.2, 2.6))
    s.floor_grid = 0

    def act_bell(t0, t1):
        f0, f1 = frames(t0), max(frames(t0) + 4, frames(t1))
        for ob in (priest, boy):
            for part in (ob, bpy.data.objects.get(ob.get("shadow", ""))):
                if part is not None:
                    switch(part, f0)
        bx, bh = WARD_BEDS_X[WARD_BELL_BED[1]], 1.4
        if p.get("bell_route", "aisle") == "side":
            # the long way round (c18 says only "a less obvious route"): in by the near door and up the
            # wall side of the aisle, no bell rung; nobody turns
            characters.walk(priest, [(1.8, -3.2, 0), (2.4, -0.6, 0), (bx - 0.6, 0.0, 0), (bx, bh, 0)], f0, f1,
                            steps_per_second=1.2)
            characters.walk(boy, [(1.2, -3.4, 0), (1.9, -0.9, 0), (bx - 1.4, -0.2, 0)], f0, f1, steps_per_second=1.2)
            return
        characters.walk(priest, [(23.0, 0.0, 0), (22.0, 0.6, 0), (bx + 0.7, 0.6, 0), (bx, bh, 0)], f0, f1,
                        steps_per_second=1.4)
        characters.walk(boy, [(21.6, 0.2, 0), (20.4, 0.55, 0), (bx - 0.9, 0.6, 0)], f0, f1, steps_per_second=1.4)
        # the boy's own pose keys: ring for 0.4 s, walk for 0.4 s, over and over
        ev = sorted((e for e in characters.EVENTS.get(boy.name, []) if not (f0 <= e[0] <= f1 and "pose" in e[2])),
                    key=lambda e: (e[0], e[1]))
        characters.EVENTS[boy.name] = [(f, k, ch) for k, (f, _, ch) in enumerate(ev)]
        slots = ["ring", "ring", "walk1", "walk2", "ring", "ring", "walk3", "walk4"]
        step, i, fr = max(2, round(0.2 * FPS)), 0, f0
        while fr < f1:
            characters.key_cell(boy, fr, pose=slots[i % len(slots)])
            fr += step
            i += 1
        characters.key_cell(boy, f1, pose="stand")
        # the patients he passes turn their heads and look worried; the one he comes to is the dying
        for (row, idx), (ob, x, base) in patients.items():
            if x < bx - 0.6 or x > 23.0:
                continue
            tp = t0 + (23.0 - x) / (23.0 - bx) * (t1 - t0)
            characters.key_cell(ob, frames(tp - 1.5), pose="lie-turn", expression="worried")
            if (row, idx) == WARD_BELL_BED:
                characters.key_cell(ob, frames(t1 - 0.5), expression="sad")
            else:
                characters.key_cell(ob, frames(tp + 2.5), pose="lie", expression=base)

    if p.get("bell", True):                 # a beat without the priest leaves him out of the ward
        s.action("bell", act_bell, at=0.1, span=14.0)
    else:
        for ob in (priest, boy):
            for part in (ob, bpy.data.objects.get(ob.get("shadow", ""))):
                if part is not None:
                    part.hide_render = True
                    part.hide_viewport = True

    def act_turn(t0, t1):
        """The First Clinic's mothers turned onto their side, bed by bed from the door end (c24)."""
        order = sorted(patients.items(), key=lambda kv: kv[1][1])
        for k, ((row, idx), (ob, x, base)) in enumerate(order):
            characters.key_cell(ob, frames(t0 + (t1 - t0) * k / max(1, len(order))), pose=side_pose)

    if p.get("turn"):                       # registered only when asked: every action runs once
        s.action("turn", act_turn, at=0.5, span=2.0)
    if p.get("door_swing"):
        # v6: the corridor door (the ajar `dark` plane above) as a real leaf on a hinge at its near jamb.
        # The unwashed hands push it open and it swings shut behind them (visual-pass s50).
        hinge = kit._link(bpy.data.objects.new("ward-door-hinge", None))
        hinge.location = (1.95, -HW + 0.05, 0.0)
        wood = kit.mat("ward-door-wood", (0.13, 0.07, 0.035), roughness=0.6)
        leaf = kit.box("ward-door-leaf", (0.6, 0.0, 1.15), (1.2, 0.06, 2.3), wood, bevel=0)
        leaf.parent = hinge

        def swing(t0, t1):
            f0, f1 = frames(t0), frames(t1)
            mid = frames(t0 + 0.5 * (t1 - t0))
            hinge.rotation_euler = (0, 0, 0)
            hinge.keyframe_insert("rotation_euler", frame=1)
            hinge.rotation_euler = (0, 0, math.radians(80))          # pushed open into the room
            hinge.keyframe_insert("rotation_euler", frame=mid)
            hinge.rotation_euler = (0, 0, 0)                          # swings shut behind them
            hinge.keyframe_insert("rotation_euler", frame=f1)

        s.action("door-swing", swing, at=0.45, span=1.6)
    if use_assets:
        assets.scene_hdri("ward", time, n)
        assets.upgrade_materials()
    return s


SCENES = {"vienna": vienna, "asylum": asylum, "ward": ward}
