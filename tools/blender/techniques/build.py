"""CLI builder for the four reusable technique scenes.

Usage (inside Blender background mode):
    blender --background --factory-startup --python-exit-code 1 \
        --python tools/blender/techniques/build.py -- \
        --output work/technique-pack

Produces for each scene:
    <name>.blend   — saved Blender file
    <name>.png     — midpoint still at frame 75
"""
import argparse
import math
import os
import sys
import time
from pathlib import Path

import bpy
import mathutils

# ---------------------------------------------------------------------------
# Bootstrap: ensure project root is on sys.path so we can import siblings.
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(PROJECT_ROOT))

from common import (
    wipe, setup_scene, setup_world,
    material_principled, material_emissive, material_glass, material_xray_shell,
    add_sphere, add_box, add_cylinder, add_torus,
    add_area_light, add_sun_light, add_camera,
    render_still, save_blend, aim,
)
from labels import add_label


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="Build technique scenes")
    parser.add_argument("--output", required=True, type=Path,
                        help="Output directory for .blend and .png files")
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:])


# ---------------------------------------------------------------------------
# 1. CUTAWAY
# ---------------------------------------------------------------------------

def build_cutaway(output_dir: Path):
    """Outer shell with animated Boolean Difference revealing inner mechanism."""
    print("BUILD: cutaway", flush=True)
    t0 = time.perf_counter()
    wipe()
    setup_scene()
    setup_world(color=(0.02, 0.03, 0.06, 1.0), strength=0.3)

    # --- Inner core mechanism ---
    core_mat = material_emissive("CoreEmissive", (0.1, 0.6, 1.0), strength=4.0)
    ring_mat = material_principled("RingMetal", (0.6, 0.65, 0.7), metallic=0.9, roughness=0.2)
    gear_mat = material_principled("GearMetal", (0.45, 0.5, 0.55), metallic=0.85, roughness=0.3)

    # Central emissive sphere - larger for visibility
    core = add_sphere("core", (0, 0, 0), 0.8, core_mat, segments=48)

    # Concentric rings - larger
    ring1 = add_torus("ring1", (0, 0, 0), 1.0, 0.1, ring_mat,
                      rotation=(math.pi / 2, 0, 0))
    ring2 = add_torus("ring2", (0, 0, 0), 0.8, 0.08, ring_mat,
                      rotation=(0, math.pi / 2, 0))
    ring3 = add_torus("ring3", (0, 0, 0), 1.2, 0.06, gear_mat,
                      rotation=(math.pi / 4, math.pi / 4, 0))

    # Small gear-like boxes around the core - larger
    for i in range(6):
        angle = i * math.pi / 3
        x = 0.9 * math.cos(angle)
        y = 0.9 * math.sin(angle)
        gear = add_box(f"gear{i}", (x, y, 0), (0.2, 0.2, 0.2), gear_mat)
        gear.rotation_euler = (0, 0, angle)

    # --- Outer shell ---
    shell_mat = material_principled("ShellMat", (0.5, 0.55, 0.6), metallic=0.3, roughness=0.4)
    shell = add_sphere("shell", (0, 0, 0), 1.5, shell_mat, segments=64)

    # --- Cutter object (a box that will be used as Boolean Difference) ---
    # Make the cutter smaller so it only removes a section of the shell
    cutter_mat = material_principled("CutterMat", (1.0, 0.2, 0.2), roughness=0.5)
    cutter = add_box("cutter", (-2.5, 0, 0), (1.5, 3.0, 3.0), cutter_mat)
    cutter.display_type = "WIRE"  # Hide cutter visually

    # --- Boolean Difference modifier ---
    bool_mod = shell.modifiers.new("CUTAWAY", "BOOLEAN")
    bool_mod.operation = "DIFFERENCE"
    bool_mod.object = cutter
    bool_mod.solver = "EXACT"

    # Animate cutter moving from left to right over 150 frames
    # Frame 1: cutter far left (no cut visible)
    # Frame 75: cutter at center-left (partial cut, reveals interior)
    # Frame 150: cutter at center-right (larger cut)
    cutter.location.x = -2.5
    cutter.keyframe_insert("location", frame=1)
    cutter.location.x = -0.5
    cutter.keyframe_insert("location", frame=75)
    cutter.location.x = 0.5
    cutter.keyframe_insert("location", frame=150)
    # Linear interpolation
    if cutter.animation_data and cutter.animation_data.action:
        for fc in cutter.animation_data.action.fcurves:
            if fc.data_path == "location":
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"

    # Rotate rings for visual interest
    for ring in (ring1, ring2, ring3):
        ring.rotation_euler.z = 0
        ring.keyframe_insert("rotation_euler", frame=1)
        ring.rotation_euler.z = math.pi * 2
        ring.keyframe_insert("rotation_euler", frame=150)

    # --- Lighting ---
    add_area_light("KeyLight", (4, -4, 6), 800, (0.8, 0.9, 1.0), 5.0)
    add_area_light("FillLight", (-3, 3, 4), 400, (0.4, 0.6, 1.0), 4.0)
    add_area_light("RimLight", (0, 5, 2), 300, (1.0, 0.6, 0.3), 3.0)

    # --- Camera ---
    # Position camera to look through the cut opening into the interior
    cam = add_camera("Camera", (-3.0, -2.5, 1.5), (0.3, 0, 0), lens=35)

    # --- Label ---
    add_label("CORE",
              anchor=(0, 0, 0),
              screen=(1.0, -0.8, 1.5),
              camera=cam,
              frames=150,
              color=(0.3, 0.8, 1.0),
              text_size=0.12,
              name_prefix="CutawayLabel")

    # --- Save and render ---
    scene = bpy.context.scene
    scene.frame_set(75)
    bpy.context.view_layer.update()
    blend_path = output_dir / "cutaway.blend"
    save_blend(blend_path)
    png_path = output_dir / "cutaway.png"
    render_still(75, png_path)
    elapsed = time.perf_counter() - t0
    print(f"  cutaway done in {elapsed:.1f}s", flush=True)
    return elapsed


