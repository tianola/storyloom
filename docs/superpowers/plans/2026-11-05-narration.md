# Local English Narration Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this bounded plan test-first. No commits unless requested.

**Goal:** Produce real local English speech WAV files and exact sample-based timings for the longform application.

**Architecture:** A Python subprocess loads Kokoro ONNX once per batch, validates a data-only request and writes deterministic metadata from actual audio arrays. Dependency installation and model download are separate from offline synthesis.

**Tech Stack:** Python 3.12, kokoro-onnx, NumPy, stdlib wave/json/unittest, ONNX CPU runtime.

**Spec:** ../specs/2026-11-05-longform-explainer.md, especially Narration adapter contract.

## Global Constraints

English narration; CPU only; all project models/artifacts under F:/AI-PROJECTS/longform-explainer; never overwrite unrelated installs. No API credentials, cloud calls, uploads, voice cloning or copyrighted music. Record actual dependency versions and model hashes. Never invent timing or performance measurements. The main conversation owns all files except the four implementation files below and this plan's checkboxes.

## Task 1: Validated request and timing contract

**Files:** Create python/narrate.py and python/test_narrate.py.

**Interfaces:** `validate_request(value: dict) -> dict`; `build_manifest(voice: str, chunks: list[dict]) -> dict`; `synthesize(request: dict, output_dir: Path, engine) -> dict`.

- [x] Write validation and sample-clock tests before production implementation.

```python
import unittest
from narrate import validate_request, build_manifest

class ContractTests(unittest.TestCase):
    def test_rejects_path_escape_id(self):
        with self.assertRaises(ValueError):
            validate_request({'voice': 'af_heart', 'speed': 1.0,
                              'utterances': [{'id': '../x', 'text': 'Hello.'}]})

    def test_boundaries_follow_actual_samples(self):
        actual = build_manifest('af_heart', [
            {'id': 'a', 'file': 'a.wav', 'text': 'First.', 'samples': 12345},
            {'id': 'b', 'file': 'b.wav', 'text': 'Second.', 'samples': 45678}])
        self.assertEqual(actual['utterances'][1]['startSample'], 12345)
        self.assertEqual(actual['totalSamples'], 58023)
```

- [x] Run `.venv/Scripts/python.exe -m unittest discover -s python -v`; verify missing implementation fails, not a typo.
- [x] Implement validation with `re.fullmatch(r'[A-Za-z0-9_-]{1,64}', id)`, unique IDs, nonempty bounded text, `math.isfinite(speed)` and range 0.5–2.0, English installed voice validation. Manifest accumulator starts at zero and each end is start plus actual samples.
- [x] Extend tests for empty request, duplicate IDs, nonfinite speed, absolute paths, empty waveform and non-24kHz engine output. Run green. Adapter must refuse missing models before creating partial final files.

## Task 2: Offline Kokoro integration and setup

**Files:** Create python/requirements.txt and scripts/setup-narration.ps1; modify python/narrate.py; test python/test_narrate.py.

**Consumes:** validated request above and official engine API from the installed pinned version.
**Produces:** CLI in spec, utterance WAVs and manifest.json with exact sampleRate/samples/startSample/endSample/totalSamples.

- [x] Check official kokoro-onnx package metadata/API and model release asset URLs. Pin compatible versions. Use known Python executable C:/Users/thana/AppData/Roaming/uv/python/cpython-3.12.14-windows-x86_64-none/python.exe rather than installing system Python.
- [x] Create project-local .venv and install CPU-only requirements. Setup script must use explicit paths, stop on nonzero exit, avoid prompts, support an already-created venv and verified assets, and never mutate user environment variables. Download only official model/voice assets to models/kokoro and record source URLs/license/hash in models/kokoro/assets.json.
- [x] Write a synthesis test with a small injected engine returning a known waveform; assert PCM frame count using wave.open, manifest samples and absence of final manifest on failure. The fake verifies the adapter contract, not actual speech quality.
- [x] Implement engine loading, one create call per utterance, real float-to-PCM conversion with clipping, 24kHz mono WAV, same-directory temporary writes and atomic rename. For request failure exit nonzero with stderr and no misleading completed manifest.
- [x] Run all Python tests green, then run the real engine for two English utterances from a temporary smoke request outside source code.

```json
{"voice":"af_heart","speed":1.0,"utterances":[{"id":"u001","text":"Energy can change form, but it does not disappear."},{"id":"u002","text":"Follow the moving dots from the battery to the lamp."}]}
```

- [x] Verify both WAV headers and actual durations with ffprobe, independently sum sample counts and compare manifest. Measure wall time and audio seconds; report real-time factor and peak memory if available, not estimates as measurements.
- [x] Keep real smoke outputs under data/narration-smoke. Report exact commands, versions, hashes, tests and remaining quality/listening limitations. Do not claim subjective voice quality from ffprobe alone.

## Acceptance and ownership

The consumer can invoke the documented CLI without network access after setup and receive correct real speech plus timings. Missing dependencies fail explicitly. Main conversation reviews changes and performs final pipeline audio resampling, mixing, captions and video validation. Do not create or edit package.json, src/, web/, renderer/, any OmniRoute configuration, or shared vault notes; report results to main for coordinated reconciliation.
