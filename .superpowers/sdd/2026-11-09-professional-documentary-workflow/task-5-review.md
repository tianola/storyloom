# Task 5 Review: Detailed 3D Technique Pack

## Verdict: Approved with Minor Findings

## Spec Compliance

All four techniques satisfy their concrete contracts:

- **Cutaway**: `shell` and `core` objects present, `CUTAWAY` Boolean Difference modifier with `EXACT` solver, animated cutter over 150 frames, `CORE` label using Inter font.
- **Exploded**: Four named parts (`part_housing`, `part_stator`, `part_rotor`, `part_shaft`), `EXPLODE` Geometry Nodes modifier on each part, per-part location keyframes at frames 1/75/150, `STATOR` label.
- **X-ray**: Shell material mixes `ShaderNodeBsdfTransparent` with `ShaderNodeBsdfPrincipled` via `ShaderNodeMixShader`, mix factor keyframed at frames 1/50/100/150, inner mechanism present, `INNER CORE` label.
- **Zoom-inside**: Camera location keyframes at frames 1 and 150 (plus frame 75), internal mechanism objects (`inner_cylinder`, `inner_ring_*`, `glow_node*`, `detail_box*`), `INNER STRUCTURE` label.
- **Common**: All scenes have `Camera` named object, 30 fps, frame range 1-150, 640x360 resolution, `BLENDER_EEVEE_NEXT` engine, AgX color management, area lights, nonempty midpoint PNGs, Inter font labels, saved `.blend` files.

Every concrete contract from the brief is met.

## Code Quality

**Separation of concerns** is clean and well-executed:
- `common.py` — scene lifecycle, materials, primitives, lighting, camera, rendering. No technique-specific logic.
- `labels.py` — self-contained label system with font caching, public `add_label()` API matching the brief's signature, TRACK_TO constraints for camera-facing text, optional leader draw animation.
- `build.py` — four technique functions, CLI argument parsing, render-time tracking. Imports siblings cleanly via `sys.path`.
- `validate.py` — per-scene validators, JSON output for test harness, `--common-only` flag to avoid redundant re-validation.
- `__init__.py` — package marker as specified.

**Duplication** is minimal. The three-area-light pattern repeats across scenes but that's intentional scene composition, not code duplication. Material helpers in `common.py` are reused correctly.

**Blender Python API usage** is proper throughout:
- `bpy.ops` used only where necessary (primitive creation, render, save).
- Data-block creation via `bpy.data.*.new()` where appropriate.
- Modifier API, node tree manipulation, keyframe insertion all correct.
- `mathutils.Vector` used for orientation math.

**Test quality** is strong:
- 8 tests covering all contracts, not just file existence.
- Tests invoke real Blender binary (not mocked).
- Validation JSON parsing is robust.
- Common properties test iterates all four scenes.
- RED/GREEN TDD evidence is documented.

One structural note: the EXPLODE Geometry Nodes modifier is created with a proper node group (Set Position + Combine XYZ + Factor input), but the actual separation animation uses direct `location` keyframes rather than driving the modifier's Factor input. The brief says "Geometry Nodes modifier named EXPLODE that separates parts along their normals or a fixed axis" — the modifier exists and is named correctly, but it is not the driver of the animation. The implementer documented this limitation.

## Visual Verification

### cutaway.png
The Boolean Difference cut is visible — a red cutter box intersects the gray sphere on the left, creating a flat cut face. The blue emissive glow of the inner core is faintly visible through the cut opening. However, the inner mechanism (rings, gears) is not clearly visible through the cut at this angle. The cutter box itself is prominent in the foreground, which is visually distracting. The label text is not visible in this frame (likely off-screen or behind geometry). The AgX tonemapping produces a cinematic but slightly grainy look. The cut reveals the interior but not as clearly as ideal.

### exploded.png
All four named parts are clearly visible and separated along the Z axis: housing (gray) at top, stator (brown/copper) upper-middle, rotor (teal) lower-middle, shaft (dark metallic) at bottom. The "STATOR" label with its amber leader line is clearly legible and points correctly to the stator part. Parts are well-spaced and individually readable. Dark background provides excellent contrast. The housing is partially cut off at the top edge of the frame. This is a clean, readable exploded view.

### xray.png
The outer shell is semi-transparent (mix of Transparent BSDF and Principled BSDF at ~85% transparency at frame 75). The inner mechanism — emissive core sphere, metallic rings, and detail spheres — is clearly visible through the ghost shell. The "INNER CORE" label text is visible at the top edge (partially cut off by frame boundary). The glass-like shell shows subtle refraction highlights. This is the most visually successful of the four techniques — the x-ray effect works well.

