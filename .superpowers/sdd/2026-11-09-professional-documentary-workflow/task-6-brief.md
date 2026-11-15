# Task 6 Brief: Carrington Event Pilot Through Preview and Purchase List

## Context

You are building the complete Carrington Event pilot episode for the professional documentary workflow project at `F:\AI-PROJECTS\longform-explainer`. This is the final task in the plan and consumes all infrastructure from Tasks 1-5.

**Existing research:** `F:\AI-PROJECTS\longform-explainer\.superpowers\sdd\2026-11-09-professional-documentary-workflow\pilot-research.md` contains 34 sources with Tier 1/2/3 labels, evidence-backed chronology, and narration guidance. Use it as the authoritative evidence base.

**Existing tools:**
- `workflow/init_episode.py` — creates nine-phase episode layout (Task 1)
- `tools/sourcing/manifest.py`, `download.py`, `providers.py`, `screenshot.mjs` — asset validation, downloads, provider CLIs (Task 2)
- `workflow/config.py` with `blender_executable()` — Blender 4.5.15 LTS selection (Task 3)
- `work/shot-recipes/index.html` — four HyperFrames shot recipes (Task 4)
- `tools/blender/techniques/{common,labels,build,validate}.py` — four Blender techniques (Task 5)
- `python/narrate.py` — Kokoro TTS adapter
- Existing cumulative-frame assembly pipeline from cable episode

## Your Task

Produce a complete local preview and purchase package for "The Carrington Event: When the Sun Reached the Telegraph" — a 12-13 minute English documentary. **Do not upload or publish anything.** This is preview-state only; the user will purchase licenses before upload.

### Step 1: Initialize the episode package

Run:
```bash
.venv/Scripts/python.exe -m workflow.init_episode --root work --slug episode-carrington --title "The Carrington Event: When the Sun Reached the Telegraph"
```

Verify the nine-phase layout exists with empty manifest and English metadata.

### Step 2: Consolidate research into facts.json

Read `pilot-research.md` and extract every evidence-backed claim into `work/episode-carrington/research/facts.json`. Each claim must have:
- `claim_id` (e.g., "c001")
- `text` (the factual statement)
- `citations` (array of source IDs from pilot-research.md, e.g., ["S02", "S12"])
- `confidence` ("high", "medium", "low")
- `visual_interpretation` (permitted visual representation)

Gate: at least 15 useful claims, every citation maps to a source in pilot-research.md, no dramatic claims without evidence support.

### Step 3: Write the locked story structure

Create `work/episode-carrington/story/beat-sheet.md` with this structure:

**Target duration:** 12-13 minutes (720-780 seconds)

- **0:00-0:45** — Event hook (aurora, telegraph sparks, tension)
- **Act I: 0:45-3:30** (165s) — Telegraph infrastructure and 1859 chronology
  - Beat 1: Telegraph network context (1850s)
  - Beat 2: August 28-29 auroral episode
  - Beat 3: September 1 — Carrington and Hodgson observe flare
  - Beat 4: September 2-3 — second major storm
  - Tension: "What caused this?"
- **Act II: 3:30-8:00** (270s) — Sun-to-ground mechanism
  - Beat 5: Solar flare vs. CME (not synonyms)
  - Beat 6: CME travel to Earth (17-hour reconstruction)
  - Beat 7: Magnetosphere compression
  - Beat 8: Geomagnetically induced currents (GICs)
  - Beat 9: Ground geoelectric fields
  - Beat 10: Telegraph circuit response
  - Tension: "Could this happen today?"
- **Act III: 8:00-11:30** (210s) — Modern infrastructure and mitigation
  - Beat 11: Modern power grid vulnerability
  - Beat 12: USGS geoelectric hazard maps
  - Beat 13: FERC/NERC reliability standards (TPL-007-1)
  - Beat 14: Monitoring and mitigation strategies
  - Tension: "Are we prepared?"
- **Payoff: 11:30-12:30** (60s) — Connect historical evidence to present engineering

Every beat must name its visual anchor and transition.

### Step 4: Write the narration and shot plan

Create `work/episode-carrington/script/narration.md` with:
- 1700-2100 English words
- 80-110 utterances (each 15-25 words)
- Each row: `utterance_id`, `narration`, `visual_id`, `visual_instruction`, `claim_ids`

Create `work/episode-carrington/script/narration_request.json` with the same data in machine-readable form.

Assign 180-216 shots for the final cut (15-18 cuts/min). Include **six detailed 3D beats**:
1. Solar flare (Blender cutaway or xray technique)
2. CME travel (Blender exploded or zoom-inside technique)
3. Magnetosphere compression (Blender technique)
4. Ground-induced current (Blender technique)
5. Telegraph circuit (HyperFrames diagram or Blender)
6. Modern transformer response (HyperFrames diagram or Blender)

Keep each 3D beat within 5-20 seconds. Use diagrams (HyperFrames shot recipes) whenever they are clearer than decorative imagery.

### Step 5: Source media and log rights

Use the Task 2 sourcing tools to download or screenshot media:

