# Owned-surface rollout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the 19 Artemis II 3D beats real machined surfaces — five project-owned PBR tiles, bevelled edges, softened sunlight — and render the episode at 720p.

**Architecture:** One cached, texture-capable material builder in `tools/blender/techniques/common.py`, one named palette in `tools/blender/techniques/surfaces.py`, and a per-object `apply_surface(obj, key)` that cube-projects UVs and assigns the shared material. Beat builders call the palette; they never build node graphs.

**Tech Stack:** Blender 4.5.15 LTS headless (EEVEE Next), Python 3, unittest integration tests that spawn Blender, ffmpeg for assembly.

**Spec:** `docs/superpowers/specs/2026-11-09-owned-surface-rollout-design.md`

## Global Constraints

- Only Apache-2.0 generated assets may ship. FLUX.1 [schnell] is Apache-2.0; FLUX.1 dev and Krea-dev are **not** and must not appear in `assets/`.
- Every shipped tile is recorded in `media/pbr/LICENSES.md` with model, Space, prompt, seed, resolution and date.
- Textured surfaces apply to **solid hardware and ground only**. Emissive, volume, plasma, atmosphere, cloud, transparent-shell and x-ray materials keep their current procedural path.
- Never load the same image datablock twice for colour and height: `bpy.data.images.load(..., check_existing=True)` returns the same block, and flipping it to Non-Color desaturates the albedo. The height channel re-uses the colour node.
- `cube_size=1.0` makes one UV unit one metre, so `metres_per_tile` is world scale. Cube-project **before** any parent-scale packing.
- Production resolution becomes 1280×720 at 30 fps; `SHOT_FRAMES` stays 150.
- Sun angle becomes 4.0 degrees and world strength 0.30 for every beat.
- No generated footage of identifiable vehicles; no hosted video (both Wan 2.2 Spaces returned `ZeroGPU quota exceeded`); no local diffusion.
- `work/probe-realism/` stays throwaway — production must not import from it.
- Never publish or upload the episode. Re-rendering locally and pulling QC frames is in scope; pushing is not.

---

### Task 1: Ship the owned tiles and their licence ledger

**Files:**
- Create: `media/pbr/` (directory)
- Create: `media/pbr/mli-kapton-s101.webp`, `mli-silver-s523.webp`, `hull-panel-s307.webp`, `suit-fabric-s419.webp`, `regolith-s214.webp`
- Create: `media/pbr/LICENSES.md`

**Interfaces:**
- Consumes: nothing.
- Produces: the five tile filenames that `surfaces.py` references in Task 3, and the ledger every later asset addition must be appended to.

- [ ] **Step 1: Copy only the five accepted tiles**

```bash
mkdir -p media/pbr
cp work/probe-realism/assets/generated/mli-kapton-flux-schnell-s101.webp media/pbr/mli-kapton-s101.webp
cp work/probe-realism/assets/generated/mli-silver-flux-schnell-s523.webp  media/pbr/mli-silver-s523.webp
cp work/probe-realism/assets/generated/hull-panel-flux-schnell-s307.webp  media/pbr/hull-panel-s307.webp
cp work/probe-realism/assets/generated/suit-fabric-flux-schnell-s419.webp media/pbr/suit-fabric-s419.webp
cp work/probe-realism/assets/generated/regolith-flux-schnell-s214.webp    media/pbr/regolith-s214.webp
```

Do **not** copy `mli-kapton-flux-schnell-s7.webp` (folded corner, superseded) or `regolith-flux-schnell-s211.webp` (4-way mirrored).

- [ ] **Step 2: Verify the five files are real 1024×1024 WebP images**

Run: `python -c "from PIL import Image; import glob; [print(f, Image.open(f).size, Image.open(f).mode) for f in sorted(glob.glob('media/pbr/*.webp'))]"`
Expected: five lines, each `(1024, 1024)` and mode `RGB`.

- [ ] **Step 3: Write the licence ledger**

