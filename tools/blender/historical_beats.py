"""Build 3 historical-asset replacement scenes for the Carrington episode.

Replaces the 3 Wikimedia preview assets with project-owned 3D renders:
  1. carrington-sunspot-3d  — Sun's surface with sunspot groups
  2. carrington-newspaper-3d — 1859 newspaper with aurora headline
  3. carrington-aurora-3d   — Aurora over telegraph landscape

Usage (Blender background mode):
    blender --background --factory-startup --python-exit-code 1 \
        --python tools/blender/historical_beats.py -- \
        --output work/episode-carrington/renders/historical
"""
import argparse
import math
import random
import subprocess
import sys
import time
from pathlib import Path

import bpy
import mathutils

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / "techniques"))
sys.path.insert(0, str(PROJECT_ROOT))

from common import (
    wipe, setup_scene, setup_world,
    material_principled, material_emissive,
    add_sphere, add_box, add_cylinder,
    add_area_light, add_sun_light, add_camera,
    render_still, save_blend, aim,
)
from labels import add_label


BG_DARK = (0.024, 0.031, 0.063)
AMBER = (1.0, 0.702, 0.278)
CYAN = (0.373, 0.831, 1.0)
SUN_ORANGE = (1.0, 0.549, 0.0)
SUN_YELLOW = (1.0, 0.843, 0.0)
PAPER = (0.92, 0.88, 0.78)
INK = (0.08, 0.06, 0.04)
AURORA_GREEN = (0.2, 1.0, 0.5)
AURORA_BLUE = (0.1, 0.5, 1.0)


