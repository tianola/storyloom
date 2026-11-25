"""tools/edit/to_cut.py: an old episode becomes a cut list only if it cuts to the same frames."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))

from edit import to_cut as T  # noqa: E402
from workflow.config import style_contract  # noqa: E402

CONTRACT = style_contract(ROOT)
FPS = int(CONTRACT["canvas"]["fps"])


def manifest(*seconds, rate=24000):
    return {"sampleRate": rate, "utterances": [{"id": f"u{i:03d}", "samples": int(s * rate), "text": "x"}
                                               for i, s in enumerate(seconds, start=1)]}


class Convert(unittest.TestCase):
    def episode(self, shots, man):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ep = Path(tmp.name) / "ep"
        (ep / "vo").mkdir(parents=True)
        (ep / "shots.json").write_text(json.dumps(shots), encoding="utf-8")
        (ep / "vo" / "manifest.json").write_text(json.dumps(man), encoding="utf-8")
        return ep

    def test_a_reused_beat_resumes_where_the_old_cursor_was(self):
        shots = {"u001": {"kind": "3d", "name": "a"}, "u002": {"kind": "3d", "name": "b"},
                 "u003": {"kind": "3d", "name": "a"}}
        ep = self.episode(shots, manifest(2.0, 1.5, 2.5))
        out, found = T.convert(ep, fps=FPS, contract=CONTRACT)
        cut = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(out.name, "cut.from-shots.json")
        self.assertEqual([s["start_anchor"] for s in cut["shots"]], ["line:u001", "line:u002", "line:u003"])
        self.assertEqual(cut["shots"][2]["source"]["in"], 2.0)      # a's second use starts after its first
        self.assertFalse((ep / "cut.json").exists())

    def test_cards_stay_on_the_old_path(self):
        ep = self.episode({"u001": {"kind": "card", "name": "process"}}, manifest(2.0))
        with self.assertRaises(ValueError) as caught:
            T.convert(ep, fps=FPS, contract=CONTRACT)
        self.assertIn("card", str(caught.exception))

    def test_install_refuses_a_cut_that_breaks_the_house_rules(self):
        ep = self.episode({"u001": {"kind": "archive", "name": "clip"}}, manifest(20.0))   # far past the archive bound
        out, found = T.convert(ep, fps=FPS, contract=CONTRACT)
        self.assertIn("archive_long", {f["code"] for f in found})
        with self.assertRaises(ValueError):
            T.convert(ep, fps=FPS, install=True, contract=CONTRACT)
        self.assertFalse((ep / "cut.json").exists())

    def test_an_existing_cut_list_is_never_overwritten(self):
        ep = self.episode({"u001": {"kind": "3d", "name": "a"}}, manifest(2.0))
        (ep / "cut.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError):
            T.convert(ep, fps=FPS, install=True, contract=CONTRACT)
        self.assertEqual((ep / "cut.json").read_text(encoding="utf-8"), "{}")

    def test_the_committed_old_episodes_convert_frame_for_frame(self):
        for slug in ("jensen-huang", "ask-chatgpt", "euv-machine", "the-light-machine"):
            src = ROOT / "work" / slug
            if not (src / "shots.json").is_file() or not (src / "vo" / "manifest.json").is_file():
                continue
            with self.subTest(slug), tempfile.TemporaryDirectory() as tmp:
                ep = Path(tmp) / slug
                shutil.copytree(src / "vo", ep / "vo", ignore=shutil.ignore_patterns("*.wav", "eleven-cache"))
                shutil.copy(src / "shots.json", ep / "shots.json")
                out, _ = T.convert(ep, fps=FPS, contract=CONTRACT)   # raises if any frame differs
                self.assertTrue(out.is_file())


if __name__ == "__main__":
    unittest.main()
