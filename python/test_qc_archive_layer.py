# -*- coding: utf-8 -*-
"""What `tools/qc_episode.py` says about the archival layer, and how loudly.

The rules themselves live in `workflow/archive.py` — #142 wrote them, #147 made the kind render.
This file judges the gate's reporting of them, which is a different question and the one the
pipeline was missing: an episode could ship 3D-only and every gate stayed silent, because
nothing translated the library's answers into findings the build reads.

The ladder decides the severity, and only the ladder:

  * metadata — `records()`, `ledger()`, the opt-out record — is deterministic, so a refusal from
    those validators lands as an `error` carrying the validator's own sentence. Paraphrasing it
    here would be a second answer to one question, and the two would drift.
  * the mix is judged in the rung `resolve_mode()` returns: `warn` reports, `closed` refuses,
    `off` says nothing.
  * the pixel bounds stay `warn`, because `enforcement_policy` will not let a number taken from
    anything other than our own frames stop a build.

Artemis II has no archival layer, so every finding it gains from this file is on the warn side.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "python"))
sys.path.insert(0, str(ROOT / "tools"))

import qc_episode  # noqa: E402
from workflow import archive  # noqa: E402
from workflow.config import style_contract  # noqa: E402
# The rights row and the shot record are 22 and 9 fields long; a second copy of them here would
# be a fixture that drifts from the validator it is supposed to satisfy.
from test_archive_records import (GOOD_LEDGER_ROW, GOOD_RECORD,  # noqa: E402
                                  episode as archival_layer, without)

CONTRACT = style_contract(ROOT)
RECORDS_NAME = archive.paths(CONTRACT)["records_filename"]
LEDGER_NAME = archive.paths(CONTRACT)["ledger_filename"]
CEILING = float(CONTRACT["archive"]["archive_rhythm"]["max_archival_shot_seconds"])
LUMA_WINDOW = float(CONTRACT["archive"]["cohesion"]["blend_luma_window_fraction"])
CUT_MAX = float(CONTRACT["archive"]["cohesion"]["loudness_delta_across_cuts_max_lu"])
# A complete, valid archival episode: one shot, its record, its rights row.
GOOD_EPISODE = {RECORDS_NAME: GOOD_RECORD, LEDGER_NAME: [GOOD_LEDGER_ROW]}


def shot(uid, kind, name, start, duration):
    return qc_episode.Shot(id=uid, kind=kind, name=name, start=start, duration=duration)


def timeline(*specs):
    """Shots laid end to end from zero, so every start and second is known by construction.

    The mix and rhythm findings quote seconds back in their text, so a fixture whose arithmetic
    the test also does by hand is the only thing that catches a mistranslated adapter field:
    `seconds` read from `start` changes a number, and a number is what this asserts on.
    """
    shots, start = [], 0.0
    for uid, kind, name, duration in specs:
        shots.append(shot(uid, kind, name, round(start, 3), float(duration)))
        start += duration
    return shots


def library_finding(code="some_code", severity="warning", message="what the library said"):
    return archive.Finding(code, severity, message)


def episode_dir(tmp, files=None, *, archival=True, shots=None):
    """An episode holding `files`, plus a timeline long enough for the mix to mean something."""
    directory = Path(tmp)
    if archival:
        archival_layer(directory)
    for relative, payload in (files or {}).items():
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    write_timeline(directory, shots or [("u001", "archive", "apollo-boot", 10.0),
                                        ("u002", "3d", "sls-launch", 40.0)])
    return directory


def published_shots(directory):
    """The shot list exactly as `run()` will read it from the fixture's own `shots.json`.

    Hand-writing a second copy of a fixture's timeline is how a test ends up judging a film the
    episode directory does not contain; `load_timeline` is the gate's own reader, so the shots the
    check sees and the shots the check was built with cannot drift apart.
    """
    return qc_episode.load_timeline(Path(directory))


def archival_findings(findings):
    """Only the findings this task added: the pre-existing checks keep their own opinions."""
    return [f for f in findings
            if f.code.startswith(("archive", "archival", "blend_luma", "cut_loud"))]


def write_timeline(directory, specs):
    """`vo/manifest.json` and `shots.json` for a shot list, at the delivery sample rate."""
    rate = 24000
    utterances, map_, start = [], {}, 0
    for uid, kind, name, duration in specs:
        samples = round(duration * rate)
        utterances.append({"id": uid, "file": f"{uid}.wav", "text": "x", "samples": samples,
                           "startSample": start, "endSample": start + samples})
        map_[uid] = {"kind": kind, "name": name}
        start += samples
    (directory / "vo").mkdir(parents=True, exist_ok=True)
    (directory / "vo/manifest.json").write_text(
        json.dumps({"sampleRate": rate, "voice": "af_heart", "totalSamples": start,
                    "utterances": utterances}), encoding="utf-8")
    (directory / "shots.json").write_text(json.dumps(map_, indent=1), encoding="utf-8")
    return directory


def codes(findings):
    return [f.code for f in findings]


class FindingAdapter(unittest.TestCase):
    """The library's `Finding(code, severity, message)` is not the gate's
    `Finding(severity, code, subject, message)`: different order, and `warning` where the gate
    writes `warn`. Passing one into `render()` is a crash on the first archival episode."""

    def test_a_library_warning_becomes_a_gate_warn_carrying_its_own_words(self):
        finding = qc_episode.to_gate_finding(library_finding(), "the subject")
        self.assertEqual(finding.severity, "warn")
        self.assertEqual(finding.code, "some_code")
        self.assertEqual(finding.subject, "the subject")
        self.assertEqual(finding.message, "what the library said")

    def test_the_library_s_error_word_is_not_mistaken_for_the_gate_s(self):
        """archive.py never emits `error` today, but the table has to say what it would mean, or
        the day it does the gate reports a blocker as advice."""
        finding = qc_episode.to_gate_finding(library_finding(severity="error"), "the subject")
        self.assertEqual(finding.severity, "error")

    def test_a_severity_neither_file_defines_is_refused_not_guessed(self):
        with self.assertRaises(ValueError) as caught:
            qc_episode.to_gate_finding(library_finding(severity="blocker"), "the subject")
        self.assertIn("blocker", str(caught.exception))

    def test_the_ladder_can_move_one_finding_without_editing_the_library(self):
        """`closed` is a rung, not a library severity: the same finding text has to be able to
        arrive as advice or as a refusal, and only the gate knows which episode is in which."""
        finding = qc_episode.to_gate_finding(library_finding(), "subject", severity="error")
        self.assertEqual(finding.severity, "error")
        self.assertEqual(finding.message, "what the library said")

    def test_the_report_prints_an_adapted_finding(self):
        text = qc_episode.render([qc_episode.to_gate_finding(library_finding(), "subject")])
        self.assertIn("[some_code] subject: what the library said", text)


class MixAdapter(unittest.TestCase):
    """`_seconds_by_layer` reads `layer`/`start`/`seconds`; the timeline has
    `kind`/`start`/`duration`. One function translates, and it is judged on numbers."""

    def test_a_timeline_shot_becomes_the_layer_the_contract_names(self):
        adapted = qc_episode.mix_shots(timeline(("u001", "3d", "sls", 60.0),
                                                ("u002", "archive", "eva", 10.5)))
        self.assertEqual(adapted, [{"layer": "3d", "start": 0.0, "seconds": 60.0},
                                   {"layer": "archive", "start": 60.0, "seconds": 10.5}])

    def test_the_seconds_the_mix_report_prints_are_the_timeline_s_own(self):
        """60 s of 3D and 10 s of archive is 0.143 archival. Any field crossing over — `seconds`
        read from `start`, `start` read from `duration` — moves a printed number."""
        findings = qc_episode.check_archive_mix(
            timeline(("u001", "3d", "sls", 60.0), ("u002", "archive", "eva", 10.0)),
            CONTRACT, {})
        self.assertEqual(codes(findings), ["archive_share_low"])
        self.assertIn("0.143", findings[0].message)
        self.assertIn("70.0", findings[0].message)
        self.assertIn("10.0", findings[0].message)


class MixRung(unittest.TestCase):
    def test_the_warn_rung_reports_the_mix_without_refusing_it(self):
        findings = qc_episode.check_archive_mix(
            timeline(("u001", "3d", "sls", 100.0), ("u002", "archive", "eva", 5.0)),
            CONTRACT, {})
        self.assertTrue(findings)
        self.assertEqual({f.severity for f in findings}, {"warn"})

    def test_closed_turns_the_same_finding_into_an_error_with_the_same_text(self):
        shots = timeline(("u001", "3d", "sls", 100.0), ("u002", "archive", "eva", 5.0))
        warned = qc_episode.check_archive_mix(shots, CONTRACT, {})
        refused = qc_episode.check_archive_mix(shots, CONTRACT, {"archive": {"mode": "closed"}})
        self.assertEqual(codes(refused), codes(warned))
        self.assertEqual([f.message for f in refused], [f.message for f in warned])
        self.assertEqual({f.severity for f in refused}, {"error"})

    def test_off_judges_nothing_at_all(self):
        contract = json.loads(json.dumps(CONTRACT))
        contract["archive"]["episode_profile"]["mode"] = "off"
        self.assertEqual(qc_episode.check_archive_mix(
            timeline(("u001", "3d", "sls", 100.0)), contract, {}), [])

    def test_a_film_with_no_archival_layer_says_so_once(self):
        findings = qc_episode.check_archive_mix(
            timeline(("u001", "3d", "sls", 100.0), ("u002", "manim", "orbit", 30.0)),
            CONTRACT, {})
        self.assertEqual(codes(findings), ["archive_layer_missing"])

    def test_a_layer_the_taxonomy_never_budgeted_is_reported_not_folded_in(self):
        findings = qc_episode.check_archive_mix(
            timeline(("u001", "archive", "eva", 20.0), ("u002", "live-action", "street", 20.0)),
            CONTRACT, {})
        self.assertIn("layer_unknown", codes(findings))
        self.assertEqual(findings[0].severity, "warn")

    def test_an_opt_out_record_lowers_the_rung_without_muting_the_mix(self):
        document = {"archive": {"mode": "closed", "enabled": False,
                                "reason": "rights_unavailable", "scope": "episode",
                                "approved_by": "the owner", "expires": "2099-01-01"}}
        findings = qc_episode.check_archive_mix(
            timeline(("u001", "3d", "sls", 100.0), ("u002", "archive", "eva", 5.0)),
            CONTRACT, document)
        self.assertTrue(findings)
        self.assertEqual({f.severity for f in findings}, {"warn"})


class MetadataRules(unittest.TestCase):
    """Metadata is on the blocking side of `enforcement_policy`, and a validator's refusal is a
    finding, not a traceback: the gate has to report the whole episode even when one row is bad."""

    def test_a_complete_archival_episode_produces_no_metadata_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = episode_dir(tmp)
            self.assertEqual(qc_episode.check_archive_metadata(
                directory, CONTRACT, {}, published_shots(directory)), [])

    def test_an_episode_with_no_archival_layer_at_all_produces_nothing(self):
        """Absence of the layer is the mix rule's judgement. Reporting it here too would state one
        fact twice and let a reader negotiate with whichever copy they liked.

        Superseded 2026-11-13 by fix round 1: this fixture used to leave the default timeline in
        place, which carries a shot of kind `archive`, so the episode it described was not a film
        with no archival layer at all but a film presenting archival footage with no book. The
        assertion is unchanged and still holds; the timeline now matches the test's own name."""
        with tempfile.TemporaryDirectory() as tmp:
            empty = episode_dir(tmp, archival=False,
                                shots=[("u001", "3d", "sls-launch", 50.0)])
            self.assertEqual(qc_episode.check_archive_metadata(
                empty, CONTRACT, {}, published_shots(empty)), [])

    def test_a_record_citing_a_licence_row_that_does_not_exist_is_an_error(self):
        broken = without(GOOD_RECORD, licence="arch-999")
        with tempfile.TemporaryDirectory() as tmp:
            directory = episode_dir(tmp, {RECORDS_NAME: {"apollo-boot": broken}})
            findings = qc_episode.check_archive_metadata(
                directory, CONTRACT, {}, published_shots(directory))
        self.assertEqual([f.severity for f in findings], ["error"])
        self.assertIn("arch-999", findings[0].message)
        self.assertIn(LEDGER_NAME, findings[0].message + findings[0].subject)

    def test_a_record_and_a_row_disagreeing_about_the_file_is_an_error(self):
        broken = without(GOOD_RECORD, asset="assets/archive/other.mp4")
        with tempfile.TemporaryDirectory() as tmp:
            directory = episode_dir(tmp, {RECORDS_NAME: {"apollo-boot": broken}})
            findings = qc_episode.check_archive_metadata(
                directory, CONTRACT, {}, published_shots(directory))
        self.assertEqual([f.severity for f in findings], ["error"])
        self.assertIn("assets/archive/other.mp4", findings[0].message)

    def test_a_missing_required_ledger_field_is_an_error_naming_the_field(self):
        broken = without(GOOD_LEDGER_ROW, credit_line=None)
        with tempfile.TemporaryDirectory() as tmp:
            directory = episode_dir(tmp, {LEDGER_NAME: [broken]})
            findings = qc_episode.check_archive_metadata(
                directory, CONTRACT, {}, published_shots(directory))
        self.assertEqual([f.severity for f in findings], ["error"])
        self.assertIn("credit_line", findings[0].message)
        self.assertEqual(findings[0].subject, LEDGER_NAME)

    def test_an_enum_violation_is_an_error(self):
        broken = without(GOOD_RECORD, aspect="crop_to_fill")
        with tempfile.TemporaryDirectory() as tmp:
            directory = episode_dir(tmp, {RECORDS_NAME: {"apollo-boot": broken}})
            findings = qc_episode.check_archive_metadata(
                directory, CONTRACT, {}, published_shots(directory))
        self.assertEqual([f.severity for f in findings], ["error"])
        self.assertIn("crop_to_fill", findings[0].message)

    def test_the_validator_s_own_sentence_reaches_the_operator_unedited(self):
        """The validators are written in the voice the operator needs; a paraphrase here is a
        second answer that will drift from the first."""
        broken = without(GOOD_RECORD, form="reel")
        with tempfile.TemporaryDirectory() as tmp:
            directory = episode_dir(tmp, {RECORDS_NAME: {"apollo-boot": broken}})
            with self.assertRaises(ValueError) as caught:
                archive.records(directory, CONTRACT)
            library_said = str(caught.exception)
            findings = qc_episode.check_archive_metadata(
                directory, CONTRACT, {}, published_shots(directory))
        self.assertIn("reel", library_said)
        self.assertIn(library_said, findings[0].message)

    def test_one_broken_file_is_reported_once(self):
        """`records()` reads the ledger, so a bad row surfaces in both calls. Two findings naming
        two different files would send the operator to the wrong one."""
        broken = without(GOOD_LEDGER_ROW, credit_line=None)
        with tempfile.TemporaryDirectory() as tmp:
            directory = episode_dir(tmp, {LEDGER_NAME: [broken]})
            findings = qc_episode.check_archive_metadata(
                directory, CONTRACT, {}, published_shots(directory))
        self.assertEqual(len(findings), 1)

    def test_an_opt_out_record_is_reported_as_advice_on_the_default_rung(self):
        document = {"archive": {"enabled": False, "reason": "topic_has_no_archive",
                                "scope": "episode", "approved_by": "the owner",
                                "expires": "2099-01-01"}}
        with tempfile.TemporaryDirectory() as tmp:
            directory = episode_dir(tmp)
            findings = qc_episode.check_archive_metadata(
                directory, CONTRACT, document, published_shots(directory))
        self.assertEqual(codes(findings), ["archive_layer_opted_out"])
        self.assertEqual(findings[0].severity, "warn")
        self.assertIn("topic_has_no_archive", findings[0].message)

    def test_an_opt_out_record_that_is_not_reviewable_is_an_error(self):
        """A waiver with no approver is exactly the unlogged exception the contract's opt-out
        block exists to make impossible, so it blocks rather than warns."""
        document = {"archive": {"enabled": False, "reason": "deadline_salvage",
                                "scope": "episode", "expires": "2099-01-01"}}
        with tempfile.TemporaryDirectory() as tmp:
            directory = episode_dir(tmp)
            findings = qc_episode.check_archive_metadata(
                directory, CONTRACT, document, published_shots(directory))
        self.assertEqual([f.severity for f in findings], ["error"])
        self.assertIn("approved_by", findings[0].message)

    def test_an_episode_that_widens_the_ladder_is_refused(self):
        """An episode document that could pick a looser rung than the contract would make the
        pipeline-wide default a suggestion again."""
        document = {"archive": {"mode": "off"}}
        with tempfile.TemporaryDirectory() as tmp:
            directory = episode_dir(tmp)
            findings = qc_episode.check_archive_metadata(
                directory, CONTRACT, document, published_shots(directory))
        self.assertEqual([f.severity for f in findings], ["error"])
        self.assertIn("off", findings[0].message)

    # ---------------------------------------------------- the book against the film (#148 fix 1)
    #
    # `archive.json` declares a layer; the timeline presents one. Until this round nothing in the
    # gate compared the two, and `workflow/archive.py::records()` cannot — it has no shot list. The
    # five tests below are that comparison, in both directions, and all of them are `error`s
    # because metadata is the blocking half of the layer.

    def test_an_archival_shot_with_no_record_is_an_error_naming_the_shot_and_the_records_file(self):
        """The stale-clip path: the assembler resolves an archival shot by name, so a clip left on
        disk from an earlier build cuts in even after its record has been deleted, and the gate
        that judged only the declared layer said nothing. The message has to tell the operator what
        to write, not merely that something is absent."""
        with tempfile.TemporaryDirectory() as tmp:
            directory = episode_dir(tmp, archival=False)      # apollo-boot is on the timeline
            findings = qc_episode.check_archive_metadata(
                directory, CONTRACT, {}, published_shots(directory))
        self.assertEqual(codes(findings), ["archive_shot_without_record"])
        self.assertEqual(findings[0].severity, "error")
        self.assertEqual(findings[0].subject, "apollo-boot")
        self.assertIn("apollo-boot", findings[0].message)
        self.assertIn(RECORDS_NAME, findings[0].message)
        self.assertIn("licence", findings[0].message)

    def test_every_archival_shot_the_timeline_carries_owing_a_record_produces_nothing(self):
        """The exemption direction, on a two-shot layer: a rule that fires against a complete book
        is noise, and noise is how a rights gate gets ignored. `records()` is keyed by shot name,
        so two archival shots citing one rights row are covered, not half-covered."""
        with tempfile.TemporaryDirectory() as tmp:
            directory = episode_dir(
                tmp, {RECORDS_NAME: {"apollo-boot": GOOD_RECORD, "boot-closeup": GOOD_RECORD}},
                shots=[("u001", "archive", "apollo-boot", 8.0),
                       ("u002", "archive", "boot-closeup", 8.0),
                       ("u003", "3d", "sls-launch", 34.0)])
            findings = qc_episode.check_archive_metadata(
                directory, CONTRACT, {}, published_shots(directory))
        self.assertEqual(findings, [])

    def test_a_record_naming_a_shot_the_film_does_not_carry_is_an_error(self):
        """The other direction of the same book: footage the ledger describes that is not in the
        film is either a cut shot or a record pointing at the wrong name, and a reader cannot tell
        which from a warning, so it refuses."""
        with tempfile.TemporaryDirectory() as tmp:
            directory = episode_dir(tmp, {RECORDS_NAME: {
                "apollo-boot": GOOD_RECORD, "saturn-v-rollout": GOOD_RECORD}})
            findings = qc_episode.check_archive_metadata(
                directory, CONTRACT, {}, published_shots(directory))
        self.assertEqual(codes(findings), ["archive_record_without_shot"])
        self.assertEqual(findings[0].severity, "error")
        self.assertEqual(findings[0].subject, "saturn-v-rollout")
        self.assertIn("saturn-v-rollout", findings[0].message)
        self.assertIn(RECORDS_NAME, findings[0].message)

    def test_a_3d_only_episode_owes_no_records_and_stays_quiet(self):
        """The shape Artemis II actually ships: 3d, manim and cards, and no `archive.json` at all.
        Both new loops must come back empty on it, or the film already published starts failing a
        gate that was written after it."""
        with tempfile.TemporaryDirectory() as tmp:
            directory = episode_dir(tmp, archival=False, shots=[
                ("u001", "3d", "gateway", 20.0), ("u002", "manim", "orbit", 15.0),
                ("u003", "cards", "splashdown", 15.0)])
            self.assertEqual(qc_episode.check_archive_metadata(
                directory, CONTRACT, {}, published_shots(directory)), [])

    def test_the_rights_book_disagreeing_with_the_film_blocks_rather_than_warns(self):
        """`metadata blocks` is the whole contract of this task, so the severity word is asserted
        on its own, on both directions at once: one unrecorded archival shot and one record for a
        shot the film does not present as archival. A `warn` here would let #132 publish the
        master with unattributed footage in it."""
        with tempfile.TemporaryDirectory() as tmp:
            directory = episode_dir(tmp, {RECORDS_NAME: {"sls-launch": GOOD_RECORD}})
            findings = qc_episode.check_archive_metadata(
                directory, CONTRACT, {}, published_shots(directory))
        self.assertEqual(codes(findings), ["archive_shot_without_record",
                                           "archive_record_without_shot"])
        self.assertEqual([f.subject for f in findings], ["apollo-boot", "sls-launch"])
        self.assertEqual({f.severity for f in findings}, {"error"})
        self.assertNotIn("warn", {f.severity for f in findings})


