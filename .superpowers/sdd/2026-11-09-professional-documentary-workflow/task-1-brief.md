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

