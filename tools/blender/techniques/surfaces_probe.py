"""Throwaway harness for python/test_blender_surfaces.py. Prints SURFACES_JSON.

Exercises material_textured(), apply_cube_uv() and the named palette in one Blender
startup, because each startup costs more than the checks themselves.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[3]
for p in (ROOT / "tools" / "blender", ROOT / "tools" / "blender" / "techniques"):
    sys.path.insert(0, str(p))
from common import add_box, add_camera, add_sun_light, setup_scene, setup_world  # noqa: E402

TILES = ROOT / "media" / "pbr"
OUT = ROOT / "work" / "probe-realism" / "renders" / "surfaces-probe.png"


def main() -> int:
    from common import apply_cube_uv, material_textured
    from surfaces import SURFACES, apply_surface, surface_material

    setup_scene(fps=30, frame_start=1, frame_end=1, resolution_x=320, resolution_y=180)
    setup_world(color=(0.010, 0.013, 0.020, 1.0), strength=0.30)

    # The palette's own hull tile, not a filename written here: this probe counts one image
    # datablock per distinct tile, and a hardcoded path that the palette has since moved on
    # from loads a sixth file and reads as a duplicate-datablock bug.
    hull_tile = Path(SURFACES["hull_panel"]["tile"])
    a = material_textured("probe_hull", hull_tile,
                          metres_per_tile=1.8, metallic=0.35, roughness=0.42, bump=0.28)
    b = material_textured("probe_hull_dup", hull_tile,
                          metres_per_tile=1.8, metallic=0.35, roughness=0.42, bump=0.28)
    soil = material_textured("probe_soil", Path(SURFACES["regolith"]["tile"]),
                             metres_per_tile=0.6, roughness=0.95, bump=0.60)

    def strip_uv(ob):
        # A fresh primitive already carries a default UVMap, so asserting on
        # `uv_layers` proves nothing unless the layer is removed first.
        for layer in list(ob.data.uv_layers):
            ob.data.uv_layers.remove(layer)

    box = add_box("probe_box", (0.0, 0.0, 0.5), (1.0, 1.0, 1.0), a)
    strip_uv(box)
    apply_cube_uv([box])

    # Production beats hide a stage or a cutaway wall before rendering it.
    failed = []
    hidden = add_box("probe_hidden", (0.0, -3.0, 0.5), (1.0, 1.0, 1.0), b)
    hidden.hide_set(True)
    hidden.hide_render = True
    strip_uv(hidden)
    try:
        apply_cube_uv([hidden])
        hidden_uved = bool(hidden.data.uv_layers)
    except Exception as exc:
        hidden_uved = False
        failed.append(f"hidden object: {type(exc).__name__}: {exc}")
    hidden_kept_hidden = hidden.hide_get() and hidden.hide_render

    # The palette half: one box per named surface.
    objs, missing = [], []
    for i, key in enumerate(sorted(SURFACES)):
        tile = Path(SURFACES[key]["tile"])
        if not tile.exists():
            missing.append(tile.name)
        ob = add_box(f"pal_{key}", (i * 1.6 - 3.2, 2.6, 0.5), (1.0, 1.0, 1.0))
        strip_uv(ob)
        try:
            apply_surface(ob, key)
            objs.append(ob)
        except Exception as exc:
            failed.append(f"{key}: {type(exc).__name__}: {exc}")
    applied = bool(objs) and all(o.data.uv_layers and o.data.materials for o in objs)

    add_camera("cam", (4.4, -5.2, 2.6), Vector((0.0, 0.6, 0.5)), lens=42.0)
    add_sun_light("sun", (-7.0, -5.0, 9.0), 3.4, angle=math.radians(4.0))
    bpy.context.scene.eevee.taa_render_samples = 8
    OUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.scene.render.filepath = str(OUT)
    bpy.ops.render.render(write_still=True)

    px = bpy.data.images.load(str(OUT), check_existing=False)
    buf = list(px.pixels[:])
    stride = max(1, (px.size[0] * px.size[1]) // 4000) * 4
    mean = sum(buf[0::stride]) / len(buf[0::stride])

    nodes = soil.node_tree.nodes
    bsdf = nodes["Principled BSDF"]
    texes = [n for n in nodes if n.bl_idname == "ShaderNodeTexImage"]
    nlink = bsdf.inputs["Normal"].links
    bump_node = nlink[0].from_node if nlink else None
    height = (bump_node.inputs["Height"].links[0].from_node
              if bump_node and bump_node.inputs["Height"].links else None)
    height_source = (height.inputs["Color"].links[0].from_node
                     if height and height.inputs["Color"].links else None)
    mapping = [n for n in nodes if n.bl_idname == "ShaderNodeMapping"][0]
    loaded = {i.name for i in bpy.data.images if i.name.startswith(TILES.name)
              or str(i.filepath_raw).replace("\\", "/").endswith(".webp")}

    report = {
        "cache_shared": a.name == b.name,
        # Distinct tile *files*, not len(SURFACES): two palette entries may legitimately
        # share one photograph at different tints — cabin_deck is hull_panel read as an
        # unbleached interior instead of a sunlit exterior. Counting palette keys here
        # would call that a duplicate-datablock bug.
        "distinct_tiles": len({Path(v["tile"]).name for v in SURFACES.values()}),
        "image_blocks": len(loaded),
        "colour_is_srgb": texes[0].image.colorspace_settings.name == "sRGB",
        # The invariant is that the height channel feeds off the *same* Image Texture
        # node as the albedo — a second node means a second image datablock, and marking
        # it Non-Color would desaturate the surface.
        "height_from_albedo": bool(bump_node)
                              and bump_node.bl_idname == "ShaderNodeBump"
                              and bool(height) and height.bl_idname == "ShaderNodeRGBToBW"
                              and bool(height_source)
                              and height_source.bl_idname == "ShaderNodeTexImage"
                              and height_source.name == texes[0].name,
        "mapping_scale": mapping.inputs["Scale"].default_value[0],
        "uv_layer": bool(box.data.uv_layers),
        "hidden_uved": hidden_uved,
        "hidden_kept_hidden": hidden_kept_hidden,
        "mean_pixel": mean,
        "keys": sorted(SURFACES),
        "failed": failed,
        "missing_tiles": missing,
        "applied": applied,
        "material_count": len({o.data.materials[0].name for o in objs if o.data.materials}),
        "palette_cache_shared": surface_material("regolith").name
                                == surface_material("regolith").name,
    }
    print("SURFACES_JSON " + json.dumps(report), flush=True)
    return 1 if failed or missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
