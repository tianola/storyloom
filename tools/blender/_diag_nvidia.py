from pathlib import Path
import bpy

source_path = Path(__file__).with_name("jensen_huang_beats.py")
source = source_path.read_text(encoding="utf-8").replace("\nrender_all()\n", "\n")
namespace = {"__file__": str(source_path), "__name__": "jensen_huang_beats"}
exec(compile(source, str(source_path), "exec"), namespace)
namespace["make_beat"]("nvidia-hq")
scene = bpy.context.scene
scene.frame_set(1)
cam = scene.camera
print("CAMERA", tuple(round(x, 3) for x in cam.location), tuple(round(x, 3) for x in cam.rotation_euler))
for obj in scene.objects:
    if obj.type in {"MESH", "CAMERA", "LIGHT"}:
        print("OBJECT", obj.name, obj.type, tuple(round(x, 3) for x in obj.location), tuple(round(x, 3) for x in obj.dimensions))
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = str(namespace["PROJECT_ROOT"] / "work" / "jensen-huang" / "qc" / "nvidia-diagnostic.png")
bpy.ops.render.render(write_still=True)
