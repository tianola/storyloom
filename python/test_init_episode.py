import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from host_double import healthy_host  # noqa: E402
from workflow.init_episode import init_episode  # noqa: E402


class InitEpisodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from toolchain import require_skills
        require_skills()   # init_episode refuses a machine without the mapped skills

    def test_creates_nine_phase_layout_and_empty_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            episode = init_episode(Path(tmp), "episode-carrington", "The Carrington Event",
                                   host=healthy_host(ROOT))
            for name in ("research", "story", "script", "assets", "vo", "motion", "edit", "qc", "dist"):
                self.assertTrue((episode / name).is_dir(), name)
            self.assertEqual(json.loads((episode / "assets/license-manifest.json").read_text()), [])
            self.assertEqual(json.loads((episode / "episode.json").read_text())["language"], "English")
            self.assertTrue((episode / "research/sources.md").is_file())
            self.assertTrue((episode / "story/beat-sheet.md").is_file())
            self.assertTrue((episode / "script/narration.md").is_file())

    def test_rejects_unsafe_slug_and_existing_episode(self):
        with tempfile.TemporaryDirectory() as tmp:
            for slug in ("../escape", "A", "two words", "a/b", ""):
                with self.subTest(slug=slug), self.assertRaises(ValueError):
                    init_episode(Path(tmp), slug, "Title")
            init_episode(Path(tmp), "episode-carrington", "Title", host=healthy_host(ROOT))
            with self.assertRaises(FileExistsError):
                init_episode(Path(tmp), "episode-carrington", "Title", host=healthy_host(ROOT))


