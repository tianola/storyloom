"""make_episode: stage order, dry run on the Jensen fixture, resumability, and the planner stop."""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))
import make_episode as M  # noqa: E402


def run(argv):
    out = io.StringIO()
    with redirect_stdout(out):
        code = M.main(argv)
    return code, out.getvalue()


class MakeEpisode(unittest.TestCase):
    def test_dry_run_lists_every_stage_in_order_and_changes_nothing(self):
        before = (ROOT / "work" / "jensen-huang" / "qc" / "make-episode.json").exists()
        code, text = run(["--episode", "work/jensen-huang", "--dry-run"])
        self.assertEqual(code, 0)
        positions = [text.index(f"[{s:9}]") for s in M.STAGES]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("qc_script.py", text)
        self.assertIn("rollout_render.py", text)
        self.assertEqual((ROOT / "work" / "jensen-huang" / "qc" / "make-episode.json").exists(), before)

    def test_a_finished_stage_is_skipped_until_its_input_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = Path(tmp) / "ep"
            (ep / "script").mkdir(parents=True)
            (ep / "qc").mkdir()
            (ep / "script" / "narration.md").write_text("One line.\n", encoding="utf-8")
            (ep / "qc" / "script-qc.json").write_text("{}", encoding="utf-8")
            state = {"script": {"inputs": M.digest(M.inputs_of("script", ep)), "finished": "now"}}
            self.assertEqual(M.status("script", ep, state, False)[0], "done")
            (ep / "script" / "narration.md").write_text("Another line.\n", encoding="utf-8")
            self.assertEqual(M.status("script", ep, state, False)[0], "run")
            self.assertEqual(M.status("script", ep, state, True)[1], "forced")

    def test_a_deleted_beat_render_reopens_render_and_assemble(self):
        """Deleting a beat's mp4 is how a beat is sent back to Blender; the stage must notice.

        2026-11-16, euv-machine: 12 beats were deleted for a geometry fix and `--from ingest`
        reported render and assemble as done, because render declared no outputs and assemble did
        not read the renders, so the master kept the old beats and QC passed on them.
        """
        with tempfile.TemporaryDirectory() as tmp:
            ep = Path(tmp) / "ep"
            (ep / "renders" / "3d").mkdir(parents=True)
            shots = {"u001": {"kind": "3d", "name": "b01"}, "u002": {"kind": "archive", "name": "a"},
                     "u003": {"kind": "3d", "name": "b02"}}
            (ep / "shots.json").write_text(json.dumps(shots), encoding="utf-8")
            for b in ("b01", "b02"):
                (ep / "renders" / "3d" / f"{b}.mp4").write_bytes(b"old " + b.encode())
            state = {s: {"inputs": M.digest(M.inputs_of(s, ep)), "finished": "now"} for s in ("render", "assemble")}
            self.assertEqual(M.status("render", ep, state, False)[0], "done")
            (ep / "renders" / "3d" / "b02.mp4").unlink()
            self.assertEqual(M.status("render", ep, state, False), ("run", "outputs missing"))
            (ep / "renders" / "3d" / "b02.mp4").write_bytes(b"redrawn")
            self.assertEqual(M.status("assemble", ep, state, False)[0], "run")

    def test_a_stage_built_with_older_code_is_named_but_not_rerun(self):
        """A code change is flagged, not acted on: re-rendering hours of beats is the author's call."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tools").mkdir()
            gate = root / "tools" / "qc_script.py"
            gate.write_bytes(b"rule = 1\r\n")
            record = {"inputs": "x", "code": M.code_digest("script", root), "finished": "now"}
            self.assertIsNone(M.code_note("script", record, root))
            gate.write_bytes(b"rule = 1\n")                 # line endings only: not a change
            self.assertIsNone(M.code_note("script", record, root))
            gate.write_bytes(b"rule = 2\n")
            self.assertIn("--force --only script", M.code_note("script", record, root))
            self.assertIsNone(M.code_note("script", {"inputs": "x", "finished": "then"}, root))

    def test_every_stage_names_code_that_exists(self):
        for stage in M.STAGES:
            self.assertTrue(M.code_of(stage), stage)

    def test_plan_without_a_planner_or_storyboard_is_blocked_with_a_brief(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = Path(tmp) / "ep"
            ep.mkdir()
            args = type("A", (), {"replan": False, "ask_cmd": None, "models": "m"})()
            cmds = M.commands("plan", ep, args)
            self.assertTrue(any(isinstance(c, str) and c.startswith("BLOCK:") for c in cmds))

    def test_unknown_stage_is_refused(self):
        with self.assertRaises(SystemExit):
            run(["--episode", "work/jensen-huang", "--only", "nope"])

    def test_narration_request_numbers_lines_like_the_script_gate(self):
        req = M.narration_request(ROOT / "work" / "jensen-huang")
        self.assertEqual(req["utterances"][0]["id"], "u001")
        self.assertEqual(req["voice"], "af_heart")


if __name__ == "__main__":
    unittest.main()
