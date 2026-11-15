# Professional Documentary Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify a reusable fern-style documentary production system, then use it to produce an English Carrington Event pilot through the licensed-preview stage.

**Architecture:** Python stdlib tools own episode scaffolding, media provenance, licensing, and configuration. HyperFrames owns DOM/GSAP shot recipes; portable Blender 4.5 owns new 3D production after a same-scene RX 580 comparison against legacy 4.1. The pilot reuses the existing Kokoro, cumulative-frame assembly, ffmpeg QA, and contact-sheet patterns; old episodes remain pinned to their existing scripts.

**Tech Stack:** Python 3.14 stdlib + unittest, Node 24, TypeScript, HyperFrames/HTML/CSS/GSAP, Playwright, Blender 4.1/4.5 EEVEE, ffmpeg/ffprobe, Kokoro TTS.

**Spec:** `docs/superpowers/specs/2026-11-09-professional-documentary-workflow-design.md`

## Global Constraints

- Target episode duration is **10–15 minutes**, language is **English**, narration is **Kokoro TTS**, pace is **15–18 cuts/min**, and solo cadence is **1 episode / 2 weeks**.
- Rendering is **CPU-only + AMD EEVEE (RX 580 4GB, no CUDA/ROCm)**; ffmpeg AMF encode is available.
- New episodes receive **4–10 detailed Blender beats**, each **5–20 seconds**, whenever 3D improves understanding.
- Keep HyperFrames as the primary renderer. Remotion is evaluation-only and no migration is permitted without explicit user approval.
- Legacy episode scripts stay on Blender 4.1. New production may switch to 4.5 only after the same-beat render comparison succeeds and its comparison frame is visually inspected.
- CC BY-NC is banned. CC BY/CC BY-SA require attribution. BBC RemArc audio is not treated as free. Editorial-only media requires a genuinely editorial context.
- Preview/comp media must be logged at download time. Clean purchased media replaces previews at the same path. No upload occurs while any used asset remains `preview`.
- API keys are read from environment variables at call time and are never written into source, manifests, logs, chat, or vault notes.
- Do not use Mograph preset assets or node groups in production while its repository has no clear license.
- Do not publish, upload, delete remote material, or create git commits. Verification checkpoints replace the plan skill's commit steps.
- Run Python tests with `.venv/Scripts/python.exe -m unittest discover -s python -v` and Node tests with `npm test` from the repository root.

## File Structure

- `workflow/`: episode initializer, templates, Blender selection, and episode-level gates.
- `tools/sourcing/`: manifest validation, atomic downloads, provider queries, screenshots, and purchase-list export.
- `tools/blender/`: portable-version verification and reusable 3D techniques; Blender-only scripts stay separate from host Python.
- `work/shot-recipes/`: isolated HyperFrames fixture containing the four reusable documentary shot types.
- `work/technique-pack/`: generated `.blend` scenes, validation report, and QA stills.
- `work/episode-carrington/`: the first full nine-phase episode.
- `python/test_*.py`: deterministic host-Python contracts discovered by the existing test command.
- `tests/*.test.ts`: Node and browser-fixture contracts discovered by `npm test`.

---

### Task 1: Workflow Scaffolding

**Files:**
- Create: `workflow/__init__.py`
- Create: `workflow/init_episode.py`
- Create: `workflow/templates/sources.md`
- Create: `workflow/templates/beat-sheet.md`
- Create: `workflow/templates/narration.md`
- Test: `python/test_init_episode.py`

**Interfaces:**
- Consumes: no new dependencies; uses Python stdlib and the existing `work/` episode root.
- Produces: `init_episode(root: Path, slug: str, title: str) -> Path`; creates `episode.json`, the nine phase directories, three copied templates, and `assets/license-manifest.json` containing `[]`.

- [ ] **Step 1: Write the failing initializer contract**