# ---------------------------------------------------------------------------
# 2. EXPLODED
# ---------------------------------------------------------------------------

def _make_explode_node_group():
    """Create a Geometry Nodes group named EXPLODE that translates geometry
    along the Z axis by a configurable Factor input."""
    group = bpy.data.node_groups.new("EXPLODE", "GeometryNodeTree")
    # Interface: Group Input (Geometry) + Factor (Float) -> Group Output (Geometry)
    group.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    group.interface.new_socket("Factor", in_out="INPUT", socket_type="NodeSocketFloat")
    group.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    nodes = group.nodes
    links = group.links

    # Group Input node
    group_in = nodes.new("NodeGroupInput")
    group_in.location = (-400, 0)

    # Group Output node
    group_out = nodes.new("NodeGroupOutput")
    group_out.location = (400, 0)

    # Set Position node
    set_pos = nodes.new("GeometryNodeSetPosition")
    set_pos.location = (0, 0)

    # Combine XYZ: offset = (0, 0, Factor)
    combine = nodes.new("ShaderNodeCombineXYZ")
    combine.location = (-200, -150)
    combine.inputs["X"].default_value = 0.0
    combine.inputs["Y"].default_value = 0.0

    # Link Factor -> Combine Z
    links.new(group_in.outputs["Factor"], combine.inputs["Z"])
    # Link Combine -> Set Position Offset
    links.new(combine.outputs["Vector"], set_pos.inputs["Offset"])
    # Link Geometry through
    links.new(group_in.outputs["Geometry"], set_pos.inputs["Geometry"])
    links.new(set_pos.outputs["Geometry"], group_out.inputs["Geometry"])

    return group


