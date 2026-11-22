# Script craft

Sources: nine fern and Veritasium scripts read beat by beat (`docs/research/reference-script-craft.md`, tags Ci =
Citicorp, Mi = Midgley, Mu = Mullis, Di = Dirac, F103 = Flight 103, Co = Coca-Cola, SS = Secret Service, Cn = the lost
console), six films measured shot by shot (`docs/research/story-not-slides.md`), public scripting packs
(`docs/research/script-skills-online.md`).

## 1 The spine

- One sentence: **[person] wants [goal], but [obstacle], therefore [action], which costs [price].** If you cannot write
  it, you have a topic, not a story.
- **A track** = the person and what happens to them. **B track** = the mechanism. B is delivered as a consequence of
  A ("because the polymerase died at 95 °C, he needed bacteria from a hot spring"). When B gets dense, cut back to A.
- **But / therefore seams.** Write every beat boundary as "but" or "therefore". An "and then" seam is a fact list:
  merge the beats or find the conflict between them.
- **Misconception first.** Open a science segment on what people (and the viewer) believed. Let a character hold the
  belief, let an event break it, and make the true answer the payoff. The misconception must be labelled as one.
- **A guess before each reveal.** A character or the narrator commits to a prediction ("everyone knew it was bad
  air"); the next event contradicts or refines it. Machine checked: `story.json` `guess` by 20%, `reversal` at 25-70%.
- **One decision with its cost.** Somewhere the person risks money, name, job or safety. Show the choice and what it
  cost (Ci, Mu, Mi).
- **A second thread** (a rival, a later checker, a victim, a witness) cuts in at least twice and returns at the end (Mi
  ping-pongs Patterson and Midgley at every chapter boundary).

## 2 Opening (first 30-60 s)

Pick one of five proven shapes:

1. **Stakes before names** (fern: F103, SS): a concrete, sensory first sentence, the toll in two sentences, then
   the question, then the title said as a sentence ("This is the story of...").
2. **Person with a problem in 12 s** (Ci, the best hook studied): name, date, the discovery, the threshold, the
   people at risk, his own words, the binary choice.
3. **Thesis without a name** (Mi): what one person did and what it cost, then straight to a puzzle carried by
   someone else; the title person arrives later (allowed only with a parallel person on screen).
4. **Demonstration, then a person-tease** (Mu): the viewer does something, a question about it, then the person in
   one funny, characterful line.
5. **A scene with the name withheld** (Di): a room, a reaction from others that sets the stakes, the name later.

Rules: 3-5 short declarative sentences; at most two numbers (one human-sized, one threshold); the question by 30 s;
never the answer in the first minute; the person on screen acting (not only named) within 3 minutes of the body.

## 3 Body: interleaving, rhythm and re-hooks

- **Person share 40-55%** of running time. A person beat (action, reaction, decision, a quoted line) at least every
  3-5 minutes; hard fail at 7 minutes of explanation without one.
- **Every explanation opens with the person's problem in one sentence** before the first technical term.
- **Explaining a mechanism**, in this order: the person fails or wants something; the one quantity that matters,
  named with a number; a physical thing the viewer could hold (phones pushed together for wind load, a licence plate
  seen from the Moon); the rule; the consequence for the story. Show the real object or place first, animate after.
- **Density:** at most one new concept per 2.5 minutes; a new term is used again within 60 s.
- **Numbers:** paired in the same sentence with a comparison, a date, odds or a threshold the viewer knows. Never more
  than two numeric sentences in a row. A number that matters gets a picture or a gag, not a chart.
- **Re-hooks:** about every 4-5 minutes. Close a section with one of: a promise ("the mystery would take over the
  rest of his life"), a negative turn ("it worked, but"), a consequence ("then the workers started dying"), a
  countdown, or the return of a frame story. Never close on a summary.
- **Chapter titles are questions or events**, not subjects: "Why did they die in one ward?", "The two doors",
  "May 1847", not "Puerperal fever" or "Background".
- **A running device** (a line or object that comes back 2-4 times with a changing meaning) ties the film together
  ("we asked; they did not respond", the lantern at the gate, the doctor's hands).
- **Comedy:** one dry line every 3-5 minutes, aimed at an institution or a habit, never at a victim.

## 4 Who speaks: the voice ladder

Neither channel puts invented speech into a real person's mouth; this project lets the story's people speak, so it
uses a ladder. Take the highest rung the record allows:

1. **Their own documented words**: a letter, a book, a diary, a court record, a recorded interview, adapted only
   for length. Name the source in the line before or after, or on a quote card. (Semmelweis left an 1861 book and
   open letters full of usable lines.)
2. **Reported speech of a documented event**, said by the narrator ("He wrote to Scanzoni that..."), or by another
   character who witnessed it.
3. **Documented feeling shown as action**: he counts the dead, he stops eating, he walks the ward at night. Show it;
   do not say the feeling word.
4. **A short human line that states no fact** (a greeting, a plea that the record says people made, a sigh, "Not
   tonight"), spoken by an unnamed or a representative person, labelled as dramatised.
5. **An imagined inner thought** only as a paraphrase of something the person documented, flagged in
   `dramatisation.json`, and only where nothing above can carry the moment.

Never: a fact, a number, a discovery, a motive or an insult the record does not support; a real person saying the
thesis of the film; a thought that changes what history says.

Lines and timing: character lines are short (8-25 words) and rare, about one every 2-3 minutes in a long film and
never two in a row without a narrator line or a picture between them. A dialogue scene is a few exchanges, not a
play. The narrator states what is documented; the characters carry emotion.

## 5 The narrator

- The explorer narrates in the third person and **present tense in scenes** ("A man walks into the ward"), past tense
  for background; "we" only for the team's own checks; "you" to put the viewer in a person's shoes or to ask for a
  guess.
- Short, flat, concrete verbs. Median sentence 10-14 words; 15-25% of 6 words or fewer; at most 10% over 25 words.
- **Do not describe the picture.** The line adds what the picture cannot show: a date, a number, a motive, a
  consequence. If the image shows a lantern being lit, do not say "a lantern is lit".
- A turn word (but, yet, until, however, suddenly) every 35-75 s; 0.35-0.85 questions a minute, never two in a row,
  one at each chapter pivot.
- Directions for the voice go in `{braces}` (they reach ElevenLabs v3 as `[direction]`): `{quietly}`, `{dry}`,
  `{pause}`. Use them where the meaning changes, not on every line.

### Telling, not reading (2026-11-21)

The narration must sound like someone telling a story, not reading a script, and must make the viewer guess, then
find out they were wrong. Full reasoning and sources: `docs/research/narration-voice.md`. Rules (these add to the
ones above; where a number differs, the stricter existing rule stands):

1. Open cold on one concrete moment, present tense; no dateline sentences (a date goes inside a sentence).
2. Median 9-13 words, ~20% under 7, a one- or two-word fragment at each turn.
3. Contractions everywhere; "Now," "So," "And" allowed; "But" opens each reversal; "So" only for a question or conclusion.
4. "You" 2-3 times, each a host moment (misconception, guess, closing question); no "I" except one earned aside.
5. Introduce a person once, full name and role in one clause.
6. Every number with a spoken comparison.
7. Belief first, then anomaly, then question.
8. No filler adjectives (incredible, fascinating, shocking).
9. Don't describe the picture, except a short "This is..." on archive.
10. Read-aloud test: split any line you would breathe in the middle of.
11. End on the open question in a pilot, the payoff in a full film.
12. Real words stay real; every line cites a verified claim; no invented facts.

Guess loop (structure for the opening and each chapter):

- Open on the anomaly, not the shock.
- Hand over clues before any explanation.
- State the belief everyone held.
- Invite the guess out loud, then leave a beat.
- Test the likely guesses on screen one by one, each failing in a short fragment.
- Drop the clue the viewer did not see coming; let them reach the answer a beat before the narrator.

Blend-voice exception: scenes stay third person and present tense (above); at the 2-3 host moments the explorer may
speak to the viewer ("you'd think..."). This does not widen the "you" allowance beyond those moments.

## 6 Ending

Four moves, 60-120 s: **payoff** (the answer to the opening question), **consequence** (what changed or did not),
**one reflection sentence**, **callback** to an object, a phrase or a place from the opening. No new mechanism after
the payoff; the last two sentences are 12 words or fewer. An open case ends by naming what is still unknown. No recap,
no "in conclusion", no call to action.

## 7 Avoid

Clickbait phrasing and fake teasers that never pay off; pattern interrupts every few seconds (pop-up text, zooms,
stings); a villain/hero frame (the antagonist is the problem, not a manufactured enemy); shock for its own sake; a
wrong claim used as a hook without being named as wrong; 150-wpm word budgets taken from generic packs without the
gate's own words-per-second; "Did you know", "In this video", "Let's dive in", "Imagine a world".