```python
import json
import tempfile
import unittest
from pathlib import Path
from workflow.init_episode import init_episode

class InitEpisodeTests(unittest.TestCase):
    def test_creates_nine_phase_layout_and_empty_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            episode = init_episode(Path(tmp), "episode-carrington", "The Carrington Event")
            for name in ("research", "story", "script", "assets", "vo", "motion", "edit", "qc", "dist"):
                self.assertTrue((episode / name).is_dir(), name)
            self.assertEqual(json.loads((episode / "assets/license-manifest.json").read_text()), [])
            self.assertEqual(json.loads((episode / "episode.json").read_text())["language"], "English")
            self.assertTrue((episode / "research/sources.md").is_file())
            self.assertTrue((episode / "story/beat-sheet.md").is_file())
            self.assertTrue((episode / "script/narration.md").is_file())

    def test_rejects_unsafe_slug_and_existing_episode(self):
        with tempfile.TemporaryDirectory() as tmp:
            for slug in ("../escape", "A", "two words", "a/b", ""):
                with self.subTest(slug=slug), self.assertRaises(ValueError):
                    init_episode(Path(tmp), slug, "Title")
            init_episode(Path(tmp), "episode-carrington", "Title")
            with self.assertRaises(FileExistsError):
                init_episode(Path(tmp), "episode-carrington", "Title")
```

- [ ] **Step 2: Watch the contract fail for the missing module**

Run: `.venv/Scripts/python.exe -m unittest python.test_init_episode -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'workflow'`.

- [ ] **Step 3: Implement the initializer and templates**

Use this public surface in `workflow/init_episode.py`:

```python
import json
import re
import shutil
from pathlib import Path

SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
PHASES = ("research", "story", "script", "assets", "vo", "motion", "edit", "qc", "dist")
TEMPLATES = {"sources.md": "research", "beat-sheet.md": "story", "narration.md": "script"}

def init_episode(root: Path, slug: str, title: str) -> Path:
    if not SLUG.fullmatch(slug):
        raise ValueError("slug must be lowercase kebab-case")
    if not title.strip():
        raise ValueError("title is required")
    episode = Path(root) / slug
    episode.mkdir(parents=True, exist_ok=False)
    for phase in PHASES:
        (episode / phase).mkdir()
    (episode / "episode.json").write_text(json.dumps({
        "slug": slug, "title": title.strip(), "language": "English",
        "workflow_version": 3, "duration_target_seconds": [600, 900]
    }, indent=2) + "\n", encoding="utf-8")
    (episode / "assets/license-manifest.json").write_text("[]\n", encoding="utf-8")
    template_root = Path(__file__).with_name("templates")
    for filename, phase in TEMPLATES.items():
        shutil.copyfile(template_root / filename, episode / phase / filename)
    return episode
```

Add a CLI accepting `--root`, `--slug`, and `--title`. `sources.md` must define claim ID, exact claim, source URL, publisher, publication date, source tier, supporting quotation, and verification status. `beat-sheet.md` must define time range, narrative purpose, tension/reveal, narration IDs, visual IDs, and transition anchor. `narration.md` must be a table with utterance ID, narration text, visual ID, visual note, source claim IDs, and estimated seconds.

- [ ] **Step 4: Verify the initializer and regression suites**

Run: `.venv/Scripts/python.exe -m unittest python.test_init_episode -v`
Expected: 2 tests PASS.

Run: `.venv/Scripts/python.exe -m unittest discover -s python -v`
Expected: all discovered tests PASS with no new failures.

- [ ] **Step 5: Record the verification checkpoint**

Create no commit. Record the passing commands and test counts in the task result.

---

### Task 2: Sourcing and License Toolkit

**Files:**
- Create: `tools/sourcing/__init__.py`
- Create: `tools/sourcing/manifest.py`
- Create: `tools/sourcing/download.py`
- Create: `tools/sourcing/providers.py`
- Create: `tools/sourcing/screenshot.mjs`
- Create: `tools/manifest_report.py`
- Create: `tests/screenshot.test.ts`
- Modify: `package.json` and `package-lock.json` via the npm Playwright installation
- Test: `python/test_sourcing.py`

**Interfaces:**
- Consumes: `init_episode()` layout from Task 1; optional `PEXELS_API_KEY` from the process environment only.
- Produces: `validate_asset(asset: dict) -> dict`, `append_asset(path: Path, asset: dict) -> dict`, `mark_purchased(path: Path, asset_id: str) -> dict`, `purchase_list(path: Path) -> list[dict]`, `download_binary(url: str, destination: Path, opener=urlopen) -> Path`, and `python tools/manifest_report.py --episode work/episode-carrington`.

