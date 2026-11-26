# STATE
## 2026-11-26 (later): track B polish, branch `claude/semmelweis-mpfb-polish` (draft PR, not merged)
- PR #8 is merged. This branch fixes the weak points of the 2:33 MPFB2 test:
  - `human3d.idle`: breathing, weight shift and head motion (F-curve modifiers, seeded per person). `human3d.blinks`: the eyes-closed key. `human3d.talk`: syllable-rate mouth flaps from mouth_timing.json (shape keys Exp_mouthOpenHalf/Open/OpenLarge). The narrator in beat 01 and the mother in beat 06 move their lips.
  - The point pose is held lower (`human3d.SOFTEN`), so sleeves no longer fan out.
  - `asylum` param `night_key` (moon fill, stronger lantern, gate key, exposure 0.55). Beat 01 shows the narrator 0-6 s and 12.9-16 s.
  - New vienna view `court-near`. Beat 07 shows the midwife at about 2/3 of the frame.
  - Hospital sets: window surrounds, sills, glazing bars, string courses, plinth; panelled clinic doors and gate. Dissecting room: herringbone floor, panelling, table legs and apron, sheet over head and feet. New asset rules: anat-floor, anat-panel, akh-plinth, door-panel. No new downloads.
- Video: `work/semmelweis-10min/renders/polish/semmelweis-first2min-polish-720p.mp4` (153 s). Before/after stills: `renders/polish/review/{before,after}-tNNNs.png`. All framing reports are empty.
- Tests: pytest python/ gives 936 passed, 24 skipped, and 2 failed. The 2 failures (test_pattern_library and test_skills_map, which create a new episode) are refused by the preflight because the worktree has no kokoro, manim or Blender. Scene catalog and storyboard tests pass with BLENDER_EXE.
- Still weak: the people stand in place (no gestures while talking, no eye direction); faces are softly lit and a little waxy; beats 03 and 05 still have no people; the beat-01 narrator sits low in the frame; the town houses and the asylum are still box-built; the sheet in beat 08 reads as a pillow.

## 2026-11-26: track B, MPFB2 people rendered (branch `claude/semmelweis-mpfb-render`, draft PR)
- PRs #4, #5, #6 are merged into `main` (fba96c9). PR #5 brought the MPFB2 people (`tools/blender/human3d_mpfb.py`, `tools/human3d_assets.py`, docs/human3d-mpfb.md, credits in docs/human3d-credits.md).
- On the PC: MPFB 2.0.18 is installed in Blender 4.5 (`bl_ext.user_default.mpfb`); the assets (about 2 GB, CC0 + CC-BY 4.0) are in the main checkout's `assets/makehuman/` (git-ignored). The 6 roles × 3 variants build on 4.5 with no code change (MPFB logs harmless node-socket errors from its eye shader). Lineup: `work/semmelweis-10min/renders/people.png`.
- Branch `claude/semmelweis-mpfb-render` (not merged) holds: the placement code an earlier PC session left uncommitted (`place_human3d` places people by real size and distance; anatomy roof, steady wing lamps, shadow pool, scenes.json), and storyboard fixes for beats 01/02/04/08 (02 and 04 hold one view, 08 cuts to the jars at 9 s, the beat-01 narrator bust is larger).
- Rendered (720p, `SEMMELWEIS_720=1`): `work/semmelweis-10min/renders/mpfb/beat-01..08.mp4`, all framing reports empty. 2-minute test: `work/semmelweis-10min/renders/mpfb/semmelweis-first2min-mpfb-720p.mp4` (153 s: beats concatenated + the first 153 s of `vo/full-audio-finished.wav`, 1.5 s fade). Review stills in `renders/mpfb/review/`.
- Weak still: the people stand stiffly (no lip sync, faces are not animated, little torso motion); beat 01 is dark and the narrator shows for only ~2 s; beat 07's court shot is wide, so the midwife is small; beats 03 and 05 have no people; the sets are box-built.
- Worktree setup note: a fresh worktree needs `assets/polyhaven/` (copied from another worktree, 60 MB) and the episode inputs (vo/, music/, shot_lengths.json, word_timing.json and so on; not in git).

- Updated: 2026-11-25. PR #2 and PR #3 are MERGED into `main` (2026-11-25 ~18:36 UTC); no open PRs. Two tracks are open (next section). Older sections below are history; where they say "NOT PUSHED" or "PR #2 is open", read them as superseded by this section.

## 2026-11-25: where things stand (reconciled against GitHub)
- `main` = 0b0301c. Branch `claude/semmelweis-v6` (6fe449d) is merged through PR #3; PR #2 (v4/v5 pilot, fd0ddcb) is merged too. The v6 commit 7955e5a is therefore on `main`, pushed.
- **Track A, pixel pilot v6 (`work/semmelweis-pilot/`):** code, sprites and `cut.json` (51 shots) are done and tested. The steps under "Still to do (in order)" in the v6 section below are still open, with these facts checked on 2026-11-25:
  - `storyboard.json` is still the v5 one (7 beats: vienna, ward); the v6 storyboard is not written;
  - `cut.json` s22 still points at `v6-07-vienna`; the re-grouping (step 3) is not done;
  - no v6 render, assemble or QC has been run; `qc/pilot-gate-status.md` still describes v5;
  - the security review is still incomplete (HTTP 401).