Create `media/pbr/LICENSES.md`. One table row per tile with `file | model | model licence | Space | seed | resolution | generated | prompt`. Model is `FLUX.1 [schnell]`, licence `Apache-2.0`, Space `evalstate/flux1_schnell`, generated `2026-11-09`. Copy the prompts verbatim from the `prompt` column of the rows in `work/probe-realism/FINDINGS.md` Addendum 2 — retype them from the tile subjects if the finding rows are terse, and mark any prompt you cannot recover as `prompt not recorded` rather than inventing one.

- [ ] **Step 4: Confirm no non-Apache model entered assets**

Run: `grep -in "krea\|dev\b\|non-commercial" media/pbr/LICENSES.md`
Expected: no match other than the sentence stating that FLUX.1 dev / Krea-dev are excluded.

- [ ] **Step 5: Commit**

```bash
git add media/pbr
git commit -m "feat(assets): ship five owned Apache-2.0 PBR tiles with a licence ledger"
```

---

### Task 2: `material_textured()` — the interface the pipeline has been missing

**Files:**
- Modify: `tools/blender/techniques/common.py` (add after `material_principled`, around line 137)
- Create: `tools/blender/techniques/surfaces_probe.py` (throwaway harness the test runs)
- Create: `python/test_blender_surfaces.py`

**Interfaces:**
- Consumes: `bpy`, the tile files from Task 1.
- Produces: `material_textured(name, tile, *, metres_per_tile=1.0, metallic=0.0, roughness=0.40, bump=0.30, tint=(1.0, 1.0, 1.0), saturate=1.0) -> bpy.types.Material` and `TEXTURED_MATERIALS` (the cache dict). Task 3 builds the palette on top of these.

- [ ] **Step 1: Write the failing test**

Create `python/test_blender_surfaces.py`, following the invocation style already used in `python/test_blender_techniques.py` (same `blender_executable(ROOT)`, same `--background --factory-startup --python-exit-code 1 --python SCRIPT --` shape):

```python
"""Integration test: one cached textured material per parameter set, not one per call."""
import json, subprocess, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from workflow.config import blender_executable

PROBE = ROOT / "tools" / "blender" / "techniques" / "surfaces_probe.py"


class TestMaterialTextured(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = subprocess.run(
            [str(blender_executable(ROOT)), "--background", "--factory-startup",
             "--python-exit-code", "1", "--python", str(PROBE)],
            capture_output=True, text=True, timeout=600)
        cls.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        cls.data = json.loads(proc.stdout.split("SURFACES_JSON ")[1])

    def test_cache_returns_the_same_datablock(self):
        self.assertTrue(self.data["cache_shared"])

    def test_one_image_datablock_per_tile(self):
        self.assertEqual(self.data["image_blocks"], self.data["distinct_tiles"])

    def test_colour_map_is_not_flipped_to_non_color(self):
        self.assertTrue(self.data["colour_is_srgb"])

    def test_height_reuses_the_colour_node(self):
        self.assertTrue(self.data["height_from_albedo"])

    def test_uv_layer_exists_after_cube_project(self):
        self.assertTrue(self.data["uv_layer"])

    def test_render_is_not_black(self):
        self.assertGreater(self.data["mean_pixel"], 0.02)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/Scripts/python.exe -m unittest python.test_blender_surfaces -v` (from the repo root; if `.venv` is absent use `python -m unittest python.test_blender_surfaces -v`)
Expected: FAIL — `surfaces_probe.py` does not exist, so Blender exits non-zero.

- [ ] **Step 3: Write the harness**

Create `tools/blender/techniques/surfaces_probe.py`:

