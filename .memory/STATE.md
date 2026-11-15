# STATE
- Updated: 2026-11-15 (evening). Work interrupted mid phase 1-2 of `docs/COMPLETION-PLAN.md`.
- User instruction: finish the code first (plan + implement); NO new episode until the pipeline is complete. Jensen episode is the regression fixture only.
- Plan: `docs/COMPLETION-PLAN.md`, 10 phases (0 green baseline, 1 scene catalog, 2 in-beat cuts, 3 storyboard data + generic builder, 4 planner, 5 script gate, 6 sound + captions, 7 archive, 8 one command, 9 clean-up/docs).

## Done and verified
- Model library, explainer look, GPU pilot, Jensen 17 3D beats; master `work/jensen-huang/jensen-huang.mp4` 188.2 s; QC PASS 0 errors 8 warnings; `python/test_model_library.py` 3/3 (run 16:30, before the look.py edits below).

## Written, NOT yet run in Blender
- `tools/blender/models/look.py`: `open_set(seconds)` (world only; `dark_stage` now calls it), `shoot(shots, ...)` (one camera, hard cuts between set-ups, lights/floor from first shot, `st.shots`, `st.taken`), `reserve`, `auto_tag(st, text, pin, start, until, size)` (chooses screen slot, skips off-screen anchors), `pill` accepts a pin object and reports off-screen anchors.
- `tools/blender/models/scenes.py`: 20 parametric scenes in `SCENES` (`chip-teardown`, `graphics-card`, `wafer`, `cores-compare`, `server-racks`, `layer-stack`, `neural-network`, `flow-diagram`, `timeline`, `scale-compare`, `bar-chart`, `line-chart`, `presenter-screen`, `people-row`, `meeting-table`, `org-radial`, `campus`, `pages`, `document`, `statement`). Each returns a `Set` with `views`, `pins` (anchors), `actions` (fn, default start fraction, span), `lens/floor_grid/gain`.
- First check to run: `python -m pytest python/test_model_library.py -q -p no:cacheprovider` (confirms `dark_stage` refactor did not break Jensen beats).

## Next (in order)
- `tools/blender/storyboard_beats.py`: generic builder. Reads `<episode>/storyboard.json` (beat name -> `{scene, params, shots:[{view, labels:[{text, anchor, at}]}], actions:[{name, at}], hud:[...], counter:{...}}`) + `shot_lengths.json`; default shot split every ~4-5 s over the scene's view sequence with drift (radius -6%, azimuth +/-7 deg); `at:<anchor>` close-up view; runs each action once (storyboard time or default); labels via `look.auto_tag`; `at` = fraction or `word:<text>` resolved from narration word timing; same CLI as Jensen builder (`--beat`, `--force`, `--still`, `--out`, plus `--episode`).
- `workflow/scenes.json` (catalog as data: description, params, anchors, views, actions, example) + `workflow/storyboard.py` validator + `python/test_scene_catalog.py` (build every scene from its example in Blender, compare with catalog).
- Express Jensen's 17 beats as `work/jensen-huang/storyboard.json`, point `episode.json` rollout.builder at the generic builder, stills check only (no full render).
- Then phases 4-9 of the plan.

## Baseline failures found (phase 0, not fixed yet)
- Python: `test_archive_source` ~44 (first: missing-episode message asserts old wording), `test_blender_surfaces` 15 + `test_regolith_stipple` 15 + `test_lunar_ground` 8 (errors, missing `media/pbr` tiles), `test_episode_paths` 7, `test_qc_episode` 2, `test_sourcing_transport` 1.
- TypeScript: 9 `tsc` errors (`src/cli.ts` 25, 195; `src/contracts.ts` 130; `src/writer.ts` 135, 136, 142, 152; `tests/writer.test.ts` 273) from Zod 4.

## Open defects
- `tools/pipeline_supervisor.py` provisions a placeholder clip for missing archive media: likely cause of the black `boarding-school_part1` (u004) shot. Phase 7 makes this an error.
- Pilot: "Fan and heatsink" leader crosses the frame at ~4 s (tag follows a part that leaves frame). New off-screen check in `pill` will report it; fix with `until=`.
- Narration "GeForce twenty-five-ninety" (should be 256); "personal life" line unsourced; script 3:08 vs 600-900 s; no captions; archive share 10%; 4 loudness jumps at archive cuts.
- Map scene with real coastlines needs a public-domain coastline file: ask user before downloading.
- Commits: see `git log`; last verified checkpoint `4ee03be`.
