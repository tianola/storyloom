"""Regression test for the side-key geometry in lighting.py.

Eighteen of the nineteen Artemis II beats placed their sun by eye and every one of them
landed inside the camera's own quadrant, which is why the whole episode reads as a softbox
no matter how much geometry is underneath: a light travelling the same way the lens looks
puts every shadow behind the object that cast it, where nothing can see it. The lunar-base
key was hand-fixed to a measured frame-right vector, and this test pins the arithmetic that
hand fix came from so the remaining beats cannot drift back.
"""
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "blender" / "techniques"))

import lighting  # noqa: E402


def deg(vector):
    return math.degrees(math.atan2(vector[2], math.hypot(vector[0], vector[1])))


class TestKeyLocation(unittest.TestCase):
    def test_a_camera_looking_along_plus_y_gets_its_key_on_the_world_x_axis(self):
        # right = (vy, -vx), so frame-right for a camera looking +Y is +X.
        key = lighting.key_location((0, -15, 5), (0, 0, 0), elevation=20.0, side=1.0)
        self.assertGreater(key[0], 0.0)
        self.assertAlmostEqual(key[1], 0.0, places=6)

    def test_the_negative_side_mirrors_across_the_view_axis(self):
        right = lighting.key_location((0, -15, 5), (0, 0, 0), elevation=20.0, side=1.0)
        left = lighting.key_location((0, -15, 5), (0, 0, 0), elevation=20.0, side=-1.0)
        self.assertAlmostEqual(right[0], -left[0], places=6)
        self.assertAlmostEqual(right[1], -left[1], places=6)
        self.assertAlmostEqual(right[2], left[2], places=6)

    def test_elevation_and_distance_are_honoured(self):
        key = lighting.key_location((16, -17, 9.5), (0, 0, 2.2),
                                    elevation=17.2, side=1.0, distance=14.0)
        self.assertAlmostEqual(math.dist(key, (0, 0, 0)), 14.0, places=6)
        self.assertAlmostEqual(deg(key), 17.2, places=6)

    def test_it_reproduces_the_hand_placed_lunar_base_key(self):
        # (8.7, 8.2, 3.7) was measured off the frame-right vector of cam-base during
        # look-dev and is the only key in the episode that produced visible shadows.
        key = lighting.key_location((16, -17, 9.5), (0, 0, 2.2),
                                    elevation=17.2, side=1.0, distance=12.5)
        wanted = (8.7, 8.2, 3.7)
        for got, want in zip(key, wanted):
            self.assertAlmostEqual(got, want, delta=0.35)


class TestFrontLight(unittest.TestCase):
    def test_a_perpendicular_key_is_exactly_side_lit(self):
        cam, tgt = (0, -15, 5), (0, 0, 0)
        key = lighting.key_location(cam, tgt, elevation=25.0, side=1.0)
        self.assertAlmostEqual(lighting.front_light(cam, tgt, key), 0.0, places=9)

    def test_the_old_pipeline_default_is_the_defect_this_catches(self):
        # gateway: the literal (5, -10, 15) seven beats shared, under the camera
        # convention almost all of them use.
        self.assertGreater(lighting.front_light((8, -8, 4), (0, 0, 0), (5, -10, 15)), 0.9)

    def test_a_positive_yaw_puts_the_key_behind_the_subject(self):
        cam, tgt = (0, -15, 5), (0, 0, 0)
        key = lighting.key_location(cam, tgt, elevation=25.0, side=1.0, yaw=40.0)
        self.assertLess(lighting.front_light(cam, tgt, key), -0.6)

    def test_a_yaw_into_the_cameras_quadrant_is_refused(self):
        with self.assertRaises(ValueError):
            lighting.key_location((0, -15, 5), (0, 0, 0), yaw=-25.0)

    def test_a_camera_looking_straight_down_gets_a_stable_key(self):
        # Horizontal view is degenerate here, so the answer only has to be finite,
        # level-correct and reproducible — not pretty.
        cam, tgt = (0, 0, 20), (0, 0, 0)
        first = lighting.key_location(cam, tgt, elevation=18.0, side=1.0)
        self.assertAlmostEqual(deg(first), 18.0, places=6)
        self.assertEqual(first, lighting.key_location(cam, tgt, elevation=18.0, side=1.0))


if __name__ == "__main__":
    unittest.main()
