"""Shared utilities for technique scenes.

Provides scene reset, EEVEE Next setup, AgX colour management,
primitive/material helpers, lighting, camera, and still rendering.
"""
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector


# ---------------------------------------------------------------------------
# Scene lifecycle
# ---------------------------------------------------------------------------

def wipe():
    """Remove every object, material, and world from the scene."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for coll in list(bpy.data.collections):
        bpy.data.collections.remove(coll)
    for mat in list(bpy.data.materials):
        bpy.data.materials.remove(mat)
    for world in list(bpy.data.worlds):
        bpy.data.worlds.remove(world)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)
    for cam in list(bpy.data.cameras):
        bpy.data.cameras.remove(cam)
    for light in list(bpy.data.lights):
        bpy.data.lights.remove(light)
    for curve in list(bpy.data.curves):
        bpy.data.curves.remove(curve)
    # Ensure at least one collection exists and is active
    if not bpy.data.collections:
        coll = bpy.data.collections.new("Scene Collection")
        bpy.context.scene.collection.children.link(coll)
    # Set active collection so bpy.ops.mesh.primitive_* works
    for lc in bpy.context.view_layer.layer_collection.children:
        if lc.name == "Scene Collection":
            bpy.context.view_layer.active_layer_collection = lc
            break


def setup_scene(fps=30, frame_start=1, frame_end=150,
                resolution_x=640, resolution_y=360):
    """Configure render settings: EEVEE Next, AgX, resolution, frame range."""
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.fps = fps
    scene.frame_start = frame_start
    scene.frame_end = frame_end
    scene.render.resolution_x = resolution_x
    scene.render.resolution_y = resolution_y
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False

    # EEVEE Next settings
    scene.eevee.taa_render_samples = 32
    # Ray tracing is the switch that makes a transparent shell behave like glass. With it
    # off, EEVEE resolves every Transparent BSDF against the *world* only, so a plasma
    # filament in front of a starfield paints a black bar over the stars and reads as a
    # solid dark rod, and an x-ray hull blacks out the cabin instead of revealing it.
    # use_ssr / use_ssr_refraction are 4.1 names and are gone in 4.5 — they silently did
    # nothing here, which is how that defect survived a whole episode.
    if hasattr(scene.eevee, "use_raytracing"):
        scene.eevee.use_raytracing = True

    # AgX colour management
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0


def setup_world(color=(0.035, 0.05, 0.08, 1.0), strength=0.25):
    """Create a simple studio world background."""
    world = bpy.data.worlds.new("Studio World")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = color
    bg.inputs["Strength"].default_value = strength
    bpy.context.scene.world = world
    return world


# ---------------------------------------------------------------------------
# Material helpers
# ---------------------------------------------------------------------------

def set_transparent(mat, method="BLENDED"):
    """Turn on real alpha blending for a material.

    EEVEE Next ignores the legacy `blend_method` (deprecated) and reads
    `surface_render_method`, whose default DITHERED scatters alpha across pixels, which
    renders as film grain over the whole shell.

    Ray-traced refraction goes with it: without it a transparent surface samples the
    world colour rather than the scene behind it, so a shell in front of stars or of the
    interior it is supposed to reveal renders as a dark solid instead of as glass.
    """
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = method
    if hasattr(mat, "blend_method"):
        mat.blend_method = "BLEND" if method == "BLENDED" else "HASHED"
    if hasattr(mat, "show_transparent_back"):
        mat.show_transparent_back = False
    if hasattr(mat, "use_raytrace_refraction"):
        mat.use_raytrace_refraction = True
        # Default depth is shallow; a corridor or a hull shell has planets behind it.
        mat.refraction_depth = 4.0
    return mat


def material_principled(name, color, metallic=0.0, roughness=0.4,
                        emission_color=(0, 0, 0, 1), emission_strength=0.0,
                        alpha=1.0):
    """Create a Principled BSDF material."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color[:3], 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission_strength > 0:
        bsdf.inputs["Emission Color"].default_value = emission_color
        bsdf.inputs["Emission Strength"].default_value = emission_strength
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
        set_transparent(mat)
    return mat


