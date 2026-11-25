"""Sound and the gate read a cut list: cuts, travels, the J-cut bell, and the timeline QC judges."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))
import audio_finish  # noqa: E402
import qc_episode  # noqa: E402
import sound_design  # noqa: E402


def shot(sid, start, end, kind, name, **src):
    return {"id": sid, "start": start, "end": end, "lines": src.pop("lines", ["u001"]),
            "source": {"kind": kind, "name": name, "in": src.pop("in", 0.0), **src},
            "transition_in": {"type": "cut", "dur": 0.0}, "overlays": [], "provenance": "reconstruction"}


CUT = {"schema": "cutlist/1", "fps": 30, "duration": 12.0, "shots": [
    shot("s01", 0.0, 3.0, "3d", "beat-a", view="door"),
    shot("s02", 3.0, 6.0, "3d", "beat-a", view="ward", to="bed", **{"in": 3.0}),
    shot("s03", 6.0, 9.0, "archive", "portrait", lines=["u001", "u002"]),
    shot("s04", 9.0, 12.0, "3d", "beat-b", view="court", lines=["u002"]),
]}
CUT["shots"][3]["audio"] = {"j_cut": {"sfx": "bell", "lead": 0.8}}


class CutSound(unittest.TestCase):
    def episode(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        ep = Path(d.name)
        (ep / "vo").mkdir()
        (ep / "vo" / "manifest.json").write_text(json.dumps({"sampleRate": 24000, "totalSamples": 264000,
            "utterances": [{"id": "u001", "samples": 168000, "startSample": 0, "endSample": 168000},
                           {"id": "u002", "samples": 96000, "startSample": 168000, "endSample": 264000}]}))
        (ep / "storyboard.json").write_text(json.dumps({"beats": {
            "beat-a": {"scene": "vienna", "actions": [{"at": 4.0}]}, "beat-b": {"scene": "vienna"}}}))
        (ep / "cut.json").write_text("{}")
        (ep / "cut.resolved.json").write_text(json.dumps(CUT))
        return ep

    def test_every_shot_change_is_a_cut_of_the_right_kind(self):
        ev = sound_design.plan_events(self.episode())
        self.assertEqual(ev["cuts"], [(3.0, "hit"), (6.0, "thud"), (9.0, "thud")])

    def test_a_travelling_shot_and_the_actions_land_on_the_film_clock(self):
        ev = sound_design.plan_events(self.episode())
        self.assertEqual(ev["travels"], [(3.0, 6.0)])
        self.assertEqual(ev["actions"], [4.0])
        self.assertEqual([r[:2] for r in ev["rooms"]], [(0.0, 6.0), (6.0, 9.0), (9.0, 12.0)])

    def test_the_j_cut_bell_is_heard_before_its_shot(self):
        ev = sound_design.plan_events(self.episode())
        self.assertEqual(ev["sfx"], [(8.2, "bell")])
        track = sound_design.design_track(24000, 24000 * 12, ev, 0.05)
        bell_part = track[int(8.25 * 24000):int(8.6 * 24000)]
        before = track[int(7.5 * 24000):int(7.9 * 24000)]
        self.assertGreater(np.abs(bell_part).max(), 2 * np.abs(before).max())

    def test_the_voice_finish_rides_the_archive_edges_of_a_cut(self):
        self.assertEqual(audio_finish.cut_points(None, CUT), [(6.0, "thud"), (9.0, "thud")])

    def test_the_gate_reads_the_shots_the_cut_published(self):
        ep = self.episode()
        shots = qc_episode.load_timeline(ep)
        self.assertEqual([(s.id, s.kind, s.start, s.duration) for s in shots],
                         [("s01", "3d", 0.0, 3.0), ("s02", "3d", 3.0, 3.0),
                          ("s03", "archive", 6.0, 3.0), ("s04", "3d", 9.0, 3.0)])
        self.assertEqual(qc_episode.check_coverage(shots, qc_episode.manifest_ids(ep), {}), [])
        self.assertEqual(qc_episode.known_cuts(ep), [3.0, 6.0, 9.0])

    def test_a_line_no_shot_plays_over_is_a_coverage_error(self):
        ep = self.episode()
        cut = json.loads((ep / "cut.resolved.json").read_text())
        for s in cut["shots"]:
            s["lines"] = ["u001"]
        (ep / "cut.resolved.json").write_text(json.dumps(cut))
        codes = [f.code for f in qc_episode.check_coverage(qc_episode.load_timeline(ep),
                                                           qc_episode.manifest_ids(ep), {})]
        self.assertEqual(codes, ["shot_missing"])


if __name__ == "__main__":
    unittest.main()
