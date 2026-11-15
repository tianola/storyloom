# Task 4 Brief: Fern Shot-Recipe Library

## Context

This task builds four reusable HyperFrames shot recipes that represent the fern-style documentary visual language. These recipes will be used by Task 6 (Carrington pilot) and future episodes.

## What exists

- HyperFrames composition pattern: see `work/showpiece-house/index.html` for the house style (dark cinematic navy, amber/cyan semantics, GSAP animations, `data-composition-id`, `data-start`, `data-duration`, `data-width`, `data-height` attributes).
- GSAP library: `tools/js/gsap.min.js` (also copied into each composition's `assets/` folder).
- House style grammar: bottom-center bold captions with key word in amber pill, cyan/red accents, big white headline cards, cyan kicker, annotation pills with leader lines.
- Node test pattern: `tests/*.test.ts` using Node's built-in test runner (`node --test`).

## Files to create

1. `work/shot-recipes/project.json` — HyperFrames project manifest
2. `work/shot-recipes/index.html` — the composition with four 4-second sections
3. `work/shot-recipes/assets/gsap.min.js` — copy from `tools/js/gsap.min.js`
4. `work/shot-recipes/assets/archival-plate.svg` — project-owned test image (simple SVG)
5. `work/shot-recipes/qa/` — snapshot directory (create empty, snapshots captured later)
6. `tests/shot-recipes.test.ts` — structural and motion contracts

## The four shot recipes

Each recipe is a 4-second section within a 16-second main composition:

### Section 1: `recreated-ui` (0–4 s)

A fictional forum post / UI recreation. Must contain:
- Semantic `article`, `header`, and `button` elements (not a screenshot)
- Typed text animation (characters appear progressively)
- Cursor movement (a blinking cursor that moves as text types)
- Quoted-element highlight (a `<blockquote>` or similar that zooms/highlights)

### Section 2: `kinetic-quote` (4–8 s)

Source-styled quote with kinetic typography. Must contain:
- Quote words revealed progressively (word-by-word or line-by-line)
- A visible source card (publisher name, date, or attribution)
- GSAP keyframes at deterministic section-relative times

### Section 3: `ken-burns` (8–12 s)

Slow pan/zoom over a static image. Must contain:
- The project-owned SVG plate (`assets/archival-plate.svg`)
- Slow scale and/or translation transform (Ken Burns effect)
- A restrained highlight mask or vignette
- GSAP keyframes at deterministic section-relative times

### Section 4: `news-lower-third` (12–16 s)

News-style source lower-third. Must contain:
- Project-owned background (can be a solid color or gradient, no external HTTP assets)
- Lower-third containing: publisher name, clip title, and date fields
- GSAP keyframes at deterministic section-relative times

## Structural constraints

- Root composition: 1920×1080, duration 16 seconds.
- All four sections: `data-start="0|4|8|12"`, `data-duration="4"`.
- Every visible annotation (text, labels) must be at least 28px font-size.
- No asset URL may use `http://` or `https://` — all assets are local.
- All copy must be in English.
- All timing must be driven by the four section starts (0, 4, 8, 12), not unrelated magic numbers.

## Test contract

The Node test (`tests/shot-recipes.test.ts`) must read the composition and assert:
- Root composition is 1920×1080 with duration 16.
- All four section IDs exist (`recreated-ui`, `kinetic-quote`, `ken-burns`, `news-lower-third`) with correct `data-start` and `data-duration`.
- Recreated UI contains semantic `article`, `header`, and `button` elements, a cursor, typed text, and a quoted-element highlight.
- Quote words, Ken Burns transform, and news source lower-third each have GSAP keyframes at deterministic section-relative times.
- Every visible annotation is at least 28px.
- No asset URL uses HTTP(S).

## HyperFrames lint

After building, run from `work/shot-recipes/`:
```bash
npx hyperframes lint
```
Expected: 0 errors.

## TDD sequence

1. Write the failing test first (RED).
2. Watch it fail because `work/shot-recipes/index.html` is absent.
3. Build the four recipes (GREEN).
4. Run structural tests and HyperFrames lint.
5. Record the verification checkpoint.

## Global constraints (carried from plan)

- Rendering is CPU-only + AMD EEVEE (RX 580 4GB, no CUDA/ROCm).
- Keep HyperFrames as the primary renderer. Remotion is evaluation-only.
- Do not publish, upload, delete remote material, or create git commits.
- Run Node tests with `npm test` from the repository root.

## Report requirements

Write your full report to `F:\AI-PROJECTS\longform-explainer\.superpowers\sdd\2026-11-09-professional-documentary-workflow\task-4-report.md`.

Include:
- Exact files created with their paths.
- RED evidence: the failing test command and its output.
- GREEN evidence: the passing test command and its output.
- HyperFrames lint output (0 errors).
- Any concerns or limitations.
- Statement that no external HTTP assets were used and no commits were made.
