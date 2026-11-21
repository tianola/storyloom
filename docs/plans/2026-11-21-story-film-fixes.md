# Story-film fixes (plan, 2026-11-21)

The owner's verdict on the dressed pilot: the narration, who speaks and when, the shots, empty scenes, houses without
character, cameras too fast and dumb, a careless environment. The rules are in `.claude/skills/story-film/`; this plan
puts them into the code and into the pilot. Opus plans and writes the story; Sonnet agents do the mechanical code.

## Root causes found

- **Camera**: `storyboard_beats.view_to_shot` gives every still shot the same 7° orbit and 6% push regardless of its
  length, with the sign flipping at every cut, so short shots jerk back and forth. `at:` close-ups use a fixed radius
  and an 18° jump. Travel moves have no hold before or after.
- **Houses**: lit windows are flat emissive rectangles; nothing lives behind them.
- **Who speaks**: nothing checks that the speaker is on screen before a line; the narrator bust moves around the
  frame; thoughts sound like speech.
- **Script**: dramatised inner thoughts with no documented basis; little use of Semmelweis's own documented words;
  shots planned by me without a world bible.

## Work

| # | Who | Files | What |
| --- | --- | --- | --- |
| A | Sonnet | `tools/blender/storyboard_beats.py`, `tools/blender/models/look.py` | duration-aware, motivated camera: locked short shots, slow drift with one direction per beat, close-up distance from subject size, holds around travel moves, speed cap |
| B | Sonnet | `tools/blender/models/world.py` (house windows only) | rooms behind lit windows: back wall, furniture shapes, curtains, lamp, moving silhouettes, lights going out |
| C | Sonnet | `workflow/storyboard.py`, `tools/audio_finish.py` (or where per-line audio is finished) | storyboard advice: speaker on screen 0.5 s before the line, speaker big enough, shot floors by kind, narrator in a fixed spot; inner-thought voice treatment (quieter, closer) |
| D | Sonnet (web) | `docs/research/semmelweis-words.md` | Semmelweis's own documented words (1861 book, open letters), contemporaries' words, with exact sources, for the voice ladder |
| E | Opus | `work/semmelweis-pilot/story/*`, `script/*`, `storyboard.json` | rewrite with the skill: beat sheet with but/therefore seams, world bible, narration with documented words, new storyboard |
| F | Opus | stills, render, QC | check against the world bible and staging rules; then the full render |

A, B, C and D run in parallel (separate files, no Blender, python tests only). E starts when D lands; F after all.