class ArchivalRhythm(unittest.TestCase):
    """Screen seconds per archival shot, from the gate's own timeline. Warn, because the bound
    is `archive_rhythm.archival_share_status`'s unvalidated cousin."""

    def test_an_archival_shot_past_the_contract_ceiling_is_a_warning(self):
        findings = qc_episode.check_archival_rhythm(
            timeline(("u001", "archive", "eva-boot", CEILING + 1.0)), CONTRACT)
        self.assertEqual([f.severity for f in findings], ["warn"])
        self.assertEqual(codes(findings), ["archival_shot_long"])
        self.assertIn("eva-boot", findings[0].subject)

    def test_a_shot_exactly_at_the_ceiling_is_not_reported(self):
        """The ceiling is a maximum, and the removal test it comes from excuses the length it
        names; `>` is the difference between a bound and an off-by-one."""
        self.assertEqual(qc_episode.check_archival_rhythm(
            timeline(("u001", "archive", "eva-boot", CEILING)), CONTRACT), [])

    def test_the_reported_number_and_the_bound_agree_after_rounding(self):
        """A shot that fails by four hundredths of a second prints as its own ceiling, which
        reads as a broken gate; the comparison is made on the number the message shows."""
        findings = qc_episode.check_archival_rhythm(
            timeline(("u001", "archive", "eva-boot", CEILING + 0.04)), CONTRACT)
        self.assertEqual(findings, [])
        findings = qc_episode.check_archival_rhythm(
            timeline(("u001", "archive", "eva-boot", CEILING + 0.06)), CONTRACT)
        self.assertEqual(len(findings), 1)
        self.assertIn(f"{CEILING + 0.1:.1f}", findings[0].message)

    def test_a_long_rendered_shot_is_judged_by_the_existing_rule_not_this_one(self):
        """`rhythm.max_shot_seconds` already watches the 3D side; flagging every long shot here
        would make the archival bound look like it fired on shots it does not cover."""
        self.assertEqual(qc_episode.check_archival_rhythm(
            timeline(("u001", "3d", "sls-launch", 44.0)), CONTRACT), [])

    def test_the_ceiling_is_read_from_the_contract(self):
        contract = json.loads(json.dumps(CONTRACT))
        contract["archive"]["archive_rhythm"]["max_archival_shot_seconds"] = CEILING + 10.0
        self.assertEqual(qc_episode.check_archival_rhythm(
            timeline(("u001", "archive", "eva-boot", CEILING + 1.0)), contract), [])

    def test_the_finding_names_the_measurement_that_would_promote_it(self):
        """A warn bound with no route to error is a permanent warning; the calibration owner is
        the first archival episode's own distribution, and the finding has to say so."""
        findings = qc_episode.check_archival_rhythm(
            timeline(("u001", "archive", "eva-boot", CEILING + 2.0)), CONTRACT)
        self.assertRegex(findings[0].message, r"(?i)distribution")
        self.assertRegex(findings[0].message, r"(?i)first archival episode|calibration")

    def test_the_finding_says_why_the_timeline_s_float_is_the_honest_number(self):
        """`shot_lengths.json` is per beat and rounded up to whole seconds, so judging a 6 s
        ceiling against it would fail shots the film never held on screen."""
        findings = qc_episode.check_archival_rhythm(
            timeline(("u001", "archive", "eva-boot", CEILING + 2.0)), CONTRACT)
        self.assertRegex(findings[0].message, r"(?i)shot_lengths|rounded|narration clock")


