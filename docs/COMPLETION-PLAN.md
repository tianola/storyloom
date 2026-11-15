# Completion plan (2026-11-15)

Goal: a topic goes in, a Fern-style long-form documentary comes out, without anyone writing
Blender code for that episode. No new episode is produced until every phase below is done;
the existing Jensen episode is the regression fixture.

## Where it stands
- 3D look and model library are good; everything else around them is hand work.
- One shot per sentence (9-12 s holds); Fern changes picture every 3-6 s.
- Each episode needs its own `*_beats.py` written by hand.
- No captions, no sound design, archive at 10% with one black shot.
- 107 Python tests and 9 TypeScript errors fail before any new work.

## Phases

| # | Phase | Deliverable | Done when |
|---|-------|-------------|-----------|
| 0 | Green baseline | Existing tests and `tsc` pass or are deleted with their dead code | `pytest python` and `npx tsc --noEmit` exit 0 |
| 1 | Scene catalog | `tools/blender/models/scenes.py`: parametric scenes (teardown, charts, people, stacks, timeline, document, flow diagram, ...) each exposing named views, anchors and actions; `workflow/scenes.json` describes them as data | Every scene builds from its example parameters in Blender; catalog and code agree (test) |
| 2 | Cuts inside a beat | `look.shoot()`: several camera set-ups per sentence with hard cuts, labels tied to a set-up, framing check that the anchor is actually on screen | A 10 s beat renders 2-3 set-ups; off-screen anchors are reported |
| 3 | Storyboard as data | `storyboard.json` per episode + generic `tools/blender/storyboard_beats.py`; validator `workflow/storyboard.py`; label timing tied to spoken words | Jensen's 17 beats are expressed as data and build with no episode-specific Python |
| 4 | Planner | `tools/plan_storyboard.py`: narration + catalog -> storyboard (LLM call with validation and repair, or a brief for an agent) | A storyboard that fails validation never reaches Blender |
| 5 | Script gate | `tools/qc_script.py`: length target, hook, chapter structure, sentence length, every claim sourced, numbers written for speech | Jensen script is reported as too short with its unsourced line named |
| 6 | Sound and captions | Word timings, soft subtitle stream + optional burned captions, per-sentence loudness levelling, synthesised transition sounds | `no_captions` and `cut_loudness_jump` clear on a re-mux of the existing master |
| 7 | Archive layer | Missing media is an error, never a black placeholder; stills get the paper/drift treatment; share target enforced at planning time | The black `boarding-school` shot is reported before render, not after |
| 8 | One command | `tools/make_episode.py --episode X`: script gate -> narration -> plan -> lengths -> render -> assemble -> captions -> QC, resumable per stage | A dry run on Jensen lists every stage and what it would do |
| 9 | Clean-up and docs | Stray root logs/scripts removed, `docs/PRODUCTION-GUIDE.md` rewritten around the one command, memory files updated | New chat can run an episode from `.memory/` alone |

## Not in this plan
- Producing a new episode (next step after phase 9).
- Map scenes with real coastlines: needs a public-domain coastline file downloaded once; ask first.
- Replacing the Kokoro voice.
