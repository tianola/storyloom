# Task 2 Report: Sourcing and License Toolkit

## What I implemented

- Added the complete section 5.1 manifest validator with exact-field enforcement, field types, known enums, HTTP(S) source URLs, repository-relative POSIX paths, `s[0-9]{3}` shot IDs, and canonical ISO dates.
- Added case-insensitive uniqueness for internal `id` values and provider-scoped external `asset_id` values.
- Enforced the licensing rules: noncommercial licences are rejected, CC BY/CC BY-SA require attribution, BBC RemArc audio cannot be marked free, and editorial media requires explicit editorial-context notes.
- Added manifest append, preview-only purchase-list selection, and purchase transitions. `mark_purchased()` preserves `file` and every unrelated field, changes only the gate fields, converts `preview-comp` to `paid-standard`, preserves an editorial licence type, and rejects repeat/non-preview purchases.
- Added `tools/manifest_report.py`, which writes provider-grouped `dist/license-purchase-list.md` tables with internal ID, provider asset ID, source/purchase URL, local path, shots, and notes. It exits 1 with the exact preview count or exits 0 with `LICENSE GATE CLEAR`.
- Added bounded binary downloads using a sibling `.partial`, 1 MiB reads, a 60-second timeout, an explicit configurable byte limit (100 MiB default), streaming SHA-256, response cleanup, and `os.replace()` only after EOF. Existing destinations are not opened or overwritten; failures remove the partial file.
- Added Wikimedia Commons, Internet Archive, and Pexels parser/search adapters and the three requested module CLIs. Normalized results contain provenance, preview URL, kind, and explicit `license_review` metadata rather than silently clearing rights.
- Pexels credentials are read from `os.environ` at call time and sent only in the in-memory Authorization header. They are not placed in query URLs or normalized results. Missing-key CLI behavior is explicit.
- Added the Playwright screenshot CLI with HTTP/HTTPS/file URL validation, a 1920×1080 viewport, `domcontentloaded`, a 1.5-second delay, full-page PNG output, and `finally` browser cleanup.
- Added the specified stdlib unittest and Node test-runner coverage. External provider and download transport are mocked; filesystem, report CLI, and local Chromium screenshot behavior are real.
- Installed `playwright` 1.65.0 as a dev dependency and installed its Chromium browser.

## Files created or modified

Created:

- `F:\AI-PROJECTS\longform-explainer\tools\sourcing\__init__.py`
- `F:\AI-PROJECTS\longform-explainer\tools\sourcing\manifest.py`
- `F:\AI-PROJECTS\longform-explainer\tools\sourcing\download.py`
- `F:\AI-PROJECTS\longform-explainer\tools\sourcing\providers.py`
- `F:\AI-PROJECTS\longform-explainer\tools\sourcing\screenshot.mjs`
- `F:\AI-PROJECTS\longform-explainer\tools\manifest_report.py`
- `F:\AI-PROJECTS\longform-explainer\python\test_sourcing.py`
- `F:\AI-PROJECTS\longform-explainer\tests\screenshot.test.ts`
- `F:\AI-PROJECTS\longform-explainer\.superpowers\sdd\2026-11-09-professional-documentary-workflow\task-2-report.md`

Modified only by the requested npm installation:

- `F:\AI-PROJECTS\longform-explainer\package.json`
- `F:\AI-PROJECTS\longform-explainer\package-lock.json`

The npm installation also populated the existing `node_modules` directory, and Playwright installed Chromium in the user browser cache. No Task 1 source was changed. No git repository or commit was created.

## Dependency installation

Commands run from `F:\AI-PROJECTS\longform-explainer`:

```text
npm install --save-dev playwright
npx playwright install chromium
```

Playwright and Chromium installation completed. The npm output reported one high-severity audit finding; see **Concerns** below.

## TDD evidence

### 1. Initial sourcing contracts — RED

