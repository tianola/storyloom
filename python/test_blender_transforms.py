"""Regression test for common.add_box transform semantics.

See tools/blender/techniques/transforms_probe.py for why this exists: a shared helper
was baking the world position into the mesh because transform_apply's location and
rotation flags default to True, which silently moved every part whose caller set a
rotation afterwards to twice the angle it asked for.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from workflow.config import blender_executable

PROBE = ROOT / "tools" / "blender" / "techniques" / "transforms_probe.py"


class TestAddBoxTransforms(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from toolchain import require_blender
        require_blender()
        proc = subprocess.run(
            [str(blender_executable(ROOT)), "--background", "--factory-startup",
             "--python-exit-code", "1", "--python", str(PROBE)],
            capture_output=True, text=True, timeout=600)
        if proc.returncode != 0:
            raise AssertionError(
                f"blender exited {proc.returncode}\n{proc.stdout[-4000:]}\n{proc.stderr[-4000:]}")
        marker = [ln for ln in proc.stdout.splitlines() if ln.startswith("TRANSFORMS_JSON ")]
        if not marker:
            raise AssertionError(f"no TRANSFORMS_JSON line in output:\n{proc.stdout[-4000:]}")
        cls.data = json.loads(marker[0].split("TRANSFORMS_JSON ", 1)[1])

    def test_the_requested_position_survives_on_the_object(self):
        self.assertEqual(self.data["location"], self.data["wanted_location"])

    def test_only_the_scale_is_baked_into_the_mesh(self):
        self.assertEqual(self.data["scale"], [1.0, 1.0, 1.0])
        self.assertEqual(self.data["local_centre"], [0.0, 0.0, 0.0])
        self.assertEqual(self.data["local_extent"], [0.1, 0.55, 0.42])

    def test_rotating_afterwards_spins_the_part_in_place(self):
        """The bug: a baked-in position rotates about the world origin, not the part."""
        self.assertEqual(self.data["world_centre_after_rotate"], self.data["wanted_location"])

    def test_a_radial_placement_lands_at_the_angle_it_asked_for(self):
        self.assertAlmostEqual(self.data["angle_after_rotate"], self.data["wanted_angle"], places=3)


if __name__ == "__main__":
    unittest.main()
