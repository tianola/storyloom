"""The preflight must prove the tools work before a run spends hours on them.

#138 audited the capabilities and #139 installed them, but installation is a one-time event in a
session log and a video build is a repeated one. The failure this closes is the one this repo has
already been bitten by twice: a stage dies 40 minutes into a five-hour render because a binary or a
model snapshot that was present when somebody last looked had moved, or was never on PATH at all.

Two design facts the tests pin down, because both were measured rather than guessed:

* The module probe uses `importlib.util.find_spec`, not `import`. `import onnxruntime` costs seconds
  and `import faster_whisper` pulls ctranslate2 in behind it; a gate that runs before every stage
  has to cost milliseconds, or the pipeline will grow a habit of skipping it.
* An executable candidate that carries a separator is checked where it is, not on PATH. Tesseract is
  installed here at `C:/Program Files/Tesseract-OCR/tesseract.exe` and is *not* on PATH, so a
  PATH-only check reports a missing tool that works fine - and a gate that cries wolf gets skipped.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from host_double import FakeHost, healthy_host  # noqa: E402
from workflow import capabilities as caps  # noqa: E402
from workflow.capabilities import (  # noqa: E402
    CAPABILITIES_FILENAME, REFUSED, RealHost, capabilities, format_findings, module_probe_argv,
    preflight, required_failures, resolve_path,
)
from workflow.config import EPISODE_PHASES  # noqa: E402
from workflow.init_episode import init_episode  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "python"))

import assemble_episode  # noqa: E402
import narrate  # noqa: E402
import qc_episode  # noqa: E402

TTS = "narration-tts"


class RegistryIsWellFormed(unittest.TestCase):
    def setUp(self):
        self.registry = capabilities(ROOT)

    def test_declares_the_two_interpreters_the_pipeline_actually_uses(self):
        self.assertEqual({"pipeline", "narration"}, set(self.registry["interpreters"]))
        for interpreter in self.registry["interpreters"].values():
            self.assertTrue(interpreter["python"].strip())
            self.assertGreater(len(interpreter["why"]), 30)

    def test_every_capability_carries_the_keys_a_finding_needs_to_be_actionable(self):
        for capability in self.registry["capabilities"]:
            for key in ("id", "phases", "required", "why", "remediation", "checks"):
                self.assertIn(key, capability, capability.get("id"))
            self.assertGreater(len(capability["why"]), 30, capability["id"])
            self.assertGreater(len(capability["remediation"]), 10, capability["id"])

    def test_every_reference_resolves_against_the_real_vocabularies(self):
        declared = [c["id"] for c in self.registry["capabilities"]]
        self.assertEqual(len(set(declared)), len(declared), "duplicate capability id")
        for capability in self.registry["capabilities"]:
            self.assertTrue(set(capability["phases"]) <= set(EPISODE_PHASES), capability["id"])
            self.assertTrue(capability["checks"], capability["id"])
            for check in capability["checks"]:
                self.assertIn(check["kind"], ("path", "executable", "module", "blender"),
                              capability["id"])
                if check["kind"] == "module":
                    self.assertIn(check["interpreter"], self.registry["interpreters"],
                                  capability["id"])
                if check["kind"] == "executable":
                    self.assertTrue(check["any_of"], capability["id"])

    def test_the_build_critical_phases_are_covered_by_a_required_capability(self):
        """A phase with no required capability is a phase nothing checks before it runs."""
        for phase in ("vo", "motion", "edit", "qc"):
            covered = [c for c in self.registry["capabilities"]
                       if c["required"] and phase in c["phases"]]
            self.assertTrue(covered, f"no required capability covers {phase}")

    def test_latex_is_declared_optional_because_the_current_scenes_do_not_use_it(self):
        """Manim's MathTex is the capability known-absent here; a hard fail would block renders."""
        latex = [c for c in self.registry["capabilities"] if "latex" in c["id"]]
        self.assertEqual(1, len(latex))
        self.assertFalse(latex[0]["required"])

    def test_the_registry_carries_no_credentials(self):
        raw = (ROOT / "workflow" / CAPABILITIES_FILENAME).read_text(encoding="utf-8").lower()
        for needle in ("api_key", "apikey", "token", "secret", "password", "sk-"):
            self.assertNotIn(needle, raw)


class ModuleProbeStaysCheap(unittest.TestCase):
    def test_the_probe_asks_for_find_spec_not_an_import(self):
        argv = module_probe_argv("python", "faster_whisper")
        self.assertEqual("python", argv[0])
        self.assertIn("find_spec", argv[2])
        self.assertNotIn("import faster_whisper", argv[2])
        self.assertEqual(["python", "-c", argv[2], "faster_whisper"], argv)


