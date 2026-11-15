
## Narration adapter (built by the sibling implementation session, integrated here)

- Contract: `.venv/Scripts/python.exe python/narrate.py --input request.json --output OUT --model models/kokoro/kokoro-v1.0.onnx --voices models/kokoro/voices-v1.0.bin`;
  stdout is the manifest path only, diagnostics go to stderr; exit codes `0` ok, `2` request/argument errors,
  `3` missing model assets, `1` engine failure. `manifest.json` carries `sampleRate 24000`, the voice, and
  `utterances[{id,file,text,samples,startSample,endSample}]` with cumulative boundaries taken from the **actual**
  written frames (`wave nframes`), not from a sample-rate calculation. WAVs and manifest are written temp+rename.
- Refusals worth knowing: empty text or utterances, non-finite/out-of-range speed (allowed 0.5–2.0), duplicate ids
  (case-insensitive), ids outside `[A-Za-z0-9_-]{1,64}`, Windows reserved names (CON, NUL, COM1, LPT9…), non-English
  voice prefixes (only `af_ am_ bf_ bm_`), a voice missing from the installed bundle, empty waveform, engine output
  that is not 24 kHz, and an output directory that would sit inside the model assets.
- Pinned: Python 3.12.14 (uv cpython build), `kokoro-onnx 0.6.1`, `onnxruntime 1.31.1` on `CPUExecutionProvider`
  (Azure provider is listed but unused), `numpy 2.5.4`, `espeakng-loader 0.2.4`, `phonemizer 3.6.0` plus seven
  transitive pins, all hash-pinned in `python/requirements.txt`. The hashes are `win_amd64`/`cp312` wheel-specific, so
  another platform needs a fresh `--dry-run --report resolution`.
- Measured cost (their numbers, `data/narration-smoke/report.json`): cold CLI 10.6–11.4 s for 6.144 s of audio
  (RTF ~1.73 end to end), model load 4.6–6.0 s, synthesis alone 4.5–4.8 s (RTF ~0.73–0.77), 25.3–26.2 s of process-tree
  CPU per run, ~495 MB peak. Extrapolated: 15–20 min of CPU synthesis for a 20-minute episode, one engine load per
  batch. 24 kHz → 48 kHz resampling stays on the TypeScript side (FFmpeg), per the pipeline's own rule.
- **Two facts that change how caching must work:**
  1. Kokoro ONNX output is *not* bit-reproducible run to run — `u002` measured 71,663 vs 71,424 samples across runs
     (~10 ms drift) while `u001` stayed stable. Never recompute an utterance duration; only consume the manifest from
     the same run that wrote those WAVs, and treat a cache hit as valid only when the artifact hashes of the WAVs and
     the manifest agree together. `loadNarration()` in `src/cli.ts` checks each WAV's byte size against the manifest's
     `samples` and then rebuilds the timeline from that manifest, which is the shape this requires.
  2. `.venv/Scripts/python.exe` is a launcher stub, so `Popen.pid` is not the real interpreter pid (28460 vs 16676
     observed). Any CPU/memory accounting must walk the process tree; `data/narration-smoke/measure.py` has a
     Toolhelp-based tree observer for that.
- **Checked on this side, not assumed:** cancelling `runProcess` against the real `.venv` interpreter left **zero**
  surviving python processes, so the tree kill that `src/server/api.ts` uses for its own child was not needed here.
  `tests/process.test.ts` now pins that behaviour (a grandchild writing a 100 ms heartbeat must stop within three
  beats of an abort), so if the stub ever stops propagating the kill the suite says so instead of silently leaking.
- Not done anywhere: listening for intelligibility or pronunciation quality, long batches, the other voices, the speed
  extremes and the 5,000-character bound on real audio — all of those are unit-tested against an injected fake engine.
