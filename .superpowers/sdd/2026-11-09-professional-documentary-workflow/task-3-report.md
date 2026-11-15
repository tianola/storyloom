# Task 3 Report: Blender 4.5 RX 580 Verification and Selection

## Outcome

Blender 4.5.15 LTS is accepted for new production. Both the real same-beat render gate and the required human-readable visual inspection gate passed. `workflow/blender.json` now selects `tools/blender-4.5.15-windows-x64/blender.exe`. The legacy Blender 4.1 binary and episode scripts were not modified.

Commotion 2.5.0 was installed into the isolated portable 4.5 configuration and verified in a second Blender process. It reports `enabled: true`, successful import, and a registered `Scene.commotion` property.

## What I implemented

- `workflow/config.py`: `blender_executable(repo_root, environ=None)` applies the required precedence: nonempty `BLENDER_EXE`, then `workflow/blender.json` `production`, then the legacy 4.1 executable.
- `tools/blender/verification_beat.py`: one deterministic procedural 640x360 scene with a glass outer shell, two metallic mechanism rings and eight teeth, emissive core, shadow-catching ground, volumetric cube, camera, and three area lights. It selects `BLENDER_EEVEE` before 4.2 and `BLENDER_EEVEE_NEXT` for 4.2–4.5, uses 32 render samples, frame 48, seed 48, and identical AgX color management. It saves a version-specific `.blend` before rendering.
- `tools/blender/verify_upgrade.py`: runs both binaries in background factory mode with `--python-exit-code 1`, captures versioned logs, checks return codes/nonempty PNGs/EEVEE-GPU-driver error patterns, creates an ffmpeg side-by-side PNG, and writes the machine-readable report. Normal execution never selects 4.5. `--accept` requires an existing successful report and is the only path that writes `workflow/blender.json`.
- `tools/blender/install_commotion.py`: discovers the top-level module from the supplied archive, installs and enables it under isolated `BLENDER_USER_CONFIG` and `BLENDER_USER_SCRIPTS`, saves preferences, then verifies import/activation/version/registered property in a fresh Blender process.
- `python/test_blender_config.py`: the brief's configuration contract verbatim.

No Mograph assets or node groups were used. No production renderer or legacy episode was migrated or refactored. No dependencies were added.

## Files created or modified

Source and configuration:

- `F:\AI-PROJECTS\longform-explainer\workflow\config.py`
- `F:\AI-PROJECTS\longform-explainer\workflow\blender.json` — created only after the successful report and actual visual inspection
- `F:\AI-PROJECTS\longform-explainer\tools\blender\verification_beat.py`
- `F:\AI-PROJECTS\longform-explainer\tools\blender\verify_upgrade.py`
- `F:\AI-PROJECTS\longform-explainer\tools\blender\install_commotion.py`
- `F:\AI-PROJECTS\longform-explainer\python\test_blender_config.py`
- `F:\AI-PROJECTS\longform-explainer\.superpowers\sdd\2026-11-09-professional-documentary-workflow\task-3-report.md`

Render and verification artifacts:

- `F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\blender-4.1.blend`
- `F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\blender-4.1.png`
- `F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\blender-4.1.log`
- `F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\blender-4.5.blend`
- `F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\blender-4.5.png`
- `F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\blender-4.5.log`
- `F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\comparison.png`
- `F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\comparison.log`
- `F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\report.json`
- `F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\commotion.json`
- `F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\commotion-install.log`
- `F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\commotion-verify.log`
- `F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\config\userpref.blend`
- `F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\scripts\addons\commotion-master\` — the supplied archive's extracted add-on files, including `__init__.py`, `blender_manifest.toml`, modules, license/readme, and Blender-generated `__pycache__` files

The previously installed binaries and `tools/blender-addons/commotion.zip` were consumed, not modified. `work/episode-cables/cable_render.py` remains timestamped 2026-11-08 13:05 and was not touched. No other legacy episode source was edited.

## Host TDD evidence

### RED — contract before implementation

The test was written while `workflow/config.py` did not exist.

Exact command:

```text
.venv/Scripts/python.exe -m unittest python.test_blender_config -v
```

Actual result: exit code 1.

```text
ModuleNotFoundError: No module named 'workflow.config'

Ran 1 test in 0.000s

FAILED (errors=1)
```

This is the expected missing-feature failure, not a fixture or assertion defect.

### GREEN — minimal implementation

Exact command:

```text
.venv/Scripts/python.exe -m unittest python.test_blender_config -v
```

Actual result: exit code 0.

```text
test_environment_then_accepted_config_then_legacy ... ok

Ran 1 test in 0.009s

