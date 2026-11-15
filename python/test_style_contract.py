import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools/blender"))

from techniques.lighting import LUNAR_KEY_ELEVATION, MAX_FRONT_YAW  # noqa: E402
from workflow.config import REQUIRED_STYLE_KEYS, style_contract  # noqa: E402


class StyleContractTests(unittest.TestCase):
    """The contract is only worth having if the code it describes still agrees with it.

    Artemis II shipped eighteen beats with one hand-placed sun because the lighting rule
    lived in nobody's reach. A test that reads both sides is what keeps this file from
    becoming a description of a style nobody builds.
    """

    def setUp(self):
        self.contract = style_contract(ROOT)

    def test_every_section_the_doctrine_asks_for_is_present(self):
        for key in REQUIRED_STYLE_KEYS:
            self.assertIn(key, self.contract, key)

    def test_palette_stays_at_three_colours(self):
        palette = self.contract["palette"]
        colours = [k for k in palette if isinstance(palette[k], dict)]
        self.assertLessEqual(len(colours), palette["count_max"], colours)
        self.assertEqual(sorted(colours), ["accent", "base", "ground"])

    def test_lighting_section_matches_the_helper_it_cites(self):
        lighting = self.contract["lighting"]
        self.assertEqual(lighting["key_elevation_deg"], LUNAR_KEY_ELEVATION)
        self.assertGreaterEqual(lighting["key_yaw_deg"], MAX_FRONT_YAW)
        self.assertTrue(lighting["key_from_camera_axis"])

    def test_rhythm_bounds_are_the_ones_the_brief_states(self):
        rhythm = self.contract["rhythm"]
        self.assertEqual(rhythm["max_static_seconds"], 10.0)
        self.assertLessEqual(rhythm["hook_max_seconds"], rhythm["max_static_seconds"])

    def test_voice_names_the_installed_one_without_naming_a_key(self):
        voice = self.contract["voice"]
        self.assertEqual(voice["voice"], "af_heart")
        self.assertNotIn("key", {k.lower() for k in voice})

    def test_no_credential_shaped_string_anywhere_in_the_file(self):
        text = (ROOT / "workflow/style.json").read_text(encoding="utf-8")
        secrets = re.findall(r"(?i)\b(sk-[A-Za-z0-9]{8,}|hf_[A-Za-z0-9]{8,}|om-[A-Za-z0-9]{4,})\b", text)
        self.assertEqual(secrets, [], secrets)

    def test_the_archive_section_cannot_vanish_from_the_contract(self):
        """The archival layer is part of the house style now, so losing it is a build error.

        A section that is only consulted when present is a section a later refactor can delete
        while every call site keeps working -- and the episode that ships is silently 3D-only,
        which is exactly the divergence this file exists to prevent.
        """
        with tempfile.TemporaryDirectory() as tmp:
            stripped = json.loads(json.dumps(self.contract))
            del stripped["archive"]
            path = Path(tmp) / "workflow" / "style.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(stripped), encoding="utf-8")
            with self.assertRaises(ValueError) as caught:
                style_contract(Path(tmp))
        self.assertIn("archive", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
