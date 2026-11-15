"""Named surfaces for the 3D beats: one entry per look, tuned against the probe.

metres_per_tile is world scale, not a magic number — apply_cube_uv makes one UV unit
one metre, so a tile of 0.6 m covers 0.6 m of ground. The probe found that anything
above roughly 2 m per tile showed no detail at all, and that a tile with a baked
shadow reads as a second, wrong shadow once Blender lights the object.

Every tile here is project-owned and Apache-2.0 generated; see
media/pbr/LICENSES.md for the model, prompt and seed behind each one.

The three hardware tiles are the repaired derivatives from tools/tile_seams.py, not the
generated files: measured across the wrap, mli-silver jumped 117/255 and hull-panel 53 against
their own adjacent-column step of 8.7 and 1.7, so every wrapped body drew a hard grid line —
the loudest single reason Orion read as a knit sweater and the SLS casings as streaked.
regolith and suit_fabric wrap at about their own local contrast (24 against 16, 3 against 0.4)
and are shipped exactly as generated.
"""
from pathlib import Path

from common import apply_cube_uv, material_textured

TILES = Path(__file__).resolve().parents[3] / "media" / "pbr"

SURFACES = {
    # Regolith is the darkest natural surface humanity has measured — a grey-brown dust at
    # roughly 8% albedo, not snow. Measured against that, the tile arrived darker still:
    # its linear mean is 0.047 and its darkest five percent sit at 0.001, so tinting it by
    # 0.34 as the first pass did put the whole ground at 0.016 — charcoal, and the lunar
    # beats rendered a black floor under white hardware. The tint was never the problem.
    # A multiply cannot lift a floor, so `levels` remaps [0, 0.14] of the tile's own range
    # onto [0.085, 0.40]: the dark end becomes mare basalt instead of a void, the median
    # lands at 0.17 where mature soil actually sits, and the tint is only a warm cast.
    "regolith": dict(tile=TILES / "regolith-s214.webp", metres_per_tile=0.6,
                     metallic=0.0, roughness=0.98, bump=0.70, bump_distance=0.024,
                     saturate=0.62, tint=(1.00, 0.975, 0.945),
                     levels=(0.0, 0.14, 0.020, 0.40)),
    "hull_panel": dict(tile=TILES / "hull-panel-s307-seam.webp", metres_per_tile=0.7,
                       metallic=0.35, roughness=0.42, bump=0.28, bump_distance=0.003,
                       saturate=0.45, tint=(0.86, 0.86, 0.85)),
    # The same panel tile, but the inside of a pressurised volume is not its skin. Out in
    # open space a bright machined panel is lit by one sun and reads correctly; inside a
    # cabin it is the largest area in the shot and four lamps hit it from every side, so
    # the outer-vehicle tint rendered the whole interior as the inside of a lamp shade.
    # Unbleached Nomex over the panel, not aluminium: dark, non-metallic, and it holds a
    # near/far gradient instead of flattening the room.
    "cabin_deck": dict(tile=TILES / "hull-panel-s307-seam.webp", metres_per_tile=0.7,
                       metallic=0.0, roughness=0.85, bump=0.30, bump_distance=0.0025,
                       saturate=0.35, tint=(0.30, 0.30, 0.32), specular=0.15),
    # Multi-layer insulation is a *bag* of foil layers, quilted and sagging. The quilt
    # pattern is right at this tile scale but the relief was not: at bump 0.42 / 8 mm the
    # tile's weave dominated the shading and every wrapped body read as knitted metal.
    # Real MLI catches the sun as broad, slowly changing creases with dark seams between
    # them, so the tile is allowed to tint but barely to bend the normal — the buckling
    # that sells it now comes from real geometry in detail.surface_relief().
    "mli_gold": dict(tile=TILES / "mli-kapton-s101-seam.webp", metres_per_tile=1.0,
                     metallic=0.62, roughness=0.32, bump=0.16, bump_distance=0.0018),
    "mli_silver": dict(tile=TILES / "mli-silver-s523-seam.webp", metres_per_tile=0.8,
                       metallic=0.45, roughness=0.38, bump=0.14, bump_distance=0.0015,
                       saturate=0.85),
    # The tile came out of the generator at linear (0.978, 0.231, 0.000) — a red channel
    # brighter than the gold MLI blanket (0.838) and brighter than the hull panel (0.583),
    # which is how four crew figures rendered as the loudest objects in the cabin and read
    # as a toy. A real flame-orange pressure garment sits near (0.51, 0.13, 0.03). Desaturate
    # first, then drop the value with the tint: at saturate 0.72 the hue went muddy-tan and
    # the suits read as skin, so the saturation stays high and only the value comes down.
    "suit_fabric": dict(tile=TILES / "suit-fabric-s419.webp", metres_per_tile=0.25,
                        metallic=0.0, roughness=0.78, bump=0.22, bump_distance=0.0015,
                        saturate=0.85, tint=(0.52, 0.46, 0.44), specular=0.10),
}


def surface_material(key):
    """The shared material for a named surface; repeated calls return the same block."""
    params = dict(SURFACES[key])
    tile = params.pop("tile")
    return material_textured(f"surface_{key}", tile, **params)


def apply_surface(obj_or_objs, key, cube_size=1.0):
    """Give a solid object its named surface. Call before any parent-scale packing.

    Only for solid hardware and ground. Emissive, volume, plasma, atmosphere, cloud,
    transparent-shell and glass materials stay on their procedural path — a tile on a
    plasma shell is a regression, not an improvement.
    """
    objs = obj_or_objs if isinstance(obj_or_objs, (list, tuple)) else [obj_or_objs]
    mat = surface_material(key)
    apply_cube_uv(list(objs), cube_size=cube_size)
    for ob in objs:
        ob.data.materials.clear()
        ob.data.materials.append(mat)
    return mat
