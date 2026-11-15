"""Integration test for the owned-surface layer: material cache, colour space, UVs,
and the named palette. Runs Blender in background mode the way
test_blender_techniques.py does and reads one JSON line back out of stdout.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from workflow.config import blender_executable

PROBE = ROOT / "tools" / "blender" / "techniques" / "surfaces_probe.py"
# cabin_deck shares the hull_panel photograph at an interior tint, so this list is longer
# than the number of tile files on disk; the probe counts those separately.
PALETTE_KEYS = ["cabin_deck", "hull_panel", "mli_gold", "mli_silver", "regolith", "suit_fabric"]


class TestOwnedSurfaces(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = subprocess.run(
            [str(blender_executable(ROOT)), "--background", "--factory-startup",
             "--python-exit-code", "1", "--python", str(PROBE)],
            capture_output=True, text=True, timeout=900)
        if proc.returncode != 0:
            raise AssertionError(
                f"blender exited {proc.returncode}\n{proc.stdout[-4000:]}\n{proc.stderr[-4000:]}")
        marker = [ln for ln in proc.stdout.splitlines() if ln.startswith("SURFACES_JSON ")]
        if not marker:
            raise AssertionError(f"no SURFACES_JSON line in output:\n{proc.stdout[-4000:]}")
        cls.data = json.loads(marker[0].split("SURFACES_JSON ", 1)[1])

    # --- material_textured() -------------------------------------------------
    def test_cache_returns_the_same_datablock(self):
        self.assertTrue(self.data["cache_shared"])

    def test_one_image_datablock_per_tile(self):
        self.assertEqual(self.data["image_blocks"], self.data["distinct_tiles"])

    def test_colour_map_is_not_flipped_to_non_color(self):
        self.assertTrue(self.data["colour_is_srgb"])

    def test_height_reuses_the_colour_node(self):
        self.assertTrue(self.data["height_from_albedo"])

    def test_metres_per_tile_becomes_the_mapping_scale(self):
        self.assertAlmostEqual(self.data["mapping_scale"], 1.0 / 0.6, places=6)

    # --- apply_cube_uv() -----------------------------------------------------
    def test_uv_layer_exists_after_cube_project(self):
        self.assertTrue(self.data["uv_layer"])

    def test_a_hidden_object_still_gets_uvs(self):
        self.assertTrue(self.data["hidden_uved"])

    def test_cube_project_leaves_visibility_as_it_was(self):
        self.assertTrue(self.data["hidden_kept_hidden"])

    def test_render_is_not_black(self):
        self.assertGreater(self.data["mean_pixel"], 0.02)

    # --- the palette ---------------------------------------------------------
    def test_palette_keys_are_the_shipped_surfaces(self):
        self.assertEqual(sorted(self.data["keys"]), PALETTE_KEYS)

    def test_every_palette_key_builds(self):
        self.assertEqual(self.data["failed"], [])

    def test_apply_surface_gives_uv_and_material(self):
        self.assertTrue(self.data["applied"])

    def test_palette_reuses_one_material_per_key(self):
        self.assertEqual(self.data["material_count"], len(PALETTE_KEYS))

    def test_surface_material_is_cached_between_calls(self):
        self.assertTrue(self.data["palette_cache_shared"])

    def test_tiles_all_exist_on_disk(self):
        self.assertEqual(self.data["missing_tiles"], [])


if __name__ == "__main__":
    unittest.main()