class TheProbeAsksTheInterpreterTheRegistryNamed(unittest.TestCase):
    """A bare interpreter name has to be resolved before it is spawned, or Windows resolves it.

    Measured on this machine, with the preflight running under `.venv-xpu/Scripts/python.exe`:
    `shutil.which("python")` answered `C:\\Python314\\python.EXE`, but `subprocess.run(["python",
    ...])` ran `C:\\Users\\thana\\AppData\\Roaming\\uv\\python\\cpython-3.12-...\\python.exe`
    instead, because CreateProcess searches the calling image's own directory before PATH and
    every venv keeps a `python.exe` there. The child reported numpy, PIL, faster_whisper,
    scenedetect and pytesseract all missing - all five are installed in the 3.14 the registry
    names - so `qc-intelligibility` failed as a required capability and `init_episode` refused to
    create an episode on a machine that could have built it. A gate that cries wolf on a healthy
    machine gets skipped, which is the failure this registry's own comments name.
    """

    def probe(self, host, python="python", name="numpy"):
        seen = []

        def fake_run(argv, **kwargs):
            seen.append([str(a) for a in argv])

            class Done:
                returncode = 0

            return Done()

        original = caps.subprocess.run
        caps.subprocess.run = fake_run
        try:
            answer = host.module(python, name)
        finally:
            caps.subprocess.run = original
        return answer, seen

    def test_a_bare_name_is_resolved_to_an_absolute_path_before_it_is_spawned(self):
        class Host(RealHost):
            def which(self, name):
                return FOUND

        # what `which` answers on the machine the test runs on: a Windows path is not absolute on Linux
        FOUND = "C:/Python314/python.EXE" if os.name == "nt" else "/usr/bin/python3"
        answer, seen = self.probe(Host())
        self.assertTrue(answer)
        self.assertEqual(seen[0][0], FOUND)
        self.assertTrue(os.path.isabs(seen[0][0]),
                        "a bare name lets CreateProcess pick the calling venv's own python.exe")

    def test_an_absolute_interpreter_is_used_exactly_as_declared(self):
        class Host(RealHost):
            def which(self, name):
                raise AssertionError("an absolute path needs no lookup")

        declared = str(ROOT / ".venv" / "Scripts" / "python.exe")
        answer, seen = self.probe(Host(), python=declared)
        self.assertTrue(answer)
        self.assertEqual(seen[0][0], declared)

    def test_an_interpreter_this_machine_does_not_have_is_reported_missing_not_spawned(self):
        class Host(RealHost):
            def which(self, name):
                return None

        answer, seen = self.probe(Host())
        self.assertFalse(answer)
        self.assertEqual(seen, [],
                         "spawning the bare name would ask whichever python.exe the caller's own "
                         "directory happens to hold, and report its gaps as this machine's")