def vmath(nodes, links, op, *srcs):
    """A Vector Math node wired from sockets and/or literal tuples.

    Vector Math carries a fourth socket named "Scale" that the SCALE operation reads its
    factor from; inputs[1] stays a plain vector and is ignored entirely by that operation.
    Linking a mask into [1] instead silently leaves every scale at its default 1.0, which
    is how a dark solar-cell field once rendered as one silver board.
    """
    node = nodes.new("ShaderNodeVectorMath")
    node.operation = op
    for i, src in zip((0, 3) if op == "SCALE" else (0, 1), srcs):
        if src is None:
            continue
        sock = node.inputs[i]
        if isinstance(src, bpy.types.NodeSocket):
            links.new(src, sock)
        elif hasattr(src, "__len__"):
            # Colours in this pipeline are written as RGBA (ColorRamp stops), but a Vector
            # Math socket only holds three components. The alpha is dropped exactly as the
            # implicit socket conversion would drop it.
            sock.default_value = tuple(src)[:3]
        else:
            sock.default_value = float(src)
    return node.outputs["Vector"]


def math_node(nodes, links, op, *srcs, clamp=False):
    """A Math node wired from sockets and/or literals."""
    node = nodes.new("ShaderNodeMath")
    node.operation = op
    for i, src in enumerate(srcs):
        if src is None:
            continue
        sock = node.inputs[i]
        if isinstance(src, bpy.types.NodeSocket):
            links.new(src, sock)
        else:
            sock.default_value = float(src)
    node.use_clamp = clamp
    return node.outputs["Value"]


def smooth_mask(nodes, links, source, edge, feather=0.06):
    """A soft 0/1 threshold on a 0..1 field.

    Map Range rather than a Math step because the Math node has no SMOOTHSTEP operation,
    and a hard edge on a sub-millimetre feature is exactly what shimmers.
    """
    node = nodes.new("ShaderNodeMapRange")
    node.interpolation_type = "SMOOTHSTEP"
    node.inputs["From Min"].default_value = edge
    node.inputs["From Max"].default_value = edge + feather
    links.new(source, node.inputs["Value"])
    return node.outputs["Result"]


