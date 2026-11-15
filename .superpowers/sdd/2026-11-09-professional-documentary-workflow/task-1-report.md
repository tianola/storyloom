# Task 1 Report: Workflow Scaffolding

## What I implemented

- Added the reusable `init_episode(root: Path, slug: str, title: str) -> Path` initializer using only the Python standard library.
- Added lowercase kebab-case slug validation, required-title validation, and existing-episode rejection through `Path.mkdir(exist_ok=False)`.
- Added creation of the nine required phase directories: `research`, `story`, `script`, `assets`, `vo`, `motion`, `edit`, `qc`, and `dist`.
- Added `episode.json` generation with the specified slug, trimmed title, `English` language, workflow version `3`, and duration target `[600, 900]`.
- Added an empty `assets/license-manifest.json` containing `[]`.
- Added copying of the three required templates into their phase directories.
- Added a standard-library CLI accepting the required `--root`, `--slug`, and `--title` arguments.
- Added the two specified `unittest` contract tests.

## Files created or modified

Created:

- `F:\AI-PROJECTS\longform-explainer\workflow\__init__.py`
- `F:\AI-PROJECTS\longform-explainer\workflow\init_episode.py`
- `F:\AI-PROJECTS\longform-explainer\workflow\templates\sources.md`
- `F:\AI-PROJECTS\longform-explainer\workflow\templates\beat-sheet.md`
- `F:\AI-PROJECTS\longform-explainer\workflow\templates\narration.md`
- `F:\AI-PROJECTS\longform-explainer\python\test_init_episode.py`
- `F:\AI-PROJECTS\longform-explainer\.superpowers\sdd\2026-11-09-professional-documentary-workflow\task-1-report.md`

No unrelated files were modified. No dependencies were added. No git repository or commit was created.

## TDD evidence

### RED

Exact command, run from `F:\AI-PROJECTS\longform-explainer` before creating the production module:

```text
.venv/Scripts/python.exe -m unittest python.test_init_episode -v
```

Relevant failure:

```text
ImportError: Failed to import test module: test_init_episode
...
ModuleNotFoundError: No module named 'workflow'

Ran 1 test in 0.000s

FAILED (errors=1)
```

This was the expected RED result because `python/test_init_episode.py` imports `workflow.init_episode`, and the `workflow` package did not yet exist. The failure therefore demonstrated the missing initializer rather than an assertion or test-fixture defect.

### GREEN

Exact command, run after implementing the initializer and templates:

```text
.venv/Scripts/python.exe -m unittest python.test_init_episode -v
```

Passing output:

```text
test_creates_nine_phase_layout_and_empty_manifest (python.test_init_episode.InitEpisodeTests.test_creates_nine_phase_layout_and_empty_manifest) ... ok
test_rejects_unsafe_slug_and_existing_episode (python.test_init_episode.InitEpisodeTests.test_rejects_unsafe_slug_and_existing_episode) ... ok

----------------------------------------------------------------------
Ran 2 tests in 0.023s

OK
```

## Full Python suite

Exact command, run from `F:\AI-PROJECTS\longform-explainer`:

```text
.venv/Scripts/python.exe -m unittest discover -s python -v
```

Exact summary:

```text
----------------------------------------------------------------------
Ran 22 tests in 0.052s

OK
```

All 22 discovered tests passed, comprising the 20 baseline tests and the 2 new initializer tests. The output contained no errors, failures, or warnings.

## Self-review findings

- The implementation follows the supplied public surface and constants without adding alternate APIs, dependencies, or future-proofing.
- The initializer creates exactly the required nine phases, metadata, empty license manifest, and three copied templates.
- `sources.md` defines claim ID, exact claim, source URL, publisher, publication date, source tier, supporting quotation, and verification status.
- `beat-sheet.md` defines time range, narrative purpose, tension/reveal, narration IDs, visual IDs, and transition anchor.
- `narration.md` is a table with utterance ID, narration text, visual ID, visual note, source claim IDs, and estimated seconds.
- The CLI exposes only the three requested arguments and calls the same public initializer.
- The tests are the specified contract tests, use real temporary filesystem state, and independently assert literal paths and values.
- Mutation check: removing or renaming a phase/template, changing the manifest or language, omitting slug validation, or allowing an existing episode would fail at least one focused assertion.
- Focused and full-suite outputs are pristine. Scope is limited to the files required by the brief and this report.

## Concerns

None.
