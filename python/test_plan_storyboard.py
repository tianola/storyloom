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

    def test_a_failed_plan_returns_its_closest_attempt_and_survives_a_garbled_answer(self):
        beats = [{"name": "a", "seconds": 5.0, "text": "x"}, {"name": "b", "seconds": 5.0, "text": "y"}]
        good_a = {"beats": {"a": {}}}                         # one beat missing: one error at least
        worse = {"beats": {"zzz": {}}}                         # both missing and one extra
        prompts = []
        answers = iter([json.dumps(good_a), "sorry, here it is: {not json", json.dumps(worse)])

        def ask(prompt):
            prompts.append(prompt)
            return next(answers)
        board, errors = P.plan(beats, {}, ask, repairs=2)
        self.assertEqual(board, good_a)
        self.assertTrue(errors)
        self.assertIn('"a"', prompts[2].split("REJECTED:")[1])   # the garbled answer did not erase the board

    def test_missing_and_extra_beats_and_too_many_labels_are_errors(self):
        board = {"beats": {"a": {"scene": "wafer", "labels": [{"text": str(i), "anchor": "die"} for i in range(6)]},
                           "zzz": {"scene": "wafer"}}}
        errors = "\n".join(P.problems(board, BEATS, CATALOG))
        self.assertIn("beat 'b' has no entry", errors)
        self.assertIn("'zzz' is not a 3D beat", errors)
        self.assertIn("at most", errors)

    def test_jensen_storyboard_is_valid_but_reads_as_slides(self):
        """The regression fixture predates the story rules: every name in it is valid, and the shape
        check names what makes it a slide deck (text rate, no montage, no held moves)."""
        board = json.loads((ROOT / "work" / "jensen-huang" / "storyboard.json").read_text(encoding="utf-8"))
        beats = P.beats_of(ROOT / "work" / "jensen-huang")
        lengths = {b["name"]: b["seconds"] for b in beats}
        shape = P.shape_problems(board, lengths)
        self.assertEqual([e for e in P.problems(board, beats, CATALOG) if e not in shape], [])
        self.assertTrue(any("on-screen text" in e for e in shape), shape)

    def test_shape_rules_count_text_charts_and_cuts(self):
        lengths = {n: 60 for n in "abcd"}
        slides = {"beats": {n: {"scene": "bar-chart", "cut": "steady",
                                "labels": [{"text": "x", "anchor": "a"}] * 4} for n in "abcd"}}
        found = " ".join(P.shape_problems(slides, lengths))
        for expected in ("on-screen text", "chart beats", "montage", "continuous camera move"):
            self.assertIn(expected, found)
        story = {"beats": {"a": {"scene": "wafer", "cut": "montage"}, "b": {"scene": "wafer"},
                           "c": {"scene": "wafer", "labels": [{"text": "Die", "anchor": "die"}]}, "d": {"scene": "wafer"}}}
        self.assertEqual(P.shape_problems(story, lengths), [])

    def test_a_held_move_with_quick_cutaways_still_counts_as_travel(self):
        lengths = {n: 15 for n in "abcd"}
        cut_in = [{"view": "at:die", "start": 0.0}, {"view": "at:edge", "start": 1.5},
                  {"view": "wide", "to": "die", "start": 3.4}]           # 11.6 s of 15 is one move
        choppy = [{"view": "at:die", "start": 0.0}, {"view": "wide", "to": "die", "start": 7.0}]   # 8 s of 15
        board = {"beats": {"a": {"scene": "wafer", "cut": "montage"}, "b": {"scene": "wafer", "shots": cut_in},
                           "c": {"scene": "wafer", "shots": choppy}, "d": {"scene": "wafer", "shots": choppy}}}
        found = " ".join(P.shape_problems(board, lengths))
        self.assertIn("1 of 4 beats are one continuous camera move", found)
        board["beats"]["c"]["shots"] = cut_in
        self.assertEqual(P.shape_problems(board, lengths), [])

    def test_hand_cut_quick_shots_count_as_a_montage(self):
        lengths = {n: 15 for n in "abcd"}
        held = [{"view": "at:die", "start": 0.0}, {"view": "at:edge", "start": 1.5},
                {"view": "wide", "to": "die", "start": 3.4}]
        quick = [{"view": v, "start": t} for v, t in (("wide", 0.0), ("at:die", 2.0), ("at:edge", 3.4), ("wide", 5.6),
                                                     ("at:die", 7.0), ("at:edge", 9.4), ("wide", 11.0), ("at:die", 13.2))]
        slow = [{"view": v, "start": t} for v, t in (("wide", 0.0), ("at:die", 4.0), ("at:edge", 8.0), ("wide", 12.0))]
        board = {"beats": {"a": {"scene": "wafer", "shots": quick}, "b": {"scene": "wafer", "shots": held},
                           "c": {"scene": "wafer", "shots": held}, "d": {"scene": "wafer"}}}
        self.assertEqual(P.shape_problems(board, lengths), [])
        board["beats"]["a"]["shots"] = slow                      # 4 s a shot is not a montage
        self.assertIn("montage", " ".join(P.shape_problems(board, lengths)))

    def test_archive_share_is_checked_at_planning_time(self):
        contract = json.loads((ROOT / "workflow" / "style.json").read_text(encoding="utf-8"))
        contract["archive"]["episode_profile"]["mix"]["min_share"]["archive"] = 0.20   # shipped floor is 0
        found = P.archive_mix(ROOT / "work" / "jensen-huang", contract)   # the fixture is short of archive
        self.assertEqual([code for code, _ in found], ["archive_share_low"])

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
        from toolchain import require_blender
        require_blender()
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
