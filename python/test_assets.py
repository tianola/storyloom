"""The pure half of tools/blender/models/assets.py: material rules, asset paths, the HDRI plan."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "blender" / "models"))
import assets as A  # noqa: E402  (imports without bpy)


class Rules(unittest.TestCase):
    def test_real_material_names(self):
        for name, tex in [("cobbles", "cobblestone_floor_01"), ("cobbles.001", "cobblestone_floor_01"),
                          ("asy-cobbles", "cobblestone_floor_01"), ("town-wall3", "rough_plaster_03"),
                          ("town-roof1", "roof_tiles"), ("akh-wall", "plaster_brick_pattern"),
                          ("akh-court", "herringbone_brick"), ("asy-wall", "castle_brick_07"),
                          ("anat-wall", "castle_brick_07"), ("ward-floor", "dark_wooden_planks"),
                          ("ward-wall", "rough_plaster_03"), ("room-wood", "dark_wooden_planks")]:
            rule = A.rule_for(name)
            self.assertIsNotNone(rule, name)
            self.assertEqual(rule.texture, tex, name)

    def test_unmatched_and_emissive_stay_plain(self):
        for name in ("room-wall0", "room-pane", "window-warm", "kit-base", "ward-corridor", "bird", "ground-earth",
                     "goods-apples", "town-wall", "", None):
            self.assertIsNone(A.rule_for(name), name)

    def test_custom_rules(self):
        rules = [A.Rule(r"^x$", "roof_tiles", 1.0, 0.5)]
        self.assertEqual(A.rule_for("x", rules).texture, "roof_tiles")
        self.assertIsNone(A.rule_for("cobbles", rules))

    def test_every_rule_is_sane(self):
        for r in A.RULES:
            self.assertIn(r.texture, A.MEAN_LUM)
            self.assertTrue(0.1 <= r.influence <= 0.7, r)
            self.assertTrue(0.5 <= r.scale <= 5.0, r)
        self.assertAlmostEqual(A.gain_for("roof_tiles") * A.MEAN_LUM["roof_tiles"], 1.0)


class Paths(unittest.TestCase):
    def test_missing_is_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(A.texture_files("roof_tiles", tmp))
            self.assertIsNone(A.hdri_path("hospital_room", tmp))
            self.assertIsNone(A.model_path("Lantern_01", tmp))

    def test_found_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp) / "textures" / "roof_tiles"
            t.mkdir(parents=True)
            (t / "roof_tiles_diff_1k.jpg").write_bytes(b"x")
            files = A.texture_files("roof_tiles", tmp)
            self.assertEqual(files["diff"].name, "roof_tiles_diff_1k.jpg")
            self.assertIsNone(files["rough"])
            self.assertIsNone(files["nor"])
            (t / "roof_tiles_rough_1k.jpg").write_bytes(b"x")
            self.assertIsNotNone(A.texture_files("roof_tiles", tmp)["rough"])
            h = Path(tmp) / "hdris" / "hospital_room"
            h.mkdir(parents=True)
            (h / "hospital_room_1k.hdr").write_bytes(b"x")
            self.assertEqual(A.hdri_path("hospital_room", tmp).name, "hospital_room_1k.hdr")

    def test_downloaded_assets_match_the_rules(self):
        # the folder itself is committed (manifest.json), so "is it a directory" said nothing
        from toolchain import require_dir_content
        require_dir_content(A.ASSET_ROOT, "assets/polyhaven")
        for r in A.RULES:
            self.assertIsNotNone(A.texture_files(r.texture), r.texture)
        for kind, table in A.HDRI_PLAN.items():
            for hid, _ in table.values():
                if hid:
                    self.assertIsNotNone(A.hdri_path(hid), hid)
        for m in ("Lantern_01", "wicker_basket_01", "wooden_crate_01", "wooden_barrels_01", "wooden_bucket_01",
                  "wooden_candlestick", "vintage_oil_lamp", "wooden_bookshelf_worn", "painted_wooden_shelves",
                  "painted_wooden_nightstand", "ceramic_vase_01"):
            self.assertIsNotNone(A.model_path(m), m)


class HdriPlan(unittest.TestCase):
    def test_streets(self):
        self.assertEqual(A.hdri_plan("street", "dusk"), ("belfast_sunset_puresky", 0.40, 0.40))
        self.assertEqual(A.hdri_plan("street", "dawn")[0], "farmland_overcast")
        self.assertEqual(A.hdri_plan("street", "day")[0], "farmland_overcast")
        self.assertIsNone(A.hdri_plan("street", "night"))

    def test_fades(self):
        self.assertEqual(A.hdri_plan("street", "dusk>night"), ("belfast_sunset_puresky", 0.40, 0.0))
        hid, a, b = A.hdri_plan("street", "night>dawn")
        self.assertEqual((hid, a, b), ("farmland_overcast", 0.0, 0.30))

    def test_ward_and_asylum(self):
        self.assertEqual(A.hdri_plan("ward", "day")[0], "hospital_room")
        self.assertLess(A.hdri_plan("ward", "night")[1], A.hdri_plan("ward", "day")[1])
        self.assertIsNone(A.hdri_plan("asylum", "night"))
        self.assertIsNone(A.hdri_plan("nowhere", "day"))


if __name__ == "__main__":
    unittest.main()
