"""Jensen Huang episode: 13 3D beats built from the reusable model library.

    blender -b -P tools/blender/jensen_huang_beats.py                      # every beat, skip rendered ones
    blender -b -P tools/blender/jensen_huang_beats.py -- --beat riva-chip  # one beat (repeatable)
    blender -b -P tools/blender/jensen_huang_beats.py -- --force           # re-render over existing files
    blender -b -P tools/blender/jensen_huang_beats.py -- --still 0.6 --out work/jensen-huang/qc/stills
        # one PNG per beat at 60% of its length, half resolution: the look check before a full render

Each beat is "which model, which move": the objects come from tools/blender/models, and
what a beat adds is the camera drift, the take-apart and the labels.
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / "models"))

import kit  # noqa: E402
import hardware  # noqa: E402
import sets  # noqa: E402
from kit import FPS, placed  # noqa: E402

EPISODE = PROJECT_ROOT / "work" / "jensen-huang"
BEATS_DIR = EPISODE / "renders" / "3d"
LENGTHS = json.loads((EPISODE / "shot_lengths.json").read_text(encoding="utf-8"))


def f(seconds):
    return max(1, round(seconds * FPS))


def grow(ob, base_z, height, f0, f1):
    """Raise a bar from its base: scale and position keyed together."""
    ob.scale[2] = 0.001
    ob.location[2] = base_z
    ob.keyframe_insert("scale", frame=f0)
    ob.keyframe_insert("location", frame=f0)
    ob.scale[2] = 1.0
    ob.location[2] = base_z + height / 2
    ob.keyframe_insert("scale", frame=f1)
    ob.keyframe_insert("location", frame=f1)


# ---------------------------------------------------------------------------
# Beats
# ---------------------------------------------------------------------------

def denny_den(sec):
    st = kit.stage(sec, target=(0.1, 0, 0.95), radius=(7.6, 5.4), azimuth=(205, 238), height=(3.3, 2.3),
                   lens=40, floor_grid=0.8, key_energy=2.0, fill=260.0)
    booth = sets.diner_booth()
    sets.figure("founder-a", (-0.65, 1.22, 0.0), facing=0.0, seated=True)
    sets.figure("founder-b", (0.65, 1.22, 0.0), facing=0.0, seated=True, jacket=kit.mid())
    sets.figure("founder-c", (-0.1, -1.22, 0.0), facing=math.pi, seated=True,
                jacket=kit.mat("kit-denim", (0.10, 0.14, 0.22), roughness=0.8))
    # the idea on the napkin lights up as the sentence reaches "a bet on a wild idea"
    kit.pulse(booth["sketch_ink"], [(1, 0.0), (f(sec * 0.45), 0.0), (f(sec * 0.62), 5.0)])
    kit.label(st, "San Jose, 1993", booth["napkin_xyz"], (0.3, 0.86), size=0.05, appear_at=f(sec * 0.55))


def leather_jacket(sec):
    st = kit.stage(sec, target=(0.9, 0.4, 2.1), radius=(13.5, 11.5), azimuth=(-112, -84), height=(2.8, 2.4),
                   lens=45, floor_grid=1.0)
    kit.cyl("stage", (0, 0, 0.09), 3.4, 0.18, kit.slate(), verts=64)
    kit.cyl("stage-rim", (0, 0, 0.02), 3.5, 0.04, kit.accent(), verts=64)
    sets.figure("presenter", (-1.3, -0.6, 0.18), facing=math.radians(12), jacket=kit.epoxy(), scale=1.7)
    # keynote screen: the valuation climbing behind him
    kit.box("screen", (1.6, 1.9, 2.5), (6.4, 0.16, 3.7), kit.epoxy(), bevel=0.03)
    kit.box("screen-face", (1.6, 1.81, 2.5), (6.1, 0.02, 3.4), kit.mat("kit-screen", (0.02, 0.028, 0.04), roughness=0.5),
            bevel=0)
    heights = [0.10, 0.13, 0.11, 0.20, 0.34, 0.62, 1.30, 2.75]
    for k, h in enumerate(heights):
        last = k == len(heights) - 1
        bar = kit.box(f"bar{k}", (-0.85 + k * 0.70, 1.77, 1.05), (0.44, 0.05, h),
                      kit.glow("bar-hot", 2.2) if last else kit.mid(), bevel=0)
        grow(bar, 1.05, h, f(0.4 + k * 0.45), f(1.2 + k * 0.45))
    kit.boxes("screen-axis", [placed((1.6, 1.78, 1.02), (5.6, 0.03, 0.02))], kit.base())
    kit.label(st, "$3 trillion", (4.05, 1.72, 3.85), (0.5, 0.8), size=0.05, appear_at=f(5.2))


def silicon_wafer(sec):
    st = kit.stage(sec, target=(0.0, 0, 0.5), radius=(15.5, 12.5), azimuth=(-125, -94), height=(9.6, 7.2),
                   floor_grid=1.0)
    kit.cyl("chuck", (0, 0, -0.14), 4.1, 0.28, kit.slate(), verts=96)
    w = hardware.wafer()
    hx, hy = w["hero_xy"]
    kit.move(w["hero"], f(2.5), f(6.5), (0, 0, 1.25))
    kit.label(st, "Silicon wafer", (-2.6, -1.6, 0.08), (0.2, 0.16), size=0.05, appear_at=f(0.8))
    kit.label(st, "One die = one chip", (hx, hy, 1.33), (0.74, 0.84), size=0.05, appear_at=f(6.6), follow=w["hero"])


def nv1_chip(sec):
    st = kit.stage(sec, target=(0.9, 0.2, 1.0), radius=(16.0, 14.0), azimuth=(-114, -90), height=(7.0, 5.6),
                   floor_grid=0.9)
    kit.box("board", (-1.9, 0, 0.06), (4.6, 4.6, 0.10), kit.pcb(), bevel=0.02)
    chip = hardware.qfp_chip("nv1", size=2.6, text="NV1", seed=2)
    carrier = kit.group("nv1-all", [chip[k] for k in ("leads", "frame", "die", "wires", "lid")])
    carrier.location = (-1.9, 0, 0.10)
    # the design decision that nearly sank the company, shown instead of said:
    # NV1 drew curved quadratic patches while everyone else settled on triangles
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=5, y_subdivisions=5, size=2.0, location=(2.2, 0.9, 1.6))
    patch = bpy.context.active_object
    for v in patch.data.vertices:
        v.co.z = 0.55 * (1 - v.co.x ** 2) * (1 - v.co.y ** 2) - 0.25
    patch.rotation_euler = (math.radians(62), 0, math.radians(-18))
    patch.modifiers.new("wire", "WIREFRAME").thickness = 0.05
    patch.data.materials.append(kit.accent())
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=1.0, location=(4.9, 0.9, 1.6))
    tri = bpy.context.active_object
    tri.modifiers.new("wire", "WIREFRAME").thickness = 0.05
    tri.data.materials.append(kit.base())
    kit.spin(patch, st.frames, 0.10)
    kit.spin(tri, st.frames, 0.22)
    kit.appear(patch, f(3.0), f(3.6))
    kit.appear(tri, f(5.4), f(6.0))
    kit.label(st, "NV1: curved patches", (2.2, 0.9, 2.3), (0.58, 0.9), size=0.045, appear_at=f(3.4))
    kit.label(st, "Everyone else: triangles", (4.9, 0.9, 0.55), (0.76, 0.14), size=0.045, appear_at=f(5.8))


def riva_chip(sec):
    st = kit.stage(sec, target=(0, 0, 1.15), radius=(13.2, 11.0), azimuth=(-122, -92), height=(7.6, 6.0),
                   floor_grid=0.8)
    chip = hardware.qfp_chip("riva", size=3.2, leads_per_side=24, text="RIVA 128", seed=4)
    kit.move(chip["lid"], f(1.6), f(3.4), (0, 0, 2.3))
    kit.move(chip["wires"], f(2.6), f(4.2), (0, 0, 0.55))
    kit.move(chip["die"], f(2.6), f(4.2), (0, 0, 0.55))
    top = chip["top"]
    kit.label(st, "Plastic package", (1.25, -1.5, top + 2.3), (0.8, 0.88), size=0.045, appear_at=f(3.5), follow=chip["lid"])
    kit.label(st, "Silicon die", (0.3, -0.4, top + 0.52), (0.14, 0.56), size=0.045, appear_at=f(4.4), follow=chip["die"])
    kit.label(st, "Pins to the board", (-1.2, -1.9, 0.08), (0.2, 0.14), size=0.045, appear_at=f(5.6))


def geforce_chip(sec):
    st = kit.stage(sec, target=(0, -0.3, 1.5), radius=(17.5, 14.5), azimuth=(-122, -94), height=(10.0, 7.6),
                   floor_grid=1.2)
    card = hardware.graphics_card(chip_text="GeForce 256")
    kit.spin(card["rotor"], st.frames, 9.0)
    kit.move(card["fan"], f(2.2), f(4.4), (0, 0, 2.7))
    kit.move(card["heatsink"], f(2.8), f(5.0), (0, 0, 1.35))
    gx, gy, gz = card["gpu_xyz"]
    kit.label(st, "Fan + heatsink", (1.2, -1.5, 2.4), (0.8, 0.76), size=0.045, appear_at=f(5.0), follow=card["heatsink"])
    kit.label(st, "GPU", (gx, gy, gz + 0.1), (0.1, 0.5), size=0.055, appear_at=f(5.8))
    kit.label(st, "Plugs into the PC", (-1.1, -2.55, 0.34), (0.36, 0.1), size=0.045, appear_at=f(7.6))


def parallel_cores(sec):
    st = kit.stage(sec, target=(0, -0.2, 0.9), radius=(15.5, 13.6), azimuth=(-103, -80), height=(10.0, 8.6),
                   floor_grid=1.1)
    F = st.frames
    for x, tag in ((-2.9, "cpu"), (2.9, "gpu")):
        kit.box(f"{tag}-substrate", (x, 0, 0.08), (4.6, 4.6, 0.16), kit.pcb(), bevel=0.03)
        kit.box(f"{tag}-die", (x, 0, 0.21), (4.0, 4.0, 0.10), kit.silicon(), bevel=0.01)
    # CPU: four large cores, working one after another
    step = F / 4
    for k, (cx, cy) in enumerate(((-1, 1), (1, 1), (-1, -1), (1, -1))):
        m = kit.glow(f"cpu-core{k}", 0.05)
        kit.box(f"cpu-core{k}", (-2.9 + cx * 0.95, cy * 0.95, 0.30), (1.6, 1.6, 0.09), m, bevel=0.03)
        kit.pulse(m, [(1, 0.05), (max(1, round(k * step)), 0.05), (round(k * step) + 6, 4.0),
                      (round((k + 1) * step) - 6, 4.0), (round((k + 1) * step), 0.6)])
    # GPU: hundreds of small cores, every one working in the same instant
    rows, cols, cell = 16, 16, 3.7 / 16
    for r in range(rows):
        m = kit.glow(f"gpu-row{r}", 0.05)
        cells = [placed((2.9 - 1.85 + (c + 0.5) * cell, -1.85 + (r + 0.5) * cell, 0.29),
                        (cell * 0.6, cell * 0.6, 0.07)) for c in range(cols)]
        kit.boxes(f"gpu-row{r}", cells, m)
        keys = [(1, 0.05)]
        for k in range(4):
            t0 = round(k * step) + 4 + r
            keys += [(max(2, t0 - 3), 0.5 if k else 0.05), (t0, 4.5), (t0 + 14, 4.5), (t0 + 26, 0.5)]
        kit.pulse(m, keys)
    kit.label(st, "CPU: 4 cores, in turn", (-2.9, 2.0, 0.3), (0.28, 0.88), size=0.045, appear_at=f(0.6))
    kit.label(st, "GPU: thousands, at once", (2.9, 2.0, 0.3), (0.72, 0.88), size=0.045, appear_at=f(2.2))


def cuda_stack(sec):
    st = kit.stage(sec, target=(0.4, 0, 2.3), radius=(16.5, 14.0), azimuth=(-108, -82), height=(6.6, 5.4),
                   floor_grid=1.2)
    chip = hardware.bga_chip("gpu", size=3.6, text="GPU")
    del chip
    ink = kit.slate()
    layers = [("CUDA", 1.75, kit.accent(), ink), ("Libraries", 2.85, kit.base(), ink),
              ("Applications", 3.95, kit.base(), ink)]
    for k, (text, z, material, text_mat) in enumerate(layers):
        slab = kit.box(f"layer-{text}", (0, 0, z), (4.6, 4.6, 0.46), material, bevel=0.05)
        word = kit.flat_text(f"text-{text}", text, (0, -2.305, z), 0.34, text_mat, rot=(math.radians(90), 0, 0))
        g = kit.group(f"g-{text}", (slab, word))
        g.location = (0, 0, 5.0)
        kit.move(g, f(1.0 + k * 1.6), f(2.2 + k * 1.6), (0, 0, -5.0))
        kit.appear(g, f(1.0 + k * 1.6), f(1.3 + k * 1.6))
    kit.label(st, "General-purpose code", (2.3, -2.3, 3.95), (0.8, 0.9), size=0.045, appear_at=f(6.2))
    kit.label(st, "Graphics chip", (1.8, -1.8, 0.4), (0.84, 0.2), size=0.045, appear_at=f(0.6))


def deep_learning(sec):
    st = kit.stage(sec, target=(0, 0, 3.7), radius=(17.5, 15.8), azimuth=(-102, -80), height=(4.4, 4.0),
                   lens=45, floor_grid=1.3)
    net = sets.neural_network()
    F = st.frames
    n = len(net["layers"])
    for li, m in enumerate(net["layers"]):
        keys = [(1, 0.15)]
        for wave in range(3):
            t0 = round(wave * F / 3) + 6 + li * 9
            keys += [(max(2, t0 - 5), 0.4 if wave else 0.15), (t0, 6.0), (t0 + 10, 6.0), (t0 + 24, 0.8)]
        kit.pulse(m, keys)
    first, last = net["positions"][0], net["positions"][n - 1]
    kit.label(st, "Image in", first[-1], (0.13, 0.9), size=0.045, appear_at=f(0.4))
    kit.label(st, "Answer out", last[-1], (0.87, 0.9), size=0.045, appear_at=f(1.6))


def dgx_cluster(sec):
    st = kit.stage(sec, target=(0, -0.8, 2.5), radius=(15.0, 13.0), azimuth=(-126, -100), height=(5.0, 4.2),
                   lens=42, floor_grid=1.2)
    racks = []
    for k, x in enumerate((-2.7, 0.0, 2.7)):
        rack = hardware.server_rack(f"rack{k}", pull=4 if k == 1 else None)
        racks.append(rack)
        for part in (rack["frame"], rack["drawer"]):
            if part is not None:
                part.location = (x, 0, 0)
        if rack["drawer"] is not None:
            kit.move(rack["drawer"], f(1.2), f(3.4), (0, -2.3, 0))
    kit.label(st, "8 GPUs in one server", (0.0, -2.4, 2.75), (0.5, 0.92), size=0.045, appear_at=f(3.5), follow=racks[1]["drawer"])


def blackwell_chip(sec):
    st = kit.stage(sec, target=(0, 0, 1.6), radius=(15.0, 12.4), azimuth=(-122, -94), height=(8.6, 6.4),
                   floor_grid=1.0)
    pkg = hardware.ai_package("blackwell")
    kit.move(pkg["lid"], f(1.4), f(3.4), (0, 0, 2.6))
    for k, layer in enumerate(pkg["memory"]):
        kit.move(layer, f(3.2 + k * 0.25), f(4.8 + k * 0.25), (0, 0, 0.28 + k * 0.30))
    mx, my = pkg["memory_xy"]
    kit.label(st, "Heat spreader", (1.4, -1.5, 2.95), (0.82, 0.86), size=0.045, appear_at=f(3.4), follow=pkg["lid"])
    kit.label(st, "Logic die", (0.0, -0.9, 0.38), (0.5, 0.09), size=0.045, appear_at=f(4.2))
    kit.label(st, "Stacked memory", (mx, -0.9, 1.75), (0.84, 0.56), size=0.045, appear_at=f(5.6), follow=pkg["memory"][-1])
    kit.label(st, "Silicon interposer", (-1.55, -1.3, 0.3), (0.17, 0.3), size=0.045, appear_at=f(7.0))


def flat_org(sec):
    st = kit.stage(sec, target=(0, 0, 0.9), radius=(19.0, 16.5), azimuth=(-118, -90), height=(12.0, 9.6),
                   floor_grid=1.1)
    kit.cyl("ceo-plinth", (0, 0, 0.22), 0.62, 0.44, kit.accent(), verts=40)
    kit.ico("ceo-head", (0, 0, 0.86), 0.34, kit.accent(), subdivisions=1)
    rings = ((3.1, 16), (5.2, 26), (7.0, 18))
    start = 1.0
    for ri, (radius, count) in enumerate(rings):
        seats, heads, links = [], [], []
        for k in range(count):
            a = k * 2 * math.pi / count + ri * 0.31
            x, y = math.cos(a) * radius, math.sin(a) * radius
            seats.append(((x, y, 0.13), 0.30, 0.26))
            heads.append((x, y, 0.52))
            links.append(((x * 0.13, y * 0.13, 0.05), (x, y, 0.05)))
        parts = (kit.cylinders(f"ring{ri}-seats", seats, kit.base(), segments=20),
                 kit.balls(f"ring{ri}-heads", heads, 0.20, kit.base()),
                 kit.rods(f"ring{ri}-links", links, 0.018, kit.accent()))
        g = kit.group(f"ring{ri}", parts)
        kit.appear(g, f(start + ri * 1.8), f(start + ri * 1.8 + 0.9))
    kit.label(st, "60 direct reports", (5.2, -0.4, 0.75), (0.82, 0.88), size=0.045, appear_at=f(5.6))
    kit.label(st, "No layers in between", (-1.4, -0.9, 0.08), (0.2, 0.82), size=0.045, appear_at=f(7.2))


def nvidia_hq(sec):
    kit.stage(sec, target=(0, 0, 1.4), radius=(27.0, 22.0), azimuth=(-118, -84), height=(13.5, 9.5), lens=40,
              floor_grid=2.0, key_energy=4.5)
    sets.campus_building()


BEATS = {
    "denny-den": denny_den, "leather-jacket": leather_jacket, "silicon-wafer": silicon_wafer,
    "nv1-chip": nv1_chip, "riva-chip": riva_chip, "geforce-chip": geforce_chip,
    "parallel-cores": parallel_cores, "cuda-stack": cuda_stack, "deep-learning": deep_learning,
    "dgx-cluster": dgx_cluster, "blackwell-chip": blackwell_chip, "flat-org": flat_org,
    "nvidia-hq": nvidia_hq,
}


def configure_video(scene, out_path):
    scene.eevee.taa_render_samples = 24
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    scene.render.ffmpeg.audio_codec = "NONE"
    scene.render.filepath = str(out_path)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--beat", action="append", choices=sorted(BEATS))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--still", type=float, action="append",
                    help="render one PNG at this fraction of the beat instead of the video (repeatable)")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)

    names = args.beat or list(BEATS)
    out_dir = args.out or BEATS_DIR
    if not out_dir.is_absolute():
        out_dir = PROJECT_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    for idx, name in enumerate(names):
        seconds = LENGTHS[name]
        t0 = time.time()
        if args.still:
            BEATS[name](seconds)
            scene = bpy.context.scene
            scene.render.resolution_percentage = 50
            for frac in args.still:
                frame = max(1, round(frac * seconds * FPS))
                kit.common.render_still(frame, out_dir / f"{name}-{round(frac * 100):03d}.png", samples=16)
            for line in kit.LAST.problems:
                print(f"    FRAMING {name}: {line}")
            print(f"  [{idx + 1}/{len(names)}] {name} stills in {time.time() - t0:.1f}s")
            continue
        out_path = out_dir / f"{name}.mp4"
        if out_path.exists() and out_path.stat().st_size > 0 and not args.force:
            print(f"  [{idx + 1}/{len(names)}] {name} already rendered, skipping")
            continue
        print(f"  [{idx + 1}/{len(names)}] {name} ({seconds}s = {seconds * FPS} frames)...")
        BEATS[name](seconds)
        configure_video(bpy.context.scene, out_path)
        bpy.ops.render.render(animation=True)
        print(f"    done in {time.time() - t0:.1f}s")
    print(f"{len(names)} beats -> {out_dir}")


main()