```bash
python -m tools.sourcing.providers wikimedia "Carrington event 1859" --limit 5
python -m tools.sourcing.providers internet-archive "Carrington telegraph 1859" --limit 5
python -m tools.sourcing.providers pexels "solar storm aurora" --limit 5
```

For each sourced item, add an entry to `work/episode-carrington/assets/license-manifest.json` with:
- `asset_id` (unique, case-insensitive)
- `provider` ("wikimedia", "internet-archive", "pexels", "project-owned")
- `license_type` ("cc-by", "cc-by-sa", "public-domain", "paid-preview", "project-owned")
- `license_status` ("preview" or "purchased")
- `file` (repository-relative POSIX path)
- `shot_ids` (array of shots using this asset)
- `attribution` (required credit text)

**Gate:** Every external file in the shot plan has one manifest entry. No CC BY-NC entries. Every entry names its shots.

For assets you cannot access or screenshot without bypassing authentication, select a free alternative or mark as `license_status: "preview"` with a note.

### Step 6: Generate narration and build the visual timeline

Generate Kokoro WAVs:
```bash
python python/narrate.py --script work/episode-carrington/script/narration_request.json --out work/episode-carrington/vo/
```

Build the visual timeline using existing tools:
- HyperFrames shot recipes from `work/shot-recipes/` for diagrams, quotes, archival plates, news lower-thirds
- Blender techniques from `tools/blender/techniques/` for the six 3D beats
- Existing cumulative-frame assembly pattern from cable episode

Render each shot as a PNG sequence or MP4 clip. Use `round(elapsed * FPS)` for frame counts and `tpad=stop_mode=clone:stop=1` before trim.

### Step 7: Assemble the preview and run media verification

Assemble the final preview:
```bash
ffmpeg -f concat -safe 0 -i shot_list.txt -c:v libx264 -pix_fmt yuv420p -r 30 -s 1920x1080 -c:a aac -b:a 192k work/episode-carrington/dist/episode-carrington-preview.mp4
```

**Targets:**
- 1920x1080, 30fps, H.264 video, AAC audio
- 600-900 seconds (10-15 minutes)
- 15-18 cuts/min
- No static shot over 8 seconds without meaningful motion
- −16±1 LUFS integrated loudness

Run the episode's cumulative-frame timing test with ffprobe. Extract contact sheets including all six 3D beats and transition midpoints. Inspect visually.

Verify: no clipped words, no caption overlap, no empty frames, no missing labels, no watermarked media accidentally absent from the manifest.

### Step 8: Export packaging and enforce the license gate

Run:
```bash
python tools/manifest_report.py --episode work/episode-carrington
```

Expected: `dist/license-purchase-list.md` lists every remaining preview asset grouped by provider. The command exits 1 while previews remain (this is the intended preview state).

Create:
- `work/episode-carrington/dist/thumbnail.png` (a representative frame)
- `work/episode-carrington/dist/metadata.md` (title, description, chapters, sources, all required attribution)

**Do not run any upload command.** The delivery report must distinguish fully rendered/verified items from anything still requiring user viewing, listening, license purchase, or clean-asset replacement.

### Step 9: Run final regression and completion audit

Run:
```bash
.venv/Scripts/python.exe -m unittest discover -s python -v
npm test
.venv/Scripts/python.exe -m unittest discover -s work/episode-carrington -p "test_*.py" -v
```

Expected: all runnable tests PASS.

Audit every objective clause:
- ✅ Detailed 3D beats (six techniques)
- ✅ Free-renderer research (pilot-research.md with 34 sources)
- ✅ Download-now/license-later sourcing (manifest with preview status)
- ✅ Free fallback (no paid calls made)
- ✅ Increased research/motion/edit depth (12-13 min, 180-216 shots)
- ✅ Installed capabilities (Tasks 1-5 tools used)
- ✅ Concrete user actions (purchase list, attribution text)
- ✅ No upload (preview-state only)

## Constraints

- **No external HTTP(S) assets** unless downloaded via Task 2 tools with manifest entry
- **No paid calls** — use free providers and project-owned assets only
- **No git commits** — the project is not a git repository
- **No upload or publication** — preview-state only
- **All copy in English**
- **All visible text >= 28px** (HyperFrames house style)
- **House style:** dark cinematic navy (#060810), amber/cyan accents
- **Blender 4.5.15 LTS** with EEVEE Next, AgX color management
- **Kokoro TTS** with `af_heart` voice, speed 1.0

## Report Contract

Write your full report to:
`F:\AI-PROJECTS\longform-explainer\.superpowers\sdd\2026-11-09-professional-documentary-workflow\task-6-report.md`

Include:
- Status: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED
- Files created (exact paths)
- Test evidence (RED/GREEN for each step)
- Visual inspection notes (what you saw in contact sheets)
- Render times and performance measurements
- Concerns and limitations
- User action list (what the user must do before upload: purchase licenses, review preview, etc.)

## Second Brain Update

After completing the task, update:
- `E:\Documents\Obsidian Vault\AI-SECOND-BRAIN\PROJECTS\longform-explainer\STATUS.md` — append Task 6 completion section
- `E:\Documents\Obsidian Vault\AI-SECOND-BRAIN\INDEX.md` — add session bullet at top of Sessions Journal
