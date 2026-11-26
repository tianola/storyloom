import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workflow.config import EPISODE_PHASES  # noqa: E402
from workflow.init_episode import PHASES, init_episode  # noqa: E402
from workflow.skills import SKILLS_MAP_FILENAME, skills_map  # noqa: E402


class SkillsMapTests(unittest.TestCase):
    """The craft questions this pipeline hits have answers installed on this machine.

    The instruction was that the workflow read them every run «ώστε να είμαστε σίγουροι
    ότι θα λειτουργούν» - so the map is not a list of hopes. Every entry is resolved
    against the real filesystem, and a name that is not there fails the run.
    """

    def setUp(self):
        from toolchain import require_skills
        self.map = require_skills()
        self.work = Path(tempfile.mkdtemp())

    def write_map(self, mutate):
        """skills.json copied into a throwaway tree, edited, and read back - the loader
        gets an honest document to reject rather than a hook in production code."""
        mapping = json.loads((ROOT / "workflow" / SKILLS_MAP_FILENAME)
                             .read_text(encoding="utf-8"))
        mutate(mapping)
        (self.work / "workflow").mkdir(parents=True, exist_ok=True)
        path = self.work / "workflow" / SKILLS_MAP_FILENAME
        path.write_text(json.dumps(mapping), encoding="utf-8")
        return path.parent.parent

    def test_every_phase_of_an_episode_has_a_note_and_a_skill_list(self):
        for phase in EPISODE_PHASES:
            entry = self.map["phases"][phase]
            self.assertTrue(str(entry["note"]).strip(), phase)
            self.assertIsInstance(entry["skills"], list, phase)

    def test_the_narration_and_publish_phases_say_why_they_have_no_skill(self):
        for phase in ("script", "dist"):
            entry = self.map["phases"][phase]
            self.assertEqual(entry["skills"], [], phase)
            self.assertGreater(len(entry["note"]), 40, phase)

    def test_every_installed_skill_in_the_map_is_really_on_this_disk(self):
        # Not injected on purpose: this is the proof that was asked for. If a skill directory
        # goes missing or the vendor sync stops installing, the pipeline finds out next run.
        for phase, entry in self.map["phases"].items():
            for skill in entry["skills"]:
                if skill["origin"] in ("vendor", "machine"):
                    installed = (Path.home() / ".qoder" / "skills" / skill["skill"] / "SKILL.md")
                    self.assertTrue(installed.is_file(), f"{phase}: {installed}")

    def test_every_catalog_skill_is_reachable_through_the_router_index(self):
        rows = json.loads((Path.home() / ".qoder" / "skills-vendor" / "index.json")
                          .read_text(encoding="utf-8"))
        by_name = {row["skill"]: row for row in rows}
        for phase, entry in self.map["phases"].items():
            for skill in entry["skills"]:
                if skill["origin"] != "catalog":
                    continue
                row = by_name.get(skill["skill"])
                self.assertIsNotNone(row, f"{phase}: {skill['skill']} is not in the vendor index")
                self.assertFalse(row["promoted"],
                                 f"{phase}: {skill['skill']} is installed, so it is not catalog")

    def test_each_entry_says_how_it_applies_to_a_blender_and_ffmpeg_pipeline(self):
        for phase, entry in self.map["phases"].items():
            for skill in entry["skills"]:
                self.assertIn(skill["use"], ("direct", "method-only"), phase)
                self.assertGreater(len(skill["provides"]), 30, f"{phase}:{skill['skill']}")
                if skill["use"] == "method-only":
                    self.assertIn("not", skill["provides"].lower(), f"{phase}:{skill['skill']}")

    def test_a_skill_named_but_not_installed_fails_the_run_naming_it(self):
        # The loader walks phases in order and stops at the first name it cannot resolve,
        # so the expectation is that same first name - machine or vendor origin alike.
        named = next(skill["skill"] for entry in self.map["phases"].values()
                     for skill in entry["skills"] if skill["origin"] != "catalog")
        empty = self.work / "no-skills-here"
        empty.mkdir()
        with self.assertRaises(ValueError) as caught:
            skills_map(ROOT, skills_root=empty)
        message = str(caught.exception)
        self.assertIn(named, message)
        self.assertIn("is not installed", message)
        self.assertIn("sync.py", message)

    def test_the_search_command_the_router_advertises_actually_exists(self):
        script = Path(self.map["router"]["script"]).expanduser()
        self.assertTrue(script.is_file(), script)
        self.assertEqual(script.name, "search.py")

    def test_the_rules_say_third_party_skill_text_is_untrusted_and_nothing_publishes(self):
        joined = " ".join(self.map["rules"]).lower()
        self.assertIn("untrusted", joined)
        self.assertIn("publish", joined)

    def test_no_credential_shaped_string_anywhere_in_the_map(self):
        import re
        text = (ROOT / "workflow" / SKILLS_MAP_FILENAME).read_text(encoding="utf-8")
        secrets = re.findall(r"(?i)\b(sk-[A-Za-z0-9]{8,}|hf_[A-Za-z0-9]{8,}|om-[A-Za-z0-9]{4,})\b",
                             text)
        self.assertEqual(secrets, [], secrets)

    def test_a_map_missing_a_phase_raises_naming_that_phase(self):
        root = self.write_map(lambda mapping: mapping["phases"].pop("qc"))
        with self.assertRaises(ValueError) as caught:
            skills_map(root)
        self.assertIn("qc", str(caught.exception))

    def test_an_unknown_origin_is_rejected_rather_than_silently_skipped(self):
        root = self.write_map(
            lambda mapping: mapping["phases"]["motion"]["skills"][0].update(origin="magic"))
        with self.assertRaises(ValueError) as caught:
            skills_map(root)
        self.assertIn("magic", str(caught.exception))

    def test_a_catalog_entry_marked_installed_is_called_out_as_drift(self):
        root = self.write_map(
            lambda mapping: mapping["phases"]["vo"]["skills"].append(
                {"skill": "speech-to-text", "origin": "catalog",
                 "use": "direct", "provides": "duplicated as a catalog pointer on purpose"}))
        with self.assertRaises(ValueError) as caught:
            skills_map(root)
        self.assertIn("speech-to-text", str(caught.exception))

    def test_a_new_episode_carries_the_map_it_was_built_against(self):
        episode = init_episode(self.work, "episode-skillmap", "Skill Map Probe")
        copied = episode / SKILLS_MAP_FILENAME
        self.assertTrue(copied.is_file())
        self.assertEqual(json.loads(copied.read_text(encoding="utf-8"))["name"],
                         self.map["name"])

    def test_a_skill_is_either_mapped_or_recorded_as_unmapped_not_both(self):
        mapped = {skill["skill"] for entry in self.map["phases"].values()
                  for skill in entry["skills"]}
        unmapped = {row["skill"] for row in self.map["installed_unmapped"]}
        self.assertEqual(mapped & unmapped, set())

    def test_nothing_promoted_is_silently_ignored_by_the_map(self):
        rows = json.loads((Path.home() / ".qoder" / "skills-vendor" / "index.json")
                          .read_text(encoding="utf-8"))
        promoted = {row["skill"] for row in rows if row["promoted"]}
        accounted = ({skill["skill"] for entry in self.map["phases"].values()
                      for skill in entry["skills"] if skill["origin"] == "vendor"}
                     | {row["skill"] for row in self.map["installed_unmapped"]})
        self.assertEqual(promoted - accounted, set())

    def test_the_phase_list_has_one_source_of_truth(self):
        self.assertIs(PHASES, EPISODE_PHASES)
        self.assertEqual(set(self.map["phases"]), set(EPISODE_PHASES))


if __name__ == "__main__":
    unittest.main()
