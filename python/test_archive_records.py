# -*- coding: utf-8 -*-
"""The archival layer as data, validated before anything is encoded.

`workflow/style.json` archive section states rights rules that block a build ("metadata:
error"), and `workflow/capabilities.json` says the `assets` preflight stays optional until
#142 gives the archive kind something to feed. This file is that something: one record per
archival shot, one ledger row per archival asset, and the rules read out of the contract
rather than retyped here.

Why the ledger is its own file and not more columns in `assets/license-manifest.json`:
`sourcing.manifest.validate_asset` enforces an *exact* field set for stock assets it bought
from a vendor, and `manifest_report.purchase_list` loads that same file to decide whether an
upload is blocked. An archival quotation has a different shape — a rights *basis* rather than
a purchase status, a credit line, a retrieval provenance — and putting both in one file means
one of the two validators has to stop being exact. Two files keep both honest.
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from workflow.archive import key_side, ledger, paths, records  # noqa: E402
from workflow.config import style_contract  # noqa: E402

CONTRACT = style_contract(ROOT)
# The filenames come from the contract, so a renamed archival path moves the tests with it
# instead of failing them; archive.py reads the same values.
ARCHIVE_FILENAME = paths(CONTRACT)["records_filename"]
LEDGER_FILENAME = paths(CONTRACT)["ledger_filename"]
# The division of labour is read the same way: a renamed token moves the tests with the contract
# instead of failing them, and the validator under test reads these very dictionaries.
DIVISION = CONTRACT["archive"]["division_of_labour"]
CARRIES_FIELD = DIVISION["carries_field"]
ARCHIVE_TOKEN = next(iter(DIVISION["archive_carries"]))
ANIMATION_TOKEN = next(iter(DIVISION["animation_carries"]))

GOOD_RECORD = {
    "asset": "assets/archive/apollo_boot_1969.mp4",
    "licence": "arch-001",
    "form": "clip",
    "native_fps": 16.0,
    "motion_mode": "retime_to_natural",
    "aspect": "pillarbox_visible_edge",
    "treatment": "keep_distinct",
    "light_side": "left",
    "carries": ARCHIVE_TOKEN,
}

GOOD_LEDGER_ROW = {
    "id": "arch-001",
    "provider": "NASA",
    "license": "PD-US-NO-RESTRICTION",
    "url": "https://archive.org/details/nasa-apollo-boot",
    "file": "assets/archive/apollo_boot_1969.mp4",
    "source_archive": "NASA Image Library / Internet Archive mirror",
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


def without(base, **changes):
    """A fixture copy where a value of None deletes the key.

    `dict(base, **changes)` cannot express "this shot declares no aspect", and every test that
    proves a required field is actually required needs exactly that. Without the delete case the
    merge silently re-adds the key from the base fixture, and the test passes while asserting
    nothing — which is how a required-field gate ships without ever having been tested.
    """
    out = dict(base)
    for key, value in changes.items():
        if value is None:
            out.pop(key, None)
        else:
            out[key] = value
    return out


def episode(tmp, *, record=None, row=None, rows=None):
    """A minimal episode carrying one archival shot."""
    directory = Path(tmp)
    record = without(GOOD_RECORD, **(record or {}))
    rows = [without(GOOD_LEDGER_ROW, **(row or {}))] if rows is None else rows
    (directory / ARCHIVE_FILENAME).write_text(
        json.dumps({"apollo-boot": record}, indent=1), encoding="utf-8")
    (directory / LEDGER_FILENAME).parent.mkdir(parents=True, exist_ok=True)
    (directory / LEDGER_FILENAME).write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return directory


class TestPaths(unittest.TestCase):
    def test_the_contract_declares_where_the_archival_layer_lives(self):
        declared = paths(CONTRACT)
        for key in ("records_filename", "ledger_filename", "source_dir", "render_dir"):
            self.assertTrue(str(declared[key]).strip(), f"archive.paths.{key} is empty")

    def test_the_archival_ledger_is_not_the_stock_licence_manifest(self):
        """`sourcing.manifest.validate_asset` enforces an exact thirteen-field stock schema, so
        a rights row with the ten archival fields cannot be a row in that file. The two ledgers
        stay separate files, each with its own exact validator."""
        self.assertNotEqual(paths(CONTRACT)["ledger_filename"], "assets/license-manifest.json")

    def test_a_contract_without_paths_is_refused_not_guessed(self):
        contract = json.loads(json.dumps(CONTRACT))
        del contract["archive"]["paths"]
        with self.assertRaises(ValueError) as caught:
            paths(contract)
        self.assertIn("archive.paths", str(caught.exception))


class TestKeySide(unittest.TestCase):
    def test_key_side_comes_from_the_lighting_section(self):
        self.assertEqual(key_side(CONTRACT), CONTRACT["lighting"]["key_side"])

    def test_the_declared_side_is_the_side_the_beats_render(self):
        """`key_side` is a claim about artemis_beats.add_key's default, so check the default."""
        src = (ROOT / "tools" / "blender" / "artemis_beats.py").read_text(encoding="utf-8")
        self.assertIn("def add_key(cam, frame, *, name=\"sun\", energy=5.0, color=None, "
                      "angle=None,\n            side=1.0,", src,
                      "add_key moved its default side; lighting.key_side has to move with it")
        self.assertEqual(key_side(CONTRACT), "right")