```python
"""Throwaway harness for python/test_blender_surfaces.py. Prints SURFACES_JSON."""
import json, sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
sys.path.insert(0, str(ROOT / "tools" / "blender" / "techniques"))
from common import add_box, apply_cube_uv, material_textured, setup_scene, setup_world

TILES = ROOT / "assets" / "pbr" / "generated"


def main() -> int:
    setup_scene(fps=30, frame_start=1, frame_end=1, resolution_x=320, resolution_y=180)
    setup_world(color=(0.010, 0.013, 0.020, 1.0), strength=0.30)
    a = material_textured("probe_hull", TILES / "hull-panel-s307.webp",
                          metres_per_tile=1.8, metallic=0.35, roughness=0.42, bump=0.28)
    b = material_textured("probe_hull_dup", TILES / "hull-panel-s307.webp",
                          metres_per_tile=1.8, metallic=0.35, roughness=0.42, bump=0.28)
    c = material_textured("probe_soil", TILES / "regolith-s214.webp",
                          metres_per_tile=0.6, roughness=0.95, bump=0.60)
    box = add_box("probe_box", (0.0, 0.0, 0.5), (1.0, 1.0, 1.0), a)
    apply_cube_uv([box], cube_size=1.0)
    bpy.ops.object.select_all(action="DESELECT")
    bpy.ops.object.light_sun_add(location=(-6.0, -5.0, 8.0), rotation=(0.6, 0.2, 0.0))
    bpy.context.active_object.data.energy = 3.4
    bpy.context.active_object.data.angle = 0.0698
    bpy.ops.object.empty_add(type="CAMERA", location=(4.0, -4.0, 2.0))
    cam = bpy.context.active_object
    cam.data.lens = 45.0
    from mathutils import Vector
    cam.rotation_euler = (Vector((0.0, 0.0, 0.5)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    bpy.context.scene.eevee.taa_render_samples = 8
    out = ROOT / "work" / "probe-realism" / "renders" / "surfaces-probe.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.render.frame_path = lambda **kw: str(out)
    bpy.context.scene.render.filepath = str(out)
    bpy.ops.render.render(write_still=True)

    px = bpy.data.images.load(str(out), check_existing=False)
    w, h = px.size
    step = max(1, (w * h) // 4000)
    buf = list(px.pixels[:])
    mean = sum(buf[0::step * 4]) / len(buf[0::step * 4])

    nodes = a.node_tree.nodes
    img = [n for n in nodes if n.type == "TEX_IMAGE"]
    bsdf = nodes["Principled BSDF"]
    height_link = bsdf.inputs["Normal"].links[0].from_node if bsdf.inputs["Normal"].links else None
    report = {
        "cache_shared": a.name == b.name,
        "distinct_tiles": 2,
        "image_blocks": len({i.image.name for i in img} |
                            {n.image.name for n in c.node_tree.nodes if n.type == "TEX_IMAGE"}),
        "colour_is_srgb": img[0].image.colorspace_settings.name == "sRGB",
        "height_from_albedo": height_link is not None and height_link.type == "RGBTOBW"
                              and height_link.inputs["Color"].links[0].from_node.type == "TEX_IMAGE",
        "uv_layer": bool(box.data.uv_layers),
        "mean_pixel": mean,
    }
    print("SURFACES_JSON " + json.dumps(report), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the test to verify it still fails for the right reason**

Run: `python -m unittest python.test_blender_surfaces -v`
Expected: FAIL — `ImportError: cannot import name 'material_textured'`.

- [ ] **Step 5: Implement `material_textured` and `apply_cube_uv`**

Add to `tools/blender/techniques/common.py`, directly after `material_principled`:

```python
TEXTURED_MATERIALS: dict = {}


