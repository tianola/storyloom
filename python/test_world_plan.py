"""The living town's schedule (tools/blender/models/world_plan.py, no Blender) and the storyboard
keys acting people take (workflow/storyboard.py)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "blender" / "models"))
sys.path.insert(0, str(ROOT))
import world_plan as W  # noqa: E402
from workflow import storyboard as S  # noqa: E402


class WindowLives(unittest.TestCase):
    KEYS = [(h, s) for h in range(60) for s in range(3)]

    def test_seeded_and_share(self):
        a = W.window_lives(self.KEYS, 20.0, 5)
        self.assertEqual(a, W.window_lives(self.KEYS, 20.0, 5))
        self.assertNotEqual(a, W.window_lives(self.KEYS, 20.0, 6))
        self.assertTrue(0.08 * len(self.KEYS) < len(a) < 0.27 * len(self.KEYS), len(a))

    def test_crossings_are_ordered_and_in_the_beat(self):
        for legs in W.window_lives(self.KEYS, 20.0, 2, share=1.0).values():
            self.assertIn(len(legs), (1, 2))
            for t0, t1, d in legs:
                self.assertTrue(0.0 <= t0 < t1 <= 20.0 and d in (-1, 1))
            for (a0, a1, _), (b0, b1, _) in zip(legs, legs[1:]):
                self.assertLessEqual(a1, b0)

    def test_only_while_lit(self):
        sched = W.window_schedule(self.KEYS, 20.0, share=0.6, seed=1)
        lives = W.window_lives(self.KEYS, 20.0, 1, share=1.0, schedule=sched)
        self.assertTrue(lives)
        for k, legs in lives.items():
            on, off = sched[k]
            for t0, t1, _ in legs:
                self.assertTrue(on <= t0 and t1 <= (off or 20.0), (k, legs, sched[k]))


class Windows(unittest.TestCase):
    KEYS = [(h, s) for h in range(40) for s in range(3)]

    def test_seeded_and_within_the_beat(self):
        a = W.window_schedule(self.KEYS, 20.0, share=0.6, seed=3, start=0.1, end=0.5)
        self.assertEqual(a, W.window_schedule(self.KEYS, 20.0, share=0.6, seed=3, start=0.1, end=0.5))
        self.assertNotEqual(a, W.window_schedule(self.KEYS, 20.0, share=0.6, seed=4, start=0.1, end=0.5))
        for on, off in a.values():
            self.assertTrue(on == 0.0 or 2.0 <= on <= 10.0, on)
            if off is not None:
                self.assertTrue(on < off <= 20.0)

    def test_share(self):
        n = len(W.window_schedule(self.KEYS, 20.0, share=0.5, seed=1))
        self.assertTrue(0.35 * len(self.KEYS) < n < 0.65 * len(self.KEYS), n)


class Lamps(unittest.TestCase):
    def test_in_order_along_the_street(self):
        xs = [12, -12, 0, 0, 24, 12, -12, 24]
        t = W.lamplighter_order(xs, 10.0, start=0.1, end=0.5)
        self.assertEqual(t, sorted(t))
        self.assertEqual((t[0], t[-1]), (1.0, 5.0))
        self.assertEqual(t[0], t[1])          # two lamps at one x light together


class Walkers(unittest.TestCase):
    def test_on_the_street_and_the_first_two_greet(self):
        people = W.street_people(20.0, seed=5, count=6)
        self.assertEqual(len(people), 6)
        for p in people:
            for path, t0, t1 in p["legs"]:
                self.assertTrue(0 <= t0 <= t1 <= 20.0)
                self.assertTrue(all(-4.0 < y < 4.0 for _, y, _ in path))
        a, b = people[0], people[1]
        self.assertIsNotNone(a["greet"])
        meet_a, meet_b = a["legs"][0][0][1], b["legs"][0][0][1]
        self.assertLess(abs(meet_a[0] - meet_b[0]), 1.5)


class Groups(unittest.TestCase):
    def test_turns_pass_and_stay_in_the_beat(self):
        turns = W.chatter(12.0, seed=2, people=2)
        self.assertGreater(len(turns), 4)
        self.assertTrue(all(0 <= t < 12.0 for t, _ in turns))
        self.assertTrue(all(a[1] != b[1] for a, b in zip(turns, turns[1:])))
        self.assertEqual(turns, W.chatter(12.0, seed=2, people=2))

    def test_groups_stand_by_the_houses_out_of_the_lanes(self):
        for g in W.street_groups(20.0, seed=4, count=4):
            self.assertIn(len(g["who"]), (2, 3))
            self.assertEqual(len(g["who"]), len(g["at"]))
            for x, y, _ in g["at"]:
                self.assertTrue(3.0 <= abs(y) < 4.0, y)

    def test_most_walkers_are_moving_from_the_first_frame(self):
        people = W.street_people(20.0, seed=5, count=12)
        starts = [p["legs"][0][1] for p in people[2:]]
        self.assertGreater(sum(1 for t in starts if t == 0.0), len(starts) / 2)


class ActingCast(unittest.TestCase):
    def beat(self, **cast):
        return {"beats": {"b": {"scene": "vienna", "shots": [{"view": "roofs"}],
                                "cast": [dict({"who": "semmelweis", "screen": [0.5, 1.0]}, **cast)]}}}

    def test_good_actor(self):
        self.assertEqual(S.validate(self.beat(speaker="semmelweis", bust=True, height=0.6, pose="talk",
                                              acts=[{"at": "word:So", "face": "worried"}]),
                                    cast={"semmelweis": {}}), [])

    def test_bad_pose_face_speaker_and_span(self):
        errors = S.validate(self.beat(pose="fly", face="bored", speaker="nobody", span=[0, 1], shot=0),
                            cast={"semmelweis": {}})
        text = " ".join(errors)
        for bit in ("pose 'fly'", "face 'bored'", "nobody", "either 'shot' or 'span'"):
            self.assertIn(bit, text)

    def test_small_speaker_is_advice(self):
        warnings = []
        S.validate(self.beat(speaker="semmelweis", height=0.1), cast={"semmelweis": {}}, warnings=warnings)
        self.assertTrue(warnings)

    def test_glide_needs_a_travel(self):
        board = {"beats": {"b": {"scene": "vienna", "shots": [{"view": "aerial", "glide": "log"}]}}}
        self.assertTrue(any("glide" in e for e in S.validate(board)))

    def test_plain_sprite_cannot_act(self):
        board = {"beats": {"b": {"scene": "vienna", "cast": [{"who": "token", "screen": [0.5, 0.9], "speaker": "x"}]}}}
        self.assertTrue(any("plain sprite" in e for e in S.validate(board)))


if __name__ == "__main__":
    unittest.main()