class TestRecords(unittest.TestCase):
    def test_a_complete_record_loads(self):
        with tempfile_() as episode_dir:
            loaded = records(episode(episode_dir), CONTRACT)
        self.assertEqual(list(loaded), ["apollo-boot"])
        self.assertEqual(loaded["apollo-boot"]["motion_mode"], "retime_to_natural")

    def test_aspect_treatment_must_be_one_of_the_contract_enums(self):
        with tempfile_() as episode_dir:
            with self.assertRaises(ValueError) as caught:
                records(episode(episode_dir, record={"aspect": "crop_to_fill"}), CONTRACT)
        self.assertIn("crop_to_fill", str(caught.exception))
        self.assertIn("aspect", str(caught.exception))

    def test_an_undeclared_aspect_is_refused_not_defaulted(self):
        """`treatment_required` exists because an accidental edge crop of a 4:3 frame is the
        third state the contract rejects; a silent default would ship exactly that."""
        with tempfile_() as episode_dir:
            with self.assertRaises(ValueError) as caught:
                records(episode(episode_dir, record={"aspect": None}), CONTRACT)
        self.assertIn("aspect", str(caught.exception))

    def test_cohesion_treatment_is_required_too(self):
        with tempfile_() as episode_dir:
            with self.assertRaises(ValueError) as caught:
                records(episode(episode_dir, record={"treatment": None}), CONTRACT)
        self.assertIn("treatment", str(caught.exception))

    def test_motion_mode_is_required_only_when_the_rate_is_not_the_canvas_rate(self):
        canvas_fps = float(CONTRACT["canvas"]["fps"])
        with tempfile_() as episode_dir:
            with self.assertRaises(ValueError):
                records(episode(episode_dir, record={"motion_mode": None}), CONTRACT)
            # Same shot, already at the canvas rate: nothing to declare.
            loaded = records(episode(episode_dir, record={"motion_mode": None,
                                                           "native_fps": canvas_fps}),
                             CONTRACT)
        self.assertEqual(loaded["apollo-boot"]["native_fps"], canvas_fps)

    def test_light_side_is_a_left_right_choice_or_absent(self):
        with tempfile_() as episode_dir:
            with self.assertRaises(ValueError) as caught:
                records(episode(episode_dir, record={"light_side": "north"}), CONTRACT)
        self.assertIn("north", str(caught.exception))
        with tempfile_() as episode_dir:
            self.assertIn("apollo-boot",
                          records(episode(episode_dir, record={"light_side": None}), CONTRACT))

    def test_a_record_pointing_at_no_licence_row_is_refused(self):
        """The link between the shot and its rights row is the whole point of the ledger; an
        id nobody can resolve is a shot that ships with no documented rights."""
        with tempfile_() as episode_dir:
            with self.assertRaises(ValueError) as caught:
                records(episode(episode_dir, record={"licence": "arch-999"}), CONTRACT)
        self.assertIn("arch-999", str(caught.exception))

    def test_the_asset_path_and_the_ledger_file_must_be_the_same_file(self):
        with tempfile_() as episode_dir:
            with self.assertRaises(ValueError) as caught:
                records(episode(episode_dir, record={"asset": "assets/archive/other.mp4"}),
                        CONTRACT)
        self.assertIn("assets/archive/other.mp4", str(caught.exception))

    def test_a_still_needs_no_frame_rate(self):
        with tempfile_() as episode_dir:
            loaded = records(episode(episode_dir, record={"form": "still", "native_fps": None,
                                                           "motion_mode": None}), CONTRACT)
        self.assertEqual(loaded["apollo-boot"]["form"], "still")

    def test_a_still_that_declares_a_frame_rate_is_refused(self):
        """The rate is a reinterpretation instruction, and a still has nothing to reinterpret;
        accepting it here is how a still ends up as a one-frame clip played at an odd cadence."""
        with tempfile_() as episode_dir:
            with self.assertRaises(ValueError) as caught:
                records(episode(episode_dir, record={"form": "still", "motion_mode": None}),
                        CONTRACT)
        self.assertIn("native_fps", str(caught.exception))

    def test_an_unbuilt_shot_map_is_not_a_record_file(self):
        with tempfile_() as episode_dir:
            with self.assertRaises(ValueError) as caught:
                records(episode_dir, CONTRACT)
        self.assertIn(ARCHIVE_FILENAME, str(caught.exception))


