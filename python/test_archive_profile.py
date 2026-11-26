# -*- coding: utf-8 -*-
"""The archival layer as the pipeline's default look, stated once and read everywhere.

`workflow/archive.py` already validates one shot and one rights row, but nothing in the repo
said that an *episode* owes the film an archival layer. That absence is why the layer has sat
beside the pipeline since #142 without ever reaching a master: `tools/assemble_episode.py` has
no archive reference, `tools/qc_episode.py` has none, and `workflow/init_episode.py` seeds
nothing that would make a new episode notice. A style that is only consulted when a call site
happens to ask for it is not a default — it is an option with extra steps.

The shape here comes from the research wave (2026-11-13), and each of its four rules is what one
of these classes tests:

  * a default has to be a **required** key, so the failure mode of losing it is a build error
    rather than a silently 3D-only episode;
  * rollout is a **ladder** (`off` → `warn` → `closed`) and the `warn` rung reports exactly the
    refusals `closed` would make, so a rule can be enforced against real distributions before
    it can stop a build — the same reason `enforcement_policy` puts pixel rules on the warn side;
  * opting out is a **record** with a closed reason enum, an owner and an expiry, and it
    downgrades the gate instead of silencing it, because an opt-out that mutes the finding is
    how a house style dies one convenience at a time;
  * every numeric bound is **house style**, not a published standard — no archive-documentation
    body publishes a source-concentration cap or a quotation ceiling, so a number that reads
    like a rule is a claim about this repo's taste and has to say so.
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from workflow.archive import mix_findings, profile, require_mix, resolve_mode  # noqa: E402
from workflow.config import style_contract  # noqa: E402

CONTRACT = style_contract(ROOT)
# The shipped contract has no archive floor (owner decision 2026-11-17: archive is evidence, not a
# quota). The floor machinery stays, so it is exercised against a contract that declares one.
FLOORED = json.loads(json.dumps(CONTRACT))
FLOORED["archive"]["episode_profile"]["mix"]["min_share"]["archive"] = 0.20
FLOORED["archive"]["episode_profile"]["mix"]["min_per_act"]["archive"] = 1


def stripped(*keys):
    """The shipped contract with one or more nested keys deleted.

    Every "this is required" test needs the delete case, and `dict(..., key=None)` cannot
    express it — passing None re-adds the key from the base. A required-field test that only
    ever blanks a value proves the validator catches empty strings, not missing data.
    """
    contract = json.loads(json.dumps(CONTRACT))
    node = contract
    for key in keys[:-1]:
        node = node[key]
    del node[keys[-1]]
    return contract


class TestProfileIsRequired(unittest.TestCase):
    def test_the_shipped_contract_carries_a_profile(self):
        declared = profile(CONTRACT)
        self.assertEqual(declared["mode"], "warn",
                         "the archival layer is a default now, so a contract still reading "
                         "`off` means the rollout never started")

    def test_an_archive_block_with_no_profile_is_refused_not_treated_as_off(self):
        """The whole point of making the profile required.

        If a missing block meant `off`, deleting `episode_profile` from style.json would keep
        every call site working and produce a 3D-only episode — the divergence between the
        stated style and the shipped one that this file exists to prevent.
        """
        with self.assertRaises(ValueError) as caught:
            profile(stripped("archive", "episode_profile"))
        self.assertIn("episode_profile", str(caught.exception))


class TestModeLadder(unittest.TestCase):
    def test_the_ladder_is_the_three_rollout_modes_in_order(self):
        ladder = profile(CONTRACT)["modes"]
        self.assertEqual(list(ladder), ["off", "warn", "closed"],
                         "the ladder order is what makes narrowing and widening decidable")
        self.assertIn(profile(CONTRACT)["mode"], ladder)

    def test_no_rung_of_the_ladder_is_left_undefined(self):
        """`warn` has to mean "report what closed would refuse", not "log something vague".

        A rung with no stated meaning is the rung the next person picks when a build annoys
        them, and the difference between `warn` and `off` is the only thing that keeps the
        rollout honest.
        """
        declared = profile(CONTRACT)
        for mode in declared["modes"]:
            self.assertIn(mode, declared["mode_meaning"], f"{mode} has no declared meaning")
            self.assertGreater(len(declared["mode_meaning"][mode].strip()), 40,
                               f"{mode} is defined by a placeholder")
        self.assertIn("closed", declared["mode_meaning"]["warn"],
                      "warn must name the refusals it reports, or it is just a log line")

    def test_a_mode_outside_the_ladder_is_refused(self):
        contract = json.loads(json.dumps(CONTRACT))
        contract["archive"]["episode_profile"]["mode"] = "warn_but_please"
        with self.assertRaises(ValueError) as caught:
            profile(contract)
        self.assertIn("warn_but_please", str(caught.exception))


class TestVisualMix(unittest.TestCase):
    def test_the_mix_names_every_layer_the_pipeline_can_render(self):
        layers = profile(CONTRACT)["mix"]["layers"]
        self.assertEqual(sorted(layers), ["3d", "archive", "black", "cards", "graphic", "manim"],
                         "the taxonomy is contract data now: the render queue and the canvas "
                         "test read it instead of each carrying its own tuple")

    def test_the_default_mix_sets_no_archive_quota(self):
        """A share floor is what filled the ask-chatgpt cut with generic clips; the shipped
        profile asks for none, and a film with no archive at all draws no finding from it."""
        mix = profile(CONTRACT)["mix"]
        self.assertEqual(float(mix["min_share"]["archive"]), 0.0)
        self.assertEqual(int(mix["min_per_act"]["archive"]), 0)
        self.assertEqual(mix_findings(shots(**{"3d": [(0.0, 540.0)]}), CONTRACT), [])

    def test_the_share_is_measured_in_screen_seconds_not_shot_counts(self):
        """Counts let a film be carried by three one-second inserts over ninety 20-second beats.

        The measured basis is data because the QC side has to be able to say which number it
        compared, and an assertion on the string is the only way a change of basis shows up
        here instead of quietly changing what passes.
        """
        self.assertIn("second", profile(CONTRACT)["mix"]["measured_on"])

    def test_every_layer_in_the_mix_has_a_share_bound(self):
        mix = profile(CONTRACT)["mix"]
        for layer in mix["layers"]:
            self.assertIn(layer, mix["min_share"], f"{layer} is in the taxonomy but unbudgeted")
            self.assertIn(layer, mix["min_per_act"],
                          f"{layer} has a share but no per-act obligation")

    def test_an_act_is_a_span_of_screen_time_stated_in_the_contract(self):
        """Per-act obligations need an act, and the only act definition this repo has is length.

        Refusing a band that cannot partition a film (a minimum of zero seconds would put every
        shot in the same act) is the point: `min_per_act` is only a rule if `act_seconds` says
        where the boundaries are.
        """
        low, high = profile(CONTRACT)["mix"]["act_seconds"]
        self.assertLess(0 < low <= high, float("inf"))
        self.assertGreaterEqual(low, 30.0, "an act shorter than a shot length partitions nothing")

    def test_an_unknown_layer_in_the_mix_is_refused(self):
        mix_data = json.loads(json.dumps(CONTRACT))
        mix_data["archive"]["episode_profile"]["mix"]["min_share"]["stock"] = 0.1
        with self.assertRaises(ValueError) as caught:
            profile(mix_data)
        self.assertIn("stock", str(caught.exception))


class TestHouseStyleLabels(unittest.TestCase):
    def bound_leaves(self, node, prefix=""):
        for key, value in node.items():
            if isinstance(value, dict):
                yield from self.bound_leaves(value, f"{prefix}{key}.")
            elif isinstance(value, list) and value and all(
                    isinstance(v, (int, float)) and not isinstance(v, bool) for v in value):
                yield prefix + key, value          # a declared range is a bound as much as a scalar
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                yield prefix + key, value

    def test_every_numeric_bound_has_a_basis_and_says_where_it_came_from(self):
        """No archive-documentation body publishes a concentration cap or a quotation ceiling.

        A number in a style contract reads like a rule, so an unlabelled one imports a standard
        that does not exist and a later reader will not dare question it. Either the basis
        admits this repo's taste or it cites a numbered rule from the guide — the test fails on
        a bare number either way.
        """
        archive = CONTRACT["archive"]
        offenders = []
        for name in ("episode_profile", "rights"):
            for dotted, _value in self.bound_leaves(archive[name]):
                leaf = dotted.rsplit(".", 1)[-1]
                parent = archive[name]
                for part in dotted.split(".")[:-1]:
                    parent = parent[part]
                basis = parent.get(f"{leaf}_basis") or parent.get("basis")
                if basis is None:
                    offenders.append(f"{name}:{dotted} has no basis")
                elif not re.search(r"house style|rule\s*\d+|^\s*\d+:", basis, re.I):
                    offenders.append(f"{name}:{dotted} basis cites nothing: {basis[:60]!r}")
        self.assertEqual(offenders, [], offenders)


class TestOptOutIsARecord(unittest.TestCase):
    def test_the_opt_out_requires_a_reason_from_a_closed_enum(self):
        opt = profile(CONTRACT)["opt_out"]
        self.assertTrue(opt["required_fields"])
        for field in ("reason", "approved_by", "expires", "scope"):
            self.assertIn(field, opt["required_fields"], f"{field} is not part of the record")
        self.assertTrue(opt["reason_enum"])

    def test_the_reason_enum_has_no_catch_all(self):
        """`other` makes the record a formality: any convenience becomes a reason.

        The names that live here are the names an owner has to sign, so the list is short and
        each entry is something a human can be asked about later.
        """
        reasons = profile(CONTRACT)["opt_out"]["reason_enum"]
        for forbidden in ("other", "misc", "miscellaneous", "n_a", "na"):
            self.assertNotIn(forbidden, reasons, f"{forbidden} turns the enum back into a "
                                                 "free-text box")

    def test_an_opt_out_cannot_silence_the_layer(self):
        """The record downgrades the gate; it does not mute it.

        This flag is the difference between "this episode is excused and we can see it" and
        "this episode is excused and nobody will ever know", and the resolver's behaviour is
        tested against it in TestEpisodeRecord.
        """
        self.assertIs(profile(CONTRACT)["opt_out"]["silences_gate"], False)

    def test_a_scope_that_is_not_a_layer_or_a_span_is_refused(self):
        scopes = profile(CONTRACT)["opt_out"]["scope_values"]
        self.assertIn("episode", scopes)
        for scope in scopes:
            self.assertIn(scope, ("episode", "act", "sequence"),
                          f"{scope} is not a span this pipeline can measure")


class TestEpisodeRecord(unittest.TestCase):
    """`resolve_mode` is where the default meets the one document an episode owns."""

    def record(self, **changes):
        opt = {"enabled": False, "reason": "rights_unavailable", "scope": "episode",
               "approved_by": "thana", "expires": "2027-06-30"}
        opt.update(changes)
        return {"archive": opt}

    def closed(self):
        contract = json.loads(json.dumps(CONTRACT))
        contract["archive"]["episode_profile"]["mode"] = "closed"
        return contract

    def test_an_episode_that_says_nothing_gets_the_default(self):
        mode, findings = resolve_mode(CONTRACT, {"slug": "next"})
        self.assertEqual(mode, profile(CONTRACT)["mode"])
        self.assertEqual(findings, [])

    def test_enabled_true_is_the_default_and_needs_no_record(self):
        mode, findings = resolve_mode(CONTRACT, {"archive": {"enabled": True}})
        self.assertEqual(mode, "warn")
        self.assertEqual(findings, [])

    def test_an_opt_out_without_a_reason_is_refused(self):
        """The reason is what makes the exemption reviewable after the fact.

        A record that only says `enabled: false` is the unlogged exception the research names as
        the way a house style actually dies: not a rejected rule, a convenience nobody signed.
        """
        with self.assertRaises(ValueError) as caught:
            resolve_mode(CONTRACT, {"archive": {"enabled": False}})
        self.assertIn("reason", str(caught.exception))

    def test_a_reason_outside_the_closed_enum_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            resolve_mode(CONTRACT, self.record(reason="too_much_work"))
        self.assertIn("too_much_work", str(caught.exception))

    def test_an_opt_out_needs_a_named_approver(self):
        with self.assertRaises(ValueError) as caught:
            resolve_mode(CONTRACT, self.record(approved_by="  "))
        self.assertIn("approved_by", str(caught.exception))

    def test_an_expiry_that_is_not_an_iso_date_is_refused(self):
        for bad in ("someday", "2027-06-30T00:00", ""):
            with self.assertRaises(ValueError, msg=bad):
                resolve_mode(CONTRACT, self.record(expires=bad))

    def test_an_expired_record_is_refused_rather_than_ignored(self):
        """Silence on a stale exemption is how an opt-out becomes permanent by accident.

        The expiry only has teeth if pasting an old date is an error the build reports; the
        alternative is an episode that opted out for one deadline and stayed opted out forever.
        """
        with self.assertRaises(ValueError) as caught:
            resolve_mode(CONTRACT, self.record(expires="2020-01-01"))
        self.assertIn("expires", str(caught.exception))

    def test_a_scope_outside_the_declared_spans_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            resolve_mode(CONTRACT, self.record(scope="chapter"))
        self.assertIn("chapter", str(caught.exception))

    def test_an_opt_out_downgrades_closed_to_warn_and_reports_itself(self):
        """The record excuses the episode from refusing; it does not excuse it from being seen.

        This is `silences_gate: false` as behaviour. If opting out also deleted the finding, the
        only evidence that the film was made without the layer would be a line in a file nobody
        opens, and the next episode would inherit the exemption rather than the rule.
        """
        mode, findings = resolve_mode(self.closed(), self.record())
        self.assertEqual(mode, "warn")
        self.assertEqual([f.code for f in findings], ["archive_layer_opted_out"])
        self.assertIn("rights_unavailable", findings[0].message)
        self.assertIn("thana", findings[0].message)

    def test_an_opt_out_on_a_warning_episode_still_reports_itself(self):
        mode, findings = resolve_mode(CONTRACT, self.record())
        self.assertEqual(mode, "warn")
        self.assertEqual([f.code for f in findings], ["archive_layer_opted_out"])

    def test_an_episode_cannot_widen_to_off(self):
        """`off` is a branch state, not an episode choice; otherwise one document turns the
        default back into an option."""
        with self.assertRaises(ValueError) as caught:
            resolve_mode(self.closed(), {"archive": {"mode": "off"}})
        self.assertIn("off", str(caught.exception))

    def test_an_episode_may_narrow_itself_to_closed(self):
        mode, findings = resolve_mode(CONTRACT, {"archive": {"mode": "closed"}})
        self.assertEqual(mode, "closed")
        self.assertEqual(findings, [])

    def test_a_non_object_archive_record_is_refused(self):
        for bad in ("yes", ["enabled"], 7):
            with self.assertRaises(ValueError, msg=repr(bad)):
                resolve_mode(CONTRACT, {"archive": bad})


def shots(**by_layer):
    """A shot list shaped the way the QC timeline will hand it over."""
    out = []
    for layer, spans in by_layer.items():
        for start, seconds in spans:
            out.append({"layer": layer, "start": start, "seconds": seconds})
    return out


class TestMixObligation(unittest.TestCase):
    def clean_timeline(self):
        """Nine minutes, no overlaps, two acts, 120 of 540 screen seconds archival."""
        return shots(
            **{"3d": [(0.0, 140.0), (180.0, 90.0), (470.0, 70.0)],
               "archive": [(140.0, 40.0), (270.0, 40.0), (430.0, 40.0)],
               "cards": [(310.0, 60.0)],
               "manim": [(370.0, 60.0)]})

    def test_a_timeline_that_meets_the_obligation_reports_nothing(self):
        self.assertEqual(mix_findings(self.clean_timeline(), FLOORED), [])

    def test_an_empty_timeline_is_refused_not_passed(self):
        """A build with no shots is a build that has not started, and reporting "no archive"
        about it would blame the layer for the assembler."""
        with self.assertRaises(ValueError):
            mix_findings([], FLOORED)

    def test_a_3d_only_film_names_the_missing_layer_once(self):
        """One blocking code, not three, so the report says what to fix.

        Emitting share_low and act_missing next to layer_missing describes one fact three ways
        and pushes the reader to compare numbers instead of adding the layer.
        """
        timeline = shots(**{"3d": [(0.0, 240.0), (240.0, 300.0)]})
        found = mix_findings(timeline, FLOORED)
        self.assertEqual([f.code for f in found], ["archive_layer_missing"])
        self.assertEqual(found[0].severity, "warning",
                         "warn mode reports what closed would refuse, without refusing it")

    def test_the_share_is_measured_in_seconds_not_in_shot_counts(self):
        """Three two-second inserts are 20% of the shots and 2% of the film.

        The count reading passes; the second reading is the one that matches what a viewer
        receives, which is what mix.measured_on declares.
        """
        timeline = shots(**{"3d": [(i * 20.0, 20.0) for i in range(12)],
                            "archive": [(10.0, 2.0), (150.0, 2.0), (300.0, 2.0)]})
        found = mix_findings(timeline, FLOORED)
        self.assertIn("archive_share_low", [f.code for f in found])

    def test_an_act_with_no_archival_shot_is_named_by_its_bounds(self):
        """The layer can meet a global share and still abandon the last third of the argument.

        Reporting the span rather than an act index is what makes the finding actionable: the
        editor needs seconds to look at, not a number this file invented.
        """
        timeline = shots(**{"3d": [(0.0, 120.0), (120.0, 120.0), (300.0, 240.0)],
                            "archive": [(10.0, 60.0)]})
        found = mix_findings(timeline, FLOORED)
        self.assertIn("archive_act_missing", [f.code for f in found])
        message = [f.message for f in found if f.code == "archive_act_missing"][0]
        self.assertIn("270", message)

    def test_a_layer_the_taxonomy_does_not_know_about_is_reported(self):
        """A fifth visual kind added by an assembler is invisible to a mix that budgets four.

        Without this, `stock` footage could carry an entire film and the share would still
        compute over the layers the contract happens to name.
        """
        timeline = shots(**{"3d": [(0.0, 200.0), (200.0, 100.0)],
                            "archive": [(10.0, 60.0), (300.0, 80.0)],
                            "stock": [(120.0, 60.0)]})
        found = mix_findings(timeline, FLOORED)
        self.assertIn("layer_unknown", [f.code for f in found])
        self.assertIn("stock", [f.message for f in found if f.code == "layer_unknown"][0])

    def test_off_reports_nothing_at_all(self):
        timeline = shots(**{"3d": [(0.0, 540.0)]})
        self.assertEqual(mix_findings(timeline, FLOORED, mode="off"), [])

    def test_closed_refuses_and_warn_does_not(self):
        timeline = shots(**{"3d": [(0.0, 540.0)]})
        require_mix(timeline, FLOORED, mode="warn")
        with self.assertRaises(ValueError) as caught:
            require_mix(timeline, FLOORED, mode="closed")
        self.assertIn("archive_layer_missing", str(caught.exception))

    def test_the_act_partition_is_the_same_one_the_finding_names(self):
        """A gate bound calibrated on a different span than the gate measures ships findings
        nobody can act on, so the act length is derived from the contract band, not from a
        constant in this file."""
        _low, high = profile(CONTRACT)["mix"]["act_seconds"]
        total = 450.0
        self.assertLessEqual(total / 2, high)
        self.assertEqual(mix_findings(self.clean_timeline(), FLOORED), [])


if __name__ == "__main__":
    unittest.main()