class ArchivalLayerSeededTests(unittest.TestCase):
    """A new episode starts owing the archival layer, and starts able to pay it.

    Seeding is what makes a default a fact rather than a sentence in a guide. If `archive.json`
    appears only when somebody remembers to make it, then the episode that never made one is
    indistinguishable from the episode that made one and deleted it, and the gate has no state to
    read. Two empty files and one `enabled: true` in the episode document give the layer a place
    to be declared, so absence becomes a finding the pipeline reports instead of a gap it walks
    past.
    """

    @classmethod
    def setUpClass(cls):
        from toolchain import require_skills
        require_skills()   # init_episode refuses a machine without the mapped skills

    def test_a_new_episode_declares_the_archival_layer_on(self):
        with tempfile.TemporaryDirectory() as tmp:
            episode = init_episode(Path(tmp), "episode-carrington", "The Carrington Event",
                                   host=healthy_host(ROOT))
            document = json.loads((episode / "episode.json").read_text(encoding="utf-8"))
        self.assertTrue(document["archive"]["enabled"],
                        "a new episode that does not state the layer is opted in has to be "
                        "edited into the style rather than edited out of it")

    def test_a_new_episode_carries_the_record_file_and_the_rights_ledger(self):
        from workflow.archive import paths
        from workflow.config import style_contract

        declared = paths(style_contract(ROOT))
        with tempfile.TemporaryDirectory() as tmp:
            episode = init_episode(Path(tmp), "episode-carrington", "The Carrington Event",
                                   host=healthy_host(ROOT))
            for key in ("records_filename", "ledger_filename"):
                self.assertTrue((episode / declared[key]).is_file(),
                                f"{declared[key]} was not seeded")
            self.assertEqual(json.loads(
                (episode / declared["ledger_filename"]).read_text(encoding="utf-8")), [])

    def test_the_seeded_files_are_the_empty_state_the_validators_accept(self):
        """Present-and-empty is a different state from absent, and only the validators know which
        is which — so the seed has to satisfy them, not merely exist."""
        from workflow.archive import ledger, records
        from workflow.config import style_contract

        contract = style_contract(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            episode = init_episode(Path(tmp), "episode-carrington", "The Carrington Event",
                                   host=healthy_host(ROOT))
            self.assertEqual(records(episode, contract), {})
            self.assertEqual(ledger(episode, contract), {})

    def test_the_seeded_names_come_from_the_contract_not_from_memory(self):
        """The filenames are style data carrying a `why` that argues for them; a seed that
        retypes them is how a renamed archival path ends up writing one file and reading another."""
        import workflow.init_episode as module
        from workflow.archive import paths
        from workflow.config import style_contract

        renamed = json.loads(json.dumps(style_contract(ROOT)))
        # Snapshotted as strings, not held as `paths()`: that accessor hands back the live
        # contract dict, so a `declared` reference would follow the mutation it is meant to
        # prove the code did.
        original_records = paths(renamed)["records_filename"]
        renamed["archive"]["paths"]["records_filename"] = "archive-records.json"
        renamed["archive"]["paths"]["ledger_filename"] = "assets/archival-rights.json"
        original = module.style_contract
        module.style_contract = lambda root: renamed
        try:
            with tempfile.TemporaryDirectory() as tmp:
                episode = init_episode(Path(tmp), "episode-carrington", "The Carrington Event",
                                       host=healthy_host(ROOT))
                self.assertTrue((episode / "archive-records.json").is_file())
                self.assertTrue((episode / "assets/archival-rights.json").is_file())
                self.assertFalse((episode / original_records).exists(),
                                 "both the renamed and the remembered name were written")
        finally:
            module.style_contract = original


class RolloutPlanSeededTests(unittest.TestCase):
    """A new episode starts owing a render plan, and starts unable to pay it.

    `tools/rollout_render.py` carried its builder script, its luma baseline and one hero beat as
    three literals of its own, so the queue could render exactly one film and a second episode's
    `finish` re-cut a beat that film never had. They are episode authoring now, which means a fresh
    directory is missing them, and a seed that guessed `tools/blender/artemis_beats.py` would hand
    every new episode last week's frames.

    So the keys are seeded empty — the same treatment the archival layer got above. An episode whose
    author has not chosen a builder yet and an episode whose `episode.json` lost the key are
    different states, and only a document on disk tells them apart; the queue reads the first as
    "author this" and refuses both until the value exists.
    """

    @classmethod
    def setUpClass(cls):
        from toolchain import require_skills
        require_skills()   # init_episode refuses a machine without the mapped skills

    def build(self, tmp):
        return init_episode(Path(tmp), "episode-carrington", "The Carrington Event",
                            host=healthy_host(ROOT))

    def document(self, episode):
        return json.loads((episode / "episode.json").read_text(encoding="utf-8"))

    def test_a_new_episode_declares_every_key_the_render_queue_reads(self):
        from workflow.episode import ROLLOUT_FILES

        with tempfile.TemporaryDirectory() as tmp:
            body = self.document(self.build(tmp))
        plan = body["rollout"]
        for key in list(ROLLOUT_FILES) + ["finish_beats"]:
            self.assertIn(key, plan, f"rollout.{key} was not seeded")
        self.assertIsInstance(plan["finish_beats"], list)

    def test_the_seeded_plan_names_no_previous_episode(self):
        """The guard has to be able to fail: seeding Artemis' builder would render Artemis' beats
        into every new film, and the frames would arrive at the right size and the wrong shape."""
        with tempfile.TemporaryDirectory() as tmp:
            plan = self.document(self.build(tmp))["rollout"]
        for key in ("builder", "baseline"):
            self.assertFalse(str(plan[key]).strip(),
                             f"rollout.{key} was seeded with {plan[key]!r}, which is some other "
                             "film's authoring and not this one's")
        self.assertEqual(plan["finish_beats"], [])

    def test_the_queue_refuses_a_seeded_episode_naming_the_document_and_the_keys(self):
        from workflow.episode import rollout_plan

        with tempfile.TemporaryDirectory() as tmp:
            episode = self.build(tmp)
            with self.assertRaises(ValueError) as caught:
                rollout_plan(episode, Path(tmp))
        message = str(caught.exception)
        self.assertIn("episode.json", message)
        self.assertIn("builder", message)
        self.assertIn("baseline", message)


if __name__ == "__main__":
    unittest.main()
