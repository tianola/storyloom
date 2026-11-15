"""Diagram labels must not print on top of each other, nor off the edge of the frame.

A manim diagram places every label one call at a time — `next_to(dot, DOWN, buff=0.3)`,
`next_to(band, DOWN, buff=0.55)` — and each of those is defensible in isolation. What nobody
sees until the frame is rendered is the *pair*: in `DistanceScene` the "Earth" dot is five
units left and the Earth-orbit band is at -3.94, both hung under the axis, and the two strings
land in the same strip of sky. Measured through the layout itself, before this file's fix:

    "Earth"                    x -5.304 .. -4.696   y -0.892 .. -0.700
    "everything in Earth orbit" x -4.998 .. -2.882  y -0.989 .. -0.800
    shared region              0.302 x 0.092 units

At 135 px per unit — the 1080p the scene renders at — that is forty-one pixels of "Earth"
printed across "everything in Earth orbit", a quarter of the label's own height. That is the
defect this gate holds shut, and the reason the gate reads the scene's own geometry instead of
watching for it: it is one row of a table this file now refuses to let go wrong again. The fix
moves the dot's caption out to its left, where the nearest other label is 0.65 units away.

Each bound has a regression measured against this same probe, so gate and number agree by
construction:

    "Earth" back under its dot    0.302 x 0.092 units shared with the orbit caption
    title at `to_edge(UP, buff=-0.6)`   ends at y 4.600, past the 3.75 the frame allows

The measurement runs the real `construct()` for each scene under the interpreter that has
manim installed, with `play` and `wait` replaced by a recorder (`tools/manim/label_probe.py`)
that notes which mobjects each animation would have shown. No frame is rendered, so the boxes
are where the renderer will draw them and the whole suite costs about two seconds.

Boxes are tight glyph outlines, not em boxes, so two labels that merely kiss at their corners
share no area and pass. `MIN_EDGE_MARGIN` is drawn against the tightest real value in the
scene: titles go `to_edge(UP, buff=0.3)`, which puts their outline exactly 0.3 from the frame.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "tools" / "manim" / "label_probe.py"
MANIM_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"

# Bounds. The module docstring carries the measured defect each one is drawn against.
MAX_OVERLAP_UNITS = 0.02   # 2.7 px of 1080p: two outlines grazing, not two words sharing.
MIN_EDGE_MARGIN = 0.25     # titles sit at buff 0.3; anything under a quarter unit is cropped.
MIN_LABELS = 3             # a recorder that found nothing would pass every gate below.


def intersect(a, b):
    """The width and height of two boxes' shared region, negative when they miss."""
    return (min(a["x1"], b["x1"]) - max(a["x0"], b["x0"]),
            min(a["y1"], b["y1"]) - max(a["y0"], b["y0"]))


class TestManimLabels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MANIM_PYTHON.is_file():
            raise AssertionError(f"no manim interpreter at {MANIM_PYTHON}")
        proc = subprocess.run(
            [str(MANIM_PYTHON), str(PROBE)],
            capture_output=True, text=True, timeout=600, cwd=str(ROOT))
        if proc.returncode != 0:
            raise AssertionError(
                f"label_probe exited {proc.returncode}\n{proc.stdout[-3000:]}\n{proc.stderr[-3000:]}")
        marker = [ln for ln in proc.stdout.splitlines() if ln.startswith("MANIMLABELS_JSON ")]
        if not marker:
            raise AssertionError(f"no MANIMLABELS_JSON line in output:\n{proc.stdout[-3000:]}")
        cls.d = json.loads(marker[0].split("MANIMLABELS_JSON ", 1)[1])
        cls.scenes = cls.d["scenes"]

    def test_the_probe_reads_every_scene(self):
        """Guard against a vacuous pass: a recorder that stopped reaching Text mobjects would
        otherwise report four clean scenes."""
        for name, labels in self.scenes.items():
            self.assertGreaterEqual(len(labels), MIN_LABELS,
                                    f"{name} reported {len(labels)} labels; the recorder is "
                                    f"not seeing the scene's text")
        self.assertEqual(sorted(self.scenes), sorted([
            "TrajectoryScene", "FreeReturnScene", "DistanceScene", "ReentryAngleScene"]))

    def test_no_two_labels_print_on_top_of_each_other(self):
        for name, labels in self.scenes.items():
            for i, a in enumerate(labels):
                for b in labels[i + 1:]:
                    w, h = intersect(a, b)
                    self.assertFalse(
                        w > MAX_OVERLAP_UNITS and h > MAX_OVERLAP_UNITS,
                        f"{name}: \"{a['text']}\" and \"{b['text']}\" share "
                        f"{w:.3f} x {h:.3f} units")

    def test_every_label_clears_the_frame_edge(self):
        half_w = self.d["frame"]["width"] / 2
        half_h = self.d["frame"]["height"] / 2
        for name, labels in self.scenes.items():
            for a in labels:
                self.assertGreaterEqual(a["x0"], -half_w + MIN_EDGE_MARGIN,
                                        f"{name}: \"{a['text']}\" starts at x {a['x0']:.3f}")
                self.assertLessEqual(a["x1"], half_w - MIN_EDGE_MARGIN,
                                     f"{name}: \"{a['text']}\" ends at x {a['x1']:.3f}")
                self.assertGreaterEqual(a["y0"], -half_h + MIN_EDGE_MARGIN,
                                        f"{name}: \"{a['text']}\" starts at y {a['y0']:.3f}")
                self.assertLessEqual(a["y1"], half_h - MIN_EDGE_MARGIN,
                                     f"{name}: \"{a['text']}\" ends at y {a['y1']:.3f}")


if __name__ == "__main__":
    unittest.main()
