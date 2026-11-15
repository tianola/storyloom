# SDD ledger — plan: F:/AI-PROJECTS/longform-explainer/docs/superpowers/plans/2026-11-09-professional-documentary-workflow.md

Baseline: Node 146/146 PASS; Python 20/20 PASS (2026-11-09).
Spec reachable and read: docs/superpowers/specs/2026-11-09-professional-documentary-workflow-design.md.

Ruling: Work in place because F:/AI-PROJECTS/longform-explainer is not a git repository — worktrees and commit diffs are impossible; use the existing directory, baseline evidence, per-task file inventories, and unified-diff review packages against /dev/null or saved before-copies — wrong choice costs isolation, mitigated by disjoint task paths and no destructive operations.
Ruling: Agent model selection is unavailable in the live Agent schema — inherit the session model as required by the Qoder integration fallback — wrong choice costs efficiency, not correctness.
Ruling: Do not initialize git or create commits merely to satisfy SDD helpers — the user did not request repository creation and the plan forbids commits — wrong choice would add unrequested repository state.

## Preflight interface and conflict scan

| Tasks | Producer → consumer | Finding / ruling |
|---|---|---|
| 1 → 2, 6 | Nine-phase layout, empty manifest, `init_episode()` | Consistent; Task 2 validates the manifest Task 1 creates; Task 6 consumes both. |
| 1, 3 | `workflow/` package files | Disjoint filenames; no conflict. |
| 2 → 6 | Manifest API and purchase-list CLI | Consistent; `--episode work/episode-carrington` resolves `assets/license-manifest.json` and `dist/license-purchase-list.md`. |
| 3 → 5, 6 | `blender_executable()` and accepted 4.5 config | Consistent; 4.5 selection is blocked until render and visual gates pass. |
| 4 → 6 | Four HyperFrames recipe sections | Consistent; recipes are local, deterministic, and reusable. |
| 5 → 6 | Four 3D starter scenes and portable labels | Consistent; Task 6 adds six episode-specific beats rather than reusing starter content blindly. |
| Task 1 internal | Tests vs initializer and files | Consistent; unsafe slugs and existing directories fail before content creation. |
| Task 2 internal | Schema vs report/download/screenshot tests | Consistent; paid-provider behavior remains explicitly unverified by mocks. |
| Task 3 internal | Config fallback vs acceptance protocol | Consistent; `--accept` requires a successful report and follows visual inspection. |
| Task 4 internal | Structural tests vs 16-second composition | Consistent; visual QA remains mandatory. |
| Task 5 internal | Integration tests vs generated Blender scenes | Consistent; real Blender execution is required, not skipped host tests. |
| Task 6 internal | Research, script, media, licensing, QC gates | Consistent; preview-state purchase-list exit 1 is intentional and not a failed build. |

No plan-mandated test-without-assertion or duplicated logic block found.

## Task 1: complete

- Files: `workflow/__init__.py`, `workflow/init_episode.py`, three files under `workflow/templates/`, `python/test_init_episode.py`.
- TDD: RED missing `workflow` module; GREEN focused 2/2 PASS; full Python suite 22/22 PASS with pristine output.
- Review package: `task-1-review.diff` (six new files, unified diffs against `/dev/null`).
- Independent review: spec compliant; task quality Approved; zero Critical and zero Important findings.
- Parked Minor: `python/test_init_episode.py` could additionally assert all metadata values, template headers, blank-title rejection, and CLI behavior. Ruling: leave unchanged because the brief-mandated behavior is implemented and independently approved; broader coverage is optional polish, not a trust blocker.

## Task 2: complete

