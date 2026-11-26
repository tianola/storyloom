"""Rigged 3D people for the storyboard renderer.

Each person is a dressed MPFB2 (MakeHuman) character built by tools/blender/human3d_mpfb.py, in several
variants per role (work/<episode>/human3d/<who>.blend, <who>.2.blend, ...); the older CharMorph builds of
human3d_build.py and human3d_poses.py follow the same contract. A cast entry with "render": "3d" uses this module instead of the 2D
sprites in characters.py:

  load_template(who, built_dir)  append the character once per Blender run (hidden)
  instance(who, built_dir, name) copy it (rig, body, garments, hair), so every cast member has its own pose
  set_pose(inst, pose, frame)     FK pose from the library (stand, sit, kneel), keyed at a frame
  play_walk(inst, start_frame)    the baked walk clip, as an NLA strip from a frame
  set_face(inst, face, frame)     expression shape keys
  talk(inst, visemes, fps)        mouth shapes from mouth_timing.json, keyed in beat time
  show(inst, f0, f1, total)       visible only while the cast member is in its shot

Nothing here knows the camera: storyboard_beats.place_human3d decides the foot point and the height.
"""
import json
from pathlib import Path

import bpy

# mouth_timing.json shapes -> expression shape keys (CharMorph's 83 expression keys, male and female alike)
MOUTH = {
    "rest": (None, 0.0),
    "closed": ("Exp_mouthClosed_max", 1.0),
    "half": ("Exp_mouthOpenHalf_max", 1.0),
    "open": ("Exp_mouthOpen_max", 1.0),
    "wide": ("Exp_mouthOpenLarge_max", 0.8),
}
FACE = {
    "neutral": {},
    "worried": {"Exp_browSqueezeL_max": 0.5, "Exp_browSqueezeR_max": 0.5, "Exp_browsMidVert_max": 0.3},
    "sad": {"Exp_browsMidVert_max": 0.6, "Exp_mouthSmile_min": 0.4},
    "shocked": {"Exp_browOutVertL_max": 0.7, "Exp_browOutVertR_max": 0.7, "Exp_mouthOpenO_max": 0.6},
    "angry": {"Exp_browSqueezeL_max": 0.9, "Exp_browSqueezeR_max": 0.9},
    "smile": {"Exp_mouthSmile_max": 0.8},
}
ALL_FACE_KEYS = sorted({k for face in FACE.values() for k in face} | {v[0] for v in MOUTH.values() if v[0]})
IK_SWITCHES = ["upper_arm_parent.L", "upper_arm_parent.R", "thigh_parent.L", "thigh_parent.R"]

TEMPLATES = {}
USED = {}   # role -> how many cast members of that role this beat has placed, to hand out the variants in turn


def reset():
    """A new beat: forget the templates (they belonged to the last scene) and start the variants again."""
    TEMPLATES.clear()
    USED.clear()


def variants(who, built_dir):
    """The built files of a role: <who>.blend, then <who>.2.blend, <who>.3.blend ... (human3d_mpfb.py)."""
    d = Path(built_dir)
    out = [who] if (d / f"{who}.blend").exists() else []
    k = 2
    while (d / f"{who}.{k}.blend").exists():
        out.append(f"{who}.{k}")
        k += 1
    return out or [who]


def pick_variant(who, built_dir, variant=None):
    """`variant` (1-based) when the storyboard names one, otherwise the next one in turn for this beat; the
    first cast member of a role is always variant 1, so a named person looks the same in every beat."""
    names = variants(who, built_dir)
    if variant:
        return names[(int(variant) - 1) % len(names)]
    n = USED.get(who, 0)
    USED[who] = n + 1
    return names[n % len(names)]


def _rig_of(objects):
    return next(o for o in objects if o.type == "ARMATURE" and o.data.get("rig_id"))


def _body_of(objects):
    return next(o for o in objects if o.type == "MESH" and o.name.startswith("mb_") and o.data.shape_keys)


