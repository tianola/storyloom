"""plan_shots: every line gets a shot, archive only goes where the line names what it shows."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))
import plan_shots as P  # noqa: E402

LINES = [{"id": f"u{i:03d}", "seconds": 8.0, "text": f"line {i} about nothing in particular"} for i in range(1, 21)]


def lines(**said):
    """LINES with some texts replaced: lines(u005="Charles Kao measured the loss")."""
    return [{**u, "text": said.get(u["id"], u["text"])} for u in LINES]


KAO = {"depicts": ["Charles Kao"]}


class PlanShots(unittest.TestCase):
    def test_every_line_is_covered_and_beats_are_grouped(self):
        shots, share, unused = P.plan(LINES, {}, {}, 14.0)
        self.assertEqual(list(shots), [u["id"] for u in LINES])
        self.assertEqual((share, unused), (0.0, []))
        names = [s["name"] for s in shots.values()]
        self.assertEqual(names[0], names[1])          # 8 s + 8 s share a 14 s beat
        self.assertNotEqual(names[1], names[2])

    def test_a_beat_never_straddles_an_archive_cutaway(self):
        short = [{"id": f"u{i:03d}", "seconds": 3.0, "text": "Charles Kao" if i == 4 else "x"} for i in range(1, 9)]
        shots, _, _ = P.plan(short, {"a": KAO}, {"u004": "a"}, 14.0)
        self.assertEqual(shots["u004"]["kind"], "archive")
        self.assertNotEqual(shots["u003"]["name"], shots["u005"]["name"])

    def test_a_record_goes_on_the_first_line_that_names_it(self):
        shots, _, unused = P.plan(lines(u012="In 1966 Charles Kao published", u015="Kao again"),
                                  {"a": KAO}, {}, 14.0)
        self.assertEqual([u for u, s in shots.items() if s["kind"] == "archive"], ["u012"])
        self.assertEqual(unused, [])

    def test_a_record_no_line_names_is_left_out_not_spread(self):
        """The old planner spread unhinted clips evenly over the film; that is how stock B-roll got in."""
        shots, share, unused = P.plan(LINES, {"a": KAO}, {}, 14.0)
        self.assertEqual(unused, ["a"])
        self.assertEqual(share, 0.0)
        self.assertTrue(all(s["kind"] == "3d" for s in shots.values()))

    def test_a_clip_of_a_category_is_refused_as_stock(self):
        with self.assertRaisesRegex(ValueError, "stock footage"):
            P.plan(lines(u003="the data centre hums"), {"hall": {"depicts": ["data centre", "servers"]}}, {}, 14.0)
        with self.assertRaisesRegex(ValueError, "depicts"):
            P.plan(LINES, {"hall": {}}, {}, 14.0)

    def test_a_hint_must_name_what_the_clip_shows(self):
        with self.assertRaisesRegex(ValueError, "never names"):
            P.plan(LINES, {"a": KAO}, {"u005": "a"}, 14.0)
        shots, _, _ = P.plan(lines(u005="Charles Kao"), {"a": KAO}, {"u005": "a"}, 14.0)
        self.assertEqual(shots["u005"]["name"], "a")

    def test_names_match_whole_words_case_insensitively(self):
        rule = P.load_evidence_rule()
        self.assertTrue(P.names_it("the GB200 NVL72 rack", {"depicts": ["gb200 nvl72"]}, rule))
        self.assertFalse(P.names_it("Kaolin clay", {"depicts": ["Kao"]}, rule))

    def test_unknown_hints_are_errors(self):
        with self.assertRaises(ValueError):
            P.plan(LINES, {"a": KAO}, {"u999": "a"}, 14.0)
        with self.assertRaises(ValueError):
            P.plan(LINES, {"a": KAO}, {"u005": "zzz"}, 14.0)

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
                {"id": f"u{i:03d}", "samples": 800, "text": "x"} for i in range(1, 7)]}), encoding="utf-8")
            self.assertEqual(P.main(["--episode", str(ep)]), 0)
            shots = json.loads((ep / "shots.json").read_text(encoding="utf-8"))
            self.assertEqual(len(shots), 6)


if __name__ == "__main__":
    unittest.main()
