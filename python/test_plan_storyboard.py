"""The planner: a fake model stands in for the LLM, so repair and refusal are tested for free."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))
import plan_storyboard as P  # noqa: E402
from workflow import storyboard as sb  # noqa: E402

CATALOG = sb.load_catalog()
BEATS = [{"name": "a", "text": "Silicon die.", "seconds": 9}, {"name": "b", "text": "Many cores.", "seconds": 8}]
GOOD = {"beats": {"a": {"scene": "wafer", "labels": [{"text": "Die", "anchor": "die", "at": "word:die"}]},
                  "b": {"scene": "cores-compare"}}}


def scripted(*answers):
    seen = []

    def ask(prompt):
        seen.append(prompt)
        return answers[min(len(seen), len(answers)) - 1]
    ask.prompts = seen
    return ask


class Planner(unittest.TestCase):
    def test_beats_come_from_the_episode(self):
        beats = P.beats_of(ROOT / "work" / "jensen-huang")
        self.assertEqual([b["name"] for b in beats][:2], ["denny-den", "valuation"])
        self.assertIn("Denny", beats[0]["text"])

    def test_a_valid_answer_is_accepted_even_inside_a_code_fence(self):
        board, errors = P.plan(BEATS, CATALOG, scripted("Here you go:\n```json\n" + json.dumps(GOOD) + "\n```"))
        self.assertEqual(errors, [])
        self.assertEqual(board, GOOD)

    def test_an_invalid_answer_is_sent_back_with_its_errors_and_repaired(self):
        bad = {"beats": {"a": {"scene": "wafer", "labels": [{"text": "Die", "anchor": "nope"}]},
                         "b": {"scene": "cores-compare"}}}
        ask = scripted(json.dumps(bad), json.dumps(GOOD))
        board, errors = P.plan(BEATS, CATALOG, ask)
        self.assertEqual((board, errors), (GOOD, []))
        self.assertIn("unknown anchor 'nope'", ask.prompts[1])

    def test_a_planner_that_never_gets_it_right_returns_the_errors(self):
        board, errors = P.plan(BEATS, CATALOG, scripted("not json at all"), repairs=2)
        self.assertIsNone(board)
        self.assertTrue(errors)

    def test_missing_and_extra_beats_and_too_many_labels_are_errors(self):
        board = {"beats": {"a": {"scene": "wafer", "labels": [{"text": str(i), "anchor": "die"} for i in range(6)]},
                           "zzz": {"scene": "wafer"}}}
        errors = "\n".join(P.problems(board, BEATS, CATALOG))
        self.assertIn("beat 'b' has no entry", errors)
        self.assertIn("'zzz' is not a 3D beat", errors)
        self.assertIn("at most", errors)

    def test_jensen_storyboard_passes_the_planner_check(self):
        board = json.loads((ROOT / "work" / "jensen-huang" / "storyboard.json").read_text(encoding="utf-8"))
        self.assertEqual(P.problems(board, P.beats_of(ROOT / "work" / "jensen-huang"), CATALOG), [])

    def test_a_rejected_plan_never_replaces_storyboard_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = Path(tmp)
            for name in ("shots.json", "shot_lengths.json"):
                (ep / name).write_text((ROOT / "work" / "jensen-huang" / name).read_text(encoding="utf-8"), encoding="utf-8")
            (ep / "vo").mkdir()
            (ep / "vo" / "manifest.json").write_text(
                (ROOT / "work" / "jensen-huang" / "vo" / "manifest.json").read_text(encoding="utf-8"), encoding="utf-8")
            (ep / "storyboard.json").write_text('{"keep": "me"}', encoding="utf-8")
            code = P.main(["--episode", str(ep), "--ask-cmd", f'"{sys.executable}" -c "print(\'{{}}\')"', "--repairs", "0"])
            self.assertEqual(code, 1)
            self.assertEqual(json.loads((ep / "storyboard.json").read_text(encoding="utf-8")), {"keep": "me"})
            self.assertTrue((ep / "storyboard-rejected.json").exists())

    def test_the_brief_names_every_scene_and_beat(self):
        prompt = P.build_prompt(BEATS, CATALOG)
        for scene in CATALOG:
            self.assertIn(scene, prompt)
        self.assertIn("a (9 s): Silicon die.", prompt)


class BuilderGate(unittest.TestCase):
    def test_blender_refuses_an_invalid_storyboard_before_building_anything(self):
        from workflow.config import blender_executable
        with tempfile.TemporaryDirectory() as tmp:
            ep = Path(tmp)
            (ep / "shot_lengths.json").write_text('{"a": 6}', encoding="utf-8")
            (ep / "storyboard.json").write_text('{"beats": {"a": {"scene": "nope"}}}', encoding="utf-8")
            run = subprocess.run([str(blender_executable(ROOT)), "-b", "--factory-startup", "--python-exit-code", "3",
                                  "-P", str(ROOT / "tools" / "blender" / "storyboard_beats.py"), "--",
                                  "--episode", str(ep), "--out", str(ep / "out")],
                                 capture_output=True, text=True)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn("refused before any scene was built", run.stdout + run.stderr)
            self.assertNotIn("SyntaxError", run.stdout + run.stderr)
            self.assertIn("unknown scene", run.stdout + run.stderr)
            self.assertFalse(list((ep / "out").glob("*")) if (ep / "out").exists() else [])


if __name__ == "__main__":
    unittest.main()
