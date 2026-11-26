"""Generic beat builder: renders any episode from its storyboard, with no episode-specific Python.

    blender -b -P tools/blender/storyboard_beats.py -- --episode work/jensen-huang
    blender -b -P tools/blender/storyboard_beats.py -- --episode work/jensen-huang --beat riva-chip --force
    blender -b -P tools/blender/storyboard_beats.py -- --episode work/jensen-huang --still 0.3 --still 0.8 --out qc/stills
    blender -b -P tools/blender/storyboard_beats.py -- --catalog out.json     # what the scene code really offers

Inputs, both under the episode folder:
  storyboard.json    {"beats": {name: {scene, params, shots, labels, actions, hud, counter}}}
  shot_lengths.json  {name: seconds}
Optional: word_timing.json {name: [{"word": "...", "start": seconds}]} resolves `word:<text>` times.

Times (`at`, `start`, `until`) are a fraction of the beat when <= 1.0 (and a float), seconds when
larger, or the string `word:<text>`. Validation lives in workflow/storyboard.py; this file trusts it
but still reports (never hides) anything that does not frame.
"""
import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / "models"))

import kit  # noqa: E402
import camera_plan  # noqa: E402
import look  # noqa: E402
import scenes  # noqa: E402
from kit import FPS  # noqa: E402

from workflow import storyboard as timing  # noqa: E402  (kit put the project root on sys.path)

MOUTHS = {}          # mouth_timing.json of the episode: {beat: [{"uid", "speaker", "mode", "visemes"}]}
BEAT = {"name": None}
CLOSE_RADIUS = 4.6


def when(spec, seconds, words, default=None):
    """Resolve a time spec to seconds inside a beat (workflow/storyboard.py), saying so when a
    `word:` mark is missing from the word timing."""
    return timing.when(spec, seconds, words, default, warn=print)


def plan_shots(scene, spec, seconds, words):
    """-> [{"start", "view"|"close", ...}] with a start for every shot, in time order."""
    shots = spec.get("shots")
    if not shots:
        shots = timing.default_shots(list(scene.sequence), list(scene.pins), seconds, spec.get("cut", "travel"))
    return timing.shot_starts(shots, seconds, words, warn=print)


def apply_forced(plan, forced, seconds):
    """Give each (start, anchor) its own close-up shot of ~2.4 s, then return to the view that was
    running; shots that began inside that stretch are dropped."""
    for start, anchor in sorted(forced):
        t0, t1 = max(0.0, start - 0.1), min(seconds, start + 2.3)
        cover = max((s for s in plan if s["start"] <= t1), key=lambda s: s["start"])
        back = {"view": cover.get("view"), "start": t1}
        plan = [s for s in plan if not (t0 < s["start"] <= t1)]
        if t0 <= 0.0:
            plan[0] = {"view": f"at:{anchor}", "start": 0.0}
        else:
            plan.append({"view": f"at:{anchor}", "start": t0})
        if t1 < seconds - 0.8 and not any(t1 < s["start"] < t1 + 0.8 for s in plan):
            plan.append(back)
        plan.sort(key=lambda s: s["start"])
    return plan


def held_box(objects):
    """(centre, (width, height)) of the world bounding box of `objects` and everything parented
    under them that renders; None when there is nothing to hold. An object listed by name that
    never renders (`hold_box`) still counts: it is a frame a scene draws around a region."""
    seen, stack = [], list(objects)
    while stack:
        ob = stack.pop()
        if ob is None or ob in seen:
            continue
        seen.append(ob)
        stack.extend(ob.children)
    pts = [ob.matrix_world @ Vector(c) for ob in seen if ob.type in {"MESH", "FONT", "CURVE"}
           and (not ob.hide_render or ob.get("hold_box")) for c in ob.bound_box]
    if not pts:
        return None
    lo = Vector(map(min, *pts)) if len(pts) > 1 else pts[0]
    hi = Vector(map(max, *pts)) if len(pts) > 1 else pts[0]
    return (lo + hi) / 2, (max(hi.x - lo.x, hi.y - lo.y), hi.z - lo.z)


