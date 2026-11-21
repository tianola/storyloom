"""Camera rules of tools/blender/models/camera_plan.py: drift scales with the shot, travels hold at both ends."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "blender" / "models"))
import camera_plan as C  # noqa: E402


class Drift(unittest.TestCase):
    def test_short_shots_are_locked(self):
        for d in (0.5, 1.2, 2.4):
            self.assertEqual(C.drift_amount(d), (0.0, 1.0))
            self.assertEqual(C.drift_amount(d, "push"), (0.0, 1.0))

    def test_drift_scales_with_duration_and_is_capped(self):
        az3, r3 = C.drift_amount(3.0)
        az6, r6 = C.drift_amount(6.0)
        self.assertAlmostEqual(az3, 1.8)
        self.assertAlmostEqual(r3, 0.97)
        self.assertGreater(az6, az3)
        self.assertLess(r6, r3)
        az, r = C.drift_amount(120.0)
        self.assertEqual(az, 4.0)
        self.assertAlmostEqual(r, 0.92)
        for d in (2.5, 5, 10, 40):
            self.assertLessEqual(C.drift_amount(d)[0] / d, 0.6 + 1e-9)
            self.assertLessEqual(1 - C.drift_amount(d)[1], d * 0.01 + 1e-9)

    def test_lock_push_pull(self):
        self.assertEqual(C.drift_amount(20.0, "lock"), (0.0, 1.0))
        self.assertAlmostEqual(C.drift_amount(4.0, "push")[1], 0.92)
        self.assertAlmostEqual(C.drift_amount(30.0, "push")[1], 0.85)
        self.assertAlmostEqual(C.drift_amount(30.0, "pull")[1], 1.15)

    def test_unknown_move_is_loud(self):
        with self.assertRaises(ValueError) as caught:
            C.drift_amount(5.0, "whip")
        self.assertIn("whip", str(caught.exception))
        self.assertIn("lock", str(caught.exception))

    def test_direction_is_stable_per_beat(self):
        self.assertEqual(C.stable_sign("riva-chip"), C.stable_sign("riva-chip"))
        self.assertIn(C.stable_sign("a"), (1.0, -1.0))
        self.assertEqual({C.stable_sign(f"beat-{i}") for i in range(30)}, {1.0, -1.0})


class Travel(unittest.TestCase):
    def test_holds_at_both_ends(self):
        keys = C.travel_keys(10.0, 9)
        self.assertEqual(keys[0][1], keys[1][1])
        self.assertEqual(keys[-1][1], keys[-2][1])
        self.assertEqual((keys[0][1], keys[-1][1]), (0.0, 1.0))
        self.assertAlmostEqual(keys[1][0], 0.06)           # 0.6 s of 10 s
        self.assertAlmostEqual(keys[-2][0], 1 - 0.12)      # 1.2 s of 10 s
        times = [t for t, _ in keys]
        self.assertEqual(times, sorted(times))

    def test_holds_shrink_in_short_shots(self):
        keys = C.travel_keys(4.0, 5)
        self.assertAlmostEqual(keys[1][0], 0.10)           # 10% of 4 s = 0.4 s < 0.6 s
        self.assertAlmostEqual(keys[-2][0], 1 - 0.15)

    def test_glide_keys_stay_monotonic(self):
        progress = [p for _, p in C.travel_keys(30.0, 31)]
        self.assertEqual(progress, sorted(progress))
        self.assertEqual(len(progress), 33)


class Speed(unittest.TestCase):
    def test_still_camera_is_zero(self):
        p, t = (10.0, 0.0, 2.0), (0.0, 0.0, 0.0)
        self.assertEqual(C.camera_speed(p, t, p, t, 5.0)["pan_frames_s"], 0.0)

    def test_orbit_speed(self):
        t = (0.0, 0.0, 0.0)
        p0, p1 = C.orbit_point(t, 10, 0, 0), C.orbit_point(t, 10, 10, 0)
        s = C.camera_speed(p0, t, p1, t, 2.0, lens=50.0)
        self.assertAlmostEqual(s["angular_deg_s"], 5.0, places=6)
        fov = math.degrees(2 * math.atan(18 / 50))         # about 39.6 degrees
        self.assertAlmostEqual(s["pan_frames_s"], 5.0 / fov, places=2)

    def test_shot_speed_excludes_holds_and_flags_fast_pan(self):
        entry = {"target": (0, 0, 0), "radius": (10, 10), "azimuth": (0, 40), "height": (0, 0)}
        slow = C.shot_speed(entry, 40.0)["pan_frames_s"]
        self.assertLess(slow, C.MAX_PAN)
        self.assertGreater(C.shot_speed(entry, 3.0)["pan_frames_s"], C.MAX_PAN)
        travel = dict(entry, target_to=(0, 0, 0))
        self.assertGreater(C.shot_speed(travel, 10.0)["pan_frames_s"], C.shot_speed(entry, 10.0)["pan_frames_s"])


if __name__ == "__main__":
    unittest.main()


class Governor(unittest.TestCase):
    def entry(self):
        return {"start": 0.0, "target": (0.0, 0.0, 1.0), "target_to": (20.0, 0.0, 1.0),
                "radius": (8.0, 4.0), "azimuth": (180.0, 90.0), "height": (2.0, 1.5)}

    def test_a_fast_travel_is_cut_short_to_the_speed_limit(self):
        e = self.entry()
        self.assertGreater(C.shot_speed(e, 4.0)["pan_frames_s"], C.MAX_PAN)
        slow, f = C.govern_travel(e, 4.0)
        self.assertLess(f, 1.0)
        self.assertGreater(f, 0.0)
        self.assertLessEqual(C.shot_speed(slow, 4.0)["pan_frames_s"], C.MAX_PAN)
        self.assertEqual(slow["target"], e["target"])
        self.assertEqual(slow["radius"][0], e["radius"][0])

    def test_a_slow_travel_is_left_alone(self):
        e = self.entry()
        same, f = C.govern_travel(e, 400.0)
        self.assertEqual(f, 1.0)
        self.assertIs(same, e)

    def test_a_held_shot_is_left_alone(self):
        e = {"start": 0.0, "target": (0, 0, 1), "radius": (5, 5), "azimuth": (0, 3), "height": (2, 2)}
        self.assertIs(C.govern_travel(e, 1.0)[0], e)