class TestDivisionOfLabour(unittest.TestCase):
    """Which of the two styles carries a shot is a declared fact, not a habit.

    The contract's own `forbidden` sentence - an archival clip used merely to avoid shooting or
    building the equivalent shot - was uncheckable prose while the categories lived in nobody's
    reach: no production file read `division_of_labour` at all. A record now names the category it
    serves, so the judgement is legible in the episode directory, and naming an animation-side
    category is that forbidden case arriving as data the validator can refuse.
    """

    def test_a_record_that_names_what_the_archive_carries_is_accepted(self):
        with tempfile_() as episode_dir:
            loaded = records(episode(episode_dir), CONTRACT)
        self.assertEqual(loaded["apollo-boot"][CARRIES_FIELD], ARCHIVE_TOKEN)

    def test_a_record_that_declares_no_category_is_refused_not_defaulted(self):
        """A default here would be the same silent answer the aspect rule refuses: the shot ships
        with a category nobody chose, and the forbidden case becomes unfindable."""
        with tempfile_() as episode_dir:
            with self.assertRaises(ValueError) as caught:
                records(episode(episode_dir, record={CARRIES_FIELD: ""}), CONTRACT)
        self.assertIn(CARRIES_FIELD, str(caught.exception))

    def test_a_token_from_neither_list_is_refused_and_the_choices_are_named(self):
        with tempfile_() as episode_dir:
            with self.assertRaises(ValueError) as caught:
                records(episode(episode_dir, record={CARRIES_FIELD: "b_roll"}), CONTRACT)
        message = str(caught.exception)
        self.assertIn("b_roll", message)
        self.assertIn(ARCHIVE_TOKEN, message, "a refusal that does not say what the choices were "
                                              "sends the next editor guessing")

    def test_an_animation_side_category_is_the_forbidden_case(self):
        """The refusal quotes the contract's sentence rather than inventing a reason of its own."""
        with tempfile_() as episode_dir:
            with self.assertRaises(ValueError) as caught:
                records(episode(episode_dir, record={CARRIES_FIELD: ANIMATION_TOKEN}), CONTRACT)
        message = str(caught.exception)
        self.assertIn(ANIMATION_TOKEN, message)
        self.assertIn(DIVISION["forbidden"][:48], message)

    def test_the_two_lists_share_no_token_so_the_answer_is_decidable(self):
        """A token in both lists would make the forbidden case unrefusable by construction."""
        self.assertEqual(set(DIVISION["archive_carries"]) & set(DIVISION["animation_carries"]),
                         set())
        self.assertTrue(DIVISION["archive_carries"])
        self.assertTrue(DIVISION["animation_carries"])

    def test_the_categories_come_from_the_contract_not_from_the_validator(self):
        """A category added to the contract has to work with no code edit - that is the whole
        reason the layer is data. Pinning one token here would let the validator carry a copy."""
        import copy

        clone = copy.deepcopy(CONTRACT)
        clone["archive"]["division_of_labour"]["archive_carries"]["witness_account"] = (
            "a witness's own account of the event")
        with tempfile_() as episode_dir:
            loaded = records(episode(episode_dir, record={CARRIES_FIELD: "witness_account"}),
                             clone)
        self.assertEqual(loaded["apollo-boot"][CARRIES_FIELD], "witness_account")


