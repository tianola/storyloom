"""Retarget CMU mocap (BVH) onto a CharMorph Rigify character's FK controls, and bake keyframes.

Method: for each mapped bone, the source bone's world rotation change from its rest pose is applied to the
target bone's rest world rotation, then converted to the target's local basis relative to its (already set)
parent. Parents are processed first so each child sees the parent's final pose.

Used from another script (e.g. human3d_clips.py) that already has the character open in Blender:

    import human3d_mocap
    human3d_mocap.retarget(rig, bvh_path, start_frame=1, fps_out=30, clip_name="walk")

The BVH is imported as a separate armature, then deleted.
"""
import math

import bpy
from mathutils import Matrix, Vector

# CMU/Bruce BVH joint name -> Rigify FK control on the CharMorph rig
MAP = {
    "LowerBack": "spine_fk",
    "Spine": "spine_fk.001",
    "Spine1": "spine_fk.002",
    "Neck": "neck",
    "Head": "head",
    "LeftShoulder": "shoulder.L",
    "LeftArm": "upper_arm_fk.L",
    "LeftForeArm": "forearm_fk.L",
    "LeftHand": "hand_fk.L",
    "RightShoulder": "shoulder.R",
    "RightArm": "upper_arm_fk.R",
    "RightForeArm": "forearm_fk.R",
    "RightHand": "hand_fk.R",
    "LeftUpLeg": "thigh_fk.L",
    "LeftLeg": "shin_fk.L",
    "LeftFoot": "foot_fk.L",
    "LeftToeBase": "toe.L",
    "RightUpLeg": "thigh_fk.R",
    "RightLeg": "shin_fk.R",
    "RightFoot": "foot_fk.R",
    "RightToeBase": "toe.R",
}
ROOT_MAP = "Hips"
ROOT_CONTROL = "torso"
LIMB_SWITCHES = ["upper_arm_parent.L", "upper_arm_parent.R", "thigh_parent.L", "thigh_parent.R"]


def _import_bvh(path):
    before = set(bpy.data.objects.keys())
    bpy.ops.import_anim.bvh(filepath=path, axis_forward="-Z", axis_up="Y", global_scale=1.0,
                            frame_start=1, use_fps_scale=False, update_scene_fps=False,
                            update_scene_duration=False, rotate_mode="QUATERNION")
    new = [bpy.data.objects[n] for n in bpy.data.objects.keys() if n not in before]
    arm = next(o for o in new if o.type == "ARMATURE")
    return arm, new


def _rest_world(arm, bone_name):
    return arm.matrix_world @ arm.data.bones[bone_name].matrix_local


def retarget(rig, bvh_path, start_frame=1, fps_out=30, clip_name="clip", scale=None):
    """Bake the BVH onto `rig` (Rigify FK controls). Returns (first, last) frame keyed."""
    scene = bpy.context.scene
    src, temp_objs = _import_bvh(bvh_path)
    src_fps = scene.render.fps / scene.render.fps_base
    n_src = src.animation_data.action.frame_range[1] if src.animation_data and src.animation_data.action else 0
    frame_range = scene.frame_end = int(n_src)
    # the BVH frame time gives the clip length in seconds
    bvh_frames = int(scene.frame_end)
    bvh_time = _bvh_frame_time(bvh_path)
    seconds = bvh_frames * bvh_time
    out_frames = max(2, int(round(seconds * fps_out)))

    # IK/FK: limbs follow the FK controls
    for name in LIMB_SWITCHES:
        pb = rig.pose.bones.get(name)
        if pb is not None:
            pb["IK_FK"] = 1.0

    rig_pb = rig.pose.bones
    order = _parent_order(rig, list(MAP.values()) + [ROOT_CONTROL])
    if scale is None:
        scale = _root_scale(src, rig)
    for k in range(out_frames):
        t = k / float(fps_out)
        src_frame = 1 + t / bvh_time
        frame = start_frame + k
        scene.frame_set(int(src_frame))
        bpy.context.view_layer.update()
        # subframe: blend the two neighbouring source frames
        for name in order:
            if name == ROOT_CONTROL:
                _set_root(src, rig, frame, scale)
                continue
            bvh_name = next(b for b, c in MAP.items() if c == name)
            _set_fk(src, rig, bvh_name, name, frame)
        bpy.context.view_layer.update()
    # remove the temporary source armature
    for ob in temp_objs:
        bpy.data.objects.remove(ob, do_unlink=True)
    rig.animation_data_create()
    return start_frame, start_frame + out_frames - 1


