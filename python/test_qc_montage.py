# -*- coding: utf-8 -*-
"""The episode-level look QC has to be able to describe a film other than Artemis II.

`montage_episode.py` — one labelled frame per utterance, tiled — lived inside
`work/episode-artemis-ii/qc/` and imported that episode's own `EPISODE` directory and `VISUAL_MAP`
from the assembler. When #146 turned those into data the script did not become portable, it became
unimportable: the evidence the look pass is judged on could only ever be regenerated for one film,
which is how a house style quietly stops being one.

So it moved to `tools/` and takes `--episode`. The two facts it labels with are the two the episode
now owns: which shot is on screen (`shots.json`) and how long the narration over it runs
(`manifest.json` and its own `sampleRate`).
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "python"))

import qc_montage as Q  # noqa: E402


def seeded(directory: Path, slug: str) -> Path:
    """An episode directory with the three files the montage reads."""
    ep = directory / slug
    (ep / "qc").mkdir(parents=True)
    (ep / "episode.json").write_text(json.dumps({"slug": slug, "title": "T", "workflow_version": 3}),
                                     encoding="utf-8")
    (ep / "shots.json").write_text(json.dumps({
        "u001": {"kind": "3d", "name": "launch"},
        "u002": {"kind": "manim", "name": "delta-v", "title": "Budget"}}, indent=1),
        encoding="utf-8")
    (ep / "vo").mkdir()
    (ep / "vo" / "manifest.json").write_text(json.dumps({
        "sampleRate": 16000,
        "totalSamples": 240000,
        "utterances": [{"id": "u001", "samples": 160000},    # 10 s
                       {"id": "u002", "samples": 80000}]}),  #  5 s
        encoding="utf-8")
    return ep


class CellTests(unittest.TestCase):
    def test_each_cell_is_labelled_with_the_shot_the_episode_declares(self):
        """The label comes from `shots.json`, not from a table typed into this script."""
        cells = Q.cells({"utterances": [{"id": "u001", "samples": 160000},
                                        {"id": "u002", "samples": 80000}]},
                        {"u001": ("3d", "launch"), "u002": ("manim", "delta-v", "Budget")},
                        16000)
        self.assertEqual([label for label, _ in cells],
                         ["u001 3d:launch 0-10s", "u002 manim:delta-v 10-15s"])

    def test_the_frame_is_grabbed_at_the_midpoint_of_the_utterance(self):
        """The look question is what the viewer sees while the sentence is spoken."""
        cells = Q.cells({"utterances": [{"id": "u001", "samples": 160000},
                                        {"id": "u002", "samples": 80000}]},
                        {"u001": ("3d", "launch"), "u002": ("3d", "launch")}, 16000)
        self.assertEqual([round(mid, 3) for _, mid in cells], [5.0, 12.5])

    def test_the_span_is_measured_in_the_rate_the_narration_declares(self):
        """A montage timed at the wrong rate would grab the frame before the sentence starts."""
        cells = Q.cells({"utterances": [{"id": "u001", "samples": 160000}]},
                        {"u001": ("3d", "launch")}, 8000)
        self.assertEqual(cells, [("u001 3d:launch 0-20s", 10.0)])


class RunTests(unittest.TestCase):
    def test_an_invocation_without_an_episode_is_refused(self):
        import contextlib
        import io
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as caught:
                Q.main([])
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("--episode", stderr.getvalue())

    def test_a_run_tiles_the_episode_and_writes_its_sheet_under_qc(self):
        """The whole path, with the frame grab stubbed: no ffmpeg, no GPU, one real episode."""
        import tempfile
        grabbed = []

        def fake_grab(master, when, png):
            grabbed.append((master, round(when, 3)))
            _white(png)

        with tempfile.TemporaryDirectory() as tmp:
            ep = seeded(Path(tmp), "episode-vostok")
            (ep / "episode-vostok.mp4").write_bytes(b"\0")
            original = Q.grab
            Q.grab = fake_grab
            try:
                rc = Q.main(["--episode", str(ep)])
            finally:
                Q.grab = original
            sheet = ep / "qc" / "montage.png"
            self.assertEqual(rc, 0)
            self.assertEqual([when for _, when in grabbed], [5.0, 12.5])
            self.assertEqual(grabbed[0][0], ep / "episode-vostok.mp4")
            # Inside the `with`: the throwaway episode is gone by the time the block exits, and an
            # assertion about a deleted file passes for nobody and fails for everybody.
            self.assertTrue(sheet.is_file(),
                            "the sheet must land in the episode's own evidence directory")
            from PIL import Image
            with Image.open(sheet) as page:
                self.assertEqual(page.size, (Q.COLS * Q.CELL_W, Q.CELL_H + Q.PAD),
                                 "two cells are one row of the grid, label strip included")

    def test_it_refuses_an_episode_whose_shots_do_not_cover_its_narration(self):
        """A montage over a hole in the timeline shows a frame for a sentence with no shot."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ep = seeded(Path(tmp), "episode-tsiolkovsky")
            (ep / "shots.json").write_text(json.dumps(
                {"u001": {"kind": "3d", "name": "launch"},
                 "u099": {"kind": "3d", "name": "orphan"}}), encoding="utf-8")
            with self.assertRaises(ValueError) as caught:
                Q.main(["--episode", str(ep)])
        self.assertIn("u002", str(caught.exception))


def _white(png):
    from PIL import Image
    Image.new("RGB", (64, 36), (255, 255, 255)).save(png)


if __name__ == "__main__":
    unittest.main()