- [ ] **Step 1: Write failing licensing and atomic-download tests**

```python
import json
import tempfile
import unittest
from pathlib import Path
from tools.sourcing.manifest import append_asset, mark_purchased, purchase_list, validate_asset

VALID = {
    "id": "a0001", "file": "assets/archival/carrington.jpg", "kind": "photo",
    "provider": "wikimedia", "asset_id": "File:Carrington_Richard_1859.jpg",
    "url": "https://commons.wikimedia.org/wiki/File:Carrington_Richard_1859.jpg",
    "watermarked": False, "license_status": "free", "license_type": "PD",
    "attribution": "", "shots": ["s012"], "downloaded_at": "2026-11-09", "notes": ""
}

class ManifestTests(unittest.TestCase):
    def test_rejects_noncommercial_and_missing_attribution(self):
        for license_type in ("CC-BY-NC", "CC-BY-NC-SA"):
            with self.subTest(license_type=license_type), self.assertRaises(ValueError):
                validate_asset({**VALID, "license_type": license_type})
        with self.assertRaises(ValueError):
            validate_asset({**VALID, "license_type": "CC-BY", "attribution": ""})

    def test_purchase_list_contains_only_preview_and_purchase_preserves_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "license-manifest.json"
            path.write_text("[]\n")
            preview = {**VALID, "license_status": "preview", "license_type": "preview-comp", "watermarked": True}
            append_asset(path, preview)
            self.assertEqual([a["id"] for a in purchase_list(path)], ["a0001"])
            updated = mark_purchased(path, "a0001")
            self.assertEqual(updated["file"], preview["file"])
            self.assertFalse(updated["watermarked"])
            self.assertEqual(purchase_list(path), [])
```

Add a download test whose fake opener returns `b"media"` and whose failing opener raises after one chunk. Assert successful bytes land at `destination`, failures leave neither destination nor `.partial`, and an existing destination is never overwritten. Add provider parser fixtures for Wikimedia `imageinfo`, Internet Archive `response.docs`, and Pexels `photos`; assert each normalized result contains provider, asset ID, source URL, preview URL, and license-review metadata without storing an API key.

- [ ] **Step 2: Watch the sourcing contracts fail**

Run: `.venv/Scripts/python.exe -m unittest python.test_sourcing -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.sourcing'`.

- [ ] **Step 3: Implement manifest validation and purchase export**

Require the exact fields shown in spec §5.1, unique case-insensitive asset IDs, repository-relative POSIX file paths, safe shot IDs matching `s[0-9]{3}`, ISO dates, and known enum values. `mark_purchased()` sets only `license_status="purchased"`, `license_type="paid-standard"` for formerly paid previews, and `watermarked=false`; it never changes `file`.

`tools/manifest_report.py` must write `dist/license-purchase-list.md`, grouped by provider, with asset ID, purchase/source URL, local path, shot IDs, and notes. Its upload gate must exit 1 when any manifest entry has `license_status="preview"` and print `UPLOAD BLOCKED: N preview assets`; otherwise print `LICENSE GATE CLEAR`.

- [ ] **Step 4: Implement atomic binary downloads and provider CLIs**

Use a `.partial` sibling, 1 MiB chunks, a 60-second timeout, explicit maximum bytes, SHA-256 logging in memory only, and `os.replace()` only after a complete response. Reject non-HTTP(S) schemes and redirects to non-HTTP(S) schemes. Provider commands:

```bash
python -m tools.sourcing.providers wikimedia "Carrington event" --limit 5
python -m tools.sourcing.providers internet-archive "Carrington telegraph" --limit 5
python -m tools.sourcing.providers pexels "solar storm" --limit 5
```

The Pexels command must exit with a clear `PEXELS_API_KEY is required` message when the variable is absent. No provider command may print the key.

- [ ] **Step 5: Add the browser screenshot helper**

Run: `npm install --save-dev playwright`
Run: `npx playwright install chromium`

Implement `node tools/sourcing/screenshot.mjs --url <http(s)-or-file-URL> --out <local.png>` with a 1920×1080 viewport, `domcontentloaded`, a 1.5-second settling delay, full-page PNG capture, and explicit browser cleanup. The Node test must screenshot a local HTML fixture and assert the PNG signature plus a file size above 1,000 bytes.

