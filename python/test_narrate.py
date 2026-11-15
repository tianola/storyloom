import contextlib
import copy
import io
import json
import math
import sys
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from host_double import healthy_host  # noqa: E402
from narrate import EngineError, build_manifest, main, synthesize, validate_request  # noqa: E402

# These tests are about the adapter's CLI contract, so they answer the preflight with a healthy
# machine rather than inheriting whatever this box happens to have installed. The gate's own
# behaviour is asserted in `python/test_capabilities.py`.
HOST = healthy_host(ROOT)


def request():
    return {
        "voice": "af_heart",
        "speed": 1.0,
        "utterances": [{"id": "u001", "text": "An English sentence."}],
    }


class FakeEngine:
    """Mirrors the kokoro-onnx Kokoro surface used by the adapter."""

    sample_rate = 24000
    voices = ["af_heart", "af_sky", "am_adam"]

    def __init__(self, frames_by_text=None, rate=None, error=None):
        self.frames_by_text = frames_by_text or {}
        self.rate = rate if rate is not None else 24000
        self.error = error
        self.calls = []

    def create(self, text, voice, speed=1.0, split_pattern=None):
        self.calls.append({"text": text, "voice": voice, "speed": speed, "split_pattern": split_pattern})
        if self.error:
            raise self.error
        frames = self.frames_by_text.get(text, 4800)
        return np.linspace(-0.5, 0.5, frames, dtype=np.float32), self.rate