class TestRightsLedger(unittest.TestCase):
    def test_a_complete_row_loads(self):
        with tempfile_() as episode_dir:
            rows = ledger(episode(episode_dir), CONTRACT)
        self.assertEqual(rows["arch-001"]["rights_basis"], "us_federal_public_domain")

    def test_every_field_the_contract_lists_is_required(self):
        for missing in CONTRACT["archive"]["rights"]["required_fields"]:
            with tempfile_() as episode_dir:
                with self.assertRaises(ValueError) as caught:
                    ledger(episode(episode_dir, row={missing: None}), CONTRACT)
            self.assertIn(missing, str(caught.exception), f"{missing} went unreported")

    def test_an_empty_string_does_not_satisfy_a_required_field(self):
        """A rights row that carries the key and nothing else is the common way a spreadsheet
        export ships, and it is exactly as undocumented as a missing column."""
        for blank in CONTRACT["archive"]["rights"]["required_fields"]:
            with tempfile_() as episode_dir:
                with self.assertRaises(ValueError) as caught:
                    ledger(episode(episode_dir, row={blank: "  "}), CONTRACT)
            self.assertIn(blank, str(caught.exception), f"{blank} accepted while blank")

    def test_a_rights_basis_outside_the_enum_is_refused(self):
        with tempfile_() as episode_dir:
            with self.assertRaises(ValueError) as caught:
                ledger(episode(episode_dir, row={"rights_basis": "probably_fine"}), CONTRACT)
        self.assertIn("probably_fine", str(caught.exception))

    def test_a_retrieved_date_that_is_not_a_date_is_refused(self):
        with tempfile_() as episode_dir:
            with self.assertRaises(ValueError) as caught:
                ledger(episode(episode_dir, row={"retrieved_date": "last tuesday"}), CONTRACT)
        self.assertIn("retrieved_date", str(caught.exception))

    def test_a_fair_use_quotation_without_a_credit_line_is_refused(self):
        """The credit line is both the on-screen source card text and the evidence that the
        quotation is subordinate to our own narration; an empty one fails both."""
        with tempfile_() as episode_dir:
            with self.assertRaises(ValueError) as caught:
                ledger(episode(episode_dir, row={
                    "rights_basis": "fair_use_quotation", "credit_line": "  "}), CONTRACT)
        self.assertIn("credit_line", str(caught.exception))

    def test_a_url_that_is_not_http_s_is_refused(self):
        for url in ("ftp://example/x", "example/x", "file:///C:/x.mp4"):
            with tempfile_() as episode_dir:
                with self.assertRaises(ValueError, msg=url) as caught:
                    ledger(episode(episode_dir, row={"url": url}), CONTRACT)
            self.assertIn("url", str(caught.exception))

    def test_a_credential_in_a_url_is_refused(self):
        with tempfile_() as episode_dir:
            with self.assertRaises(ValueError) as caught:
                ledger(episode(episode_dir, row={
                    "url": "https://archive.org/details/x?token=abc"}), CONTRACT)
        self.assertIn("token", str(caught.exception))

    def test_duplicate_ids_are_refused(self):
        with tempfile_() as episode_dir:
            rows = [GOOD_LEDGER_ROW, GOOD_LEDGER_ROW]
            with self.assertRaises(ValueError) as caught:
                ledger(episode(episode_dir, rows=rows), CONTRACT)
        self.assertIn("arch-001", str(caught.exception))

    def test_an_episode_without_an_archival_layer_has_no_rows(self):
        """Artemis II ships as rendered: no archive.json, no ledger file, and the gate must not
        call that a breach."""
        with tempfile_() as episode_dir:
            self.assertEqual(ledger(episode_dir, CONTRACT), {})
            self.assertEqual(records(episode_dir, CONTRACT, required=False), {})

    def test_the_credential_names_are_the_contract_s_list_not_the_module_s(self):
        """The words that name a credential live in style.json as data. That keeps the
        validator free of credential-shaped literals of its own, and it means swapping the list
        swaps what is refused."""
        contract = json.loads(json.dumps(CONTRACT))
        contract["archive"]["rights"]["credential_query_names"] = ["embargo"]
        with tempfile_() as episode_dir:
            # The default list no longer applies once the contract names something else.
            ledger(episode(episode_dir, row={"url": "https://archive.org/x?token=abc"}),
                   contract)
            with self.assertRaises(ValueError) as caught:
                ledger(episode(episode_dir, row={"url": "https://archive.org/x?embargo=1"}),
                       contract)
        self.assertIn("embargo", str(caught.exception))

    def test_hyphen_and_underscore_forms_of_one_name_are_both_refused(self):
        with tempfile_() as episode_dir:
            for parameter in ("access_token", "access-token", "accesstoken"):
                with self.assertRaises(ValueError, msg=parameter):
                    ledger(episode(episode_dir,
                                   row={"url": f"https://archive.org/x?{parameter}=abc"}),
                           CONTRACT)

    def test_no_credential_shaped_assignment_in_the_module(self):
        source = (ROOT / "workflow" / "archive.py").read_text(encoding="utf-8")
        assigned = re.findall(
            r'\b\w*(?:key|token|secret|password|credential)\w*\s*=\s*["\'][^"\']+["\']',
            source, re.I)
        self.assertFalse(assigned, f"{assigned} looks like a credential literal embedded in "
                                   "workflow/archive.py; the names belong in style.json")


