"""Print what Blender's GPU context actually sees after a card swap.

Headless EEVEE still needs a real GL context, so the only way to prove the new card is
being used (and not a Microsoft basic display driver falling back to software) is to ask
Blender itself.
"""
import bpy

prefs = bpy.context.preferences.system
for attr in ("gpu_backend", "gpu_vendor", "gpu_device", "opengl_gl_version",
             "shader_compile_threading", "compute_device_type"):
    print(f"{attr}: {getattr(prefs, attr, '<absent>')}")

cyc = bpy.context.preferences.addons.get("cycles")
if cyc:
    cprefs = cyc.preferences
    if hasattr(cprefs, "refresh_all_devices"):
        cprefs.refresh_all_devices()
    names = [(d.name, d.type) for d in cprefs.devices]
    print(f"cycles devices: {names or '<none>'}")
    print(f"cycles cpu devices: {[(d.name, d.type) for d in cprefs.cpu_devices]}")
print("BLENDER_GPU_PROBE_DONE")