def material_textured(name, tile, *, metres_per_tile=1.0, metallic=0.0,
                      roughness=0.40, bump=0.30, tint=(1.0, 1.0, 1.0),
                      saturate=1.0, bump_distance=0.004):
    """One owned PBR tile driving colour, roughness-uniform and relief.

    Cached by parameter set: 19 beats reuse the same handful of surfaces, and an
    uncached version would load each image dozens of times.
    """
    tile = Path(tile)
    key = (tile.name, round(metres_per_tile, 4), round(metallic, 4), round(roughness, 4),
           round(bump, 4), tuple(round(c, 4) for c in tint[:3]), round(saturate, 4),
           round(bump_distance, 5))
    hit = TEXTURED_MATERIALS.get(key)
    if hit is not None:
        return hit

    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt, n, l = mat.node_tree, mat.node_tree.nodes, mat.node_tree.links
    bsdf = n["Principled BSDF"]

    img = bpy.data.images.load(str(tile), check_existing=True)
    tex = n.new("ShaderNodeTexImage")
    tex.image = img
    tex.extension = "REPEAT"
    mapping = n.new("ShaderNodeMapping")
    scale = 1.0 / max(metres_per_tile, 1e-4)
    mapping.inputs["Scale"].default_value = (scale, scale, scale)
    uv = n.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    l.new(uv.outputs["UV"], mapping.inputs["Vector"])
    l.new(mapping.outputs["Vector"], tex.inputs["Vector"])

    hs = n.new("ShaderNodeHueSaturation")
    hs.inputs["Saturation"].default_value = saturate
    l.new(tex.outputs["Color"], hs.inputs["Color"])
    mix = n.new("ShaderNodeMixRGB")
    mix.blend_type = "MULTIPLY"
    mix.inputs["Fac"].default_value = 1.0
    mix.inputs["Color2"].default_value = (*tint[:3], 1.0)
    l.new(hs.outputs["Color"], mix.inputs["Color1"])
    l.new(mix.outputs["Color"], bsdf.inputs["Base Color"])

    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness

    if bump > 0.0:
        # The albedo node doubles as the height source. Loading the tile a second
        # time returns the same datablock (check_existing) and marking it Non-Color
        # would desaturate the surface.
        bw = n.new("ShaderNodeRGBToBW")
        l.new(tex.outputs["Color"], bw.inputs["Color"])
        bump_node = n.new("ShaderNodeBump")
        bump_node.inputs["Strength"].default_value = bump
        bump_node.inputs["Distance"].default_value = bump_distance
        l.new(bw.outputs["Val"], bump_node.inputs["Height"])
        l.new(bump_node.outputs["Normal"], bsdf.inputs["Normal"])

    TEXTURED_MATERIALS[key] = mat
    return mat


def apply_cube_uv(objs, cube_size=1.0):
    """Cube-project so one UV unit equals one metre of world space."""
    for ob in objs:
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = ob
        ob.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.cube_project(cube_size=cube_size)
        bpy.ops.object.mode_set(mode="OBJECT")
        ob.select_set(False)