- [ ] **Step 6: Verify sourcing and existing suites**

Run: `.venv/Scripts/python.exe -m unittest python.test_sourcing -v`
Expected: all sourcing tests PASS.

Run: `npm test -- --test-name-pattern=screenshot`
Expected: screenshot test PASS.

Run: `.venv/Scripts/python.exe -m unittest discover -s python -v && npm test`
Expected: all tests PASS.

- [ ] **Step 7: Record the verification checkpoint**

Record test counts and state explicitly that live paid-provider preview behavior is not proven by mocked provider tests.

---

### Task 3: Blender 4.5 RX 580 Verification and Selection

**Files:**
- Create: `workflow/config.py`
- Create: `tools/blender/verification_beat.py`
- Create: `tools/blender/verify_upgrade.py`
- Create: `tools/blender/install_commotion.py`
- Create: `workflow/blender.json` only after visual acceptance
- Test: `python/test_blender_config.py`
- Output: `work/blender-upgrade/{blender-4.1.png,blender-4.5.png,comparison.png,report.json,commotion.json}`

**Interfaces:**
- Consumes: installed portable Blender paths and the independent license/config tools from Tasks 1–2.
- Produces: `blender_executable(repo_root: Path, environ: Mapping[str, str] | None = None) -> Path`; environment `BLENDER_EXE` wins, then accepted `workflow/blender.json`, then legacy 4.1.

- [ ] **Step 1: Write the failing configuration contract**

```python
import json
import tempfile
import unittest
from pathlib import Path
from workflow.config import blender_executable

class BlenderConfigTests(unittest.TestCase):
    def test_environment_then_accepted_config_then_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "tools/blender-4.1.0-windows-x64/blender.exe"
            self.assertEqual(blender_executable(root), legacy)
            config = root / "workflow/blender.json"
            config.parent.mkdir()
            config.write_text(json.dumps({"production": "tools/custom/blender.exe"}))
            self.assertEqual(blender_executable(root), root / "tools/custom/blender.exe")
            self.assertEqual(blender_executable(root, {"BLENDER_EXE": "D:/override/blender.exe"}), Path("D:/override/blender.exe"))
```

- [ ] **Step 2: Watch the configuration contract fail**

Run: `.venv/Scripts/python.exe -m unittest python.test_blender_config -v`
Expected: FAIL because `workflow.config` does not exist.

- [ ] **Step 3: Implement configuration and one procedural verification beat**

`verification_beat.py` runs inside either Blender version and creates the same 640×360 frame: glass outer shell, metallic inner mechanism, emissive core, shadow-catching ground, volumetric cube, camera, and area lights. Select `BLENDER_EEVEE` on 4.1 and `BLENDER_EEVEE_NEXT` on 4.2–4.5, use 32 samples, set frame 48, save the version-specific `.blend`, and render PNG. Keep geometry, lighting, seed, frame, and color management identical.

`verify_upgrade.py` runs both binaries in background factory mode, captures versioned logs, requires exit code 0 and nonempty PNGs, creates a side-by-side `comparison.png` with ffmpeg, and writes `report.json` containing versions, return codes, output sizes, and elapsed seconds. It does not select 4.5 until called with `--accept` and an existing successful report.

- [ ] **Step 4: Verify host contracts, then execute the real GPU/driver probe**

Run: `.venv/Scripts/python.exe -m unittest python.test_blender_config -v`
Expected: PASS.

Run: `python tools/blender/verify_upgrade.py`
Expected: both 4.1 and 4.5 renders exist, return codes are 0, and no EEVEE/driver initialization error appears in the logs.

- [ ] **Step 5: Inspect visual evidence and select the production binary**

Read `work/blender-upgrade/comparison.png`. Confirm that the 4.5 frame contains the shell, internal mechanism, shadows, emissive core, and visible volume rather than a black or partial frame. Record differences honestly; a successful launch alone is not visual verification.

Run: `python tools/blender/verify_upgrade.py --accept`
Expected: `workflow/blender.json` points to `tools/blender-4.5.15-windows-x64/blender.exe` and legacy 4.1 remains unchanged.

- [ ] **Step 6: Install and activate Commotion in the portable 4.5 configuration**

