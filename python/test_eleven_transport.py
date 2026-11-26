"""ElevenLabs calls survive a busy server, explain a refusal, and never leave a broken cache.

No network: the opener is replaced, so these run anywhere and spend no credits.
"""
import base64
import contextlib
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
sys.path.insert(0, str(ROOT))

import eleven  # noqa: E402
import narrate  # noqa: E402
from host_double import healthy_host  # noqa: E402

VOICE = "eleven:EXAVITQu4vr4xnSDxMaL"
GOOD = {"audio_base64": base64.b64encode(bytes(480)).decode(), "alignment": None}


class Answer(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def http_error(code, body=b"{}"):
    return urllib.error.HTTPError("https://api.elevenlabs.io", code, "reason", {}, io.BytesIO(body))


def opener(script):
    """Answers each call with the next item: an exception is raised, a dict is returned as JSON."""
    calls = []

    def open_(req, timeout):
        calls.append(req)
        item = script[len(calls) - 1]
        if isinstance(item, BaseException):
            raise item
        return Answer(json.dumps(item).encode())
    return open_, calls


class Transport(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.dict("os.environ", {"ELEVENLABS_API_KEY": "test-key"})
        patch.start()
        self.addCleanup(patch.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.waits = []

    def engine(self, script):
        open_, calls = opener(script)
        return eleven.ElevenEngine(Path(self.tmp.name), opener=open_, sleep=self.waits.append), calls

    def test_a_busy_server_is_retried_until_it_answers(self):
        e, calls = self.engine([http_error(429), http_error(503), urllib.error.URLError("reset"), GOOD])
        pcm, rate = e.create("Bad air.", VOICE)
        self.assertEqual((len(calls), rate), (4, 24000))
        self.assertEqual(self.waits, list(eleven.RETRY_WAITS[:3]))

    def test_a_refusal_is_not_retried_and_says_why(self):
        body = json.dumps({"detail": {"status": "quota_exceeded", "message": "You have 12 credits left."}}).encode()
        e, calls = self.engine([http_error(401, body)])
        with self.assertRaises(RuntimeError) as caught:
            e.create("Bad air.", VOICE)
        self.assertEqual(len(calls), 1)
        self.assertIn("HTTP 401", str(caught.exception))
        self.assertIn("12 credits left", str(caught.exception))
        self.assertNotIn("test-key", str(caught.exception))

    def test_it_gives_up_after_the_last_wait(self):
        e, calls = self.engine([http_error(500)] * (len(eleven.RETRY_WAITS) + 1))
        with self.assertRaises(RuntimeError):
            e.create("Bad air.", VOICE)
        self.assertEqual(len(calls), len(eleven.RETRY_WAITS) + 1)

    def test_a_damaged_cache_entry_is_fetched_again_and_replaced(self):
        e, calls = self.engine([GOOD, GOOD])
        e.create("Bad air.", VOICE)
        (entry,) = Path(self.tmp.name).glob("*.json")
        entry.write_text('{"audio_base64": "AAAA', encoding="utf-8")   # cut off mid-write
        e.create("Bad air.", VOICE)
        self.assertEqual(len(calls), 2)
        self.assertIn("audio_base64", json.loads(entry.read_text(encoding="utf-8")))
        self.assertEqual([p.name for p in Path(self.tmp.name).iterdir()], [entry.name])  # no temporaries


class CloudOnlyNarration(unittest.TestCase):
    """An episode spoken entirely by ElevenLabs does not need Kokoro installed, downloaded or loaded."""

    def run_main(self, voice, host):
        loaded = []
        with tempfile.TemporaryDirectory() as tmp:
            req = Path(tmp) / "request.json"
            req.write_text(json.dumps({"voice": voice, "speed": 1.0,
                                       "utterances": [{"id": "u001", "text": "Bad air."}]}), encoding="utf-8")
            err = io.StringIO()
            with mock.patch.object(narrate, "eleven_engine",
                                   lambda d: eleven.ElevenEngine(d, fetch=lambda v, b: GOOD)), \
                    contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                code = narrate.main(["--input", str(req), "--output", str(Path(tmp) / "vo")],
                                    engine_factory=lambda *a: loaded.append(a), host=host)
            wrote = (Path(tmp) / "vo" / "manifest.json").is_file()
        return code, loaded, wrote, err.getvalue()

    def test_no_weights_and_no_kokoro_module_still_narrate(self):
        host = healthy_host(ROOT, missing_modules=["kokoro_onnx"])
        code, loaded, wrote, _ = self.run_main(VOICE, host)
        self.assertEqual((code, loaded, wrote), (0, [], True))

    def test_a_local_voice_still_needs_the_preflight_and_the_weights(self):
        host = healthy_host(ROOT, missing_modules=["kokoro_onnx"])
        code, loaded, wrote, _ = self.run_main("af_heart", host)
        self.assertEqual((code, loaded, wrote), (narrate.REFUSED, [], False))

    def test_a_local_voice_without_model_arguments_is_an_error_not_a_crash(self):
        code, loaded, wrote, err = self.run_main("af_heart", healthy_host(ROOT))
        self.assertEqual((code, wrote), (3, False))
        self.assertIn("--model", err)


if __name__ == "__main__":
    unittest.main()