OK
```

Before acceptance, a real call to `blender_executable(Path('.'))` printed `tools\blender-4.1.0-windows-x64\blender.exe`, proving the safe legacy fallback. After acceptance it printed `tools\blender-4.5.15-windows-x64\blender.exe`.

## Real Blender render verification

Exact host command:

```text
python tools/blender/verify_upgrade.py
```

Host result: exit code 0. Machine-readable evidence: `F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\report.json` with `success: true`.

### Blender 4.1

Version: `4.1.0`, hash `40a5e739e270`. Engine: `BLENDER_EEVEE`.

Exact command recorded in `report.json`:

```text
F:\AI-PROJECTS\longform-explainer\tools\blender-4.1.0-windows-x64\blender.exe --background --factory-startup --python-exit-code 1 --python F:\AI-PROJECTS\longform-explainer\tools\blender\verification_beat.py -- --output F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\blender-4.1.png
```

- Process return code: 0
- Wall elapsed: 4.978 seconds
- Blender-reported render/save time: 2.09 seconds
- PNG: `F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\blender-4.1.png`
- PNG size: 325,013 bytes
- Scene: `F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\blender-4.1.blend`
- Log: `F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\blender-4.1.log`
- Driver/EEVEE initialization errors detected: none

The log shows frame 48, all named scene objects syncing, 32/32 samples, and `Blender quit`. It also contains the non-EEVEE warning `TBBmalloc: skip allocation functions replacement ...`; this did not prevent the completed render.

### Blender 4.5

Version: `4.5.15 LTS`, hash `5afeabba6097`. Engine: `BLENDER_EEVEE_NEXT`.

Exact command recorded in `report.json`:

```text
F:\AI-PROJECTS\longform-explainer\tools\blender-4.5.15-windows-x64\blender.exe --background --factory-startup --python-exit-code 1 --python F:\AI-PROJECTS\longform-explainer\tools\blender\verification_beat.py -- --output F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\blender-4.5.png
```

- Process return code: 0
- Wall elapsed: 19.259 seconds
- Blender-reported render/save time: 15.92 seconds
- PNG: `F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\blender-4.5.png`
- PNG size: 327,071 bytes
- Scene: `F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\blender-4.5.blend`
- Log: `F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\blender-4.5.log`
- Driver/EEVEE initialization errors detected: none

The log shows frame 48, 32/32 samples, a saved PNG, and `Blender quit`.

### Side-by-side construction

The host used the installed ffmpeg 9.0.2:

```text
ffmpeg -y -i F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\blender-4.1.png -i F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\blender-4.5.png -filter_complex hstack=inputs=2 -frames:v 1 F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\comparison.png
```

- Return code: 0
- Elapsed: 0.099 seconds
- Comparison: `F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\comparison.png`
- Size: 585,454 bytes
- Log: `F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\comparison.log`

## Actual visual inspection and acceptance

I used the image-reading capability on `F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\comparison.png` before running `--accept`. The left frame is Blender 4.1 and the right frame is Blender 4.5.

Concrete observations:

- Both images are complete, lit frames rather than black, empty, partially initialized, or missing geometry.
- Both contain the outer spherical glass shell, visible internal metal rings/mechanism, bright cyan emissive core, ground/contact shadow, and a visible blue-to-warm atmospheric volume.
- The 4.5 shell has clearer glossy reflection bands and the inner metallic/copper ring is easier to distinguish. Its core surround is cleaner and less grainy.
- The 4.1 shell looks more diffuse and its core surround has more visible speckle/dither. Its contact shadow is darker and more pronounced; the 4.5 shadow is softer/lighter.
- Both show some 32-sample glass dither/noise. This is a visual limitation, not a missing frame or driver failure.
- I saw no obvious geometry corruption, driver-specific corruption, clipped-off subject, or absent volumetric region in either frame.

Only after those observations did I run:

```text
python tools/blender/verify_upgrade.py --accept
```

Result: exit code 0. It printed `Accepted after external visual inspection: workflow/blender.json`.

Final `F:\AI-PROJECTS\longform-explainer\workflow\blender.json`:

```json
{
  "production": "tools/blender-4.5.15-windows-x64/blender.exe"
}
```

Final `blender_executable()` selection: `tools\blender-4.5.15-windows-x64\blender.exe`. `BLENDER_EXE` still overrides it, and removing the accepted config restores the 4.1 fallback.

## Commotion installation and activation

Exact host command:

```text
python tools/blender/install_commotion.py
```

Host result: exit code 0.

The supplied archive was `F:\AI-PROJECTS\longform-explainer\tools\blender-addons\commotion.zip`; its discovered module was `commotion-master`. The install process used Blender 4.5.15 LTS in background factory mode, called `bpy.ops.preferences.addon_install(filepath=...)`, called `bpy.ops.preferences.addon_enable(module="commotion-master")`, and saved user preferences. The second process ran without factory startup so it loaded the saved preferences, imported the module, read its manifest, and checked `addon_utils.check()`.

Environment isolation:

- `BLENDER_USER_CONFIG=F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\config`
- `BLENDER_USER_SCRIPTS=F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\scripts`

Evidence in `F:\AI-PROJECTS\longform-explainer\work\blender-upgrade\commotion.json`:

- `blender_version: 4.5.15 LTS`
- `module: commotion-master`
- `version: 2.5.0`
- `enabled: true`
- `import_succeeded: true`
- `scene_property_registered: true`
- `install_returncode: 0`
- `verify_returncode: 0`

`commotion-install.log` records installation into the isolated `scripts\addons` directory and `Writing userprefs ... ok`. `commotion-verify.log` records the second-process JSON evidence and `Blender quit`.

Non-blocking warning: the install log says the manifest-based add-on is missing legacy `bl_info`, which Blender warns can cause poor performance. The supplied 4.4+ manifest was not rewritten. Activation and registration nevertheless passed in the real second process. Production Blender remains usable without this optional add-on.

## Host regression checks

Final focused command:

```text
.venv/Scripts/python.exe -m unittest python.test_blender_config -v
```

Result: **1/1 PASS**, exit code 0, clean output.

Full command from the brief, run once after all implementation changes:

```text
.venv/Scripts/python.exe -m unittest discover -s python -v
```

Result:

```text
Ran 44 tests in 2.006s