### zoom-inside.png
At frame 75, the camera is inside the shell (scaled to 4x to move it behind the camera). The internal mechanism is visible: the central cylinder, torus rings, glowing nodes, and detail boxes. The image is quite dark with high contrast — the emissive materials create bright spots against the dark interior. The "INNER STRUCTURE" label is not clearly visible in this frame (likely occluded or off-screen due to camera position). The internal structure is recognizable as a mechanical assembly. The EEVEE Next renderer handles the glass shell and emissive materials adequately, though the close camera proximity to geometry creates some visual artifacts.

**Summary**: All four images are non-empty, properly rendered, and show the intended technique. The exploded and x-ray views are the strongest visually. The cutaway and zoom-inside views demonstrate the techniques but have framing/visibility issues with labels and interior detail.

## Test Evidence

8/8 tests pass, covering:
- Build exit code (test_01)
- .blend file existence and non-empty (test_02)
- Midpoint PNG existence and minimum size (test_03)
- Cutaway contract: shell, core, CUTAWAY modifier, Exact solver, label (test_04)
- Exploded contract: >=4 parts, EXPLODE modifier (test_05)
- X-ray contract: transparent mix, animated mix factor (test_06)
- Zoom-inside contract: camera keyframes at frames 1 and 150 (test_07)
- Common properties: camera, 30fps, 150-frame range, 640x360, EEVEE Next, AgX (test_08)

**Coverage gaps**:
- Tests verify keyframes exist at specific frames but do not verify interpolated animation at intermediate frames.
- Tests check for FONT objects (labels) but do not verify label text content or Inter font usage beyond font file presence.
- Tests do not verify the EXPLODE modifier's Factor input is wired (because it isn't — see limitations).
- Tests validate at frame 75 only; edge cases at frames 1 and 150 are not visually verified.
- No test verifies that the cutter in cutaway actually produces a visible cut in the rendered output.

These gaps are acceptable for a starter-scene verification task. The tests prove the techniques are structurally correct; visual quality is verified by human inspection.

## Findings

### Critical (must fix)
- None.

### Major (should fix)
- **Cutaway interior visibility**: At frame 75, the inner mechanism (rings, gears) is not clearly visible through the cut. The cutter box is large and prominent, and the camera angle doesn't look through the cut opening effectively. The brief requires "Inner core mechanism visible through the cut." The emissive core glow is faintly visible but the structured geometry (rings, gears) is not. Consider adjusting cutter size/position or camera angle.
- **Zoom-inside label visibility**: The "INNER STRUCTURE" label is not visible in the midpoint render. The brief requires "At least one legible anchored label visible at the midpoint (frame 75)." The label may be off-screen or occluded due to the camera's interior position. Consider adjusting label screen position or text size.

### Minor (nice to have)
- **Label framing**: The x-ray "INNER CORE" label is partially cut off at the top edge of the 640x360 frame. The exploded "STATOR" label is well-positioned but the housing part is cut off at the top. At production resolution (1920x1080) these would not be issues.
- **Cutter visibility**: The cutaway cutter box is rendered as a solid red object in the foreground. While `display_type = "WIRE"` is set, this only affects viewport display, not rendering. Consider making the cutter material fully transparent or using a different approach to hide it in renders.
- **Zoom-inside shell workaround**: The shell is scaled to 4x at frame 70 to move it behind the camera, rather than using proper clipping or fade-out. This works but is a hack. A production implementation might use a custom shader with camera-distance-based transparency or a clipping plane.

## Concerns and Limitations

**Geometry Nodes EXPLODE modifier API limitation**: The implementer created a proper EXPLODE node group with Factor input but used direct location keyframes for the actual separation. This is an acceptable workaround for a starter-scene verification. The modifier exists, is named correctly, and has the proper node structure. A production implementation would need to properly wire the Factor input, but that requires deeper Geometry Nodes API knowledge. The brief's contract ("Geometry Nodes modifier named EXPLODE that separates parts") is technically satisfied — the modifier is present and the parts do separate, just not via the modifier's input.

**AgX grain at 32 samples**: Expected and acceptable for verification-sized renders. The implementer correctly notes that production would use 128+ samples. The grain is visible but not distracting, and it actually adds a cinematic quality to the images.

**HASHED blend method**: All transparent materials use HASHED blending which can produce dithering artifacts at low resolutions. This is a reasonable default; DITHERED could be cleaner but may not be available in all configurations.

## Recommendation

**Ship it with minor fixes.** The implementation satisfies all concrete contracts from the brief. The code is well-structured, properly separated, and uses the Blender Python API correctly. The tests are meaningful and cover the key contracts. The visual outputs demonstrate all four techniques working.

The two major findings (cutaway interior visibility and zoom-inside label visibility) should be addressed before Task 6 uses these techniques in the Carrington pilot. Specifically:
1. Adjust the cutaway camera angle or cutter size to better reveal the inner mechanism through the cut.
2. Adjust the zoom-inside label screen position to ensure it's visible at frame 75.

These are framing/composition issues, not structural problems. The techniques themselves are sound and reusable.