def solar_cell_material(name, *, cells=(16, 11), axes="XZ",
                        cell_color=(0.028, 0.038, 0.070),
                        gap_color=(0.42, 0.43, 0.45),
                        bus_color=(0.66, 0.64, 0.58),
                        roughness_cell=0.22, roughness_gap=0.42,
                        jitter=0.30):
    """An actual photovoltaic wing: square cells, silver gaps, thin busbars.

    Ten beats drew each array as one flat navy box at metallic 0.45, so a solar panel —
    the object that most reliably says "spacecraft" — rendered as a painted rectangle and
    was the strongest remaining "cube" signal on screen.

    Sampled in **Generated** coordinates rather than Object: the wings are cubes scaled by
    `obj.scale`, which is never applied, so Object space would give a non-square grid whose
    cell count depends on the mesh's unit size. Generated spans 0..1 across the bounding
    box, so `cells` is the literal number of cells across the panel whatever its metres,
    and square cells just mean matching `cells` to the aspect ratio. `axes` names the two
    wide axes, because a wing can lie in XZ (Orion) or XY (CubeSat) depending on which
    axis was squashed.

    The thresholds are smoothstepped instead of hard-stepped: a procedural hard edge
    shimmers at the pixel size where a texture would mip-map.
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    def vm(op, *srcs):
        return vmath(nodes, links, op, *srcs)

    def mn(op, *srcs, clamp=False):
        return math_node(nodes, links, op, *srcs, clamp=clamp)

    def wave(axis, scale, edge, feather=0.045):
        node = nodes.new("ShaderNodeTexWave")
        node.wave_type = "BANDS"
        node.bands_direction = axis
        node.wave_profile = "SAW"
        node.inputs["Scale"].default_value = scale
        links.new(grid, node.inputs["Vector"])
        return smooth_mask(nodes, links, node.outputs["Fac"], edge, feather)

    tex = nodes.new("ShaderNodeTexCoord")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(tex.outputs["Generated"], sep.inputs["Vector"])
    join = nodes.new("ShaderNodeCombineXYZ")
    for src_axis, dst in zip(axes, join.inputs):
        links.new(sep.outputs[src_axis], dst)
    # One unit of `grid` is now one cell, so a wave at scale 1 repeats once per cell.
    grid = vm("MULTIPLY", join.outputs["Vector"], (*cells, 1.0))

    # A real cell is 156 mm with a 2 mm gap, so the interconnect lines are a few percent
    # of the pitch. Wider than that and the grid, not the silicon, becomes the read.
    gap = mn("MAXIMUM", wave("X", 1.0, 0.955), wave("Y", 1.0, 0.955))
    busbar = mn("MAXIMUM", wave("X", 0.25, 0.975, 0.025), wave("Y", 0.25, 0.975, 0.025))
    busbar = mn("MULTIPLY", busbar, mn("SUBTRACT", 1.0, gap))

    noise = nodes.new("ShaderNodeTexWhiteNoise")
    noise.noise_dimensions = "3D"
    links.new(vm("FLOOR", grid), noise.inputs["Vector"])
    shade = mn("MULTIPLY_ADD", noise.outputs["Value"], jitter, 1.0 - jitter)

    col = vm("ADD", cell_color, vm("SCALE", vm("SUBTRACT", gap_color, cell_color), gap))
    col = vm("ADD", col, vm("SCALE", vm("SUBTRACT", bus_color, cell_color), busbar))
    links.new(vm("SCALE", col, shade), bsdf.inputs["Base Color"])

    links.new(mn("MULTIPLY_ADD", gap, roughness_gap - roughness_cell,
                 roughness_cell, clamp=True), bsdf.inputs["Roughness"])
    metal = mn("MULTIPLY_ADD", gap, 0.62, 0.28)
    links.new(mn("MULTIPLY_ADD", busbar, 0.30, metal, clamp=True),
              bsdf.inputs["Metallic"])

    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.12
    bump.inputs["Distance"].default_value = 0.0035
    # Cells sit proud of the interconnect: 4.5 has no ONE_MINUS math operation.
    links.new(mn("SUBTRACT", 1.0, gap), bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def material_emissive(name, color, strength=5.0):
    """Create a purely emissive material."""
    mat = material_principled(
        name, color, roughness=0.2,
        emission_color=(*color[:3], 1.0),
        emission_strength=strength,
    )
    return mat


def material_glass(name, color=(0.55, 0.8, 1.0), roughness=0.12, ior=1.45):
    """Create a glass BSDF material."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    glass = nodes.new("ShaderNodeBsdfGlass")
    glass.inputs["Color"].default_value = (*color[:3], 1.0)
    glass.inputs["Roughness"].default_value = roughness
    glass.inputs["IOR"].default_value = ior
    mat.node_tree.links.new(glass.outputs[0], output.inputs["Surface"])
    set_transparent(mat)
    if hasattr(mat, "use_screen_refraction"):
        mat.use_screen_refraction = True
    return mat


