"""Record the pose library on a built 3D character (run with Blender in background, after human3d_build.py).

    blender -b --factory-startup --enable-autoexec -P tools/blender/human3d_poses.py -- \
        --db <charmorph-db> --blend <built.blend> --clips <dir with 02_01.bvh, 23_03.bvh>

What is stored on the rig object:
  rig["human3d_poses"]   JSON {pose name: {FK control: [w, x, y, z]}} for "stand", "sit", "kneel"
  an action named "walk" (the baked walk clip), kept with a fake user so it survives saving

"stand" and "sit" come from CharMorph's own pose files (standing_basic, sit_basic) through its
apply_pose operator. "kneel" is one frame of CMU clip 23_03 (subject B kneels), retargeted. "walk" is
CMU clip 02_01, retargeted and baked. Other pose names fall back to "stand" in the renderer.
"""
import argparse
import json
import sys
from pathlib import Path

import bpy

REPO_TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_TOOLS))
import human3d_mocap  # noqa: E402

KNEEL_SRC_FRAME = 361   # frame 90 of the 30 fps timeline in the test renders (BVH is 120 fps)


def parse(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--blend", required=True)
    ap.add_argument("--clips", required=True)
    return ap.parse_args(argv)


def _rig_and_body():
    rig = next(o for o in bpy.data.objects if o.type == "ARMATURE" and o.data.get("rig_id"))
    body = next(o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("mb_"))
    return rig, body


def _reset(rig):
    for pb in rig.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)


def _read_fk(rig):
    out = {}
    for ctrl in sorted(set(human3d_mocap.MAP.values()) | {"torso", "root", "neck", "head"}):
        pb = rig.pose.bones.get(ctrl)
        if pb is None:
            continue
        q = pb.rotation_quaternion
        out[ctrl] = [q.w, q.x, q.y, q.z]
    return out


def _capture_charmorph_pose(rig, name):
    _reset(rig)
    ui = bpy.context.window_manager.charmorph_ui
    ui.pose = name
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="POSE")
    result = bpy.ops.charmorph.apply_pose()
    bpy.ops.object.mode_set(mode="OBJECT")
    print("HUMAN3D_POSE", name, result)
    return _read_fk(rig)


def main():
    args = parse(sys.argv[sys.argv.index("--") + 1:])
    bpy.ops.preferences.addon_enable(module="rigify")
    bpy.ops.preferences.addon_enable(module="CharMorph")
    bpy.context.preferences.addons["CharMorph"].preferences.data_path = args.db
    bpy.ops.charmorph.reload_library()
    bpy.ops.wm.open_mainfile(filepath=args.blend)
    rig, body = _rig_and_body()
    clips = Path(args.clips)

    poses = {}
    poses["stand"] = _capture_charmorph_pose(rig, "standing_basic")
    poses["sit"] = _capture_charmorph_pose(rig, "sit_basic")
    _reset(rig)
    poses["kneel"] = human3d_mocap.capture_pose(rig, str(clips / "23_03.bvh"), KNEEL_SRC_FRAME)
    _reset(rig)

    # walk: retarget the whole clip and keep it as an action on the rig
    before = set(bpy.data.actions.keys())
    f0, f1 = human3d_mocap.retarget(rig, str(clips / "02_01.bvh"), start_frame=1, fps_out=30, clip_name="walk")
    action = rig.animation_data.action if rig.animation_data else None
    if action is None:
        raise SystemExit("walk retarget produced no action")
    action.name = "walk"
    action.use_fake_user = True
    rig.animation_data.action = None
    _reset(rig)
    print("HUMAN3D_WALK_FRAMES", f0, f1, "new actions", sorted(set(bpy.data.actions.keys()) - before))

    rig["human3d_poses"] = json.dumps(poses)
    bpy.ops.wm.save_as_mainfile(filepath=args.blend, check_existing=False)
    print("HUMAN3D_POSES_SAVED", args.blend, sorted(poses.keys()))


if __name__ == "__main__":
    main()
