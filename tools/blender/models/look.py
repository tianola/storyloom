"""The "explainer" look: a studio set where the subject is lit by what it does.

Every storyboard beat is built in it (`open_set` then `shoot`): a haze sky with a horizon
instead of a black void, an evenly glossy concrete floor that reflects what glows on it
(screen-traced reflections), a warm key and cool rim from the first view plus a fill and
an overhead softbox sized to the whole set, emissive accents with bloom, and shallow depth
of field. Motion comes from the mechanism itself: signals running along traces, parts
lighting as they work. Tags (`auto_tag`) take a free slot at the frame's edge.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

import camera_plan
import kit
from kit import FPS

WARM = (1.0, 0.36, 0.045)
COOL = (0.20, 0.72, 1.0)


def _keys_linear(id_data):
    if id_data.animation_data and id_data.animation_data.action:
        for fc in id_data.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"


def open_set(seconds, res=None):
    """An empty set under the haze sky, ready for objects. Returns the frame count.

    Split from the camera so a scene can be built first and then asked which views it
    offers: `shoot()` places the camera afterwards.
    """
    frames = int(round(seconds * FPS))
    kit.common.wipe()
    kit.reset_materials()
    del bpy.app.handlers.frame_change_pre[:]
    # the off-white parts drop back and the gold accent glows faintly: in this look the
    # brightest thing in frame should be whatever is doing the work
    kit.TONE.update(base=(0.36, 0.37, 0.40), accent_glow=0.55)
    canvas = kit.STYLE["canvas"]
    w, h = res or (canvas["width"], canvas["height"])
    kit.common.setup_scene(FPS, 1, frames, w, h)
    scene = bpy.context.scene
    # screen-traced reflections and AO: the floor mirrors what glows on it and parts sit on
    # the ground instead of floating in it
    scene.eevee.use_raytracing = True
    if hasattr(scene.eevee, "ray_tracing_method"):
        scene.eevee.ray_tracing_method = "SCREEN"
    if hasattr(scene.eevee, "use_fast_gi"):
        scene.eevee.use_fast_gi = True
    scene.view_settings.exposure = 0.25
    scene.world = haze_world()
    return frames


HORIZON = (0.050, 0.060, 0.078)     # the haze where the floor meets the sky
ZENITH = (0.006, 0.008, 0.014)


def haze_world():
    """A sky with depth instead of a black void: dark overhead, a cool haze at the horizon,
    and a faint even fill so the shadow side of a part is dark grey rather than missing."""
    world = bpy.data.worlds.new("Haze World")
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes["Background"]
    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(coord.outputs["Generated"], sep.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (*HORIZON, 1.0)
    ramp.color_ramp.elements[1].position = 0.45
    ramp.color_ramp.elements[1].color = (*ZENITH, 1.0)
    up = nt.nodes.new("ShaderNodeMath")
    up.operation = "ABSOLUTE"
    nt.links.new(sep.outputs["Z"], up.inputs[0])
    nt.links.new(up.outputs[0], ramp.inputs["Fac"])
    fill = nt.nodes.new("ShaderNodeBackground")
    fill.inputs["Color"].default_value = (0.030, 0.034, 0.044, 1.0)
    fill.inputs["Strength"].default_value = 1.0
    path = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(path.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(fill.outputs[0], mix.inputs[1])
    nt.links.new(bg.outputs[0], mix.inputs[2])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.0
    nt.links.new(mix.outputs[0], nt.nodes["World Output"].inputs["Surface"])
    return world


def stage_floor(centre, floor_z, grid, reach):
    """A large floor that reads as a material: speckled, slightly glossy concrete with faint
    tile seams every `grid` units, fading into the horizon haze far from the camera, so a
    small part stands somewhere instead of hanging in a black void."""
    m = bpy.data.materials.new("look-floor")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    coord = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 1.4
    noise.inputs["Detail"].default_value = 6.0
    noise.inputs["Roughness"].default_value = 0.62
    nt.links.new(coord.outputs["Object"], noise.inputs["Vector"])
    tone = nt.nodes.new("ShaderNodeValToRGB")
    tone.color_ramp.elements[0].position = 0.35
    tone.color_ramp.elements[0].color = (0.036, 0.039, 0.046, 1.0)
    tone.color_ramp.elements[1].position = 0.70
    tone.color_ramp.elements[1].color = (0.050, 0.054, 0.062, 1.0)
    nt.links.new(noise.outputs["Fac"], tone.inputs["Fac"])
    # one even sheen: varying the roughness breaks a light's reflection into patches that
    # read as smoke on the floor
    b.inputs["Roughness"].default_value = 0.42
    b.inputs["Specular IOR Level"].default_value = 0.35

    # tile seams: distance to the nearest grid line, in both directions
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(coord.outputs["Object"], sep.inputs["Vector"])

    def seam(axis):
        scale = nt.nodes.new("ShaderNodeMath")
        scale.operation = "MULTIPLY"
        scale.inputs[1].default_value = 1.0 / max(grid, 0.05)
        nt.links.new(sep.outputs[axis], scale.inputs[0])
        ping = nt.nodes.new("ShaderNodeMath")
        ping.operation = "PINGPONG"
        ping.inputs[1].default_value = 0.5
        nt.links.new(scale.outputs[0], ping.inputs[0])
        edge = nt.nodes.new("ShaderNodeMath")
        edge.operation = "LESS_THAN"
        edge.inputs[1].default_value = 0.012
        nt.links.new(ping.outputs[0], edge.inputs[0])
        return edge

    seams = nt.nodes.new("ShaderNodeMix")
    seams.data_type = "RGBA"
    seams.inputs["B"].default_value = (0.10, 0.11, 0.13, 1.0)
    seams.inputs["Factor"].default_value = 0.0
    if grid:
        lines = nt.nodes.new("ShaderNodeMath")
        lines.operation = "MAXIMUM"
        nt.links.new(seam("X").outputs[0], lines.inputs[0])
        nt.links.new(seam("Y").outputs[0], lines.inputs[1])
        nt.links.new(lines.outputs[0], seams.inputs["Factor"])
    nt.links.new(tone.outputs["Color"], seams.inputs["A"])

    # far floor melts into the haze, so there is a horizon and no hard edge
    view = nt.nodes.new("ShaderNodeCameraData")
    far = nt.nodes.new("ShaderNodeMapRange")
    far.inputs["From Min"].default_value = reach * 2.5
    far.inputs["From Max"].default_value = reach * 9.0
    nt.links.new(view.outputs["View Distance"], far.inputs["Value"])
    fade = nt.nodes.new("ShaderNodeMix")
    fade.data_type = "RGBA"
    fade.inputs["B"].default_value = (*HORIZON, 1.0)
    nt.links.new(far.outputs["Result"], fade.inputs["Factor"])
    nt.links.new(seams.outputs["Result"], fade.inputs["A"])
    nt.links.new(fade.outputs["Result"], b.inputs["Base Color"])
    glow = nt.nodes.new("ShaderNodeMath")
    glow.operation = "MULTIPLY"
    glow.inputs[1].default_value = 0.9
    nt.links.new(far.outputs["Result"], glow.inputs[0])
    b.inputs["Emission Color"].default_value = (*HORIZON, 1.0)
    nt.links.new(glow.outputs[0], b.inputs["Emission Strength"])

    size = max(400.0, reach * 40)
    return kit.box("bench", (centre[0], centre[1], floor_z - 0.05), (size, size, 0.1), m, bevel=0)


def set_bounds(exclude=()):
    """Centre and half-size of everything built so far: lights are placed for the whole set,
    not only for the first shot, so a cut to the far side still finds it lit."""
    lo, hi = Vector((1e9, 1e9, 1e9)), Vector((-1e9, -1e9, -1e9))
    found = False
    for ob in bpy.context.scene.objects:
        if ob.type not in {"MESH", "CURVE", "FONT"} or ob in exclude or ob.hide_render:
            continue
        for corner in ob.bound_box:
            p = ob.matrix_world @ Vector(corner)
            lo = Vector(map(min, lo, p))
            hi = Vector(map(max, hi, p))
            found = True
    if not found:
        return Vector((0, 0, 0.5)), 3.0
    centre = (lo + hi) / 2
    return centre, max(1.5, min(40.0, ((hi - lo).length / 2)))


def light_set(target, mid, reach, *, gain=1.0, key_side=1.0):
    """Warm key, cool rim, a low fill and an overhead softbox.

    The key and rim keep their old placement from the first view (their energy is what the
    scenes were tuned against); the fill and the softbox are sized to the whole set so a cut
    to its far side, or a wide view of it, is still lit like the same room."""
    centre, half = set_bounds()
    key = Vector(kit.key_location(mid, target, elevation=38.0, side=key_side, yaw=-10.0, distance=reach))
    key += Vector(target)
    soft_light("key", key, target, 5.2 * gain * reach ** 2, (1.0, 0.80, 0.62), size=reach * 0.7)
    back = Vector(target) + (Vector(target) - Vector(mid)).normalized() * reach * 0.9
    back.z = target[2] + reach * 0.55
    back += Vector((-(mid.y - target[1]), mid.x - target[0], 0)).normalized() * reach * 0.5 * -key_side
    soft_light("rim", back, target, 8.0 * gain * reach ** 2, (0.45, 0.70, 1.0), size=reach * 0.5)
    span = max(half, reach * 0.6)
    side = (Vector(mid) - centre)
    side.z = 0
    side = side.normalized() if side.length > 1e-6 else Vector((0, -1, 0))
    across = Vector((-side.y, side.x, 0)) * key_side
    fill = centre - across * span * 1.6 + side * span * 0.8
    fill.z = centre.z + span * 0.5
    soft_light("fill", fill, centre, 1.6 * gain * span ** 2, (0.62, 0.74, 1.0), size=span * 1.4)
    top = centre + Vector((0, 0, span * 2.2))
    soft_light("softbox", top, centre, 2.4 * gain * span ** 2, (0.95, 0.93, 0.90), size=span * 2.0)


def soft_light(name, location, target, energy, color, size=6.0):
    lamp = kit.common.add_area_light(name, location, energy, color=color, size=size)
    kit.common.aim(lamp, target)
    return lamp


def neon(name, color, strength=3.0, base=None):
    """Emissive accent. The base colour is kept dark so it reads as a light source."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*(base or tuple(c * 0.25 for c in color)), 1.0)
    b.inputs["Roughness"].default_value = 0.5
    b.inputs["Emission Color"].default_value = (*color, 1.0)
    b.inputs["Emission Strength"].default_value = strength
    return m


