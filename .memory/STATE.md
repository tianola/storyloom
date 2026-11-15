# STATE
- Updated: 2026-11-15 (late).
- Done: model library `tools/blender/models/` (`kit`, `hardware`, `sets`, `look`); explainer look (dark stage, bloom, DOF, screen rig, pill tags, HUD counters, signal-trace material); GPU dive pilot; all Jensen beats on the explainer look; 4 placeholder cards replaced by 3D beats (`valuation`, `founding-team`, `wall-street`, `headlines`) -> 17 3D beats, 2 archive shots, 0 cards; tags enlarged to 0.056 of frame height.
- Verified earlier today (13-beat version): `python/test_model_library.py` 3/3; assembly exit 0; `qc_episode.py` PASS, 0 errors, 8 warnings. The old `arch-001b` timecode failure did NOT recur.
- Running now (background, ~90 min from ~15:10): render 17 beats `--force` -> pilot -> clear `segments/` -> assemble -> QC. Logs: `work/jensen-huang/qc/render-models.log`, `work/explainer-pilot-render.log`, `work/jensen-huang/qc/assemble-models.log`, `work/jensen-huang/qc/qc-episode-models.json`.
- Not verified yet: 17-beat master, enlarged tags at full res, pilot with cooler exiting back-left, test with 17 beats.
- Open defects: `boarding-school_part1` archive shot renders black; narration says "GeForce twenty-five-ninety" (should be 256); "personal life" line is unsourced; no captions; archive share 10% vs 20% floor; loudness jumps at 4 archive boundaries; 107 pre-existing Python test failures (`test_archive_source` 44, missing `media/pbr` tiles 38, others); 9 `tsc` errors from Zod 4.
- `valuation` columns and `wall-street` line are illustrative shapes, not per-year data.
- Commits: `707c6d7`, `6509e8d`, `9afa319`, `ee08609`, baseline `748657b`.
- Next: when the background chain ends, check contact sheets of master + pilot, rerun the model test, read QC; then captions (word-by-word), fix narration error + re-TTS, boarding-school archive shot.