class TestProvenanceTypes(unittest.TestCase):
    """The structured half of a rights row is typed by the contract, not by guesswork.

    Ten string columns describe a purchase. Eleven more fields — timecodes, a timebase, a
    frame rate, an obligations list, two booleans — describe what may actually be done with the
    file, and each one can be wrong in a way a blank string cannot: an empty obligations list
    reads as "no obligations" to a human and as "column missing" to a spreadsheet, and a
    `qc_watermark` of `False` is a real answer that a `.strip()` check deletes.
    """

    def test_the_contract_gives_every_required_field_a_declared_type(self):
        rights = CONTRACT["archive"]["rights"]
        declared = set(rights["field_types"])
        required = set(rights["required_fields"])
        self.assertEqual(declared, required,
                         f"{sorted(required ^ declared)} disagree between required_fields and "
                         "field_types; a field with no type is validated by whoever remembers it")

    def test_a_required_field_that_the_type_table_lost_is_refused_not_assumed_text(self):
        """A renamed field is the common accident, and defaulting it to text accepts `[]` as a
        value while rejecting `False` — silently inverting two of the rules that protect the
        watermarked-copy and obligations questions."""
        contract = json.loads(json.dumps(CONTRACT))
        del contract["archive"]["rights"]["field_types"]["obligations"]
        with tempfile_() as episode_dir:
            with self.assertRaises(ValueError) as caught:
                ledger(episode(episode_dir), contract)
        self.assertIn("obligations", str(caught.exception))

    def test_a_boolean_that_is_blank_is_refused_while_false_is_accepted(self):
        """`False` is the answer that makes a watermarked master impossible to ship by accident,
        so it has to be storable; only an absent or non-boolean value is a missing declaration."""
        with tempfile_() as episode_dir:
            ledger(episode(episode_dir, row={"qc_watermark": False}), CONTRACT)
        for bad in ("", "  ", "false", 0, None):
            with tempfile_() as episode_dir:
                with self.assertRaises(ValueError, msg=repr(bad)) as caught:
                    ledger(episode(episode_dir, row={"qc_watermark": bad}), CONTRACT)
            self.assertIn("qc_watermark", str(caught.exception))

    def test_a_number_declared_as_a_string_is_refused(self):
        """`"24"` would pass a `str()` presence check and then be compared as text, so the
        timebase that gates every frame number would gate nothing."""
        for field in ("timebase", "source_frame_rate", "source_year"):
            with tempfile_() as episode_dir:
                with self.assertRaises(ValueError, msg=field) as caught:
                    ledger(episode(episode_dir, row={field: "24"}), CONTRACT)
            self.assertIn(field, str(caught.exception))

    def test_an_obligations_list_may_be_empty_when_no_basis_imposes_one(self):
        """Empty is a declaration here, not a gap: US federal footage carries no attribution
        duty, and a row that has to say `["none"]` to satisfy a validator teaches the reader
        that the column is decoration."""
        with tempfile_() as episode_dir:
            rows = ledger(episode(episode_dir, row={"obligations": []}), CONTRACT)
        self.assertEqual(rows["arch-001"]["obligations"], [])


class TestThirdPartyRights(unittest.TestCase):
    """The question NASA clearance never answers: is anybody else in this frame."""

    def test_an_explicit_none_is_accepted_as_the_answer_it_is(self):
        with tempfile_() as episode_dir:
            rows = ledger(episode(episode_dir, row={"third_party_rights": "none"}), CONTRACT)
        self.assertEqual(rows["arch-001"]["third_party_rights"], "none")

    def test_a_list_of_named_third_party_rights_is_accepted(self):
        with tempfile_() as episode_dir:
            rows = ledger(episode(episode_dir,
                                  row={"third_party_rights": ["music cue, Universal Music "
                                                              "Publishing", "a contractor's "
                                                              "trademark on the hardware"]}),
                          CONTRACT)
        self.assertEqual(len(rows["arch-001"]["third_party_rights"]), 2)

    def test_an_unresolved_third_party_answer_is_a_stop_not_a_warning(self):
        """The research is unambiguous: a federal clip is public domain *as to the agency's
        rights only*, and music, faces and trademarks inside it are separately encumbered. A row
        that says `unknown` and reaches a warning is a row that ships."""
        for placeholder in ("unknown", "tbd", "TBD", "to be determined", "", "  ", "check later"):
            with tempfile_() as episode_dir:
                with self.assertRaises(ValueError, msg=repr(placeholder)) as caught:
                    ledger(episode(episode_dir, row={"third_party_rights": placeholder}),
                           CONTRACT)
            self.assertIn("third_party_rights", str(caught.exception))

    def test_an_empty_list_does_not_count_as_an_explicit_none(self):
        """`[]` says "there are no third parties", which is the same claim as `none` reached by a
        different route, and a list you can leave empty is a list nobody fills."""
        with tempfile_() as episode_dir:
            with self.assertRaises(ValueError) as caught:
                ledger(episode(episode_dir, row={"third_party_rights": []}), CONTRACT)
        self.assertIn("third_party_rights", str(caught.exception))

    def test_a_blank_entry_inside_the_list_is_refused(self):
        with tempfile_() as episode_dir:
            with self.assertRaises(ValueError) as caught:
                ledger(episode(episode_dir,
                               row={"third_party_rights": ["music cue", "  "]}), CONTRACT)
        self.assertIn("third_party_rights", str(caught.exception))


