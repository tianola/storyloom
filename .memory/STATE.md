# STATE
- Updated: 2026-11-15 (night). Phases 0-6 of `docs/COMPLETION-PLAN.md` done and verified.
- User instruction: finish the code first; NO new episode until the pipeline is complete. Jensen episode is the regression fixture only.
- Blender for tests in a worktree: `export BLENDER_EXE=F:/AI-PROJECTS/longform-explainer/tools/blender-4.5.15-windows-x64/blender.exe` (the exe is gitignored, so it only exists in the main checkout). Unset it for `test_blender_config`.

## Done and verified (commit after `76a184c`)
- `tools/blender/storyboard_beats.py`: generic builder. `--episode DIR [--beat N] [--force] [--still F] [--out D]`, `--catalog FILE`. Reads `storyboard.json` + `shot_lengths.json` (+ optional `word_timing.json`). Cuts every ~4.5 s with drift; label whose anchor is off screen gets its own 2.4 s close-up shot and the beat is rebuilt (up to 2 repairs).
- `workflow/scenes.json` (20 scenes: params, examples, views, anchors, actions), `workflow/storyboard.py` validator (`python -m workflow.storyboard <episode>`), `python/test_storyboard.py`, `python/test_scene_catalog.py`.
- `work/jensen-huang/storyboard.json`: the 17 beats as data; 0 framing problems in stills; `episode.json` rollout.builder -> generic builder; `tools/rollout_render.py` `builder_args()` adds `--episode`. Hand-written `jensen_huang_beats.py` and its two probes deleted.
- Tests passing: model_library 3, scene_catalog, storyboard, rollout_render, jensen_huang_episode (57 passed).
- Phase 0 so far: `archive_source` `used_urls` was a set read as a dict (44 failures -> ~16).

## Next (in order)
- 7 archive layer; 8 `tools/make_episode.py`; 9 clean-up/docs (stray root files: `qc_findings.txt`, `test_import.py`, `fix_licence.py`, `undefined`, ...).

## Phase 6: DONE
- `tools/captions.py` (word timings estimated from the waveform, `vo/words.json`, per-beat `word_timing.json` for the storyboard builder, `captions.srt/.vtt`, soft `mov_text` stream, `--burn`), `tools/audio_finish.py` (per-utterance levelling to the median, bounded 9 dB; synthesised whoosh/thud under cuts; level ride across archive cuts measured like the gate), `assemble_episode.py` flags `--remux`, `--out`, `--no-finish`, `--burn-captions`. `qc.captions_required` is now true.
- Proven on a scratch copy of the Jensen episode (main's files untouched): `assemble_episode.py --episode <copy> --remux --out remuxed.mp4` then `qc_episode.py`: PASS, 0 errors, 3 warnings (was 8); `no_captions` and the 4 `cut_loudness_jump` are gone, remaining are the 2 long archive shots and archive share. The real master in main has NOT been re-muxed.
- Finding: the 3+ LU jumps were sentence-end declination inside 1 s windows (every cut steps 1-7 LU), not level differences between sentences (those were < 1 LU); only the ride fixes it.
- Lesson: a heredoc `
` inside Python source became a real newline and broke `storyboard_beats.py` for a while; the gate test now also asserts no SyntaxError.

## Phase 5: DONE
- `tools/qc_script.py --episode DIR` (bounds in `workflow/style.json` `script`): length 600-900 s at 2.36 words/s, hook <= 10 s, chapters (`script/chapters.json`, >= 3), sentence length, speech-safe text (no digits/symbols; product names like NV1 only warn), every line cites a verified claim in `research/sources.md` via `script/claims.json` or is declared `"framing"`; sensitive lines (personal life, marriage, ...) always need a source. Writes `qc/script-qc.json`, exit 1 on errors. Jensen: 24 errors (188 s, hook 14.8 s, no chapters, every line unsourced since `sources.md` is empty, u018 sensitive). Tests: `python/test_qc_script.py` (8).
- Note: shell heredocs mangle `` into a backspace; write regexes with the Write/Edit tools.

## Phase 4: DONE
- `tools/plan_storyboard.py --episode DIR [--brief | --ask-cmd CMD [--repairs N] | --check]`: brief for an agent, or a command that gets the prompt on stdin and prints JSON; invalid answers are sent back with the errors; `storyboard.json` is only replaced by a valid one (rejects go to `storyboard-rejected.json`, exit 1). `storyboard_beats.py` also refuses an invalid storyboard before building. Tests: `python/test_plan_storyboard.py` (9). No real LLM call has been run yet.

## Phase 0: DONE (2026-11-15)
- `tsc` clean, 160 TS tests pass. Python: 619 passed, 2 skipped, 0 failed in the main checkout setup (in a worktree: export BLENDER_EXE, junction `.venv` and symlink `node_modules` to the main checkout; `narration-tts` preflight tests need the main checkout's `models/`; `test_blender_config` needs BLENDER_EXE unset).
- Deleted as dead: `tools/archive_source.py` (+ test, style.json `entry_point`), the Artemis builder stack (`artemis_beats.py`, `work/artemis_beats.*`, `bench_beat.py`, `lunar_ground_probe.py`, `techniques/surfaces*.py`, `tools/tile_seams.py`) and their tests (surfaces, regolith, lunar ground, tile seams, Artemis text guards). The "real episode" tests in `test_episode_paths`/`test_qc_episode` now read Jensen. `tools/sourcing/` (transport, providers, download) stays.
- Phase 7 must write the archive sourcing step fresh if still wanted.

## Open defects
- `tools/pipeline_supervisor.py` provisions a placeholder clip for missing archive media: likely cause of the black `boarding-school_part1` shot. Phase 7 makes it an error.
- Narration "GeForce twenty-five-ninety" (should be 256); "personal life" line unsourced; script 3:08 vs 600-900 s; no captions; archive share 10%; 4 loudness jumps at archive cuts.
- "Today" tag in `valuation` close-up sits against the bar (cosmetic).
- Map scene with real coastlines needs a public-domain coastline file: ask the user before downloading.
