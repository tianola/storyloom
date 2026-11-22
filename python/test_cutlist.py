"""The cut list: one film clock, anchors on words, frame-exact shots and transitions.

These pin the timing schema the v6 directing pass was approved on (§10 of the plan): every time is
rounded once on the film clock, a cut on a word leads the word by two frames, a transition is
centred on its cut and needs material on both sides, an overlay lives inside its shot, and an
archival shot's screen time — half of each transition included — never passes the contract bound.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))
from edit import cutlist as C  # noqa: E402
from workflow.config import style_contract  # noqa: E402

CONTRACT = style_contract(ROOT)
FPS = 30


def line(uid, start, end, words=()):
    """A line on the film clock; `words` are (word, start, end) relative to the line."""
    return {"id": uid, "start": start, "end": end,
            "words": [{"w": w, "s": start + s, "e": start + e} for w, s, e in words]}


LINES = [
    line("u001", 0.0, 4.0, [("It's", 0.1, 0.4), ("the", 0.5, 0.6), ("door", 0.7, 1.0),
                            ("and", 1.5, 1.7), ("the", 2.0, 2.1), ("bell", 2.2, 2.6)]),
    line("u002", 4.0, 9.5, [("Bad", 0.2, 0.5), ("air.", 0.6, 1.0)]),
]
BY_ID = {l["id"]: l for l in LINES}


def shot(anchor, kind="3d", name="beat-a", **kw):
    s = {"start_anchor": anchor, "source": {"kind": kind, "name": name}, "provenance": "reconstruction"}
    s.update(kw)
    return s


def authored(shots, tail=0.0):
    return {"schema": "cutlist/1", "fps": FPS, "lead_frames": 2, "tail": tail, "shots": shots}


class Anchors(unittest.TestCase):
    def test_a_word_anchor_leads_its_word_by_two_frames(self):
        t = C.resolve_anchor("word:door@u001", BY_ID, fps=FPS, lead_frames=2)
        self.assertAlmostEqual(t, 0.7 - 2 / FPS, places=6)

    def test_the_nth_match_and_the_end_of_a_word(self):
        self.assertAlmostEqual(C.resolve_anchor("word:the@u001#2", BY_ID, fps=FPS, lead_frames=2),
                               2.0 - 2 / FPS, places=6)
        self.assertAlmostEqual(C.resolve_anchor("word:bell@u001:end", BY_ID, fps=FPS, lead_frames=2),
                               2.6, places=6)

    def test_line_anchors_and_plain_seconds(self):
        self.assertEqual(C.resolve_anchor("line:u002", BY_ID, fps=FPS, lead_frames=2), 4.0)
        self.assertEqual(C.resolve_anchor("line:u002:end", BY_ID, fps=FPS, lead_frames=2), 9.5)
        self.assertEqual(C.resolve_anchor(3.25, BY_ID, fps=FPS, lead_frames=2), 3.25)

    def test_punctuation_and_case_do_not_hide_a_word(self):
        self.assertAlmostEqual(C.resolve_anchor("word:AIR@u002", BY_ID, fps=FPS, lead_frames=2),
                               4.6 - 2 / FPS, places=6)

    def test_a_lead_never_reaches_back_into_the_previous_line(self):
        self.assertEqual(C.resolve_anchor("word:It's@u001", BY_ID, fps=FPS, lead_frames=5), 0.0)

    def test_a_missing_word_is_an_error_not_a_guess(self):
        with self.assertRaisesRegex(ValueError, "window.*u001"):
            C.resolve_anchor("word:window@u001", BY_ID, fps=FPS, lead_frames=2)
        with self.assertRaisesRegex(ValueError, "u009"):
            C.resolve_anchor("line:u009", BY_ID, fps=FPS, lead_frames=2)

    def test_words_from_an_elevenlabs_alignment_skip_bracketed_directions(self):
        chars = list("[sad] Bad air.")
        t = [i * 0.1 for i in range(len(chars))]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "u.align.json"
            p.write_text(json.dumps({"alignment": {
                "characters": chars, "character_start_times_seconds": t,
                "character_end_times_seconds": [x + 0.1 for x in t]}}), encoding="utf-8")
            words = C.words_from_alignment(p)
        self.assertEqual([w for w, _, _ in words], ["Bad", "air."])
        self.assertAlmostEqual(words[0][1], 0.6)


class Resolve(unittest.TestCase):
    def test_shots_tile_the_film_on_whole_frames(self):
        cut = C.resolve(authored([shot("line:u001"), shot("word:door@u001"),
                                  shot("line:u002", name="beat-b")], tail=1.0), LINES)
        starts = [s["start"] for s in cut["shots"]]
        ends = [s["end"] for s in cut["shots"]]
        self.assertEqual(starts[0], 0.0)
        self.assertEqual(starts[1:], ends[:-1])
        self.assertAlmostEqual(ends[-1], 10.5)
        for t in starts + ends:
            self.assertAlmostEqual(t * FPS, round(t * FPS), places=6)

    def test_contiguous_shots_on_one_beat_take_consecutive_slices(self):
        cut = C.resolve(authored([shot("line:u001"), shot("word:door@u001"),
                                  shot("line:u002", name="beat-b")]), LINES)
        a, b, c = cut["shots"]
        self.assertEqual(a["source"]["in"], 0.0)
        self.assertAlmostEqual(b["source"]["in"], b["start"] - a["start"])
        self.assertEqual(c["source"]["in"], 0.0)
        self.assertAlmostEqual(a["source"]["out"], a["end"] - a["start"])

    def test_an_explicit_in_point_wins(self):
        cut = C.resolve(authored([shot("line:u001", source={"kind": "3d", "name": "x", "in": 2.0})]), LINES)
        self.assertEqual(cut["shots"][0]["source"]["in"], 2.0)

    def test_shots_out_of_time_order_are_refused(self):
        with self.assertRaisesRegex(ValueError, "order"):
            C.resolve(authored([shot("line:u002"), shot("line:u001")]), LINES)

    def test_overlays_are_placed_on_the_shot_clock(self):
        cut = C.resolve(authored([shot("line:u001", overlays=[
            {"graphic": "tally", "at": 0.5, "until": 2.0, "provenance": "graphic-data"},
            {"graphic": "label", "at": 1.0, "provenance": "graphic-schematic"}]),
            shot("line:u002")]), LINES)
        o1, o2 = cut["shots"][0]["overlays"]
        self.assertAlmostEqual(o1["start"], 0.5)
        self.assertAlmostEqual(o1["end"], 2.0)
        self.assertAlmostEqual(o2["end"], cut["shots"][0]["end"])

    def test_lines_each_shot_plays_over_are_recorded(self):
        cut = C.resolve(authored([shot("line:u001"), shot("word:bell@u001"), shot("word:air@u002")]), LINES)
        self.assertEqual(cut["shots"][1]["lines"], ["u001", "u002"])

    def test_ten_minutes_of_odd_lengths_keep_zero_drift(self):
        lines, t = [], 0.0
        for i in range(200):
            d = 2.0 + (i * 0.0137) % 1.0 + 1 / 7.0      # never a whole number of frames
            lines.append(line(f"u{i + 1:03d}", t, t + d))
            t += d
        cut = C.resolve(authored([shot(f"line:{l['id']}", name=f"b{i % 3}")
                                  for i, l in enumerate(lines)]), lines)
        plan = C.render_plan(cut)
        self.assertEqual(sum(p["frames"][1] - p["frames"][0] for p in plan), round(t * FPS))
        for s, l in zip(cut["shots"], lines):
            self.assertLessEqual(abs(s["start"] - l["start"]), 0.5 / FPS + 1e-9)


class Validate(unittest.TestCase):
    def resolved(self, shots, tail=0.0):
        return C.resolve(authored(shots, tail=tail), LINES)

    def codes(self, cut, **kw):
        return {f["code"] for f in C.validate(cut, CONTRACT, **kw)}

    def test_a_clean_cut_has_no_findings(self):
        self.assertEqual(self.codes(self.resolved([shot("line:u001"), shot("line:u002")])), set())

    def test_gaps_and_overlaps_are_refused(self):
        cut = self.resolved([shot("line:u001"), shot("line:u002")])
        cut["shots"][0]["end"] = 3.9
        self.assertIn("gap", self.codes(cut))
        cut["shots"][0]["end"] = 4.1
        self.assertIn("overlap", self.codes(cut))

    def test_off_frame_times_and_one_frame_shots_are_refused(self):
        cut = self.resolved([shot("line:u001"), shot("line:u002")])
        cut["shots"][0]["end"] = cut["shots"][1]["start"] = 4.01
        self.assertIn("off_frame", self.codes(cut))
        cut = self.resolved([shot("line:u001"), shot(4.0 - 1 / FPS), shot("line:u002")])
        self.assertIn("too_short", self.codes(cut))

    def test_transition_durations_are_bounded_by_type(self):
        for kind, dur, ok in (("dissolve", 0.3, True), ("dissolve", 1.5, False), ("dip", 0.8, True),
                              ("dip", 0.1, False), ("match", 0.3, True), ("match", 0.5, False),
                              ("cut", 0.2, False), ("wipe", 0.3, False)):
            cut = self.resolved([shot("line:u001"), shot("line:u002", name="b",
                                                         transition_in={"type": kind, "dur": dur})])
            self.assertEqual("transition" not in self.codes(cut), ok, (kind, dur))

    def test_an_overlay_outside_its_shot_is_refused(self):
        cut = self.resolved([shot("line:u001", overlays=[{"graphic": "tally", "at": 3.0, "until": 5.0,
                                                          "provenance": "graphic-data"}]),
                             shot("line:u002")])
        self.assertIn("overlay_outside", self.codes(cut))

    def test_archive_six_seconds_passes_and_six_point_one_fails(self):
        bound = CONTRACT["archive"]["archive_rhythm"]["max_archival_shot_seconds"]
        self.assertEqual(bound, 6.0)
        ok = self.resolved([shot("line:u001"), shot(2.0, kind="archive", name="a"), shot(8.0)], tail=2.0)
        self.assertNotIn("archive_long", self.codes(ok))
        bad = self.resolved([shot("line:u001"), shot(2.0, kind="archive", name="a"), shot(8.1)], tail=2.0)
        self.assertIn("archive_long", self.codes(bad))

    def test_archive_screen_time_counts_half_of_each_transition(self):
        # 5.8 s between the cuts, a 0.6 s dissolve each side: 0.3 + 5.8 + 0.3 would be 6.4 s if the
        # windows were added on; centred on the cuts they are already inside the 5.8 s.
        cut = self.resolved([shot("line:u001"),
                             shot(2.0, kind="archive", name="a", transition_in={"type": "dissolve", "dur": 0.6}),
                             shot(7.8, name="b", transition_in={"type": "dissolve", "dur": 0.6})], tail=2.0)
        self.assertNotIn("archive_long", self.codes(cut))
        self.assertAlmostEqual(C.screen_seconds(cut["shots"][1]), 5.8)

    def test_archive_is_never_retimed(self):
        cut = self.resolved([shot("line:u001", kind="archive", name="a", speed=1.5), shot("line:u002")])
        self.assertIn("archive_speed", self.codes(cut))

    def test_every_shot_carries_provenance(self):
        s = shot("line:u001")
        del s["provenance"]
        self.assertIn("provenance", self.codes(self.resolved([s, shot("line:u002")])))

    def test_a_transition_needs_material_in_a_fixed_length_source(self):
        cut = self.resolved([shot("line:u001", kind="archive", name="a"),
                             shot("line:u002", name="b", transition_in={"type": "dissolve", "dur": 0.6})])
        self.assertIn("handle", self.codes(cut, source_seconds={"a": 4.0, "b": 30.0}))
        self.assertNotIn("handle", self.codes(cut, source_seconds={"a": 4.3, "b": 30.0}))

    def test_a_transition_cannot_eat_a_whole_shot(self):
        cut = self.resolved([shot("line:u001"), shot(4.0 - 4 / FPS, name="b",
                                                     transition_in={"type": "dissolve", "dur": 0.3}),
                             shot("line:u002", name="c", transition_in={"type": "dissolve", "dur": 0.3})])
        self.assertIn("transition_overlap", self.codes(cut))


class RenderPlan(unittest.TestCase):
    def cut(self, tr):
        return C.resolve(authored([shot("line:u001", name="a"),
                                   shot("line:u002", name="b", transition_in=tr)], tail=0.5), LINES)

    def test_a_dissolve_is_one_piece_centred_on_its_cut(self):
        plan = C.render_plan(self.cut({"type": "dissolve", "dur": 0.3}))
        self.assertEqual([p["kind"] for p in plan], ["segment", "transition", "segment"])
        seg_a, tr, seg_b = plan
        self.assertEqual(tr["frames"], (120 - 4, 120 + 5))
        self.assertEqual(seg_a["frames"], (0, 116))
        self.assertEqual(seg_b["frames"], (125, 300))
        self.assertEqual(tr["type"], "dissolve")

    def test_pieces_abut_and_cover_the_film(self):
        plan = C.render_plan(self.cut({"type": "dip", "dur": 0.8}))
        for p, q in zip(plan, plan[1:]):
            self.assertEqual(p["frames"][1], q["frames"][0])
        self.assertEqual(plan[0]["frames"][0], 0)
        self.assertEqual(plan[-1]["frames"][1], 300)

    def test_both_sides_of_a_transition_read_their_own_source_clock(self):
        tr = C.render_plan(self.cut({"type": "dissolve", "dur": 0.3}))[1]
        self.assertAlmostEqual(tr["out"]["seek"], 116 / FPS)          # beat a at its own 3.87 s
        self.assertAlmostEqual(tr["in"]["seek"], 0.0)                 # beat b from its first frame
        self.assertEqual(tr["out"]["name"], "a")
        self.assertEqual(tr["in"]["name"], "b")

    def test_the_incoming_source_is_given_a_head_for_its_half_of_the_window(self):
        cut = self.cut({"type": "dissolve", "dur": 0.3})
        b = cut["shots"][1]
        self.assertAlmostEqual(b["source"]["in"], 4 / FPS)            # head of 4 frames
        seg_b = C.render_plan(cut)[2]
        self.assertAlmostEqual(seg_b["seek"], 9 / FPS)

    def test_source_lengths_include_heads_and_tails(self):
        lengths = C.source_seconds_needed(self.cut({"type": "dissolve", "dur": 0.3}))
        self.assertAlmostEqual(lengths["a"], 125 / FPS)               # runs 5 frames past its cut
        self.assertAlmostEqual(lengths["b"], 4 / FPS + 6.0)           # head + its 6.0 s

    def test_cuts_on_words_land_two_frames_before_the_word(self):
        cut = C.resolve(authored([shot("line:u001"), shot("word:door@u001"),
                                  shot("word:bell@u001"), shot("word:air@u002")]), LINES)
        plan = C.render_plan(cut)
        words = [0.7, 2.2, 4.6]
        for p, w in zip(plan[1:], words):
            self.assertLessEqual(abs(round(w * FPS) - p["frames"][0] - 2), 1)

    def test_a_j_cut_sound_is_scheduled_ahead_of_its_picture(self):
        cut = C.resolve(authored([shot("line:u001"),
                                  shot("line:u002", audio={"j_cut": {"sfx": "bell", "lead": 0.8}})]), LINES)
        self.assertEqual(C.audio_events(cut), [{"sfx": "bell", "at": 3.2, "shot": "s02", "kind": "j_cut"}])

    def test_an_l_cut_sound_runs_on_past_its_picture(self):
        cut = C.resolve(authored([shot("line:u001", audio={"l_cut": {"sfx": "bell", "lag": 0.5}}),
                                  shot("line:u002")]), LINES)
        self.assertEqual(C.audio_events(cut), [{"sfx": "bell", "at": 0.0, "until": 4.5, "shot": "s01",
                                                "kind": "l_cut"}])

    def test_the_source_card_holds_for_its_seconds_or_the_whole_shot(self):
        cut = C.resolve(authored([shot("line:u001", kind="archive", name="a"),
                                  shot(5.0, kind="archive", name="c"), shot(7.0)]), LINES)
        self.assertEqual(C.card_hold(cut["shots"][0], CONTRACT), 3.0)
        self.assertAlmostEqual(C.card_hold(cut["shots"][1], CONTRACT), 2.0)


class Beats(unittest.TestCase):
    def test_storyboard_shot_times_come_from_the_cut(self):
        cut = C.resolve(authored([
            shot("line:u001", source={"kind": "3d", "name": "beat-a", "view": "door"}),
            shot("word:bell@u001", source={"kind": "3d", "name": "beat-a", "view": "bell", "move": "push"}),
            shot("line:u002", source={"kind": "3d", "name": "beat-b", "view": "court", "to": "doors"},
                 transition_in={"type": "dip", "dur": 0.6})]), LINES)
        beats = C.beat_shots(cut)
        self.assertEqual([s["view"] for s in beats["beat-a"]], ["door", "bell"])
        self.assertEqual(beats["beat-a"][0]["start"], 0.0)
        self.assertAlmostEqual(beats["beat-a"][1]["start"], cut["shots"][1]["source"]["in"])
        self.assertEqual(beats["beat-a"][1]["move"], "push")
        self.assertEqual(beats["beat-b"], [{"view": "court", "start": 0.0, "to": "doors"}])
        self.assertAlmostEqual(cut["shots"][2]["source"]["in"], 9 / FPS)   # the dip's head


class HeldMove(unittest.TestCase):
    def test_a_held_move_travels_through_its_waypoints_on_their_words(self):
        cut = C.resolve(authored([
            shot("line:u001", source={"kind": "3d", "name": "wing", "view": "table",
                                      "via": [{"view": "door", "at": "word:door@u001"},
                                              {"view": "bed", "at": "word:bell@u001"}],
                                      "at_params": {"walk_from": "word:door@u001"}}),
            shot("line:u002", name="b")]), LINES)
        beats = C.beat_shots(cut)
        self.assertEqual([(e["view"], e.get("to"), e.get("move")) for e in beats["wing"]],
                         [("table", "door", None), ("door", "bed", None), ("bed", None, "push")])
        self.assertAlmostEqual(beats["wing"][1]["start"], C.snap(0.7 - 2 / FPS, FPS))
        self.assertAlmostEqual(C.beat_params(cut)["wing"]["walk_from"], C.snap(0.7 - 2 / FPS, FPS))

    def test_waypoints_out_of_order_are_refused(self):
        with self.assertRaisesRegex(ValueError, "waypoints"):
            C.resolve(authored([shot("line:u001", source={"kind": "3d", "name": "w", "view": "a",
                                                          "via": [{"view": "b", "at": "word:bell@u001"},
                                                                  {"view": "c", "at": "word:door@u001"}]}),
                                shot("line:u002")]), LINES)


if __name__ == "__main__":
    unittest.main()