def load_template(who, built_dir):
    """Append the built character once per Blender run. The template stays hidden; copies are placed."""
    if who in TEMPLATES:
        return TEMPLATES[who]
    path = Path(built_dir) / f"{who}.blend"
    if not path.exists():
        raise FileNotFoundError(f"3D character not built: {path} (run tools/blender/human3d_build.py)")
    with bpy.data.libraries.load(str(path), link=False) as (src, dst):
        dst.objects = [n for n in src.objects if not n.startswith("WGT-") and n not in ("Camera", "Light", "Cube")]
        dst.actions = [n for n in src.actions if n == "walk"]
    objects = [o for o in dst.objects if o is not None]
    coll = bpy.data.collections.get("human3d_templates") or bpy.data.collections.new("human3d_templates")
    if coll.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(coll)
    for o in objects:
        if o.name not in coll.objects:
            coll.objects.link(o)
        o.hide_render = True
        o.hide_viewport = True
    rig = _rig_of(objects)
    body = _body_of(objects)
    skin_look(objects)
    walk = next((a for a in dst.actions if a is not None), None)
    poses = json.loads(rig["human3d_poses"]) if "human3d_poses" in rig.keys() else {}
    TEMPLATES[who] = {"rig": rig, "body": body, "parts": [o for o in objects if o.type == "MESH"],
                      "poses": poses, "walk": walk}
    return TEMPLATES[who]


# MPFB's skin group as built reads as wax at film distance: strong subsurface, a clear coat and an even
# roughness. Skin that reads as skin is drier and less translucent, with the pores (its roughness and bump
# noise) stronger; lips and ears a touch redder; the eyes' outer layer a wet, sharp coat that catches light.
SKIN = {"SSS strength": 0.07, "Clearcoat": 0.0, "Roughness": 0.52, "Pore strength": 0.55, "Pore scale": 1600.0,
        "Contrast": 0.08}
SKIN_PART = {"lips": {"colorMixInStrength": 0.2, "Roughness": 0.38},
             "ears": {"colorMixInStrength": 0.12}}
EYES = {"Clearcoat": 1.0, "Clearcoat Roughness": 0.02, "OuterLayerRoughness": 0.0}


def skin_look(objects):
    """Tune the MPFB skin and eye shader inputs of a loaded character (its materials, once per template)."""
    for ob in objects:
        if ob.type != "MESH":
            continue
        for slot in ob.material_slots:
            m = slot.material
            if m is None or not m.use_nodes or m.get("human3d_skin"):
                continue
            for node in m.node_tree.nodes:
                if node.bl_idname != "ShaderNodeGroup" or node.node_tree is None:
                    continue
                part = next((p for p in reversed(m.name.split(".")) if not p.isdigit()), "")
                if "SSS strength" in node.inputs:
                    wanted = dict(SKIN, **SKIN_PART.get(part, {}))
                elif "OuterLayerRoughness" in node.inputs:
                    wanted = EYES
                else:
                    continue
                for key, value in wanted.items():
                    if key in node.inputs and not node.inputs[key].is_linked:
                        node.inputs[key].default_value = value
            m["human3d_skin"] = True


def instance(who, built_dir, name, collection, variant=None):
    """A copy of the character for one cast member: rig, body, garments and hair, all linked and re-pointed.
    Roles built in several variants (human3d_mpfb.py) hand them out in turn, see pick_variant."""
    if "." not in who:
        who = pick_variant(who, built_dir, variant)
    t = load_template(who, built_dir)
    mapping = {}
    rig = t["rig"].copy()
    rig.name = f"{name}_rig"
    collection.objects.link(rig)
    mapping[t["rig"]] = rig
    for part in t["parts"]:
        p = part.copy()
        p.data = part.data.copy()
        p.name = f"{name}_{part.name}"
        collection.objects.link(p)
        mapping[part] = p
    for old, new in mapping.items():
        if old.type == "MESH":
            # garments and hair are not children of the rig in the built file; here every part follows the rig,
            # so the whole costume moves and scales with the person
            new.parent = mapping.get(old.parent, rig) if old.parent is not None else rig
            new.matrix_parent_inverse.identity()
            for m in new.modifiers:
                if m.type == "ARMATURE" and m.object in mapping:
                    m.object = mapping[m.object]
                if m.type == "SHRINKWRAP" and m.target in mapping:
                    m.target = mapping[m.target]
    for new in mapping.values():
        new.hide_render = False
        new.hide_viewport = False
    body = mapping[t["body"]]
    return {"rig": rig, "body": body, "parts": [mapping[p] for p in t["parts"]], "poses": t["poses"], "walk": t["walk"]}


