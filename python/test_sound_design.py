"""Sound design: events read off the storyboard, levels from the contract, the reversal drop."""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))
import music_bed  # noqa: E402
import sound_design as S  # noqa: E402


def tiny_episode(tmp, board, story=None):
    ep = Path(tmp)
    (ep / "vo").mkdir()
    rate = 1000
    lines = [("u001", "a", "3d", 0, 10), ("u002", "a", "3d", 10, 20), ("u003", "arch", "archive", 20, 25),
             ("u004", "b", "3d", 25, 40)]
    manifest = {"sampleRate": rate, "utterances": [
        {"id": u, "file": f"{u}.wav", "startSample": a * rate, "endSample": b * rate} for u, _, _, a, b in lines]}
    (ep / "vo" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (ep / "shots.json").write_text(json.dumps({u: {"name": n, "kind": k} for u, n, k, _, _ in lines}), encoding="utf-8")
    (ep / "storyboard.json").write_text(json.dumps({"beats": board}), encoding="utf-8")
    (ep / "shot_lengths.json").write_text(json.dumps({"a": 20, "arch": 5, "b": 15}), encoding="utf-8")
    if story:
        (ep / "script").mkdir()
        (ep / "script" / "story.json").write_text(json.dumps(story), encoding="utf-8")
    return ep


class Events(unittest.TestCase):
    def test_the_builder_and_the_sound_share_one_shot_timing(self):
        """Both plan shots with workflow/storyboard.py; neither keeps a copy of the rules."""
        for path in (ROOT / "tools" / "blender" / "storyboard_beats.py", ROOT / "tools" / "sound_design.py"):
            src = path.read_text(encoding="utf-8")
            self.assertIn("timing.default_shots", src, path.name)
            self.assertNotRegex(src, r"(?m)^def default_shots|^TRAVEL_SECONDS|^MONTAGE_LENGTHS", path.name)

    def test_shots_cuts_moves_actions_rooms_and_the_reversal(self):
        board = {"a": {"scene": "server-racks", "shots": [{"view": "at:x", "start": 0.0}, {"view": "at:y", "start": 1.2},
                                                           {"view": "wide", "to": "drawer", "start": 3.1}],
                       "actions": [{"name": "open", "at": 0.5}]},
                 "b": {"scene": "heat-loop", "cut": "montage"}}
        with tempfile.TemporaryDirectory() as tmp:
            ev = S.plan_events(tiny_episode(tmp, board, {"reversal": "u004"}))
        kinds = dict((round(t, 2), k) for t, k in ev["cuts"])
        self.assertEqual(kinds[1.2], "hit")
        self.assertEqual(kinds[3.1], "hit")
        self.assertEqual(kinds[20.0], "thud")                 # into archive
        self.assertEqual(kinds[25.0], "thud")                 # and out of it
        self.assertEqual(ev["travels"], [(3.1, 20.0)])
        self.assertEqual(ev["actions"], [10.0])               # 0.5 of the 20 s render
        self.assertEqual([r for _, _, r in ev["rooms"]], ["hum", "room", "flow"])
        self.assertEqual(ev["reversal"], 25.0)
        self.assertGreaterEqual(sum(k == "hit" and t > 25 for t, k in ev["cuts"]), 6)   # montage cuts in b

    def test_the_track_is_reproducible_and_bounded(self):
        board = {"a": {"scene": "fiber-trip"}, "b": {"scene": "document"}}
        with tempfile.TemporaryDirectory() as tmp:
            ev = S.plan_events(tiny_episode(tmp, board, {"reversal": "u002"}))
        one = S.design_track(8000, 40 * 8000, ev, 0.08)
        two = S.design_track(8000, 40 * 8000, ev, 0.08)
        self.assertTrue(np.array_equal(one, two))
        self.assertLess(float(np.abs(one).max()), 0.5)
        self.assertEqual(S.music_drops(ev), [(8.6, 10.0 + S.rules()["reversal_music_drop_seconds"])])

    def test_reverb_keeps_the_dry_hit_and_adds_a_decaying_tail(self):
        rate, cfg = 8000, {"rt60_s": 0.5, "predelay_ms": 10, "wet": 0.4}
        x = np.zeros(rate * 2)
        x[1000] = 1.0
        y = S.reverb(x, rate, cfg)
        self.assertAlmostEqual(float(y[1000]), 1.0, places=6)            # the hit itself is untouched
        early = np.abs(y[1100:1600]).max()
        late = np.abs(y[4000:4500]).max()
        self.assertGreater(early, 0.0)
        self.assertLess(late, early * 0.2)                                # and the room dies away
        self.assertTrue(np.array_equal(y, S.reverb(x, rate, cfg)))

    def test_the_bed_falls_silent_over_a_drop_and_comes_back(self):
        bed = np.ones((10 * 100, 2))
        out = music_bed.apply_drops(bed, [(4.0, 6.0)], 100)
        self.assertEqual(float(out[450, 0]), 0.0)
        self.assertEqual(float(out[300, 0]), 1.0)
        self.assertEqual(float(out[999, 0]), 1.0)
        self.assertTrue(0.0 < float(out[650, 0]) < 1.0)    # easing back in


if __name__ == "__main__":
    unittest.main()
