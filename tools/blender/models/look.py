"""The "explainer" look: a dark stage where the subject is lit by what it does.

fern-minimal (kit.stage) is a matte tabletop under one raking sun, cut on sentences.
This is the other register, for the stretches that take a system apart: near-black
world, emissive accents with bloom, shallow depth of field, and ONE camera path that
travels from the whole object down into its smallest part without a cut. Motion comes
from the mechanism itself: signals running along traces, parts lighting as they work.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

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
    """Empty dark world, ready for objects. Returns the frame count.

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
    scene.eevee.use_raytracing = False
    world = bpy.data.worlds.new("Dark World")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.004, 0.006, 0.012, 1.0)
    bg.inputs["Strength"].default_value = 1.0
    scene.world = world
    return frames


def dark_stage(seconds, path, *, lens=35.0, fstop=4.0, bloom=True, res=None, screen_depth=0.92):
    """Black world, two soft lights, and a camera that follows `path` in one move.

    path: [(seconds, camera_xyz, look_at_xyz), ...]. Both the camera and the point it
    looks at are keyed with Bezier handles, so the travel eases through every waypoint
    instead of stopping at it. Focus rides on the look-at point.
    """
    frames = open_set(seconds, res)
    scene = bpy.context.scene

    aim = kit._link(bpy.data.objects.new("cam-target", None))
    cam = kit.common.add_camera("camera", path[0][1], path[0][2], lens=lens)
    cam.data.clip_start = 0.005
    cam.data.clip_end = 500.0
    track = cam.constraints.new("TRACK_TO")
    track.target = aim
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"
    for t, pos, look in path:
        frame = max(1, round(t * FPS))
        cam.location = pos
        cam.keyframe_insert("location", frame=frame)
        aim.location = look
        aim.keyframe_insert("location", frame=frame)
    cam.data.dof.use_dof = True
    cam.data.dof.focus_object = aim
    cam.data.dof.aperture_fstop = fstop

    if bloom:
        import detail
        detail.add_glare(scene, glare_type="BLOOM", threshold=1.0, size=6)

    # Everything drawn "on the screen" hangs off this rig. It sits at the lens and is
    # scaled, frame by frame, to just inside the focus distance: scaling about the lens
    # changes how far away a tag is without changing where or how large it appears, so
    # tags stay sharp through a dive instead of dissolving in the depth of field.
    rig = kit._link(bpy.data.objects.new("screen-rig", None))
    rig.parent = cam
    for frame in range(1, frames + 1, 2):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        d = screen_depth * (aim.matrix_world.translation - cam.matrix_world.translation).length
        rig.scale = (d, d, d)
        rig.keyframe_insert("scale", frame=frame)
    scene.frame_set(1)

    st = kit.Stage(cam, path[-1][2], frames)
    st.rig = rig
    st.mid_cam = Vector(path[len(path) // 2][1])
    st.floor_z = -1e9
    kit.LAST = st
    return st


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


def orbit_stage(seconds, *, target=(0, 0, 0.5), radius=(11.0, 9.0), azimuth=(-70.0, -40.0),
                height=(6.0, 5.0), lens=50.0, fstop=6.3, floor_z=0.0, floor_grid=1.0, key_side=1.0, gain=1.0,
                **_ignored):
    """kit.stage's call shape in the explainer look: the same slow arc around a subject,
    on the dark stage, lit by a warm key and a cool rim placed from the camera."""
    steps = max(2, int(seconds))
    path = []
    for i in range(steps + 1):
        t = i / steps
        path.append((seconds * t,
                     tuple(kit._orbit_point(target, radius[0] + (radius[1] - radius[0]) * t,
                                            azimuth[0] + (azimuth[1] - azimuth[0]) * t,
                                            height[0] + (height[1] - height[0]) * t)),
                     target))
    st = dark_stage(seconds, path, lens=lens, fstop=fstop, screen_depth=0.45)
    _keys_linear(st.cam)
    st.target = target
    st.floor_z = floor_z
    reach = sum(radius) / 2
    mid = kit._orbit_point(target, reach, sum(azimuth) / 2, sum(height) / 2)
    key = Vector(kit.key_location(mid, target, elevation=38.0, side=key_side, yaw=-10.0, distance=reach))
    key += Vector(target)
    soft_light("key", key, target, 4.6 * gain * reach ** 2, (1.0, 0.80, 0.62), size=reach * 0.6)
    back = Vector(target) + (Vector(target) - Vector(mid)).normalized() * reach * 0.9
    back.z = target[2] + reach * 0.55
    back += Vector((-(mid.y - target[1]), mid.x - target[0], 0)).normalized() * reach * 0.5 * -key_side
    soft_light("rim", back, target, 8.0 * gain * reach ** 2, (0.45, 0.70, 1.0), size=reach * 0.5)
    kit.box("bench", (target[0], target[1], floor_z - 0.05), (120, 120, 0.1),
            kit.mat("look-bench", (0.012, 0.014, 0.018), roughness=0.8), bevel=0)
    if floor_grid:
        n = 22
        dots = [((target[0] + (i - n / 2) * floor_grid, target[1] + (j - n / 2) * floor_grid, floor_z + 0.004),
                 0.03, 0.008) for i in range(n + 1) for j in range(n + 1)]
        kit.cylinders("floor-grid", dots, kit.mat("look-grid", (0.10, 0.12, 0.15), roughness=0.8), segments=8)
    return st


def tag(st, text, anchor, screen, *, size=0.040, appear_at=1, follow=None, until=None):
    """kit.label's call shape, drawn as a pill."""
    u, v = screen
    half_u = (len(text) * 0.255 + 0.75) * size * 9 / 16
    if not (0.02 < u - half_u and u + half_u < 0.98 and 0.05 < v < 0.95):
        st.problems.append(f"tag '{text}' leaves the frame: u={u - half_u:.2f}..{u + half_u:.2f} v={v:.2f}")
    return pill(st, text, anchor, screen, start=appear_at / FPS, until=until, size=size, follow=follow)


# ---------------------------------------------------------------------------
# Several camera set-ups inside one beat
# ---------------------------------------------------------------------------

def shoot(shots, *, lens=50.0, fstop=6.3, floor_z=0.0, floor_grid=1.0, gain=1.0, key_side=1.0,
          screen_depth=0.45, bloom=True):
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
        for k in range(5):
            t = k / 4
            frame = round(f0 + (f1 - f0) * t)
            pos = kit._orbit_point(shot["target"],
                                   shot["radius"][0] + (shot["radius"][1] - shot["radius"][0]) * t,
                                   shot["azimuth"][0] + (shot["azimuth"][1] - shot["azimuth"][0]) * t,
                                   shot["height"][0] + (shot["height"][1] - shot["height"][0]) * t)
            cam.location = pos
            cam.keyframe_insert("location", frame=frame)
            aim.location = shot["target"]
            aim.keyframe_insert("location", frame=frame)
            d = screen_depth * (pos - Vector(shot["target"])).length
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
    key = Vector(kit.key_location(mid, target, elevation=38.0, side=key_side, yaw=-10.0, distance=reach))
    key += Vector(target)
    soft_light("key", key, target, 4.6 * gain * reach ** 2, (1.0, 0.80, 0.62), size=reach * 0.6)
    back = Vector(target) + (Vector(target) - Vector(mid)).normalized() * reach * 0.9
    back.z = target[2] + reach * 0.55
    back += Vector((-(mid.y - target[1]), mid.x - target[0], 0)).normalized() * reach * 0.5 * -key_side
    soft_light("rim", back, target, 8.0 * gain * reach ** 2, (0.45, 0.70, 1.0), size=reach * 0.5)
    kit.box("bench", (target[0], target[1], floor_z - 0.05), (160, 160, 0.1),
            kit.mat("look-bench", (0.012, 0.014, 0.018), roughness=0.8), bevel=0)
    if floor_grid:
        n = 26
        dots = [((target[0] + (i - n / 2) * floor_grid, target[1] + (j - n / 2) * floor_grid, floor_z + 0.004),
                 0.03, 0.008) for i in range(n + 1) for j in range(n + 1)]
        kit.cylinders("floor-grid", dots, kit.mat("look-grid", (0.10, 0.12, 0.15), roughness=0.8), segments=8)

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