The Python tests, including the brief's manifest tests verbatim plus download/provider/report contracts, were written before the production package existed.

Exact command:

```text
.venv/Scripts/python.exe -m unittest python.test_sourcing -v
```

Relevant exact failure:

```text
ModuleNotFoundError: No module named 'tools.sourcing'

Ran 1 test in 0.000s

FAILED (errors=1)
```

This was the expected missing-package failure, not an assertion or fixture defect.

The Node screenshot test was also written before `screenshot.mjs` existed.

Exact command:

```text
npm test -- --test-name-pattern=screenshot
```

Relevant exact failure and summary:

```text
Error: Cannot find module 'F:\AI-PROJECTS\longform-explainer\tools\sourcing\screenshot.mjs'

tests 147
pass 146
fail 1
```

This was the expected missing-helper failure. With this repository's current Node argument ordering, the focused command executed the full 147-test discovery set rather than filtering the other tests; the screenshot test was the sole failure.

### 2. Initial implementation — GREEN

Exact Python command:

```text
.venv/Scripts/python.exe -m unittest python.test_sourcing -v
```

Exact summary:

```text
Ran 17 tests in 0.408s

OK
```

Exact Node command:

```text
npm test -- --test-name-pattern=screenshot
```

The output included:

```text
✔ screenshot helper captures a full-page local HTML fixture as PNG

tests 147
pass 147
fail 0
duration_ms 12923.2839
```

### 3. Secret-hygiene self-review regression — RED then GREEN

Review found that source URLs with credential query parameters could be persisted even though user-info credentials were already rejected. A parametrized regression test was added before the validator change.

Exact RED command:

```text
.venv/Scripts/python.exe -m unittest python.test_sourcing -v
```

The new test failed once for each of `api_key`, `apikey`, `api-key`, `key`, `token`, `access_token`, and `auth`:

```text
AssertionError: ValueError not raised

Ran 18 tests in 0.332s

FAILED (failures=7)
```

This proved that the validator accepted every credential-bearing fixture before the fix. The minimal fix rejects those query-parameter names at the common manifest-validation boundary, protecting append, load, purchase export, and report generation.

Exact GREEN command:

```text
.venv/Scripts/python.exe -m unittest python.test_sourcing -v
```

Exact summary:

```text
Ran 18 tests in 0.336s

OK
```

### 4. Provider asset-ID uniqueness self-review regression — RED then GREEN

Review clarified that case-insensitive asset uniqueness must cover the provider `asset_id` as well as the internal `id`. The new test used a different internal ID and a case-variant of the same Wikimedia provider asset ID.

Exact RED command:

```text
.venv/Scripts/python.exe -m unittest python.test_sourcing -v
```

Relevant exact failure:

```text
FAIL: test_rejects_case_insensitive_duplicate_provider_asset_ids
AssertionError: ValueError not raised

Ran 19 tests in 0.342s

FAILED (failures=1)
```

The fix enforces uniqueness of `(provider.casefold(), asset_id.casefold())` both when loading and appending, without incorrectly treating identical external IDs from different providers as the same asset.

Exact GREEN command:

```text
.venv/Scripts/python.exe -m unittest python.test_sourcing -v
```

Exact summary:

```text
Ran 19 tests in 0.342s

OK
```

This is the final focused Python result: **19/19 PASS**.

## Full-suite verification

The exact combined command from the brief was run once, after all source and test changes:

```text
.venv/Scripts/python.exe -m unittest discover -s python -v && npm test
```

Exact Python summary:

```text
Ran 41 tests in 0.433s

OK
```

Exact Node summary:

```text
tests 147
suites 0
pass 147
fail 0
cancelled 0
skipped 0
todo 0
duration_ms 12244.6793
```

The final full suites therefore pass **Python 41/41** and **Node 147/147**. The screenshot test passed again in this fresh full run. There were no test errors or failures.

## Tested versus unverified

### Tested

