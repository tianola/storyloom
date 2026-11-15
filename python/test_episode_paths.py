# -*- coding: utf-8 -*-
"""Which episode a run is about, and where its files live, as one read rather than three literals.

Until #146 the answer to "what is the current episode?" was written into the source of three
tools: `tools/assemble_episode.py` pinned `work/episode-artemis-ii` and a 32-entry `VISUAL_MAP`,
`tools/rollout_render.py` pinned seven more paths at the same directory, and
`tools/qc_shot_continuity.py` imported the assembler's copy. A second episode therefore could not
be assembled without editing pipeline code — which is precisely how a pipeline-wide style default
becomes one episode's private trick. `qc_episode.py` had already solved this for the gate by
taking `--episode`, so this module gives the same answer to the tools that build the master.

The shot table is data too. `shots.json` in the episode directory already carried the identical
mapping — the assembler was *publishing* it from its own literal, which made the code the source
and the file a copy. Reading it back deletes the duplicate and lets a future episode state its own
shots, including `archive` shots, without anybody touching `tools/`.

What is *not* parameterised here: the canvas, the audio spec, the archival profile. Those are
house style and live in `workflow/style.json`; an episode that disagreed with them would be a
different house, not a different film.
"""
import ast
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from workflow import episode as E  # noqa: E402
from workflow.config import style_contract  # noqa: E402

CONTRACT = style_contract(ROOT)
ARTEMIS = ROOT / "work" / "jensen-huang"

# One fully documented archival shot, for the tests that ask where a film's archive comes from.
# Written out here instead of borrowed from `test_archive_records.py` because a test that leans on
# another file's fixtures breaks when that file is edited for its own reasons, and the second file
# is not the one under test.
ARCHIVE_RECORD = {
    "asset": "assets/archive/apollo_boot_1969.mp4",
    "licence": "arch-001",
    "form": "clip",
    "native_fps": 16.0,
    "motion_mode": "retime_to_natural",
    "aspect": "pillarbox_visible_edge",
    "treatment": "keep_distinct",
    "carries": "filmed_event",
}
ARCHIVE_ROW = {
    "id": "arch-001",
    "provider": "NASA",
    "license": "PD-US-NO-RESTRICTION",
    "url": "https://archive.org/details/nasa-apollo-boot",
    "file": "assets/archive/apollo_boot_1969.mp4",
    "source_archive": "NASA Image Library",
    "rights_basis": "us_federal_public_domain",
    "credit_line": "NASA, Apollo 11 EVA (1969)",
    "retrieval_url": "https://archive.org/download/nasa-apollo-boot/apollo_boot_1969.mp4",
    "retrieved_date": "2026-11-13",
    "purpose_of_use": "the only filmed record of the gait the narration describes",
    "third_party_rights": "none",
    "in_timecode": "00:01:12:09",
    "out_timecode": "00:01:18:21",
    "timebase": 24,
    "source_frame_rate": 24.0,
    "licence_version": "NASA images and media usage guidelines, as retrieved",
    "obligations": ["credit the source archive verbatim"],
    "qc_watermark": False,
    "derivative_transformations": ["pillarbox to preserve the frame edge"],
    "uploaded_as_is": False,
    "source_year": 1969,
}


def seeded(directory: Path, slug: str = "episode-test", document_extra=None) -> Path:
    """A directory that looks like an episode: its own `episode.json` and nothing else."""
    ep = directory / slug
    ep.mkdir(parents=True)
    body = {"slug": slug, "title": "A Test Film", "workflow_version": 3}
    if document_extra:
        body.update(document_extra)
    (ep / "episode.json").write_text(json.dumps(body, indent=2), encoding="utf-8")
    return ep


def archival(directory: Path, slug: str = "episode-apollo", *, record=None, row=None,
             asset=True, record_file=True, table=None) -> Path:
    """A throwaway film that declares one archival shot, plus the files that shot cites.

    Every state the lookup has to judge is reachable here: `record={}` is a declared shot with no
    record, `record_file=False` is a film that never wrote the file at all, `asset=False` is a
    record whose media never arrived. A fixture that cannot state the broken case leaves the guard
    unable to fail.
    """
    from workflow.archive import paths

    ep = seeded(directory, slug)
    declared = paths(CONTRACT)
    if record_file:
        (ep / declared["records_filename"]).write_text(
            json.dumps({"apollo-era": ARCHIVE_RECORD} if record is None else record, indent=1),
            encoding="utf-8")
    ledger_path = ep / declared["ledger_filename"]
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(json.dumps([ARCHIVE_ROW] if row is None else [row], indent=1),
                           encoding="utf-8")
    shots_table = ({"u001": {"kind": "archive", "name": "apollo-era"},
                    "u002": {"kind": "3d", "name": "launch"}} if table is None else table)
    E.shots_path(ep).write_text(json.dumps(shots_table, indent=1), encoding="utf-8")
    if asset:
        media = ep / declared["source_dir"]
        media.mkdir(parents=True, exist_ok=True)
        (media / Path(ARCHIVE_RECORD["asset"]).name).write_bytes(b"stub archival source")
    return ep