class PathResolution(unittest.TestCase):
    """A declared path is a promise about where to look, not necessarily a literal filename.

    The Hugging Face cache puts a revision hash in the middle of the path the QC tool needs, so a
    literal entry would rot the day somebody re-downloads the model - and the failure mode would be
    the gate reporting a present model as missing. A pattern resolves to a real file when one matches
    and stays a pattern when none does, so the finding reads "missing" instead of raising.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_a_pattern_resolves_to_the_file_that_is_actually_there(self):
        for revision in ("aaa", "bbb"):
            leaf = self.tmp / "snapshots" / revision
            leaf.mkdir(parents=True)
            (leaf / "model.bin").write_bytes(b"x")
        want = _flat(self.tmp / "snapshots" / "aaa" / "model.bin")
        self.assertEqual(want, _flat(resolve_path(self.tmp, "snapshots/*/model.bin")))

    def test_a_pattern_that_matches_nothing_does_not_raise(self):
        resolved = _flat(resolve_path(self.tmp, "snapshots/*/model.bin"))
        self.assertIn("*", resolved)
        self.assertIsNone(RealHost().size(Path(resolved)))

    def test_a_home_relative_path_is_expanded_before_it_is_statified(self):
        resolved = _flat(resolve_path(self.tmp, "~/.cache/huggingface/whatever"))
        self.assertTrue(Path(resolved).is_absolute(), resolved)
        self.assertNotIn("~", resolved)


def _flat(path) -> str:
    return str(path).replace("\\", "/")


class PreflightAsksEveryQuestion(unittest.TestCase):
    def test_a_healthy_machine_yields_no_failures_at_all(self):
        self.assertEqual([], [f for f in preflight(ROOT, host=healthy_host(ROOT)) if not f.ok])

    def test_every_capability_reports_on_every_one_of_its_checks(self):
        registry = capabilities(ROOT)
        checks = sum(len(c["checks"]) for c in registry["capabilities"])
        self.assertEqual(checks, len(preflight(ROOT, host=healthy_host(ROOT))))

    def test_a_phase_filter_only_asks_about_that_phase(self):
        host = healthy_host(ROOT)
        preflight(ROOT, phase="qc", host=host)
        self.assertNotIn("blender", host.asked_kinds())
        self.assertIn("module", host.asked_kinds())
        self.assertNotIn("narration-tts", {f.capability for f in preflight(ROOT, phase="qc", host=host)})

    def test_an_unknown_phase_is_rejected_rather_than_silently_checking_nothing(self):
        with self.assertRaises(ValueError):
            preflight(ROOT, phase="broadcast", host=healthy_host(ROOT))


class PreflightFailsOnAHalfBuiltMachine(unittest.TestCase):
    def test_a_missing_python_module_fails_the_capability_that_needs_it(self):
        host = healthy_host(ROOT, missing_modules=["kokoro_onnx"])
        failures = required_failures(preflight(ROOT, host=host))
        self.assertEqual([TTS], sorted({f.capability for f in failures}))
        self.assertIn("kokoro_onnx", failures[0].detail)
        self.assertIn(".venv/Scripts/python.exe", failures[0].remediation)

    def test_a_short_model_file_fails_even_though_the_path_exists(self):
        """The 325 MB Kokoro weights are the thing that can half-download and still look present."""
        model = _path_check(ROOT, TTS)
        host = healthy_host(ROOT, short_paths={model: 1024})
        failures = required_failures(preflight(ROOT, host=host))
        self.assertIn(TTS, [f.capability for f in failures])
        self.assertIn("bytes", failures[0].detail)

    def test_a_missing_model_file_says_so_rather_than_reporting_zero_bytes(self):
        model = _path_check(ROOT, TTS)
        host = healthy_host(ROOT, missing_paths=[model])
        failures = required_failures(preflight(ROOT, host=host))
        self.assertIn("missing", " ".join(f.detail for f in failures).lower())

    def test_a_required_binary_that_is_nowhere_fails_with_its_remediation(self):
        host = healthy_host(ROOT, missing_executables=["ffmpeg"])
        failures = required_failures(preflight(ROOT, host=host))
        self.assertIn("ffmpeg", " ".join(f.detail + " " + f.remediation for f in failures))

    def test_a_blender_path_that_is_gone_fails_the_3d_capability(self):
        failures = required_failures(preflight(ROOT, host=healthy_host(ROOT, blender=False)))
        self.assertIn("blender", " ".join(f.capability + f.detail for f in failures).lower())

    def test_an_off_path_binary_still_passes_when_the_registry_names_where_it_lives(self):
        """Tesseract: installed, not on PATH. A gate that calls this missing gets ignored."""
        registry = self._write_registry({
            "id": "ocr", "phases": ["assets"], "required": True,
            "why": "burned-in caption OCR on archive clips",
            "remediation": "install Tesseract-OCR",
            "checks": [{"kind": "executable",
                        "any_of": ["tesseract", "C:/Program Files/Tesseract-OCR/tesseract.exe"]}]})
        host = FakeHost(present=["C:/Program Files/Tesseract-OCR/tesseract.exe"])
        findings = preflight(registry, host=host)
        self.assertEqual([], [f for f in findings if not f.ok])
        self.assertNotIn(("executable", "C:/Program Files/Tesseract-OCR/tesseract.exe"), host.asked)

    def test_an_optional_capability_may_fail_without_failing_the_run(self):
        registry = self._write_registry({
            "id": "latex-for-mathtext", "phases": ["motion"], "required": False,
            "why": "MathTex needs a TeX distribution, Text does not",
            "remediation": "winget install MiKTeX.MiKTeX",
            "checks": [{"kind": "executable", "any_of": ["xelatex", "pdflatex", "latex"]}]})
        findings = preflight(registry, host=FakeHost())
        self.assertEqual([], required_failures(findings))
        self.assertFalse([f for f in findings if f.ok])

    def _write_registry(self, capability):
        """A one-capability registry in a throwaway tree, so semantics are tested without hooks."""
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        template = json.loads((ROOT / "workflow" / CAPABILITIES_FILENAME).read_text(encoding="utf-8"))
        one = dict(template, name="test registry", capabilities=[capability] if isinstance(capability, dict) else capability)
        (tmp / "workflow").mkdir()
        (tmp / "workflow" / CAPABILITIES_FILENAME).write_text(json.dumps(one), encoding="utf-8")
        return tmp


class EpisodeInitRefusesAHalfBuiltMachine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from toolchain import require_skills
        require_skills()   # init_episode refuses a machine without the mapped skills

    def test_a_missing_capability_stops_the_episode_from_being_created(self):
        """The value is the stop, not the message: a build started on a broken box ends broken."""
        host = healthy_host(ROOT, missing_modules=["kokoro_onnx"])
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError) as caught:
                init_episode(Path(tmp), "episode-test", "Test", host=host)
            message = str(caught.exception)
            self.assertIn("preflight", message.lower())
            self.assertIn(TTS, message)
            self.assertFalse((Path(tmp) / "episode-test").exists())

    def test_a_healthy_machine_still_lands_the_capability_registry_with_the_episode(self):
        with tempfile.TemporaryDirectory() as tmp:
            episode = init_episode(Path(tmp), "episode-test", "Test", host=healthy_host(ROOT))
            copied = json.loads((episode / CAPABILITIES_FILENAME).read_text(encoding="utf-8"))
            self.assertEqual(capabilities(ROOT)["name"], copied["name"])


class FindingsReadAsATable(unittest.TestCase):
    def test_the_report_names_the_capability_and_what_to_do_about_it(self):
        host = healthy_host(ROOT, missing_modules=["kokoro_onnx"])
        text = format_findings(preflight(ROOT, host=host))
        self.assertIn(TTS, text)
        self.assertIn("FAIL", text)
        self.assertIn("PASS", text)
        self.assertIn(".venv/Scripts/python.exe", text)

    def test_the_real_host_probes_through_the_filesystem_and_path_lookup(self):
        """Only the plumbing is asserted here - what this machine reports is the tool's business."""
        host = RealHost()
        self.assertIsNone(host.which("definitely-not-a-real-binary-xyz"))
        self.assertIsNotNone(host.which("ffmpeg"))
        self.assertIsNotNone(host.size(ROOT / "workflow" / CAPABILITIES_FILENAME))
        self.assertIsNone(host.size(ROOT / "workflow" / "no-such-file.json"))
        self.assertTrue(host.module("python", "json"))
        self.assertFalse(host.module("python", "definitely_not_a_real_module_xyz"))