class BlendLuma(unittest.TestCase):
    """`blend` shots owe the episode a luma match; `keep_distinct` shots are exempt by design,
    because their whole job is to read as a different provenance."""

    def test_a_blend_shot_inside_the_episode_band_passes(self):
        shots = timeline(("u001", "3d", "sls", 5.0), ("u002", "archive", "press", 5.0))
        declared = {"sls": {"treatment": "keep_distinct"}, "press": {"treatment": "blend"}}
        self.assertEqual(qc_episode.check_blend_luma(
            shots, declared, {"u001": 100.0, "u002": 105.0}, CONTRACT), [])

    def test_a_blend_shot_outside_the_band_is_a_warning(self):
        shots = timeline(("u001", "3d", "sls", 5.0), ("u002", "archive", "press", 5.0))
        declared = {"sls": {"treatment": "keep_distinct"}, "press": {"treatment": "blend"}}
        findings = qc_episode.check_blend_luma(
            shots, declared, {"u001": 100.0, "u002": 80.0}, CONTRACT)
        self.assertEqual(codes(findings), ["blend_luma_off_band"])
        self.assertEqual(findings[0].severity, "warn")
        self.assertIn("press", findings[0].subject)

    def test_a_keep_distinct_shot_is_never_judged_against_the_band(self):
        shots = timeline(("u001", "3d", "sls", 5.0), ("u002", "archive", "boot", 5.0),
                         ("u003", "archive", "press", 5.0))
        declared = {"sls": {}, "boot": {"treatment": "keep_distinct"},
                    "press": {"treatment": "keep_distinct"}}
        self.assertEqual(qc_episode.check_blend_luma(
            shots, declared, {"u001": 100.0, "u002": 10.0, "u003": 250.0}, CONTRACT), [])

    def test_an_episode_with_no_blend_shot_produces_nothing(self):
        """Artemis II declares no archival layer at all, so the window must close without ever
        decoding a frame — a finding here could only ever be a warning, and a warning that
        reaches a non-archival episode is noise that gets the gate ignored."""
        shots = timeline(("u001", "3d", "sls", 5.0), ("u002", "manim", "orbit", 5.0))
        self.assertEqual(qc_episode.check_blend_luma(
            shots, {}, {"u001": 0.0, "u002": 255.0}, CONTRACT), [])

    def test_the_window_is_the_contract_s_fraction_of_the_episode_luma(self):
        contract = json.loads(json.dumps(CONTRACT))
        shots = timeline(("u001", "archive", "press", 5.0), ("u002", "3d", "sls", 5.0))
        declared = {"press": {"treatment": "blend"}, "sls": {"treatment": "blend"}}
        lumas = {"u001": 100.0, "u002": 88.0}          # mean 94, so the band is +-9.4
        self.assertEqual(qc_episode.check_blend_luma(shots, declared, lumas, contract), [])
        contract["archive"]["cohesion"]["blend_luma_window_fraction"] = LUMA_WINDOW / 4
        self.assertEqual(len(qc_episode.check_blend_luma(shots, declared, lumas, contract)), 2)

    def test_a_blend_shot_the_pixels_never_answered_for_is_reported(self):
        shots = timeline(("u001", "archive", "press", 5.0), ("u002", "3d", "sls", 5.0))
        declared = {"press": {"treatment": "blend"}, "sls": {"treatment": "keep_distinct"}}
        findings = qc_episode.check_blend_luma(shots, declared, {"u002": 90.0}, CONTRACT)
        self.assertEqual(codes(findings), ["blend_luma_unmeasured"])


