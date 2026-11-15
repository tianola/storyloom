import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from workflow.config import blender_executable  # noqa: E402

class BlenderConfigTests(unittest.TestCase):
    def test_environment_then_accepted_config_then_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "tools/blender-4.1.0-windows-x64/blender.exe"
            self.assertEqual(blender_executable(root), legacy)
            config = root / "workflow/blender.json"
            config.parent.mkdir()
            config.write_text(json.dumps({"production": "tools/custom/blender.exe"}))
            self.assertEqual(blender_executable(root), root / "tools/custom/blender.exe")
            self.assertEqual(blender_executable(root, {"BLENDER_EXE": "D:/override/blender.exe"}), Path("D:/override/blender.exe"))
