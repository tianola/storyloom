"""Character style lab: the same three characters (a sleepy worker with a mug, an explorer who points,
a word-token who waves) drawn in four looks, so one can be chosen for the episode.

  vinyl    glossy toy beans with noodle arms and big shiny eyes
  hose     1930s rubber-hose cartoon: pie eyes, white gloves, big shoes, ink outlines, flat shading
  gummy    translucent candy blobs that glow from inside, bead eyes, no limbs to speak of
  clay     stop-motion plasticine: thumbprinted matte surface, big nose, toothy grin, thick brows

Everything is built around the origin with the character facing -Y, feet on z=0, about 1.2 tall,
then grouped under one empty so a scene can place, turn and scale it.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

import kit

# ---------------------------------------------------------------------------
# geometry helpers
# ---------------------------------------------------------------------------


def link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def smooth(ob):
    if ob.type == "MESH":
        for p in ob.data.polygons:
            p.use_smooth = True
    return ob


def subsurf(ob, levels=2):
    m = ob.modifiers.new("sub", "SUBSURF")
    m.levels = m.render_levels = levels
    return smooth(ob)


def to_mesh(ob):
    """Bake a metaball or curve into a plain mesh object (so outlines and ray casts work on it)."""
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    name, mw = ob.name, ob.matrix_world.copy()
    mats = list(getattr(ob.data, "materials", []))
    bpy.data.objects.remove(ob)
    new = link(bpy.data.objects.new(name, me))
    new.matrix_world = mw
    if not me.materials:
        for m in mats:
            me.materials.append(m)
    return smooth(new)


def blob(name, elems, mat, res=0.022):
    """Metaball shape baked to a mesh. elems: dicts with co, r, and optional type/size/stiff."""
    mb = bpy.data.metaballs.new(name)
    mb.resolution = mb.render_resolution = res
    mb.threshold = 0.6
    ob = link(bpy.data.objects.new(name, mb))
    for e in elems:
        el = mb.elements.new(type=e.get("type", "BALL"))
        el.co = e["co"]
        el.radius = e["r"]
        el.stiffness = e.get("stiff", 2.0)
        if "size" in e:
            el.size_x, el.size_y, el.size_z = e["size"]
    mb.materials.append(mat)
    return to_mesh(ob)


def ball(name, loc, r, mat, scale=(1, 1, 1), rot=(0, 0, 0), seg=32, rings=16):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=rings, radius=r, location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = scale
    ob.data.materials.append(mat)
    return smooth(ob)


def cap(name, loc, r, mat, keep=0.5, scale=(1, 1, 1), rot=(0, 0, 0), below=False):
    """The top (or bottom) part of a sphere: `keep` is the fraction of the height kept. Lids, domes, mouths."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=20, radius=r)
    z0 = r * (1 - 2 * keep) * (-1 if below else 1)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, z0), plane_no=(0, 0, -1 if below else 1),
                                 clear_inner=True)
    cut = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
    if cut:
        bmesh.ops.holes_fill(bm, edges=cut, sides=0)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = link(bpy.data.objects.new(name, me))
    ob.location, ob.scale, ob.rotation_euler = loc, scale, rot
    me.materials.append(mat)
    return smooth(ob)


def tube(name, pts, r, mat, radii=None, mesh=True):
    """A smooth noodle through the points (bezier, auto handles), radius scaled per point by `radii`."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = r
    cu.bevel_resolution = 6
    cu.resolution_u = 14
    cu.use_fill_caps = True
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        bp = sp.bezier_points[i]
        bp.co = p
        bp.handle_left_type = bp.handle_right_type = "AUTO"
        bp.radius = radii[i] if radii else 1.0
    cu.materials.append(mat)
    ob = link(bpy.data.objects.new(name, cu))
    return to_mesh(ob) if mesh else ob


def torus(name, loc, major, minor, mat, scale=(1, 1, 1), rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor, major_segments=48, minor_segments=16,
                                     location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = scale
    ob.data.materials.append(mat)
    return smooth(ob)


def rounded_box(name, loc, size, mat, bevel=0.3, rot=(0, 0, 0)):
    """A soft box: a cube with a wide bevel, subdivided."""
    ob = kit.box(name, loc, size, mat, bevel=0)
    ob.rotation_euler = rot
    b = ob.modifiers.new("bev", "BEVEL")
    b.width = bevel * min(size)
    b.segments = 4
    return subsurf(ob, 1)


def mug(name, loc, mat, ink, scale=1.0):
    body = kit.cyl(f"{name}-cup", loc, 0.075 * scale, 0.14 * scale, mat, verts=32)
    handle = torus(f"{name}-handle", (loc[0] + 0.08 * scale, loc[1], loc[2]), 0.04 * scale, 0.014 * scale, mat,
                   rot=(math.pi / 2, 0, 0))
    coffee = kit.cyl(f"{name}-coffee", (loc[0], loc[1], loc[2] + 0.066 * scale), 0.066 * scale, 0.01, ink, verts=32)
    steam = [tube(f"{name}-steam{k}", [(loc[0] + dx, loc[1], loc[2] + 0.1 * scale),
                                       (loc[0] + dx + 0.025, loc[1], loc[2] + 0.16 * scale),
                                       (loc[0] + dx - 0.02, loc[1], loc[2] + 0.22 * scale),
                                       (loc[0] + dx + 0.01, loc[1], loc[2] + 0.28 * scale)],
                  0.008 * scale, kit.mat("cs-steam", (0.9, 0.9, 0.9), emission=0.6), radii=[1, 0.9, 0.6, 0.2])
             for k, dx in enumerate((-0.025 * scale, 0.03 * scale))]
    return [body, handle, coffee] + steam


def hit(ob, x, z, y0=-5.0):
    """Where a ray from the front (−Y) at (x, z) meets `ob`: (point, normal), in the object's space."""
    bpy.context.view_layer.update()
    ok, loc, nor, _ = ob.ray_cast(Vector((x, y0, z)), Vector((0, 1, 0)))
    if not ok:
        return Vector((x, -0.3, z)), Vector((0, -1, 0))
    return loc, nor