class TestUnresolvedPlaceholders(unittest.TestCase):
    def test_a_placeholder_in_free_text_is_refused_as_unresolved(self):
        rights = CONTRACT["archive"]["rights"]
        for field in rights["placeholder_checked_fields"]:
            for value in rights["unresolved_placeholders"]:
                with tempfile_() as episode_dir:
                    with self.assertRaises(ValueError, msg=f"{field}={value!r}") as caught:
                        ledger(episode(episode_dir, row={field: value}), CONTRACT)
                self.assertIn(field, str(caught.exception),
                              f"{field} accepted {value!r} without naming the field")

    def test_the_placeholder_list_is_contract_data_not_a_literal_in_the_validator(self):
        contract = json.loads(json.dumps(CONTRACT))
        contract["archive"]["rights"]["unresolved_placeholders"] = ["provisional"]
        with tempfile_() as episode_dir:
            ledger(episode(episode_dir, row={"purpose_of_use": "unknown"}), contract)
            with self.assertRaises(ValueError) as caught:
                ledger(episode(episode_dir, row={"purpose_of_use": "provisional"}), contract)
        self.assertIn("purpose_of_use", str(caught.exception))

    def test_the_purpose_of_use_is_the_field_a_quotation_argue_is_fought_over(self):
        """Fair use asks whether the quotation is subordinate to a larger purpose, and the row's
        answer to that is a sentence, not a checkbox — so a filler sentence fails like a blank."""
        with tempfile_() as episode_dir:
            with self.assertRaises(ValueError) as caught:
                ledger(episode(episode_dir,
                               row={"purpose_of_use": "reference"}), CONTRACT)
        self.assertIn("purpose_of_use", str(caught.exception))


class TestTimecodeArithmetic(unittest.TestCase):
    """In and out points as they are written on the record, converted at the rate they were cut.

    Drop-frame exists because 29.97 fps does not divide an hour: the timecode skips two frame
    numbers a minute so the label keeps telling clock time. The consequence is that the same
    written string means two different real durations, and a quotation ceiling applied to the
    label instead of the seconds is a ceiling that is wrong by a frame a minute.
    """

    def _row(self, **changes):
        base = dict(third_party_rights="none", timebase=30, source_frame_rate=29.97,
                    in_timecode="00:00:00:00", out_timecode="00:01:00:00",
                    rights_basis="us_federal_public_domain")
        return {**base, **changes}

    def test_a_non_drop_frame_span_is_the_frame_count_over_the_source_rate(self):
        with tempfile_() as episode_dir:
            rows = ledger(episode(episode_dir, row=self._row()), CONTRACT)
        self.assertAlmostEqual(rows["arch-001"]["span_seconds"], 1800 / 29.97, places=4)

    def test_the_drop_frame_form_of_the_same_label_is_shorter(self):
        """1800 counted frames at 29.97 is 60.06 s; `00:01:00;00` names the 1798th frame, because
        two numbers were skipped, and that is 59.99 s. Neither is "one minute" and both are on
        real records, which is why timebase and source_frame_rate are separate declarations."""
        with tempfile_() as episode_dir:
            rows = ledger(episode(episode_dir, row=self._row(
                out_timecode="00:01:00;00")), CONTRACT)
        self.assertAlmostEqual(rows["arch-001"]["span_seconds"], 1798 / 29.97, places=4)
        self.assertLess(rows["arch-001"]["span_seconds"], 60.0)

    def test_a_span_crossing_a_minute_subtracts_every_tenth_minute_once(self):
        with tempfile_() as episode_dir:
            rows = ledger(episode(episode_dir, row=self._row(
                in_timecode="00:00:59;00", out_timecode="00:01:10;00")), CONTRACT)
        # 330 labels apart, 328 recorded frames: the minute-1 drop falls inside the span, and a
        # ceiling applied to the labels would grant two frames nobody recorded.
        self.assertAlmostEqual(rows["arch-001"]["span_seconds"], 328 / 29.97, places=4)

    def test_the_span_crossing_the_tenth_minute_subtracts_eighteen_drops_not_twenty(self):
        """Every tenth minute is exempt, which is the whole reason the label tracks the clock.
        A minute-1 span cannot tell that formula from one that drops there too, so this is the
        fixture that does: 330 recorded frames across the tenth, and 328 for a formula that
        charges it. Short by two frames is a quotation ceiling quietly granted two frames less
        than the footage holds."""
        with tempfile_() as episode_dir:
            rows = ledger(episode(episode_dir, row=self._row(
                in_timecode="00:09:59;00", out_timecode="00:10:10;00")), CONTRACT)
        self.assertAlmostEqual(rows["arch-001"]["span_seconds"], 330 / 29.97, places=4)

    def test_a_malformed_timecode_is_refused_and_names_its_field(self):
        for bad in ("0:01:00:00", "00:1:00:00", "00:01:00", "00:01:00:9", "00:61:00:00",
                    "00:01:00.00", "one minute in"):
            with tempfile_() as episode_dir:
                with self.assertRaises(ValueError, msg=bad) as caught:
                    ledger(episode(episode_dir, row=self._row(out_timecode=bad)), CONTRACT)
            self.assertIn("out_timecode", str(caught.exception))

    def test_a_frame_number_at_or_above_the_timebase_is_refused(self):
        """`00:00:00:30` at timebase 30 is not a frame, it is a minute written wrongly, and
        accepting it makes every span computed from the row too short by one frame."""
        for bad in ("00:00:00:30", "00:00:00:31"):
            with tempfile_() as episode_dir:
                with self.assertRaises(ValueError) as caught:
                    ledger(episode(episode_dir, row=self._row(
                        in_timecode=bad, out_timecode="00:00:05:00")), CONTRACT)
            self.assertIn("in_timecode", str(caught.exception))

    def test_drop_frame_notation_at_an_integral_rate_is_refused(self):
        """Nothing drops. The notation is only defined for the 1.001 ratios, and a `;` on 24 fps
        material both misparses the span and says the operator did not know which was which."""
        with tempfile_() as episode_dir:
            with self.assertRaises(ValueError) as caught:
                ledger(episode(episode_dir, row=self._row(
                    timebase=24, source_frame_rate=24.0, in_timecode="00:00:00;00",
                    out_timecode="00:00:05;00")), CONTRACT)
        self.assertIn("drop-frame", str(caught.exception).casefold())
        self.assertIn("in_timecode", str(caught.exception))

    def test_the_timebase_may_not_exceed_the_source_rate_rounded_up(self):
        """A 24 fps clip labelled at timebase 30 counts frames that were never recorded; every
        span it reports is 25 % too long and every in-point is a different frame."""
        with tempfile_() as episode_dir:
            with self.assertRaises(ValueError) as caught:
                ledger(episode(episode_dir, row=self._row(
                    timebase=30, source_frame_rate=24.0)), CONTRACT)
        self.assertIn("timebase", str(caught.exception))

    def test_an_out_point_not_after_the_in_point_is_refused(self):
        for out, in_ in (("00:00:00:00", "00:01:00:00"), ("00:00:05:00", "00:00:05:00")):
            with tempfile_() as episode_dir:
                with self.assertRaises(ValueError) as caught:
                    ledger(episode(episode_dir, row=self._row(
                        in_timecode=in_, out_timecode=out)), CONTRACT)
            self.assertIn("out_timecode", str(caught.exception))


