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
    walk = next((a for a in dst.actions if a is not None), None)
    poses = json.loads(rig["human3d_poses"]) if "human3d_poses" in rig.keys() else {}
    TEMPLATES[who] = {"rig": rig, "body": body, "parts": [o for o in objects if o.type == "MESH"],
                      "poses": poses, "walk": walk}
    return TEMPLATES[who]


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


def _key_pose_bone(pb, frame):
    pb.keyframe_insert("rotation_quaternion", frame=frame)


# the CharMorph kneel clip (CMU 23_03) retargets badly onto the rig, so there a kneel is the seated pose;
# the MPFB characters have a kneel of their own
POSE_STAND_IN = {"kneel": "sit"}


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
    for ctrl, q in entry.items():
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
    """Expression shape keys for `face`, keyed at `frame`; everything else in the face set to zero."""
    wanted = FACE.get(face or "neutral", {})
    for keys in _key_sets(inst):
        for name in ALL_FACE_KEYS:
            kb = keys.get(name)
            if kb is None:
                continue
            kb.value = wanted.get(name, 0.0)
            kb.keyframe_insert("value", frame=frame)


def talk(inst, visemes, fps):
    """Mouth shapes from [shape, start, end] visemes in beat seconds; the mouth rests between them."""
    for keys in _key_sets(inst):
        for shape, t0, t1 in visemes:
            name, value = MOUTH.get(shape, (None, 0.0))
            f0 = max(1, round(t0 * fps) + 1)
            f1 = max(f0 + 1, round(t1 * fps) + 1)
            if name and keys.get(name):
                keys[name].value = value
                keys[name].keyframe_insert("value", frame=f0)
                keys[name].value = 0.0
                keys[name].keyframe_insert("value", frame=f1)


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