def render_animation(output_dir, name, frame_end=150):
    scene = bpy.context.scene
    scene.frame_end = frame_end

    out_dir = output_dir / name
    out_dir.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(out_dir / "frame-####.png")
    bpy.ops.render.render(animation=True)
    print(f"  Rendered {frame_end} frames to {out_dir}", flush=True)

    mp4_path = output_dir / f"{name}.mp4"
    subprocess.run([
        "ffmpeg", "-y",
        "-framerate", "30",
        "-i", str(out_dir / "frame-%04d.png"),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "medium",
        "-crf", "18",
        "-movflags", "+faststart",
        str(mp4_path),
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if mp4_path.exists():
        size_mb = mp4_path.stat().st_size / 1024 / 1024
        print(f"  MP4: {mp4_path} ({size_mb:.1f} MB)", flush=True)

    scene.frame_set(frame_end // 2)
    still_path = output_dir / f"{name}-mid.png"
    scene.render.filepath = str(still_path)
    bpy.ops.render.render(write_still=True)
    print(f"  Still: {still_path}", flush=True)


def build_sunspot_scene(output_dir):
    print("BUILD: carrington-sunspot-3d", flush=True)
    t0 = time.perf_counter()
    wipe()
    setup_scene(resolution_x=1920, resolution_y=1080)
    setup_world(color=(*BG_DARK, 1.0), strength=0.15)

    sun = add_sphere("Sun", location=(0, 0, 0), radius=4.0)
    sun_mat = material_principled("SunSurface", SUN_ORANGE,
                                  roughness=0.8,
                                  emission_color=(0.3, 0.15, 0.0, 1.0),
                                  emission_strength=2.0)
    sun.data.materials.append(sun_mat)

    sunspot_groups = [
        (15, -20, 0.6, "A"),
        (12, -15, 0.4, "A2"),
        (-8, 10, 0.5, "B"),
        (-5, 15, 0.35, "B2"),
        (20, 30, 0.3, "C"),
    ]

    for lat, lon, size, tag in sunspot_groups:
        lat_r = math.radians(lat)
        lon_r = math.radians(lon)
        x = 4.01 * math.cos(lat_r) * math.cos(lon_r)
        y = 4.01 * math.cos(lat_r) * math.sin(lon_r)
        z = 4.01 * math.sin(lat_r)

        umbra = add_sphere(f"umbra_{tag}", location=(x, y, z),
                          radius=size * 0.4)
        u_mat = material_principled(f"umbra_{tag}", (0.05, 0.02, 0.0),
                                    roughness=1.0)
        umbra.data.materials.append(u_mat)

        penumbra = add_sphere(f"penumbra_{tag}", location=(x, y, z),
                             radius=size * 0.7)
        p_mat = material_principled(f"pen_{tag}", (0.3, 0.15, 0.05),
                                    roughness=0.9)
        penumbra.data.materials.append(p_mat)

    random.seed(42)
    for i in range(40):
        theta = random.uniform(0, 2 * math.pi)
        phi = random.uniform(-0.3 * math.pi, 0.3 * math.pi)
        r = 4.005
        x = r * math.cos(phi) * math.cos(theta)
        y = r * math.cos(phi) * math.sin(theta)
        z = r * math.sin(phi)
        granule = add_sphere(f"granule_{i}", location=(x, y, z),
                            radius=0.08 + random.random() * 0.12)
        g_mat = material_principled(
            f"gran_{i}",
            (1.0, 0.6 + random.random() * 0.2, 0.1),
            roughness=0.7,
            emission_color=(0.1, 0.05, 0.0, 1.0),
            emission_strength=0.5,
        )
        granule.data.materials.append(g_mat)

    cam = add_camera("Camera", location=(0, -10, 2), target=(0, 0, 0), lens=50)
    bpy.context.scene.camera = cam

    add_area_light("RimLight", location=(5, -8, 5),
                   energy=50, color=SUN_YELLOW, size=8)

    add_label("Carrington's Observation", anchor=(0, 0, 2),
              screen=(-3.5, -6, 3.5), camera=cam, frames=150,
              color=AMBER, text_size=0.35)
    add_label("1 September 1859", anchor=(0, 0, 1),
              screen=(-3.5, -6, 2.8), camera=cam, frames=150,
              color=CYAN, text_size=0.25)
    add_label("4.5-inch Refractor · Projection Method", anchor=(0, 0, 0),
              screen=(-3.5, -6, 2.2), camera=cam, frames=150,
              color=(0.7, 0.7, 0.7), text_size=0.2)

    save_blend(output_dir / "carrington-sunspot-3d.blend")
    render_animation(output_dir, "carrington-sunspot-3d", frame_end=150)
    print(f"  Done in {time.perf_counter() - t0:.1f}s", flush=True)


def build_newspaper_scene(output_dir):
    print("BUILD: carrington-newspaper-3d", flush=True)
    t0 = time.perf_counter()
    wipe()
    setup_scene(resolution_x=1920, resolution_y=1080)
    setup_world(color=(0.02, 0.02, 0.03, 1.0), strength=0.1)

    page = add_box("Page", location=(0, 0, 0), size=(6, 0.05, 8))
    page.rotation_euler = (math.radians(15), 0, math.radians(-3))
    page_mat = material_principled("Paper", PAPER, roughness=0.9)
    page.data.materials.append(page_mat)

    headlines = [
        ("EXTRAORDINARY", 5.0, 0.3, 2.8, 0.12),
        ("AURORA BOREALIS", 4.5, 0.25, 2.2, 0.1),
        ("TELEGRAPH DISRUPTED", 4.0, 0.2, 1.7, 0.08),
        ("SPARKS AND FIRES", 3.5, 0.18, 1.2, 0.07),
    ]
    for text, width, height, z_pos, thickness in headlines:
        block = add_box(f"hl_{text[:8]}", location=(0, 0.06, z_pos),
                       size=(width, thickness, height))
        # Parented, not given the page's euler: add_box keeps the placement on the object
        # transform, so copying page.rotation_euler would tilt the block about its own
        # centre and leave it floating off the tilted sheet. Parenting composes the two
        # transforms, which is the same world matrix the sheet's tilt is meant to give it.
        block.parent = page
        b_mat = material_principled(f"ink_{text[:8]}", INK, roughness=0.8)
        block.data.materials.append(b_mat)

    for x_off in [-1.5, 0, 1.5]:
        rule = add_box(f"rule_{x_off}", location=(x_off, 0.06, -0.5),
                      size=(0.02, 0.06, 6))
        rule.parent = page
        r_mat = material_principled(f"rulemat_{abs(x_off)}",
                                    (0.3, 0.25, 0.2), roughness=0.9)
        rule.data.materials.append(r_mat)

    for col_x in [-2.2, -0.7, 0.8, 2.3]:
        for line_i in range(12):
            z = -3.5 + line_i * 0.45
            line_w = 1.2 + math.sin(line_i * 0.7) * 0.3
            tline = add_box(f"txt_{col_x}_{line_i}",
                           location=(col_x, 0.06, z),
                           size=(line_w, 0.04, 0.06))
            tline.parent = page
            t_mat = material_principled(f"txtmat_{col_x}_{line_i}",
                                        (0.2, 0.18, 0.15), roughness=0.9)
            tline.data.materials.append(t_mat)

    date_bar = add_box("DateBar", location=(0, 0.06, 3.5),
                       size=(5.5, 0.06, 0.2))
    date_bar.parent = page
    date_mat = material_principled("DateInk", INK, roughness=0.8)
    date_bar.data.materials.append(date_mat)

    cam = add_camera("Camera", location=(0, -12, 6), target=(0, 0, 0), lens=35)
    bpy.context.scene.camera = cam

    add_area_light("DeskLamp", location=(3, -5, 6),
                   energy=500, color=(1.0, 0.9, 0.7), size=4)
    add_area_light("FillLight", location=(-4, -3, 3),
                   energy=200, color=(0.8, 0.85, 1.0), size=6)
    add_area_light("TopLight", location=(0, 0, 8),
                   energy=300, color=(1.0, 1.0, 1.0), size=10)

    add_label("New York Times · August 30, 1859", anchor=(0, 0, 3.5),
              screen=(-3, -5, 5), camera=cam, frames=150,
              color=AMBER, text_size=0.3)
    add_label("Historical Record", anchor=(0, 0, 3),
              screen=(-3, -5, 4.4), camera=cam, frames=150,
              color=CYAN, text_size=0.22)

    save_blend(output_dir / "carrington-newspaper-3d.blend")
    render_animation(output_dir, "carrington-newspaper-3d", frame_end=150)
    print(f"  Done in {time.perf_counter() - t0:.1f}s", flush=True)


def build_aurora_scene(output_dir):
    print("BUILD: carrington-aurora-3d", flush=True)
    t0 = time.perf_counter()
    wipe()
    setup_scene(resolution_x=1920, resolution_y=1080)
    setup_world(color=(0.01, 0.01, 0.03, 1.0), strength=0.05)

    scene = bpy.context.scene
    scene.view_settings.exposure = 0.0

    # Ground plane
    ground = add_box("Ground", location=(0, 0, 0), size=(40, 0.15, 25))
    g_mat = material_principled("GroundMat", (0.08, 0.1, 0.06), roughness=1.0)
    ground.data.materials.append(g_mat)

    # Snow patches
    random.seed(1859)
    for i in range(12):
        px = random.uniform(-15, 15)
        py = random.uniform(-8, 8)
        patch = add_box(f"snow_{i}", location=(px, py, 0.08),
                       size=(random.uniform(1, 3), 0.02, random.uniform(1, 2)))
        s_mat = material_principled(f"snow_{i}", (0.12, 0.14, 0.13), roughness=0.9)
        patch.data.materials.append(s_mat)

    # Telegraph poles
    pole_positions = [-5, -1.5, 1.5, 5]
    pole_mat = material_principled("PoleWood", (0.4, 0.28, 0.15), roughness=0.9)
    ins_mat = material_principled("Insulator", (0.9, 0.9, 0.85), roughness=0.3)

    for i, px in enumerate(pole_positions):
        pole = add_cylinder(f"pole_{i}", location=(px, 0, 1.5),
                           radius=0.07, depth=3.0)
        pole.data.materials.append(pole_mat)
        arm = add_box(f"arm_{i}", location=(px, 0, 2.9),
                     size=(0.9, 0.05, 0.07))
        arm.data.materials.append(pole_mat)
        for ix in [-0.4, 0.4]:
            insulator = add_sphere(f"ins_{i}_{ix}",
                                  location=(px + ix, 0, 2.95), radius=0.04)
            insulator.data.materials.append(ins_mat)

    # Wires
    wire_mat = material_principled("WireMetal", (0.5, 0.45, 0.4),
                                   metallic=0.8, roughness=0.3)
    for i in range(len(pole_positions) - 1):
        x1, x2 = pole_positions[i], pole_positions[i + 1]
        wire_pts = []
        for t in range(20):
            frac = t / 19
            wx = x1 + (x2 - x1) * frac
            sag = 0.2 * math.sin(frac * math.pi)
            wy = math.sin(frac * math.pi * 2) * 0.03
            wz = 2.7 - sag
            wire_pts.append((wx, wy, wz))
        for j in range(len(wire_pts) - 1):
            p1, p2 = wire_pts[j], wire_pts[j + 1]
            mid = ((p1[0]+p2[0])/2, (p1[1]+p2[1])/2, (p1[2]+p2[2])/2)
            dx, dy, dz = p2[0]-p1[0], p2[1]-p1[1], p2[2]-p1[2]
            length = math.sqrt(dx*dx + dy*dy + dz*dz)
            seg = add_cylinder(f"wire_{i}_{j}", location=mid,
                              radius=0.01, depth=length)
            direction = mathutils.Vector((dx, dy, dz)).normalized()
            rot_quat = mathutils.Vector((0, 0, 1)).rotation_difference(direction)
            seg.rotation_euler = rot_quat.to_euler()
            seg.data.materials.append(wire_mat)

    # Aurora curtains — colored transparent planes lit by matching area lights
    aurora_layers = [
        (AURORA_GREEN, 20, 5, 0, -3, 5.5),
        (AURORA_BLUE, 24, 7, 1, -1, 7.5),
        (AURORA_GREEN, 18, 4, 2, 1, 9.5),
    ]
    for color, width, height, idx, y_off, z_pos in aurora_layers:
        aurora = add_box(f"aurora_{idx}",
                        location=(0, y_off, z_pos),
                        size=(width, 0.06, height))
        aurora.rotation_euler = (math.radians(-10), 0, 0)
        # Semi-transparent colored plane
        a_mat = material_principled(f"aurora_mat_{idx}", color,
                                    roughness=0.5, alpha=0.6)
        aurora.data.materials.append(a_mat)
        # Matching area light behind each aurora layer
        add_area_light(f"aurora_light_{idx}",
                       location=(0, y_off - 2, z_pos + 1),
                       energy=80, color=color, size=width * 0.8)
        # Gentle drift
        aurora.keyframe_insert(data_path="location", frame=1)
        aurora.location.z += 0.3
        aurora.keyframe_insert(data_path="location", frame=75)
        aurora.location.z -= 0.3
        aurora.keyframe_insert(data_path="location", frame=150)

    # Stars — small emissive spheres
    random.seed(1859)
    for i in range(80):
        sx = random.uniform(-20, 20)
        sy = random.uniform(-10, -5)
        sz = random.uniform(5, 15)
        star = add_sphere(f"star_{i}", location=(sx, sy, sz),
                         radius=0.02 + random.random() * 0.02)
        s_mat = material_emissive(f"star_mat_{i}", (1, 1, 0.9), strength=3.0)
        star.data.materials.append(s_mat)

    # Camera
    cam = add_camera("Camera", location=(0, -6, 2), target=(0, 3, 5), lens=24)
    bpy.context.scene.camera = cam

    # Lighting — green glow from aurora direction, strong fill for ground/poles
    add_area_light("SkyGlow", location=(0, 0, 12),
                   energy=200, color=AURORA_GREEN, size=25)
    add_area_light("FillLight", location=(0, -3, 4),
                   energy=200, color=(0.5, 0.55, 0.7), size=10)
    add_area_light("GroundFill", location=(0, 3, 2),
                   energy=250, color=(0.7, 0.75, 0.6), size=10)
    add_area_light("PoleKey", location=(-3, -2, 3),
                   energy=180, color=(0.8, 0.85, 0.7), size=5)
    add_sun_light("MoonLight", location=(8, -5, 10),
                  energy=0.3, color=(0.7, 0.75, 1.0))

    # Labels
    add_label("The Carrington Event", anchor=(0, 0, 8),
              screen=(-5, -3, 12), camera=cam, frames=150,
              color=AMBER, text_size=0.4)
    add_label("2 September 1859",
              anchor=(0, 0, 6), screen=(-5, -3, 10), camera=cam, frames=150,
              color=CYAN, text_size=0.28)
    add_label("Aurora visible to ~18 degrees latitude",
              anchor=(0, 0, 5), screen=(-5, -3, 8.5), camera=cam, frames=150,
              color=(0.7, 0.7, 0.7), text_size=0.22)

    save_blend(output_dir / "carrington-aurora-3d.blend")
    render_animation(output_dir, "carrington-aurora-3d", frame_end=150)
    print(f"  Done in {time.perf_counter() - t0:.1f}s", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Build historical beat scenes")
    parser.add_argument("--output", required=True, type=Path,
                        help="Output directory")
    parser.add_argument("--scene", choices=["all", "sunspot", "newspaper", "aurora"],
                        default="all", help="Which scene(s) to build")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])

    output_dir = args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    scenes = {
        "sunspot": build_sunspot_scene,
        "newspaper": build_newspaper_scene,
        "aurora": build_aurora_scene,
    }

    if args.scene == "all":
        for name, fn in scenes.items():
            fn(output_dir)
    else:
        scenes[args.scene](output_dir)

    print("\nAll historical beats complete.", flush=True)


if __name__ == "__main__":
    main()
