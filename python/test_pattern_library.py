import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workflow.config import PATTERN_IDS, REQUIRED_PATTERN_KEYS, pattern_library  # noqa: E402
from workflow.init_episode import init_episode  # noqa: E402


class PatternLibraryTests(unittest.TestCase):
    """The six presentation patterns the user pasted are a contract, not a mood board.

    They arrived as a screenshot of a prompt gallery, so the five tagged fields are
    the part worth keeping and the little UI labels are decoration damaged by OCR.
    A pattern only helps a beat builder if the obligation it implies is written down
    next to it in words the builder cannot skip.
    """

    def setUp(self):
        self.library = pattern_library(ROOT)
        self.by_id = {p["id"]: p for p in self.library["patterns"]}

    def test_all_six_patterns_the_user_pasted_are_stored(self):
        self.assertEqual(list(self.by_id), list(PATTERN_IDS))
        titles = {p["title"] for p in self.library["patterns"]}
        for heading in ("The Photo Teardown", "The Product Viewer", "The How It Works Model",
                        "The Data City", "The 3D Print Maker", "The Mini World"):
            self.assertIn(heading, titles, heading)

    def test_every_pattern_keeps_the_five_brief_fields(self):
        for pattern in self.library["patterns"]:
            for key in REQUIRED_PATTERN_KEYS:
                self.assertTrue(str(pattern.get(key, "")).strip(), f"{pattern['id']} {key}")

    def test_the_how_it_works_pattern_carries_its_two_numbers(self):
        numbers = self.by_id["how-it-works"]["pipeline_use"]["numbers"]
        self.assertEqual(numbers["step_ceiling_seconds"], 10.0)
        self.assertEqual(numbers["reading_age_years"], 12)

    def test_how_it_works_obligation_demands_the_interior(self):
        obligation = self.by_id["how-it-works"]["pipeline_use"]["obligation"].lower()
        self.assertIn("interior", obligation)
        self.assertIn("label", obligation)

    def test_every_pattern_says_who_reads_it(self):
        for pattern in self.library["patterns"]:
            use = pattern["pipeline_use"]
            self.assertIn(use["enforced_by"], {"builder", "gate", "not-yet-enforced"}, pattern["id"])
            self.assertTrue(use["applies_when"].strip(), pattern["id"])

    def test_a_pattern_that_claims_gate_enforcement_is_found_in_the_gate(self):
        claimed = [p["id"] for p in self.library["patterns"]
                   if p["pipeline_use"]["enforced_by"] == "gate"]
        if not claimed:
            self.skipTest("no pattern claims gate enforcement yet")
        source = (ROOT / "tools/qc_episode.py").read_text(encoding="utf-8")
        self.assertIn("pattern_library", source, claimed)

    def test_a_missing_field_raises_naming_the_pattern_that_lost_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("workflow").mkdir()
            broken = json.loads((ROOT / "workflow/patterns.json").read_text(encoding="utf-8"))
            broken["patterns"][2].pop("rules")
            (root / "workflow/patterns.json").write_text(json.dumps(broken), encoding="utf-8")
            with self.assertRaises(ValueError) as caught:
                pattern_library(root)
            self.assertIn("how-it-works", str(caught.exception))

    def test_no_credential_shaped_string_anywhere_in_the_file(self):
        text = (ROOT / "workflow/patterns.json").read_text(encoding="utf-8")
        secrets = re.findall(r"(?i)\b(sk-[A-Za-z0-9]{8,}|hf_[A-Za-z0-9]{8,}|om-[A-Za-z0-9]{4,})\b", text)
        self.assertEqual(secrets, [], secrets)


class EpisodeCarriesItsPatternsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from toolchain import require_skills
        require_skills()   # init_episode refuses a machine without the mapped skills

    def test_a_new_episode_copies_the_library_it_was_built_against(self):
        with tempfile.TemporaryDirectory() as tmp:
            episode = init_episode(Path(tmp), "episode-thruster", "How a Thruster Works")
            copy = json.loads((episode / "patterns.json").read_text(encoding="utf-8"))
            self.assertEqual([p["id"] for p in copy["patterns"]], list(PATTERN_IDS))


if __name__ == "__main__":
    unittest.main()
