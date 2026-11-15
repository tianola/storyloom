import argparse
import json
import os
import sys

# Ensure project root is in path when invoked by Blender CLI
sys.path.insert(0, os.getcwd())

try:
    import bpy
except ImportError:
    bpy = None

from tools.blender.utils_purge import purge_orphan_data_blocks
from tools.utils.logger import get_logger

logger = get_logger("BlenderRenderWorker")

def configure_render_engine(samples: int = 64, resolution_x: int = 1920, resolution_y: int = 1080):
    if bpy is None:
        return
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x = resolution_x
    scene.render.resolution_y = resolution_y
    scene.render.image_settings.file_format = 'PNG'

def render_beat(beat_data: dict, output_dir: str):
    beat_id = beat_data.get("beat_id", "unknown")
    output_path = os.path.join(output_dir, f"{beat_id}.png")
    os.makedirs(output_dir, exist_ok=True)

    logger.info(f"Starting render for beat {beat_id} -> {output_path}")
    if bpy is not None:
        configure_render_engine(
            samples=beat_data.get("samples", 64),
            resolution_x=beat_data.get("res_x", 1920),
            resolution_y=beat_data.get("res_y", 1080)
        )
        bpy.context.scene.render.filepath = output_path
        bpy.ops.render.render(write_still=True)
        purge_orphan_data_blocks()
    else:
        # Fallback mock output if run outside Blender CLI for CI/testing
        with open(output_path, "wb") as f:
            f.write(b"MOCK_PNG_DATA")
    logger.info(f"Completed render for beat {beat_id}")
    return output_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Headless Blender Beat Renderer")
    parser.add_argument("--payload", required=True, help="JSON payload string")
    parser.add_argument("--output-dir", default="output/frames", help="Output directory")
    args = parser.parse_args()

    data = json.loads(args.payload)
    render_beat(data, args.output_dir)
