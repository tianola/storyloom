# STATE
- Updated: 2026-11-15 16:35.
- Done: model library `tools/blender/models/` (`kit`, `hardware`, `sets`, `look`); explainer look (dark stage, bloom, DOF, screen rig, pill tags, HUD counters, signal-trace material); GPU dive pilot; all Jensen beats on the explainer look; 17 3D beats, 2 archive shots, 0 cards; tags at 0.056 of frame height.
- Verified 16:30 (17-beat version): all 17 beats rendered `--force`; `python/test_model_library.py` 3/3; assembly exit 0; master `work/jensen-huang/jensen-huang.mp4` 188.2 s 1080p; `qc_episode.py` PASS, 0 errors, 8 warnings (2 `archival_shot_long`, `archive_share_low` 0.102, 4 `cut_loudness_jump`, `no_captions`). Tags legible and in frame on contact sheet of all 19 segments.
- Pilot `work/explainer-pilot/inside-gpu.mp4` re-rendered; cooler exits back-left. Defect: at ~4 s the "Fan and heatsink" leader line runs across the frame to the bottom-right instead of ending on the cooler (tag follows a part that leaves the frame). Last 5 s are bright but not clipped.
- Reviewed only by contact sheets, never played in real time.
- Open defects: `boarding-school_part1` (u004) archive shot renders black with credit only; narration says "GeForce twenty-five-ninety" (should be 256); "personal life" line unsourced; no captions; archive share 10% vs 20% floor; loudness jumps at 4 archive boundaries; script 3:08 vs 600-900 s target; 107 pre-existing Python test failures (`test_archive_source` 44, missing `media/pbr` tiles 38, others); 9 `tsc` errors from Zod 4.
- `valuation` columns and `wall-street` line are illustrative shapes, not per-year data.
- Commits: `d4132e4`, `707c6d7`, `6509e8d`, `9afa319`, `ee08609`, baseline `748657b`.
- Next: fix pilot leader (hide tag with `until=` before the cooler leaves, or anchor to a fixed point); captions (word-by-word); fix narration error + re-TTS; boarding-school archive shot; longer script.
