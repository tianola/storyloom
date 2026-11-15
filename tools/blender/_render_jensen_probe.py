from pathlib import Path

import bpy

source_path = Path(__file__).with_name("jensen_huang_beats.py")
source = source_path.read_text(encoding="utf-8").replace("\nrender_all()\n", "\n")
namespace = {"__file__": str(source_path), "__name__": "jensen_huang_beats"}
exec(compile(source, str(source_path), "exec"), namespace)

name = "nvidia-hq"
namespace["make_beat"](name)
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE_NEXT"
scene.eevee.taa_render_samples = 32
scene.render.image_settings.file_format = "FFMPEG"
scene.render.ffmpeg.format = "MPEG4"
scene.render.ffmpeg.codec = "H264"
scene.render.ffmpeg.audio_codec = "AAC"
scene.render.threads_mode = "FIXED"
scene.render.threads = 8
scene.render.filepath = str(namespace["BEATS_DIR"] / f"{name}.mp4")
bpy.ops.render.render(animation=True)