def material_xray_shell(name, color=(0.55, 0.8, 1.0), mix_factor=0.5):
    """Create an X-ray shell material: mix of Transparent BSDF and Principled BSDF.

    The mix factor is animated: 0 = fully opaque, 1 = fully transparent.
    Returns (material, mix_node) so the caller can animate mix_node.inputs[0].
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.inputs["Base Color"].default_value = (*color[:3], 1.0)
    principled.inputs["Roughness"].default_value = 0.3
    principled.inputs["Alpha"].default_value = 0.6
    mix = nodes.new("ShaderNodeMixShader")
    mix.inputs[0].default_value = mix_factor
    mat.node_tree.links.new(transparent.outputs[0], mix.inputs[1])
    mat.node_tree.links.new(principled.outputs[0], mix.inputs[2])
    mat.node_tree.links.new(mix.outputs[0], output.inputs["Surface"])
    # HASHED dithers alpha per pixel, which renders as film grain over the whole shell.
    return set_transparent(mat), mix


# ---------------------------------------------------------------------------
# Primitive helpers
# ---------------------------------------------------------------------------

def _link_and_select(obj):
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    return obj


def add_sphere(name, location, radius, material=None, segments=32):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments, radius=radius, location=location)
    ob = bpy.context.active_object
    ob.name = name
    if material:
        ob.data.materials.append(material)
    bpy.ops.object.shade_smooth()
    return ob


TEXTURED_MATERIALS: dict = {}


def material_textured(name, tile, *, metres_per_tile=1.0, metallic=0.0,
                      roughness=0.40, bump=0.30, tint=(1.0, 1.0, 1.0),
                      saturate=1.0, bump_distance=0.004, specular=None, levels=None):
    """One owned PBR tile driving colour and relief, cached by parameter set.

    material_principled() can only take numbers, which is why every surface in the
    episode was uniform. The cache matters: 19 beats reuse the same handful of
    surfaces, and an uncached version would create a material and an image load per
    call.

    `specular` is the Principled specular level. The 0.5 default is a hardening for
    plastics and painted metal; a woven garment reflects almost none of it, and at the
    default every area light in a closed cabin lays a broad white sheet over the tile.
    That sheet is additive and unsaturated, so it compresses the colour difference
    between channels: the flame-orange suit tile measured (189, 92, 0) as an albedo and
    rendered (169, 134, 119), which is the same object reading as pale salmon.

    `levels` is ``(in_lo, in_hi, out_lo, out_hi)`` in linear reflectance. A generated
    photo arrives with whatever exposure the model happened to pick, and multiplying by
    a tint cannot fix that: a tile whose dark end sits at 0.001 stays at 0.001 however
    hard you push the gain, so the surface reads as holes punched in a colour instead of
    a colour with grain in it. Remapping the range first is what sets the floor.
    """
    tile = Path(tile)
    key = (tile.name, round(metres_per_tile, 4), round(metallic, 4), round(roughness, 4),
           round(bump, 4), tuple(round(c, 4) for c in tint[:3]), round(saturate, 4),
           round(bump_distance, 5), round(specular, 4) if specular is not None else None,
           tuple(round(c, 4) for c in levels) if levels else None)
    hit = TEXTURED_MATERIALS.get(key)
    if hit is not None:
        return hit

    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = nodes["Principled BSDF"]

    img = bpy.data.images.load(str(tile), check_existing=True)
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.extension = "REPEAT"
    mapping = nodes.new("ShaderNodeMapping")
    scale = 1.0 / max(metres_per_tile, 1e-4)
    mapping.inputs["Scale"].default_value = (scale, scale, scale)
    uv = nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    links.new(uv.outputs["UV"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], tex.inputs["Vector"])

    hs = nodes.new("ShaderNodeHueSaturation")
    hs.inputs["Saturation"].default_value = saturate
    links.new(tex.outputs["Color"], hs.inputs["Color"])
    colour_out = hs.outputs["Color"]
    if levels:
        in_lo, in_hi, out_lo, out_hi = levels
        remap = nodes.new("ShaderNodeMapRange")
        remap.interpolation_type = "LINEAR"
        remap.clamp = True
        remap.inputs["From Min"].default_value = in_lo
        remap.inputs["From Max"].default_value = in_hi
        remap.inputs["To Min"].default_value = out_lo
        remap.inputs["To Max"].default_value = out_hi
        links.new(colour_out, remap.inputs["Value"])
        colour_out = remap.outputs["Result"]
    mix = nodes.new("ShaderNodeMixRGB")
    mix.blend_type = "MULTIPLY"
    mix.inputs["Fac"].default_value = 1.0
    mix.inputs["Color2"].default_value = (*tint[:3], 1.0)
    links.new(colour_out, mix.inputs["Color1"])
    links.new(mix.outputs["Color"], bsdf.inputs["Base Color"])

    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if specular is not None:
        # 4.x renamed the socket; a missing input must not silently leave the 0.5 default.
        sock = next((i for i in bsdf.inputs
                     if i.name in ("Specular IOR Level", "Specular")), None)
        if sock is not None:
            sock.default_value = specular

    if bump > 0.0:
        # The albedo node doubles as the height source. Loading the tile a second
        # time returns this same datablock (check_existing) and marking it Non-Color
        # would desaturate the surface.
        bw = nodes.new("ShaderNodeRGBToBW")
        links.new(tex.outputs["Color"], bw.inputs["Color"])
        bump_node = nodes.new("ShaderNodeBump")
        bump_node.inputs["Strength"].default_value = bump
        bump_node.inputs["Distance"].default_value = bump_distance
        links.new(bw.outputs["Val"], bump_node.inputs["Height"])
        links.new(bump_node.outputs["Normal"], bsdf.inputs["Normal"])

    TEXTURED_MATERIALS[key] = mat
    return mat


def apply_cube_uv(objs, cube_size=1.0):
    """Cube-project so one UV unit equals one metre of world space.

    Run this before any parent-scale packing: projecting afterwards measures the
    unscaled mesh and the tile lands at the wrong size.
    """
    if not isinstance(objs, (list, tuple)):
        objs = [objs]
    for ob in objs:
        # Beats hide a pre-drop stage or a cutaway wall with hide_set/hide_viewport, and
        # an object hidden from the view layer cannot enter EDIT mode — the operators
        # below then fail with no exception and no UVs, so the surface samples one texel
        # and renders as the flat colour it had before texturing.
        was_hidden = (ob.hide_get(), ob.hide_viewport, ob.hide_render)
        ob.hide_set(False)
        ob.hide_viewport = False
        ob.hide_render = False
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = ob
        ob.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.cube_project(cube_size=cube_size)
        bpy.ops.object.mode_set(mode="OBJECT")
        ob.select_set(False)
        ob.hide_set(was_hidden[0])
        ob.hide_viewport = was_hidden[1]
        ob.hide_render = was_hidden[2]


def harden_edges(ob, width=0.010, segments=3, angle_deg=40.0):
    """A mathematically sharp 90-degree edge catches no highlight and reads as a placeholder."""
    m = ob.modifiers.new("bevel", "BEVEL")
    m.width = width
    m.segments = segments
    m.angle_limit = math.radians(angle_deg)
    m.limit_method = "ANGLE"
    m.harden_normals = True
    return m


def add_box(name, location, size, material=None):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = size
    # location and rotation are NOT optional here. transform_apply's own flags default
    # to True, so `transform_apply(scale=True)` silently bakes the world position into
    # the mesh as well and leaves the object at the origin — and every caller that sets
    # rotation_euler afterwards then rotates that baked mesh about the world origin,
    # landing the part at twice the angle it asked for. Baking scale only is the whole
    # point: the size becomes metres, the transform stays free.
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material:
        ob.data.materials.append(material)
    return ob


def add_cylinder(name, location, radius, depth, material=None, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(
        radius=radius, depth=depth, location=location, rotation=rotation)
    ob = bpy.context.active_object
    ob.name = name
    if material:
        ob.data.materials.append(material)
    bpy.ops.object.shade_smooth()
    return ob


def add_torus(name, location, major_radius, minor_radius, material=None,
              rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_torus_add(
        location=location, major_radius=major_radius,
        minor_radius=minor_radius, rotation=rotation)
    ob = bpy.context.active_object
    ob.name = name
    if material:
        ob.data.materials.append(material)
    bpy.ops.object.shade_smooth()
    return ob


# ---------------------------------------------------------------------------
# Lighting
# ---------------------------------------------------------------------------

def aim(obj, target):
    """Point obj's -Z axis at target."""
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def add_area_light(name, location, energy, color=(1, 1, 1), size=5.0):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.color = color
    data.shape = "DISK"
    data.size = size
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    aim(obj, (0, 0, 0))
    return obj


