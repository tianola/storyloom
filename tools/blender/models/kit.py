"""Shared kit for the reusable model library: materials, instanced meshes, staging, labels.

Everything a beat needs that is not a specific object lives here, so a beat file reads as
"which model, which move" and never as a pile of primitives. The palette, canvas and key
light come from workflow/style.json; nothing here invents its own.
"""
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for p in (str(HERE.parent / "techniques"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import common  # noqa: E402
from lighting import key_location  # noqa: E402
from workflow.config import style_contract  # noqa: E402

STYLE = style_contract(ROOT)
PALETTE = STYLE["palette"]
BASE = tuple(PALETTE["base"]["rgb_linear"])
GROUND = tuple(PALETTE["ground"]["rgb_linear"])
ACCENT = tuple(PALETTE["accent"]["rgb_linear"])
ROUGH_MIN = STYLE["materials"]["roughness_min"]
METAL_MAX = STYLE["materials"]["metallic_max"]
FPS = STYLE["canvas"]["fps"]
FONT_PATH = ROOT / "tools" / "fonts" / "Inter-SemiBold.ttf"


# ---------------------------------------------------------------------------
# Materials: one cached datablock per name, all inside the matte contract
# ---------------------------------------------------------------------------

_MATS = {}


def mat(name, color, metallic=0.0, roughness=0.6, emission=0.0, emission_color=None):
    """Cached matte material. Roughness and metallic are clamped to the style contract."""
    if name in _MATS and _MATS[name].name in bpy.data.materials:
        return _MATS[name]
    m = common.material_principled(
        name, color,
        metallic=min(metallic, METAL_MAX),
        roughness=max(roughness, ROUGH_MIN),
        emission_color=(*(emission_color or color)[:3], 1.0),
        emission_strength=emission)
    _MATS[name] = m
    return m


def reset_materials():
    _MATS.clear()


# A look may retune these two before a beat builds its models.
TONE = {"base": BASE, "accent_glow": 0.0}


def base():      return mat("kit-base", TONE["base"], roughness=0.55)
def ground():    return mat("kit-ground", GROUND, roughness=0.9)
def floor_mat(): return mat("kit-floor", tuple(c * 0.42 for c in GROUND), roughness=0.9)
def accent():    return mat("kit-accent", ACCENT, metallic=METAL_MAX, roughness=0.45, emission=TONE["accent_glow"])
def epoxy():     return mat("kit-epoxy", (0.022, 0.024, 0.028), roughness=0.62)
def pcb():       return mat("kit-pcb", (0.035, 0.085, 0.075), roughness=0.6)
def steel():     return mat("kit-steel", (0.50, 0.52, 0.55), metallic=0.6, roughness=0.45)
def silicon():   return mat("kit-silicon", (0.20, 0.23, 0.30), metallic=0.55, roughness=0.42)
def circuit():   return mat("kit-circuit", (0.42, 0.46, 0.55), metallic=0.5, roughness=0.45)
def slate():     return mat("kit-slate", (0.09, 0.10, 0.115), roughness=0.7)
def mid():       return mat("kit-mid", (0.33, 0.34, 0.35), roughness=0.65)


def glow(name, strength=4.0, color=ACCENT):
    """An emissive accent whose strength can be keyed with `pulse`."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Roughness"].default_value = 0.5
    b.inputs["Emission Color"].default_value = (*color, 1.0)
    b.inputs["Emission Strength"].default_value = strength
    return m


def pulse(material, keys):
    """Key emission strength: keys is [(frame, strength), ...]."""
    socket = material.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
    for frame, value in keys:
        socket.default_value = value
        socket.keyframe_insert("default_value", frame=frame)


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

def _link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def box(name, loc, size, material, bevel=0.02):
    ob = common.add_box(name, loc, size, material)
    if bevel:
        common.harden_edges(ob, width=min(bevel, 0.45 * min(size)), segments=2)
    return ob


def cyl(name, loc, radius, depth, material, rot=(0, 0, 0), verts=48, radius2=None):
    bpy.ops.mesh.primitive_cone_add(
        vertices=verts, radius1=radius, radius2=radius if radius2 is None else radius2,
        depth=depth, location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    ob.data.materials.append(material)
    soften(ob)
    return ob


def ico(name, loc, radius, material, subdivisions=2, smooth=False):
    """Icosphere. Left faceted by default: the low-poly facets are the house look."""
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdivisions, radius=radius, location=loc)
    ob = bpy.context.active_object
    ob.name = name
    ob.data.materials.append(material)
    if smooth:
        soften(ob)
    return ob


def soften(ob, angle=40.0):
    me = ob.data
    for poly in me.polygons:
        poly.use_smooth = True
    me.set_sharp_from_angle(angle=math.radians(angle))
    return ob


def placed(loc, size=(1, 1, 1), rot_z=0.0):
    """Matrix for one instance in `boxes` / `cylinders` / `balls`."""
    return (Matrix.Translation(loc) @ Matrix.Rotation(rot_z, 4, "Z")
            @ Matrix.Diagonal((*size, 1.0)))


def _mesh_object(name, bm, material):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = _link(bpy.data.objects.new(name, me))
    ob.data.materials.append(material)
    return ob


def boxes(name, matrices, material):
    """Many boxes as ONE object: pins, fins, die cells, windows. Keeps the scene light."""
    bm = bmesh.new()
    for m in matrices:
        bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    return _mesh_object(name, bm, material)


def cylinders(name, items, material, segments=16):
    """items: [(location, radius, depth), ...] upright cylinders as one object."""
    bm = bmesh.new()
    for loc, radius, depth in items:
        bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=radius,
                              radius2=radius, depth=depth, matrix=Matrix.Translation(loc))
    return soften(_mesh_object(name, bm, material))


def balls(name, locations, radius, material):
    bm = bmesh.new()
    for loc in locations:
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=radius,
                                   matrix=Matrix.Translation(loc))
    return _mesh_object(name, bm, material)


def rod(name, a, b, radius, material, verts=8):
    """A straight bar between two points: wires, leader lines, connections."""
    a, b = Vector(a), Vector(b)
    d = b - a
    ob = cyl(name, (a + b) / 2, radius, d.length, material, verts=verts)
    ob.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    return ob


def rods(name, pairs, radius, material):
    """Many straight bars as one object."""
    bm = bmesh.new()
    for a, b in pairs:
        a, b = Vector(a), Vector(b)
        d = b - a
        m = (Matrix.Translation((a + b) / 2) @ d.to_track_quat("Z", "Y").to_matrix().to_4x4()
             @ Matrix.Diagonal((radius * 2, radius * 2, d.length, 1.0)))
        bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    return _mesh_object(name, bm, material)


def group(name, children=()):
    """An empty at the origin that carries a sub-assembly, so one keyframe moves it all."""
    e = _link(bpy.data.objects.new(name, None))
    e.empty_display_size = 0.2
    for c in children:
        if c is not None:
            c.parent = e
    return e


def flat_text(name, text, loc, size, material, rot=(0, 0, 0), align="CENTER", extrude=0.004):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = text
    cu.font = bpy.data.fonts.load(str(FONT_PATH), check_existing=True)
    cu.size = size
    cu.align_x = align
    cu.align_y = "CENTER"
    cu.extrude = extrude
    cu.materials.append(material)
    ob = _link(bpy.data.objects.new(name, cu))
    ob.location = loc
    ob.rotation_euler = rot
    return ob


# ---------------------------------------------------------------------------
# Animation
# ---------------------------------------------------------------------------

def move(ob, f0, f1, delta):
    """Ease `ob` by `delta` between two frames; it holds before and after."""
    ob.keyframe_insert("location", frame=f0)
    ob.location = Vector(ob.location) + Vector(delta)
    ob.keyframe_insert("location", frame=f1)


def appear(ob, f0, f1=None):
    """Scale in from nothing: the reveal used for labels and late-arriving parts."""
    f1 = f1 or f0 + 10
    full = tuple(ob.scale)
    ob.scale = (0.0001, 0.0001, 0.0001)
    ob.keyframe_insert("scale", frame=max(1, f0 - 1))
    ob.keyframe_insert("scale", frame=f0)
    ob.scale = full
    ob.keyframe_insert("scale", frame=f1)


def spin(ob, frames, turns, axis=2):
    ob.rotation_euler[axis] = 0.0
    ob.keyframe_insert("rotation_euler", frame=1)
    ob.rotation_euler[axis] = turns * 2 * math.pi
    ob.keyframe_insert("rotation_euler", frame=frames)
    _linear(ob)


def _linear(ob):
    if ob.animation_data and ob.animation_data.action:
        for fc in ob.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"


# ---------------------------------------------------------------------------
# Staging: floor, camera move, key light
# ---------------------------------------------------------------------------

LAST = None


class Stage:
    def __init__(self, cam, target, frames):
        self.cam, self.target, self.frames = cam, target, frames
        self.problems = []
        self.rig = None
        self.mid_cam = None
        self.floor_z = 0.0


def _world(ambient):
    """Dark backdrop for the lens, soft sky for the lighting.

    A world dim enough to be the backdrop leaves every shadow pure black, and a lifted
    part then hides whatever it was lifted off. Light Path splits the two jobs.
    """
    world = bpy.data.worlds.new("Studio World")
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    seen = nt.nodes.new("ShaderNodeBackground")
    seen.inputs["Color"].default_value = (0.012, 0.016, 0.026, 1.0)
    sky = nt.nodes.new("ShaderNodeBackground")
    sky.inputs["Color"].default_value = (0.62, 0.68, 0.80, 1.0)
    sky.inputs["Strength"].default_value = ambient
    path = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(path.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(sky.outputs["Background"], mix.inputs[1])
    nt.links.new(seen.outputs["Background"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    bpy.context.scene.world = world


def _orbit_point(target, radius, azimuth_deg, height):
    a = math.radians(azimuth_deg)
    return Vector((target[0] + radius * math.cos(a), target[1] + radius * math.sin(a), height))


def stage(seconds, *, target=(0, 0, 0.5), radius=(11.0, 9.0), azimuth=(-70.0, -40.0),
          height=(6.0, 5.0), lens=50.0, floor=True, floor_z=0.0, floor_grid=1.0,
          key_side=1.0, key_energy=3.6, fill=60.0, world_strength=0.55, res=None):
    """Build the shared set for one beat and return the camera.

    The camera travels an arc around `target` (radius, azimuth and height each go from
    their first value to their second) while a Track-To keeps the subject framed, so the
    move is one slow drift for the length of the sentence. The key sun is derived from
    the camera at the shot's mid frame, never typed in.
    """
    frames = int(round(seconds * FPS))
    common.wipe()
    reset_materials()
    TONE.update(base=BASE, accent_glow=0.0)
    canvas = STYLE["canvas"]
    w, h = res or (canvas["width"], canvas["height"])
    common.setup_scene(FPS, 1, frames, w, h)
    # Nothing in the library is transparent, and ray tracing is what setup_scene turns on
    # for glass. Measured on riva-chip at 1080p/32 samples: 1.32 s a frame with it,
    # 0.75 s without, for a picture that does not change.
    bpy.context.scene.eevee.use_raytracing = False
    _world(world_strength)

    aim = _link(bpy.data.objects.new("cam-target", None))
    aim.location = target
    start = _orbit_point(target, radius[0], azimuth[0], height[0])
    cam = common.add_camera("camera", start, target, lens=lens)
    track = cam.constraints.new("TRACK_TO")
    track.target = aim
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"
    steps = max(2, frames // 15)
    for i in range(steps + 1):
        t = i / steps
        cam.location = _orbit_point(
            target,
            radius[0] + (radius[1] - radius[0]) * t,
            azimuth[0] + (azimuth[1] - azimuth[0]) * t,
            height[0] + (height[1] - height[0]) * t)
        cam.keyframe_insert("location", frame=1 + round(t * (frames - 1)))
    _linear(cam)

    mid_cam = _orbit_point(target, sum(radius) / 2, sum(azimuth) / 2, sum(height) / 2)
    lighting = STYLE["lighting"]
    key = key_location(mid_cam, target, elevation=lighting["key_elevation_deg"] + 18.0,
                       side=key_side, yaw=lighting["key_yaw_deg"])
    common.add_sun_light("key", key, key_energy, angle=math.radians(3.0))
    if fill:
        # A wide, weak overhead fill: it lifts the shadow side enough to read form and
        # is far too soft to compete with the key for the shadow direction.
        lamp = common.add_area_light("fill", (target[0], target[1], target[2] + 9.0), fill,
                                     size=14.0)
        lamp.rotation_euler = (0, 0, 0)

    if floor:
        box("floor", (target[0], target[1], floor_z - 0.05), (90, 90, 0.1), floor_mat(), bevel=0)
        if floor_grid:
            # A dotted floor grid: it is what turns a camera drift into visible parallax
            # instead of a subject sliding over a blank plane.
            n = 22
            dots = [((target[0] + (i - n / 2) * floor_grid, target[1] + (j - n / 2) * floor_grid,
                      floor_z + 0.004), 0.035, 0.008)
                    for i in range(n + 1) for j in range(n + 1)]
            cylinders("floor-grid", dots, mid(), segments=8)
    global LAST
    LAST = Stage(cam, target, frames)
    LAST.mid_cam = mid_cam
    LAST.floor_z = floor_z
    return LAST


def label(st, text, anchor, screen, *, size=0.045, appear_at=1, follow=None, color=None):
    """A callout that stays put on screen while its leader tracks the 3D point it names.

    `screen` is (u, v) in frame fractions from the bottom-left; `size` is the cap height
    as a fraction of frame height. The text rides on the camera, so a camera drift can
    never slide it out of frame; only the leader line moves, which is what tells the
    viewer the label belongs to the object and not to the picture. `follow` parents the
    anchor to a part, so the leader stays on a piece that is being lifted away.
    """
    u, v = screen
    half_u = len(text) * size * 0.29 * 9 / 16
    if not (0.02 < u - half_u and u + half_u < 0.98 and 0.05 < v < 0.95):
        st.problems.append(f"label '{text}' leaves the frame: u={u - half_u:.2f}..{u + half_u:.2f} v={v:.2f}")
    material = mat("kit-label", color or BASE, roughness=0.6, emission=1.6)
    cam = st.cam
    scene = bpy.context.scene
    a = Vector(anchor)
    per_depth = Vector(((2 * u - 1) * 18.0 / cam.data.lens, (2 * v - 1) * 18.0 / cam.data.lens * 9 / 16, -1.0))

    # The text sits at roughly the subject's distance, pulled in wherever its line of
    # sight would otherwise run into the floor: a label low in the frame at the
    # subject's depth is under the ground plane and simply does not render.
    depth = (a - st.mid_cam).length * 0.82
    for frame in (1, st.frames):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        ray = cam.matrix_world.to_3x3() @ per_depth
        if ray.z < -1e-6:
            depth = min(depth, 0.85 * (cam.matrix_world.translation.z - st.floor_z) / -ray.z)
    # Parts are left in their final pose, so `follow` offsets are measured there.
    cap = size * 2 * depth * 18.0 / cam.data.lens * 9 / 16
    local = per_depth * depth

    txt = flat_text(f"label-{text}", text, local, cap, material, extrude=0.0)
    txt.parent = cam
    appear(txt, appear_at, appear_at + 8)

    pin = _link(bpy.data.objects.new(f"anchor-{text}", None))
    if follow is not None:
        pin.parent = follow
        pin.location = a - follow.matrix_world.translation
    else:
        pin.location = a
    dot = ico(f"dot-{text}", (0, 0, 0), cap * 0.16, material, subdivisions=1)
    dot.parent = pin

    # the leader leaves the text on the side that faces the anchor
    from bpy_extras.object_utils import world_to_camera_view
    seen = world_to_camera_view(scene, cam, a)
    du, dv = seen.x - u, seen.y - v
    if abs(dv) < 0.07:
        start = Vector(((1 if du > 0 else -1) * (len(text) * cap * 0.30 + cap * 0.5), 0, 0))
    else:
        start = Vector((0, (1 if dv > 0 else -1) * cap * 0.95, 0))
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, 0.5, 0)))
    line = _mesh_object(f"leader-{text}", bm, material)
    line.parent = cam
    line.location = local + start
    line.scale = (cap * 0.05, 1.0, cap * 0.05)
    stretch = line.constraints.new("STRETCH_TO")
    stretch.target = pin
    stretch.rest_length = 1.0
    stretch.volume = "NO_VOLUME"
    for ob in (line, dot):
        ob.hide_render = True
        ob.keyframe_insert("hide_render", frame=max(1, appear_at - 1))
        ob.hide_render = False
        ob.keyframe_insert("hide_render", frame=appear_at)
    return txt


def prism(name, outline, z0, z1, material):
    """Extrude a 2D outline (list of (x, y), counter-clockwise) between two heights."""
    bm = bmesh.new()
    lower = [bm.verts.new((x, y, z0)) for x, y in outline]
    upper = [bm.verts.new((x, y, z1)) for x, y in outline]
    n = len(outline)
    bm.faces.new(list(reversed(lower)))
    bm.faces.new(upper)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((lower[i], lower[j], upper[j], upper[i]))
    return soften(_mesh_object(name, bm, material), angle=30.0)


def rounded_polygon(corners, radius, steps=8):
    """Outline of a convex polygon with every corner replaced by an arc."""
    pts, n = [], len(corners)
    for i in range(n):
        p = Vector(corners[i]).to_2d()
        a = (Vector(corners[i - 1]).to_2d() - p).normalized()
        b = (Vector(corners[(i + 1) % n]).to_2d() - p).normalized()
        half = a.angle(b) / 2
        centre = p + (a + b).normalized() * (radius / math.sin(half))
        start = p + a * (radius / math.tan(half)) - centre
        sweep = math.pi - 2 * half
        for k in range(steps + 1):
            t = sweep * k / steps
            v = Vector((start.x * math.cos(t) - start.y * math.sin(t), start.x * math.sin(t) + start.y * math.cos(t)))
            pts.append(tuple(centre + v))
    return pts
