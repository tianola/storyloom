# Task 5 Brief: Detailed 3D Technique Pack

## Context

This task builds four reusable Blender 3D techniques that demonstrate professional documentary visualization methods. These techniques will be used by Task 6 (Carrington pilot) and future episodes.

## What exists

- **Blender 4.5.15 LTS**: Accepted for production at `tools/blender-4.5.15-windows-x64/blender.exe`. Selection via `workflow/config.py:blender_executable()`.
- **EEVEE Next**: Blender 4.5 uses `BLENDER_EEVEE_NEXT` engine (not legacy EEVEE).
- **Inter font family**: Available at `tools/fonts/Inter-*.ttf` (Regular, Medium, SemiBold, Bold, etc.).
- **Legacy label pattern**: See `work/episode-cables/cable_render.py` for the world-anchor/screen-space leader-line behavior that must be ported to `labels.py`. Do NOT import the entire legacy scene.
- **Verification beat**: See `tools/blender/verification_beat.py` for the scene construction pattern (glass shell, metallic rings, emissive core, etc.).

## Files to create

1. `tools/blender/techniques/__init__.py` — empty module marker
2. `tools/blender/techniques/common.py` — shared utilities (scene reset, EEVEE Next setup, color management, primitive/material helpers, lighting, still rendering)
3. `tools/blender/techniques/labels.py` — ported label system with `add_label(text, anchor, screen, camera, frames) -> list[bpy.types.Object]`
4. `tools/blender/techniques/build.py` — CLI that builds all four scenes and saves them to `--output <dir>`
5. `tools/blender/techniques/validate.py` — CLI that validates each scene and writes `validation.json`
6. `python/test_blender_techniques.py` — integration test that invokes Blender in background mode
7. `work/technique-pack/` — output directory for generated scenes and stills

## The four techniques

### 1. Cutaway (cutaway.blend)

- Outer shell (sphere or box) with an animated Boolean Difference modifier
- Inner core mechanism (rings, gears, or structured geometry) visible through the cut
- Modifier name: `CUTAWAY`, solver: Exact
- The cutter object animates to reveal more of the interior over 150 frames
- At least one legible anchored label pointing to the core

### 2. Exploded (exploded.blend)

- At least four named parts (e.g., `part_housing`, `part_rotor`, `part_stator`, `part_shaft`)
- Geometry Nodes modifier named `EXPLODE` that separates parts along their normals or a fixed axis
- Per-part separation animated over 150 frames (parts move apart, then back together)
- At least one legible anchored label pointing to a named part

### 3. X-ray (xray.blend)

- Outer shell with a material that mixes Transparent BSDF and a surface shader (Principled BSDF or Diffuse BSDF)
- The mix factor is animated: shell starts opaque, becomes transparent, then opaque again
- Inner mechanism visible through the transparent shell
- At least one legible anchored label pointing to the inner mechanism

### 4. Zoom-inside (zoom-inside.blend)

- Outer shell (can be clipped/faded or have a hole)
- Internal mechanism (detailed geometry inside the shell)
- Camera location keyframes at frame 1 (outside, looking at the object) and frame 150 (inside, looking at the mechanism)
- Smooth camera dolly animation between the two positions
- At least one legible anchored label visible at the midpoint (frame 75)

## Common requirements for all scenes

- Camera: present and named `Camera`
- Frame rate: 30 fps
- Frame range: 1–150 (5 seconds)
- Resolution: 640×360 (verification size, not full production)
- Render engine: BLENDER_EEVEE_NEXT
- Color management: AgX
- Lighting: at least one area light or sun light
- Midpoint PNG: rendered at frame 75, saved as `<scene-name>.png`, nonempty file
- Label text: uses the bundled Inter font (load from `tools/fonts/Inter-Regular.ttf` or similar)
- Save .blend: each scene saved as `<scene-name>.blend` before rendering

## Label system (labels.py)

Port the label pattern from `cable_render.py`. The public function signature:

```python
def add_label(text: str, anchor: tuple[float, float, float], screen: tuple[float, float, float], camera: bpy.types.Object, frames: int) -> list[bpy.types.Object]:
    """
    anchor: 3D world position the label points to
    screen: 3D world position where the label text appears
    camera: the scene camera (for orientation)
    frames: total animation length
    
    Returns: list of created objects (text, backing plate, leader line, anchor dot)
    """
```

The label must include:
- Text object using Inter font
- Backing plate (dark semi-transparent plane behind text)
- Leader line (thin cylinder or edge from anchor to screen position)
- Anchor dot (small sphere at the anchor position)
- Optional: animated leader endpoint that draws from anchor to screen over the first 30 frames

## Test contract (test_blender_techniques.py)

The test must:
1. Invoke Blender in background mode with `tools/blender/techniques/build.py -- --output <tempdir>`
2. Verify exit code 0
3. For each scene, invoke `validate.py -- --scene <name> --blend <path>` and verify exit code 0
4. Assert the concrete contracts:
   - cutaway: has `shell`, `core`, `CUTAWAY` Difference modifier with Exact solver, visible label
   - exploded: has ≥4 named parts, `EXPLODE` Geometry Nodes modifier with per-part separation
   - xray: shell material mixes Transparent BSDF with surface shader, animates mix factor
   - zoom-inside: camera location keyframes at frames 1 and 150, internal mechanism visible at midpoint
   - every scene: camera, 30fps, 150-frame range, nonempty midpoint PNG, label text using Inter font

## TDD sequence

1. **RED**: Write the failing test first in `python/test_blender_techniques.py`. Run `.venv/Scripts/python.exe -m unittest python.test_blender_techniques -v` and verify it fails because the builder module or generated scenes do not exist.

2. **GREEN**: Implement `common.py`, `labels.py`, `build.py`, `validate.py`. Run the test again and verify it passes.

3. **Visual inspection**: Read the four midpoint PNGs. Verify that the cut is visible, separated parts remain readable, the internal mechanism is visible through the ghost shell, and the zoom ends inside a recognizable structure. Check label contrast, leader endpoints, clipping, and empty/black frames.

4. **Full regression**: Run `.venv/Scripts/python.exe -m unittest discover -s python -v && npm test` to verify no regressions.

## Global constraints (carried from plan)

- Rendering is CPU-only + AMD EEVEE (RX 580 4GB, no CUDA/ROCm).
- Keep HyperFrames as the primary renderer for 2D. Blender is for 3D beats only.
- Do not publish, upload, delete remote material, or create git commits.
- Run Python tests with `.venv/Scripts/python.exe -m unittest discover -s python -v`.
- Use Blender 4.5.15 LTS (accepted production version).

## Report requirements

Write your full report to `F:\AI-PROJECTS\longform-explainer\.superpowers\sdd\2026-11-09-professional-documentary-workflow\task-5-report.md`.

Include:
- Exact files created with their paths.
- RED evidence: the failing test command and its output.
- GREEN evidence: the passing test command and its output.
- Visual inspection results for all four midpoint PNGs (what you saw, any artifacts).
- Full regression results (Python unittest + npm test).
- Render times for each scene.
- Any RX 580 artifacts or EEVEE limitations encountered.
- Any concerns or limitations.
- Statement that no commits were made and no remote material was published.

## Important notes

- This is a **real Blender integration task**. The test must invoke the actual Blender binary, not mock it.
- The scenes are **starter-scene verification**, not complete pilot episode content. They prove the techniques work.
- If Blender crashes or hangs, capture the log and report it. Do not silently skip the render.
- If a technique cannot be implemented as specified (e.g., Geometry Nodes API limitation), document the workaround and adjust the test contract accordingly.
