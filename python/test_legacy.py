"""Older episodes keep their cut: `shots.json` read as a cut list lands on today's frames.

`legacy.from_shots` is how tools that read shots (the gate, the report, the v6 assembler) see an
episode cut before cut lists existed. These compare it against the arithmetic `build_segments`
actually runs, on real episodes in this repository, so the adapter cannot drift from the cutter.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))
from edit import cutlist as C, legacy as L  # noqa: E402
from workflow.config import style_contract  # noqa: E402
from workflow.episode import shots  # noqa: E402

CONTRACT = style_contract(ROOT)
FPS = CONTRACT["canvas"]["fps"]
EPISODES = ["semmelweis-pilot", "ask-chatgpt", "jensen-huang"]


def build_segments_arithmetic(manifest, shot_map):
    """What `assemble_episode.build_segments` computes per utterance: frames and seek."""
    rate = int(manifest["sampleRate"])
    consumed, clock, out = {}, 0, []
    for u in manifest["utterances"]:
        kind, name = shot_map[u["id"]][:2]
        begin = u.get("startSample", clock)
        clock = u.get("endSample", begin + u["samples"])
        frames = round(clock / rate * FPS) - round(begin / rate * FPS)
        key = f"card-{u['id']}" if kind == "cards" else f"{kind}/{name}"
        start = consumed.get(key, 0.0)
        consumed[key] = start + u["samples"] / rate
        out.append((u["id"], frames, start))
    return out


class Legacy(unittest.TestCase):
    def episode(self, slug):
        ep = ROOT / "work" / slug
        if not (ep / "shots.json").is_file():
            self.skipTest(f"{slug} is not in this checkout")
        # semmelweis-pilot is cut from cut.json since v6; its v5 voice and shots.json are the legacy pair
        vo = ep / "v5-backup" / "vo" if (ep / "cut.json").is_file() else ep / "vo"
        manifest = json.loads((vo / "manifest.json").read_text(encoding="utf-8"))
        table = json.loads((ep / "shots.json").read_text(encoding="utf-8"))
        return ep, manifest, {uid: (r["kind"], r["name"]) for uid, r in table.items()}

    def test_segment_boundaries_equal_build_segments_to_the_frame(self):
        for slug in EPISODES:
            with self.subTest(slug):
                ep, manifest, shot_map = self.episode(slug)
                cut = L.from_shots(shot_map, manifest, fps=FPS)
                plan = C.render_plan(cut)
                expected = build_segments_arithmetic(manifest, shot_map)
                self.assertEqual(len(plan), len(expected))
                for piece, (uid, frames, seek) in zip(plan, expected):
                    self.assertEqual(piece["kind"], "segment")
                    self.assertEqual(piece["shot"], uid)
                    self.assertEqual(piece["frames"][1] - piece["frames"][0], frames, uid)
                    self.assertLessEqual(abs(piece["seek"] - seek), 0.5 / FPS + 1e-9, uid)

    def test_every_legacy_transition_is_a_cut_and_the_film_has_no_gaps(self):
        ep, manifest, shot_map = self.episode("semmelweis-pilot")
        cut = L.from_shots(shot_map, manifest, fps=FPS)
        self.assertTrue(all(s["transition_in"]["type"] == "cut" for s in cut["shots"]))
        codes = {f["code"] for f in C.validate(cut, CONTRACT)}
        self.assertFalse(codes & {"gap", "overlap", "transition", "overlay_outside"}, codes)

    def test_per_utterance_cards_each_start_at_zero(self):
        manifest = {"sampleRate": 24000, "utterances": [
            {"id": "u001", "samples": 48000}, {"id": "u002", "samples": 24000},
            {"id": "u003", "samples": 24000}]}
        shot_map = {"u001": ("cards", "bar-chart"), "u002": ("cards", "bar-chart"),
                    "u003": ("3d", "beat-01")}
        cut = L.from_shots(shot_map, manifest, fps=30)
        self.assertEqual([s["source"]["name"] for s in cut["shots"]], ["card-u001", "card-u002", "beat-01"])
        self.assertEqual([s["source"]["in"] for s in cut["shots"]], [0.0, 0.0, 0.0])
        self.assertEqual([s["end"] for s in cut["shots"]], [2.0, 3.0, 4.0])

    def test_lines_on_one_beat_take_consecutive_slices(self):
        manifest = {"sampleRate": 24000, "utterances": [
            {"id": "u001", "samples": 36000}, {"id": "u002", "samples": 12000},
            {"id": "u003", "samples": 24000}]}
        shot_map = {"u001": ("3d", "beat-01"), "u002": ("archive", "a"), "u003": ("3d", "beat-01")}
        cut = L.from_shots(shot_map, manifest, fps=30)
        self.assertEqual([s["source"]["in"] for s in cut["shots"]], [0.0, 0.0, 1.5])

    def test_an_episode_without_a_cut_list_is_assembled_the_old_way(self):
        import assemble_episode as A
        self.assertEqual(A.edit_mode(ROOT / "work" / "ask-chatgpt"), "legacy")


if __name__ == "__main__":
    unittest.main()
