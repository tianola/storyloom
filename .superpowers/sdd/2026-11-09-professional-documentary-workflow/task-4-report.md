# Task 4 Report: Fern Shot-Recipe Library

## Status: DONE

## Files Created

| File | Path | Purpose |
|------|------|---------|
| Test suite | `tests/shot-recipes.test.ts` | 13 structural and motion contracts |
| Composition | `work/shot-recipes/index.html` | 16-second composition with four 4-second sections |
| Project manifest | `work/shot-recipes/project.json` | HyperFrames project metadata |
| GSAP library | `work/shot-recipes/assets/gsap.min.js` | Copied from `tools/js/gsap.min.js` |
| Archival plate | `work/shot-recipes/assets/archival-plate.svg` | Project-owned test image (aged document SVG) |
| QA directory | `work/shot-recipes/qa/.gitkeep` | Empty placeholder for future snapshots |

## The Four Shot Recipes

### Section 1: `recreated-ui` (0-4 s)
- Fictional forum post with semantic `<article>`, `<header>`, `<button>` elements
- Typewriter text animation: characters appear progressively via GSAP `tl.call()` loop
- Blinking cursor (`typed-cursor` class with CSS `cursor-blink` animation)
- `<blockquote>` highlight that zooms in with `quote-highlight` class (box-shadow glow)

### Section 2: `kinetic-quote` (4-8 s)
- Three quote lines revealed word-by-word with `back.out` easing
- Source card with publisher name ("Carrington Archive") and attribution ("Royal Observatory Notes, 1859")
- GSAP keyframes at deterministic section-relative times (S2 = 4)

### Section 3: `ken-burns` (8-12 s)
- Project-owned SVG plate (`assets/archival-plate.svg`) as `<img>` source
- Slow scale (1.0 -> 1.15) and translate (pan) transform over 3.6 seconds
- Radial vignette overlay + highlight mask with amber glow border
- GSAP keyframes at deterministic section-relative times (S3 = 8)

### Section 4: `news-lower-third` (12-16 s)
- Project-owned gradient background (no external assets)
- Lower-third card with: publisher name, clip title (with amber accent), date field
- Big headline + cyan kicker above
- GSAP keyframes at deterministic section-relative times (S4 = 12)

## RED Evidence

Command:
```
node --test --test-reporter=spec --test-name-pattern=shot-recipes "tests/shot-recipes.test.ts"
```

Output (before implementation):
```
✖ shot-recipes: composition HTML file exists
  Error: ENOENT: no such file or directory, open '...\work\shot-recipes\index.html'
✖ shot-recipes: root composition is 1920x1080 with duration 16
  Error: ENOENT: no such file or directory, open '...\work\shot-recipes\index.html'
... (all 13 tests fail)
ℹ tests 13
ℹ pass 0
ℹ fail 13
```

## GREEN Evidence

Command:
```
node --test --test-reporter=spec --test-name-pattern=shot-recipes "tests/shot-recipes.test.ts"
```

Output (after implementation):
```
✔ shot-recipes: composition HTML file exists (5.3138ms)
✔ shot-recipes: root composition is 1920x1080 with duration 16 (0.2902ms)
✔ shot-recipes: all four section IDs exist with correct timing (0.3247ms)
✔ shot-recipes: recreated-ui has semantic article, header, button, cursor, typed text, and quoted highlight (0.2999ms)
✔ shot-recipes: kinetic-quote has word-by-word reveal, source card, and GSAP keyframes (0.4274ms)
✔ shot-recipes: ken-burns uses project-owned SVG plate with scale/transform and vignette (0.308ms)
✔ shot-recipes: news-lower-third has background, publisher, title, date, and GSAP keyframes (0.3317ms)
✔ shot-recipes: every visible annotation is at least 28px font-size (0.2549ms)
✔ shot-recipes: no asset URL uses HTTP(S) (0.2979ms)
✔ shot-recipes: GSAP keyframes use deterministic section-relative times (0, 4, 8, 12) (0.3603ms)
✔ shot-recipes: project.json exists and is valid (1.9458ms)
✔ shot-recipes: assets directory contains gsap.min.js and archival-plate.svg (0.8234ms)
✔ shot-recipes: qa directory exists with .gitkeep (2.0966ms)
ℹ tests 13
ℹ pass 13
ℹ fail 0
```

## HyperFrames Lint Output

```
◆  Linting shot-recipes/index.html
◇  0 error(s), 4 warning(s)
```

The 4 warnings are advisory (`nested_structure_needs_subcomposition`) — the same pattern used by `showpiece-house/index.html`. They recommend splitting sections into sub-compositions for the timeline editor, which is a future refactor, not a correctness issue.

## Full Regression Results

### Node tests (`npm test`)
```
ℹ tests 160
ℹ pass 160
ℹ fail 0
```

### Python tests (`python -m unittest discover -s python -v`)
```
Ran 44 tests in 2.051s
OK
```

No regressions introduced.

## Constraints Verification

- No external HTTP(S) assets used — all assets are local
- No git commits created
- No remote material published, uploaded, or deleted
- All visible text >= 28px font-size (verified by test)
- All copy in English
- All timing driven by section starts (0, 4, 8, 12)
- Rendering is CPU-only (no CUDA/ROCm dependencies)
- House style maintained: dark cinematic navy (#060810), amber/cyan accents

## Concerns and Limitations

1. **Lint warnings**: The 4 `nested_structure_needs_subcomposition` warnings are advisory. If the HyperFrames timeline editor is used heavily, splitting into sub-compositions would improve the editing experience. This is a future enhancement, not a blocker.

2. **Typewriter implementation**: The typed text effect uses `tl.call()` per character (67 calls for the full string). This is correct but verbose. A future optimization could batch characters or use a custom GSAP plugin.

3. **Archival plate SVG**: The test SVG is a simple placeholder document. For production use with the Carrington pilot, this would be replaced with a real scanned document image.