def stature(inst):
    """Standing height of the character at rig scale 1: the top of its body mesh (feet are at z=0)."""
    body = inst["body"]
    top = max((body.matrix_parent_inverse @ __import__("mathutils").Vector(c)).z for c in body.bound_box)
    return top if top > 0.5 else 1.75


def size_jitter(n):
    """A small size change per cast member (about +-3 %), so two people of one role and variant still differ."""
    return 1.0 + ((n * 37 + 11) % 7 - 3) * 0.01


def _key_pose_bone(pb, frame):
    pb.keyframe_insert("rotation_quaternion", frame=frame)


# the CharMorph kneel clip (CMU 23_03) retargets badly onto the rig, so there a kneel is the seated pose;
# the MPFB characters have a kneel of their own
POSE_STAND_IN = {"kneel": "sit"}

# the MPFB "point" pose lifts the arm about 65 degrees out from the body; the coats and blouses are weighted
# for a hanging arm, so the sleeve stretches into a fin. A pointing arm held lower (the fraction of the
# library rotation kept) keeps the cloth on the arm and still reads as a gesture
SOFTEN = {"point": {"upper_arm_fk.R": 0.55, "upper_arm_fk.L": 0.6, "forearm_fk.R": 0.8}}


def _toward_rest(q, keep):
    """The rotation `q` (w, x, y, z) scaled to `keep` of its angle (a slerp toward the rest pose)."""
    import math
    w, x, y, z = q
    w = max(-1.0, min(1.0, w))
    angle = 2 * math.acos(abs(w))
    s = math.sqrt(max(1e-12, 1 - w * w))
    if angle < 1e-6:
        return q
    sign = 1.0 if w >= 0 else -1.0
    half = angle * keep / 2
    return [math.cos(half), sign * x / s * math.sin(half), sign * y / s * math.sin(half),
            sign * z / s * math.sin(half)]


def set_pose(inst, pose, frame):
    """Pose from the library; a pose without its own entry uses its stand-in, then the standing pose."""
    rig = inst["rig"]
    library = inst["poses"]
    if pose not in library:
        pose = POSE_STAND_IN.get(pose, pose)
    entry = library.get(pose) or library.get("stand") or {}
    if "torso@loc" not in entry and any(k.endswith("@loc") for e in library.values() for k in e):
        entry = dict(entry, **{"torso@loc": [0.0, 0.0, 0.0]})
    for name in IK_SWITCHES:
        pb = rig.pose.bones.get(name)
        if pb is not None:
            pb["IK_FK"] = 1.0
            pb.keyframe_insert('["IK_FK"]', frame=frame)
    soften = SOFTEN.get(pose, {})
    for ctrl, q in entry.items():
        if ctrl in soften:
            q = _toward_rest(q, soften[ctrl])
        if ctrl.endswith("@loc"):
            # a control's location (MPFB poses lower the torso to kneel and sit)
            pb = rig.pose.bones.get(ctrl[:-4])
            if pb is not None:
                pb.location = q
                pb.keyframe_insert("location", frame=frame)
            continue
        pb = rig.pose.bones.get(ctrl)
        if pb is None:
            continue
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = q
        _key_pose_bone(pb, frame)


def play_walk(inst, start_frame):
    """The baked walk clip as an NLA strip starting at `start_frame` (the standing pose is replaced meanwhile)."""
    rig = inst["rig"]
    if inst["walk"] is None:
        return
    # the clip's vertical hip bob lifts the figure off the floor in this rig (its torso control is not
    # vertical), so the test walk keeps the leg and arm cycle and drops the torso translation
    for fc in list(inst["walk"].fcurves):
        if fc.data_path == 'pose.bones["torso"].location':
            inst["walk"].fcurves.remove(fc)
    if rig.animation_data is None:
        rig.animation_data_create()
    # the active action (the poses keyed by set_pose) is evaluated over the NLA and would hold the legs still:
    # the bones the clip moves are left to the clip
    walked = {fc.data_path for fc in inst["walk"].fcurves}
    act = rig.animation_data.action
    if act is not None:
        for fc in list(act.fcurves):
            if fc.data_path in walked:
                act.fcurves.remove(fc)
    track = rig.animation_data.nla_tracks.new()
    strip = track.strips.new("walk", int(start_frame), inst["walk"])
    if any(m.type == "CYCLES" for fc in inst["walk"].fcurves for m in fc.modifiers):
        strip.repeat = 60   # a one-cycle clip (human3d_mpfb.py) repeats for the rest of the shot
    strip.extrapolation = "HOLD_FORWARD"