def capture_pose(rig, bvh_path, src_frame):
    """The FK pose of `rig` at one frame of a BVH clip, as {control: quaternion}. Nothing is keyed."""
    scene = bpy.context.scene
    src, temp_objs = _import_bvh(bvh_path)
    scene.frame_set(int(src_frame))
    bpy.context.view_layer.update()
    for name in LIMB_SWITCHES:
        pb = rig.pose.bones.get(name)
        if pb is not None:
            pb["IK_FK"] = 1.0
    out = {}
    for bvh_name, ctrl in MAP.items():
        if rig.pose.bones.get(ctrl) is None:
            continue
        _set_fk(src, rig, bvh_name, ctrl, 0, key=False)
        q = rig.pose.bones[ctrl].rotation_quaternion
        out[ctrl] = [q.w, q.x, q.y, q.z]
    for ob in temp_objs:
        bpy.data.objects.remove(ob, do_unlink=True)
    return out


def _bvh_frame_time(path):
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("Frame Time"):
                return float(line.split(":")[1])
    return 1.0 / 30.0


def _parent_order(rig, names):
    depth = {}
    for n in names:
        pb = rig.pose.bones.get(n)
        d, p = 0, pb.parent if pb else None
        while p is not None:
            d += 1
            p = p.parent
        depth[n] = d
    return sorted([n for n in names if rig.pose.bones.get(n)], key=lambda n: depth[n])


def _root_scale(src, rig):
    """Ratio between the character's leg length and the BVH leg length (both in metres)."""
    def leg(ob, bone_a, bone_b, world):
        a = ob.data.bones.get(bone_a)
        b = ob.data.bones.get(bone_b)
        if not a or not b:
            return None
        return ((ob.matrix_world @ a.head_local) - (ob.matrix_world @ b.head_local)).length
    src_leg = leg(src, "LeftUpLeg", "LeftFoot", True)
    tgt = rig.pose.bones.get("thigh_fk.L")
    tgt_leg = None
    if tgt is not None:
        tgt_leg = (rig.matrix_world @ tgt.bone.head_local - rig.matrix_world @ rig.pose.bones["foot_fk.L"].bone.head_local).length
    if not src_leg or not tgt_leg:
        return 1.0
    return tgt_leg / src_leg


def _set_root(src, rig, frame, scale):
    src_hips = src.pose.bones.get(ROOT_MAP)
    tgt = rig.pose.bones.get(ROOT_CONTROL)
    if src_hips is None or tgt is None:
        return
    # the vertical is the world Z of the hips, not the BVH armature's local Z (the BVH's up axis is not local Z)
    cur_world = src.matrix_world @ src_hips.head
    rest_world = src.matrix_world @ src.data.bones[ROOT_MAP].head_local
    # in place: keep only the vertical bob; horizontal drift stays with the clip's own foot placement, which
    # we do not reproduce, so the figure does not walk off its spot
    dz = (cur_world.z - rest_world.z) * scale
    tgt.location = Vector((0.0, 0.0, dz))
    tgt.keyframe_insert("location", frame=frame)
    # the hips rotation belongs on the torso too; without it the spine would carry the pelvis twice
    _set_fk(src, rig, ROOT_MAP, ROOT_CONTROL, frame)


def _set_fk(src, rig, bvh_name, ctrl_name, frame, key=True):
    s = src.pose.bones.get(bvh_name)
    c = rig.pose.bones.get(ctrl_name)
    if s is None or c is None:
        return
    src_rest = _rest_world(src, bvh_name).to_3x3()
    src_now = (src.matrix_world @ s.matrix).to_3x3()
    delta = src_now @ src_rest.inverted()  # world-space change from the source's rest, same as applied to the target
    tgt_rest = _rest_world(rig, c.name).to_3x3()
    desired = delta @ tgt_rest  # target world rotation with the same change
    if c.parent is not None:
        parent_now = (rig.matrix_world @ c.parent.matrix).to_3x3()
        parent_rest_local = (rig.matrix_world @ c.parent.bone.matrix_local).to_3x3()
        bone_rest_local = (rig.matrix_world @ c.bone.matrix_local).to_3x3()
        rel_rest = parent_rest_local.inverted() @ bone_rest_local
        basis = (parent_now @ rel_rest).inverted() @ desired
    else:
        basis = (rig.matrix_world @ c.bone.matrix_local).to_3x3().inverted() @ desired
    c.rotation_mode = "QUATERNION"
    c.rotation_quaternion = basis.to_quaternion()
    if key:
        c.keyframe_insert("rotation_quaternion", frame=frame)