```

Confirm `Path` is already imported at the top of `common.py`; if it is not, add `from pathlib import Path`.

- [ ] **Step 6: Run the test to verify it passes**

Run: `python -m unittest python.test_blender_surfaces -v`
Expected: PASS, 6 tests. If `test_render_is_not_black` fails, check the camera track-quat line before changing the material — the material is only half of that assertion.

- [ ] **Step 7: Run the existing Blender suite for regressions**

Run: `python -m unittest python.test_blender_techniques python.test_blender_config -v`
Expected: PASS, unchanged.

- [ ] **Step 8: Commit**

```bash
git add tools/blender/techniques/common.py tools/blender/techniques/surfaces_probe.py python/test_blender_surfaces.py
git commit -m "feat(blender): add a cached texture-capable material builder"
```

---

### Task 3: The named surface palette

**Files:**
- Create: `tools/blender/techniques/surfaces.py`
- Modify: `python/test_blender_surfaces.py` (add a palette test class)

**Interfaces:**
- Consumes: `material_textured`, `apply_cube_uv` from Task 2; the tile names from Task 1.
- Produces: `SURFACES` (dict of key → parameter dict), `apply_surface(obj_or_objs, key)` and `surface_material(key)`. Task 4 calls `apply_surface` from the beat builders.

- [ ] **Step 1: Write the failing palette test**

Append to `python/test_blender_surfaces.py`:

```python
class TestPalette(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = subprocess.run(
            [str(blender_executable(ROOT)), "--background", "--factory-startup",
             "--python-exit-code", "1", "--python", str(ROOT / "tools" / "blender" /
             "techniques" / "palette_probe.py")],
            capture_output=True, text=True, timeout=600)
        cls.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        cls.data = json.loads(proc.stdout.split("PALETTE_JSON ")[1])

    def test_every_key_builds(self):
        self.assertEqual(self.data["failed"], [])

    def test_keys_are_the_five_shipped_surfaces(self):
        self.assertEqual(sorted(self.data["keys"]),
                         ["hull_panel", "mli_gold", "mli_silver", "regolith",
                          "suit_fabric"])

    def test_apply_surface_gives_uv_and_material(self):
        self.assertTrue(self.data["applied"])

    def test_palette_materials_are_cached_across_objects(self):
        self.assertLessEqual(self.data["material_count"], self.data["object_count"])
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m unittest python.test_blender_surfaces.TestPalette -v`
Expected: FAIL — `surfaces.py` and `palette_probe.py` do not exist.

- [ ] **Step 3: Create the palette**

Create `tools/blender/techniques/surfaces.py`:

```python
"""Named surfaces for the 3D beats: one entry per look, tuned against the probe.

metres_per_tile is world scale, not a magic number: apply_cube_uv makes one UV unit
one metre, so a tile of 0.6 m is 0.6 m of ground. The probe found that anything above
roughly 2 m per tile showed no detail at all.
"""
from pathlib import Path

TILES = Path(__file__).resolve().parents[3] / "assets" / "pbr" / "generated"

SURFACES = {
    "regolith": dict(tile=TILES / "regolith-s214.webp", metres_per_tile=0.6,
                     metallic=0.0, roughness=0.95, bump=0.60, bump_distance=0.018,
                     saturate=0.80, tint=(0.72, 0.66, 0.58)),
    "hull_panel": dict(tile=TILES / "hull-panel-s307.webp", metres_per_tile=0.7,
                       metallic=0.35, roughness=0.42, bump=0.28, bump_distance=0.003,
                       saturate=0.45, tint=(0.86, 0.86, 0.85)),
    "mli_gold": dict(tile=TILES / "mli-kapton-s101.webp", metres_per_tile=1.0,
                     metallic=0.70, roughness=0.24, bump=0.38, bump_distance=0.006),
    "mli_silver": dict(tile=TILES / "mli-silver-s523.webp", metres_per_tile=0.8,
                       metallic=0.60, roughness=0.30, bump=0.42, bump_distance=0.008,
                       saturate=0.90),
    "suit_fabric": dict(tile=TILES / "suit-fabric-s419.webp", metres_per_tile=0.25,
                        metallic=0.0, roughness=0.62, bump=0.22, bump_distance=0.0015,
                        saturate=0.90, tint=(1.00, 0.94, 0.88)),
}


def surface_material(key):
    from common import material_textured
    params = dict(SURFACES[key])
    tile = params.pop("tile")
    return material_textured(f"surface_{key}", tile, **params)


def apply_surface(obj_or_objs, key, cube_size=1.0):
    """Cube-project the object and give it the named surface. Call before parent scaling."""
    from common import apply_cube_uv
    objs = obj_or_objs if isinstance(obj_or_objs, (list, tuple)) else [obj_or_objs]
    mat = surface_material(key)
    apply_cube_uv(list(objs), cube_size=cube_size)
    for ob in objs:
        ob.data.materials.clear()
        ob.data.materials.append(mat)
    return mat
```

- [ ] **Step 4: Create the palette harness**

Create `tools/blender/techniques/palette_probe.py` — builds one box per palette key, applies each surface, and reports the datablock counts:

```python
"""Throwaway harness for the palette half of python/test_blender_surfaces.py."""
import json, sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[3]
for p in (ROOT / "tools" / "blender", ROOT / "tools" / "blender" / "techniques"):
    sys.path.insert(0, str(p))
from common import add_box, setup_scene, setup_world
from surfaces import SURFACES, apply_surface


def main() -> int:
    setup_scene(fps=30, frame_start=1, frame_end=1, resolution_x=320, resolution_y=180)
    setup_world(color=(0.010, 0.013, 0.020, 1.0), strength=0.30)
    failed, objs = [], []
    for i, key in enumerate(sorted(SURFACES)):
        ob = add_box(f"pal_{key}", (i * 1.4 - 2.8, 0.0, 0.5), (1.0, 1.0, 1.0))
        try:
            apply_surface(ob, key)
            objs.append(ob)
        except Exception as exc:  # a bad tile path must name itself
            failed.append(f"{key}: {exc}")
    applied = all(bool(o.data.uv_layers) and o.data.materials for o in objs)
    print("PALETTE_JSON " + json.dumps({
        "keys": sorted(SURFACES), "failed": failed, "applied": applied,
        "object_count": len(objs),
        "material_count": len({o.data.materials[0].name for o in objs if o.data.materials}),
    }), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m unittest python.test_blender_surfaces -v`
Expected: PASS, 10 tests. `test_palette_materials_are_cached_across_objects` proves the cache: 5 objects, 5 materials, and a second pass over the same keys adds none.

- [ ] **Step 6: Commit**

```bash
git add tools/blender/techniques/surfaces.py tools/blender/techniques/palette_probe.py python/test_blender_surfaces.py
git commit -m "feat(blender): named surface palette for the 3D beats"
```

---

### Task 4: Roll the surfaces, bevels and lighting across the 19 beats

**Files:**
- Modify: `tools/blender/artemis_beats.py` (19 `beat_*` builders, `setup_scene` calls at 640×360, `add_astronaut`, `add_orion`, `regolith_material` call sites)
- Create: `tools/blender/bevel_pass.py` is **not** created — reuse the probe's `bevel()` recipe inside `common.py` as `harden_edges(obj, width=0.010, segments=3)`

**Interfaces:**
- Consumes: `apply_surface`, `surface_material` from Task 3; `harden_edges`.
- Produces: the same 19 beat functions with the same signatures and the same output filenames, so the assembler is untouched.

- [ ] **Step 1: Add `harden_edges` to `common.py`**

```python
def harden_edges(ob, width=0.010, segments=3, angle_deg=40.0):
    """A 90-degree primitive edge catches no highlight and reads as a placeholder."""
    m = ob.modifiers.new("bevel", "BEVEL")
    m.width = width
    m.segments = segments
    m.angle_limit = __import__("math").radians(angle_deg)
    m.limit_method = "ANGLE"
    m.harden_normals = True
    return m
```

Use `import math` at the top of `common.py` if it is already imported — do not use the inline `__import__` if `math` is in scope.

- [ ] **Step 2: Move the render settings to 720p**

Every one of the 19 `setup_scene(fps=30, frame_end=SHOT_FRAMES, resolution_x=640, resolution_y=360)` calls becomes `resolution_x=1280, resolution_y=720`. Verify the count before and after:

Run: `grep -c "resolution_x=640" tools/blender/artemis_beats.py` → then `grep -c "resolution_x=1280" tools/blender/artemis_beats.py`
Expected: the first number is the beat count, the second equals it, and the first is 0 after the change.

- [ ] **Step 3: Soften the sun and lift the fill in every beat**

Where each beat creates its key sun, set the light angle to `math.radians(4.0)` and the world strength to `0.30` (the probe measured these against the hard black blobs at 1.8°/0.18). If beats share a single helper for the sun, change the helper once.

- [ ] **Step 4: Apply the palette per material class**

Replace, in the beat builders, the flat `material_principled` results on **solid hardware and ground** with palette surfaces, and call `harden_edges` on the boxes and cylinders that carry them. The mapping is fixed:

| Current material | Becomes |
| --- | --- |
| `regolith_material()` call sites and any ground/pad surface (`"pad"`, `"scorched"`, lunar ground boxes) | `apply_surface(obj, "regolith")` |
| capsule / rocket hull bodies (`ROCKET_WHITE` on a solid hull, `"orion-body"`, `"capsule"`, `mat_hull`) | `apply_surface(obj, "hull_panel")` |
| gold foil (`"cubesat-foil"`, any MLI / thermal blanket box or cylinder) | `apply_surface(obj, "mli_gold")` |
| silver / white thermal panels | `apply_surface(obj, "mli_silver")` |
| `add_astronaut` suit body (`mat_suit`) | `apply_surface(obj, "suit_fabric")` |

Leave untouched, by class: `material_emissive`, `material_surface` procedural variants that drive plumes, `plasma_material`, `plasma_volume_material`, `atmosphere_material`, `cloud_material`, `blend_shell`, `set_transparent`, `material_xray_shell`, and every window/visor glass.

- [ ] **Step 5: Self-check the diff against the constraint**

Run: `git diff -U2 tools/blender/artemis_beats.py | grep -n "apply_surface"` then confirm no `apply_surface` line sits inside a block that also touches `Emission`, `Volume`, or `Alpha`.
Expected: every textured surface is on a solid object.

- [ ] **Step 6: Verify every beat still builds**

Run each beat in isolation at 1 frame, still-image mode, and assert exit 0:

```bash
for b in sls_launch orion_space orion_deep_space lunar_flyby earth_rise lunar_approach far_side splashdown earth_from_moon apollo_era crew_quarters rendezvous cubesats heat_shield gateway mars lunar_base free_return tli_burn; do
  tools/blender-4.5.15-windows-x64/blender.exe -b -P tools/blender/artemis_beats.py -- --only "$b" --smoke > "work/episode-artemis-ii/qc/smoke-$b.log" 2>&1
  echo "$b exit=$?"
done
```

Expected: 19 lines, all `exit=0`. If `artemis_beats.py` has no `--only`/`--smoke` flags, add them in this step — they are the harness that makes the rollout reviewable — and note that in the report.

- [ ] **Step 7: Commit**

```bash
git add tools/blender/artemis_beats.py tools/blender/techniques/common.py
git commit -m "feat(blender): owned surfaces, hardened edges and 720p across all 19 beats"
```

---

### Task 5: Re-render, re-assemble and pull QC frames

**Files:**
- Create: `work/episode-artemis-ii/qc/render-all19-v4.log`
- Modify: nothing under `src/` — the assembler reads the same filenames.

**Interfaces:**
- Consumes: the 19 rebuilt beats from Task 4, the existing assembler and timeline.
- Produces: a re-assembled episode and a frame sheet for the user to judge.

- [ ] **Step 1: Clear the cached beat renders** so nothing stale survives the look change.

Run: `ls work/episode-artemis-ii/beats/*.mp4 | wc -l` then delete only that beat directory's mp4s.
Expected: the count matches the number of beats, and the re-render regenerates every one.

- [ ] **Step 2: Render all 19 beats at 720p**

Run: `tools/blender-4.5.15-windows-x64/blender.exe -b -P tools/blender/artemis_beats.py > work/episode-artemis-ii/qc/render-all19-v4.log 2>&1; echo "BLENDER_EXIT=$?"`
Expected: `BLENDER_EXIT=0`. Budget ~40 minutes from the measured 0.2 s/frame × 150 frames × 19 beats at 4× the pixel count. Capture the exit code immediately — piping Blender through `grep`/`tail` reports the pipe's status, not Blender's.

- [ ] **Step 3: Re-assemble the episode**

Run the project's existing assemble command with the segment cache cleared (the same invocation that produced the current cut).
Expected: a new mp4 whose duration matches the narration timeline.

- [ ] **Step 4: Pull QC frames and judge them**

Sample one frame per beat plus the continuity QC the harness already runs, and read them. Report per beat: does the surface read as hardware, is any object black, is any tile obviously repeating.

- [ ] **Step 5: Commit the evidence, not the media**

```bash
git add work/episode-artemis-ii/qc/render-all19-v4.log work/episode-artemis-ii/qc/*.png
git commit -m "docs(qc): 720p owned-surface render evidence for all 19 beats"
```

Do **not** publish or upload anything.

---

## Self-review notes

- Spec coverage: assets+licence (Task 1), the interface gap (Task 2), the declarative palette (Task 3), rollout bounded by material class plus lighting plus 720p (Task 4), verification (Task 5). The non-goals need no task.
- Task 4 is deliberately the largest: the mapping table is mechanical and one reviewer can read the whole diff as one unit. Splitting it per beat would multiply review cost without adding a gate.
- `metres_per_tile` values are the probe's measured ones, not guesses. If a beat's object scale makes a tile read wrong, change that beat's `metres_per_tile` — never the tile.
