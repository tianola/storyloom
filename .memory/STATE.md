# STATE
- Updated: 2026-11-15 (night). Phases 0-3 of `docs/COMPLETION-PLAN.md` done and verified.
- User instruction: finish the code first; NO new episode until the pipeline is complete. Jensen episode is the regression fixture only.
- Blender for tests in a worktree: `export BLENDER_EXE=F:/AI-PROJECTS/longform-explainer/tools/blender-4.5.15-windows-x64/blender.exe` (the exe is gitignored, so it only exists in the main checkout). Unset it for `test_blender_config`.

## Done and verified (commit after `76a184c`)
- `tools/blender/storyboard_beats.py`: generic builder. `--episode DIR [--beat N] [--force] [--still F] [--out D]`, `--catalog FILE`. Reads `storyboard.json` + `shot_lengths.json` (+ optional `word_timing.json`). Cuts every ~4.5 s with drift; label whose anchor is off screen gets its own 2.4 s close-up shot and the beat is rebuilt (up to 2 repairs).
- `workflow/scenes.json` (20 scenes: params, examples, views, anchors, actions), `workflow/storyboard.py` validator (`python -m workflow.storyboard <episode>`), `python/test_storyboard.py`, `python/test_scene_catalog.py`.
- `work/jensen-huang/storyboard.json`: the 17 beats as data; 0 framing problems in stills; `episode.json` rollout.builder -> generic builder; `tools/rollout_render.py` `builder_args()` adds `--episode`. Hand-written `jensen_huang_beats.py` and its two probes deleted.
- Tests passing: model_library 3, scene_catalog, storyboard, rollout_render, jensen_huang_episode (57 passed).
- Phase 0 so far: `archive_source` `used_urls` was a set read as a dict (44 failures -> ~16).

## Next (in order)
- Phase 4 `tools/plan_storyboard.py`; 5 `tools/qc_script.py`; 6 word timings (feeds `word:` times) + captions + loudness; 7 archive layer; 8 `tools/make_episode.py`; 9 clean-up/docs (stray root files: `qc_findings.txt`, `test_import.py`, `fix_licence.py`, `undefined`, ...).

## Phase 0: DONE (2026-11-15)
- `tsc` clean, 160 TS tests pass. Python: 619 passed, 2 skipped, 0 failed in the main checkout setup (in a worktree: export BLENDER_EXE, junction `.venv` and symlink `node_modules` to the main checkout; `narration-tts` preflight tests need the main checkout's `models/`; `test_blender_config` needs BLENDER_EXE unset).
- Deleted as dead: `tools/archive_source.py` (+ test, style.json `entry_point`), the Artemis builder stack (`artemis_beats.py`, `work/artemis_beats.*`, `bench_beat.py`, `lunar_ground_probe.py`, `techniques/surfaces*.py`, `tools/tile_seams.py`) and their tests (surfaces, regolith, lunar ground, tile seams, Artemis text guards). The "real episode" tests in `test_episode_paths`/`test_qc_episode` now read Jensen. `tools/sourcing/` (transport, providers, download) stays.
- Phase 7 must write the archive sourcing step fresh if still wanted.

## Open defects
- `tools/pipeline_supervisor.py` provisions a placeholder clip for missing archive media: likely cause of the black `boarding-school_part1` shot. Phase 7 makes it an error.
- Narration "GeForce twenty-five-ninety" (should be 256); "personal life" line unsourced; script 3:08 vs 600-900 s; no captions; archive share 10%; 4 loudness jumps at archive cuts.
- "Today" tag in `valuation` close-up sits against the bar (cosmetic).
- Map scene with real coastlines needs a public-domain coastline file: ask the user before downloading.
