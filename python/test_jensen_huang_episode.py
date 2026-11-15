import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import qc_episode  # noqa: E402
from workflow.config import style_contract  # noqa: E402


EPISODE = ROOT / "work/jensen-huang"
MASTER = EPISODE / "jensen-huang.mp4"
CONTRACT = style_contract(ROOT)


class JensenHuangArchiveAuthoring(unittest.TestCase):
    def test_static_alexnet_source_is_declared_as_a_moving_still(self):
        records = json.loads((EPISODE / "archive.json").read_text(encoding="utf-8"))
        record = records["alexnet-era_part1"]
        self.assertEqual(record["form"], "still")
        self.assertNotIn("motion_mode", record)
        self.assertEqual(record["still_move"]["pan_deg"], 2.0)
        self.assertNotEqual(record["still_move"]["zoom_from"], record["still_move"]["zoom_to"])


@unittest.skipUnless(MASTER.is_file(), "Jensen Huang master is not present")
class JensenHuangMotionRegression(unittest.TestCase):
    def test_3d_beats_that_hold_longer_than_ten_seconds_are_moving(self):
        shots = qc_episode.load_timeline(EPISODE)
        motions = qc_episode.measure_motions(MASTER, shots)
        threshold = CONTRACT["rhythm"]["motion_static_max"]

        for uid in ("u003", "u019"):
            self.assertGreaterEqual(
                motions[uid],
                threshold,
                f"{uid} motion {motions[uid]:.3f} is below the static threshold",
            )


if __name__ == "__main__":
    unittest.main()
