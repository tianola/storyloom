"""The reusable model library (tools/blender/models) builds, and its beats stay framed.

Runs the Jensen Huang builder in still mode: every beat is constructed in real Blender,
one half-resolution frame is rendered per beat, and the builder reports any callout
whose text would leave the frame. A model that stops building, or a label nudged off
screen, fails here in about half a minute instead of after a full render.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from workflow.config import blender_executable  # noqa: E402

BUILDER = ROOT / "tools" / "blender" / "jensen_huang_beats.py"
BEATS = [
    "denny-den", "leather-jacket", "silicon-wafer", "nv1-chip", "riva-chip", "geforce-chip",
    "parallel-cores", "cuda-stack", "deep-learning", "dgx-cluster", "blackwell-chip", "flat-org",
    "nvidia-hq",
]


class ModelLibraryBuilds(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        cls.proc = subprocess.run(
            [str(blender_executable(ROOT)), "--background", "--factory-startup",
             "--python-exit-code", "1", "--python", str(BUILDER), "--",
             "--still", "0.85", "--out", str(cls.out)],
            cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace", timeout=900)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_beat_builds_in_blender(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stdout[-3000:])

    def test_every_beat_renders_a_frame_that_is_not_empty(self):
        for name in BEATS:
            still = self.out / f"{name}-085.png"
            self.assertTrue(still.is_file(), f"{name} produced no still")
            # a blank or black frame compresses to a few kilobytes
            self.assertGreater(still.stat().st_size, 60_000, f"{name} rendered an almost empty frame")

    def test_no_callout_leaves_the_frame(self):
        off = [line.strip() for line in self.proc.stdout.splitlines() if "FRAMING" in line]
        self.assertEqual(off, [], "\n".join(off))


if __name__ == "__main__":
    unittest.main()