Run Blender 4.5 in background mode with `BLENDER_USER_CONFIG` set to `work/blender-upgrade/config`, call `bpy.ops.preferences.addon_install(filepath=<commotion.zip>)`, enable the module supplied by the archive, save user preferences, then run a second background process that imports the enabled module and writes `commotion.json` with its version and activation state.

Expected: `commotion.json` reports `"enabled": true`; failure leaves production usable because Commotion is optional.

- [ ] **Step 7: Run regression checks and record the checkpoint**

Run: `.venv/Scripts/python.exe -m unittest discover -s python -v`
Expected: all tests PASS. Record actual render times and any visual limitations separately from test results.

---

### Task 4: Fern Shot-Recipe Library

**Files:**
- Create: `work/shot-recipes/project.json`
- Create: `work/shot-recipes/index.html`
- Create: `work/shot-recipes/assets/gsap.min.js` by copying the existing local GSAP file
- Create: `work/shot-recipes/assets/archival-plate.svg` as a project-owned test image
- Create: `work/shot-recipes/qa/` snapshots and lint output
- Test: `tests/shot-recipes.test.ts`

**Interfaces:**
- Consumes: HyperFrames, local GSAP, the house composition pattern in `work/showpiece-house/`, and no external network assets.
- Produces: four 4-second sections with stable IDs `recreated-ui`, `kinetic-quote`, `ken-burns`, and `news-lower-third`; `window.__timelines.main` exposes a paused deterministic timeline.

- [ ] **Step 1: Write failing structural and motion contracts**

The Node test must read the composition and assert:
- root composition is 1920×1080 with duration 16;
- all four section IDs exist with `data-start="0|4|8|12"` and `data-duration="4"`;
- recreated UI contains semantic `article`, `header`, and `button` elements, a cursor, typed text, and a quoted-element highlight rather than a screenshot;
- quote words, Ken Burns transform, and news source lower-third each have GSAP keyframes at deterministic section-relative times;
- every visible annotation is at least 28px and no asset URL uses HTTP(S).

- [ ] **Step 2: Watch the recipe contract fail**

Run: `npm test -- --test-name-pattern=shot-recipes`
Expected: FAIL because `work/shot-recipes/index.html` is absent.

- [ ] **Step 3: Build the four recipes**

Use a 16-second main composition. Recreated UI shows a fictional forum post with typed text, cursor movement, and highlight zoom. Kinetic quote reveals source-styled lines and words with a visible source card. Ken Burns applies slow scale/translation to the project-owned SVG plate with a restrained highlight mask. News insert uses a project-owned background and a lower-third containing publisher, clip title, and date fields. Keep all copy in English and all timing driven by the four section starts, not unrelated magic numbers.

- [ ] **Step 4: Run structural tests and HyperFrames lint**

Run: `npm test -- --test-name-pattern=shot-recipes`
Expected: all recipe tests PASS.

Run from `work/shot-recipes/`: `npx hyperframes lint`
Expected: 0 errors.

- [ ] **Step 5: Capture and inspect midpoint QA snapshots**

Capture frames at 2, 6, 10, and 14 seconds with the HyperFrames snapshot CLI into `work/shot-recipes/qa/`. Read the contact sheet or all four images. Verify legible text, no overlap, visible cursor/highlight, quote progression, Ken Burns framing, and an unobscured source lower-third. Record the snapshot paths and any issues; numeric DOM checks do not replace this visual pass.

- [ ] **Step 6: Run full regressions and record the checkpoint**

Run: `npm test && .venv/Scripts/python.exe -m unittest discover -s python -v`
Expected: all tests PASS.

---

### Task 5: Detailed 3D Technique Pack

**Files:**
- Create: `tools/blender/techniques/common.py`
- Create: `tools/blender/techniques/labels.py`
- Create: `tools/blender/techniques/build.py`
- Create: `tools/blender/techniques/validate.py`
- Create: `work/technique-pack/` generated scenes, stills, and `validation.json`
- Test: `python/test_blender_techniques.py`

**Interfaces:**
- Consumes: accepted Blender 4.5 from `blender_executable()` and the local Inter font.
- Produces: `cutaway.blend`, `exploded.blend`, `xray.blend`, `zoom-inside.blend`, one midpoint PNG per scene, and `validation.json`; `labels.py` exposes `add_label(text, anchor, screen, camera, frames) -> list[bpy.types.Object]`.