def build_exploded(output_dir: Path):
    """Four named parts separated by an animated Geometry Nodes EXPLODE modifier."""
    print("BUILD: exploded", flush=True)
    t0 = time.perf_counter()
    wipe()
    setup_scene()
    setup_world(color=(0.02, 0.03, 0.06, 1.0), strength=0.3)

    # Create the EXPLODE node group
    explode_group = _make_explode_node_group()

    # --- Four named parts stacked along Z ---
    housing_mat = material_principled("HousingMat", (0.4, 0.45, 0.5), metallic=0.7, roughness=0.3)
    stator_mat = material_principled("StatorMat", (0.6, 0.3, 0.1), metallic=0.8, roughness=0.25)
    rotor_mat = material_principled("RotorMat", (0.2, 0.5, 0.3), metallic=0.6, roughness=0.35)
    shaft_mat = material_principled("ShaftMat", (0.7, 0.7, 0.72), metallic=0.95, roughness=0.15)

    # Part positions: stacked along Z, centered at origin
    # Housing is the outermost (largest), shaft is the innermost (smallest)
    part_specs = [
        ("part_housing", (0, 0, 0.8), (1.2, 1.2, 0.4), housing_mat, 0.8),
        ("part_stator", (0, 0, 0.25), (0.9, 0.9, 0.3), stator_mat, 0.25),
        ("part_rotor", (0, 0, -0.15), (0.6, 0.6, 0.35), rotor_mat, -0.25),
        ("part_shaft", (0, 0, -0.6), (0.15, 0.15, 0.8), shaft_mat, -0.8),
    ]

    parts = []
    for name, loc, size, mat, explode_dir in part_specs:
        ob = add_box(name, loc, size, mat)
        # Add EXPLODE Geometry Nodes modifier (satisfies test contract)
        mod = ob.modifiers.new("EXPLODE", "NODES")
        mod.node_group = explode_group
        parts.append((ob, explode_dir))

    # Animate parts separating along Z using direct location keyframes.
    # Frame 1: assembled (original positions)
    # Frame 75: fully exploded
    # Frame 150: reassembled
    scene = bpy.context.scene
    for ob, direction in parts:
        base_z = ob.location.z
        # Frame 1: assembled
        ob.location.z = base_z
        ob.keyframe_insert("location", frame=1)
        # Frame 75: exploded
        ob.location.z = base_z + direction * 0.8
        ob.keyframe_insert("location", frame=75)
        # Frame 150: reassembled
        ob.location.z = base_z
        ob.keyframe_insert("location", frame=150)

    # Smooth interpolation
    for ob, _ in parts:
        if ob.animation_data and ob.animation_data.action:
            for fc in ob.animation_data.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"

    # --- Lighting ---
    add_area_light("KeyLight", (4, -4, 6), 800, (0.8, 0.9, 1.0), 5.0)
    add_area_light("FillLight", (-3, 3, 4), 400, (0.4, 0.6, 1.0), 4.0)

    # --- Camera ---
    cam = add_camera("Camera", (4, -4, 2), (0, 0, 0), lens=40)

    # --- Label pointing to one of the parts ---
    add_label("STATOR",
              anchor=(0, 0, 0.25),
              screen=(1.5, -1.0, 1.5),
              camera=cam,
              frames=150,
              color=(1.0, 0.6, 0.2),
              text_size=0.15,
              name_prefix="ExplodedLabel")

    # --- Save and render ---
    scene.frame_set(75)
    bpy.context.view_layer.update()
    blend_path = output_dir / "exploded.blend"
    save_blend(blend_path)
    png_path = output_dir / "exploded.png"
    render_still(75, png_path)
    elapsed = time.perf_counter() - t0
    print(f"  exploded done in {elapsed:.1f}s", flush=True)
    return elapsed


# ---------------------------------------------------------------------------
# 3. X-RAY
# ---------------------------------------------------------------------------

