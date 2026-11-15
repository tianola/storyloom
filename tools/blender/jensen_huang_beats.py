"""Jensen Huang episode — 13 procedural 3D beats.

Usage (Blender background mode, no args needed — all beat names and paths are hardcoded):
    blender -b -P tools/blender/jensen_huang_beats.py
"""
import json
import math
import sys
import time
from pathlib import Path

import bpy
import mathutils

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / "techniques"))
sys.path.insert(0, str(PROJECT_ROOT))

from common import wipe, setup_scene, setup_world  # noqa: E402

BEATS_DIR = PROJECT_ROOT / "work" / "jensen-huang" / "renders" / "3d"
FPS = 30
WIDTH, HEIGHT = 1920, 1080
CAMERA_TARGET = (0.0, 0.0, 1.5)


def aim_camera(camera, target=CAMERA_TARGET):
    camera.rotation_euler = (
        mathutils.Vector(target) - camera.location
    ).to_track_quat("-Z", "Y").to_euler()


# Shot lengths in seconds (from shot_lengths.json)
LENGTHS = {
    "denny-den": 14, "leather-jacket": 12, "silicon-wafer": 11,
    "nv1-chip": 12, "riva-chip": 10, "geforce-chip": 12,
    "parallel-cores": 12, "cuda-stack": 10, "deep-learning": 7,
    "dgx-cluster": 8, "blackwell-chip": 12, "flat-org": 11, "nvidia-hq": 11,
}


def make_beat(name):
    wipe()
    total_frames = LENGTHS[name] * FPS
    setup_scene(FPS, 1, total_frames, WIDTH, HEIGHT)
    setup_world()

    scene = bpy.context.scene
    cam = bpy.ops.object.camera_add()
    cam_obj = bpy.context.object
    scene.camera = cam_obj
    camera_target = (0.0, 0.0, 3.0) if name == "nvidia-hq" else CAMERA_TARGET
    if name == "nvidia-hq":
        cam_obj.data.lens = 35
    cam_obj.location = (20.0, -28.0, 13.0) if name == "nvidia-hq" else (12.0, -16.0, 8.0)
    aim_camera(cam_obj, camera_target)
    cam_obj.keyframe_insert(data_path="location", frame=1)
    cam_obj.keyframe_insert(data_path="rotation_euler", frame=1)

    cam_obj.location = (-18.0, -24.0, 11.0) if name == "nvidia-hq" else (-10.0, -12.0, 6.0)
    aim_camera(cam_obj, camera_target)
    cam_obj.keyframe_insert(data_path="location", frame=total_frames)
    cam_obj.keyframe_insert(data_path="rotation_euler", frame=total_frames)

    # Key light - ABSURDLY strong, dramatic
    sun = bpy.ops.object.light_add(type='SUN')
    sun_obj = bpy.context.object
    sun_obj.location = (-30, 15, 35)
    sun_obj.rotation_euler = (math.radians(88), math.radians(50), math.radians(270))
    sun_obj.data.energy = 50.0

    fill = bpy.ops.object.light_add(type='SUN')
    fill_obj = bpy.context.object
    fill_obj.location = (30, -30, 35)
    fill_obj.rotation_euler = (math.radians(89), 0, math.radians(-40))
    fill_obj.data.energy = 10.0

    _build(name)


