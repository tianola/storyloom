"""The Claude-backed tools: the API wrapper, the API planner and the frame critic.

No network and no credits: the SDK client and the model's answers are replaced.
"""
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))

import claude_client as CC  # noqa: E402
import frame_critic as FC  # noqa: E402
import plan_storyboard as P  # noqa: E402


class FakeStream:
    def __init__(self, message):
        self.message = message

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.message


class FakeAPI:
    """Records the request and answers with one message."""

    def __init__(self, text='{"ok": true}', stop="end_turn"):
        self.calls = []
        message = SimpleNamespace(stop_reason=stop, stop_details=SimpleNamespace(category="x", explanation="y"),
                                  content=[SimpleNamespace(type="thinking", thinking=""),
                                           SimpleNamespace(type="text", text=text)])
        outer = self

        class Messages:
            def stream(self, **kw):
                outer.calls.append(kw)
                return FakeStream(message)
        self.beta = SimpleNamespace(messages=Messages())


class Client(unittest.TestCase):
    def setUp(self):
        try:
            import anthropic  # noqa: F401
        except ImportError:
            self.skipTest("the anthropic package is not installed")

    def test_the_stable_part_is_a_cached_system_block_and_the_fallback_is_on(self):
        api = FakeAPI("hello")
        self.assertEqual(CC.ask_text("RULES", "beats", api=api), "hello")
        kw = api.calls[0]
        self.assertEqual(kw["model"], CC.MODEL)
        self.assertEqual(kw["system"][0]["cache_control"], {"type": "ephemeral"})
        self.assertEqual(kw["fallbacks"], "default")
        self.assertIn(CC.FALLBACK_BETA, kw["betas"])
        self.assertNotIn("thinking", kw)            # adaptive is the default; effort sets depth
        self.assertEqual(kw["output_config"]["effort"], "high")

    def test_structured_answers_carry_the_schema_and_the_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            png = Path(tmp) / "a.png"
            png.write_bytes(b"\x89PNG fake")
            api = FakeAPI('{"verdict": "pass"}')
            self.assertEqual(CC.ask_json("S", "U", {"type": "object"}, images=[png], api=api), {"verdict": "pass"})
            kw = api.calls[0]
            self.assertEqual(kw["output_config"]["format"]["type"], "json_schema")
            content = kw["messages"][0]["content"]
            self.assertEqual([c["type"] for c in content], ["image", "text"])
            self.assertEqual(content[0]["source"]["media_type"], "image/png")

    def test_a_refusal_or_a_cut_off_answer_is_an_error_not_a_blank(self):
        for stop in ("refusal", "max_tokens"):
            with self.subTest(stop), self.assertRaises(CC.ClaudeError):
                CC.ask_text("S", "U", api=FakeAPI("partial", stop=stop))


class ApiPlanner(unittest.TestCase):
    def test_rules_and_catalog_are_the_cached_part_and_beats_follow(self):
        seen = []
        ask = P.api_ask(lambda system, user: seen.append((system, user)) or '{"beats": {}}')
        prompt = "RULES\n\nSCENE CATALOG\nx\n\nBEATS (name, seconds on screen, narration)\n- a (5 s): hi"
        self.assertEqual(ask(prompt), '{"beats": {}}')
        system, user = seen[0]
        self.assertIn("SCENE CATALOG", system)
        self.assertNotIn("BEATS (", system)
        self.assertTrue(user.startswith("BEATS ("))

    def test_the_real_prompt_splits_before_the_beats(self):
        beats = [{"name": "a", "seconds": 5.0, "text": "x"}]
        prompt = P.build_prompt(beats, {}, ["one error"], {"beats": {}})
        self.assertIn(P.STABLE_END, prompt)
        self.assertLess(prompt.index("SCENE CATALOG"), prompt.index(P.STABLE_END))
        self.assertLess(prompt.index(P.STABLE_END), prompt.index("REJECTED"))   # errors are not cached

    def test_an_api_failure_stops_the_stage_with_the_reason(self):
        def broken(system, user):
            raise CC.ClaudeError("the Anthropic API key was refused")
        with self.assertRaises(SystemExit) as caught:
            P.api_ask(broken)("x\n\nBEATS (y")
        self.assertIn("key was refused", str(caught.exception))


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is not installed")
class FrameCritic(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ep = Path(self.tmp.name) / "ep"
        (self.ep / "renders" / "3d").mkdir(parents=True)
        board = {"beats": {"beat-01": {"scene": "ward", "note": "the ward at night"},
                           "beat-02": {"scene": "asylum", "note": "not rendered yet"}}}
        (self.ep / "storyboard.json").write_text(json.dumps(board), encoding="utf-8")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=320x180:r=30:d=2",
                        "-pix_fmt", "yuv420p", str(self.ep / "renders" / "3d" / "beat-01.mp4")], check=True)
        self.asked = []

    def ask(self, system, user, images):
        self.asked.append((system, user, [Path(p).name for p in images]))
        for p in images:
            self.assertTrue(Path(p).is_file())
        return {"verdict": "fix", "summary": "Figure too small.",
                "problems": [{"kind": "subject_too_small", "severity": "major", "frame": 2, "note": "Move in."}]}

    def run_review(self, **kw):
        with redirect_stdout(io.StringIO()):
            return FC.review(self.ep, ask=self.ask, log=print, **kw)

    def test_rendered_beats_are_sent_with_their_storyboard_entry_and_reported(self):
        report = self.run_review()
        self.assertEqual(list(report["beats"]), ["beat-01"])          # beat-02 has no render
        system, user, images = self.asked[0]
        self.assertEqual(len(images), 3)
        self.assertIn("the ward at night", user)
        written = json.loads((self.ep / "qc" / "frame-critic.json").read_text(encoding="utf-8"))
        self.assertEqual(written["beats"]["beat-01"]["verdict"], "fix")

    def test_an_unchanged_beat_is_not_sent_twice(self):
        self.run_review()
        self.run_review()
        self.assertEqual(len(self.asked), 1)
        board = json.loads((self.ep / "storyboard.json").read_text(encoding="utf-8"))
        board["beats"]["beat-01"]["note"] = "the ward at dawn"
        (self.ep / "storyboard.json").write_text(json.dumps(board), encoding="utf-8")
        self.run_review()
        self.assertEqual(len(self.asked), 2)

    def test_a_dry_run_sends_nothing_and_writes_nothing(self):
        with redirect_stdout(io.StringIO()):
            FC.review(self.ep, dry_run=True)
        self.assertFalse((self.ep / "qc" / "frame-critic.json").exists())

    def test_strict_fails_the_run_on_a_major_problem(self):
        self.run_review()
        original = FC.review
        FC.review = lambda *a, **k: json.loads((self.ep / "qc" / "frame-critic.json").read_text(encoding="utf-8"))
        try:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(FC.main(["--episode", str(self.ep), "--strict"]), 1)
                self.assertEqual(FC.main(["--episode", str(self.ep)]), 0)
        finally:
            FC.review = original

    def test_the_schema_is_strict_enough_for_structured_outputs(self):
        def walk(node):
            if node.get("type") == "object":
                self.assertIs(node["additionalProperties"], False)
                self.assertEqual(sorted(node["required"]), sorted(node["properties"]))
                for child in node["properties"].values():
                    walk(child)
            if node.get("type") == "array":
                walk(node["items"])
        walk(FC.SCHEMA)


if __name__ == "__main__":
    unittest.main()