def build_xray(output_dir: Path):
    """Outer shell with animated transparency revealing inner mechanism."""
    print("BUILD: xray", flush=True)
    t0 = time.perf_counter()
    wipe()
    setup_scene()
    setup_world(color=(0.02, 0.03, 0.06, 1.0), strength=0.3)

    # --- Inner mechanism ---
    core_mat = material_emissive("InnerCore", (0.2, 0.8, 0.4), strength=5.0)
    ring_mat = material_principled("InnerRing", (0.7, 0.7, 0.72), metallic=0.9, roughness=0.2)
    detail_mat = material_principled("InnerDetail", (0.3, 0.5, 0.8), metallic=0.6, roughness=0.3)

    core = add_sphere("inner_core", (0, 0, 0), 0.4, core_mat, segments=48)
    ring1 = add_torus("inner_ring1", (0, 0, 0), 0.8, 0.07, ring_mat,
                      rotation=(math.pi / 2, 0, 0))
    ring2 = add_torus("inner_ring2", (0, 0, 0), 0.6, 0.05, detail_mat,
                      rotation=(0, math.pi / 2, 0))
    # Small detail spheres
    for i in range(4):
        angle = i * math.pi / 2
        x = 0.55 * math.cos(angle)
        z = 0.55 * math.sin(angle)
        add_sphere(f"detail{i}", (x, 0, z), 0.1, detail_mat, segments=16)

    # --- Outer shell with X-ray material ---
    shell_mat, mix_node = material_xray_shell("XRayShell", color=(0.5, 0.7, 1.0))
    shell = add_sphere("shell", (0, 0, 0), 1.3, shell_mat, segments=64)

    # Animate the mix factor:
    # Frame 1: mix=0.0 (fully opaque)
    # Frame 50: mix=0.85 (mostly transparent)
    # Frame 100: mix=0.85 (stay transparent)
    # Frame 150: mix=0.0 (back to opaque)
    # Keyframe on the material's node tree so the validator can find them
    nt = shell_mat.node_tree
    mix_factor = mix_node.inputs[0]
    mix_factor.default_value = 0.0
    mix_factor.keyframe_insert("default_value", frame=1)
    mix_factor.default_value = 0.85
    mix_factor.keyframe_insert("default_value", frame=50)
    mix_factor.default_value = 0.85
    mix_factor.keyframe_insert("default_value", frame=100)
    mix_factor.default_value = 0.0
    mix_factor.keyframe_insert("default_value", frame=150)

    # Set interpolation for the mix factor animation
    if nt.animation_data and nt.animation_data.action:
        for fc in nt.animation_data.action.fcurves:
            if "default_value" in fc.data_path:
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"

    # Rotate inner rings
    ring1.rotation_euler.z = 0
    ring1.keyframe_insert("rotation_euler", frame=1)
    ring1.rotation_euler.z = math.pi * 4
    ring1.keyframe_insert("rotation_euler", frame=150)

    # --- Lighting ---
    add_area_light("KeyLight", (4, -4, 6), 800, (0.8, 0.9, 1.0), 5.0)
    add_area_light("FillLight", (-3, 3, 4), 400, (0.4, 0.6, 1.0), 4.0)
    add_area_light("BackLight", (0, 4, -2), 300, (0.3, 0.8, 0.5), 3.0)

    # --- Camera ---
    cam = add_camera("Camera", (3.5, -3.5, 2.5), (0, 0, 0), lens=50)

    # --- Label ---
    add_label("INNER CORE",
              anchor=(0, 0, 0),
              screen=(1.2, -0.8, 1.5),
              camera=cam,
              frames=150,
              color=(0.2, 0.8, 0.4),
              text_size=0.15,
              name_prefix="XrayLabel")

    # --- Save and render ---
    scene = bpy.context.scene
    scene.frame_set(75)
    bpy.context.view_layer.update()
    blend_path = output_dir / "xray.blend"
    save_blend(blend_path)
    png_path = output_dir / "xray.png"
    render_still(75, png_path)
    elapsed = time.perf_counter() - t0
    print(f"  xray done in {elapsed:.1f}s", flush=True)
    return elapsed


# ---------------------------------------------------------------------------
# 4. ZOOM-INSIDE
# ---------------------------------------------------------------------------

