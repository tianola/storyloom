# STATE
- Updated: 2026-11-15 (night). Phases 1-3 of `docs/COMPLETION-PLAN.md` done and verified; phase 0 partly done.
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
- Finish phase 0 (see below).

## Baseline failures left (phase 0)
- `test_archive_source` ~16: `_replace_missing_bytes` undefined (archive_source.py:783), `already['licence']` KeyError (:777), `tools/sourcing/rights.py` does not exist (#149b half-done refactor; decide: finish or delete), ordering/fixture mismatches.
- `test_blender_surfaces` 15 + `test_regolith_stipple` 15 + `test_lunar_ground` 8: missing `media/pbr` tiles (ignored media; worktree lacks them). `test_manim_labels` 3, `test_episode_paths` 7 and `test_qc_episode` 2 need `work/episode-artemis-ii` (ignored files). `test_skills_map`, `test_pattern_library`, `test_sourcing_transport` 1 each, `test_blender_config` fails only when BLENDER_EXE is set.
- TypeScript: 9 `tsc` errors from Zod 4 (`src/cli.ts` 25, 195; `src/contracts.ts` 130; `src/writer.ts` 135, 136, 142, 152; `tests/writer.test.ts` 273).

## Open defects
- `tools/pipeline_supervisor.py` provisions a placeholder clip for missing archive media: likely cause of the black `boarding-school_part1` shot. Phase 7 makes it an error.
- Narration "GeForce twenty-five-ninety" (should be 256); "personal life" line unsourced; script 3:08 vs 600-900 s; no captions; archive share 10%; 4 loudness jumps at archive cuts.
- "Today" tag in `valuation` close-up sits against the bar (cosmetic).
- Map scene with real coastlines needs a public-domain coastline file: ask the user before downloading.