def _key_sets(inst):
    """The body's shape keys, then those of the parts that carry the same face keys (MPFB eyebrows,
    eyelashes and beards), so the brows move with the forehead."""
    out = [inst["body"].data.shape_keys.key_blocks]
    for p in inst["parts"]:
        if p is not inst["body"] and p.data.shape_keys is not None:
            out.append(p.data.shape_keys.key_blocks)
    return out


def set_face(inst, face, frame):
    """Expression shape keys for `face`, keyed at `frame`; everything else in the face set to zero. A
    face is never quite symmetric: one side's keys are scaled a little (per person, from its rig name)."""
    wanted = FACE.get(face or "neutral", {})
    lean = 0.8 + 0.15 * ((sum(map(ord, inst["rig"].name)) * 37) % 100) / 100.0
    side = "R" if sum(map(ord, inst["rig"].name)) % 2 else "L"
    for keys in _key_sets(inst):
        for name in ALL_FACE_KEYS:
            kb = keys.get(name)
            if kb is None:
                continue
            value = wanted.get(name, 0.0)
            if name.endswith(f"{side}_max"):
                value *= lean
            kb.value = value
            kb.keyframe_insert("value", frame=frame)


# the face is never still: the brows lift and settle a little, one more than the other, and the corners
# of the mouth move (noise on the expression keys over whatever face is keyed)
FACE_IDLE = [("Exp_browsMidVert_max", 0.16, 3.0), ("Exp_browOutVertL_max", 0.10, 4.5),
             ("Exp_browOutVertR_max", 0.07, 5.5), ("Exp_mouthSmile_max", 0.05, 6.0)]


def face_idle(inst, seed, fps):
    import random
    rnd = random.Random(seed * 271 + 9)
    phases = {name: rnd.uniform(0, 1000) for name, _, _ in FACE_IDLE}
    for p in [inst["body"]] + [q for q in inst["parts"] if q is not inst["body"]]:
        sk = p.data.shape_keys
        if sk is None or sk.animation_data is None or sk.animation_data.action is None:
            continue
        for name, strength, period in FACE_IDLE:
            fc = sk.animation_data.action.fcurves.find(f'key_blocks["{name}"].value')
            if fc is None:
                if sk.key_blocks.get(name) is None:
                    continue
                sk.key_blocks[name].keyframe_insert("value", frame=1)
                fc = sk.animation_data.action.fcurves.find(f'key_blocks["{name}"].value')
                if fc is None:
                    continue
            m = fc.modifiers.new("NOISE")
            m.blend_type = "REPLACE"
            m.scale = period * fps
            m.strength = strength
            m.phase = phases[name]       # the same phase on body, brows and lashes: they move as one face
            m.offset = 0.0


def gaze(inst, yaw, pitch):
    """Turn the head (and a little of the neck) by `yaw` radians (positive = to the person's left) and tip it
    down by `pitch`, as a constant layer over the pose and the idle head motion."""
    import math
    rig = inst["rig"]
    act = rig.animation_data.action if rig.animation_data else None
    if act is None:
        return
    yaw = max(-1.05, min(1.05, yaw))
    pitch = max(-0.35, min(0.5, pitch))
    for bone, share in (("neck", 0.35), ("head", 0.65)):
        for axis, angle in ((2, yaw * share), (1, pitch * share)):
            fc = act.fcurves.find(f'pose.bones["{bone}"].rotation_quaternion', index=axis)
            if fc is None or abs(angle) < 1e-4:
                continue
            m = fc.modifiers.new("FNGENERATOR")
            m.function_type = "SIN"
            m.amplitude = 0.0
            m.value_offset = math.sin(angle / 2)
            m.use_additive = True


