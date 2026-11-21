---
name: story-film
description: Write the script, cast, world and storyboard for a long-form animated story documentary in this project (fern / Veritasium style, a living 3D world with talking pixel characters and an on-screen narrator). Use whenever you write or rewrite narration.md, story.json, cast.json, dramatisation.json, chapters, shots.json or storyboard.json, plan a new episode on any topic, or fix a film the owner called empty, slow, a presentation, or careless.
---

# Story film

A film here is a **story in a living place**, not a lecture with pictures. A person (or a "you") wants something,
the world pushes back, and the science arrives because the story needs it. The narrator is a small explorer who
talks on screen; the people of the story speak when the record lets them. Every place looks lived in and every
camera move has a reason.

The owner's standing complaints, which this skill exists to prevent:

- "a presentation": facts toured in order, charts, labels, a voice reading over pictures;
- "empty": bare houses, rooms with nothing in them, streets with three people, places without character;
- "slow" and "fast and dumb" at once: long static holds, then short shots whose camera jerks for no reason;
- "who is talking?": voices with no visible speaker and characters standing idle while someone else talks.

Research behind every rule, with sources: `docs/research/story-not-slides.md` (measured films),
`docs/research/reference-script-craft.md` (nine fern and Veritasium scripts beat by beat),
`docs/research/staging-camera-sets.md` (camera, staging, set dressing, acting) and
`docs/research/script-skills-online.md` (what the public scripting packs get right and wrong).

## The workflow (do the passes in order; do not skip to writing lines)

1. **Find the story.** Use the source sheet (`research/sources.md`, verified claims only). Pick the type of film from
   `references/topics.md`. Write the one-line spine: *who* wants *what*, *but* what stands in the way, *therefore* what
   they do, and what it costs. Write three candidate cold opens (a story moment, a contradiction, a strange object)
   and pick one.
2. **Beat sheet** (`story/beat-sheet.md`). One line per beat, joined only by **but** or **therefore**, never "and then".
   Mark the A track (the person and events) and the B track (the mechanism), the guess the viewer will make, the
   reversal that breaks it, the re-hooks and the payoff. Rules: `references/script.md` sections 1-3.
3. **World bible** (`story/world.md`). For every place: who lives or works there, what they are doing at this hour,
   the dominant use, a personal object, a sign of wear, the practical light, at least three period markers, the
   colour and mood. For every character: look, voice, what they want in this scene, how they move. Rules:
   `references/staging.md` sections 5-6. A place you cannot fill this way is not ready to be built.
4. **Narration** (`script/narration.md` and its data files, format in `references/files.md`). Write for the ear:
   present tense in scenes, short concrete sentences, a turn every 35-75 s. Characters speak by the voice ladder in
   `references/script.md` section 4: their documented words first, invention last and labelled.
5. **Storyboard** (`shots.json`, `storyboard.json`). Cover each beat like a film scene: establish the place, find the
   person doing something, go closer as the emotion rises, show who speaks before they speak. Montage only for the
   hook and tension; explanations in one held, motivated move. Rules: `references/staging.md` sections 1-4 and 7.
6. **Review passes** (`references/review.md`): first-time-viewer read, sound-off picture read, accuracy read, cut pass.
   Then run the gates (`tools/qc_script.py`, `tools/plan_storyboard.py --check`); never loosen a gate to pass.

## Non-negotiables

- **Accuracy.** Every factual line cites a verified claim (`script/claims.json`). A misconception may open a segment
  only if the film names it as one. Numbers come with a comparison, a date or odds in the same sentence.
- **Real people's words.** No invented line may state a fact, a discovery, a motive or a quote the record does not
  support. Character lines follow the voice ladder and each one has a `script/dramatisation.json` entry.
- **Nothing generic.** No stock place, no random walker, no empty room, no label explaining what the picture should
  show, no chart where a picture or a gag can carry the number.
- **The person drives the science.** No explanation block opens before the person's problem has been shown; no more
  than 5 minutes of explanation without a person beat.
- **Every camera move is motivated** (follow, reveal, push-in on emotion, pull-out on consequence) and slow enough to
  read; otherwise the camera is locked. Never a move that only exists to "keep it moving".

## Quick numbers (details and sources in the references)

| What | Target |
| --- | --- |
| question or stake | in the first 30 s; no answer in the first minute |
| named person or "you" | by 12-30 s; acting in a scene within 3 min of the body |
| spoken pace | 150-175 words a minute (the gate counts 2.36 words/s including pauses) |
| sentences | median 10-14 words; 15-25% of 6 words or fewer; at most 10% over 25 |
| turns / questions | a turn word every 35-75 s; 0.35-0.85 questions a minute |
| person share | 40-55% of the film is person and decision; under 25% fails |
| quoted or character lines | short (8-25 words), about one every 2-3 min in a long film, never two in a row |
| new concepts | at most one per 2.5 min; reuse a new term within 60 s |
| re-hook | about every 4-5 min; one after the payoff |
| ending | payoff, consequence, one reflection, callback to the opening; 60-120 s; no new mechanism |
| shot lengths | establishing wide 5-8 s, medium 3-5 s, dialogue single = line + 0.5 s, reaction 1.5-3 s, insert 1-2.5 s; montage cuts 1.2-2.6 s only in hook/tension |
| camera speed | no pan faster than a frame width per 7 s; push-in 8-15% over 4-8 s; hold 1-2 s after a move lands |
| background life | 3-5 extras with tasks per wide; never crossing the speaker |

## When the owner says...

- **"a presentation"**: the beat sheet is a topic list. Rebuild it around a person's problem and a but/therefore chain.
- **"empty"**: the world bible is missing or not applied. Dress each place with its use, people at tasks, practical
  lights, period markers and objects with history; fill windows with rooms and lives.
- **"slow"**: too many words between turns, long holds with nothing changing, or narration describing what is
  visible. Cut words; give every held shot something that changes.
- **"fast", "dumb camera"**: shots under their floor, moves without motivation, or drift that ignores the shot length.
  Lock the frame, lengthen the shot, or motivate the move.
- **"who is talking?"**: the speaker is not in frame half a second before the line, is not the brightest element, or
  the narrator and the characters share the frame without a fixed place for the narrator.
