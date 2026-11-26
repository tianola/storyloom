"""The legacy assembler's concat lists survive the paths people really have.

A Greek folder name went through the OS code page (cp1252 on Windows) and an apostrophe ended the
quoted path; both broke the concat. The lists are now UTF-8 with quotes escaped.
"""
import shutil
import sys
import tempfile
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))

import assemble_episode as A  # noqa: E402


def tone(path, seconds):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\x01\x00" * int(24000 * seconds))


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is not installed")
class ConcatPaths(unittest.TestCase):
    def test_audio_concat_in_a_greek_folder_with_an_apostrophe(self):
        with tempfile.TemporaryDirectory() as tmp:
            episode = Path(tmp) / "Σέμελβαϊς ο' γιατρός"
            (episode / "vo").mkdir(parents=True)
            tone(episode / "vo" / "u001.wav", 0.5)
            tone(episode / "vo" / "u002.wav", 0.25)
            manifest = {"utterances": [{"id": "u001", "file": "u001.wav"}, {"id": "u002", "file": "u002.wav"}]}
            out = A.concat_audio(episode, manifest)
            with wave.open(str(out)) as w:
                self.assertAlmostEqual(w.getnframes() / w.getframerate(), 0.75, places=2)


if __name__ == "__main__":
    unittest.main()