def _cube(name, loc, scale, color, metallic=0.0, roughness=0.4):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    mat = bpy.data.materials.new(name + "_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    obj.data.materials.append(mat)
    return obj


def _cyl(name, loc, r, depth, color, metallic=0.3, roughness=0.4):
    bpy.ops.mesh.primitive_cylinder_add(location=loc, radius=r, depth=depth)
    obj = bpy.context.object
    obj.name = name
    mat = bpy.data.materials.new(name + "_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    obj.data.materials.append(mat)
    return obj


def _build(name):
    s = 1.0
    if name == "denny-den":
        # Diner table with two chairs
        _cube("table", (0, 0, 1.2), (2, 1, 0.15), (0.5, 0.35, 0.2), roughness=0.7)
        _cyl("table-leg1", (-1.2, -0.6, 0.6), 0.1, 1.2, (0.4, 0.4, 0.4), metallic=0.6)
        _cyl("table-leg2", (1.2, -0.6, 0.6), 0.1, 1.2, (0.4, 0.4, 0.4), metallic=0.6)
        _cube("chair1", (-2.5, 0, 0.8), (0.7, 0.7, 0.8), (0.3, 0.2, 0.15), roughness=0.8)
        _cube("chair2", (2.5, 0, 0.8), (0.7, 0.7, 0.8), (0.3, 0.2, 0.15), roughness=0.8)
        # Figure silhouettes
        _cyl("fig1", (-2.5, 0, 1.8), 0.3, 1.0, (0.2, 0.2, 0.25), roughness=0.6)
        _cyl("fig2", (2.5, 0, 1.8), 0.3, 1.0, (0.15, 0.15, 0.15), roughness=0.6)

    elif name == "leather-jacket":
        # Abstract figure in jacket
        _cyl("torso", (0, 0, 1.0), 0.6, 2.0, (0.1, 0.08, 0.05), roughness=0.9)
        _cube("jacket-collar", (0, 0, 2.2), (0.7, 0.5, 0.3), (0.08, 0.06, 0.04), roughness=0.85)
        _cyl("head", (0, 0, 2.8), 0.35, 0.6, (0.8, 0.65, 0.5), roughness=0.7)

    elif name == "silicon-wafer":
        # Circular wafer with grid
        bpy.ops.mesh.primitive_cylinder_add(location=(0, 0, 0), radius=3.0, depth=0.3)
        wafer = bpy.context.object
        wafer.name = "wafer"
        mat = bpy.data.materials.new("wafer_mat")
        mat.use_nodes = True
        b = mat.node_tree.nodes.get("Principled BSDF")
        b.inputs["Base Color"].default_value = (0.15, 0.15, 0.18, 1.0)
        b.inputs["Metallic"].default_value = 0.8
        b.inputs["Roughness"].default_value = 0.2
        wafer.data.materials.append(mat)
        # Die grid
        for i in range(-2, 3):
            for j in range(-2, 3):
                if (i * i + j * j) < 5:
                    _cube(f"die_{i}_{j}", (i * 1.1, j * 1.1, 0.18),
                          (0.4, 0.4, 0.05), (0.2, 0.25, 0.3), metallic=0.9, roughness=0.1)

    elif name in ("nv1-chip", "riva-chip", "geforce-chip", "blackwell-chip"):
        # Evolving chip: larger and more detailed with each generation
        gen = {"nv1-chip": 1, "riva-chip": 2, "geforce-chip": 3, "blackwell-chip": 4}[name]
        size = 0.5 + gen * 0.4
        color = (0.1, 0.1, 0.1 + gen * 0.05, )
        chip = _cube(name, (0, 0, 0), (size, size, size * 0.15), color, metallic=0.4, roughness=0.3)
        # Pins
        pin_count = gen * 8
        for i in range(pin_count):
            x = (i / pin_count - 0.5) * size * 2.5
            _cube(f"pin_{i}", (x, -size * 0.6, 0), (0.02, 0.15, 0.05),
                  (0.6, 0.6, 0.5), metallic=0.9, roughness=0.2)
        _cube("label", (0, 0, size * 0.15 + 0.05), (size * 0.7, size * 0.7, 0.02),
               (0.9, 0.85, 0.7), roughness=0.6)

    elif name == "parallel-cores":
        # Grid of cubes in parallel arrangement
        for i in range(4):
            for j in range(4):
                c = _cube(f"core_{i}_{j}", (i * 1.5 - 3, j * 1.5 - 3, 0),
                          (0.5, 0.5, 1.0), (0.1, 0.5 + i * 0.1, 0.9),
                          metallic=0.5, roughness=0.3)

    elif name == "cuda-stack":
        # Layered planes showing the stack architecture
        layers = [("hardware", 0.0, (0.3, 0.3, 0.35)), ("driver", 0.8, (0.4, 0.3, 0.3)),
                  ("runtime", 1.6, (0.3, 0.4, 0.5)), ("app", 2.4, (0.2, 0.5, 0.4))]
        for lbl, z, col in layers:
            _cube(lbl, (0, 0, z), (3, 3, 0.3), col, roughness=0.5)

    elif name == "deep-learning":
        # Neural network: layers of glowing spheres
        layers = [3, 5, 5, 2]
        for li, count in enumerate(layers):
            x = li * 2.5 - 3.75
            for ni in range(count):
                z = ni * 1.2 - (count - 1) * 0.6
                bpy.ops.mesh.primitive_uv_sphere_add(location=(x, 0, z), radius=0.35)
                obj = bpy.context.object
                obj.name = f"n_{li}_{ni}"
                mat = bpy.data.materials.new(obj.name + "_m")
                mat.use_nodes = True
                b = mat.node_tree.nodes.get("Principled BSDF")
                b.inputs["Base Color"].default_value = (0.2, 0.6 + li * 0.1, 0.8, 1.0)
                # Emission input names changed across Blender versions; guard both.
                for key in ("Emission Color", "Emission"):
                    if key in b.inputs:
                        b.inputs[key].default_value = (0.1, 0.3, 0.5, 1.0)
                        break
                if "Emission Strength" in b.inputs:
                    b.inputs["Emission Strength"].default_value = 0.5
                obj.data.materials.append(mat)

    elif name == "dgx-cluster":
        # Server rack with multiple units
        for i in range(4):
            _cube(f"server_{i}", (0, i * 0.8 - 1.2, i * 0.5),
                  (2, 0.3, 0.45), (0.15, 0.15, 0.15), metallic=0.7, roughness=0.3)
        _cube("rack-frame", (0, -1.6, 0.8), (2.5, 0.3, 2.0), (0.3, 0.3, 0.3), metallic=0.5)

    elif name == "flat-org":
        # Radial org chart: central node with direct reports
        _cyl("ceo", (0, 0, 0), 0.8, 0.3, (0.9, 0.8, 0.3), metallic=0.4)
        for i in range(12):
            angle = i * math.pi / 6
            x, z = math.cos(angle) * 3.5, math.sin(angle) * 3.5
            _cyl(f"report_{i}", (x, 0, z), 0.4, 0.2, (0.3, 0.5, 0.7), metallic=0.3)

    elif name == "nvidia-hq":
        # Modern building facade
        _cube("building", (0, 0, 3), (6, 4, 6), (0.4, 0.45, 0.5), roughness=0.4)
        # Windows grid
        for i in range(4):
            for j in range(6):
                _cube(f"win_{i}_{j}", (-2.5 + i * 1.6, -4.1, -2 + j * 1.5),
                      (0.5, 0.05, 1.0), (0.7, 0.85, 0.95), metallic=0.1, roughness=0.1)
        # Ground
        _cube("ground", (0, 0, -0.1), (10, 10, 0.2), (0.3, 0.28, 0.25), roughness=0.9)


def render_all():
    BEATS_DIR.mkdir(parents=True, exist_ok=True)
    names = list(LENGTHS.keys())
    total = len(names)
    print(f"Rendering {total} beats at {WIDTH}x{HEIGHT} {FPS}fps")

    for idx, name in enumerate(names):
        t0 = time.time()
        out_path = str(BEATS_DIR / f"{name}.mp4")
        if Path(out_path).exists() and Path(out_path).stat().st_size > 0:
            print(f"  [{idx+1}/{total}] {name} already rendered, skipping")
            continue
        print(f"  [{idx+1}/{total}] {name} ({LENGTHS[name]}s = {LENGTHS[name]*FPS} frames)...")
        make_beat(name)

        scene = bpy.context.scene
        scene.render.engine = "BLENDER_EEVEE_NEXT" if bpy.app.version >= (4, 2) else "BLENDER_EEVEE"
        scene.eevee.taa_render_samples = 32
        scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.ffmpeg.audio_codec = "AAC"
        # Use all CPU threads for FFmpeg encoding
        scene.render.threads_mode = 'FIXED'
        scene.render.threads = 8  # Ryzen 7 5700X has 8 cores
        scene.render.filepath = out_path

        bpy.ops.render.render(animation=True)
        elapsed = time.time() - t0
        print(f"    done in {elapsed:.1f}s")

    print(f"All {total} beats rendered to {BEATS_DIR}")


render_all()