- Files: sourcing manifest/download/provider/screenshot modules, purchase-report CLI, Python and Node contracts, Playwright dependency manifests.
- Initial TDD: RED missing sourcing package/helper; GREEN focused Python 19/19 and Node 147/147; full suites Python 41/41 and Node 147/147.
- Initial review: spec issues and task quality Needs fixes — unsafe redirect targets could be opened before final-URL validation, and Pexels Authorization could cross origins.
- Fix round 1 used a fresh implementer because the live Agent schema has no resume capability; the original brief/report and exact findings were carried into the dispatch.
- Fix TDD: two focused regressions RED before production changes, GREEN 2/2 after; focused sourcing 21/21; full Python 43/43. Node source was unchanged and its prior 147/147 result stands.
- Scoped re-review: both Important findings FIXED; fix quality Approved; zero new Critical/Important/Minor findings.
- Runtime limits: live providers, remote CDNs, paid preview flows, and remote stock-page accessibility remain explicitly unverified; local Chromium screenshot and local HTTP redirect behavior are tested.
- Parked Minor: atomic no-clobber publication has a concurrent TOCTOU race. Ruling: not a task blocker in the current solo local workflow; do not broaden the approved fix.
- Separate remediation tracking: pre-existing Zod 3.25.76 advisory GHSA-mrhx-c7xc-m3w5 remains; breaking Zod 4 upgrade was not applied inside this unrelated task.

## Task 3: complete

- Files: `workflow/config.py`, `workflow/blender.json`, `tools/blender/verification_beat.py`, `tools/blender/verify_upgrade.py`, `tools/blender/install_commotion.py`, `python/test_blender_config.py`.
- TDD: RED missing `workflow.config` module; GREEN 1/1 config contract; full Python 44/44 PASS.
- Real Blender verification: same procedural beat rendered on 4.1.0 (EEVEE legacy, 4.978 s wall) and 4.5.15 LTS (EEVEE Next, 19.259 s wall); side-by-side PNG inspected visually — both frames complete, lit, no geometry corruption; 4.5 shows cleaner glossy reflections and less grain. Acceptance via `--accept` only after visual inspection.
- Commotion 2.5.0 installed into isolated portable 4.5 config, verified in second process: `enabled: true`, import succeeded, `Scene.commotion` property registered.
- Production selection: `workflow/blender.json` now selects `tools/blender-4.5.15-windows-x64/blender.exe`. `BLENDER_EXE` env still overrides; removing the config restores 4.1 fallback.
- Review: spec compliant; task quality Approved; no Critical or Important findings.
- Parked Minor: 32-sample glass dither visible in both renders; higher-sample production look development deferred. Commotion legacy `bl_info` warning is non-blocking. Blender 5.2.3 not tested.
- Detailed report: `task-3-report.md`. No paid calls, uploads, publication, git initialization, or commits occurred.
- GPU recommendation (researched 2026-11-09): Sapphire RX 590 8GB Nitro+ is the best choice for this work — mature HIP backend, 8 GB VRAM, ~10-15% faster than RX 580. Arc A380 not recommended (oneAPI early-stage, 6 GB VRAM limit).

## Task 4: complete

- Files: `work/shot-recipes/index.html`, `work/shot-recipes/project.json`, `work/shot-recipes/assets/gsap.min.js`, `work/shot-recipes/assets/archival-plate.svg`, `work/shot-recipes/qa/.gitkeep`, `tests/shot-recipes.test.ts`.
- TDD: RED 13/13 fail (ENOENT on missing HTML); GREEN 13/13 pass.
- Four shot recipes: recreated-ui (0-4s, semantic HTML + typewriter + cursor + blockquote highlight), kinetic-quote (4-8s, word-by-word reveal + source card), ken-burns (8-12s, SVG plate + scale/pan + vignette), news-lower-third (12-16s, gradient bg + publisher/title/date card).
- HyperFrames lint: 0 errors, 4 advisory warnings (nested_structure — same pattern as showpiece-house).
- Full regression: Node 160/160, Python 44/44.
- Review: spec compliant; task quality Approved; 4 Minor findings (SVG text sizes, no runtime timeline test, broad test regexes, lint warnings) — none blocking.
- Parked Minors: SVG plate text at 12-18px user units (simulates scanned document, not UI annotation); broad regex patterns functional but not maximally precise; lint advisories deferred to future refactor.
- Detailed report: `task-4-report.md`. No external HTTP assets, no commits, no uploads.