- [ ] **Step 1: Write the failing real-Blender integration contract**

The test invokes the accepted Blender binary in background mode with `tools/blender/techniques/build.py -- --output <tempdir>`, then invokes `validate.py` for each scene. Assert exit code 0 and these concrete contracts:
- cutaway has `shell`, `core`, `CUTAWAY` Difference modifier using Exact solver, and a visible label;
- exploded has at least four named parts and an `EXPLODE` Geometry Nodes modifier with per-part separation;
- xray shell material mixes Transparent BSDF with a surface shader and animates the mix factor;
- zoom-inside has camera location keyframes at frames 1 and 150 and an internal mechanism visible at the midpoint;
- every scene has a camera, 30fps, 150-frame range, a nonempty midpoint PNG, and label text using the bundled Inter font.

- [ ] **Step 2: Watch the integration contract fail**

Run: `.venv/Scripts/python.exe -m unittest python.test_blender_techniques -v`
Expected: FAIL because the builder module or generated scenes do not exist.

- [ ] **Step 3: Implement shared materials, camera, primitives, and labels**

`common.py` owns scene reset, EEVEE Next setup, color management, primitive/material helpers, lighting, and still rendering. `labels.py` ports the existing world-anchor/screen-space leader-line behavior from `cable_render.py`, including camera-parented text, backing plate, animated leader endpoint, anchor dot, and linear interpolation. It must not import the entire legacy cable scene.

- [ ] **Step 4: Implement four independent scene builders**

Build each scene procedurally with named objects and a 5-second animation. Use an animated Boolean cutter for cutaway, Geometry Nodes instance/offset separation for exploded, animated Transparent BSDF mix for xray, and a camera dolly through a clipped/faded shell for zoom-inside. Add at least one legible anchored label per scene and save the `.blend` before rendering its midpoint PNG.

- [ ] **Step 5: Run Blender validation and inspect all four stills**

Run: `.venv/Scripts/python.exe -m unittest python.test_blender_techniques -v`
Expected: all integration tests PASS on the accepted 4.5 binary.

Read the four midpoint PNGs. Verify that the cut is visible, separated parts remain readable, the internal mechanism is visible through the ghost shell, and the zoom ends inside a recognizable structure. Check label contrast, leader endpoints, clipping, and empty/black frames. Record render times and any RX 580 artifacts.

- [ ] **Step 6: Run full regressions and record the checkpoint**

Run: `.venv/Scripts/python.exe -m unittest discover -s python -v && npm test`
Expected: all tests PASS. State that the technique pack is starter-scene verification, not yet a complete pilot episode.

---

### Task 6: Carrington Event Pilot Through Preview and Purchase List

**Files:**
- Create: `work/episode-carrington/` through `init_episode()`
- Create: `research/sources.md`, `research/facts.json`, `story/beat-sheet.md`, `script/narration.md`, `script/narration_request.json`
- Create: `assets/license-manifest.json` entries and sourced media
- Create: `vo/`, `motion/`, `edit/`, `qc/`, and `dist/` production artifacts
- Create: `dist/episode-carrington-preview.mp4`, `dist/license-purchase-list.md`, `dist/thumbnail.png`, `dist/metadata.md`
- Test: `work/episode-carrington/test_assemble_timing.py` using the existing cumulative-frame/ffprobe pattern

**Interfaces:**
- Consumes: every interface from Tasks 1–5, existing `python/narrate.py`, existing Kokoro models, existing cumulative-frame assembly, and ffmpeg/ffprobe.
- Produces: a complete local preview and purchase package. It never produces an upload action.

- [ ] **Step 1: Initialize the exact pilot package**

Run: `.venv/Scripts/python.exe -m workflow.init_episode --root work --slug episode-carrington --title "The Carrington Event: When the Sun Reached the Telegraph"`
Expected: the nine-phase layout exists with an empty manifest and English metadata.

- [ ] **Step 2: Produce citation-backed research**

