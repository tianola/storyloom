"""workflow/scenes.json and tools/blender/models/scenes.py describe the same scenes.

Blender builds every scene from the catalog's example parameters and reports the views,
anchors and actions it really has; the catalog must list exactly those. A scene added to the
code but not the catalog (or the reverse) fails here, not in the middle of an episode.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from workflow.config import blender_executable  # noqa: E402


class SceneCatalog(unittest.TestCase):
    def test_catalog_matches_the_code(self):
        from toolchain import require_blender
        require_blender()
        catalog = json.loads((ROOT / "workflow" / "scenes.json").read_text(encoding="utf-8"))["scenes"]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "found.json"
            run = subprocess.run([str(blender_executable(ROOT)), "--background", "--factory-startup", "-P",
                                  str(ROOT / "tools" / "blender" / "storyboard_beats.py"), "--",
                                  "--catalog", str(out)], capture_output=True, text=True, cwd=ROOT)
            self.assertTrue(out.exists(), run.stdout[-1500:] + run.stderr[-1500:])
            found = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(sorted(found), sorted(catalog), "scene names differ")
        for name, real in found.items():
            for key in ("views", "anchors", "actions"):
                self.assertEqual(sorted(catalog[name][key]), sorted(real[key]), f"{name}: {key} differ")


if __name__ == "__main__":
    unittest.main()
