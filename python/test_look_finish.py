# -*- coding: utf-8 -*-
"""The shared finishing pass is contract data, and the gate proves it ran.

`archive.cohesion.shared_finishing_pass` names `tools/look_pass.py` as the one transform that
makes an episode read as a single film: grain, bloom, vignette and contrast reach the 3D beats,
the Manim layer, the cards and the archival inserts in the same pass, which is the mechanism the
research says carries cohesion. Two things made that claim unenforceable:

* the eight strengths and the encode settings lived as Python defaults in the tool, so the one
  place a number reaches the screen without being contract data was the place that decides how
  every source looks together (D-017 says any number reaching the screen is contract data);
* nothing checked the pass had run at all. A concat that skipped the grade, a second grade added
  by hand afterwards, or a look-dev override that quietly became the shipped master all produced
  a file the gate called clean.

So: the numbers are read, the run leaves a report naming what it used and the digest of the file
it wrote, and the gate reads that report instead of trusting.
"""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import look_pass as L  # noqa: E402
import qc_episode as Q  # noqa: E402
from workflow.config import style_contract  # noqa: E402

CONTRACT = style_contract(ROOT)
COHESION = CONTRACT["archive"]["cohesion"]
FINISH = COHESION["finish"]
STRENGTHS = FINISH["strengths"]
ENCODE = FINISH["encode"]
REPORT = FINISH["report_filename"]


def contract_with(**changed):
    """A copy of the house contract with one finishing number moved.

    Every test here has to be able to prove the code reads the file rather than remembering a
    value that happens to match it, so the fixture moves the file.
    """
    import copy
    clone = copy.deepcopy(CONTRACT)
    finish = clone["archive"]["cohesion"]["finish"]
    for key, value in changed.items():
        if key in finish["strengths"]:
            finish["strengths"][key] = value
        elif key in finish["encode"]:
            finish["encode"][key] = value
        else:
            finish[key] = value
    return clone


def graded_file(directory: Path, name="video-graded.mp4", body=b"graded-bytes"):
    """A stand-in master whose digest the tests can predict."""
    path = Path(directory) / name
    path.write_bytes(body)
    return path


def report_for(graded: Path, *, strengths=None, digest=None, contract=CONTRACT):
    """The evidence file `look_pass.apply` would have left beside a graded master."""
    body = {
        "tool": "tools/look_pass.py",
        "graded": str(graded),
        "graded_sha256": digest if digest is not None else hashlib.sha256(graded.read_bytes()).hexdigest(),
        "strengths": dict(strengths if strengths is not None else STRENGTHS),
        "overrides": {},
        "encode": dict(ENCODE),
        "filtergraph": L.build_vf(contract=contract),
    }
    path = Path(graded).parent / REPORT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, indent=2), encoding="utf-8")
    return path


class FakeFfmpeg:
    """Stands in for the encoder and does what the encoder does: the output file appears."""

    def __init__(self):
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append([str(a) for a in argv])
        destination = Path(argv[-1])
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"encoded")

        class Done:
            returncode = 0

        return Done()


class TheNumbersAreContractData(unittest.TestCase):
    def test_the_module_holds_no_finishing_number_of_its_own(self):
        source = (ROOT / "tools" / "look_pass.py").read_text(encoding="utf-8")
        for name, value in list(STRENGTHS.items()) + list(ENCODE.items()):
            if isinstance(value, str):
                continue
            with self.subTest(strength=name):
                self.assertNotIn(repr(float(value)), source,
                                 f"{name}={value} is written into the tool as well as the contract")

    def test_the_graph_carries_the_grain_the_contract_declares(self):
        vf = L.build_vf(contract=contract_with(grain=7.25))
        self.assertIn("noise=alls=7.25", vf)

    def test_moving_a_contract_strength_moves_the_graph(self):
        baseline = L.build_vf(contract=CONTRACT)
        moved = L.build_vf(contract=contract_with(vignette=0.11))
        self.assertNotEqual(baseline, moved)
        self.assertIn("vignette=0.11", moved)

    def test_the_encode_settings_reach_the_command_line(self):
        ran = FakeFfmpeg()
        original = L.subprocess.run
        L.subprocess.run = ran
        try:
            with tempfile.TemporaryDirectory() as tmp:
                src = graded_file(Path(tmp), "concat.mp4")
                L.apply(src, Path(tmp) / "video-graded.mp4", contract=contract_with(crf=23))
        finally:
            L.subprocess.run = original
        argv = ran.calls[0]
        self.assertEqual(argv[argv.index("-crf") + 1], "23")
        self.assertEqual(argv[argv.index("-c:v") + 1], ENCODE["codec"])
        self.assertEqual(argv[argv.index("-preset") + 1], ENCODE["preset"])
        self.assertEqual(argv[argv.index("-pix_fmt") + 1], ENCODE["pixel_format"])

    def test_an_explicit_override_wins_over_the_contract_and_is_named(self):
        ran = FakeFfmpeg()
        original = L.subprocess.run
        L.subprocess.run = ran
        try:
            with tempfile.TemporaryDirectory() as tmp:
                src = graded_file(Path(tmp), "concat.mp4")
                dst = Path(tmp) / "video-graded.mp4"
                L.apply(src, dst, contract=CONTRACT, grain=9.0)
                body = json.loads((Path(tmp) / REPORT).read_text(encoding="utf-8"))
        finally:
            L.subprocess.run = original
        self.assertEqual(body["strengths"]["grain"], 9.0)
        self.assertEqual(body["overrides"]["grain"], {"contract": STRENGTHS["grain"], "used": 9.0},
                         "a look-dev override has to be visible in the evidence, not folded in")