Research the 1859 observations and telegraph effects, Carrington's sunspot drawing, solar flares/CMEs, magnetosphere interaction, geomagnetically induced currents, modern power-grid risk, and mitigation. Use authoritative NASA/NOAA/USGS and primary/public-domain historical sources where available, with independent corroboration for contested numerical claims. Write every supported claim to `facts.json` with claim ID, text, citations, confidence, and permitted visual interpretation. Do not carry forward dramatic claims that the sources do not support.

Gate: at least 15 useful sources, every factual narration claim maps to a claim ID, and every citation has a supporting extract or an explicitly marked snippet-only limitation.

- [ ] **Step 3: Write the locked story structure**

Use a 12–13 minute target: a 0:00–0:45 event hook; Act I 0:45–3:30 for telegraph infrastructure and the 1859 chronology; Act II 3:30–8:00 for Sun-to-ground mechanism; Act III 8:00–11:30 for modern infrastructure and mitigation; payoff 11:30–12:30 connecting historical evidence to present engineering. Each act ends on a tension or reveal and every beat names its visual and transition anchor.

- [ ] **Step 4: Write and validate the narration/shot plan**

Write approximately 1,700–2,100 English words across 80–110 utterances. Every row has utterance ID, exact narration, visual ID, visual instruction, and claim IDs. Assign 180–216 shots for the final cut and six detailed 3D beats: solar flare, CME travel, magnetosphere compression, ground-induced current, telegraph circuit, and modern transformer response. Keep each 3D beat within 5–20 seconds and use diagrams whenever they are clearer than decorative imagery.

- [ ] **Step 5: Source media and log rights before timeline use**

Prioritize public-domain historical telegraph material, Carrington's drawing, historical newspapers/maps, and NASA solar imagery. Record every downloaded item immediately with the Task 2 API. Use preview/screenshot media only when accessible without bypassing authentication or access controls; otherwise select a free alternative. Run manifest validation after each sourcing batch and keep provider/asset IDs and attribution exact.

Gate: every external file in the shot plan has one manifest entry, every entry names its shots, and there is no CC BY-NC entry.

- [ ] **Step 6: Generate narration and build the visual timeline**

Generate Kokoro WAVs and timings with the existing narration adapter. Apply auto-editor only as a conservative first-pass cleanup after measuring its effect; retain manual creative pacing. Build recreated UI, quote, archival, news, diagram, and six Blender shots using Tasks 4–5. Use the existing cumulative `round(elapsed*FPS)` shot counts and `tpad=stop_mode=clone:stop=1` before trim. Render section QA and transition-midpoint snapshots before final assembly.

- [ ] **Step 7: Assemble the preview and run media verification**

Assemble 1920×1080, 30fps, H.264 video with AAC audio. Target 600–900 seconds, 15–18 cuts/min, no static shot over 8 seconds without meaningful motion, and −16±1 LUFS integrated loudness. Run the episode's cumulative-frame timing test with ffprobe, extract contact sheets including all six 3D beats and transition midpoints, and inspect them visually. Verify no clipped words, caption overlap, empty frames, missing labels, or watermarked media accidentally absent from the manifest.

- [ ] **Step 8: Export packaging and enforce the license gate**

Run: `python tools/manifest_report.py --episode work/episode-carrington`
Expected: `dist/license-purchase-list.md` lists every remaining preview asset grouped by provider; the command exits 1 while previews remain, which is the intended preview state.

Create `thumbnail.png` and `metadata.md` containing title, description, chapters, sources, and all required attribution. No upload command is run. The delivery report must distinguish fully rendered/verified items from anything still requiring user viewing, listening, license purchase, or clean-asset replacement.

- [ ] **Step 9: Run final regression and completion audit**

Run: `.venv/Scripts/python.exe -m unittest discover -s python -v && npm test`
Run: `.venv/Scripts/python.exe -m unittest discover -s work/episode-carrington -p "test_*.py" -v`
Expected: all runnable tests PASS and the pilot media gates have fresh evidence. Audit every objective clause: detailed 3D, free-renderer research, download-now/license-later sourcing, free fallback, increased research/motion/edit depth, installed capabilities, concrete user actions, and no upload.

## Execution Handoff

The existing user mandate explicitly says to install and start without another approval pause, so execution uses **Subagent-Driven Development** with a fresh implementer per task and independent review. Tasks 1–5 are the infrastructure wave. Task 6 starts after their required interfaces are verified; its research may proceed independently while rendering infrastructure is being built.