def top(ob, x=0.0, y=0.0):
    bpy.context.view_layer.update()
    ok, loc, nor, _ = ob.ray_cast(Vector((x, y, 6)), Vector((0, 0, -1)))
    return loc if ok else Vector((x, y, 1.0))


def group(name, parts, loc=(0, 0, 0), facing=0.0, scale=1.0):
    g = kit.group(name, parts)
    g.location = loc
    g.rotation_euler = (0, 0, facing)
    g.scale = (scale, scale, scale)
    return g


# ---------------------------------------------------------------------------
# materials
# ---------------------------------------------------------------------------

def _new(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, m.node_tree


def vinyl(name, color, rough=0.28, coat=0.6, sss=0.08):
    m, nt = _new(name)
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Coat Roughness"].default_value = 0.12
    b.inputs["Subsurface Weight"].default_value = sss
    b.inputs["Subsurface Radius"].default_value = (0.4, 0.2, 0.1)
    b.inputs["Subsurface Scale"].default_value = 0.05
    return m


def glow(name, color, strength):
    m, nt = _new(name)
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Emission Color"].default_value = (*color, 1)
    b.inputs["Emission Strength"].default_value = strength
    return m


def gummy(name, color):
    m, nt = _new(name)
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = 0.1
    b.inputs["Coat Weight"].default_value = 1.0
    b.inputs["Coat Roughness"].default_value = 0.05
    b.inputs["Subsurface Weight"].default_value = 1.0
    b.inputs["Subsurface Radius"].default_value = tuple(min(1.0, c * 1.4 + 0.15) for c in color)
    b.inputs["Subsurface Scale"].default_value = 0.35
    b.inputs["Emission Color"].default_value = (*color, 1)
    b.inputs["Emission Strength"].default_value = 0.35
    return m


def clay(name, color, bump=0.35):
    """Matte plasticine: a fine noise for the surface, a coarser one for thumb-pressed dents."""
    m, nt = _new(name)
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = 0.62
    b.inputs["Subsurface Weight"].default_value = 0.2
    b.inputs["Subsurface Radius"].default_value = (0.5, 0.25, 0.15)
    b.inputs["Subsurface Scale"].default_value = 0.03
    coord = nt.nodes.new("ShaderNodeTexCoord")
    fine = nt.nodes.new("ShaderNodeTexNoise")
    fine.inputs["Scale"].default_value = 90.0
    fine.inputs["Detail"].default_value = 8.0
    dents = nt.nodes.new("ShaderNodeTexVoronoi")
    dents.feature = "SMOOTH_F1"
    dents.inputs["Scale"].default_value = 9.0
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "MULTIPLY_ADD"
    add.inputs[1].default_value = 0.25
    nt.links.new(coord.outputs["Object"], fine.inputs["Vector"])
    nt.links.new(coord.outputs["Object"], dents.inputs["Vector"])
    nt.links.new(fine.outputs["Fac"], add.inputs[0])
    nt.links.new(dents.outputs["Distance"], add.inputs[2])
    bmp = nt.nodes.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = bump
    bmp.inputs["Distance"].default_value = 0.004
    nt.links.new(add.outputs["Value"], bmp.inputs["Height"])
    nt.links.new(bmp.outputs["Normal"], b.inputs["Normal"])
    return m


def toon(name, color, shade=0.42):
    """Two-tone cel shading: lit or in shadow, nothing between, plus a thin bright rim."""
    m, nt = _new(name)
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    diff = nt.nodes.new("ShaderNodeBsdfDiffuse")
    s2r = nt.nodes.new("ShaderNodeShaderToRGB")
    bw = nt.nodes.new("ShaderNodeRGBToBW")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    ramp.color_ramp.elements[0].color = (*[c * shade for c in color], 1)
    ramp.color_ramp.elements[1].position = 0.12
    ramp.color_ramp.elements[1].color = (*color, 1)
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(diff.outputs[0], s2r.inputs[0])
    nt.links.new(s2r.outputs["Color"], bw.inputs[0])
    nt.links.new(bw.outputs[0], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def ink_line():
    m = bpy.data.materials.get("cs-outline")
    if m:
        return m
    m, nt = _new("cs-outline")
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0.01, 0.008, 0.01, 1)
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    m.use_backface_culling = True
    return m


def outline(ob, thick=0.012):
    """Inverted hull: a slightly larger, inside-out copy in black, culled from the front."""
    if ob.type != "MESH":
        return ob
    ob.data.materials.append(ink_line())
    s = ob.modifiers.new("outline", "SOLIDIFY")
    s.thickness = thick
    s.offset = 1.0
    s.use_flip_normals = True
    s.use_rim = False
    s.material_offset = len(ob.data.materials) - 1
    return ob


# ---------------------------------------------------------------------------
# faces
# ---------------------------------------------------------------------------

def eye(name, body, x, z, r, *, white, pupil, lid_mat=None, lid=0.0, look=(0.0, 0.0), size=0.5,
        squash=1.0, sink=0.45, droop=0.0):
    """A glossy eye seated on `body` at (x, z): white, pupil, catch-light, and optionally an upper lid
    covering `lid` of it (0 open, 0.5 half shut, 1 closed)."""
    p, n = hit(body, x, z)
    c = p - n * r * sink
    parts = [ball(f"{name}-w", c, r, white, scale=(1, 0.82, squash))]
    front = c + Vector((look[0] * r * 0.38, -r * 0.7, look[1] * r * 0.38 * squash))
    parts.append(ball(f"{name}-p", front, r * size, pupil, scale=(1, 0.55, squash)))
    hl = glow("cs-catch", (1, 1, 1), 3.0)
    parts.append(ball(f"{name}-h", front + Vector((-r * size * 0.32, -r * size * 0.45, r * size * 0.38 * squash)),
                      r * size * 0.26, hl, seg=12, rings=8))
    if lid > 0 and lid_mat is not None:
        sx = 1 if x > 0 else -1
        parts.append(cap(f"{name}-lid", c, r * 1.07, lid_mat, keep=lid, scale=(1, 0.86, squash),
                         rot=(0, math.radians(droop * sx), 0)))
    return parts


def smile(name, body, x0, x1, z, depth, mat, r=0.012, lift=0.0):
    pts = []
    for k in range(5):
        t = k / 4
        x = x0 + (x1 - x0) * t
        zz = z - depth * math.sin(math.pi * t) + lift * (abs(t - 0.5) * 2)
        p, n = hit(body, x, zz)
        pts.append(p + n * 0.004)
    return tube(name, pts, r, mat)


def open_mouth(name, body, x, z, w, h, inside, tongue, below=0.0):
    p, n = hit(body, x, z)
    parts = [ball(f"{name}", p - n * 0.01, 1.0, inside, scale=(w, 0.03, h), seg=32, rings=16)]
    parts.append(ball(f"{name}-tongue", p + Vector((0, -0.012, -h * 0.45)), 1.0, tongue, scale=(w * 0.55, 0.03, h * 0.35)))
    return parts


# ---------------------------------------------------------------------------
# style 1: vinyl beans
# ---------------------------------------------------------------------------

def vinyl_person(name, role="worker", *, color=(0.18, 0.62, 0.55), loc=(0, 0, 0), facing=0.0, scale=1.0):
    white = vinyl("cs-v-white", (0.92, 0.92, 0.9), rough=0.15)
    dark = vinyl("cs-v-dark", (0.02, 0.02, 0.025), rough=0.1)
    skin = vinyl(f"cs-v-{name}", color)
    blush = vinyl("cs-v-blush", (0.95, 0.35, 0.35), rough=0.5, coat=0)
    shoe = vinyl("cs-v-shoe", (0.08, 0.07, 0.09))
    body = blob(f"{name}-body", [{"co": (0, 0, 0.5), "r": 0.62, "type": "ELLIPSOID", "size": (0.68, 0.6, 0.95)},
                                 {"co": (0, -0.02, 0.36), "r": 0.5}], skin)
    parts = [body]
    sleepy = role in ("worker", "sleeper", "bored")
    tz = top(body).z
    lid = {"sleeper": 1.0, "bored": 0.58}.get(role, 0.48)
    for sx in (-1, 1):
        parts += eye(f"{name}-eye{sx}", body, sx * 0.12, tz - 0.2, 0.1, white=white, pupil=dark, lid_mat=skin,
                     lid=lid if sleepy else 0.0, look=(0.25 * sx if sleepy else -0.3, -0.35 if sleepy else 0.6),
                     size=0.5, droop=-12 if sleepy else 0)
        p, n = hit(body, sx * 0.2, tz - 0.36)
        parts.append(ball(f"{name}-blush{sx}", p - n * 0.008, 0.055, blush, scale=(1, 0.3, 0.6)))
    if role == "sleeper":
        parts += open_mouth(f"{name}-mouth", body, 0.02, tz - 0.42, 0.03, 0.03, dark, vinyl("cs-v-tongue", (0.85, 0.25, 0.3)))
    elif role == "bored":
        parts.append(smile(f"{name}-smile", body, -0.06, 0.06, tz - 0.4, -0.02, dark, r=0.012))
    elif sleepy:
        parts += open_mouth(f"{name}-mouth", body, 0.0, tz - 0.42, 0.05, 0.065, dark, vinyl("cs-v-tongue", (0.85, 0.25, 0.3)))
    else:
        parts.append(smile(f"{name}-smile", body, -0.08, 0.08, tz - 0.37, 0.04, dark, r=0.013))
    # arms: noodles with mitten hands
    hand = skin
    if role == "worker":
        arms = [[(-0.27, 0, 0.62), (-0.42, -0.05, 0.45), (-0.4, -0.08, 0.3)],
                [(0.27, 0, 0.62), (0.45, -0.12, 0.5), (0.3, -0.3, 0.52)]]
        parts += mug(f"{name}-mug", (0.26, -0.36, 0.52), white, dark)
    elif role == "sleeper":
        arms = [[(-0.27, 0, 0.62), (-0.38, -0.22, 0.6), (-0.18, -0.42, 0.66)],
                [(0.27, 0, 0.62), (0.38, -0.22, 0.6), (0.18, -0.42, 0.66)]]
    elif role == "bored":
        arms = [[(-0.27, 0, 0.62), (-0.36, -0.25, 0.62), (-0.2, -0.42, 0.7)],
                [(0.27, 0, 0.62), (0.42, -0.2, 0.62), (0.3, -0.38, 0.74)]]
        parts += mug(f"{name}-mug", (0.26, -0.44, 0.74), white, dark)
    elif role == "explorer":
        arms = [[(-0.27, 0, 0.62), (-0.5, -0.1, 0.85), (-0.62, -0.18, 1.12)],
                [(0.27, 0, 0.62), (0.42, -0.05, 0.45), (0.4, -0.06, 0.3)]]
    else:
        arms = [[(-0.27, 0, 0.62), (-0.45, -0.05, 0.75), (-0.5, -0.05, 0.98)],
                [(0.27, 0, 0.62), (0.42, -0.05, 0.45), (0.4, -0.06, 0.3)]]
    for k, pts in enumerate(arms):
        parts.append(tube(f"{name}-arm{k}", pts, 0.042, skin, radii=[1.1, 0.9, 0.85]))
        parts.append(ball(f"{name}-hand{k}", pts[-1], 0.075, hand, scale=(1, 0.8, 1.05)))
        parts.append(ball(f"{name}-thumb{k}", Vector(pts[-1]) + Vector((0.05 * (1 if k else -1), -0.04, 0.03)), 0.032, hand))
    if role == "explorer":
        parts.append(tube(f"{name}-finger", [arms[0][-1], (-0.66, -0.24, 1.22)], 0.026, hand))
        parts.append(ball(f"{name}-fingertip", (-0.66, -0.24, 1.22), 0.026, hand))
    for sx in (-1, 1):
        parts.append(tube(f"{name}-leg{sx}", [(sx * 0.12, 0, 0.2), (sx * 0.13, -0.02, 0.07)], 0.05, skin))
        parts.append(ball(f"{name}-shoe{sx}", (sx * 0.14, -0.06, 0.05), 0.1, shoe, scale=(0.9, 1.35, 0.55)))
    t = top(body)
    if role in ("worker", "sleeper", "bored"):
        hat = vinyl("cs-v-hat", (0.98, 0.7, 0.05), rough=0.25)
        tilt = (math.radians(-8), math.radians(10), 0)
        parts.append(cap(f"{name}-dome", (0.02, 0, t.z - 0.07), 0.25, hat, keep=0.5, scale=(1, 1, 0.85), rot=tilt))
        parts.append(torus(f"{name}-brim", (0.02, -0.01, t.z - 0.07), 0.25, 0.03, hat, scale=(1, 1.05, 0.55), rot=tilt))
        parts.append(tube(f"{name}-ridge", [(0.05, -0.2, t.z + 0.05), (0.04, 0, t.z + 0.15), (0.03, 0.2, t.z + 0.09)], 0.022, hat))
    elif role == "explorer":
        hat = vinyl("cs-v-pith", (0.86, 0.78, 0.58), rough=0.5)
        parts.append(cap(f"{name}-dome", (0, 0, t.z - 0.08), 0.27, hat, keep=0.55, scale=(1, 1.08, 0.8)))
        parts.append(torus(f"{name}-brim", (0, 0, t.z - 0.08), 0.34, 0.035, hat, scale=(1, 1.1, 0.4)))
        parts.append(kit.cyl(f"{name}-lamp", (0, -0.27, t.z + 0.02), 0.05, 0.06, glow("cs-lamp", (1, 0.93, 0.75), 8.0),
                             rot=(math.pi / 2, 0, 0), verts=24))
        parts.append(rounded_box(f"{name}-pack", (0, 0.3, 0.5), (0.4, 0.22, 0.42), vinyl("cs-v-pack", (0.55, 0.25, 0.08))))
    return group(name, parts, loc, facing, scale)


def vinyl_token(name, word="cat", number="9059", *, color=(0.98, 0.5, 0.08), loc=(0, 0, 0), facing=0.0, scale=1.0):
    white = vinyl("cs-v-white", (0.92, 0.92, 0.9), rough=0.15)
    dark = vinyl("cs-v-dark", (0.02, 0.02, 0.025), rough=0.1)
    skin = vinyl(f"cs-v-{name}", color)
    body = blob(f"{name}-body", [{"co": (0, 0, 0.42), "r": 0.52}, {"co": (0, 0, 0.3), "r": 0.42}], skin)
    parts = [body]
    for sx in (-1, 1):
        parts += eye(f"{name}-eye{sx}", body, sx * 0.13, 0.55, 0.12, white=white, pupil=dark, look=(0.1, 0.5), size=0.55)
        parts.append(tube(f"{name}-foot{sx}", [(sx * 0.12, 0, 0.12), (sx * 0.14, -0.04, 0.04)], 0.045, skin))
        parts.append(ball(f"{name}-shoe{sx}", (sx * 0.15, -0.07, 0.04), 0.085, skin, scale=(0.9, 1.3, 0.55)))
    parts += open_mouth(f"{name}-mouth", body, 0.0, 0.4, 0.08, 0.05, dark, vinyl("cs-v-tongue", (0.85, 0.25, 0.3)))
    wave = [(0.3, 0, 0.42), (0.45, -0.05, 0.55), (0.5, -0.05, 0.75)]
    parts.append(tube(f"{name}-arm", wave, 0.038, skin))
    parts.append(ball(f"{name}-hand", wave[-1], 0.065, skin))
    rest = [(-0.3, 0, 0.4), (-0.42, -0.06, 0.3), (-0.38, -0.1, 0.2)]
    parts.append(tube(f"{name}-arm2", rest, 0.038, skin))
    parts.append(ball(f"{name}-hand2", rest[-1], 0.065, skin))
    t = top(body)
    parts.append(tube(f"{name}-curl", [(0, 0, t.z - 0.02), (0.02, -0.02, t.z + 0.12), (0.1, -0.02, t.z + 0.2),
                                       (0.14, -0.02, t.z + 0.12), (0.08, -0.02, t.z + 0.1)], 0.018, dark, radii=[1, 1, 0.9, 0.8, 0.6]))
    p, n = hit(body, 0, 0.22)
    plate = rounded_box(f"{name}-plate", p + Vector((0, -0.01, 0)), (0.36, 0.04, 0.17), dark, bevel=0.4)
    parts.append(plate)
    ink = glow("cs-ink", (0.96, 0.96, 0.94), 2.0)
    parts.append(kit.flat_text(f"{name}-word", word, p + Vector((0, -0.04, 0.025)), 0.1, ink, rot=(math.pi / 2, 0, 0)))
    parts.append(kit.flat_text(f"{name}-id", number, p + Vector((0, -0.04, -0.045)), 0.05,
                               glow("cs-ink-cool", (0.45, 0.85, 1.0), 2.0), rot=(math.pi / 2, 0, 0)))
    return group(name, parts, loc, facing, scale)


# ---------------------------------------------------------------------------
# style 2: rubber hose
# ---------------------------------------------------------------------------

def _glove(name, at, mat, k, point=False):
    parts = [ball(f"{name}-palm", at, 0.07, mat, scale=(1, 0.8, 1))]
    for i, (dx, dz) in enumerate(((-0.05, 0.06), (0.0, 0.08), (0.05, 0.06))):
        tip = Vector(at) + Vector((dx * k, -0.03, dz + (0.08 if point and i == 1 else 0)))
        if point and i != 1:
            tip = Vector(at) + Vector((dx * k, -0.06, 0.0))
        parts.append(tube(f"{name}-f{i}", [Vector(at) + Vector((dx * k * 0.6, -0.01, 0.02)), tip], 0.026, mat))
    parts.append(torus(f"{name}-cuff", Vector(at) + Vector((0, 0.0, -0.07)), 0.06, 0.02, mat))
    return parts


def hose_person(name, role="worker", *, color=(0.85, 0.12, 0.1), loc=(0, 0, 0), facing=0.0, scale=1.0):
    face = toon("cs-h-face", (0.98, 0.86, 0.68))
    black = toon("cs-h-black", (0.03, 0.03, 0.035), shade=1.0)
    white = toon("cs-h-white", (0.97, 0.97, 0.95), shade=0.75)
    suit = toon(f"cs-h-{name}", color)
    body = blob(f"{name}-body", [{"co": (0, 0, 0.42), "r": 0.48, "type": "ELLIPSOID", "size": (0.75, 0.62, 0.9)},
                                 {"co": (0, 0, 0.28), "r": 0.4}], suit)
    head = blob(f"{name}-head", [{"co": (0, 0, 0.98), "r": 0.42, "type": "ELLIPSOID", "size": (1.0, 0.92, 0.88)},
                                 {"co": (0, -0.05, 0.86), "r": 0.3}], face)
    parts = [body, head]
    sleepy = role == "worker"
    for sx in (-1, 1):
        p, n = hit(head, sx * 0.09, 1.02)
        c = p - n * 0.02
        h = 0.035 if sleepy else 0.075
        parts.append(ball(f"{name}-eye{sx}", c, 1.0, black, scale=(0.04, 0.03, h)))
        if not sleepy:
            parts.append(ball(f"{name}-pie{sx}", c + Vector((0.012, -0.02, 0.03)), 1.0, white, scale=(0.012, 0.01, 0.022)))
        else:
            parts.append(tube(f"{name}-bag{sx}", [c + Vector((-0.04, -0.01, -0.05)), c + Vector((0, -0.015, -0.065)),
                                                    c + Vector((0.04, -0.01, -0.05))], 0.006, black))
    p, n = hit(head, 0, 0.93)
    parts.append(ball(f"{name}-nose", p - n * 0.01, 0.05, black, scale=(1.2, 0.9, 0.9)))
    if sleepy:
        parts += open_mouth(f"{name}-mouth", head, 0.0, 0.82, 0.07, 0.07, black, toon("cs-h-tongue", (0.9, 0.2, 0.25)))
    else:
        parts += open_mouth(f"{name}-mouth", head, 0.0, 0.83, 0.12, 0.05, black, toon("cs-h-tongue", (0.9, 0.2, 0.25)))
    # skinny black limbs with bends, white gloves, huge shoes
    if role == "worker":
        arms = [[(-0.3, 0, 0.55), (-0.48, -0.05, 0.42), (-0.42, -0.12, 0.25), (-0.5, -0.12, 0.15)],
                [(0.3, 0, 0.55), (0.5, -0.1, 0.48), (0.42, -0.25, 0.55), (0.28, -0.34, 0.55)]]
        parts += mug(f"{name}-mug", (0.22, -0.4, 0.58), white, black)
    elif role == "explorer":
        arms = [[(-0.3, 0, 0.55), (-0.45, -0.05, 0.75), (-0.58, -0.12, 0.98), (-0.68, -0.18, 1.18)],
                [(0.3, 0, 0.55), (0.48, -0.05, 0.42), (0.45, -0.12, 0.25), (0.52, -0.12, 0.15)]]
    for k, pts in enumerate(arms):
        parts.append(tube(f"{name}-arm{k}", pts, 0.025, black))
        parts += _glove(f"{name}-g{k}", Vector(pts[-1]) + Vector((0, 0, 0.04)), white, 1 if k else -1,
                        point=(role == "explorer" and k == 0))
    for sx in (-1, 1):
        parts.append(tube(f"{name}-leg{sx}", [(sx * 0.13, 0, 0.18), (sx * 0.16, -0.02, 0.1), (sx * 0.15, -0.02, 0.07)], 0.026, black))
        parts.append(ball(f"{name}-shoe{sx}", (sx * 0.17, -0.1, 0.06), 0.13, black, scale=(0.85, 1.55, 0.55)))
        parts.append(ball(f"{name}-sole{sx}", (sx * 0.17, -0.1, 0.02), 0.13, white, scale=(0.86, 1.56, 0.18)))
    t = top(head)
    if role == "worker":
        hat = toon("cs-h-hat", (1.0, 0.78, 0.1))
        tilt = (math.radians(-6), math.radians(-14), 0)
        parts.append(cap(f"{name}-dome", (-0.03, 0, t.z - 0.06), 0.27, hat, keep=0.5, scale=(1, 1, 0.9), rot=tilt))
        parts.append(torus(f"{name}-brim", (-0.03, 0, t.z - 0.06), 0.28, 0.03, hat, scale=(1, 1.05, 0.5), rot=tilt))
    else:
        hat = toon("cs-h-pith", (0.92, 0.84, 0.62))
        parts.append(cap(f"{name}-dome", (0, 0, t.z - 0.08), 0.29, hat, keep=0.55, scale=(1, 1.08, 0.8)))
        parts.append(torus(f"{name}-brim", (0, 0, t.z - 0.08), 0.37, 0.035, hat, scale=(1, 1.1, 0.4)))
        parts.append(kit.cyl(f"{name}-lamp", (0, -0.29, t.z + 0.02), 0.05, 0.06, glow("cs-lamp", (1, 0.93, 0.75), 8.0),
                             rot=(math.pi / 2, 0, 0), verts=24))
    for ob in parts:
        if ob.type == "MESH" and not ob.name.endswith(("-h", "-lamp")):
            outline(ob, 0.012)
    return group(name, parts, loc, facing, scale)


def hose_token(name, word="cat", number="9059", *, color=(0.98, 0.5, 0.08), loc=(0, 0, 0), facing=0.0, scale=1.0):
    black = toon("cs-h-black", (0.03, 0.03, 0.035), shade=1.0)
    white = toon("cs-h-white", (0.97, 0.97, 0.95), shade=0.75)
    skin = toon(f"cs-h-{name}", color)
    body = blob(f"{name}-body", [{"co": (0, 0, 0.45), "r": 0.55}], skin)
    parts = [body]
    for sx in (-1, 1):
        p, n = hit(body, sx * 0.1, 0.58)
        c = p - n * 0.02
        parts.append(ball(f"{name}-eye{sx}", c, 1.0, black, scale=(0.05, 0.03, 0.09)))
        parts.append(ball(f"{name}-pie{sx}", c + Vector((0.015, -0.02, 0.035)), 1.0, white, scale=(0.014, 0.01, 0.025)))
        parts.append(tube(f"{name}-leg{sx}", [(sx * 0.12, 0, 0.12), (sx * 0.15, -0.02, 0.05)], 0.022, black))
        parts.append(ball(f"{name}-shoe{sx}", (sx * 0.16, -0.08, 0.05), 0.11, black, scale=(0.85, 1.5, 0.55)))
    parts += open_mouth(f"{name}-mouth", body, 0.0, 0.43, 0.12, 0.06, black, toon("cs-h-tongue", (0.9, 0.2, 0.25)))
    for k, pts in enumerate(([(0.3, 0, 0.42), (0.48, -0.05, 0.6), (0.5, -0.05, 0.82)],
                             [(-0.3, 0, 0.4), (-0.46, -0.05, 0.3), (-0.42, -0.1, 0.2)])):
        parts.append(tube(f"{name}-arm{k}", pts, 0.022, black))
        parts += _glove(f"{name}-g{k}", Vector(pts[-1]) + Vector((0, 0, 0.04)), white, -1 if k else 1)
    p, n = hit(body, 0, 0.24)
    parts.append(rounded_box(f"{name}-plate", p + Vector((0, -0.01, 0)), (0.36, 0.04, 0.16), white, bevel=0.4))
    parts.append(kit.flat_text(f"{name}-word", word, p + Vector((0, -0.04, 0.02)), 0.1, black, rot=(math.pi / 2, 0, 0)))
    parts.append(kit.flat_text(f"{name}-id", number, p + Vector((0, -0.04, -0.045)), 0.045, black, rot=(math.pi / 2, 0, 0)))
    for ob in parts:
        if ob.type == "MESH" and not ob.name.endswith("-h"):
            outline(ob, 0.012)
    return group(name, parts, loc, facing, scale)


# ---------------------------------------------------------------------------
# style 3: gummy glow
# ---------------------------------------------------------------------------

def gummy_person(name, role="worker", *, color=(0.1, 0.75, 0.35), loc=(0, 0, 0), facing=0.0, scale=1.0):
    g = gummy(f"cs-g-{name}", color)
    dark = vinyl("cs-g-bead", (0.01, 0.01, 0.012), rough=0.05)
    sleepy = role == "worker"
    elems = [{"co": (0, 0, 0.32), "r": 0.6, "type": "ELLIPSOID", "size": (0.85, 0.75, 0.62)},
             {"co": (0, 0, 0.78), "r": 0.42},
             {"co": (-0.34, -0.02, 0.48), "r": 0.17},
             {"co": (0.34, -0.02, 0.48) if role != "explorer" else (0.3, -0.03, 0.62), "r": 0.17},
             {"co": (0.34, -0.02, 0.48) if role != "explorer" else (0.4, -0.05, 0.8), "r": 0.15},
             {"co": (-0.16, -0.02, 0.05), "r": 0.17}, {"co": (0.16, -0.02, 0.05), "r": 0.17}]
    body = blob(f"{name}-body", elems, g, res=0.02)
    parts = [body]
    for sx in (-1, 1):
        p, n = hit(body, sx * 0.11, 0.82)
        if sleepy:
            parts.append(tube(f"{name}-eye{sx}", [p + Vector((-0.035, -0.01, 0.01)), p + Vector((0, -0.012, -0.012)),
                                                   p + Vector((0.035, -0.01, 0.01))], 0.009, dark))
        else:
            parts.append(ball(f"{name}-eye{sx}", p - n * 0.005, 0.03, dark, scale=(1, 0.7, 1.3)))
            parts.append(ball(f"{name}-glint{sx}", p + Vector((-0.01, -0.02, 0.014)), 0.009, glow("cs-catch", (1, 1, 1), 3.0)))
    if sleepy:
        p, n = hit(body, 0.0, 0.7)
        parts.append(ball(f"{name}-mouth", p, 0.022, dark, scale=(1, 0.5, 1.2)))
        parts += mug(f"{name}-mug", (0.36, -0.22, 0.5), vinyl("cs-g-mug", (0.92, 0.92, 0.9), rough=0.2), dark)
    else:
        parts.append(smile(f"{name}-smile", body, -0.05, 0.05, 0.72, 0.025, dark, r=0.008))
    t = top(body)
    if role == "worker":
        hat = vinyl("cs-v-hat", (0.98, 0.7, 0.05), rough=0.25)
        tilt = (0, math.radians(14), 0)
        parts.append(cap(f"{name}-dome", (0.06, 0, t.z - 0.05), 0.17, hat, keep=0.5, scale=(1, 1, 0.85), rot=tilt))
        parts.append(torus(f"{name}-brim", (0.06, 0, t.z - 0.05), 0.17, 0.02, hat, scale=(1, 1.05, 0.55), rot=tilt))
    else:
        parts.append(kit.cyl(f"{name}-lamp", (0, -0.2, t.z - 0.12), 0.045, 0.05, glow("cs-lamp", (1, 0.93, 0.75), 8.0),
                             rot=(math.pi / 2, 0, 0), verts=24))
    return group(name, parts, loc, facing, scale)


def gummy_token(name, word="cat", number="9059", *, color=(1.0, 0.45, 0.05), loc=(0, 0, 0), facing=0.0, scale=1.0):
    g = gummy(f"cs-g-{name}", color)
    dark = vinyl("cs-g-bead", (0.01, 0.01, 0.012), rough=0.05)
    body = blob(f"{name}-body", [{"co": (0, 0, 0.22), "r": 0.62, "type": "ELLIPSOID", "size": (0.9, 0.85, 0.7)},
                                 {"co": (0, 0, 0.42), "r": 0.42},
                                 {"co": (-0.26, -0.04, 0.12), "r": 0.16}, {"co": (0.26, -0.04, 0.12), "r": 0.16}],
                g, res=0.02)
    parts = [body]
    for sx in (-1, 1):
        p, n = hit(body, sx * 0.1, 0.56)
        parts.append(ball(f"{name}-eye{sx}", p - n * 0.005, 0.032, dark, scale=(1, 0.7, 1.3)))
        parts.append(ball(f"{name}-glint{sx}", p + Vector((-0.01, -0.02, 0.015)), 0.01, glow("cs-catch", (1, 1, 1), 3.0)))
    parts.append(smile(f"{name}-smile", body, -0.05, 0.05, 0.48, 0.03, dark, r=0.009))
    p, n = hit(body, 0, 0.3)
    ink = glow("cs-ink", (0.96, 0.96, 0.94), 2.5)
    parts.append(kit.flat_text(f"{name}-word", word, p + Vector((0, -0.01, 0.0)), 0.12, ink, rot=(math.pi / 2, 0, 0)))
    parts.append(kit.flat_text(f"{name}-id", number, p + Vector((0, -0.01, -0.08)), 0.05,
                               glow("cs-ink-cool", (0.45, 0.85, 1.0), 2.0), rot=(math.pi / 2, 0, 0)))
    return group(name, parts, loc, facing, scale)


# ---------------------------------------------------------------------------
# style 4: clay
# ---------------------------------------------------------------------------

def clay_person(name, role="worker", *, color=(0.15, 0.3, 0.62), loc=(0, 0, 0), facing=0.0, scale=1.0):
    skin = clay("cs-c-skin", (0.86, 0.6, 0.45))
    suit = clay(f"cs-c-{name}", color)
    white = clay("cs-c-white", (0.94, 0.93, 0.88), bump=0.15)
    dark = clay("cs-c-dark", (0.04, 0.035, 0.035), bump=0.1)
    brow = clay("cs-c-brow", (0.18, 0.1, 0.06))
    body = blob(f"{name}-body", [{"co": (0, 0, 0.36), "r": 0.5, "type": "ELLIPSOID", "size": (0.8, 0.66, 0.8)},
                                 {"co": (0, 0, 0.22), "r": 0.42}], suit)
    head = blob(f"{name}-head", [{"co": (0, 0, 0.92), "r": 0.44, "type": "ELLIPSOID", "size": (1.0, 0.9, 0.85)},
                                 {"co": (0, -0.04, 0.8), "r": 0.34}], skin)
    parts = [body, head]
    sleepy = role == "worker"
    for sx in (-1, 1):
        parts += eye(f"{name}-eye{sx}", head, sx * 0.085, 0.98, 0.085, white=white, pupil=dark, lid_mat=skin,
                     lid=0.55 if sleepy else 0.12, look=(0.0, -0.2) if sleepy else (-0.4, 0.5), size=0.42, sink=0.35,
                     droop=-10 if sleepy else 0)
        p, n = hit(head, sx * 0.1, 1.09)
        lift = -0.015 if sleepy else 0.02
        parts.append(tube(f"{name}-brow{sx}", [p + Vector((-0.06 * sx, -0.01, lift)), p + Vector((0, -0.02, 0.01)),
                                                p + Vector((0.06 * sx, -0.01, -lift))], 0.018, brow, radii=[0.7, 1, 0.8]))
        bpy.context.view_layer.update()
        ok, q, m, _ = head.ray_cast(Vector((sx * 5, 0, 0.9)), Vector((-sx, 0, 0)))
        parts.append(ball(f"{name}-ear{sx}", q + Vector((sx * 0.02, 0, 0)), 0.065, skin, scale=(0.55, 0.9, 1.15)))
    p, n = hit(head, 0, 0.9)
    parts.append(ball(f"{name}-nose", p - n * 0.02, 0.075, skin, scale=(1, 1.1, 0.9)))
    # wide mouth with a row of teeth
    p, n = hit(head, 0, 0.78)
    if sleepy:
        parts += open_mouth(f"{name}-mouth", head, 0.0, 0.77, 0.07, 0.06, dark, clay("cs-c-tongue", (0.75, 0.25, 0.28)))
    else:
        parts.append(cap(f"{name}-mouth", p - n * 0.03, 0.13, dark, keep=0.45, below=True, scale=(1, 0.35, 0.8)))
        for i in range(5):
            x = -0.08 + i * 0.04
            q, m = hit(head, x, 0.79)
            parts.append(rounded_box(f"{name}-tooth{i}", q + Vector((0, -0.01, 0)), (0.034, 0.02, 0.035), white, bevel=0.4))
        if role == "explorer":
            parts.append(tube(f"{name}-tash", [p + Vector((-0.14, -0.03, 0.0)), p + Vector((-0.06, -0.06, 0.06)),
                                               p + Vector((0, -0.07, 0.04)), p + Vector((0.06, -0.06, 0.06)),
                                               p + Vector((0.14, -0.03, 0.0))], 0.03, brow, radii=[0.4, 1, 0.8, 1, 0.4]))
    if role == "worker":
        arms = [[(-0.3, 0, 0.5), (-0.42, -0.05, 0.36), (-0.38, -0.1, 0.22)],
                [(0.3, 0, 0.5), (0.44, -0.12, 0.42), (0.3, -0.3, 0.48)]]
        parts += mug(f"{name}-mug", (0.26, -0.36, 0.5), white, dark)
    else:
        arms = [[(-0.3, 0, 0.5), (-0.5, -0.1, 0.72), (-0.6, -0.16, 0.98)],
                [(0.3, 0, 0.5), (0.42, -0.05, 0.36), (0.38, -0.1, 0.22)]]
    for k, pts in enumerate(arms):
        parts.append(tube(f"{name}-arm{k}", pts, 0.065, suit, radii=[1, 0.9, 0.8]))
        parts.append(ball(f"{name}-hand{k}", pts[-1], 0.075, skin, scale=(1, 0.85, 1.05)))
    for sx in (-1, 1):
        parts.append(ball(f"{name}-shoe{sx}", (sx * 0.16, -0.08, 0.05), 0.12, dark, scale=(0.85, 1.4, 0.5)))
    t = top(head)
    if role == "worker":
        hat = clay("cs-c-hat", (0.95, 0.7, 0.08))
        tilt = (math.radians(-10), math.radians(-6), 0)
        parts.append(cap(f"{name}-dome", (0, 0.01, t.z - 0.07), 0.29, hat, keep=0.5, scale=(1, 1, 0.85), rot=tilt))
        parts.append(torus(f"{name}-brim", (0, 0.0, t.z - 0.07), 0.3, 0.035, hat, scale=(1, 1.05, 0.5), rot=tilt))
    else:
        hat = clay("cs-c-pith", (0.85, 0.77, 0.55))
        parts.append(cap(f"{name}-dome", (0, 0, t.z - 0.08), 0.3, hat, keep=0.55, scale=(1, 1.08, 0.8)))
        parts.append(torus(f"{name}-brim", (0, 0, t.z - 0.08), 0.38, 0.04, hat, scale=(1, 1.1, 0.4)))
        parts.append(kit.cyl(f"{name}-lamp", (0, -0.3, t.z + 0.03), 0.05, 0.06, glow("cs-lamp", (1, 0.93, 0.75), 8.0),
                             rot=(math.pi / 2, 0, 0), verts=24))
    return group(name, parts, loc, facing, scale)


def clay_token(name, word="cat", number="9059", *, color=(0.95, 0.48, 0.1), loc=(0, 0, 0), facing=0.0, scale=1.0):
    skin = clay(f"cs-c-{name}", color)
    white = clay("cs-c-white", (0.94, 0.93, 0.88), bump=0.15)
    dark = clay("cs-c-dark", (0.04, 0.035, 0.035), bump=0.1)
    body = blob(f"{name}-body", [{"co": (0, 0, 0.42), "r": 0.52}, {"co": (0, 0, 0.3), "r": 0.44}], skin)
    parts = [body]
    for sx in (-1, 1):
        parts += eye(f"{name}-eye{sx}", body, sx * 0.1, 0.56, 0.1, white=white, pupil=dark, look=(0.0, 0.4), size=0.45, sink=0.35)
        parts.append(ball(f"{name}-shoe{sx}", (sx * 0.15, -0.07, 0.04), 0.09, skin, scale=(0.9, 1.3, 0.55)))
    p, n = hit(body, 0, 0.4)
    parts.append(cap(f"{name}-mouth", p - n * 0.03, 0.13, dark, keep=0.45, below=True, scale=(1, 0.35, 0.75)))
    for i in range(5):
        x = -0.08 + i * 0.04
        q, m = hit(body, x, 0.415)
        parts.append(rounded_box(f"{name}-tooth{i}", q + Vector((0, -0.01, 0)), (0.034, 0.02, 0.035), white, bevel=0.4))
    wave = [(0.3, 0, 0.42), (0.45, -0.05, 0.55), (0.5, -0.05, 0.75)]
    parts.append(tube(f"{name}-arm", wave, 0.045, skin, radii=[1, 0.9, 0.8]))
    parts.append(ball(f"{name}-hand", wave[-1], 0.065, skin))
    p, n = hit(body, 0, 0.2)
    parts.append(rounded_box(f"{name}-plate", p + Vector((0, -0.015, 0)), (0.34, 0.04, 0.15), white, bevel=0.4))
    parts.append(kit.flat_text(f"{name}-word", word, p + Vector((0, -0.045, 0.02)), 0.09, dark, rot=(math.pi / 2, 0, 0)))
    parts.append(kit.flat_text(f"{name}-id", number, p + Vector((0, -0.045, -0.04)), 0.045, dark, rot=(math.pi / 2, 0, 0)))
    return group(name, parts, loc, facing, scale)


STYLES = {
    "vinyl": (vinyl_person, vinyl_token, {"worker": (0.2, 0.62, 0.56), "explorer": (0.95, 0.42, 0.38)}),
    "hose": (hose_person, hose_token, {"worker": (0.85, 0.12, 0.1), "explorer": (0.25, 0.45, 0.2)}),
    "gummy": (gummy_person, gummy_token, {"worker": (0.1, 0.75, 0.35), "explorer": (0.2, 0.45, 1.0)}),
    "clay": (clay_person, clay_token, {"worker": (0.15, 0.3, 0.62), "explorer": (0.35, 0.4, 0.18)}),
}


def lineup(style):
    """Worker, explorer and token side by side, a little turned towards each other."""
    person, tok, colors = STYLES[style]
    person(f"{style}-worker", "worker", color=colors["worker"], loc=(-1.15, 0, 0), facing=math.radians(12))
    person(f"{style}-explorer", "explorer", color=colors["explorer"], loc=(0.05, 0.1, 0), facing=math.radians(-4))
    tok(f"{style}-token", loc=(1.15, -0.05, 0), facing=math.radians(-14), scale=0.95)