class TestQuotationCeiling(unittest.TestCase):
    def test_a_quotation_longer_than_the_contract_ceiling_is_refused(self):
        ceiling = float(CONTRACT["archive"]["rights"]["fair_use_quotation_max_seconds"])
        with tempfile_() as episode_dir:
            with self.assertRaises(ValueError) as caught:
                ledger(episode(episode_dir,
                               row={"rights_basis": "fair_use_quotation",
                                    "timebase": 25, "source_frame_rate": 25.0,
                                    "in_timecode": "00:00:00:00",
                                    "out_timecode": f"00:00:{int(ceiling) + 1:02d}:00"}),
                       CONTRACT)
        message = str(caught.exception)
        self.assertIn("fair_use_quotation", message)
        self.assertIn("credit_line", message,
                      "the refusal should say what a longer quotation would have to carry")

    def test_a_quotation_at_the_ceiling_loads(self):
        ceiling = float(CONTRACT["archive"]["rights"]["fair_use_quotation_max_seconds"])
        seconds = int(ceiling)
        frames = round((ceiling - seconds) * 25)
        with tempfile_() as episode_dir:
            rows = ledger(episode(episode_dir,
                                  row={"rights_basis": "fair_use_quotation",
                                       "timebase": 25, "source_frame_rate": 25.0,
                                       "in_timecode": "00:00:00:00",
                                       "out_timecode": f"00:00:{seconds:02d}:{frames:02d}"}),
                          CONTRACT)
        self.assertAlmostEqual(rows["arch-001"]["span_seconds"], ceiling, places=4)

    def test_the_ceiling_applies_to_quotations_only(self):
        """Twelve seconds of public-domain footage is not a legal question; twelve seconds of a
        licensed cue, or forty seconds of a quotation, is. Applying one ceiling everywhere turns
        the exception into the rule and hides the case it was written for."""
        with tempfile_() as episode_dir:
            ledger(episode(episode_dir,
                           row={"timebase": 25, "source_frame_rate": 25.0,
                                "in_timecode": "00:00:00:00",
                                "out_timecode": "00:01:00:00"}), CONTRACT)


