# Longform Explainer — Approved Design

Approval: 2026-11-05. The user selected English narration and F: storage, delegated architecture choice, requested good AI models including existing OmniRoute, and authorized useful skill/plugin installation. No publishing is authorized.

## Product

A local browser application turns a topic in technology, economics, studying, general information or science into a researched, narrated, meaningfully animated YouTube-ready video. Normal duration range: 8–20 minutes, with a short preview mode for iteration. Input is a topic, audience, duration and evidence sources; output is an editable evidence/script/storyboard package and a playable MP4 plus captions, chapters, thumbnail, description, citations and asset licenses. An importable reviewed script permits deterministic creation without an LLM.

## Architecture

Use Node 24 + TypeScript for loopback-only API, durable SQLite jobs, child process supervision and browser UI. Motion Canvas is the initial animation choice, with deterministic per-frame rendering and FFmpeg assembly. A Python 3.12 Kokoro ONNX subprocess produces English narration. CPU inference only on Ryzen 7 5700X / 64 GiB / RX 580 4 GiB. No CUDA/ROCm dependency. Use free local runtime; never infer that a localhost proxy is free. OmniRoute at http://localhost:20128/v1 is optional only after explicit route/cost validation. No fallback from free/local to paid models. Credentials stay out of source, fixtures, logs, exports and notes.

## Data and quality

- Evidence sources retain URL, publisher, fetched time, extract and reuse terms. Claims cite existing source IDs; model output cannot invent URLs.
- User-supplied URLs cross a strict SSRF boundary: HTTP(S) only, no userinfo, deny private/reserved/link-local destinations including IPv6 and redirects, limit response size and timeout, pin validated DNS for the connection or use a narrowly allowlisted provider.
- Structured output validation is not factual verification. Unreviewed claims visibly block final approval; record reviewer decisions.
- Animation is trusted code driven by validated data, never model-written executable code. Scene vocabulary must include flows, comparisons, evolving charts, timelines and mechanism diagrams. One explanatory action per beat with deliberate emphasis and visual continuity.
- Text has separate display and spoken forms. English narration uses local Kokoro. Audio sample counts are the master clock. Resample 24 kHz speech to 48 kHz using FFmpeg, do not rewrite metadata. Captions use actual synthesized utterance boundaries; do not claim word alignment without an aligner.
- Every export records model IDs, generation settings, engine versions, input hashes, licenses and source/claim IDs. Original vector graphics are labeled generated; imported assets require documented rights.
- Preview quality may be 1280x720. Final target is 1920x1080, 30 fps, H.264/AAC, 48 kHz. Validation rejects missing streams, zero duration, blank frames and duration drift. Render intermediate files atomically and rename only after probing.

## Jobs and resource boundaries

SQLite persists states queued, researching, scripting, awaiting_review, narrating, rendering, assembling, completed, failed, cancelled, interrupted. A single heavy job runs at a time. Restart marks in-flight jobs interrupted; resume reuses only hash-matching valid artifacts. Cancellation closes child process trees. Bound retries and expose actual errors rather than silently substituting sample output. Check F: free space before stages with a 15 GiB reserve; never delete final exports automatically. Keep project dependencies, models and generated media in this project, do not move unrelated Ollama models or alter existing services.

## UI

A readable responsive local studio with topic/category/duration inputs, model and engine readiness, evidence/script review, chapter/scene timeline, job progress, cancel/resume, preview playback and export download. Empty, validation, dependency-unavailable and failed-job states are first-class. No upload or publish button. Never store provider keys in localStorage. Bind 127.0.0.1 only and reject cross-origin mutation requests.

## Narration adapter contract

Files owned by the narration task: python/narrate.py, python/requirements.txt, python/test_narrate.py, scripts/setup-narration.ps1. Runtime artifacts live in .venv/ and models/kokoro/; tests use temporary directories, never overwrite production output.

CLI: `.venv/Scripts/python.exe python/narrate.py --input request.json --output output-directory --model models/kokoro/kokoro-v1.0.onnx --voices models/kokoro/voices-v1.0.bin`.

Input JSON: `{ "voice": "af_heart", "speed": 1.0, "utterances": [{"id":"u001","text":"An English sentence."}] }`. IDs must be simple unique safe filenames. Accept English voice IDs validated against the installed engine. Reject empty text/utterances, nonfinite or out-of-range speed, duplicate IDs and output escape paths.

Output: one 24 kHz mono PCM WAV per utterance plus manifest.json `{ "sampleRate":24000, "voice":"af_heart", "utterances":[{"id":"u001","file":"u001.wav","text":"An English sentence.","samples":24000,"startSample":0,"endSample":24000}], "totalSamples":24000 }`. These numeric values illustrate schema only, not a performance/duration claim. Actual files determine values. Atomic manifest writes; exit nonzero on any failure; diagnostics on stderr and final manifest path on stdout. No network access during synthesis; setup separately retrieves official pinned model assets and records hashes and licenses. No copyrighted background music or voice cloning.

## Acceptance

Tests cover schema boundaries, source ID integrity, source-fetch defenses, job state/restart/cancel, cache invalidation, sample timing, captions and export probing. Browser verification must exercise a valid create/review/render/playback flow, invalid inputs, unavailable engine, cancellation and resume. Actual narrated longform output must be inspected at opening/middle/ending and transitions and listened to. Cover all five topic categories through normal UI inputs, without representing fixtures as generated content. A passing test suite alone is insufficient. Report measured speed, resource use, limitations and unverified items. No git commit/push or remote publication without separate instruction.
