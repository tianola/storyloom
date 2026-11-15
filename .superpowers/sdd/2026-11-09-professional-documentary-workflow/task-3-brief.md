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