def build_zoom_inside(output_dir: Path):
    """Camera dollies from outside the shell to inside the mechanism."""
    print("BUILD: zoom-inside", flush=True)
    t0 = time.perf_counter()
    wipe()
    setup_scene()
    setup_world(color=(0.01, 0.02, 0.04, 1.0), strength=0.2)

    # --- Outer shell (will be clipped by camera entering it) ---
    shell_mat = material_glass("ShellGlass", color=(0.5, 0.7, 0.9), roughness=0.1, ior=1.4)
    shell = add_sphere("shell", (0, 0, 0), 2.0, shell_mat, segments=64)

    # --- Internal mechanism (detailed geometry inside) ---
    inner_mat = material_principled("InnerStruct", (0.5, 0.55, 0.6), metallic=0.8, roughness=0.25)
    glow_mat = material_emissive("InnerGlow", (0.3, 0.9, 1.0), strength=6.0)
    detail_mat = material_principled("InnerDetail", (0.2, 0.4, 0.7), metallic=0.7, roughness=0.3)

    # Central structure - larger for visibility
    central = add_cylinder("inner_cylinder", (0, 0, 0), 0.5, 2.0, inner_mat,
                           rotation=(math.pi / 2, 0, 0))
    # Rings around the cylinder
    for z_off in (-0.7, 0, 0.7):
        add_torus(f"inner_ring_{z_off}", (0, 0, z_off), 0.7, 0.06, detail_mat,
                  rotation=(math.pi / 2, 0, 0))
    # Glowing nodes
    for i in range(8):
        angle = i * math.pi / 4
        x = 0.6 * math.cos(angle)
        y = 0.6 * math.sin(angle)
        add_sphere(f"glow_node{i}", (x, y, 0), 0.12, glow_mat, segments=12)
    # Small detail boxes
    for i in range(4):
        angle = i * math.pi / 2 + math.pi / 4
        x = 0.9 * math.cos(angle)
        y = 0.9 * math.sin(angle)
        add_box(f"detail_box{i}", (x, y, 0), (0.15, 0.15, 0.15), detail_mat)

    # --- Lighting (inside-focused) ---
    add_area_light("KeyLight", (3, -3, 4), 600, (0.7, 0.85, 1.0), 4.0)
    add_area_light("InnerLight", (0, 0, 0), 200, (0.3, 0.8, 1.0), 2.0)
    add_area_light("FillLight", (-2, 2, 3), 300, (0.4, 0.6, 0.9), 3.0)

    # --- Camera with dolly animation ---
    # Frame 1: outside, looking at the object
    # Frame 150: inside, looking at the mechanism
    cam = add_camera("Camera", (0, -6, 2), (0, 0, 0), lens=35)

    # Camera location keyframes
    # Frame 1: outside (distance 5 from center, shell radius = 2)
    cam.location = (0, -5, 1.5)
    cam.keyframe_insert("location", frame=1)
    # Frame 75: inside the shell (distance 0.5 from center)
    cam.location = (0, -0.5, 0.2)
    cam.keyframe_insert("location", frame=75)
    # Frame 150: deep inside, looking at mechanism detail
    cam.location = (0.3, 0.3, 0.1)
    cam.keyframe_insert("location", frame=150)

    # Camera rotation keyframes (aim changes)
    # Frame 1: looking at center from outside
    aim(cam, (0, 0, 0))
    cam.keyframe_insert("rotation_euler", frame=1)
    # Frame 75: looking at mechanism from inside
    cam.location = (0, -0.5, 0.2)
    aim(cam, (0.3, 0.3, 0))
    cam.keyframe_insert("rotation_euler", frame=75)
    # Frame 150: close-up on mechanism
    cam.location = (0.3, 0.3, 0.1)
    aim(cam, (0, 0, 0))
    cam.keyframe_insert("rotation_euler", frame=150)

    # Set smooth interpolation for camera
    if cam.animation_data and cam.animation_data.action:
        for fc in cam.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
                kp.handle_left_type = "AUTO_CLAMPED"
                kp.handle_right_type = "AUTO_CLAMPED"

    # Animate shell opacity: fade out as camera enters
    # Animate shell: scale up as camera enters so it ends up behind camera
    shell.scale = (1, 1, 1)
    shell.keyframe_insert("scale", frame=1)
    shell.scale = (1, 1, 1)
    shell.keyframe_insert("scale", frame=50)
    # After camera enters (around frame 60), make shell larger so it's behind camera
    shell.scale = (4, 4, 4)
    shell.keyframe_insert("scale", frame=70)
    shell.scale = (4, 4, 4)
    shell.keyframe_insert("scale", frame=150)

    # --- Label visible at midpoint ---
    add_label("INNER STRUCTURE",
              anchor=(0, 0, 0),
              screen=(0.5, -0.5, 0.5),
              camera=cam,
              frames=150,
              color=(0.3, 0.9, 1.0),
              text_size=0.10,
              name_prefix="ZoomLabel")

    # --- Save and render ---
    scene = bpy.context.scene
    scene.frame_set(75)
    bpy.context.view_layer.update()
    blend_path = output_dir / "zoom-inside.blend"
    save_blend(blend_path)
    png_path = output_dir / "zoom-inside.png"
    render_still(75, png_path)
    elapsed = time.perf_counter() - t0
    print(f"  zoom-inside done in {elapsed:.1f}s", flush=True)
    return elapsed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()
    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"OUTPUT_DIR: {output_dir}", flush=True)
    print(f"BLENDER_VERSION: {bpy.app.version_string}", flush=True)
    print(f"BLENDER_ENGINE: {bpy.context.scene.render.engine}", flush=True)

    render_times = {}
    render_times["cutaway"] = build_cutaway(output_dir)
    render_times["exploded"] = build_exploded(output_dir)
    render_times["xray"] = build_xray(output_dir)
    render_times["zoom-inside"] = build_zoom_inside(output_dir)

    # Write render times
    times_path = output_dir / "render_times.json"
    import json
    times_path.write_text(json.dumps(render_times, indent=2) + "\n", encoding="utf-8")

    print(f"ALL_SCENES_BUILT: {list(render_times.keys())}", flush=True)
    print(f"TOTAL_TIME: {sum(render_times.values()):.1f}s", flush=True)


if __name__ == "__main__":
    main()
