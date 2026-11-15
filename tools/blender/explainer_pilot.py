"""Pilot for the "explainer" look: one unbroken move from a graphics card down to its cores.

    blender -b -P tools/blender/explainer_pilot.py                         # the video
    blender -b -P tools/blender/explainer_pilot.py -- --still 1,4,7,10,13,17,23
        # half-resolution PNGs at those seconds: the look check before the render

The shot answers one question without a cut: why is a GPU fast? The camera starts on
the whole card, the cooler lifts away, the package opens, and the lens keeps going
until the die fills the frame and its cores can be seen working, first one after
another, then all at once.
"""
import argparse
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
import look  # noqa: E402
from kit import FPS  # noqa: E402

OUT_DIR = PROJECT_ROOT / "work" / "explainer-pilot"
SECONDS = 24.0
DIE = (-0.2, 0.1, 0.52)      # centre of the die surface, in card space
DIE_W = 0.90


def f(seconds):
    return max(1, round(seconds * FPS))


def build():
    path = [
        (0.0, (7.6, -10.2, 5.8), (0.0, 0.0, 0.9)),
        (3.0, (4.6, -7.0, 4.2), (-0.2, 0.1, 0.9)),
        (7.0, (1.7, -3.0, 2.0), (-0.2, 0.1, 0.62)),
        (11.0, (0.45, -1.15, 1.10), (-0.2, 0.1, 0.55)),
        (15.0, (0.10, -0.74, 0.86), (-0.2, 0.1, 0.54)),
        (SECONDS, (-0.66, -0.50, 0.80), (-0.16, 0.16, 0.54)),
    ]
    st = look.dark_stage(SECONDS, path, lens=35.0, fstop=9.0)
    F = st.frames

    # light: a warm key from frame-right, a cool rim from behind, a small top light on the die
    look.soft_light("key", (9.0, -4.0, 7.0), (0, 0, 0.5), 650.0, (1.0, 0.80, 0.62), size=7.0)
    look.soft_light("rim", (-8.0, 7.0, 5.0), (0, 0, 0.5), 1100.0, (0.45, 0.70, 1.0), size=6.0)
    look.soft_light("die-top", (DIE[0] - 0.4, DIE[1] + 0.5, 1.5), DIE, 2.2, (0.55, 0.75, 1.0), size=1.2)
    kit.box("bench", (0, 0, -0.06), (60, 60, 0.1), kit.mat("look-bench", (0.012, 0.014, 0.018), roughness=0.8),
            bevel=0)

    card = hardware.graphics_card(chip_text="GPU")
    kit.spin(card["rotor"], F, 22.0)
    # the generic die is swapped for one that can be flown over
    for ob in [o for o in bpy.data.objects if o.name.startswith("card-gpu-die")]:
        bpy.data.objects.remove(ob, do_unlink=True)
    waves = 8
    core_mats = [look.neon(f"core-wave{w}", look.WARM, 0.12, base=(0.10, 0.045, 0.012)) for w in range(waves)]
    city = hardware.core_city(
        "city", DIE, DIE_W, n=32, waves=waves, core_mats=core_mats,
        trace_x=look.signal_material("trace-x", F, axis="X", spacing=0.16, speed=0.20, lanes=1 / 0.028),
        trace_y=look.signal_material("trace-y", F, axis="Y", spacing=0.21, speed=0.16, lanes=1 / 0.028))

    # the take-apart, timed so each layer leaves just before the lens arrives
    kit.move(card["fan"], f(2.0), f(4.6), (-3.2, 3.4, 3.0))
    kit.move(card["heatsink"], f(2.6), f(5.4), (-3.2, 3.4, 1.9))
    lid = bpy.data.objects["card-gpu-g-lid"]
    kit.move(lid, f(6.6), f(9.2), (-1.6, 1.4, 0.9))

    # In this look the off-white parts would be the brightest thing in frame; they are
    # furniture here, so they drop back and leave the light to the parts that work.
    kit.base().node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.20, 0.21, 0.23, 1.0)

    # One core at a time: a single lit core steps along a row while the rest stay dark.
    pitch = city["pitch"]
    hop = kit.box("one-core", (0, 0, 0), (pitch * 0.66, pitch * 0.66, pitch * 1.05),
                  look.neon("one-core-glow", look.WARM, 5.0), bevel=0)
    x0, y0 = DIE[0] - DIE_W / 2 + pitch * 0.5, DIE[1] - DIE_W / 2 + pitch * 0.5
    steps = [(8 + k, 9) for k in range(12)] + [(19 - k, 10) for k in range(12)]
    hop.hide_render = True
    hop.keyframe_insert("hide_render", frame=f(12.3) - 1)
    hop.hide_render = False
    hop.keyframe_insert("hide_render", frame=f(12.3))
    for k, (i, j) in enumerate(steps):
        hop.location = (x0 + i * pitch, y0 + j * pitch, DIE[2] + pitch * 0.53)
        hop.keyframe_insert("location", frame=f(12.3) + k * 4)
    for fc in hop.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"
    hop.keyframe_insert("hide_render", frame=f(15.9) - 1)
    hop.hide_render = True
    hop.keyframe_insert("hide_render", frame=f(15.9))

    # All at once: every core fires on the same beat, with a one-frame shimmer between
    # diagonals so the field reads as many parts rather than one flashing slab.
    for w, m in enumerate(core_mats):
        keys = [(1, 0.10), (f(16.0), 0.10)]
        frame = f(16.2) + w
        while frame < F:
            keys += [(frame, 0.16), (frame + 3, 1.05), (frame + 7, 1.05), (frame + 15, 0.16)]
            frame += 22
        kit.pulse(m, keys)

    # tags: each names the layer the lens is about to pass
    look.pill(st, "Graphics card", (2.6, -1.4, 0.45), (0.72, 0.80), start=0.4, until=2.6)
    look.pill(st, "Fan and heatsink", (0.9, -1.2, 1.3), (0.30, 0.84), start=2.9, until=5.4,
              follow=card["heatsink"])
    look.pill(st, "GPU chip", (-0.2, 0.1, 0.80), (0.30, 0.78), start=5.8, until=8.6)
    look.pill(st, "Silicon die", (DIE[0] + 0.25, DIE[1] - 0.25, DIE[2] + 0.03), (0.70, 0.78), start=9.6,
              until=12.2)
    look.pill(st, "One core", (DIE[0] - 0.02, DIE[1] - 0.16, DIE[2] + 0.04), (0.30, 0.74), start=12.6, until=15.6)

    look.hud_text(st, "One core at a time", (0.5, 0.90), size=0.050, start=12.4, until=15.8)
    number = look.hud_text(st, "1", (0.5, 0.88), size=0.095, start=16.2, color=look.WARM, strength=2.4)
    look.hud_text(st, "cores working in the same instant", (0.5, 0.785), size=0.040, start=16.2)
    look.counter(number, 16.2, 19.6, lambda t: 1024 ** t)
    return st


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--still", help="comma-separated seconds: render half-resolution PNGs instead of the video")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--samples", type=int, default=32)
    args = ap.parse_args(argv)
    out = args.out if args.out.is_absolute() else PROJECT_ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    build()
    scene = bpy.context.scene
    if args.still:
        scene.render.resolution_percentage = 50
        for s in args.still.split(","):
            kit.common.render_still(f(float(s)), out / f"inside-gpu-{float(s):05.1f}s.png", samples=16)
        for line in kit.LAST.problems:
            print("FRAMING", line)
        print(f"stills in {time.time() - t0:.1f}s")
        return
    scene.eevee.taa_render_samples = args.samples
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    scene.render.ffmpeg.audio_codec = "NONE"
    scene.render.filepath = str(out / "inside-gpu.mp4")
    bpy.ops.render.render(animation=True)
    print(f"video in {time.time() - t0:.1f}s")


main()
