# Decisions

The approved design lives in `docs/superpowers/specs/2026-11-05-longform-explainer.md`, sha256
`426e780e90b6b3ce53cfba23251a5715e2ba64db3f936d719008b246c5e83842`. That file is byte-stable on purpose: its hash is recorded as
`licenseTextHash`/`artifactHash` in the rights ledger of every episode package, so decisions that change implementation are
recorded here instead of editing the spec.

## D-001 — Deterministic SVG renderer replaces the Motion Canvas baseline (2026-11-06)

**Chosen:** `src/scene-state.ts` computes numeric element state per frame, `src/svg-scene.ts` serializes it to SVG,
`@resvg/resvg-js` rasterizes to PNG, and FFmpeg encodes the frame sequence per scene.

**Rejected for now:** Motion Canvas as the baseline renderer.

**Why:** no browser process inside the render path; licensing and telemetry stay fully local and auditable; one runtime
dependency instead of a Vite plus Playwright toolchain; determinism becomes a tested property rather than a hoped-for
behaviour (`tests/frames.test.ts` rasterizes one frame twice and compares bytes, and proves different frames differ).

**Compatibility kept:** the scene contract is unchanged — validated data drives trusted renderer code, never
model-written JavaScript. Motion Canvas 3.17.2 can still be added as a second renderer because its `Renderer` awaits the
async `Exporter.handleFrame`, its `range` is expressed in seconds with an inclusive end frame, and completion is reported
through `onFinished`. No adapter was written; nothing depends on one.

**Status:** implemented and covered by tests. The spec's Architecture paragraph still names Motion Canvas as the initial
choice; read this entry as the current reality.

## D-002 — One claims ledger, inside the script (2026-11-06)

**Chosen:** an episode package carries claims only in `script.claims`, plus a top-level `reviews` map of
`claimId -> {reviewer, reviewedAt}`. `ProjectSchema` is `.strict()`, so a second top-level `claims` array is rejected
outright rather than silently ignored.

**Rejected:** separate `project.claims` and `script.claims` arrays.

**Why:** the first real package drifted — `c5`, `c7` and `c8` carried different wording in the two copies, so the reviewed
statement and the statement the narration actually spoke were not the same sentence. A gate that reads one copy cannot
catch that.

**Status:** enforced by `tests/cli.test.ts`; `withReviews()` reports `missing-review-record` and `orphan-review` as
blocking problems before any rendering starts.

## D-003 — Local free models are the default writer; OmniRoute stays unproven (2026-11-06)

**Chosen:** scripts come from an imported, human-reviewed file or from local Ollama (`qwen3.5:4b` in project-local storage,
port 11435). Every model-facing path refuses a blank or sentinel model id.

**Rejected as default:** OmniRoute at `http://localhost:20128/v1`.

**Why:** a localhost proxy is not evidence of a free route. Read-only inspection found 1,959 routes, and entries priced at
zero do not prove zero cost; `auto`/`cheap` routing has no free-tier filter. No credential was persisted anywhere and no
paid inference was performed.

**Status:** the free local baseline works; route-level cost validation for OmniRoute remains open, so the pipeline never
falls back from local to paid.
