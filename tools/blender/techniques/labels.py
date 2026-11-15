"""Anchored label system for technique scenes.

Ported from the cable_render.py label pattern: world-anchor + screen-space
leader line with text, backing plate, anchor dot, and optional animation.
"""
import math
import os
from pathlib import Path

import bpy
import mathutils


# ---------------------------------------------------------------------------
# Font cache
# ---------------------------------------------------------------------------

_FONT = None
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_FONT_PATH = _PROJECT_ROOT / "tools" / "fonts" / "Inter-SemiBold.ttf"


def _get_font():
    global _FONT
    if _FONT is None:
        _FONT = bpy.data.fonts.load(str(_FONT_PATH))
    return _FONT


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def add_label(text: str,
              anchor: tuple[float, float, float],
              screen: tuple[float, float, float],
              camera: bpy.types.Object,
              frames: int,
              color=(0.3, 0.8, 1.0),
              text_size=0.18,
              name_prefix="Label") -> list[bpy.types.Object]:
    """Create an anchored label with text, backing plate, leader line, anchor dot.

    Args:
        text: Label text string.
        anchor: 3D world position the label points to (the feature).
        screen: 3D world position where the label text appears.
        camera: The scene camera (unused for orientation in this simplified
                version — screen position is in world space).
        frames: Total animation length (used for optional draw animation).
        color: RGB colour for emissive elements.
        text_size: Blender font size for the text object.
        name_prefix: Name prefix for created objects.

    Returns:
        List of created objects: [text_obj, leader_line, anchor_dot, backing_plate].
    """
    created = []

    # --- Text object ---
    cu = bpy.data.curves.new(f"{name_prefix}Text", "FONT")
    cu.body = text
    cu.font = _get_font()
    cu.size = text_size
    cu.align_x = "LEFT"
    cu.space_character = 1.08
    text_mat = _emissive_material(f"{name_prefix}TextMat", color, strength=2.5)
    cu.materials.append(text_mat)
    text_obj = bpy.data.objects.new(f"{name_prefix}Text", cu)
    text_obj.location = screen
    bpy.context.collection.objects.link(text_obj)
    # Track to camera so text always faces the viewer
    track = text_obj.constraints.new("TRACK_TO")
    track.target = camera
    track.track_axis = "TRACK_Z"
    track.up_axis = "UP_Y"
    created.append(text_obj)

    # --- Backing plate (dark semi-transparent plane behind text) ---
    plate_mat = _dark_plate_material(f"{name_prefix}PlateMat")
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=screen)
    plate = bpy.context.active_object
    plate.name = f"{name_prefix}Plate"
    plate.data.materials.append(plate_mat)
    # Scale to fit text (approximate)
    pad = text_size * 0.4
    text_width = len(text) * text_size * 0.55
    text_height = text_size * 1.4
    plate.scale = (text_width + pad, text_height + pad, 1.0)
    bpy.ops.object.transform_apply(scale=True)
    # Offset plate slightly behind text (toward camera)
    cam_dir = mathutils.Vector(camera.location) - mathutils.Vector(screen)
    cam_dir.normalize()
    plate.location += cam_dir * 0.01
    # Track to camera
    ptrack = plate.constraints.new("TRACK_TO")
    ptrack.target = camera
    ptrack.track_axis = "TRACK_Z"
    ptrack.up_axis = "UP_Y"
    created.append(plate)

    # --- Leader line (thin cylinder from anchor to screen) ---
    anchor_v = mathutils.Vector(anchor)
    screen_v = mathutils.Vector(screen)
    direction = screen_v - anchor_v
    length = direction.length
    mid = anchor_v + direction * 0.5
    line_mat = _emissive_material(f"{name_prefix}LineMat", color, strength=1.5)
    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.008, depth=length, location=mid)
    leader = bpy.context.active_object
    leader.name = f"{name_prefix}Leader"
    leader.data.materials.append(line_mat)
    # Orient cylinder along the direction
    leader.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    created.append(leader)

    # --- Anchor dot (small sphere at the anchor position) ---
    dot_mat = _emissive_material(f"{name_prefix}DotMat", color, strength=4.0)
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=12, radius=0.03, location=anchor)
    dot = bpy.context.active_object
    dot.name = f"{name_prefix}Dot"
    dot.data.materials.append(dot_mat)
    bpy.ops.object.shade_smooth()
    created.append(dot)

    # --- Optional: animate leader line drawing (first 30 frames) ---
    # Scale the leader from 0 to full length over frames 1..30
    if frames >= 30:
        leader.scale = (1.0, 1.0, 0.001)
        leader.keyframe_insert("scale", frame=1)
        leader.scale = (1.0, 1.0, 1.0)
        leader.keyframe_insert("scale", frame=30)
        # Set interpolation to ease
        if leader.animation_data and leader.animation_data.action:
            for fc in leader.animation_data.action.fcurves:
                if fc.data_path == "scale":
                    for kp in fc.keyframe_points:
                        kp.interpolation = "BEZIER"

    return created


# ---------------------------------------------------------------------------
# Internal material helpers
# ---------------------------------------------------------------------------

def _emissive_material(name, color, strength=2.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Emission Color"].default_value = (*color, 1.0)
    bsdf.inputs["Emission Strength"].default_value = strength
    bsdf.inputs["Roughness"].default_value = 0.3
    return mat


def _dark_plate_material(name, alpha=0.82):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.01, 0.02, 0.04, 1.0)
    bsdf.inputs["Alpha"].default_value = alpha
    bsdf.inputs["Roughness"].default_value = 1.0
    mat.blend_method = "HASHED"
    return mat
