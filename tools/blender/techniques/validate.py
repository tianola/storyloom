"""CLI validator for technique scenes.

Usage (inside Blender background mode):
    blender --background --python-exit-code 1 \
        --python tools/blender/techniques/validate.py -- \
        --scene cutaway --blend work/technique-pack/cutaway.blend

Prints VALIDATION_JSON:<json> to stdout for the test harness to parse.
"""
import argparse
import json
import sys
from pathlib import Path

import bpy


def parse_args():
    parser = argparse.ArgumentParser(description="Validate a technique scene")
    parser.add_argument("--scene", required=True,
                        choices=["cutaway", "exploded", "xray", "zoom-inside"])
    parser.add_argument("--blend", required=True, type=Path,
                        help="Path to the .blend file to validate")
    parser.add_argument("--common-only", action="store_true",
                        help="Only check common scene properties, skip technique-specific checks")
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:])


def validate_common():
    """Validate properties every scene must have."""
    scene = bpy.context.scene
    result = {
        "has_camera": scene.camera is not None and scene.camera.name == "Camera",
        "fps": scene.render.fps,
        "frame_start": scene.frame_start,
        "frame_end": scene.frame_end,
        "resolution_x": scene.render.resolution_x,
        "resolution_y": scene.render.resolution_y,
        "engine": scene.render.engine,
        "view_transform": scene.view_settings.view_transform,
    }
    return result


def validate_cutaway():
    """Validate the cutaway scene contract."""
    result = {}

    # Check for 'shell' object
    shell = bpy.data.objects.get("shell")
    result["has_shell"] = shell is not None

    # Check for 'core' object
    core = bpy.data.objects.get("core")
    result["has_core"] = core is not None

    # Check for CUTAWAY Boolean modifier with Exact solver
    result["has_cutaway_modifier"] = False
    result["has_exact_solver"] = False
    if shell:
        for mod in shell.modifiers:
            if mod.name == "CUTAWAY" and mod.type == "BOOLEAN":
                result["has_cutaway_modifier"] = True
                if mod.solver == "EXACT":
                    result["has_exact_solver"] = True
                break

    # Check for visible label (any FONT curve object)
    result["has_label"] = False
    for obj in bpy.data.objects:
        if obj.type == "FONT":
            result["has_label"] = True
            break

    # Check Inter font is loaded
    result["has_inter_font"] = False
    for font in bpy.data.fonts:
        if "Inter" in font.name or "Inter" in (font.filepath or ""):
            result["has_inter_font"] = True
            break

    return result


def validate_exploded():
    """Validate the exploded scene contract."""
    result = {}

    # Check for at least 4 named parts
    part_names = ["part_housing", "part_rotor", "part_stator", "part_shaft"]
    found_parts = [n for n in part_names if bpy.data.objects.get(n) is not None]
    result["part_count"] = len(found_parts)
    result["part_names"] = found_parts

    # Check for EXPLODE Geometry Nodes modifier on at least one part
    result["has_explode_modifier"] = False
    for name in found_parts:
        ob = bpy.data.objects.get(name)
        if ob:
            for mod in ob.modifiers:
                if mod.name == "EXPLODE" and mod.type == "NODES":
                    result["has_explode_modifier"] = True
                    break
        if result["has_explode_modifier"]:
            break

    # Check for label
    result["has_label"] = any(obj.type == "FONT" for obj in bpy.data.objects)

    return result


def validate_xray():
    """Validate the xray scene contract."""
    result = {}

    # Check for shell with transparent mix material
    shell = bpy.data.objects.get("shell")
    result["has_shell"] = shell is not None
    result["has_transparent_mix"] = False
    result["has_animated_mix"] = False

    if shell and shell.data.materials:
        mat = shell.data.materials[0]
        if mat.use_nodes:
            # Look for a Mix Shader node
            for node in mat.node_tree.nodes:
                if node.type == "MIX_SHADER":
                    result["has_transparent_mix"] = True
                    # Check if the mix factor has keyframes
                    # The factor is inputs[0] of the Mix Shader
                    # We need to check if the material has animation data
                    if mat.node_tree.animation_data and mat.node_tree.animation_data.action:
                        for fc in mat.node_tree.animation_data.action.fcurves:
                            if "default_value" in fc.data_path:
                                if len(fc.keyframe_points) >= 2:
                                    result["has_animated_mix"] = True
                                    break
                    break

    # Check for inner mechanism
    result["has_inner_core"] = bpy.data.objects.get("inner_core") is not None

    # Check for label
    result["has_label"] = any(obj.type == "FONT" for obj in bpy.data.objects)

    return result


def validate_zoom_inside():
    """Validate the zoom-inside scene contract."""
    result = {}

    # Check for camera with location keyframes at frames 1 and 150
    cam = bpy.data.objects.get("Camera")
    result["has_camera"] = cam is not None
    result["has_camera_keyframe_f1"] = False
    result["has_camera_keyframe_f150"] = False

    if cam and cam.animation_data and cam.animation_data.action:
        for fc in cam.animation_data.action.fcurves:
            if fc.data_path == "location":
                frames = {int(kp.co[0]) for kp in fc.keyframe_points}
                if 1 in frames:
                    result["has_camera_keyframe_f1"] = True
                if 150 in frames:
                    result["has_camera_keyframe_f150"] = True

    # Check for internal mechanism
    inner_objects = [o for o in bpy.data.objects if o.name.startswith("inner_")]
    result["has_internal_mechanism"] = len(inner_objects) > 0

    # Check for label
    result["has_label"] = any(obj.type == "FONT" for obj in bpy.data.objects)

    return result


def main():
    args = parse_args()

    # Open the blend file
    blend_path = args.blend.resolve()
    if not blend_path.exists():
        print(f"ERROR: Blend file not found: {blend_path}", file=sys.stderr)
        sys.exit(1)

    bpy.ops.wm.open_mainfile(filepath=str(blend_path))

    # Common validation
    result = validate_common()

    if not args.common_only:
        # Technique-specific validation
        validators = {
            "cutaway": validate_cutaway,
            "exploded": validate_exploded,
            "xray": validate_xray,
            "zoom-inside": validate_zoom_inside,
        }
        specific = validators[args.scene]()
        result.update(specific)

    result["scene"] = args.scene
    result["blend_file"] = str(blend_path)
    result["valid"] = all(v for k, v in result.items()
                         if k not in ("scene", "blend_file", "valid",
                                      "part_names", "part_count")
                         and isinstance(v, bool))

    print(f"VALIDATION_JSON:{json.dumps(result)}", flush=True)

    if not result["valid"]:
        print(f"VALIDATION FAILED for {args.scene}", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
