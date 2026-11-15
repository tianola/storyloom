"""Missing or unreadable archive media stops the build; the supervisor never papers over it."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))
import pipeline_supervisor as S  # noqa: E402


class NoPlaceholders(unittest.TestCase):
    def test_no_fix_creates_media(self):
        self.assertFalse(hasattr(S, "_provision_placeholder_clip"))
        self.assertFalse(hasattr(S, "_regenerate_corrupt_clip"))
        self.assertEqual([f.name for f in S.FIX_CATALOG], ["finishing-unreported"])

    def test_missing_media_is_a_finding_not_a_fix(self):
        out = "shot x (u001) reads a.mp4 from archive.json, which is not on disk at C:/e/assets/a.mp4"
        self.assertFalse(any(f.detect(out) for f in S.FIX_CATALOG))
        import re
        names = [n for n, pattern, _ in S.AGENT_ONLY if re.search(pattern, out, re.I | re.S)]
        self.assertIn("missing-archive-media", names)


if __name__ == "__main__":
    unittest.main()