def gestures(inst, spans, fps, base_pose, seed):
    """While a person speaks ([start, end] seconds per line), the arms move with the words: the open-handed
    "talk" pose on most phrases, now and then the hands together, and back to the base pose in the pauses.
    Each change is keyed with a lead-in, so the arms travel between poses rather than snap."""
    import random
    rnd = random.Random(seed * 3571 + 5)
    library = inst["poses"]
    choices = [p for p in ("talk", "talk", "look-hands") if p in library]   # point swings the arm out sideways
    if not choices:
        return
    for t0, t1 in spans:
        t = t0
        while t < t1 - 0.6:
            seg = min(t1, t + rnd.uniform(1.6, 3.2))
            pose = rnd.choice(choices)
            f_in = max(2, round(t * fps) + 1)
            set_pose(inst, base_pose, max(1, f_in - round(0.35 * fps)))
            set_pose(inst, pose, f_in + round(0.25 * fps))
            set_pose(inst, pose, max(f_in + round(0.3 * fps), round(seg * fps) - round(0.3 * fps)))
            t = seg
        set_pose(inst, base_pose, round(t1 * fps) + round(0.5 * fps))


# speakers' arms are never quite still between gestures either
ARM_IDLE = [("upper_arm_fk.L", 1), ("upper_arm_fk.R", 1), ("forearm_fk.L", 1), ("forearm_fk.R", 1),
            ("hand_fk.L", 3), ("hand_fk.R", 3)]


def arm_idle(inst, seed, fps, strength=0.05):
    import random
    rnd = random.Random(seed * 911 + 1)
    act = inst["rig"].animation_data.action if inst["rig"].animation_data else None
    if act is None:
        return
    for bone, axis in ARM_IDLE:
        fc = act.fcurves.find(f'pose.bones["{bone}"].rotation_quaternion', index=axis)
        if fc is None:
            continue
        m = fc.modifiers.new("NOISE")
        m.blend_type = "REPLACE"
        m.scale = rnd.uniform(1.5, 2.5) * fps
        m.strength = strength
        m.phase = rnd.uniform(0, 1000)


# mouth_timing.json marks whole phrases as one "half" or "open" stretch; a held open mouth reads as a gape,
# so inside each stretch the jaw opens and closes at syllable rate (about 4-6 a second), each syllable a
# little different, and the stretch's shape sets how far it opens
SYLLABLE = (0.13, 0.22)          # seconds per syllable, min and max
OPENING = {"half": ("Exp_mouthOpenHalf_max", 0.9), "open": ("Exp_mouthOpen_max", 0.75),
           "wide": ("Exp_mouthOpenLarge_max", 0.6)}
MOUTH_KEYS = sorted({name for name, _ in OPENING.values()})


def talk(inst, visemes, fps, seed=0):
    """Mouth motion from [shape, start, end] visemes in beat seconds: syllable flaps inside the spoken
    stretches, the mouth shut in the "rest" and "closed" ones. Each key set (body, brows, lashes) gets the
    same curve, so the face moves as one."""
    import random
    rnd = random.Random(seed * 7919 + len(visemes))
    keys_out = {}                 # shape key -> [(frame, value)]
    for shape, t0, t1 in visemes:
        f0 = max(1, round(t0 * fps) + 1)
        f1 = max(f0 + 1, round(t1 * fps) + 1)
        if shape not in OPENING:
            for name in MOUTH_KEYS:
                keys_out.setdefault(name, []).append((f0, 0.0))
            continue
        name, peak = OPENING[shape]
        t = t0
        while t < t1 - 0.06:
            step = rnd.uniform(*SYLLABLE)
            mid, end = t + step * 0.45, min(t1, t + step)
            keys_out.setdefault(name, []).append((round(mid * fps) + 1, peak * rnd.uniform(0.45, 1.0)))
            keys_out[name].append((round(end * fps) + 1, peak * rnd.uniform(0.0, 0.15)))
            for other in MOUTH_KEYS:
                if other != name:
                    keys_out.setdefault(other, []).append((round(mid * fps) + 1, 0.0))
            t = end
        keys_out.setdefault(name, []).append((f1, 0.0))
    for keys in _key_sets(inst):
        for name, points in keys_out.items():
            kb = keys.get(name)
            if kb is None:
                continue
            last = {}
            for frame, value in points:
                last[max(1, frame)] = value          # a later key on the same frame wins
            for frame in sorted(last):
                kb.value = last[frame]
                kb.keyframe_insert("value", frame=frame)