class TheRunLeavesEvidence(unittest.TestCase):
    def test_apply_writes_the_report_at_the_path_the_contract_names(self):
        ran = FakeFfmpeg()
        original = L.subprocess.run
        L.subprocess.run = ran
        try:
            with tempfile.TemporaryDirectory() as tmp:
                src = graded_file(Path(tmp), "concat.mp4")
                L.apply(src, Path(tmp) / "video-graded.mp4", contract=CONTRACT)
                path = Path(tmp) / REPORT
                self.assertTrue(path.is_file(), f"{REPORT} was not written")
                body = json.loads(path.read_text(encoding="utf-8"))
        finally:
            L.subprocess.run = original
        self.assertEqual(body["strengths"], STRENGTHS)
        self.assertEqual(body["encode"], ENCODE)

    def test_the_report_digests_the_file_it_wrote(self):
        ran = FakeFfmpeg()
        original = L.subprocess.run
        L.subprocess.run = ran
        try:
            with tempfile.TemporaryDirectory() as tmp:
                src = graded_file(Path(tmp), "concat.mp4")
                dst = Path(tmp) / "video-graded.mp4"
                L.apply(src, dst, contract=CONTRACT)
                body = json.loads((Path(tmp) / REPORT).read_text(encoding="utf-8"))
                expected = hashlib.sha256(dst.read_bytes()).hexdigest()
        finally:
            L.subprocess.run = original
        self.assertEqual(body["graded_sha256"], expected)

    def test_a_grade_that_produced_no_file_is_a_failure_not_a_report(self):
        class ProducedNothing:
            def __call__(self, argv, **kwargs):
                class Done:
                    returncode = 0
                return Done()

        original = L.subprocess.run
        L.subprocess.run = ProducedNothing()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                src = graded_file(Path(tmp), "concat.mp4")
                with self.assertRaises(FileNotFoundError):
                    L.apply(src, Path(tmp) / "video-graded.mp4", contract=CONTRACT)
                self.assertFalse((Path(tmp) / REPORT).exists(),
                                 "evidence was written for a grade that did not happen")
        finally:
            L.subprocess.run = original


class TheSingleTransformClaimIsGated(unittest.TestCase):
    def check(self, tmp, **kwargs):
        episode = Path(tmp)
        graded = graded_file(episode)
        report_for(graded, **kwargs)
        return Q.check_shared_finish(episode, graded, CONTRACT)

    def test_a_grade_that_matches_the_contract_is_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.check(tmp), [])

    def test_no_report_at_all_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            graded = graded_file(Path(tmp))
            findings = Q.check_shared_finish(Path(tmp), graded, CONTRACT)
        self.assertEqual([f.code for f in findings], ["shared_finish_unreported"])
        self.assertEqual(findings[0].severity, "error")

    def test_a_strength_off_the_contract_is_an_error_naming_the_strength(self):
        moved = dict(STRENGTHS)
        moved["contrast"] = 1.4
        with tempfile.TemporaryDirectory() as tmp:
            findings = self.check(tmp, strengths=moved)
        self.assertEqual([f.code for f in findings], ["shared_finish_off_contract"])
        self.assertEqual(findings[0].severity, "error")
        self.assertIn("contrast", findings[0].message)
        self.assertIn("1.4", findings[0].message)

    def test_a_master_re_encoded_after_the_grade_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            episode = Path(tmp)
            graded = graded_file(episode)
            report_for(graded)
            graded.write_bytes(b"somebody graded it again by hand")
            findings = Q.check_shared_finish(episode, graded, CONTRACT)
        self.assertEqual([f.code for f in findings], ["shared_finish_digest_moved"])
        self.assertEqual(findings[0].severity, "error")

    def test_a_missing_graded_file_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            episode = Path(tmp)
            report_for(episode / "video-graded.mp4", digest="0" * 64)
            findings = Q.check_shared_finish(episode, episode / "video-graded.mp4", CONTRACT)
        self.assertEqual([f.code for f in findings], ["shared_finish_missing"])

    def test_the_severity_is_the_one_enforcement_policy_declares_for_metadata(self):
        """`enforcement_policy.metadata_rules` is contract data, so the gate reads its own severity."""
        policy = CONTRACT["archive"]["enforcement_policy"]["metadata_rules"]
        self.assertTrue(policy.startswith("error"),
                        "this test assumes the contract still puts metadata on the blocking side")
        with tempfile.TemporaryDirectory() as tmp:
            graded = graded_file(Path(tmp))
            findings = Q.check_shared_finish(Path(tmp), graded, CONTRACT)
        self.assertEqual(findings[0].severity, policy.split()[0])

    def test_the_gate_runs_as_part_of_the_episode_run(self):
        source = (ROOT / "tools" / "qc_episode.py").read_text(encoding="utf-8")
        run = source[source.index("def run("):]
        self.assertIn("check_shared_finish", run,
                      "the check exists but nothing calls it, which is how the archive layer "
                      "became declared and not enforced")


if __name__ == "__main__":
    unittest.main()