OK
```

This is **44/44 PASS**, exit code 0, with no failures, errors, skips, or warning-contaminated test output. The previous 43 tests plus the new Blender configuration contract all ran. Node source was untouched and the Task 3 brief does not request a Node rerun; Node therefore remains at the supplied/previously verified 147/147 baseline, not a fresh Task 3 measurement.

## Tested versus unverified

### Tested and inspected

- Real configuration precedence through temporary roots and explicit environment mappings.
- Actual legacy fallback before acceptance and selected 4.5 path after acceptance.
- Real background EEVEE render of the same procedural frame on Blender 4.1.0 and EEVEE Next on 4.5.15 LTS, using the machine's local Windows driver path; no CUDA, ROCm, software-render flag, or alternate binary was used.
- Nonempty version-specific `.blend` and PNG outputs, 32/32 samples, clean process exits, and absence of detected EEVEE/GPU/driver initialization errors.
- Actual visual inspection of the side-by-side image, including the specific similarities, differences, and artifacts listed above.
- Acceptance only after that inspection.
- Real Commotion install, preference save, second-process import, enabled state, manifest version, and registered scene property.
- Focused and complete host Python tests.

### Explicitly unverified / limited

- This is one deterministic 640x360 midpoint verification beat, not a complete episode, animation motion test, long-duration stability test, or comprehensive EEVEE feature benchmark.
- The render proves the real local EEVEE execution path on this machine. It does not establish performance on other GPUs/drivers or provide a raw GPU-device identification string in the log.
- The 4.5 wall time for this small scene was 19.259 seconds versus 4.978 seconds on 4.1. These timings include process/scene setup and must not be extrapolated to episode render cost without representative production shots.
- Glass dither at 32 samples remains visible; higher-sample production look development has not been performed in this task.
- Commotion activation is verified, but its individual animation operators and production shot results were not exercised.
- Blender 5.2.3 was not tested or selected.
- No Node test was rerun because no Node code changed and it was outside this brief's required checks.

## Self-review findings and concerns

- The implementation uses exactly the requested source/test/config file boundaries and output directory. Blender scene construction is isolated in `verification_beat.py`; host orchestration remains in the two other tools.
- Both Blender subprocess paths use `--python-exit-code 1`, preventing a Python exception from being misreported as a successful render merely because the Blender launcher returned zero.
- Acceptance requires successful return codes, nonempty render outputs, no detected driver errors, a successful nonempty comparison, and an existing report. Actual visual inspection remains a deliberate external human/agent gate rather than a numeric comparison masquerading as viewing.
- The `.blend` is saved before rendering, and frame/seed/resolution/color-management settings are shared across versions. Only the version-required engine identifier and guarded API compatibility settings differ.
- Commotion is isolated from the global user configuration. Its installation does not write `workflow/blender.json` or alter production selection.
- No Mograph asset/node group, paid call, upload, purchase, remote deletion, git initialization, or commit occurred. No old episode was rewritten.
- Non-blocking observations are the visible 32-sample dither, the 4.1 TBBmalloc warning, and the Commotion legacy `bl_info` warning described above. There is no unresolved render or activation blocker.