def add_sun_light(name, location, energy, color=(1, 1, 1), rotation=None,
                  angle=None):
    data = bpy.data.lights.new(name, "SUN")
    data.energy = energy
    data.color = color
    if angle is not None:
        # A point-direction sun gives a hard-edged black silhouette wherever a vehicle
        # crosses a lit body. Widening the disc to a few degrees buys a penumbra, which
        # is what a shadow on regolith or concrete actually looks like.
        data.angle = angle
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    if rotation is None:
        # A sun renders its direction from rotation only and ignores its position, so the
        # vector has to be converted or every call site shares one hardcoded angle.
        d = Vector(location)
        if d.length > 0:
            obj.rotation_euler = (-d.normalized()).to_track_quat("-Z", "Y").to_euler()
        else:
            obj.rotation_euler = (0.5, 0, 0.3)
    else:
        obj.rotation_euler = rotation
    return obj


# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------

def add_camera(name, location, target, lens=50.0):
    """Create a camera aimed at target."""
    data = bpy.data.cameras.new(name)
    data.lens = lens
    data.clip_start = 0.1
    data.clip_end = 2000.0
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    aim(obj, target)
    bpy.context.scene.camera = obj
    return obj


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_still(frame, output_path, samples=32):
    """Render a single frame to a PNG file."""
    scene = bpy.context.scene
    scene.eevee.taa_render_samples = samples
    scene.frame_set(frame)
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(output_path)
    bpy.ops.render.render(write_still=True)
    return Path(output_path)


def save_blend(output_path):
    """Save the current scene as a .blend file."""
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