def signal_material(name, frames, *, axis="X", color=COOL, rest=0.12, peak=9.0, spacing=0.25,
                    speed=0.5, lanes=40.0, base=(0.01, 0.02, 0.035)):
    """A trace that carries moving pulses of light.

    Along `axis` (object space) a comet of brightness repeats every `spacing` units and
    travels at `speed` units a second; every lane across the other axis gets its own
    phase, so a field of parallel traces does not blink in unison. It is one material on
    one mesh, which is why thousands of signals cost nothing to render.
    """
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*base, 1.0)
    b.inputs["Roughness"].default_value = 0.5
    b.inputs["Emission Color"].default_value = (*color, 1.0)
    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(coord.outputs["Object"], sep.inputs["Vector"])
    along, across = ("X", "Y") if axis == "X" else ("Y", "X")

    def math_node(op, a, b_value):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        for i, v in enumerate((a, b_value)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                nt.links.new(v, n.inputs[i])
        return n

    lane = math_node("FLOOR", math_node("MULTIPLY", sep.outputs[across], lanes).outputs[0], None)
    phase = math_node("MULTIPLY", lane.outputs[0], 0.37)
    clock = nt.nodes.new("ShaderNodeValue")
    clock.outputs[0].default_value = 0.0
    clock.outputs[0].keyframe_insert("default_value", frame=1)
    clock.outputs[0].default_value = -speed / spacing * frames / FPS
    clock.outputs[0].keyframe_insert("default_value", frame=frames)
    _keys_linear(nt)
    pos = math_node("MULTIPLY", sep.outputs[along], 1.0 / spacing)
    total = math_node("ADD", math_node("ADD", pos.outputs[0], phase.outputs[0]).outputs[0], clock.outputs[0])
    saw = math_node("FRACT", total.outputs[0], None)
    comet = math_node("POWER", saw.outputs[0], 7.0)
    strength = math_node("ADD", math_node("MULTIPLY", comet.outputs[0], peak).outputs[0], rest)
    nt.links.new(strength.outputs[0], b.inputs["Emission Strength"])
    return m


def pill(st, text, anchor, screen, *, start, until=None, size=0.040, follow=None):
    """A small rounded tag with a hairline to the part it names, on screen for a window.

    `start` / `until` are seconds. The tag rides on the camera at half the distance to
    its anchor (measured over the window, at the closest the camera gets), so it stays
    in front of the subject through a dive.
    """
    f0 = max(1, round(start * FPS))
    f1 = round(until * FPS) if until else st.frames
    cam, scene = st.cam, bpy.context.scene
    if isinstance(anchor, bpy.types.Object):
        scene.frame_set((f0 + f1) // 2)
        bpy.context.view_layer.update()
        a = anchor.matrix_world.translation.copy()
    else:
        a = Vector(anchor)
    u, v = screen
    per_depth = Vector(((2 * u - 1) * 18.0 / cam.data.lens, (2 * v - 1) * 18.0 / cam.data.lens * 9 / 16, -1.0))
    depth = 1.0
    cap = size * 2 * depth * 18.0 / cam.data.lens * 9 / 16
    local = per_depth * depth

    ink = kit.mat("look-pill-ink", (0.95, 0.95, 0.93), emission=1.3)
    txt = kit.flat_text(f"pill-{text}", text, local, cap, ink, extrude=0.0)
    txt.parent = st.rig
    half_w = len(text) * cap * 0.255 + cap * 0.75
    plate_mat = kit.mat("look-pill-plate", (0.035, 0.04, 0.05), roughness=0.9, emission=0.25,
                        emission_color=(0.06, 0.07, 0.09))
    outline = kit.rounded_polygon([(-half_w, -cap), (half_w, -cap), (half_w, cap), (-half_w, cap)], cap * 0.95)
    plate = kit.prism(f"pill-plate-{text}", outline, -cap * 0.06, -cap * 0.03, plate_mat)
    plate.parent = st.rig
    plate.location = local

    if isinstance(anchor, bpy.types.Object):
        pin = anchor
    else:
        pin = kit._link(bpy.data.objects.new(f"anchor-{text}", None))
        scene.frame_set(f1)
        bpy.context.view_layer.update()
        if follow is not None:
            pin.parent = follow
            pin.location = a - follow.matrix_world.translation
        else:
            pin.location = a
    hair = kit.mat("look-pill-hair", WARM, emission=1.1)
    dot = kit.ico(f"pill-dot-{text}", (0, 0, 0), 1.0, hair, subdivisions=1)
    dot.parent = pin
    # the dot lives in the world, so its size is set from how far away it will be seen
    scene.frame_set((f0 + f1) // 2)
    bpy.context.view_layer.update()
    r = cap * 0.16 * (a - cam.matrix_world.translation).length
    dot.scale = (r, r, r)
    scene.frame_set((f0 + f1) // 2)
    bpy.context.view_layer.update()
    from bpy_extras.object_utils import world_to_camera_view
    seen = world_to_camera_view(scene, cam, pin.matrix_world.translation)
    if seen.z <= 0 or not (0.0 <= seen.x <= 1.0 and 0.0 <= seen.y <= 1.0):
        st.problems.append(f"tag '{text}' points at something off screen (u={seen.x:.2f} v={seen.y:.2f})")
    below = seen.y < v
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, 0.5, 0)))
    line = kit._mesh_object(f"pill-line-{text}", bm, hair)
    line.parent = st.rig
    line.location = local + Vector((0, (-1.08 if below else 1.08) * cap, 0))
    line.scale = (cap * 0.018, 1.0, cap * 0.018)
    stretch = line.constraints.new("STRETCH_TO")
    stretch.target = pin
    stretch.rest_length = 1.0
    stretch.volume = "NO_VOLUME"

    for ob in (txt, plate, line, dot):
        ob.hide_render = True
        ob.keyframe_insert("hide_render", frame=max(1, f0 - 1))
        ob.hide_render = False
        ob.keyframe_insert("hide_render", frame=f0)
        if until:
            ob.keyframe_insert("hide_render", frame=f1 - 1)
            ob.hide_render = True
            ob.keyframe_insert("hide_render", frame=f1)
    for ob in (txt, plate):
        if ob.parent is None:
            continue
        full = tuple(ob.scale)
        ob.scale = (0.001, 0.001, 0.001)
        ob.keyframe_insert("scale", frame=f0)
        ob.scale = full
        ob.keyframe_insert("scale", frame=f0 + 7)
    return txt


def hud_text(st, text, screen, *, size=0.05, start=0.0, until=None, color=(0.95, 0.95, 0.93), strength=1.6):
    """Text fixed to the screen: headings, counters, equations."""
    cam = st.cam
    u, v = screen
    cap = size * 2 * 18.0 / cam.data.lens * 9 / 16
    local = Vector(((2 * u - 1) * 18.0 / cam.data.lens, (2 * v - 1) * 18.0 / cam.data.lens * 9 / 16, -1.0))
    material = kit.mat(f"look-hud-{color}", color, emission=strength)
    txt = kit.flat_text(f"hud-{text}", text, local, cap, material, extrude=0.0)
    txt.parent = st.rig
    f0 = max(1, round(start * FPS))
    txt.hide_render = True
    txt.keyframe_insert("hide_render", frame=max(1, f0 - 1))
    txt.hide_render = False
    txt.keyframe_insert("hide_render", frame=f0)
    if until:
        txt.keyframe_insert("hide_render", frame=round(until * FPS) - 1)
        txt.hide_render = True
        txt.keyframe_insert("hide_render", frame=round(until * FPS))
    return txt


def counter(text_obj, start, end, value_at, template="{:,}"):
    """Drive a HUD text from the frame number: value_at(t) with t in 0..1 over the window."""
    f0, f1 = round(start * FPS), round(end * FPS)
    name = text_obj.name

    def update(scene, *_):
        ob = bpy.data.objects.get(name)
        if ob is None:
            return
        t = min(1.0, max(0.0, (scene.frame_current - f0) / max(1, f1 - f0)))
        ob.data.body = template.format(int(value_at(t)))

    bpy.app.handlers.frame_change_pre.append(update)
    return update


# ---------------------------------------------------------------------------
# Several camera set-ups inside one beat
# ---------------------------------------------------------------------------

def shoot(shots, *, lens=50.0, fstop=6.3, floor_z=0.0, floor_grid=1.0, gain=1.0, key_side=1.0,
          screen_depth=0.45, bloom=True, lighting="studio"):
    """Camera, lights and floor for a set built after `open_set()`.

    shots: [{"start": seconds, "target": xyz, "radius": (a, b), "azimuth": (a, b),
             "height": (a, b)}, ...] in time order. Each is a slow arc; between two of them
    the picture cuts. It is one camera whose keys jump a frame apart, so everything that
    rides on the camera (tags, counters, focus) follows the cut for free.
    """
    scene = bpy.context.scene
    frames = scene.frame_end
    first = shots[0]
    aim = kit._link(bpy.data.objects.new("cam-target", None))
    start_pos = kit._orbit_point(first["target"], first["radius"][0], first["azimuth"][0], first["height"][0])
    cam = kit.common.add_camera("camera", tuple(start_pos), first["target"], lens=lens)
    cam.data.clip_start = 0.005
    cam.data.clip_end = 500.0
    track = cam.constraints.new("TRACK_TO")
    track.target = aim
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"
    cam.data.dof.use_dof = True
    cam.data.dof.focus_object = aim
    cam.data.dof.aperture_fstop = fstop
    rig = kit._link(bpy.data.objects.new("screen-rig", None))
    rig.parent = cam

    bounds = []
    for i, shot in enumerate(shots):
        f0 = 1 if i == 0 else round(shot["start"] * FPS) + 1
        f1 = frames if i == len(shots) - 1 else round(shots[i + 1]["start"] * FPS)
        f1 = max(f1, f0 + 4)
        bounds.append((f0, f1))
        travel = "target_to" in shot          # one continuous move from one view to another
        glide = travel and shot.get("glide") == "log"
        keys = 31 if glide else 9 if travel else 5
        # a travel holds still at both ends (staging.md: 0.5-1 s before a move, 1-2 s after): the first
        # two and last two keys share a progress, and the keys between them are eased
        plan = camera_plan.travel_keys((f1 - f0) / FPS, keys) if travel else [(k / (keys - 1), k / (keys - 1)) for k in range(keys)]
        for frac, t in plan:
            frame = round(f0 + (f1 - f0) * frac)
            (r0, r1), (h0, h1) = shot["radius"], shot["height"]
            if glide and r0 > 0 and r1 > 0:
                # a long descent (a town from the air down to one window): the distance shrinks by the
                # same ratio every second, so the end does not rush; height and aim follow the distance
                r = r0 * (r1 / r0) ** t
                u = (r0 - r) / (r0 - r1) if r0 != r1 else t
            else:
                r, u = r0 + (r1 - r0) * t, t
            target = Vector(shot["target"]).lerp(Vector(shot.get("target_to", shot["target"])), u)
            pos = kit._orbit_point(tuple(target), r,
                                   shot["azimuth"][0] + (shot["azimuth"][1] - shot["azimuth"][0]) * t,
                                   h0 + (h1 - h0) * u)
            cam.location = pos
            cam.keyframe_insert("location", frame=frame)
            aim.location = target
            aim.keyframe_insert("location", frame=frame)
            d = screen_depth * (pos - target).length
            rig.scale = (d, d, d)
            rig.keyframe_insert("scale", frame=frame)
    for ob in (cam, aim, rig):
        _keys_linear(ob)
    if bloom:
        import detail
        detail.add_glare(scene, glare_type="BLOOM", threshold=1.0, size=6)

    target = first["target"]
    reach = sum(first["radius"]) / 2
    mid = kit._orbit_point(target, reach, sum(first["azimuth"]) / 2, sum(first["height"]) / 2)
    if lighting == "studio":
        light_set(target, mid, reach, gain=gain, key_side=key_side)
        stage_floor(target, floor_z, floor_grid, reach)
    # "world": the scene lit itself (sky, sun or moon, lamps) and stands on its own ground

    st = kit.Stage(cam, target, frames)
    st.rig = rig
    st.mid_cam = Vector(mid)
    st.floor_z = floor_z
    st.shots = bounds
    st.taken = []
    kit.LAST = st
    scene.frame_set(1)
    return st


_SLOTS = ([(u, v) for v in (0.88, 0.12) for u in (0.18, 0.34, 0.50, 0.66, 0.82)]
          + [(u, v) for u in (0.15, 0.85) for v in (0.70, 0.50, 0.30)])


def reserve(st, rect, f0, f1):
    """Mark a screen rectangle (u0, v0, u1, v1) as occupied between two frames."""
    st.taken.append((rect, f0, f1))


def _free(st, rect, f0, f1):
    for (a0, b0, a1, b1), g0, g1 in st.taken:
        if f0 <= g1 and g0 <= f1 and rect[0] < a1 and a0 < rect[2] and rect[1] < b1 and b0 < rect[3]:
            return False
    return True


def auto_tag(st, text, pin, *, start, until=None, size=0.052):
    """A tag whose place on screen is chosen, not typed.

    The anchor is projected at the middle of the tag's window; of the edge slots that
    keep the pill inside the frame and clear of every other tag and counter, the one
    nearest the anchor wins, with a penalty for slots whose leader would cross the
    middle of the picture. An anchor that is not on screen gets no tag at all: a leader
    pointing out of frame reads as a mistake, and the report says so.
    """
    from bpy_extras.object_utils import world_to_camera_view
    scene = bpy.context.scene
    f0 = max(1, round(start * FPS))
    f1 = round(until * FPS) if until else st.frames
    scene.frame_set((f0 + f1) // 2)
    bpy.context.view_layer.update()
    seen = world_to_camera_view(scene, st.cam, pin.matrix_world.translation)
    if seen.z <= 0 or not (0.03 <= seen.x <= 0.97 and 0.04 <= seen.y <= 0.96):
        st.problems.append(f"tag '{text}' skipped: its anchor is off screen (u={seen.x:.2f} v={seen.y:.2f})")
        return None
    half_u = (len(text) * 0.255 + 0.75) * size * 9 / 16
    half_v = size * 1.15
    best, best_score = None, 1e9
    for u, v in _SLOTS:
        u = min(max(u, half_u + 0.03), 0.97 - half_u)
        rect = (u - half_u, v - half_v, u + half_u, v + half_v)
        if not _free(st, rect, f0, f1):
            continue
        du, dv = u - seen.x, (v - seen.y) * 9 / 16
        dist = math.hypot(du, dv)
        if dist < 0.10:
            continue
        cu, cv = seen.x - 0.5, (seen.y - 0.5) * 9 / 16
        centre = math.hypot(cu, cv)
        crossing = 0.0
        if centre > 0.03:
            crossing = max(0.0, -(du * cu + dv * cv) / (dist * centre))
        score = dist + 0.45 * crossing
        if score < best_score:
            best, best_score = (u, v, rect), score
    if best is None:
        st.problems.append(f"tag '{text}' skipped: no free place on screen")
        return None
    u, v, rect = best
    reserve(st, rect, f0, f1)
    return pill(st, text, pin, (u, v), start=start, until=until, size=size)