def view_to_shot(scene, shot, index, previous):
    """Turn a planned shot into the dict `look.shoot` takes.

    A held shot breathes by camera_plan.drift_amount (scaled to its length, locked under 2.5 s, one
    direction for the whole beat, `"move"` in the storyboard picks lock/push/pull/drift); a close-up
    keeps the angle of the shot before; a travel is one eased move with a hold at both ends."""
    move = camera_plan.check_move(shot.get("move"), f"beat '{BEAT['name']}' shot {index + 1}")
    sign = camera_plan.stable_sign(BEAT["name"] or "")
    duration = shot.get("end", shot["start"] + 4.0) - shot["start"]
    name = shot.get("view", "")
    if name.startswith("at:"):
        pin = scene.pins[name[3:]]
        bpy.context.scene.frame_set(max(1, round((shot["start"] + 1.0) * FPS)))
        bpy.context.view_layer.update()
        target = tuple(pin.matrix_world.translation)
        base = previous or next(iter(scene.views.values()))
        # same angle as the shot before (a small constant offset, never a swing); the distance comes
        # from the size of the subject when the pin holds a box, else the stock close-up distance
        radius, azimuth, height = CLOSE_RADIUS, base["azimuth"] + camera_plan.CLOSE_AZIMUTH_OFFSET * sign, target[2] + 2.2
        held = held_box(getattr(scene, "holds", {}).get(name[3:], []))
        if held:
            # a close-up on a sentence, a title or a building holds all of it: centred on it, at the
            # distance where it fills about 80% of the frame, from the same angle as before
            centre, (w, h) = held
            tan_h = 18.0 / scene.lens
            radius = max(2.0, (w / 2) / (tan_h * 0.8), (h / 2) / (tan_h * 9 / 16 * 0.8))
            target, height = tuple(centre), centre[2] + radius * 2.2 / CLOSE_RADIUS
    else:
        v = scene.views[name]
        target, radius, azimuth, height = v["target"], v["radius"], v["azimuth"], v["height"]
    to = shot.get("to")
    if to and to in scene.views:
        # travel: one continuous move from this view to the next; the next shot starts where this lands
        w = scene.views[to]
        az1 = w["azimuth"]
        while az1 - azimuth > 180.0:
            az1 -= 360.0
        while azimuth - az1 > 180.0:
            az1 += 360.0
        entry = {"start": shot["start"], "target": tuple(target), "target_to": tuple(w["target"]),
                 "radius": (radius, w["radius"]), "azimuth": (azimuth, az1),
                 "height": (height, w["height"]), "glide": shot.get("glide")}
        # never faster than one frame width per 7 s: a move too long for its time lands short
        entry, f = camera_plan.govern_travel(entry, duration, scene.lens)
        if f < 1.0:
            print(f"    CAMERA {BEAT['name']}: shot {index + 1} travels {f:.0%} of the way to '{to}' "
                  f"to stay under the pan limit in {duration:.1f}s")
        return entry, {"target": entry["target_to"], "radius": entry["radius"][1],
                       "azimuth": entry["azimuth"][1], "height": entry["height"][1]}
    d_az, factor = camera_plan.drift_amount(duration, move)
    return {"start": shot["start"], "target": tuple(target),
            "radius": (radius, radius * factor),
            "azimuth": (azimuth, azimuth + d_az * sign),
            "height": (height, height)}, {"target": target, "radius": radius, "azimuth": azimuth, "height": height}


def speed_report(entries, bounds, lens):
    """Warnings (kind "camera_speed") for every shot whose pan is faster than one frame width per
    7 s: printed as CAMERA lines and returned as strings for the framing report."""
    out = []
    for k, (entry, (s, e)) in enumerate(zip(entries, bounds)):
        speed = camera_plan.shot_speed(entry, e - s, lens)
        if speed["pan_frames_s"] > camera_plan.MAX_PAN:
            line = (f"camera_speed: shot {k + 1} ({s:.1f}-{e:.1f}s) pans {speed['pan_frames_s']:.2f} frame widths/s "
                    f"({speed['angular_deg_s']:.1f} deg/s), over the {camera_plan.MAX_PAN:.2f} limit (one frame width per 7 s)")
            print(f"    CAMERA {BEAT['name']}: {line}")
            out.append(line)
    return out


def ink(h):
    """Colour options of a HUD entry: {"color": "warm"|"cool"} makes it glow."""
    if h.get("color") == "warm":
        return {"color": look.WARM, "strength": 2.2}
    if h.get("color") == "cool":
        return {"color": look.COOL, "strength": 2.2}
    return {}


def _screen_ray(cam, u, v):
    """World origin and direction of the camera ray through screen point (u, v), v from the top."""
    scene = bpy.context.scene
    tr, br, bl, tl = cam.data.view_frame(scene=scene)
    local = tl + (tr - tl) * u + (bl - tl) * v
    origin = cam.matrix_world.translation.copy()
    return origin, (cam.matrix_world @ local - origin).normalized()


def _ground_surface(origin, direction, fallback):
    """First surface the ray meets, skipping other cast members: (point, normal, object name).
    Nothing hit gives (a point `fallback` along the ray, None, None)."""
    scene = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    start = origin
    for _ in range(6):
        hit, loc, normal, _i, ob, _m = scene.ray_cast(dg, start, direction, distance=500.0)
        if not hit:
            break
        if not ob.name.startswith("cast-") and not ob.name.startswith("hud"):
            return loc, normal, ob.name
        start = loc + direction * 0.001
    return origin + direction * fallback, None, None


def _occluder(origin, direction, dist):
    """Name of the first set object the ray meets before `dist` (cast members do not count), or None."""
    scene = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    start, left = origin, dist
    for _ in range(6):
        hit, loc, _n, _i, ob, _m = scene.ray_cast(dg, start, direction, distance=left)
        if not hit:
            return None
        if not ob.name.startswith("cast-") and not ob.name.startswith("hud"):
            return ob.name
        step = (loc - start).length + 0.001
        start = loc + direction * 0.001
        left -= step
        if left <= 0:
            return None
    return None


def _floor_point(origin, direction):
    """Where the ray meets the floor plane z = 0, or None when it does not point down at it."""
    if direction.z > -1e-6 or origin.z <= 0:
        return None
    return origin + direction * (-origin.z / direction.z)


def _ground(origin, direction, fallback):
    """First surface the ray meets, skipping other cast members; else a point `fallback` along it."""
    return _ground_surface(origin, direction, fallback)[0]


def _first_hit(origin, direction):
    """Where the ray first meets a set object (cast members do not count), or None."""
    scene = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    start = origin
    for _ in range(6):
        hit, loc, _n, _i, ob, _m = scene.ray_cast(dg, start, direction)
        if not hit:
            return None
        if not ob.name.startswith("cast-") and not ob.name.startswith("hud"):
            return loc
        start = loc + direction * 0.001
    return None


