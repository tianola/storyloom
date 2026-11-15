"""Render one beat at an arbitrary resolution into a scratch directory.

The beat script hardcodes both its output directory and 1280x720, so a resolution
benchmark otherwise overwrites production frames and rewrites the beat mp4. This wrapper
rebinds the two module globals the beat actually reads — `setup_scene` (resolution) and
`SHOT_FRAMES` (length) — and calls the beat with its own output path, so nothing outside
the scratch directory is touched.

    ARTEMIS_BENCH_RES=1920x1080 ARTEMIS_BENCH_FRAMES=150 \
      blender -b -P tools/blender/bench_beat.py

Nothing here is production: it exists to measure a GPU, and its output is a log and a
throwaway mp4.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy  # noqa: E402
import artemis_beats as mod  # noqa: E402

RES = os.environ.get("ARTEMIS_BENCH_RES", "1920x1080")
FRAMES = int(os.environ.get("ARTEMIS_BENCH_FRAMES", "150"))
BEAT = os.environ.get("ARTEMIS_BENCH_BEAT", "sls_launch")
OUT = Path(os.environ.get(
    "ARTEMIS_BENCH_OUT",
    str(mod.PROJECT_ROOT / "work/episode-artemis-ii/qc/bench"))).resolve()
W, H = (int(v) for v in RES.lower().replace("×", "x").split("x"))

real_setup = mod.setup_scene


def setup_scene(*args, **kwargs):
    kwargs.pop("resolution_x", None)
    kwargs.pop("resolution_y", None)
    rv = real_setup(*args, **kwargs)
    scene = bpy.context.scene
    scene.render.resolution_x = W
    scene.render.resolution_y = H
    scene.render.resolution_percentage = 100
    print(f"BENCH res={W}x{H} samples={scene.eevee.taa_render_samples} "
          f"frames={mod.SHOT_FRAMES} engine={scene.render.engine}", flush=True)
    return rv


mod.setup_scene = setup_scene
mod.STILL_ONLY = False
mod.SHOT_FRAMES = FRAMES

OUT.mkdir(parents=True, exist_ok=True)
beat_fn = getattr(mod, f"beat_{BEAT}")
print(f"BENCH beat={BEAT} -> {OUT}", flush=True)
beat_fn(OUT)
print("BENCH DONE", flush=True)
