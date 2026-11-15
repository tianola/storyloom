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