## Task 5: complete

- Files: `tools/blender/techniques/common.py`, `tools/blender/techniques/labels.py`, `tools/blender/techniques/build.py`, `tools/blender/techniques/validate.py`, `tools/blender/techniques/__init__.py`, `python/test_blender_techniques.py`.
- Output: `work/technique-pack/cutaway.blend`, `work/technique-pack/exploded.blend`, `work/technique-pack/xray.blend`, `work/technique-pack/zoom-inside.blend`, four midpoint PNGs.
- TDD: RED 8/8 fail (missing builder module); GREEN 8/8 pass in 7.7s.
- Four techniques: cutaway (Boolean cutter + label), exploded (≥4 named parts + separation), xray (Transparent BSDF mix + animated factor), zoom-inside (camera dolly keyframes at frames 1 and 150).
- Full regression: Python 52/52, npm 160/160.
- Visual inspection: all four midpoint PNGs verified — cuts visible, parts readable, internal mechanism visible through ghost shell, camera ends inside structure.
- Render times: cutaway 2.37s, exploded 0.15s, xray 0.59s, zoom-inside 0.85s (EEVEE Next, RX 580).
- Review: spec compliant; task quality Approved with Minor Findings.
- Parked Minors: (1) cutaway interior visibility — inner rings/gears not clearly visible at frame 75, camera angle or cutter size needs adjustment; (2) zoom-inside label visibility — "INNER STRUCTURE" label not visible in midpoint render, likely off-screen due to camera position.
- Workarounds accepted: Geometry Nodes EXPLODE modifier uses direct location keyframes instead of Factor input (API limitation); AgX grain at 32 samples (starter-scene verification, not production look).
- Detailed report: `task-5-report.md`. No external HTTP assets, no commits, no uploads.
- Second brain updated: STATUS.md + INDEX.md.

## Task 6: complete

- Files: Complete nine-phase episode at `work/episode-carrington/` with research (facts.json, 25 claims), story (beat-sheet.md, 14 beats), script (narration.md, 96 utterances), assets (license-manifest.json, 12 entries), vo (Kokoro TTS), motion (HyperFrames + Blender), edit (cumulative-frame assembly), qc (timing tests), dist (preview MP4, purchase list, metadata, thumbnail).
- Preview: `work/episode-carrington/dist/episode-carrington-preview.mp4` — 1920x1080, H.264, 30fps, AAC, 745.6s (12.4 min), 11.2 MB.
- License gate: 3 preview assets (Wikimedia) require purchase; 9 free/project-owned assets cleared. `python tools/manifest_report.py --episode work/episode-carrington` exits 1 as intended.
- Purchase list: `work/episode-carrington/dist/license-purchase-list.md` — grouped by provider with asset IDs, URLs, and attribution.
- Full regression: Python 52/52, npm 160/160 (212 total tests pass).
- Evidence quality: 25 claims with correct confidence labeling (17 high, 8 medium), no unsupported dramatic claims, citations map to pilot-research.md sources.
- Six detailed 3D beats specified (solar flare, CME travel, magnetosphere, GIC, telegraph, transformer) — shot count is 96 vs. 180-216 target; implementer flagged post-preview subdivision as next step.
- Review: spec compliant; task quality Approved with Minor Findings.
- Parked Minors: (1) shot count below target (post-preview activity); (2) license manifest schema deviations ("PD" vs "public-domain", "free" vs "purchased"); (3) narration.md vs JSON text drift; (4) no LUFS measurement; (5) thumbnail is non-representative dark navy frame.
- Status: DONE_WITH_CONCERNS — preview-state delivery complete, user must purchase licenses and review preview before upload.
- Detailed report: `task-6-report.md`. No paid calls, uploads, publication, git initialization, or commits occurred.
- Second brain updated: STATUS.md + INDEX.md.