class ResolveTests(unittest.TestCase):
    """The episode is chosen by the person running the tool, never by the tool."""

    def test_a_directory_resolves_to_itself(self):
        with self.subTest():
            import tempfile
            with tempfile.TemporaryDirectory() as tmp:
                ep = seeded(Path(tmp))
                self.assertEqual(E.resolve(Path(tmp), ep), ep)

    def test_a_slug_resolves_under_work(self):
        self.assertEqual(E.resolve(ROOT, "jensen-huang"), ARTEMIS)

    def test_a_relative_path_resolves_against_the_repo_root(self):
        self.assertEqual(E.resolve(ROOT, "work/jensen-huang"), ARTEMIS)

    def test_an_unknown_spec_is_refused_and_says_where_it_looked(self):
        with self.assertRaises(ValueError) as caught:
            E.resolve(ROOT, "episode-that-does-not-exist")
        message = str(caught.exception)
        self.assertIn("episode-that-does-not-exist", message)
        self.assertIn(str(ROOT / "work"), message)

    def test_a_directory_that_is_not_an_episode_is_refused(self):
        """A typo'd path that happens to exist must not assemble an empty film."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            stray = Path(tmp) / "not-an-episode"
            stray.mkdir()
            with self.assertRaises(ValueError) as caught:
                E.resolve(Path(tmp), stray)
        self.assertIn("episode.json", str(caught.exception))

    def test_the_real_episode_resolves_and_carries_its_title(self):
        document = E.document(E.resolve(ROOT, "jensen-huang"))
        self.assertEqual(document["slug"], "jensen-huang")
        self.assertIn("Jensen", document["title"])


class LayoutTests(unittest.TestCase):
    """One place says where a film's parts live, so the assembler and the gate cannot disagree."""

    def test_the_master_is_named_for_the_episode_directory(self):
        """`jensen-huang.mp4` inside `work/jensen-huang` — the existing convention,
        derived instead of typed. A deliverable whose name disagrees with its directory is how a
        `dist` publish copies the previous episode."""
        self.assertEqual(E.master(ARTEMIS), ARTEMIS / "jensen-huang.mp4")

    def test_the_derivation_works_for_a_name_that_is_not_artemis(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ep = seeded(Path(tmp), "episode-vostok")
            self.assertEqual(E.master(ep).name, "episode-vostok.mp4")

    def test_every_layer_renders_under_the_episode(self):
        self.assertEqual(E.render_dir(ARTEMIS, "3d", CONTRACT), ARTEMIS / "renders" / "3d")
        self.assertEqual(E.render_dir(ARTEMIS, "manim", CONTRACT), ARTEMIS / "renders" / "manim")
        self.assertEqual(E.render_dir(ARTEMIS, "cards", CONTRACT), ARTEMIS / "renders" / "cards")

    def test_the_archive_render_directory_comes_from_the_contract(self):
        """The archival layer's path is style data with a `why` arguing for it; retyping it here
        is how a renamed path ends up written to one name and read from another."""
        from workflow.archive import paths
        declared = paths(CONTRACT)["render_dir"]
        self.assertEqual(E.render_dir(ARTEMIS, "archive", CONTRACT), ARTEMIS / declared)

    def test_renaming_the_contract_path_moves_the_archive_layer(self):
        from workflow.archive import paths
        renamed = json.loads(json.dumps(CONTRACT))
        renamed["archive"]["paths"]["render_dir"] = "renders/archive-footage"
        original = paths(renamed)["render_dir"]
        self.assertEqual(original, "renders/archive-footage")
        self.assertEqual(E.render_dir(ARTEMIS, "archive", renamed),
                         ARTEMIS / "renders" / "archive-footage")

    def test_a_layer_the_contract_does_not_declare_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            E.render_dir(ARTEMIS, "stock", CONTRACT)
        self.assertIn("stock", str(caught.exception))

    def test_the_supporting_files_are_named_in_one_place(self):
        self.assertEqual(E.vo_dir(ARTEMIS), ARTEMIS / "vo")
        self.assertEqual(E.segments_dir(ARTEMIS), ARTEMIS / "segments")
        self.assertEqual(E.shots_path(ARTEMIS), ARTEMIS / "shots.json")
        self.assertEqual(E.shot_lengths_path(ARTEMIS), ARTEMIS / "shot_lengths.json")
        self.assertEqual(E.graded_path(ARTEMIS), ARTEMIS / "video-graded.mp4")
        self.assertEqual(E.music_bed_path(ARTEMIS), ARTEMIS / "music" / "bed.wav")


class ShotMapTests(unittest.TestCase):
    """`shots.json` is the source of what is on screen; the assembler reads it instead of being it.

    The tuple shape is what `card_frame` and the segment builder already consume, and what
    `test_card_motion.py` passes by hand, so the reader adapts the JSON to that shape rather than
    rewriting the drawing code.
    """

    def test_the_real_episode_table_reads_as_the_shape_the_assembler_used(self):
        shots = E.shots(ARTEMIS, CONTRACT)
        self.assertEqual(shots["u001"], ("3d", "denny-den", "", ""))
        self.assertEqual(shots["u004"], ("archive", "boarding-school_part1", "", ""))

    def test_the_table_is_total_over_the_episode(self):
        """The old literal and the published file were measured identical before the literal was
        deleted; if a future edit moves one, this is where it surfaces."""
        shots = E.shots(ARTEMIS, CONTRACT)
        self.assertEqual(len(shots), 19)
        self.assertEqual(shots["u019"][0], "3d")

    def test_a_card_record_keeps_its_text_in_order(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ep = seeded(Path(tmp))
            self._write(ep, {"u001": {"kind": "cards", "name": "bar-chart",
                                      "title": "T", "subtitle": "S"}})
            self.assertEqual(E.shots(ep, CONTRACT)["u001"],
                             ("cards", "bar-chart", "T", "S"))

    def test_a_record_without_a_title_still_loads_as_a_short_tuple(self):
        """Not every card carries a subtitle, and the drawing code reads `entry[3]` only when it
        is there — a record missing the optional text is a shorter tuple, not a KeyError."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ep = seeded(Path(tmp))
            self._write(ep, {"u001": {"kind": "3d", "name": "launch"}})
            self.assertEqual(E.shots(ep, CONTRACT)["u001"], ("3d", "launch"))

    def test_a_kind_outside_the_contract_taxonomy_is_refused(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ep = seeded(Path(tmp))
            self._write(ep, {"u001": {"kind": "stock", "name": "clip"}})
            with self.assertRaises(ValueError) as caught:
                E.shots(ep, CONTRACT)
        message = str(caught.exception)
        self.assertIn("stock", message)
        for layer in CONTRACT["archive"]["episode_profile"]["mix"]["layers"]:
            self.assertIn(layer, message)

    def test_a_record_without_a_name_is_refused(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ep = seeded(Path(tmp))
            self._write(ep, {"u001": {"kind": "3d"}})
            with self.assertRaises(ValueError) as caught:
                E.shots(ep, CONTRACT)
        self.assertIn("u001", str(caught.exception))

    def test_an_empty_table_is_refused_rather_than_assembled_as_black(self):
        """A seeded episode starts with `{}`; that is the state "shots not chosen yet", and the
        build that reads it as "no visuals" ships a black film with correct duration."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ep = seeded(Path(tmp))
            self._write(ep, {})
            with self.assertRaises(ValueError) as caught:
                E.shots(ep, CONTRACT)
        self.assertIn("shots.json", str(caught.exception))

    def test_a_missing_table_is_refused_naming_the_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ep = seeded(Path(tmp))
            with self.assertRaises(ValueError) as caught:
                E.shots(ep, CONTRACT)
        self.assertIn("shots.json", str(caught.exception))

    @staticmethod
    def _write(ep, table):
        E.shots_path(ep).write_text(json.dumps(table, indent=1), encoding="utf-8")


class CoverageTests(unittest.TestCase):
    """Every spoken utterance owes a visual, and the debt is checked before the encode."""

    def test_an_utterance_with_no_shot_is_refused_by_name(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ep = seeded(Path(tmp))
            with self.assertRaises(ValueError) as caught:
                E.require_coverage(ep, {"u001": ("3d", "a")}, ["u001", "u002", "u003"])
        message = str(caught.exception)
        self.assertIn("u002", message)
        self.assertIn("u003", message)
        self.assertNotIn("u001 ", message)

    def test_a_shot_no_utterance_speaks_over_is_refused(self):
        """An orphan entry is a beat that will never be seen — usually the residue of a re-cut
        script, and the reason the render queue then burns GPU minutes on an unused shot."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ep = seeded(Path(tmp))
            with self.assertRaises(ValueError) as caught:
                E.require_coverage(ep, {"u001": ("3d", "a"), "u009": ("3d", "b")}, ["u001"])
        self.assertIn("u009", str(caught.exception))

    def test_a_total_table_passes(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ep = seeded(Path(tmp))
            E.require_coverage(ep, {"u001": ("3d", "a"), "u002": ("cards", "b", "T", "S")},
                               ["u001", "u002"])

    def test_the_real_episode_covers_its_own_manifest(self):
        """The integration half of "identical to the literal": the published table must cover the
        published narration, or the episode that ships is the one with holes in it."""
        shots = E.shots(ARTEMIS, CONTRACT)
        manifest = json.loads((E.vo_dir(ARTEMIS) / "manifest.json").read_text(encoding="utf-8"))
        E.require_coverage(ARTEMIS, shots, [u["id"] for u in manifest["utterances"]])


class AssemblerReadsItsEpisodeTests(unittest.TestCase):
    """The assembler is a function of the episode it was handed, not of a directory it remembers.

    These are the seams `main()` wires together: the path for one shot's source, the per-beat
    lengths the renderers size to, and the table both read. Each is testable without ffmpeg, which
    is the point of moving the answers into `workflow/episode.py`.
    """

    def setUp(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import assemble_episode
        self.A = assemble_episode

    def test_a_moving_shot_is_sliced_from_its_own_layer_directory(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ep = seeded(Path(tmp))
            (ep / "renders" / "3d").mkdir(parents=True)
            (ep / "renders" / "3d" / "launch.mp4").write_bytes(b"x")
            self.assertEqual(self.A.visual_for(ep, "u001", ("3d", "launch"), CONTRACT),
                             ep / "renders" / "3d" / "launch.mp4")

    def test_an_archival_shot_is_sliced_from_the_contract_render_directory(self):
        """#147 dispatches the kind; the path is already right, and this is the guard that the
        assembler never grew its own `archive` literal to disagree with the contract's."""
        import tempfile
        from workflow.archive import paths
        with tempfile.TemporaryDirectory() as tmp:
            ep = seeded(Path(tmp))
            directory = ep / paths(CONTRACT)["render_dir"]
            directory.mkdir(parents=True)
            (directory / "apollo-11.mp4").write_bytes(b"x")
            self.assertEqual(self.A.visual_for(ep, "u001", ("archive", "apollo-11"), CONTRACT),
                             directory / "apollo-11.mp4")

    def test_a_card_takes_its_per_utterance_clip(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ep = seeded(Path(tmp))
            (ep / "renders" / "cards").mkdir(parents=True)
            (ep / "renders" / "cards" / "card-u022.mp4").write_bytes(b"x")
            self.assertEqual(
                self.A.visual_for(ep, "u022", ("cards", "bar-chart", "T", "S"), CONTRACT),
                ep / "renders" / "cards" / "card-u022.mp4")

    def test_a_shot_whose_source_was_never_rendered_is_refused_by_name(self):
        """The old behaviour printed `WARNING: no visual, using black` and carried on, so a
        missing beat reached the master as a black frame with correct total duration. A build that
        cannot find its source is a build that should stop and say which shot it is holding."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ep = seeded(Path(tmp))
            (ep / "renders" / "3d").mkdir(parents=True)
            with self.assertRaises(ValueError) as caught:
                self.A.visual_for(ep, "u004", ("3d", "crew-quarters"), CONTRACT)
        message = str(caught.exception)
        self.assertIn("u004", message)
        self.assertIn("crew-quarters", message)

    def test_the_beat_length_is_the_narration_over_it_summed(self):
        """Two sentences over one camera move are one 20 s beat, not two 10 s replays."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ep = seeded(Path(tmp))
            manifest = {"sampleRate": 24000, "utterances": [
                {"id": "u001", "samples": 240000},   # 10 s
                {"id": "u002", "samples": 120000},   # 5 s, same beat
                {"id": "u003", "samples": 48000}]}   # 2 s, a card: never a render
            shots = {"u001": ("3d", "launch"), "u002": ("3d", "launch"),
                     "u003": ("cards", "bar-chart", "T", "S")}
            self.A.write_shot_lengths(ep, manifest, shots)
            table = json.loads(E.shot_lengths_path(ep).read_text(encoding="utf-8"))
        self.assertEqual(table, {"launch": 15})
        self.assertNotIn("bar-chart", table)
        self.assertFalse(E.shots_path(ep).exists(),
                         "the assembler reads the table now; publishing it again would overwrite "
                         "the authoring with a copy of the read")

    def test_the_seconds_are_divided_by_the_rate_the_narration_declares(self):
        """`qc_episode.py` reads `sampleRate` off the manifest; this file divided by its own 24000.

        Two answers to one question is how a cut mis-times in silence: narration produced at
        another rate would land every beat 1.5x long while the gate, reading the manifest, still
        called the master clean. The rate is a fact about the audio this episode shipped with.
        """
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ep = seeded(Path(tmp))
            manifest = {"sampleRate": 16000, "utterances": [
                {"id": "u001", "samples": 160000},   # 10 s at the declared rate
                {"id": "u002", "samples": 80000}]}   #  5 s, same beat
            shots = {"u001": ("3d", "launch"), "u002": ("3d", "launch")}
            self.A.write_shot_lengths(ep, manifest, shots)
            table = json.loads(E.shot_lengths_path(ep).read_text(encoding="utf-8"))
        self.assertEqual(table, {"launch": 15},
                         "the beat was timed by the assembler's own constant, not the "
                         "rate the narration declares")

    def test_the_assembler_holds_no_master_path_of_its_own(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ep = seeded(Path(tmp), "episode-tsiolkovsky")
            self.assertEqual(self.A.master(ep), E.master(ep))


class ArchiveSourceTests(unittest.TestCase):
    """One archival shot's record, rights row, source file and output clip, as a single lookup.

    The assembler and the rollout queue both need to know what an `archive` shot is cut from. When
    each worked it out for itself, one could ingest into the contract's directory while the other
    read from a path it had typed, and the film that shipped had a black frame where the archive
    should have been — the failure this task exists to make impossible, and impossible only while
    there is exactly one answer to the question.
    """

    def test_a_declared_archive_shot_resolves_to_its_record_row_source_and_clip(self):
        import tempfile
        from workflow.archive import paths
        with tempfile.TemporaryDirectory() as tmp:
            ep = archival(Path(tmp))
            found = E.archive_sources(ep, CONTRACT)
        self.assertEqual(list(found), ["apollo-era"])
        entry = found["apollo-era"]
        self.assertEqual(entry["source"], ep / paths(CONTRACT)["source_dir"]
                         / "apollo_boot_1969.mp4")
        self.assertEqual(entry["clip"], ep / paths(CONTRACT)["render_dir"] / "apollo-era.mp4")
        self.assertIsInstance(entry["source"], Path, "a string here would be cut by whichever "
                             "caller happened to wrap it in Path last")
        self.assertIsInstance(entry["clip"], Path)
        self.assertEqual(entry["record"], dict(ARCHIVE_RECORD, native_fps=16.0))
        self.assertEqual(entry["licence"]["id"], "arch-001")

    def test_the_clip_path_follows_the_contract_not_a_literal_here(self):
        """`render_dir` is contract data with a `why`; a lookup that typed its own `renders/archive`
        would keep ingesting to the old name after the rename that moved the film."""
        import tempfile
        renamed = json.loads(json.dumps(CONTRACT))
        renamed["archive"]["paths"]["render_dir"] = "renders/archive-footage"
        with tempfile.TemporaryDirectory() as tmp:
            ep = archival(Path(tmp))
            entry = E.archive_sources(ep, renamed)["apollo-era"]
        self.assertEqual(entry["clip"], ep / "renders" / "archive-footage" / "apollo-era.mp4")

    def test_an_archive_shot_with_no_record_is_refused_naming_the_shot(self):
        """`shots.json` says archival, `archive.json` says nothing: the cut has a hole in it and
        the ingest has nothing to build. Reaching the encode to find out costs the whole run."""
        import tempfile
        from workflow.archive import paths
        with tempfile.TemporaryDirectory() as tmp:
            ep = archival(Path(tmp), record={})
            with self.assertRaises(ValueError) as caught:
                E.archive_sources(ep, CONTRACT)
        message = str(caught.exception)
        self.assertIn("apollo-era", message)
        self.assertIn("u001", message)
        self.assertIn(paths(CONTRACT)["records_filename"], message)

    def test_an_archival_asset_that_is_not_on_disk_is_refused_naming_the_shot(self):
        """The record validates fine and the media is simply missing — the state a rights ledger
        full of links to files nobody downloaded. An ingest would fail mid-ffmpeg; this fails now."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ep = archival(Path(tmp), asset=False)
            with self.assertRaises(ValueError) as caught:
                E.archive_sources(ep, CONTRACT)
        message = str(caught.exception)
        self.assertIn("apollo-era", message)
        self.assertIn("apollo_boot_1969.mp4", message)

    def test_a_film_that_declares_no_archival_layer_needs_no_record_file(self):
        """Absence of the layer is legal at this stage: whether the absence is a *finding* is the
        mix rule's call (#148), not the lookup's, and a build that refused here could not cut a
        3D-only film at all."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ep = archival(Path(tmp), record_file=False,
                          table={"u001": {"kind": "3d", "name": "launch"}})
            self.assertEqual(E.archive_sources(ep, CONTRACT), {})

    def test_a_record_the_episode_never_declared_is_not_a_source(self):
        """A shot that fell out of the cut leaves its record behind. Ingesting it anyway would
        spend an encode on footage no utterance speaks over, so the shot table drives the lookup
        and `archive.json` only answers it."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ep = archival(Path(tmp), record={"never-declared": ARCHIVE_RECORD},
                          table={"u001": {"kind": "3d", "name": "launch"}})
            self.assertEqual(E.archive_sources(ep, CONTRACT), {})

    def test_every_shot_of_one_archival_name_is_answered_once(self):
        """Two sentences over one archival shot are one clip, the same way they are one beat in
        `shot_lengths.json`; a per-utterance answer here would ingest the same file twice."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ep = archival(Path(tmp), table={
                "u001": {"kind": "archive", "name": "apollo-era"},
                "u002": {"kind": "archive", "name": "apollo-era"}})
            self.assertEqual(list(E.archive_sources(ep, CONTRACT)), ["apollo-era"])


class IngestBeforeCuttingTests(unittest.TestCase):
    """The archival layer is produced by the same run that cuts it, from the same numbers.

    `build_segments` refuses a shot with no clip (decision D-043), so an `archive` shot only reaches
    a master if something made its clip first. That something is the assembler: cards are drawn in
    the run for the same reason, and an ingest left to be remembered by the operator is an ingest
    that gets skipped on the night, when the fallback is a black frame rather than an error.

    `ingest_clip` is replaced by a recorder here, on purpose: what these tests judge is *which*
    record, rights row and screen time the assembler hands the ingest, and how many times it asks.
    What the encoder then does with them is `test_archive_ingest.py`'s question, at real pixels.
    """

    def setUp(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import archive_ingest
        import assemble_episode
        self.A = assemble_episode
        self.calls = []
        self.real = archive_ingest.ingest_clip
        archive_ingest.ingest_clip = self._recorded
        self.addCleanup(setattr, archive_ingest, "ingest_clip", self.real)

    def _recorded(self, src, dst, **kwargs):
        """Stand in for the encoder: note everything, and leave a file where the clip would land.

        The file matters as much as the note — the caching tests below ask the second call to see
        what the first one produced, and a fake that returns without writing would test a pipeline
        state that cannot happen.
        """
        self.calls.append({"src": Path(src), "dst": Path(dst), "kwargs": kwargs})
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        Path(dst).write_bytes(b"canvas-shaped archival clip")
        return {"path": Path(dst), "duration_s": 6.0, "flipped": False, "flip_reason": "",
                "card": False, "card_reason": "not drawn by the fake"}

    def manifest(self, archive_s=4.0, other_s=3.0):
        rate = 24000
        return {"sampleRate": rate, "totalSamples": int((archive_s + other_s) * rate),
                "utterances": [{"id": "u001", "file": "u001.wav", "samples": int(archive_s * rate)},
                               {"id": "u002", "file": "u002.wav", "samples": int(other_s * rate)}]}

    def test_a_shot_with_no_clip_is_ingested_once(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ep = archival(Path(tmp))
            shot_map = E.shots(ep, CONTRACT)
            self.A.ingest_archive(ep, self.manifest(), shot_map, CONTRACT, root=ROOT)
        self.assertEqual(len(self.calls), 1, "one archival shot, one ingest — the 3D shot must not "
                                             "reach the archive encoder")
        call = self.calls[0]
        self.assertEqual(call["src"], ep / "assets" / "archive" / "apollo_boot_1969.mp4")
        self.assertEqual(call["dst"], E.render_dir(ep, "archive", CONTRACT) / "apollo-era.mp4")
        self.assertEqual(call["kwargs"]["record"]["asset"],
                         "assets/archive/apollo_boot_1969.mp4")
        self.assertEqual(call["kwargs"]["licence_row"]["id"], "arch-001")
        self.assertIs(call["kwargs"]["contract"], CONTRACT)
        self.assertIs(call["kwargs"]["root"], ROOT,
                      "the ingest resolves the contract's font through the root it was given; a "
                      "root of its own would read the repo the module lives in")

    def test_the_credit_card_is_asked_for(self):
        """`source_card.on_screen` is the contract's rule and the quotation's evidence, but the
        ingest only draws a plate when the caller asks; an archive that ships unattributed is a
        rights failure, not a look failure."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ep = archival(Path(tmp))
            self.A.ingest_archive(ep, self.manifest(), E.shots(ep, CONTRACT), CONTRACT, root=ROOT)
        self.assertTrue(self.calls[0]["kwargs"]["card"])

    def test_a_clip_that_is_already_there_is_not_ingested_again(self):
        """Caching is how this pipeline survives a re-run: every other producer in `main` checks
        for its output first, and an ingest that always re-encodes turns a segment rebuild into a
        crawl through the archive."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ep = archival(Path(tmp))
            clip = E.render_dir(ep, "archive", CONTRACT) / "apollo-era.mp4"
            clip.parent.mkdir(parents=True)
            clip.write_bytes(b"ingested by the last run")
            self.A.ingest_archive(ep, self.manifest(), E.shots(ep, CONTRACT), CONTRACT, root=ROOT)
            self.assertEqual(self.calls, [])
            self.assertEqual(clip.read_bytes(), b"ingested by the last run",
                             "the cached clip was overwritten")

    def test_a_film_with_no_archival_layer_asks_the_ingest_for_nothing(self):
        """3D-only is legal at this stage (the mix rule is the one that judges it), so the ingest
        step must be a no-op rather than a refusal or an empty ffmpeg run."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ep = archival(Path(tmp), record_file=False,
                          table={"u001": {"kind": "3d", "name": "launch"},
                                 "u002": {"kind": "3d", "name": "launch"}})
            self.assertEqual(
                self.A.ingest_archive(ep, self.manifest(), E.shots(ep, CONTRACT), CONTRACT,
                                      root=ROOT), [])
        self.assertEqual(self.calls, [])

    def test_a_still_is_given_the_seconds_its_shot_is_on_screen(self):
        """`still_filter` sizes the pan from a duration and refuses to guess one, and the only
        duration this run knows is the narration over the shot. A still cut shorter than the
        sentence it plays under freezes on its last frame — the dead still `stills_never_dead`
        names — while one cut longer is sliced back by the segment build, so the cut's number wins
        in both directions and the record's own `seconds` stays a default for direct callers."""
        import tempfile
        from workflow.archive import paths
        with tempfile.TemporaryDirectory() as tmp:
            still = dict(ARCHIVE_RECORD, form="still", seconds=1.0, native_fps=None,
                         motion_mode=None,
                         still_move={"pan_deg": 2.0, "zoom_from": 1.0, "zoom_to": 1.12})
            ep = archival(Path(tmp), record={"apollo-era": still})
            self.A.ingest_archive(ep, self.manifest(archive_s=6.0), E.shots(ep, CONTRACT),
                                  CONTRACT, root=ROOT)
            on_disk = json.loads((ep / paths(CONTRACT)["records_filename"]).read_text(
                encoding="utf-8"))
        handed = self.calls[0]["kwargs"]["record"]
        self.assertEqual(handed["seconds"], 6.0)
        self.assertEqual(on_disk["apollo-era"]["seconds"], 1.0,
                         "the cut's number is an argument to the ingest, not a rewrite of the "
                         "authoring it was cut from")

    def test_a_clip_is_not_handed_a_screen_time_it_cannot_use(self):
        """The clip's own length comes from the source it was cut from; `seconds` belongs to the
        still rules, and a stray number on a clip record is the assembler answering a question the
        retime rules already own."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ep = archival(Path(tmp))
            self.A.ingest_archive(ep, self.manifest(), E.shots(ep, CONTRACT), CONTRACT, root=ROOT)
        self.assertNotIn("seconds", self.calls[0]["kwargs"]["record"])

    def test_the_ingest_step_reports_what_it_made(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ep = archival(Path(tmp))
            made = self.A.ingest_archive(ep, self.manifest(), E.shots(ep, CONTRACT), CONTRACT,
                                         root=ROOT)
        self.assertEqual([Path(p) for p in made], [self.calls[0]["dst"]])


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not on PATH")
class ArchiveSegmentMotionTests(unittest.TestCase):
    def test_a_short_archive_clip_does_not_freeze_when_narration_runs_longer(self):
        import tempfile
        sys.path.insert(0, str(ROOT / "tools"))
        import archive_ingest as AI
        import assemble_episode as A

        with tempfile.TemporaryDirectory() as tmp:
            ep = seeded(Path(tmp), "episode-archive-tail")
            source = A.render_dir(ep, "archive", CONTRACT) / "alexnet-era.mp4"
            source.parent.mkdir(parents=True)
            subprocess.run([
                "ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                "-i", "testsrc2=size=320x240:rate=30:duration=2",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
                str(source),
            ], check=True)
            manifest = {"sampleRate": 24000, "utterances": [
                {"id": "u001", "samples": 120000},
            ]}
            A.build_segments(ep, manifest, {"u001": ("archive", "alexnet-era")})
            segment = E.segments_dir(ep) / "u001.mp4"
            self.assertAlmostEqual(AI.probe_duration(segment), 5.0, delta=0.2)
            self.assertGreater(
                AI.frame_diff(segment, 3.0, 4.0,
                             canvas=(CONTRACT["canvas"]["width"], CONTRACT["canvas"]["height"])),
                0.0005,
                "the overrun was padded with a frozen last frame",
            )

    def test_a_static_video_container_still_gets_a_terminating_move(self):
        import tempfile
        sys.path.insert(0, str(ROOT / "tools"))
        import archive_ingest as AI

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "static-container.mp4"
            output = root / "moving-still.mp4"
            subprocess.run([
                "ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                "-i", "testsrc2=size=320x240:rate=30:duration=1",
                "-vf", r"select=eq(n\,0),tpad=stop_mode=clone:stop_duration=2",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
                str(source),
            ], check=True)
            AI.ingest_clip(
                source, output,
                record={
                    "asset": "assets/archive/static-container.mp4",
                    "form": "still",
                    "aspect": "pillarbox_visible_edge",
                    "still_move": {"pan_deg": 2.0, "zoom_from": 1.03, "zoom_to": 1.15},
                    "seconds": 5.0,
                },
                licence_row={}, contract=CONTRACT, root=ROOT, card=False,
            )
            self.assertAlmostEqual(AI.probe_duration(output), 5.0, delta=0.2)
            self.assertGreater(AI.frame_diff(output, 3.0, 4.0), 0.0005)


class ArchiveShotLengthTests(unittest.TestCase):
    """Who owes `shot_lengths.json` a number, read off the layers rather than off a list of names.

    The table is the film's beat timing: the renderers size a camera move to it and the rhythm rule
    measures an archival shot against `max_archival_shot_seconds` with it. A layer whose clips come
    from a real source file therefore owes it, and the only layer that does not is the one drawn
    inside this run at the exact length of the sentence under it — which is why the exemption is one
    shared answer with the clip naming, not a second `== "cards"` in a second function.
    """

    def setUp(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import assemble_episode
        self.A = assemble_episode

    def test_an_archival_shot_owes_a_length_exactly_like_a_rendered_one(self):
        """Would fail the moment `archive` joins the exemption list — see the report for the
        mutation that shows it firing."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ep = archival(Path(tmp))
            manifest = {"sampleRate": 24000, "utterances": [
                {"id": "u001", "samples": 96000},   # 4 s over the archival beat
                {"id": "u002", "samples": 72000}]}  # 3 s over the 3D beat
            self.A.write_shot_lengths(ep, manifest, E.shots(ep, CONTRACT))
            table = json.loads(E.shot_lengths_path(ep).read_text(encoding="utf-8"))
        self.assertEqual(table, {"apollo-era": 4, "launch": 3})

    def test_the_exempt_layers_are_the_ones_cut_per_utterance(self):
        """The guard against the two questions drifting apart: the layers with no length in the
        table are exactly the layers whose clips are named for the utterance, and the rest of
        `layers(contract)` is present. Reads the same map the assembler does, so it fails when the
        map stops describing the film."""
        import tempfile
        declared = E.layers(CONTRACT)
        per_utterance = set(self.A.PER_UTTERANCE_CLIPS)
        self.assertTrue(per_utterance, "an empty exemption would put card beats in the table")
        self.assertLessEqual(per_utterance, set(declared))
        table = {f"u{n:03d}": {"kind": kind, "name": f"{kind}-shot"}
                 for n, kind in enumerate(declared, start=1)}
        rate = 24000
        manifest = {"sampleRate": rate,
                    "utterances": [{"id": uid, "samples": rate} for uid in table]}
        with tempfile.TemporaryDirectory() as tmp:
            ep = archival(Path(tmp), table=table)
            self.A.write_shot_lengths(ep, manifest, E.shots(ep, CONTRACT))
            written = json.loads(E.shot_lengths_path(ep).read_text(encoding="utf-8"))
        self.assertEqual(set(written), {f"{kind}-shot" for kind in declared} -
                         {f"{kind}-shot" for kind in per_utterance})
        self.assertEqual(self.A.clip_stem("cards", "u022", "bar-chart"), "card-u022")
        self.assertEqual(self.A.clip_stem("archive", "u001", "apollo-era"), "apollo-era")


class NoEpisodeLiteralsLeftTests(unittest.TestCase):
    """A default that lives in code is a default with one episode in it.

    These are the guards that make the deletion stick. Without them the next convenience puts
    `work/episode-artemis-ii` back into `tools/`, and a second episode silently inherits a first
    episode's shots.
    """

    TOOLS = ("tools/assemble_episode.py", "tools/rollout_render.py",
             "tools/qc_shot_continuity.py", "tools/qc_montage.py")

    def live_code(self, rel):
        """The file with comments and docstrings parsed away.

        A usage example naming a real film is documentation — `tools/qc_episode.py`, the tool this
        one is modelled on, has had one since #122 — and a guard that flags it gets weakened to
        exempt prose, which is exactly the exemption a rolled-back literal would hide behind. Only
        executable strings survive `ast.unparse`, so `"work/episode-artemis-ii"` in code fails here
        while the same path in a docstring does not.
        """
        tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            body = getattr(node, "body", None)
            if isinstance(body, list) and body and isinstance(body[0], ast.Expr) \
                    and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                body.pop(0)
        return ast.unparse(tree)

    def test_no_pipeline_tool_names_the_artemis_episode(self):
        for rel in self.TOOLS:
            with self.subTest(rel):
                self.assertNotIn("episode-artemis-ii", self.live_code(rel),
                                 f"{rel} still pins one episode in live code")

    def test_no_pipeline_tool_carries_a_shot_table_literal(self):
        for rel in self.TOOLS:
            src = self.live_code(rel)
            with self.subTest(rel):
                self.assertNotIn("VISUAL_MAP", src,
                                 f"{rel} still defines or imports a hardcoded visual map")
                self.assertListEqual([], [line for line in src.splitlines()
                                           if '"u0' in line],
                                     f"{rel} still hardcodes utterance ids")

    def test_no_pipeline_tool_names_an_episode_s_own_render(self):
        """#147's three leftovers: the builder script, the luma baseline and the hero beat.

        They were `rollout_render.py`'s own literals, so the queue rendered exactly one film and a
        second episode's `finish` stage re-cut a beat that film never had. `tools/blender/` is
        deliberately outside this check: those *are* per-episode authoring — `bench_beat.py` and
        `lunar_ground_probe.py` import a specific film's builder, and that is the point of them —
        while a dispatcher that names one is a dispatcher that cannot be told which film to drive.
        """
        for rel in self.TOOLS:
            src = self.live_code(rel)
            for literal in ("artemis_beats", "baseline-luma", "sls-launch"):
                with self.subTest(rel=rel, literal=literal):
                    self.assertNotIn(literal, src,
                                     f"{rel} still renders one episode out of the box")

    def test_the_assembler_takes_an_episode_argument(self):
        src = (ROOT / "tools" / "assemble_episode.py").read_text(encoding="utf-8")
        self.assertIn('"--episode"', src,
                      "the assembler must be told which film to build, the way qc_episode is")

    def test_the_assembler_declares_no_narration_sample_rate(self):
        """The manifest carries `sampleRate`, so a constant here is a second answer to one question.

        Naming the value rather than the identifier: `SAMPLE_RATE = 24000` returning under another
        name would still be the bug, and the rate belongs to the audio, not to the tool.
        """
        src = self.live_code("tools/assemble_episode.py")
        self.assertNotIn("24000", src,
                         "the assembler states its own narration rate instead of reading the "
                         "manifest's `sampleRate`")
        self.assertIn("sampleRate", src,
                      "nothing in the assembler reads the rate the narration declares")


if __name__ == "__main__":
    unittest.main()