class ContractTests(unittest.TestCase):
    def test_accepts_valid_request_without_mutating_it(self):
        value = request()
        original = copy.deepcopy(value)
        self.assertEqual(validate_request(value), original)
        self.assertEqual(value, original)

    def test_rejects_invalid_request_shapes(self):
        for value in (None, [], {}, {"voice": "af_heart"}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_request(value)

    def test_rejects_empty_or_malformed_utterances(self):
        for utterances in ([], "text", {}, [None], [{}], [{"id": 4, "text": "x"}]):
            with self.subTest(utterances=utterances), self.assertRaises(ValueError):
                validate_request({**request(), "utterances": utterances})

    def test_rejects_escape_and_unsafe_windows_ids(self):
        for identity in ("../x", "/tmp/x", "C:\\x", "a/b", "a\\b", ".", "", "a.b", "x" * 65, "CON", "aux", "COM1", "lpt9", "nul"):
            value = request()
            value["utterances"][0]["id"] = identity
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                validate_request(value)

    def test_rejects_duplicate_ids_including_windows_case_collisions(self):
        for identity in ("u001", "U001"):
            value = request()
            value["utterances"].append({"id": identity, "text": "Other text."})
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                validate_request(value)

    def test_rejects_invalid_text(self):
        for text in ("", "   \n", None, 12, "a" * 5001, "Hello\x00world"):
            value = request()
            value["utterances"][0]["text"] = text
            with self.subTest(text_type=type(text)), self.assertRaises(ValueError):
                validate_request(value)

    def test_rejects_nonfinite_or_out_of_range_or_nonnumeric_speed(self):
        for speed in (float("nan"), float("inf"), -float("inf"), 0, 0.49, 2.01, True, None, "1", 10**500):
            with self.subTest(speed=str(speed)[:30]), self.assertRaises(ValueError):
                validate_request({**request(), "speed": speed})

    def test_accepts_speed_endpoints(self):
        for speed in (0.5, 1, 2.0):
            self.assertEqual(validate_request({**request(), "speed": speed})["speed"], speed)

    def test_rejects_voice_ids_outside_the_installed_english_set(self):
        for voice in ("jf_alpha", "ff_siwis", "../af_heart", "", None, 42, "AF_HEART"):
            with self.subTest(voice=voice), self.assertRaises(ValueError):
                validate_request({**request(), "voice": voice})

    def test_boundaries_follow_actual_samples(self):
        actual = build_manifest("af_heart", [
            {"id": "a", "file": "a.wav", "text": "First.", "samples": 12345},
            {"id": "b", "file": "b.wav", "text": "Second.", "samples": 45678},
        ])
        self.assertEqual(actual, {
            "sampleRate": 24000,
            "voice": "af_heart",
            "utterances": [
                {"id": "a", "file": "a.wav", "text": "First.", "samples": 12345, "startSample": 0, "endSample": 12345},
                {"id": "b", "file": "b.wav", "text": "Second.", "samples": 45678, "startSample": 12345, "endSample": 58023},
            ],
            "totalSamples": 58023,
        })


class SynthesisTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / "out"

    def test_writes_pcm_wav_and_sample_accurate_manifest(self):
        value = {
            "voice": "af_heart",
            "speed": 1.0,
            "utterances": [
                {"id": "u001", "text": "First sentence."},
                {"id": "u002", "text": "Second sentence."},
            ],
        }
        engine = FakeEngine(frames_by_text={"First sentence.": 12345, "Second sentence.": 678})
        manifest = synthesize(value, self.out, engine)
        self.assertEqual(manifest["sampleRate"], 24000)
        self.assertEqual([u["samples"] for u in manifest["utterances"]], [12345, 678])
        self.assertEqual(manifest["totalSamples"], 13023)
        self.assertEqual(manifest["utterances"][1]["startSample"], 12345)
        self.assertEqual(manifest["utterances"][1]["endSample"], 13023)
        for entry in manifest["utterances"]:
            with wave.open(str(self.out / entry["file"]), "rb") as handle:
                self.assertEqual(handle.getnframes(), entry["samples"])
                self.assertEqual(handle.getframerate(), 24000)
                self.assertEqual(handle.getnchannels(), 1)
                self.assertEqual(handle.getsampwidth(), 2)
                self.assertEqual(handle.getcomptype(), "NONE")
                recorded = handle.readframes(handle.getnframes())
            self.assertEqual(len(recorded), entry["samples"] * 2)
        self.assertEqual(engine.calls[0]["voice"], "af_heart")
        self.assertEqual(engine.calls[1]["speed"], 1.0)

    def test_clips_extreme_floats_instead_of_wrapping(self):
        value = {"voice": "af_heart", "speed": 1.0, "utterances": [{"id": "u001", "text": "Loud."}]}

        class LoudEngine(FakeEngine):
            def create(self, text, voice, speed=1.0, split_pattern=None):
                return np.array([2.0, -2.0, 0.0], dtype=np.float32), 24000

        synthesize(value, self.out, LoudEngine())
        with wave.open(str(self.out / "u001.wav"), "rb") as handle:
            frames = np.frombuffer(handle.readframes(3), dtype="<i2")
        self.assertEqual(frames.tolist(), [32767, -32767, 0])

    def test_rejects_empty_waveform_without_a_manifest(self):
        value = {"voice": "af_heart", "speed": 1.0, "utterances": [{"id": "u001", "text": "Silence."}]}
        engine = FakeEngine(frames_by_text={"Silence.": 0})
        with self.assertRaises(EngineError):
            synthesize(value, self.out, engine)
        self.assertFalse((self.out / "manifest.json").exists())

    def test_rejects_unsupported_engine_sample_rate(self):
        value = {"voice": "af_heart", "speed": 1.0, "utterances": [{"id": "u001", "text": "Hello."}]}
        with self.assertRaises(EngineError):
            synthesize(value, self.out, FakeEngine(rate=22050))
        self.assertFalse((self.out / "manifest.json").exists())

    def test_second_failure_leaves_no_manifest_and_no_temporaries(self):
        value = {
            "voice": "af_heart",
            "speed": 1.0,
            "utterances": [{"id": "u001", "text": "Good."}, {"id": "u002", "text": "Bad."}],
        }
        engine = FakeEngine(error=None)

        class HalfBroken(FakeEngine):
            def create(self, text, voice, speed=1.0, split_pattern=None):
                if text == "Bad.":
                    raise RuntimeError("engine exploded")
                return super().create(text, voice, speed, split_pattern)

        with self.assertRaises(EngineError):
            synthesize(value, self.out, HalfBroken())
        self.assertFalse((self.out / "manifest.json").exists())
        self.assertEqual([p.name for p in self.out.glob("*")], ["u001.wav"])

    def test_rejects_voice_the_installed_engine_lacks(self):
        value = {"voice": "af_sarah", "speed": 1.0, "utterances": [{"id": "u001", "text": "Hello."}]}
        with self.assertRaises(ValueError):
            synthesize(value, self.out, FakeEngine())


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.model = self.root / "kokoro-v1.0.onnx"
        self.model.write_bytes(b"not-a-real-model")
        self.voices = self.root / "voices-v1.0.bin"
        self.voices.write_bytes(b"not-real-voices")

    def _run(self, args):
        err, out = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            code = main(args, engine_factory=lambda *_: FakeEngine(), host=HOST)
        return code, err.getvalue(), out.getvalue()

    def test_cli_prints_manifest_path_and_writes_real_numbers(self):
        req = self.root / "request.json"
        req.write_text(json.dumps({"voice": "af_heart", "speed": 1.0,
                                   "utterances": [{"id": "u001", "text": "Hello there."}]}), encoding="utf-8")
        out = self.root / "out"
        code, _, stdout = self._run(["--input", str(req), "--output", str(out),
                                     "--model", str(self.model), "--voices", str(self.voices)])
        self.assertEqual(code, 0)
        self.assertEqual(stdout.strip(), str(out / "manifest.json"))
        manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["utterances"][0]["samples"], 4800)

    def test_cli_exits_nonzero_for_invalid_request_without_manifest(self):
        req = self.root / "request.json"
        req.write_text(json.dumps({"voice": "af_heart", "speed": 3.0,
                                   "utterances": [{"id": "u001", "text": "Hello."}]}), encoding="utf-8")
        out = self.root / "out"
        code, stderr, stdout = self._run(["--input", str(req), "--output", str(out),
                                          "--model", str(self.model), "--voices", str(self.voices)])
        self.assertEqual(code, 2)
        self.assertIn("Speed", stderr)
        self.assertEqual(stdout, "")
        self.assertFalse((out / "manifest.json").exists())

    def test_cli_refuses_missing_model_before_writing_anything(self):
        req = self.root / "request.json"
        req.write_text(json.dumps(request()), encoding="utf-8")
        out = self.root / "out"
        missing = self.root / "definitely-absent.onnx"
        err, captured = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(captured):
            code = main(["--input", str(req), "--output", str(out),
                         "--model", str(missing), "--voices", str(missing)], host=HOST)
        self.assertEqual(code, 3)
        self.assertIn("model", err.getvalue().lower())
        self.assertEqual(captured.getvalue(), "")
        self.assertFalse((out / "manifest.json").exists())
        self.assertFalse(out.exists() and any(out.iterdir()))

    def test_cli_rejects_output_inside_the_model_directory(self):
        req = self.root / "request.json"
        req.write_text(json.dumps(request()), encoding="utf-8")
        models = self.root / "models" / "kokoro"
        models.mkdir(parents=True)
        (models / "k.onnx").write_bytes(b"placeholder")
        (models / "v.bin").write_bytes(b"placeholder")
        err, captured = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(captured):
            code = main(["--input", str(req), "--output", str(models),
                         "--model", str(models / "k.onnx"), "--voices", str(models / "v.bin")],
                        engine_factory=lambda *_: FakeEngine(), host=HOST)
        self.assertEqual(code, 2)
        self.assertIn("output", err.getvalue().lower())


if __name__ == "__main__":
    unittest.main()