- **Track B, 3D people test (commit 6fe449d, PR #3):** rigged 3D characters (CharMorph database, Rigify rig, CMU mocap) in `tools/blender/human3d_{build,poses,mocap}.py` and `tools/blender/models/human3d.py`; `storyboard_beats.place_human3d` handles cast entries with `"render": "3d"`; `SEMMELWEIS_720=1` renders at 720p. First test: `work/semmelweis-10min/storyboard.json` (33 beats; beats 01-07 use 3D people).
  - Status: experimental. Garments are shells with gaps, sets are still box-built, the walk has no torso motion, and kneel is a seated pose.
  - The CharMorph database (AGPL-3 models) and the built `.blend` files are NOT in the repo. Check the licence terms before publishing any video that uses them.
- Decision still open for the user: finish track A first (recommended: one complete reference video) or move on with track B.
- Environment note: renders, ElevenLabs voices and Blender run only on the user's Windows PC (`F:/AI-PROJECTS/longform-explainer`), not in the cloud container.

(Previous header, 2026-11-22: Updated: 2026-11-22 (late). Current work: **Semmelweis pilot v6**, the visual-storytelling and retention pass, on branch `claude/semmelweis-v6` (next section). v5 and everything below it are history.)

## 2026-11-22: pilot v6, directing pass + edit architecture (COMMITTED as 7955e5a, NOT PUSHED, branch `claude/semmelweis-v6`)
### Status after commit 7955e5a (2026-11-22, late)
- Commit `7955e5a` on `claude/semmelweis-v6`, parent `fd0ddcb` (the PR #2 head). 78 files. NOT pushed; the push and any PR wait for the user's approval.
- Left out of the commit on purpose (untracked): `.agents/`, `work/semmelweis-pilot/v5-backup/`, and two files in `work/semmelweis-pilot/vo/eleven-cache/`.
- Tests with `BLENDER_EXE` set (`tools/blender-4.5.15-windows-x64/blender.exe` in the main checkout): full suite 932 passed, 2 skipped. Without `BLENDER_EXE`, 7 Blender-only tests error, because `workflow/blender.json` points at that exe, which is absent in the worktree. Those are environment errors, not code failures.
- Security review: INCOMPLETE. The plugin's API key was rejected (HTTP 401, `invalid x-api-key`), so there was no verdict, and it covered only 2 changed files. Our own audit found no secret patterns, no new network calls, and subprocess calls only with argument lists. Re-run it with valid credentials before pushing.
- Scene catalog: `board`, `ledger` and `wing` added. `vienna` and `ward` gained the v6 views and anchors, and their descriptions now mention the v6 framings the code comments describe. The `sickbed` view has no description in the code, so none was written for it.
- Still to do (in order; sprites are DONE): the cut re-grouping, storyboard.json for v6, captions and lengths, the Blender checks and renders, assemble and QC, and the gate-status doc. The PR waits for the user.

### Approved by the user ("Εγκρίνω, ξεκίνα")
- The proposal in `work/semmelweis-pilot/directing/`:
  - `visual-pass.md` is the master document: critique, hook maths, the Fern/Veritasium modes, board moments H1–H5, curiosity loops 0/A/B/C/K, sequence vs shot, the 51-shot list, mute test, provenance, assets, the graphics spec, the timing schema and the validation report (59/59).
  - Also `cut.proposed.json`, `storyboard.proposed.json`, `timeline.png`, `narration.proposed.md`.
  - `build_proposal.py` builds the proposal; `validate_proposal.py` checks it and was mutation-tested.
- The two new lines:
  - u003 "The hospital has two maternity clinics. In the first, one mother in nine dies. Yet in the second, it's one in thirty six."
  - u005 "They take women in on alternate days."
  - "Yet" was added for `qc_script`'s 20 s hook rule.
- The architecture: cut list, legacy adapter, graphics, compositing. The plan is `C:/Users/thana/.claude/plans/keen-dazzling-dewdrop.md`.
- Rules for this pass:
  - redesign freely;
  - graphics stream frames to ffmpeg, never held in RAM;
  - cheap subagents do the easy work, Opus does the complex work and the verification.

### Done and verified (tests green)
- **`tools/edit/cutlist.py`**, the timing schema. `python/test_cutlist.py` has 37 tests.
  - One film clock; `frame(t)=round(t*fps)` (Python round, as `build_segments` does).
  - Anchors: `line:uNNN[:end]`, `word:<w>@uNNN[#n][:end]`, or seconds. A word cut leads by 2 frames. A missing word is an error.
  - `resolve()`:
    - consecutive in-points per run of one source;
    - an `n//2` transition head on the incoming source;
    - `via` waypoints for a held move through several views;
    - `at_params` for beat params timed on words.
  - `validate()` checks: gap, overlap, off_frame, too_short, provenance, archive_long (6.0 s, with half of each transition counted), archive_speed, transition bounds, overlay_outside, transition_overlap, handle, beat_reused.
  - Other functions:
    - `render_plan()`: abutting segments and transition pieces, with a piece of `n` frames at `[f-n//2, f-n//2+n)`;
    - `source_seconds_needed`, `beat_shots`, `beat_params`, `beat_spans`, `audio_events` (J/L cuts), `card_hold`, `line_clock`, `episode_cut`.
- **`tools/edit/legacy.py`**: turns `shots.json` into a resolved cut. `python/test_legacy.py` shows ask-chatgpt, jensen-huang and v5 semmelweis (from `v5-backup/vo`) cut to the same frames as `build_segments`; seeks agree within half a frame.
- **`tools/edit/assemble.py`**, the cut-mode assembler:
  - `resolve_episode` refuses a cut with findings; `publish` writes `cut.resolved.json`;
  - `write_lengths` writes `shot_lengths.json` (handles in) and `sync_storyboard` writes the beat shot times and `at_params` into `storyboard.json` as `"<n>s"`;
  - `prepare_sources` covers 3D beats, archive stills on the mat (`frame: archive_mat`), graphics, and black;
  - `draw_overlays` writes alpha .mov clips;
  - `build_pieces` runs one ffmpeg call per piece, cached, then a copy-concat.
- **`tools/assemble_episode.py`**:
  - `edit_mode()` returns "cut" if `cut.json` exists, else "legacy"; legacy is unchanged;
  - `assemble_cut()`, and `pad_audio()`, which pads the voice to the film length so the black tail survives `-shortest`;
  - the duplicate imports are removed.
- **`tools/compose/`** (Sonnet): pure ffmpeg argv builders; `python/test_compose.py` has 14 frame-exact tests.
  - Dip is a custom xfade expression, because ffmpeg 9's `fadeblack` is lopsided.
  - Import with `import compose`, tools/ on sys.path.
- **`tools/graphics/`** (Sonnet; interrupted by the usage limit, but its 70 tests pass):
  - `graphics` tokens in `workflow/style.json`, `docs/graphics.md`, `gallery.py`;
  - families: stats (tally, ratio_compare...), grids, timelines, maps (map_plan, always tagged "schematic"), boards, split, archive (archive_mat, source_card, `card_lines`, moved here; `archive_ingest` re-exports it), labels (date_stamp, day_labels...);
  - `encode.stream_to_mp4` uses a temp file and renames on success; presets `ratio-1846` and `ward-plan-routes`.
  - NOT yet verified by Opus: the gallery PNG, the memory (tracemalloc) test, and the API names that `edit/assemble.draw_graphic` uses (`graphics.get`, `presets.PRESETS`, `tokens.load_tokens`, `encode.stream_to_mp4(canvas=, alpha=)`, `frame_at(spec, t, canvas=, tokens=)`).
- **Cut-aware readers** (legacy unchanged):
  - `workflow/episode.py`: `cut_path`, `resolved_cut`, and `cut_shots`, so `shots()` returns `{shot id: (kind, name)}` for a cut episode;
  - `audio_finish`;
  - `sound_design.plan_events_from_cut`, with a `bell()` synth for the J-cut;
  - `qc_episode` (load_timeline, coverage through `Shot.lines`, known_cuts);
  - `captions.beat_word_timing`, `lip_sync`, `plan_storyboard`;
  - `make_episode.shot_table()`; the shots stage is a no-op for a cut episode.
  - Tests: `python/test_cut_sound.py`.
- **`workflow/storyboard.when()`** accepts `"<n>s"`. A bare number ≤ 1.0 still means a fraction of the beat, which is a trap for cut times.
- **Episode data:**
  - v5 is backed up in `work/semmelweis-pilot/v5-backup/`;
  - `script/narration.md` holds the approved text;
  - claims: u003 [c5,c7], u004 = old u003, u005 [c6], u006 = old u005; `story.json` question u004;
  - `qc_script` shows only the known pilot errors (length, payoff).
- **Voice:** credits were spent on the 2 new lines only.
  - New u004 = old u003 and new u006 = old u005, byte for byte; u007–u029 unchanged.
  - Narration runs 151.11 s; "nine" is heard at about 15.5 s and "thirty six" at about 18.6 s.
- **`work/semmelweis-pilot/cut.json`**: 51 shots, tail 1.0 s. It resolves clean against the new voice: 152.10 s, median 2.5 s, 22% under 1.5 s, s46 held for 23.3 s.

### In progress (code written, NOT run in Blender yet)
- **`tools/blender/models/clinic.py`** (registered in `scenes.py`):
  - `board`: stages h1/h2/h3/air/position/fear/h4; actions flip/lay/pin/pull; views h1-low34, h1-calendar, h2-close, h3-top, h4-ots, h4-turn, card-air/-position/-fear.
  - `ledger`: columns clinics or street; action tally; views ledger and ledger-street.
  - `wing`: the ward with its far door open, a corridor, and the anatomy room at x≈43.4; doctors walk from the table to the bed; views wing-table, wing-door, wing-corridor, wing-ward-door, wing-aisle, wing-ward-bed, wing-hands.
- **`world.py`:**
  - ward params `through`, `lie`, `side_bed`, `bell`, `bell_route` (aisle/side), `turn`; views second-bed, semmelweis-close, hands-window, semmelweis-hands, hands-door, sickbed;
  - anatomy `people` / `west_door`, a scalpel and drop with action `slip` (vienna `slip: true`, `anatomy_people`);
  - vienna: second-door now matched to first-door; views gate-approach, street-birth, scalpel, cut-hand.
- **`storyboard_beats.place_actor`**: a cast member may take `size` (bed or hands) and `depth`.
- **Pixel sprites** (Sonnet, interrupted):
  - `tools/pixel/people.py` and `sprites.json` now hold kneel, give-birth, look-hands, bed lie-side and sick, and a hands size (open, reach, hold);
  - 2 tests FAIL in `test_people_sprites` (Clergy.test_new_cast_and_poses, NewPoses.test_faces_work_in_the_new_poses);
  - the contact sheet isn't reviewed.

### Still to do (in order)
1. Sprites: DONE in 7955e5a. Both failing tests fixed (test_people_sprites: 19 OK); the contact sheet was viewed; atlas layouts match the cell sizes for hands and bed (each layout is the cell plus a 2 px border).
2. Graphics: verify the gallery, the memory test and the `draw_graphic` API match.
3. Re-group beats in `cut.json` so the inserts get light scenes:
   - s22 → `v6-07b-ledger`, s26 → `v6-09b-ledger`, s27 → `v6-09c-vienna`;
   - s30 and s38 on the ledger scene;
   - s45 its own ward beat (sickbed);
   - s46 `via`: wing-door at u022 "same", wing-corridor at u023 "Now", wing-ward-door at u024 "same", wing-aisle at u024 "mothers", wing-ward-bed at u025 "With", wing-hands at u025 "hands";
   - plus `at_params` walk_from/walk_to; `wing` must parse `"<n>s"`.
4. Write `storyboard.json` for v6, one beat per 3D source. Take the scene, params, cast and acts from `visual-pass.md` §8 and `storyboard.proposed.json`:
   - the board stages, and the explorer per H-moment;
   - the arrival, the doctor explaining, the students from anatomy, the porter and the kneeling mother, the street birth;
   - the ward lie/turn/bell_route params;
   - actions on words (flip "which", tally, turn, bell, slip, pull);
   - Kolletschka in bed (size bed, pose sick); the hands casts.
   - Then `plan_storyboard --check`.
5. `make_episode --only captions,lengths` writes `cut.resolved.json`, `shot_lengths.json`, `word_timing.json` and the storyboard sync.
6. Blender:
   - `storyboard_beats.py --check`, then `--still` for every new view; LOOK at them and tune the views and cast points;
   - render the beats, one Blender run at a time.
7. `make_episode --only assemble,qc`. Check the hook, the mute test and archive ≤ 6 s on the master. QC PASS with no gate loosened.
8. Run the full tests with BLENDER_EXE; update `qc/pilot-gate-status.md`.
9. Commit on `claude/semmelweis-v6` (branched from the PR #2 head, fd0ddcb) and open a PR, but only when the user says so.
- Gaps to report to the user:
  - the hands are a sprite, not a model;
  - the cut on the hand is shown as a drop of blood on the sheet;
  - the board text is Blender text, not the graphics card textures.

## 2026-11-22: pilot v5, natural narration and real archive (PR tianola/storyloom#2)
- **User feedback (2026-11-21):** "The narration must sound like someone telling you a story, not someone reading a script… make the viewer wonder, form their own guess, and then find out they were wrong." Don't make it more dramatic.
- **Study:** Fern and Veritasium, in `docs/research/narration-voice.md` (12 rules). The short form is in the story-film skill, `references/script.md` §5 "Telling, not reading".
- **Voice:** a blend.
  - The scenes are told Fern-style: third person, present tense.
  - The explorer turns to the viewer Veritasium-style at the guess and at the reveal.
- **New script:** 29 lines and 436 words; the user approved the text before any voice was spent.
  - The story runs: the puzzle of the two clinics → "what would you check first?" → the guesses fail → Kolletschka → the hands.
  - `story.json`: guess u002, question u003, reversal u013; the hook kind is mystery.
- **Archive:** three Commons stills (`pd_expired`) with Ken Burns moves and credit plates: the hospital engraving (u001), the Semmelweis portrait (u010), the Kolletschka portrait (u020).
- **Fixes:**
  - the jpg ingest, which used `ffmpeg -ss` on an image and got no frame;
  - credit plates now wrap inside the margins (`card_lines`);
  - the HUD label moved clear of a bollard. Moving the HUD nearer the lens is not an option: depth of field would blur it.
  - the cut rhythm (beat-02 is a 20.5 s held glide, beat-05 and beat-06 are montages);
  - the midwife's walk start.
- **Result:** QC PASS. Advisories: two archival holds over 6 s and one slow drift. Details in `qc/pilot-gate-status.md`.
- **Open:**
  - the user hasn't said whether to merge PR #2;
  - whether a line that mentions the 1861 book should bring arch-003 back;
  - what to do with the stray `.agents/` folder (ask the user; don't delete it).

## 2026-11-21 (uncommitted): living-world films, Semmelweis pilot
### Decided (user)
- Films must feel like a movie in a living world, not a presentation:
  - the explorer narrates on screen with a moving mouth;
  - a human story carries the science;
  - the town keeps moving: lights, walkers, smoke;
  - the protagonist speaks and thinks in his own voice.
- Topic: Ignaz Semmelweis. Make a 60-90 s pilot first; the user reviews it before any full film.
- Plan in English: `C:\Users\thana\.claude\plans\abundant-questing-volcano.md` (approved).
- Voices: Kokoro was rejected ("bad"), so narration uses ElevenLabs v3. The user bought **Starter** (38,530 characters a month, commercial use). Chosen cast in `script/cast.json`:
  - narrator/explorer: the user's own clone "yung goofy man" (`VKTXURQy46dy2BlsOQmv`); use it for the explorer in every film;
  - Semmelweis: Lajos, Hungarian accent (`tMSJwjBGNGcJ7WVIJhg4`);
  - mother: Ana (`rCmVtv8cYU60uhlsOo1M`).
  - Rejected: Sarah, George, Lily, plus the other candidates in `vo/auditions2/`.
- The key lives only in the env var `ELEVENLABS_API_KEY` or the git-ignored `.env.local`. Never print or commit it. The user pasted it in chat, so advise rotating it.
- The user is at the PC: give file paths, don't send files.

### 2026-11-21 late: pilot v4 (committed, PR tianola/storyloom#1)
- Poly Haven CC0 assets: `workflow/assets.json`, `tools/fetch_assets.py`, `tools/blender/models/assets.py` (textured materials tinted to the palette, HDRI light, glTF props); scene param `assets` (default true).
- `camera_plan.govern_travel`: a too-fast travel lands short instead of rushing.
- Faster cutaways pass the cut-rhythm gate; the empty beat-05 `at:bell` cutaway became `ward-bed`.
- Master 116 s, QC PASS (0 errors, 2 deliberate slow_shot warnings).
- Six user-downloaded CC0 packs extracted to `assets/kenney/`, `assets/quaternius/` (git-ignored, recorded in `assets/packs.json`), not wired yet.
- A session interruption kills detached Blender too: after one, re-render only the missing beat with `--beat`.

### Built (all tests pass, 723, except the 7 known Blender-env errors)
- Narration syntax: `[name] text` (spoken on screen), `[name:thought] text` (inner voice, no mouth), `{direction}` (sent to v3 as `[direction]`, stripped from captions and QC).
- New episode files: `script/cast.json`, `pronounce.json` (Kokoro only), `dramatisation.json` (claim basis and imagined part for every character line).
- `python/eleven.py`: ElevenEngine, `/with-timestamps`, pcm_24000, cache in `vo/eleven-cache`, alignment written to `vo/<id>.align.json`.
- `narrate.py`: a voice per line. `word_marks.py`: exact marks from the alignment. `qc_script.check_cast`.
- `make_episode`: per-line voices; the captions stage also runs `tools/lip_sync.py`, which writes `mouth_timing.json`.
- Talking pixel people `tools/pixel/people.py`:
  - 13 characters, with mouths, eyes, expressions and poses, plus busts;
  - contact sheet from `tools/pixel/sheet.py`;
  - `workflow/sprites.json` mirrors the registry.
- Blender `characters.py`: atlas actors; CONSTANT mapping keys from `EVENTS`/`compile_cells`; walk, talk, blinks; camera tracking.
- `tools/blender/models/world.py`:
  - scenes `vienna` (dusk/night/dawn sky, lit windows switching, lamplighter, smoke, walkers greeting, hospital with a lit room, clinic doors, anatomy room) and `asylum`;
  - bpy-free schedules in `world_plan.py`;
  - `look.shoot(lighting="world")`;
  - shot key `"glide": "log"` for the aerial-to-window descent.
- Storyboard cast keys: speaker, pose, face, acts, blink, bust, span.
- Pilot: 19 lines, sourced claims c1-c15, 7 beats with hand-written `shots.json`/`storyboard.json`, about 100 s with the new voices. The storyboard was retimed to the new beat lengths: 19/11/26/18/5/18/6 s.
- Script gate: only the 2 expected pilot errors, `length` and `payoff` (the pilot ends on the question).

### Done 2026-11-21 afternoon
- The master `work/semmelweis-pilot/semmelweis-pilot.mp4` (99.7 s) passes QC: 0 errors, 2 warnings.
  - `empty_shot` at 13.1 s: the night `bars` shot is almost black; fix it.
  - `slow_shot` u003 is deliberate.
- `qc/pilot-gate-status.md` is written. Contact sheet: `qc/final/contact.png`.

### 2026-11-21 evening: "empty and slow" fix (user said "yes, all")
- Pace:
  - per-cast `speed` in cast.json (narrator 1.15, Semmelweis 1.1, mother 1.05);
  - `eleven.tighten` caps pauses at 0.4 s and trims the edges, and the alignment is moved to match.
  - Narration went from 99.7 to 87.8 s.
- World dressing (`world.py`):
  - facades: plinths, pilasters, window heads, glazing bars, shutters, balconies, shop awnings and signs;
  - street: market stalls with sellers and buyers, pushed handcarts, clutter, a pump, trees, laundry, birds, talking groups (`world_plan.chatter`/`street_groups`);
  - court: cobbles, pump, benches, trees, a stretcher, students talking, a midwife, a queue of 8;
  - room: books, papers, candle, bed, curtains;
  - anatomy room: jars, basin, late students, lecturing;
  - cell: a real window opening, moon shaft, straw, bucket, chain.
- New views: market, street-low, room, desk, court-wide, pump, court-low, anatomy-close, jars, cell-close.
- Storyboard re-cut to about 35 shots. `plan_storyboard.shape_problems` now counts a hand-cut beat as a montage (4 or more shots, median shot no longer than 2.6 s); there is a test for it.
- Master: 87.8 s, QC PASS. One `empty_shot` at 11.6 s (beat-01 `at:window` close-up, dark). Old renders are in `renders/3d-before-dressing/`.

### In progress / left
- The user watches the pilot.
- Fix the dark `at:window` shot in beat-01.
- Run the full test suite after the latest changes (not run since).
- After the render: run `test_scene_catalog` and the Blender tests with `BLENDER_EXE` set (no other Blender running).
- The user reviews the pilot. Only after approval: expand to a full film (tavern, his room, the walk to work, Kolletschka's death, chlorine washing, the fall).
- Known weak spots:
  - the courtyard (beat-04) looks bare;
  - harmless "RNA_float_set: NodeSocket.default_value not found" at build;
  - `episode.json` still has archive enabled.
- Nothing committed; commit only when asked.
- Lesson: stopping `make_episode` does NOT stop the detached Blender. The render is a separate process; its pid is in `qc/rollout-render.json`. The old Blender went on and wrote beats 01-03 with the old timing, and beat-03 came out without a moov atom. Those files were moved to `renders/3d-old-voices/`, and beats 1-3 are being re-rendered (`build3.log`). Before you restart a render, kill that pid.

## 2026-11-18 (uncommitted): closer to Fern/Veritasium, all three gaps, pipeline-wide
- The v3 rewrite (story, archive as evidence, cut rhythm) passed QC. It was sent as preview `work/ask-chatgpt/preview/ask-chatgpt-v3-part1..4.mp4`. Cutaway CUT_A was 1.5 s, exactly on the 1.5 s short-shot bound, so it is now 1.2.
- The user asked to fix the remaining gaps generally:
  1. Look (`tools/blender/models/look.py`): `haze_world()` (horizon haze sky, even fill for non-camera rays), `stage_floor()` (even-sheen concrete, seams only when `floor_grid`, fades into the haze), `light_set()` (key/rim as before plus a set-wide fill and an overhead softbox from `set_bounds()`), screen raytracing + fast GI, exposure +0.25. Roughness noise on the floor read as smoke and was removed. Cost is about 1.2 s/frame against about 0.8 before, so the episode render takes about 6 h.
  2. Story turn: `qc_script.check_turn` requires `guess` (by 20%) and `reversal` (25-70%, with a turn word) in story.json (`script.story.guess_by_fraction`, `reversal_window`, `turn_basis`). ask-chatgpt: guess u005, reversal u050 "Actually, no. That guess is wrong."; the opening picture is now model-layers (busy maths), and the sleeping factory first appears at the reversal.
  3. Sound: `tools/sound_design.py`, called from `audio_finish.finish_voice` when storyboard.json exists. It lays a hit on every in-beat cut, a whoosh or thud at beat changes, air on travel moves, pops on actions, and a room per scene (`audio.sound_design.rooms`). At the reversal it adds a riser and a boom, and the music bed drops (`music_bed.apply_drops`, passed through `assemble_episode.add_music_bed(drops=)`). The effects track measures about 20 LU under the voice. Tests: `python/test_sound_design.py`.
- Full rebuild started 2026-11-18 morning: `--from plan`, log `work/ask-chatgpt/build6.log`. Old renders are kept in `renders/3d-cut3c`.
- The same day the user asked for a hook that grabs (shock, interest, mystery). build6 was stopped after beat-06.
  - New gate `qc_script.check_hook` (`script.story.hook`): story.json `hook {kind: shock|mystery|contradiction|stakes, image}`, no soft opener, a gap (question or contrast word) within 20 s, and a `shock` first line must cite a claim.
  - ask-chatgpt cold open u001: "The kind of machine that answers your questions weighs more than a tonne and draws as much power as a hundred homes." (c4, c20, c21, c23). It is its own beat, `beat-00` (gpu-rack, tray to wide, a tiny cat at its foot), followed by the stutter montage (beat-01).
  - `build_storyboard3.punctuate` counts from beat-01, so later cutaways are unchanged. build7 (log `build7.log`) re-renders 35 beats.
- Approved by the user, to apply AFTER build7:
  - the cleanup batch 1-5 from the audit (pilot chain, Carrington, gemini_pipeline, blender-upgrade tools, `.superpowers` before-copies, `media/texts`, shared `when`/`default_shots`, one `_relative_posix`, stale docstrings);
  - improvements 1-4 from `docs/research/other-video-pipelines.md`.
- Improvement 1 is started. The user allowed `pip install onnx` (1.23.2). New `tools/word_marks.py` exposes Kokoro's `/encoder/Cast_output_0` durations in memory and re-synthesises every line. All 127 lines are sample-identical to `vo/*.wav`, so the marks are exact. It writes `vo/word_marks.json`; tests are in `python/test_word_marks.py`.
  - Estimate error: median 0.093 s, p90 0.28 s. Of the storyboard's 15 `word:` marks, 7 are off by more than 0.2 s ("tonne" -0.37 s).
  - Still to do: `captions.word_timings` must use the marks, and beats 00, 07, 09, 17 and 31 must be re-rendered.
- 2026-11-18 later: build7 passed QC (628.9 s); the v4 preview was sent. All of the following is done and uncommitted:
  - **Cleanup:** stills are pixel-identical before and after (PSNR inf); 691 tests pass apart from the known `test_blender_config`.
    - Removed: `explainer_pilot.py`; `look.dark_stage`/`orbit_stage`/`tag`; `kit.stage`/`label`/`_world`/`floor_mat`; `historical_beats.py`; the manim carrington and solar_flare demos; `gemini_pipeline/`; `verify_upgrade.py`, `install_commotion.py`, `work/blender-upgrade`, `tools/blender-addons`; the `.superpowers` *-before copies.
    - `media/texts` is untracked and gitignored.
    - `when`/`default_shots`/`shot_starts` now live in `workflow/storyboard.py`, and `archive.relative_posix_problem` is shared.
  - **1. Word marks:** the `make_episode` captions stage runs `word_marks.py` before `captions.py`, and `captions.exact_marks` uses the marks when they match the wav and the text. Beats 00, 07, 09, 17 and 31 are being re-rendered in `render8.log`; the old renders are in `renders/3d-estimated-cues`.
  - **3. Cut cross-check:** `qc_episode.check_cut_detection` compares detected cuts with `known_cuts` from the sound design. It found a real A/V drift: picture behind the voice by +0.14 s growing to +0.65 s, caused by per-segment `-t` rounding.
    - Fix: `assemble.build_segments` now cuts by frames on the film clock.
    - New error `picture_out_of_sync` (over 0.1 s per third); warning `cut_detector_misses` below 70% recall.
  - **4. Ducking and reverb:** ffmpeg's sidechaincompress was non-deterministic, so ducking is in numpy (`music_bed.duck_gain`, `audio.ducking`): lift 5 dB, ratio 2.5. Under speech the bed goes from -35.8 to -36.0 dB; in the pauses from -35.6 to -31.4. Effects get a synthetic room reverb (`audio.sound_design.reverb`); rooms stay dry.
  - **2. Frame critic:**
    - QC warns `empty_shot` when edge share is under 2% (`qc.empty_shots`).
    - `storyboard_beats.cut_text` writes `renders/3d/<beat>.framing.json`; `--check` builds a beat without rendering it. QC turns the reports into `framing` warnings.
  - **Result:** build9 passed QC with 0 errors and 33 warnings (5 empty shots, 26 text cuts in 15 beats, the Altman clip, one slow shot). Sync is within ±0.011 s; the detector recall is 78%. The v5 preview was sent.
    - Tests: 701, only the known `test_blender_config` fails. The archive test manifest has no start/end, so `build_segments` keeps a running sample clock.
  - **Open:** reframe the cut-text shots (token-stream close-ups, document titles, "4 bits"), and fix the 5 empty shots. Nothing is committed.
- Reframe (the user said "yes, reframe them"):
  - `Set.pin(..., hold=[objs])` + `storyboard_beats.held_box`: an `at:X` close-up whose anchor declares `hold` is centred on it and fits it to about 80% of the frame (min radius 2). There is no default hold; with a default, 26 beats moved.
  - Holds are declared on: token-stream prompt (bubble + text), document title rows, document mark (a never-rendered `mark-hold` box, `hold_box` prop), tokenizer id/token/sentence, fiber phone screen and hall.
  - Token-stream `close` view is now (-1.6,0,2.9) r 5.6, height 3.5, so the question is out of frame.
  - `cut_text` skips objects marked `cut_ok` (answer tokens, tokenizer pieces, zzz). A travelling shot is sampled at 3 points and counts only if the text is cut in 2 of them.
  - Storyboard DETAILS: wire-trip uses `at:memory` instead of `at:wire`; tokenizer uses `at:sentence` instead of `at:id`.
  - `--check` also writes `<beat>.camera.json`; diffing `qc/cam-before` against `qc/cam-after` gives 15 changed beats (01 03 04 05 07 08 09 10 14 19 20 21 34 36 38). Their old renders are in `renders/3d-before-reframe`. Framing problems are now 0. build10 (`--from render`) is running.

## Episode work/ask-chatgpt (2026-11-17, uncommitted: user said "not yet")
- Story cut: narration follows the token "cat" (id 9059, c29); factory metaphor for memory-bound decoding; "trick number one/two/three". 138 lines, 41 beats.
- Look (user's choice): 3D world + pixel-art characters (Gumball-style mix). `tools/pixel/sprites.py` grids; storyboard beat key `cast` (validator in `workflow/storyboard.py`, placement `place_cast` in `storyboard_beats.py`). Scene `chip-factory` (`tools/blender/models/characters.py`): 12 desks, workers mixed pixel + 3D vinyl toys (`character_styles.py`).
- Full build done: `work/ask-chatgpt/ask-chatgpt.mp4`, 11:07, QC PASS (0 errors, 14 advisories: archive shots >6 s, slow drifts). Review frames in `qc/final/`.
- User feedback: episodes must not feel like presentations (story, reacting characters, little text). Still chart-like: b05 next-token bars, b17 energy bars, b33/b34 Wh comparison bars.
- Same day, user: "still a presentation, too much random archive; study Fern + Veritasium and fix the pipeline". Done (uncommitted): `docs/research/story-not-slides.md` (6 reference films measured). New gates: `qc_script.py` story rules + `script/story.json`; archive `depicts` evidence rule (`plan_shots.py`, `plan_storyboard.py --check`, `style.json archive.evidence`, archive floor now 0); storyboard shape (`style.json storyboard`: text/min, chart beats, montage/travel); builder `cut: travel|montage|steady` (default travel = continuous camera move, `look.shoot` target_to); QC `check_cut_rhythm` (`rhythm.cuts`). 680 tests, only the known BLENDER_EXE env failure.
- ask-chatgpt now FAILS these gates (script 48% numeric, no story.json, 27 archive records without depicts, 6.5 texts/min). Next: rewrite it as a story to the new rules.

## How to run an episode (read this first in a new chat)
1. Make `work/<name>/` with `script/narration.md` (one sentence per line), optional `script/chapters.json`, `script/claims.json`, `research/sources.md`, plus `shots.json` and `archive.json` (see `docs/PRODUCTION-GUIDE.md` section 0).
2. `python tools/make_episode.py --episode work/<name> --dry-run`, then run it with `--ask-cmd "<planner command>"` (or write `storyboard.json` from `storyboard-brief.md`). Stages: script, narration, captions, lengths, plan, ingest, render, assemble, qc. Resumable; stops at first failure.
3. Worktree/Blender env notes below. Open defects are listed at the bottom; the Jensen episode is only the regression fixture.
- User rule: do not start a new episode without being asked; ask before downloading a public-domain coastline file.

## After phase 9 (same night)
- Verified in main: 660 tests OK, dry run lists all stages.
- `tools/plan_shots.py` + stage `shots` in make_episode (now 10 stages): generates shots.json (3D beats of ~14 s, archive records spread evenly, `script/shots-hint.json` pins lines). Never overwrites an existing shots.json. `python/test_plan_shots.py`.
- Planner tried with local `huihui_ai/qwen2.5-coder-abliterate:7b` via `--ask-cmd "ollama run <model>"` (10 min): the 7B model failed validation after 2 repairs (invented `none` actions, wrong params/anchors, skipped beats, >4 labels), and the gate correctly wrote nothing to storyboard.json. Catalog digest now says to leave out `params`/`actions` for scenes that have none. A stronger model is needed for a real run; not tested.
- Jensen content defects NOT fixed on purpose (each needs re-synthesis and re-render of the fixture): "twenty-five-ninety" (line u009 should be 256), unsourced "personal life" line (u018), script 3:08 vs 600-900 s, archive share 10%.

## Phase 9: DONE
- Deleted stray root one-offs (`qc_findings.txt`, `test_import.py`, `fix_licence.py`, `regenerate_narration.py`, `update_archive_licence.py`; `undefined` did not exist). `PRODUCTION-GUIDE.md` now opens with section 0 (the one command). Kept `create_package.*`, `download_blender.ps1`, `ENHANCED-3D-TOOLKIT-REPORT.md` (not one-offs of the pipeline).
- (Earlier lines below describing "Next" are historical.)
- User instruction: finish the code first; NO new episode until the pipeline is complete. Jensen episode is the regression fixture only.
- Blender for tests in a worktree: `export BLENDER_EXE=F:/AI-PROJECTS/longform-explainer/tools/blender-4.5.15-windows-x64/blender.exe` (the exe is gitignored, so it only exists in the main checkout). Unset it for `test_blender_config`.

## Done and verified (commit after `76a184c`)
- `tools/blender/storyboard_beats.py`: generic builder. `--episode DIR [--beat N] [--force] [--still F] [--out D]`, `--catalog FILE`. Reads `storyboard.json` + `shot_lengths.json` (+ optional `word_timing.json`). Cuts every ~4.5 s with drift; label whose anchor is off screen gets its own 2.4 s close-up shot and the beat is rebuilt (up to 2 repairs).
- `workflow/scenes.json` (20 scenes: params, examples, views, anchors, actions), `workflow/storyboard.py` validator (`python -m workflow.storyboard <episode>`), `python/test_storyboard.py`, `python/test_scene_catalog.py`.
- `work/jensen-huang/storyboard.json`: the 17 beats as data; 0 framing problems in stills; `episode.json` rollout.builder -> generic builder; `tools/rollout_render.py` `builder_args()` adds `--episode`. Hand-written `jensen_huang_beats.py` and its two probes deleted.
- Tests passing: model_library 3, scene_catalog, storyboard, rollout_render, jensen_huang_episode (57 passed).
- Phase 0 so far: `archive_source` `used_urls` was a set read as a dict (44 failures -> ~16).

## Next (in order)
- (none: all phases done)

## Phase 8: DONE
- `tools/make_episode.py --episode work/X [--dry-run] [--from S] [--only S,..] [--force] [--ask-cmd CMD] [--replan] [--models DIR]`.
- Stages: script, narration, captions, lengths, plan, ingest, render, assemble, qc. Resumable via `qc/make-episode.json` (input digests; downstream stages re-run when an earlier one runs). Stops at the first failure.
- `plan` without `--ask-cmd` and without storyboard.json writes the brief and stops (exit 2). `shots.json` is still authored by hand (not generated).
- Dry run on Jensen verified (`python/test_make_episode.py`); script gate failure verified on a scratch copy (stops, records nothing). Full real run not done (needs main checkout media, Blender hours).
- Remaining: phase 9.

## Phase 7: DONE
- `pipeline_supervisor.py`: placeholder/regenerate fixes removed; missing or unreadable archive media is an AGENT_ONLY finding that stops the stage (`python/test_pipeline_supervisor.py`). Core already raised on missing sources (`workflow/episode.archive_sources`).
- `plan_storyboard.archive_mix(episode)` applies the archive share/per-act floors (`workflow.archive.mix_findings`) at planning time; `--check` fails on it. Jensen reports `archive_share_low` (10% vs 20%), as known.
- Stills already get paper/drift treatment through `archive_ingest.ingest_clip` (form: still).
- Remaining: phase 8 (`tools/make_episode.py`), phase 9 (clean-up/docs).

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
- (fixed in phase 7) supervisor placeholder clip, the likely cause of the black `boarding-school_part1` shot.
- Narration "GeForce twenty-five-ninety" (should be 256); "personal life" line unsourced; script 3:08 vs 600-900 s; no captions; archive share 10%; 4 loudness jumps at archive cuts.
- "Today" tag in `valuation` close-up sits against the bar (cosmetic).
- Map scene with real coastlines needs a public-domain coastline file: ask the user before downloading.

## Episode `work/the-light-machine` (2026-11-16): master built, QC PASS (0 errors, 15 warnings)
- "The Machine That Prints the Future" (EUV lithography), 602.5 s, 1080p, `the-light-machine.mp4`. 92 lines, 34 3D beats, 25 archive shots (21%), all Wikimedia Commons with a licence row each (`assets/archive-licence.json`); some are illustrative (Webb, Hubble, CO2 laser, Trumpf, Zeiss) and say so in `purpose_of_use`. User allowed downloading for this archive work only.
- Archive sourcing recipe: `sourcing/` (collect candidates via `tools/sourcing/providers.py wikimedia`, choose, download with the contract User-Agent, `build_records.py` writes archive.json + ledger + shots-hint.json). IBM schematic video is cut into 6 clips with ffmpeg.
- Fixed: `plan_shots` no longer lets a 3D beat straddle an archive cutaway (a beat is cut at each archive line). Fixed: `music_bed.synthesize` looped no chords, so any film longer than ~200 s had air only under the voice and failed `music_bed_missing`; the progression now repeats (test added).
- Lessons: the `statement` scene is unusable for text; `layer-stack` anchors fail for lower layers or early times; the validator does not check that `word:` anchors occur in a beat; narration runs ~3.08 words/s against the gate's 2.36; never start a second `make_episode` while Blender runs (concurrent writers corrupt the master; rebuild with `assemble_episode.py --remux`).
- Remaining warnings: 5 archive shots 6.1-6.4 s (limit 6.0, advisory), ~10 `slow_shot`. Not committed.

## Episode `work/euv-machine` (2026-11-16): the rewrite the user asked for after rejecting the-light-machine
- Full rewrite, causal chain: question, analogy, mechanism, number, recap. 127 lines, ~679 s, claims c1-c33 all sourced in `research/sources.md`. 35 3D beats from 10 new parametric scenes in `tools/blender/models/optics.py` (wave-slit, grating-lens, formula, wavelengths, litho-exposure, tin-source, bragg-mirror, light-path, scanner, photon-rain), catalogued in `workflow/scenes.json`.
- Archive: 30 records, 15 are real video clips (NASA SVS SDO 171, IBM EUV schematic, Fritzchens Fritz die, ST fab, Webb coating, ESO mirror grinding, CC0 laser cutter, raindrops), cut with ffmpeg. Ledger timebase = the source's own rate (`tb = round(fps)`). Sourcing scripts are in `work/euv-machine/sourcing/`.
- Realism rules the user set: droplets fly horizontally, collector faces up with the laser through its hole, mask lit at ~6 degrees, curved slit, 26 x 33 mm fields, mask moves 4x faster in the opposite direction. Droplets and plasma are now smooth spheres and the collector is smooth (`kit.balls(subdivisions, smooth)`). Wave labels sit above their curves, framed from the lens FOV.
- Audio fixes (contract, `workflow/style.json`): ffmpeg's native AAC at 192k overshot one transient by 3.4 dB (+1.9 dBFS), so the master is now encoded at `aac_bitrate` 384k (YouTube's recommended rate); the bed is at `music_under_voice_db` -9 (was -10) because a denser read left the floor lift at +1.9 against 2.0.
- Fixed in `make_episode.py`: render declared no outputs and assemble did not read the renders, so deleting a beat's mp4 left both stages "done" and the master kept the old beat. Render now owes `renders/3d/<beat>.mp4` per 3D beat and those files are assemble inputs (test added).
- After the first full render, QC PASSed with `--remux`; 12 beats (tin-source, wavelengths, wave-slit) were re-rendered for the realism fixes with `make_episode --from ingest` (never `--from script`: a changed style.json would re-synthesise the narration). Not committed.