class StageEntrypointsRefuseAHalfBuiltMachine(unittest.TestCase):
    """A gate nobody calls is documentation, so the check lives in the entrypoints that eat hours.

    Each test hands the stage arguments it would reject on its own - a request file that does not
    exist, a master that does not exist - and asserts the refusal code is the preflight's. That
    ordering is the whole point: a capability check that runs after the first ffmpeg call has
    already spent the thirty minutes it exists to save.
    """

    def test_the_assembler_refuses_before_it_touches_the_timeline(self):
        host = healthy_host(ROOT, missing_executables=["ffmpeg"])
        self.assertEqual(REFUSED, assemble_episode.main(host=host))

    def test_the_narration_batch_refuses_before_it_loads_the_weights(self):
        loaded = []
        host = healthy_host(ROOT, missing_modules=["kokoro_onnx"])
        with tempfile.TemporaryDirectory() as tmp:
            argv = ["--input", f"{tmp}/no-such-request.json", "--output", f"{tmp}/vo",
                    "--model", f"{tmp}/kokoro.onnx", "--voices", f"{tmp}/voices.bin"]
            code = narrate.main(argv, engine_factory=lambda *a: loaded.append(a), host=host)
        self.assertEqual(REFUSED, code)
        self.assertEqual([], loaded)

    def test_the_qc_gate_refuses_before_it_reads_the_master(self):
        host = healthy_host(ROOT, missing_modules=["faster_whisper"])
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "qc.json"
            code = qc_episode.main(["--episode", f"{tmp}/no-such-episode",
                                    "--master", f"{tmp}/no-such-master.mp4",
                                    "--json", str(report)], host=host)
        self.assertEqual(REFUSED, code)
        self.assertFalse(report.exists())

    def test_a_healthy_machine_lets_the_qc_gate_through_to_its_own_input_checks(self):
        """The gate must not swallow the tools it protects: past it, their errors are still theirs."""
        with tempfile.TemporaryDirectory() as tmp:
            code = qc_episode.main(["--episode", f"{tmp}/no-such-episode",
                                    "--master", f"{tmp}/no-such-master.mp4"],
                                   host=healthy_host(ROOT))
        self.assertNotEqual(REFUSED, code)


def _path_check(root: Path, capability_id: str) -> str:
    for capability in capabilities(root)["capabilities"]:
        if capability["id"] == capability_id:
            for check in capability["checks"]:
                if check["kind"] == "path":
                    return check["path"]
    raise AssertionError(f"capability {capability_id} declares no path check")


if __name__ == "__main__":
    unittest.main()