class CutLoudness(unittest.TestCase):
    """The mix has to survive the cut into and out of a source. Only the boundaries that cross
    the layer are judged: a 3D-to-3D cut is already covered by the bed and target rules."""

    def test_a_cut_crossing_the_layer_is_a_boundary(self):
        shots = timeline(("u001", "3d", "sls", 5.0), ("u002", "archive", "boot", 4.0),
                         ("u003", "manim", "orbit", 6.0), ("u004", "archive", "press", 3.0))
        self.assertEqual([(l.id, r.id) for l, r in qc_episode.archival_boundaries(shots)],
                         [("u001", "u002"), ("u002", "u003"), ("u003", "u004")])

    def test_a_film_that_never_leaves_the_layer_has_no_boundaries(self):
        shots = timeline(("u001", "archive", "boot", 4.0), ("u002", "archive", "press", 3.0))
        self.assertEqual(qc_episode.archival_boundaries(shots), [])

    def test_a_cut_that_jumps_over_the_bound_is_a_warning(self):
        shots = timeline(("u001", "3d", "sls", 5.0), ("u002", "archive", "boot", 4.0))
        pairs = qc_episode.archival_boundaries(shots)
        findings = qc_episode.check_cut_loudness(pairs, {"u001->u002": CUT_MAX + 1.0}, CONTRACT)
        self.assertEqual(codes(findings), ["cut_loudness_jump"])
        self.assertEqual(findings[0].severity, "warn")
        self.assertIn("boot", findings[0].subject)

    def test_a_quiet_cut_passes_and_the_bound_is_the_contract_s(self):
        contract = json.loads(json.dumps(CONTRACT))
        shots = timeline(("u001", "3d", "sls", 5.0), ("u002", "archive", "boot", 4.0))
        pairs = qc_episode.archival_boundaries(shots)
        self.assertEqual(qc_episode.check_cut_loudness(pairs, {"u001->u002": CUT_MAX}, contract),
                         [])
        contract["archive"]["cohesion"]["loudness_delta_across_cuts_max_lu"] = CUT_MAX - 1.0
        self.assertTrue(qc_episode.check_cut_loudness(pairs, {"u001->u002": CUT_MAX}, contract))

    def test_the_louder_side_is_reported_whichever_way_the_cut_goes(self):
        """A source that arrives 4 LU hot is as wrong as one that arrives 4 LU low, and only one
        of the two is caught by a signed comparison."""
        for delta in (CUT_MAX + 0.5, -(CUT_MAX + 0.5)):
            shots = timeline(("u001", "3d", "sls", 5.0), ("u002", "archive", "boot", 4.0))
            findings = qc_episode.check_cut_loudness(qc_episode.archival_boundaries(shots),
                                                     {"u001->u002": delta}, CONTRACT)
            self.assertEqual(codes(findings), ["cut_loudness_jump"], f"{delta} passed")

    def test_an_unmeasurable_boundary_is_reported_not_skipped(self):
        shots = timeline(("u001", "3d", "sls", 5.0), ("u002", "archive", "boot", 4.0))
        findings = qc_episode.check_cut_loudness(qc_episode.archival_boundaries(shots), {},
                                                 CONTRACT)
        self.assertEqual(codes(findings), ["cut_loudness_unmeasured"])

    def test_a_film_with_no_archival_layer_measures_nothing(self):
        """No boundaries, so `run()` never reaches ffmpeg for this rule and Artemis II's counts
        cannot move."""
        shots = timeline(("u001", "3d", "sls", 5.0), ("u002", "manim", "orbit", 4.0))
        self.assertEqual(qc_episode.archival_boundaries(shots), [])


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not on PATH")
class GateWiring(unittest.TestCase):
    """The checks have to reach `run()`, or the layer stays unjudged exactly as it was before."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.master = Path(cls.tmp.name) / "master.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi", "-i", "color=c=0x203050:s=320x180:d=50:r=30",
            "-f", "lavfi", "-i", "sine=frequency=220:duration=50",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "24000", "-ac", "2", str(cls.master)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def episode(self, files=None, **kwargs):
        return episode_dir(Path(tempfile.mkdtemp(dir=self.tmp.name)), files, **kwargs)

    def test_a_3d_only_episode_is_told_its_archival_layer_is_missing(self):
        findings = qc_episode.run(episode=self.episode(archival=False, shots=[
            ("u001", "3d", "sls-launch", 25.0), ("u002", "3d", "earth", 25.0)]),
            master=self.master)
        self.assertEqual(codes(archival_findings(findings)), ["archive_layer_missing"])
        self.assertEqual(archival_findings(findings)[0].severity, "warn",
                         "the default rung reports the missing layer; it does not block on it")

    def test_a_broken_rights_row_blocks_the_build(self):
        broken = without(GOOD_RECORD, licence="arch-999")
        findings = archival_findings(qc_episode.run(
            episode=self.episode({RECORDS_NAME: {"apollo-boot": broken}}), master=self.master))
        self.assertEqual([(f.severity, f.code) for f in findings if f.severity == "error"],
                         [("error", "archive_records_invalid")])

    def test_a_shot_presented_as_archival_owes_a_record_in_the_full_gate(self):
        """The unit-level rule is worth nothing if `run()` does not hand it the timeline, so this
        goes through the whole gate: `shots` is the argument the check was widened to take, and
        this fixture is the stale-clip case — an archival shot on the timeline, no records file."""
        findings = qc_episode.run(episode=self.episode(archival=False), master=self.master)
        self.assertEqual([(f.code, f.subject) for f in archival_findings(findings)
                          if f.severity == "error"],
                         [("archive_shot_without_record", "apollo-boot")])

    def test_the_rendered_report_names_the_layer(self):
        findings = qc_episode.run(episode=self.episode(archival=False, shots=[
            ("u001", "3d", "sls-launch", 25.0)]), master=self.master)
        self.assertIn("archive_layer_missing", qc_episode.render(findings))


if __name__ == "__main__":
    unittest.main()
