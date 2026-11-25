import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import fetch_assets as F  # noqa: E402


def tex(url):
    return {"Diffuse": {"1k": {"jpg": {"url": url, "size": 10}}}}


class Plan(unittest.TestCase):
    def test_texture_maps_from_the_download_host(self):
        items = F.plan("textures", "x", "1k", tex("https://dl.polyhaven.org/file/ph-assets/Textures/jpg/1k/x/x_diff_1k.jpg"))
        self.assertEqual(items[0][2], "x_diff_1k.jpg")

    def test_other_hosts_are_refused(self):
        with self.assertRaises(ValueError):
            F.plan("textures", "x", "1k", tex("https://example.com/x_diff_1k.jpg"))

    def test_model_includes_cannot_escape_the_folder(self):
        files = {"gltf": {"1k": {"gltf": {"url": "https://dl.polyhaven.org/a/m.gltf", "size": 1,
                                          "include": {"../../evil.bin": {"url": "https://dl.polyhaven.org/a/e.bin", "size": 1}}}}}}
        with self.assertRaises(ValueError):
            F.plan("models", "m", "1k", files)


if __name__ == "__main__":
    unittest.main()