- Manifest validation, both forms of case-insensitive duplicate detection, licence restrictions, append/purchase transitions, and preview-only selection using real temporary JSON files.
- Purchase-report grouping and both CLI gate outcomes through real subprocesses and real generated Markdown files.
- Successful downloads, chunk size, timeout, digest logging, maximum-size rejection, mid-stream failure cleanup, unsafe initial/final schemes, response closure, and existing-destination protection through fake transport responses.
- Wikimedia `imageinfo`, Internet Archive `response.docs`, and Pexels `photos` fixtures, including normalized provenance and licence-review fields.
- Mocked provider HTTP query construction, limit propagation, in-memory Pexels Authorization behavior, and absence of the test credential from URLs/results.
- Missing `PEXELS_API_KEY` behavior both directly and through the real CLI subprocess, with no network opener invoked.
- A real Chromium screenshot of a local `file://` HTML fixture. The output had the exact PNG signature and exceeded 1,000 bytes.

### Explicitly unverified

- No live Wikimedia, Internet Archive, or Pexels request was made. Their adapter contracts are tested with fixtures/mocks, not against current live services.
- **Live paid-provider preview behavior is not proven by mocked provider tests.** No paid-provider call, comp download, purchase, or clean-media replacement was attempted.
- No real API key or other credential was read, used, printed, written to source/manifests/reports, or stored in a vault note. Only a clearly fake unit-test sentinel exercised the in-memory header path.
- No live remote binary download was made. Atomic behavior is proven against controlled local fakes, not a remote provider CDN.
- Only local accessible HTML screenshot capture is verified. Remote stock-page, authenticated, anti-bot, or paid-preview screenshot accessibility remains unverified.
- Explicit editorial-context notes are machine-checked; whether a particular use is genuinely editorial remains an item-level editorial/legal judgment rather than something these tests claim to prove.

No upload, publication, remote deletion, purchase, or git commit occurred.

## Self-review findings

- The implementation uses exactly the requested file boundaries and providers, with no additional provider, upload feature, or broad refactor.
- The manifest schema contains all 13 section 5.1 fields and rejects missing or extra fields. The report consumes the same validated manifest API rather than duplicating gate logic.
- Every used `preview` entry blocks the report CLI gate. Free entries do not appear in the purchase list. Purchase transitions never change the local path.
- Download replacement is atomic only after a complete bounded response. The tests would catch premature destination writes, partial-file residue, overwrite behavior, missing timeout/chunk bounds, and unsafe redirect handling.
- SHA-256 is calculated incrementally and emitted through the module logger after success; no digest sidecar or credential-bearing URL log is created.
- Provider results require licence review and flag detectable noncommercial metadata. They do not mislabel Pexels or unspecified Internet Archive terms as CC0/public domain.
- The secret-hygiene review led to an additional tested guard against credentials in source-URL user info and common query parameters. The Pexels key exists only in the environment and in-memory request header.
- Tests use independent literal fixtures and expected values. Mocks replace only external HTTP behavior; they do not replace the code under test. The browser and report tests exercise real command-line entry points.
- Mutation review: removing a required schema field, allowing NC media, omitting attribution, weakening editorial/RemArc checks, accepting duplicate IDs, failing to preserve `file`, omitting a preview from the report, removing the upload exit code, writing directly to the destination, ignoring maximum bytes, or placing the Pexels key in the URL would each fail at least one test.
- No unrelated source files were modified and no temporary media or screenshot artifacts were left in the repository by the tests.

## Concerns

- `npm audit` reports one high-severity advisory in the pre-existing `zod` 3.25.76 dependency: `GHSA-mrhx-c7xc-m3w5` (oversized constrained collections can exhaust memory). The suggested remediation is a breaking upgrade to Zod 4.6.7. It was not applied because it is unrelated to Task 2 and could affect the existing workflow. Playwright itself has no reported finding in this audit output.
- Live provider behavior and genuine editorial-use determinations remain deliberately unverified as detailed above; these are runtime/review gates, not claims made by the mocked tests.