class TestObligationsAndYear(unittest.TestCase):
    def test_a_basis_that_imposes_obligations_refuses_an_empty_list(self):
        bases = CONTRACT["archive"]["rights"]["obligations_required_for_bases"]
        self.assertTrue(bases, "no basis requires obligations, so the column is decoration")
        for basis in bases:
            with tempfile_() as episode_dir:
                with self.assertRaises(ValueError) as caught:
                    ledger(episode(episode_dir, row={"rights_basis": basis,
                                                      "obligations": []}), CONTRACT)
            self.assertIn("obligations", str(caught.exception), f"{basis} accepted none")

    def test_a_basis_that_imposes_obligations_loads_when_they_are_written_down(self):
        for basis in CONTRACT["archive"]["rights"]["obligations_required_for_bases"]:
            with tempfile_() as episode_dir:
                rows = ledger(episode(episode_dir, row={"rights_basis": basis}), CONTRACT)
            self.assertTrue(rows["arch-001"]["obligations"])

    def test_expired_copyright_needs_a_year_the_ninety_five_year_term_reaches(self):
        rights = CONTRACT["archive"]["rights"]
        floor = int(rights["publication_year_floor"])
        bases = rights["publication_year_floor_for_bases"]
        self.assertIn("pd_expired", bases, "nothing gates the expired-copyright claim")
        with tempfile_() as episode_dir:
            with self.assertRaises(ValueError) as caught:
                ledger(episode(episode_dir, row={"rights_basis": "pd_expired",
                                                  "source_year": floor + 1}), CONTRACT)
        self.assertIn("source_year", str(caught.exception))
        self.assertIn(str(floor), str(caught.exception))

    def test_a_year_inside_the_floor_loads_and_a_non_gated_basis_is_not_judged_by_it(self):
        floor = int(CONTRACT["archive"]["rights"]["publication_year_floor"])
        with tempfile_() as episode_dir:
            rows = ledger(episode(episode_dir, row={"rights_basis": "pd_expired",
                                                     "source_year": floor}), CONTRACT)
        self.assertEqual(rows["arch-001"]["source_year"], floor)
        with tempfile_() as episode_dir:
            ledger(episode(episode_dir, row={"rights_basis": "us_federal_public_domain",
                                              "source_year": floor + 40}), CONTRACT)

    def test_a_source_year_from_the_future_is_refused(self):
        from datetime import date
        with tempfile_() as episode_dir:
            with self.assertRaises(ValueError) as caught:
                ledger(episode(episode_dir, row={"source_year": date.today().year + 1}),
                       CONTRACT)
        self.assertIn("source_year", str(caught.exception))

    def test_the_floor_is_labelled_as_unconfirmed_law(self):
        """The research derived 1930 from the 95-year term and flagged it as needing a Copyright
        Office confirmation. A number that decides a ship has to say how much it is worth."""
        rights = CONTRACT["archive"]["rights"]
        basis = rights["publication_year_floor_basis"]
        self.assertRegex(basis, r"(?i)house style")
        self.assertRegex(basis, r"(?i)confirm|unconfirmed|pending")


class TestDerivativeDeclarations(unittest.TestCase):
    def test_a_transformed_asset_that_declares_no_transformations_is_refused(self):
        with tempfile_() as episode_dir:
            with self.assertRaises(ValueError) as caught:
                ledger(episode(episode_dir, row={"uploaded_as_is": False,
                                                 "derivative_transformations": []}), CONTRACT)
        self.assertIn("derivative_transformations", str(caught.exception))

    def test_an_asset_uploaded_as_is_that_declares_transformations_is_a_contradiction(self):
        """One of the two claims is false, and the pair is the only statement in the row about
        whether the file a viewer sees is the file the archive holds."""
        with tempfile_() as episode_dir:
            with self.assertRaises(ValueError) as caught:
                ledger(episode(episode_dir,
                               row={"uploaded_as_is": True,
                                    "derivative_transformations": ["pillarbox"]}), CONTRACT)
        self.assertIn("uploaded_as_is", str(caught.exception))

    def test_an_asset_uploaded_as_is_loads_with_no_transformations_declared(self):
        with tempfile_() as episode_dir:
            rows = ledger(episode(episode_dir, row={"uploaded_as_is": True,
                                                     "derivative_transformations": []}),
                          CONTRACT)
        self.assertTrue(rows["arch-001"]["uploaded_as_is"])


def tempfile_():
    import contextlib
    import tempfile

    @contextlib.contextmanager
    def make():
        with tempfile.TemporaryDirectory() as directory:
            yield Path(directory)
    return make()


if __name__ == "__main__":
    unittest.main()