def blinks(inst, total, seed, fps):
    """Blinks every 2.5-5.5 s (a quick double now and then), on the eyelid shape key of the body, brows
    and lashes; a seed per person so a group never blinks together."""
    import random
    rnd = random.Random(seed * 104729 + 17)
    t = rnd.uniform(0.3, 2.5)
    frames = []
    while t * fps < total:
        frames.append(round(t * fps) + 1)
        if rnd.random() < 0.15:
            frames.append(round((t + 0.35) * fps) + 1)
        t += rnd.uniform(2.5, 5.5)
    for keys in _key_sets(inst):
        kb = keys.get("Exp_eyesClosed_max")
        if kb is None:
            continue
        kb.value = 0.0
        kb.keyframe_insert("value", frame=1)
        for f in frames:
            for df, v in ((-1, 0.0), (1, 1.0), (2, 1.0), (5, 0.0)):
                kb.value = v
                kb.keyframe_insert("value", frame=max(1, f + df))


# subtle life on a person who is not walking, layered over whatever pose is keyed: F-curve modifiers on the
# quaternion x/y/z channels of the spine and head controls (Blender normalises pose quaternions, so a small
# offset there is a small extra rotation). (bone, axis, kind, amplitude, period in seconds):
#   breathing   the chest bends a little forward and back, about every 4 s
#   sway        the chest leans side to side and the hips roll the other way, slowly: a weight shift
#   head        a slow look left and right, a small nod and tilt
IDLE = [
    ("chest", 1, "sine", 0.010, 4.2),
    ("chest", 3, "noise", 0.030, 7.0),
    ("hips", 3, "noise", 0.016, 9.0),
    ("neck", 2, "noise", 0.040, 6.0),
    ("head", 2, "noise", 0.110, 5.0),
    ("head", 1, "noise", 0.050, 3.5),
    ("head", 3, "noise", 0.030, 6.5),
]


def idle(inst, seed, fps, walking=False):
    """Breathing, a weight shift and a wandering head, out of step with everyone else (seed per person).
    A walker keeps the clip's own body motion; only its head and breathing are added where the clip
    leaves those bones to the keyed pose."""
    import math
    import random
    rig = inst["rig"]
    act = rig.animation_data.action if rig.animation_data else None
    if act is None:
        return 0
    rnd = random.Random(seed * 6151 + 3)
    added = 0
    for bone, axis, kind, amp, period in IDLE:
        if walking and bone in ("hips", "chest") and kind == "noise":
            continue
        fc = act.fcurves.find(f'pose.bones["{bone}"].rotation_quaternion', index=axis)
        if fc is None:
            continue
        amp *= rnd.uniform(0.75, 1.25)
        if kind == "sine":
            m = fc.modifiers.new("FNGENERATOR")
            m.function_type = "SIN"
            m.amplitude = amp
            m.phase_multiplier = 2 * math.pi / (period * fps * rnd.uniform(0.85, 1.15))
            m.phase_offset = rnd.uniform(0, 2 * math.pi)
            m.use_additive = True
        else:
            m = fc.modifiers.new("NOISE")
            m.blend_type = "REPLACE"           # value + (noise - 0.5) * strength: centred on the pose
            m.scale = period * fps * rnd.uniform(0.8, 1.25)
            m.strength = 2 * amp
            m.phase = rnd.uniform(0, 1000)
            m.depth = 0
        added += 1
    return added


def show(inst, f0, f1, total):
    """Visible only from frame f0 to f1 (the cast member's shot)."""
    for ob in [inst["rig"]] + inst["parts"]:
        ob.hide_render = True
        ob.keyframe_insert("hide_render", frame=1)
        ob.hide_render = False
        ob.keyframe_insert("hide_render", frame=f0)
        if f1 < total:
            ob.hide_render = True
            ob.keyframe_insert("hide_render", frame=f1 + 1)
        ob.hide_render = False