## Review fix round 1

### Exact code and test changes

- `tools/sourcing/download.py`: added a shared stdlib `HTTPRedirectHandler` subclass. It validates every absolute redirect target with `_require_http_url()` before calling the stdlib redirect implementation, so only HTTP(S) targets can be opened. On every origin change `(scheme, hostname, effective port)`, it removes `Authorization` case-insensitively from both normal and unredirected request headers. Same-origin redirects retain the header. Added the shared `_SAFE_OPENER` / `_open_url` transport and made it the default for `download_binary()`; explicit `opener` injection and the public function parameters remain unchanged.
- `tools/sourcing/providers.py`: Wikimedia, Internet Archive, and Pexels now use the same safe default transport. Existing `_open_json()` final-URL validation remains as defense in depth, and explicit opener-based tests/interfaces are unchanged.
- `python/test_sourcing.py`: added local HTTP-server infrastructure and two behavioral regressions. The download case uses a real local HTTP 302 to an FTP URL and instruments the stdlib FTP open boundary. The Pexels case uses two real local HTTP servers on different ports, the real default redirect transport, an environment-only fake sentinel, and the real Pexels parser. Only the initial request URL is replaced with the local server URL; no provider request leaves the machine.

### RED evidence

Exact command, run before production changes:

```text
./.venv/Scripts/python.exe -m unittest python.test_sourcing.DownloadTests.test_rejects_ftp_redirect_before_opening_target python.test_sourcing.ProviderTests.test_pexels_cross_origin_redirect_never_receives_authorization -v
```

Relevant failures (the fake credential value is intentionally not persisted):

```text
AssertionError: Lists differ: ['ftp://example.invalid/media.bin'] != []

AssertionError: '<fake sentinel>' is not None

Ran 2 tests in 1.588s

FAILED (failures=2)
```

Both failures were expected. The old default transport opened the FTP redirect target before the existing final-URL rejection, and copied the initial Pexels `Authorization` header to the second origin.

### GREEN evidence

Exact focused command after the shared transport fix:

```text
./.venv/Scripts/python.exe -m unittest python.test_sourcing.DownloadTests.test_rejects_ftp_redirect_before_opening_target python.test_sourcing.ProviderTests.test_pexels_cross_origin_redirect_never_receives_authorization -v
```

Exact summary:

```text
Ran 2 tests in 1.546s

OK
```

The complete focused sourcing module also passed:

```text
./.venv/Scripts/python.exe -m unittest python.test_sourcing -v
```

```text
Ran 21 tests in 1.918s

OK
```

The FTP regression proves the disallowed target is never opened because its recorded FTP-open boundary remains empty after a real local redirect, and neither the destination nor `.partial` appears. Before the fix, the same boundary recorded the FTP target and the test failed even though the final-URL check raised `ValueError`.

The two-server Pexels regression proves the initial request carries the fake sentinel while the second origin receives no `Authorization`. Its observation report combines the second server's captured headers and URLs, normalized results, and captured logs; the test asserts that the sentinel appears nowhere in that report. No credential is written to a file or provider result.

### Full Python suite

Exact command, run once after the fix:

```text
.venv/Scripts/python.exe -m unittest discover -s python -v
```

Exact summary:

```text
Ran 43 tests in 1.972s

OK
```

Node code was unchanged, so the full Node suite was not rerun in this round.

### Concerns

- No new production concerns. The first post-fix focused run exposed a test-only `AttributeError` because `assertNoLogs()` does not yield a log-capture context on this Python version. The fixture was corrected without changing production code; the final focused and full results above are clean.
- The Minor TOCTOU observation and the unrelated Zod advisory were deliberately left unchanged as scoped. No live provider request, paid call, upload, purchase, remote deletion, git initialization, or commit occurred.
