"""plan_shots: every line gets a shot, archive is spread, hints win, bad hints are refused."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))
import plan_shots as P  # noqa: E402

LINES = [{"id": f"u{i:03d}", "seconds": 8.0} for i in range(1, 21)]


class PlanShots(unittest.TestCase):
    def test_every_line_is_covered_and_beats_are_grouped(self):
        shots, share = P.plan(LINES, {}, {}, 14.0, 0.2)
        self.assertEqual(list(shots), [u["id"] for u in LINES])
        self.assertEqual(share, 0.0)
        names = [s["name"] for s in shots.values()]
        self.assertEqual(names[0], names[1])          # 8 s + 8 s share a 14 s beat
        self.assertNotEqual(names[1], names[2])

    def test_unhinted_records_are_spread_over_the_film(self):
        shots, share = P.plan(LINES, {"a": {}, "b": {}, "c": {}, "d": {}}, {}, 14.0, 0.2)
        at = [i for i, s in enumerate(shots.values()) if s["kind"] == "archive"]
        self.assertEqual(len(at), 4)
        self.assertLess(at[0], 5)
        self.assertGreater(at[-1], 14)
        self.assertAlmostEqual(share, 0.2)

    def test_hints_win_and_unknown_hints_are_errors(self):
        shots, _ = P.plan(LINES, {"a": {}}, {"u005": "a"}, 14.0, 0.2)
        self.assertEqual(shots["u005"]["name"], "a")
        with self.assertRaises(ValueError):
            P.plan(LINES, {"a": {}}, {"u999": "a"}, 14.0, 0.2)
        with self.assertRaises(ValueError):
            P.plan(LINES, {"a": {}}, {"u005": "zzz"}, 14.0, 0.2)

    def test_an_existing_shots_json_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = Path(tmp)
            (ep / "shots.json").write_text("{}", encoding="utf-8")
            self.assertEqual(P.main(["--episode", str(ep)]), 0)
            self.assertEqual((ep / "shots.json").read_text(encoding="utf-8"), "{}")

    def test_generated_file_for_a_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = Path(tmp)
            (ep / "vo").mkdir()
            (ep / "vo" / "manifest.json").write_text(json.dumps({"sampleRate": 100, "utterances": [
                {"id": f"u{i:03d}", "samples": 800} for i in range(1, 7)]}), encoding="utf-8")
            self.assertEqual(P.main(["--episode", str(ep)]), 0)
            shots = json.loads((ep / "shots.json").read_text(encoding="utf-8"))
            self.assertEqual(len(shots), 6)


if __name__ == "__main__":
    unittest.main()