def _floor_at(origin, direction, z0):
    """Where the ray meets the set's floor at height z0, or None when it does not point down at it."""
    if direction.z > -1e-6:
        return None
    return origin + direction * ((z0 - origin.z) / direction.z)


def place_cast(st, scene_set, plan, spec, seconds, words):
    """Sprites from the storyboard's `cast`: each stands where its screen point meets the set, as
    tall as `height` of the frame, facing the camera, shown only during its shot."""
    import characters
    cam = bpy.context.scene.camera
    bounds = [(s["start"], plan[i + 1]["start"] if i + 1 < len(plan) else seconds) for i, s in enumerate(plan)]
    import people as _people
    PLACED.clear()
    for n, c in enumerate(spec.get("cast", [])):
        if c.get("render") == "3d":
            place_human3d(st, scene_set, plan, spec, seconds, words, n, c, bounds)
            continue
        if c["who"] in _people.CHARACTERS:
            place_actor(st, scene_set, plan, spec, seconds, words, n, c, bounds)
            continue
        k = min(int(c.get("shot", 0)), len(bounds) - 1)
        t0, t1 = bounds[k]
        f0, f1 = max(1, round(t0 * FPS) + 1), max(2, round(t1 * FPS))
        bpy.context.scene.frame_set(min(f0 + 1, max(1, f1 - 1)))
        bpy.context.view_layer.update()
        u, v = c["screen"]
        origin, ray = _screen_ray(cam, u, v)
        target = Vector(scene_set.views[plan[k]["view"]]["target"]) if plan[k].get("view") in scene_set.views else origin + ray * 8
        reach = (target - origin).length
        # a hair in front of whatever it stands on, so a wall or a screen does not swallow half of it
        foot = _ground(origin, ray, reach * 0.8) - ray * (0.03 * reach)
        depth = (foot - origin).dot(cam.matrix_world.to_quaternion() @ Vector((0, 0, -1)))
        frame_h = 2 * depth * math.tan(cam.data.angle_y / 2)
        rows = characters.sprite_rows(c["who"], c.get("word", "cat"))
        px = c.get("height", 0.25) * frame_h / (len(rows) + 2)
        to_cam = origin - foot
        yaw = math.atan2(to_cam.x, -to_cam.y)
        ob = characters.billboard(f"cast-{n}-{c['who']}", c["who"], tuple(foot), px, facing=yaw, word=c.get("word", "cat"))
        if c.get("flip"):
            ob.scale[0] *= -1
        base = ob.location.copy()
        if c.get("walk"):
            du, dv = c["walk"]
            o2, r2 = _screen_ray(cam, u + du, v + dv)
            end = _ground(o2, r2, reach * 0.8) - r2 * (0.03 * reach) + (base - foot)
            ob.location = base
            ob.keyframe_insert("location", frame=f0)
            ob.location = end
            ob.keyframe_insert("location", frame=f1)
        elif c.get("hop"):
            lift = (len(rows) + 2) * px * 0.06
            step = max(6, int(FPS * 0.42))
            for fr in range(f0, f1 + 1, step):
                ob.location = base
                ob.keyframe_insert("location", frame=fr)
                ob.location = base + Vector((0, 0, lift))
                ob.keyframe_insert("location", frame=min(f1, fr + step // 2))
            ob.location = base
        ob.hide_render = True
        ob.keyframe_insert("hide_render", frame=1)
        ob.hide_render = False
        ob.keyframe_insert("hide_render", frame=f0)
        if f1 < round(seconds * FPS):
            ob.hide_render = True
            ob.keyframe_insert("hide_render", frame=f1 + 1)
        ob.hide_render = False
    apply_gaze()


PLACED = []   # the 3D people of this beat as place_human3d left them, for the gaze pass


def apply_gaze():
    """Turn each 3D person's head to what it looks at: `look` on its cast entry ("camera", the index of
    another cast member, or a point [x, y, z]); by default a listener looks at whoever speaks in the shot
    and a speaker at the camera when it is the narrator. Heads turn, bodies keep their facing."""
    import human3d
    by_n = {p["n"]: p for p in PLACED}
    speakers = [p for p in PLACED if p["c"].get("speaker")]
    for p in PLACED:
        c = p["c"]
        look = c.get("look")
        if look is None:
            if c.get("speaker") == "narrator" or c.get("pose") == "walk":
                continue
            other = next((q for q in speakers if q is not p and q["c"].get("shot", 0) == c.get("shot", 0)), None)
            if other is None:
                continue
            look = other["n"]
        if look == "camera":
            target = p["cam"]
        elif isinstance(look, int) and look in by_n:
            q = by_n[look]
            target = q["foot"] + Vector((0, 0, q["stature"] * 0.93))
        elif isinstance(look, list) and len(look) == 3:
            target = Vector(look)
        else:
            continue
        eye = p["foot"] + Vector((0, 0, p["stature"] * 0.93))
        d = target - eye
        want = math.atan2(d.x, -d.y)
        yaw = (want - p["yaw"] + math.pi) % (2 * math.pi) - math.pi
        pitch = math.atan2(-d.z, max(0.05, Vector((d.x, d.y)).length))
        human3d.gaze(p["inst"], yaw, pitch)
        print(f"HUMAN3D_GAZE {p['n']} {c['who']} -> {look} yaw={math.degrees(yaw):.0f} pitch={math.degrees(pitch):.0f}",
              flush=True)


def place_actor(st, scene_set, plan, spec, seconds, words, n, c, bounds):
    """A person from tools/pixel/people.py: placed like a sprite (where its screen point meets the
    set, `height` of the frame), then acting: pose and face, `acts` changes at given times, blinks,
    and a mouth that follows its speaker's lines in this beat (mouth_timing.json). A bust (a
    close-up of head and shoulders) stands in front of the set rather than on it."""
    import characters
    cam = bpy.context.scene.camera
    if "span" in c:
        t0 = when(c["span"][0], seconds, words, default=0.0)
        t1 = when(c["span"][1], seconds, words, default=seconds)
        k = max(i for i, (a, _) in enumerate(bounds) if a <= t0 + 1e-6)
    else:
        k = min(int(c.get("shot", 0)), len(bounds) - 1)
        t0, t1 = bounds[k]
    f0, f1 = max(1, round(t0 * FPS) + 1), max(2, round(t1 * FPS))
    bpy.context.scene.frame_set(min(f0 + 1, max(1, f1 - 1)))
    bpy.context.view_layer.update()
    u, v = c["screen"]
    origin, ray = _screen_ray(cam, u, v)
    target = Vector(scene_set.views[plan[k]["view"]]["target"]) if plan[k].get("view") in scene_set.views else origin + ray * 8
    reach = (target - origin).length
    standing = not c.get("bust") and c.get("size", "figure") == "figure"
    if c.get("bust") or c.get("size") == "hands":
        foot = origin + ray * reach * float(c.get("depth", 0.5))
    else:
        hit, normal, surface = _ground_surface(origin, ray, reach * 0.8)
        if standing:
            # a standing figure stands on the floor plane (z = 0) where its screen point's ray reaches it;
            # a wall or door the ray meets first would otherwise hold the figure up in mid-air
            floor = _floor_point(origin, ray)
            if floor is None:
                st.problems.append(f"cast '{c['who']}' at screen {c['screen']} points above the horizon: "
                                   f"move its 'screen' v toward 1.0 (the bottom of the frame)")
                hit = origin + ray * (reach * 0.8)
            else:
                blocker = _occluder(origin, ray, (floor - origin).length - 0.15)
                if blocker:
                    st.problems.append(f"cast '{c['who']}' at screen {c['screen']} stands behind {blocker}, "
                                       f"hidden from the camera: move its 'screen' u or v")
                hit, normal, surface = floor, Vector((0, 0, 1)), "the floor"
        foot = hit - ray * (0.03 * reach)
        # a bed or any other surface: its screen point must land on an upward-facing top, or it floats
        if normal is None or normal.z < 0.8:
            st.problems.append(f"cast '{c['who']}' at screen {c['screen']} stands on {surface or 'nothing'}, "
                               f"not on a surface: move its 'screen' v toward 1.0 (the bottom of the frame)")
    depth = (foot - origin).dot(cam.matrix_world.to_quaternion() @ Vector((0, 0, -1)))
    frame_h = 2 * depth * math.tan(cam.data.angle_y / 2)
    # `size`: figure (default), bust, or any size the character is drawn at (bed, hands)
    size = c.get("size") or ("bust" if c.get("bust") else "figure")
    ob = characters.actor(f"cast-{n}-{c['who']}", c["who"], tuple(foot), c.get("height", 0.25) * frame_h,
                          size=size, pose=c.get("pose", "stand"), expression=c.get("face", "neutral"),
                          tint=getattr(scene_set, "sprite_tint", 1.0), shadow=size == "figure")
    characters.key_cell(ob, 1, pose=c.get("pose", "stand"), expression=c.get("face", "neutral"))
    for a in c.get("acts") or []:
        characters.key_cell(ob, max(1, round(when(a["at"], seconds, words, default=0.0) * FPS) + 1),
                            pose=a.get("pose"), expression=a.get("face"))
    if c.get("walk"):
        du, dv = c["walk"]
        o2, r2 = _screen_ray(cam, u + du, v + dv)
        end = _ground(o2, r2, reach * 0.8) - r2 * (0.03 * reach)
        characters.walk(ob, [tuple(foot), tuple(end)], f0, f1)
    if c.get("blink", True):
        characters.blinks(ob, round(seconds * FPS), n * 31 + len(BEAT["name"] or ""))
    who = c.get("speaker")
    if who:
        for line in MOUTHS.get(BEAT["name"], []):
            if line["speaker"] == who and line["mode"] == "say":
                characters.talk(ob, line["visemes"], round(seconds * FPS), t_from=t0, t_to=t1)
    if c.get("flip"):
        ob.scale[0] *= -1
    ob.hide_render = True
    ob.keyframe_insert("hide_render", frame=1)
    ob.hide_render = False
    ob.keyframe_insert("hide_render", frame=f0)
    if f1 < round(seconds * FPS):
        ob.hide_render = True
        ob.keyframe_insert("hide_render", frame=f1 + 1)
    ob.hide_render = False
    shadow = bpy.data.objects.get(ob.get("shadow", ""))
    if shadow:
        for fr, hide in ((1, True), (f0, False)) + (((f1 + 1, True),) if f1 < round(seconds * FPS) else ()):
            shadow.hide_render = hide
            shadow.keyframe_insert("hide_render", frame=fr)


# the CharMorph base character is 1.833 m tall (the rig's own height before any scale)
HUMAN3D_BASE_HEIGHT = 1.833
HUMAN3D = {"dir": None}   # set by main(): <episode>/human3d, where the built characters are


from bpy_extras.object_utils import world_to_camera_view  # noqa: E402


def place_human3d(st, scene_set, plan, spec, seconds, words, n, c, bounds):
    """A rigged 3D person (models/human3d.py), placed like place_actor: where its screen point meets the set,
    `height` of the frame tall, facing the camera, shown in its shot. It is posed from the library, walks from
    `walk` (a screen offset), speaks with its speaker's mouth shapes, and takes its `face`. A bust is a
    figure whose head sits at the screen point and whose body runs off the bottom of the frame."""
    import human3d
    cam = bpy.context.scene.camera
    if "span" in c:
        t0 = when(c["span"][0], seconds, words, default=0.0)
        t1 = when(c["span"][1], seconds, words, default=seconds)
        k = max(i for i, (a, _) in enumerate(bounds) if a <= t0 + 1e-6)
    else:
        k = min(int(c.get("shot", 0)), len(bounds) - 1)
        t0, t1 = bounds[k]
    f0, f1 = max(1, round(t0 * FPS) + 1), max(2, round(t1 * FPS))
    u, v0 = c["screen"]
    bust = bool(c.get("bust")) or c.get("size") == "bust"
    height = float(c.get("height", 0.25))
    inst = human3d.instance(c["who"], HUMAN3D["dir"], f"cast-{n}-{c['who']}", bpy.context.scene.collection,
                            variant=c.get("variant"))
    rig = inst["rig"]
    # people keep their real size (a small per-cast-member variation aside): the camera depth where a figure
    # of that stature fills `height` of the frame decides where it stands, never a scale factor
    scale = human3d.size_jitter(n)
    stature = human3d.stature(inst) * scale
    z0 = getattr(scene_set, "floor_z", 0.0)

    def solve(frame):
        """(foot, camera origin, depth, problem) for the camera as it is at `frame`."""
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        k = 2 * math.tan(cam.data.angle_y / 2)
        fwd = cam.matrix_world.to_quaternion() @ Vector((0, 0, -1))
        origin, ray = _screen_ray(cam, u, v0)

        def cam_depth(p):
            return (p - origin).dot(fwd)

        if bust:
            # head at the screen point, the body hanging below it out of the frame; never inside the set
            want = max(0.6, stature / (1.8 * height * k))
            hloc = _first_hit(origin, ray)
            if hloc is not None and cam_depth(hloc) - 0.35 < want:
                want = max(0.6, cam_depth(hloc) - 0.35)
            head = origin + ray * (want / max(ray.dot(fwd), 1e-3))
            foot = head - Vector((0, 0, stature * 0.94))
            if foot.z > z0 + 0.02:
                foot.z = z0   # stand on the floor rather than float (the head sinks a little in the frame)
            return foot, origin, cam_depth(foot), None
        floor = _floor_at(origin, ray, z0)
        if floor is None:
            return (origin + ray * 6.0, origin, 6.0,
                    f"cast '{c['who']}' at screen {c['screen']} points above the horizon: "
                    f"move its 'screen' v toward 1.0 (the bottom of the frame)")
        want = max(1.2, stature / (height * k))
        if cam_depth(floor) > want:
            # too far to be `height` tall: walk the feet toward the camera, below the frame edge if need be,
            # while the head stays in the upper half of the frame (a high camera looks down on anyone near it)
            def foot_at(vv):
                o2, r2 = _screen_ray(cam, u, vv)
                return _floor_at(o2, r2, z0)

            def ok(vv):
                f2 = foot_at(vv)
                if f2 is None or cam_depth(f2) < want:
                    return False
                top = world_to_camera_view(bpy.context.scene, cam, f2 + Vector((0, 0, stature)))
                return (1.0 - top.y) <= 0.45
            lo, hi = v0, 4.0
            if ok(lo):
                for _ in range(40):
                    mid = (lo + hi) / 2
                    if ok(mid):
                        lo = mid
                    else:
                        hi = mid
                floor = foot_at(lo) or floor
        chest = floor + Vector((0, 0, min(1.3, stature * 0.7)))
        blocker = _occluder(origin, (chest - origin).normalized(), (chest - origin).length - 0.3)
        problem = (f"cast '{c['who']}' at screen {c['screen']} stands behind {blocker}, hidden from the camera: "
                   f"move its 'screen' u or v") if blocker else None
        return floor, origin, cam_depth(floor), problem

    # a camera that dollies in should arrive at the framing the storyboard asks for, so the people are placed
    # against the camera of the shot's last frame; where that hides them, against its first frame
    frames = [max(f0 + 1, f1 - 1), min(f0 + 1, max(1, f1 - 1))]
    if c.get("place") == "start":
        frames.reverse()
    if c.get("at"):
        # a set point chosen by the storyboard (behind a desk, at a board): stand there, whatever the screen
        frame = frames[0]
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        origin = cam.matrix_world.translation.copy()
        foot = Vector((float(c["at"][0]), float(c["at"][1]), z0))
        depth = (foot - origin).dot(cam.matrix_world.to_quaternion() @ Vector((0, 0, -1)))
        problem = None
    else:
        for frame in frames:
            foot, origin, depth, problem = solve(frame)
            if problem is None:
                break
    if problem:
        st.problems.append(problem)
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()
    rig.scale = (scale, scale, scale)
    rig.rotation_mode = "XYZ"
    to_cam = origin - foot
    yaw = math.atan2(to_cam.x, -to_cam.y)
    if c.get("facing") is not None:
        yaw = math.radians(float(c["facing"]))
    rig.rotation_euler = (0.0, 0.0, yaw)
    PLACED.append({"n": n, "c": c, "inst": inst, "foot": foot.copy(), "yaw": yaw, "stature": stature,
                   "cam": origin.copy()})
    rig.location = tuple(foot)
    rig.keyframe_insert("location", frame=1)
    print(f"HUMAN3D_PLACE {n} {c['who']} screen={c['screen']} bust={bust} foot={tuple(round(x, 3) for x in foot)} "
          f"scale={scale:.3f} depth={depth:.2f} pose={c.get('pose')}", flush=True)

    if c.get("walk"):
        du, dv = c["walk"]
        # the walk is the screen offset's step on the floor, taken from wherever the feet ended up
        a = _floor_at(*_screen_ray(cam, u, v0), z0)
        b = _floor_at(*_screen_ray(cam, u + du, v0 + dv), z0)
        end = foot + (b - a) if (a is not None and b is not None and not bust) else foot
        rig.location = tuple(foot)
        rig.keyframe_insert("location", frame=f0)
        rig.location = tuple(end)
        rig.keyframe_insert("location", frame=f1)
        if rig.animation_data and rig.animation_data.action:
            for fc in rig.animation_data.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"

    human3d.set_pose(inst, c.get("pose", "stand"), 1)
    human3d.set_pose(inst, c.get("pose", "stand"), f0)
    if c.get("pose") == "walk":
        human3d.play_walk(inst, f0)
    human3d.set_face(inst, c.get("face", "neutral"), f0)
    for a in c.get("acts") or []:
        fa = max(1, round(when(a["at"], seconds, words, default=0.0) * FPS) + 1)
        if "pose" in a:
            human3d.set_pose(inst, a["pose"], fa)
        if "face" in a:
            human3d.set_face(inst, a["face"], fa)
    who = c.get("speaker")
    person_seed = n * 31 + sum(map(ord, BEAT["name"] or ""))
    spans = []
    if who:
        for line in MOUTHS.get(BEAT["name"], []):
            if line["speaker"] == who and line["mode"] == "say":
                human3d.talk(inst, line["visemes"], FPS, seed=n)
                spoken = [v for v in line["visemes"] if v[0] not in ("rest", "closed")]
                if spoken:
                    spans.append((max(t0, spoken[0][1]), min(t1, spoken[-1][2])))
        # the arms move with the words, unless the person walks or holds a pose the storyboard set
        if c.get("gesture", True) and c.get("pose", "stand") in ("stand", "talk") and not c.get("acts"):
            human3d.gestures(inst, [s for s in spans if s[1] - s[0] > 0.8], FPS, c.get("pose", "stand"),
                             person_seed)
    # life: breathing, a weight shift, a wandering head, a face that is never still, and blinks, all
    # out of step with the others
    if c.get("idle", True):
        human3d.idle(inst, person_seed, FPS, walking=c.get("pose") == "walk")
        human3d.face_idle(inst, person_seed, FPS)
        if spans and c.get("pose") != "walk":
            human3d.arm_idle(inst, person_seed, FPS)
    if c.get("blink", True):
        human3d.blinks(inst, round(seconds * FPS), person_seed, FPS)
    human3d.show(inst, f0, f1, round(seconds * FPS))


def drop_set_extras(st):
    """Remove the pixel people the scene builder put in its set (guards, queues, walkers, students).

    A beat with "extras": "none" shows only its own cast, so a 3D film never mixes in a 2D sprite. The
    removed figures and their shadow blots leave the scene before the cast is placed."""
    import characters
    gone = []
    for ob in list(characters.ACTORS):
        if ob.name not in bpy.data.objects:
            continue
        shadow = bpy.data.objects.get(ob.get("shadow", ""))
        if shadow is not None:
            bpy.data.objects.remove(shadow, do_unlink=True)
        gone.append(ob.name)
        bpy.data.objects.remove(ob, do_unlink=True)
    characters.ACTORS.clear()
    if gone:
        print(f"EXTRAS_DROPPED {len(gone)} {', '.join(gone)}", flush=True)


def build_beat(name, spec, seconds, words, forced=()):
    """forced: [(start_seconds, anchor)] — the shot running then becomes a close-up on that anchor."""
    import characters
    import human3d
    BEAT["name"] = name
    human3d.reset()   # each beat starts a new scene; the cached templates belonged to the last one
    characters.ACTORS.clear()
    characters.EVENTS.clear()
    frames = look.open_set(seconds)
    scene = scenes.SCENES[spec["scene"]](spec.get("params") or {}, seconds)
    plan = plan_shots(scene, spec, seconds, words)
    plan = apply_forced(plan, forced, seconds)
    for i, shot in enumerate(plan):
        shot["end"] = plan[i + 1]["start"] if i + 1 < len(plan) else seconds
    shots, previous = [], None
    for i, shot in enumerate(plan):
        entry, previous = view_to_shot(scene, shot, i, previous)
        shots.append(entry)
    st = look.shoot(shots, lens=scene.lens, floor_z=scene.floor_z, floor_grid=scene.floor_grid, gain=scene.gain,
                    lighting=getattr(scene, "lighting", "studio"))
    st.offscreen = []

    overrides = {a["name"]: a for a in spec.get("actions", [])}
    for action, (fn, at, span) in scene.actions.items():
        t0 = when(overrides.get(action, {}).get("at"), seconds, words, default=at * seconds)
        t0 = max(0.0, min(t0, seconds - span))
        fn(t0, t0 + span)
    if spec.get("extras", "pixel") == "none":
        drop_set_extras(st)
    place_cast(st, scene, plan, spec, seconds, words)
    characters.finish_actors(st.cam)

    bounds = [(s["start"], plan[i + 1]["start"] if i + 1 < len(plan) else seconds) for i, s in enumerate(plan)]
    for label in spec.get("labels", []):
        start = when(label.get("at"), seconds, words, default=0.3 * seconds)
        end = next((e for s, e in bounds if s <= start < e), seconds)
        until = when(label.get("until"), seconds, words, default=end if end < seconds else None)
        pin = scene.pins.get(label["anchor"])
        if pin is None:
            st.problems.append(f"label '{label['text']}': scene '{spec['scene']}' has no anchor '{label['anchor']}'")
            continue
        if look.auto_tag(st, label["text"], pin, start=start, until=until) is None and "off screen" in st.problems[-1]:
            st.offscreen.append((start, label["anchor"]))

    for h in spec.get("hud", []):
        look.hud_text(st, h["text"], tuple(h["screen"]), size=h.get("size", 0.05),
                      start=when(h.get("at"), seconds, words, default=0.0),
                      until=when(h.get("until"), seconds, words, default=None), **ink(h))
        look.reserve(st, (h["screen"][0] - 0.18, h["screen"][1] - 0.06, h["screen"][0] + 0.18, h["screen"][1] + 0.06),
                     1, frames)
    c = spec.get("counter")
    if c:
        t0 = when(c.get("start"), seconds, words, default=0.0)
        t1 = when(c.get("end"), seconds, words, default=seconds)
        text = look.hud_text(st, c["template"].format(int(c["from"])), tuple(c["screen"]),
                             size=c.get("size", 0.07), start=t0, **ink(c))
        if c.get("curve") == "exp":
            value = lambda t: c["from"] * (c["to"] / c["from"]) ** t
        else:
            value = lambda t: c["from"] + (c["to"] - c["from"]) * t * t * (3 - 2 * t)
        look.counter(text, t0, t1, value, c["template"])
        look.reserve(st, (c["screen"][0] - 0.2, c["screen"][1] - 0.07, c["screen"][0] + 0.2, c["screen"][1] + 0.07),
                     1, frames)
    st.problems += cut_text(st, bounds, ["to" in s for s in plan])
    st.problems += speed_report(shots, bounds, scene.lens)
    st.scene_set = scene
    return st


def camera_signature(st):
    """The camera's position and aim at every 10th frame, rounded: equal signatures, equal shots."""
    scene = bpy.context.scene
    out = []
    for frame in range(1, st.frames + 1, 10):
        scene.frame_set(frame)
        m = st.cam.matrix_world
        out.append([round(v, 3) for v in (*m.translation, *m.to_euler())])
    scene.frame_set(1)
    return out


def cut_text(st, bounds, travels=None, margin=0.005):
    """Text the frame edge cuts through, shot by shot: a text object some of whose corners are on
    screen and some off. A word wholly off screen is not shown and is fine; half a title is what a
    viewer reads as a mistake ("Why does my c"). A held shot is read at its middle; a camera move
    at three points, and only text cut at two of them counts (a move passes over things). Text a
    scene marks `cut_ok` (typed answer pieces, tokens in a row, decoration) is not read."""
    from bpy_extras.object_utils import world_to_camera_view
    scene = bpy.context.scene
    texts = [ob for ob in scene.objects if ob.type == "FONT" and not ob.get("cut_ok")]
    travels = travels or [False] * len(bounds)
    problems = []

    def cut_at(frame):
        scene.frame_set(max(1, frame))
        bpy.context.view_layer.update()
        found = set()
        for ob in texts:
            if ob.hide_render or not ob.data.body.strip():
                continue
            seen = [world_to_camera_view(scene, st.cam, ob.matrix_world @ Vector(c)) for c in ob.bound_box]
            if any(p.z <= 0 for p in seen):
                continue
            inside = [margin <= p.x <= 1 - margin and margin <= p.y <= 1 - margin for p in seen]
            if any(inside) and not all(inside):
                found.add(ob.data.body.strip())
        return found

    for k, ((s, e), moving) in enumerate(zip(bounds, travels)):
        if moving:
            seen = [cut_at(round((s + (e - s) * q) * FPS)) for q in (0.25, 0.5, 0.75)]
            cut = sorted(t for t in set().union(*seen) if sum(t in x for x in seen) >= 2)
        else:
            cut = sorted(cut_at(round((s + e) / 2 * FPS)))
        if cut:
            shown = ", ".join(f"'{t[:24]}'" for t in cut[:3]) + (f" and {len(cut) - 3} more" if len(cut) > 3 else "")
            problems.append(f"shot {k + 1} ({s:.1f}-{e:.1f}s): the frame edge cuts through text {shown}")
    scene.frame_set(1)
    return problems


def build_beat_framed(name, spec, seconds, words):
    """Build a beat; where a label's anchor is off screen in its shot, cut to a close-up on it
    and build again (twice at most). Whatever still fails is left in `st.problems`."""
    forced = []
    for _ in range(3):
        st = build_beat(name, spec, seconds, words, forced)
        fresh = [f for f in st.offscreen if f not in forced]
        if not fresh:
            return st
        forced += fresh
    return st


def dump_catalog(path):
    """Build every scene with default parameters and write what it offers: the ground truth the
    data catalog (workflow/scenes.json) is compared with."""
    catalog_path = PROJECT_ROOT / "workflow" / "scenes.json"
    declared = json.loads(catalog_path.read_text(encoding="utf-8"))["scenes"] if catalog_path.exists() else {}
    out = {}
    for name, fn in scenes.SCENES.items():
        found = {"views": [], "anchors": set(), "actions": set()}
        for params in declared.get(name, {}).get("examples") or [{}]:
            look.open_set(6)
            s = fn(dict(params), 6)
            found["views"] += [v for v in s.views if v not in found["views"]]
            found["anchors"] |= set(s.pins)
            found["actions"] |= set(s.actions)
        out[name] = {"views": found["views"], "anchors": sorted(found["anchors"]), "actions": sorted(found["actions"])}
    Path(path).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"catalog of {len(out)} scenes -> {path}")


def configure_video(scene, out_path):
    scene.eevee.taa_render_samples = 24
    if os.environ.get("SEMMELWEIS_720"):
        # the 2-minute 3D test renders at 720p; the episode itself stays at its own resolution
        scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = 1280, 720, 100
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    scene.render.ffmpeg.audio_codec = "NONE"
    scene.render.filepath = str(out_path)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", type=Path)
    ap.add_argument("--catalog", type=Path, help="write the scene catalog the code offers and exit")
    ap.add_argument("--beat", action="append")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--still", type=float, action="append")
    ap.add_argument("--check", action="store_true", help="build each beat and write its framing report, render nothing")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)

    if args.catalog:
        dump_catalog(args.catalog)
        return
    episode = args.episode if args.episode.is_absolute() else PROJECT_ROOT / args.episode
    HUMAN3D["dir"] = episode / "human3d"
    board = json.loads((episode / "storyboard.json").read_text(encoding="utf-8"))["beats"]
    lengths = json.loads((episode / "shot_lengths.json").read_text(encoding="utf-8"))
    timing_path = episode / "word_timing.json"
    timing = json.loads(timing_path.read_text(encoding="utf-8")) if timing_path.exists() else {}
    mouth_path = episode / "mouth_timing.json"
    MOUTHS.update(json.loads(mouth_path.read_text(encoding="utf-8")) if mouth_path.exists() else {})
    cast_path = episode / "script" / "cast.json"
    cast = json.loads(cast_path.read_text(encoding="utf-8")) if cast_path.exists() else None

    sys.path.insert(0, str(PROJECT_ROOT))
    from workflow import storyboard as validator
    advice = []
    refused = validator.validate({"beats": board}, validator.load_catalog(), lengths, cast=cast, warnings=advice)
    for line in advice:
        print(f"    ADVICE {line}")
    if refused:
        raise SystemExit("storyboard refused before any scene was built:\n  " + ("\n  ").join(refused))

    names = args.beat or [n for n in board if n in lengths]
    unknown = [n for n in names if n not in board]
    if unknown:
        raise SystemExit(f"not in storyboard: {', '.join(unknown)}")
    out_dir = args.out or (episode / "renders" / "3d")
    if not out_dir.is_absolute():
        out_dir = PROJECT_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    for idx, name in enumerate(names):
        seconds = lengths[name]
        t0 = time.time()
        if args.still:
            st = build_beat_framed(name, board[name], seconds, timing.get(name, []))
            bpy.context.scene.render.resolution_percentage = 50
            if os.environ.get("STORYLOOM_CYCLES_STILLS"):
                # a machine without a GPU (the cloud checks): Cycles on the CPU, a few samples, denoised
                sc = bpy.context.scene
                sc.render.engine = "CYCLES"
                sc.cycles.device = "CPU"
                sc.cycles.samples = int(os.environ["STORYLOOM_CYCLES_STILLS"])
                sc.cycles.use_denoising = True
            for frac in args.still:
                frame = max(1, round(frac * seconds * FPS))
                kit.common.render_still(frame, out_dir / f"{name}-{round(frac * 100):03d}.png", samples=16)
            for line in st.problems:
                print(f"    FRAMING {name}: {line}")
            print(f"  [{idx + 1}/{len(names)}] {name} stills in {time.time() - t0:.1f}s")
            continue
        if args.check:
            st = build_beat_framed(name, board[name], seconds, timing.get(name, []))
            (out_dir / f"{name}.framing.json").write_text(json.dumps(st.problems, indent=0), encoding="utf-8")
            # what the camera does, so a code change can be checked for which renders it makes stale
            (out_dir / f"{name}.camera.json").write_text(json.dumps(camera_signature(st)), encoding="utf-8")
            for line in st.problems:
                print(f"    FRAMING {name}: {line}")
            print(f"  [{idx + 1}/{len(names)}] {name} checked in {time.time() - t0:.1f}s")
            continue
        out_path = out_dir / f"{name}.mp4"
        if out_path.exists() and out_path.stat().st_size > 0 and not args.force:
            print(f"  [{idx + 1}/{len(names)}] {name} already rendered, skipping")
            continue
        print(f"  [{idx + 1}/{len(names)}] {name} ({seconds}s = {seconds * FPS} frames)...")
        st = build_beat_framed(name, board[name], seconds, timing.get(name, []))
        for line in st.problems:
            print(f"    FRAMING {name}: {line}")
        # beside the render, so QC can report it without re-building the scene
        (out_dir / f"{name}.framing.json").write_text(json.dumps(st.problems, indent=0), encoding="utf-8")
        configure_video(bpy.context.scene, out_path)
        bpy.ops.render.render(animation=True)
        print(f"    done in {time.time() - t0:.1f}s")
    print(f"{len(names)} beats -> {out_dir}")


if __name__ == "__main__":
    main()
