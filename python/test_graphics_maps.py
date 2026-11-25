"""map_plan: schematic tag required, routes draw progressively."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_graphics_support import SMALL, TOKENS, ink_bbox  # noqa: E402

import numpy as np  # noqa: E402

from tools.graphics import get  # noqa: E402
from tools.graphics.common import hex_rgb  # noqa: E402
from tools.graphics.presets import PRESETS, get_preset  # noqa: E402


def route_extent(img, colour):
    a = np.asarray(img)
    hit = np.all(a[..., :3] == np.array(hex_rgb(TOKENS["palette"][colour])), axis=-1)
    hit[300:, :] = False  # ignore the legend strip
    xs = np.nonzero(hit.any(axis=0))[0]
    return (xs.min(), xs.max()) if len(xs) else None


class MapPlan(unittest.TestCase):
    def test_schematic_false_or_missing_is_refused(self):
        _, spec = get_preset("ward-plan-routes")
        spec["schematic"] = False
        with self.assertRaises(ValueError) as cm:
            get("map_plan").frame_at(spec, 0, SMALL)
        self.assertIn("schematic", str(cm.exception))
        del spec["schematic"]
        with self.assertRaises(ValueError):
            get("map_plan").frame_at(spec, 0, SMALL)

    def test_tag_is_always_drawn_even_on_an_empty_plan(self):
        img = get("map_plan").frame_at({"schematic": True}, 0, SMALL)
        self.assertIsNotNone(ink_bbox(img, TOKENS["palette"]["paper"]))
        ink = np.all(np.asarray(img)[..., :3] == np.array(hex_rgb(TOKENS["palette"]["ink"])), axis=-1)
        self.assertGreater(int(ink.sum()), 200)

    def test_route_is_drawn_progressively_with_arrowhead(self):
        _, spec = get_preset("ward-plan-routes")
        p = get("map_plan")
        none = route_extent(p.frame_at(spec, 0.2, SMALL), "danger")
        half = route_extent(p.frame_at(spec, 0.3 + 1.2, SMALL), "danger")
        full = route_extent(p.frame_at(spec, 3.0, SMALL), "danger")
        self.assertIsNone(none)
        self.assertLess(half[1], full[1])
        self.assertGreater(half[1], half[0] + 100)

    def test_second_route_waits_for_its_own_build(self):
        _, spec = get_preset("ward-plan-routes")
        p = get("map_plan")
        self.assertIsNone(route_extent(p.frame_at(spec, 2.9, SMALL), "cool"))
        self.assertIsNotNone(route_extent(p.frame_at(spec, 4.0, SMALL), "cool"))

    def test_preset_is_a_long_ward_with_beds_and_both_routes(self):
        prim, spec = PRESETS["ward-plan-routes"]
        self.assertEqual(prim, "map_plan")
        self.assertGreaterEqual(len([r for r in spec["rooms"] if r.get("minor")]), 20)
        self.assertEqual([r["label"] for r in spec["routes"]], ["old route", "quieter route"])
        self.assertTrue(spec["schematic"])
        # presets hand out copies: editing one must not edit the registry
        _, mine = get_preset("ward-plan-routes")
        mine["routes"].clear()
        self.assertEqual(len(PRESETS["ward-plan-routes"][1]["routes"]), 2)


if __name__ == "__main__":
    unittest.main()
