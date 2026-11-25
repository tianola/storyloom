# Narration voice: telling, not reading

Research note, 2026-11-21. Companion to [reference-script-craft.md](reference-script-craft.md), which covers the
story spine and structure. This note covers the sound of the narration line by line.

## 1 Purpose

The Semmelweis pilot narration sounded like someone reading a script. Fern and Veritasium narration sounds like
someone telling you a story. This note says why, and sets rules so the next script gets it right.

The direction from the user (2026-11-21, translated):

> The narration must sound like someone telling you a story, not someone reading a script. Don't just make the video
> more dramatic: make the viewer wonder what is going on, form their own guess, then find out they were wrong.

Two things follow. The sound has to change (sentences, connectors, openings). And the structure has to change: the
viewer must be given a puzzle and room to guess before the answer arrives. Drama alone does not do that.

## 2 What was wrong with the old pilot script

Lines quoted from `work/semmelweis-pilot/script/narration.md` as it stood at commit 9c5b214.

**Datelines used as sentences.** A caption is not speech. Nobody tells a story this way.

- "Vienna, eighteen sixty five. A doctor is led into an asylum."
- "Vienna, eighteen forty six. Semmelweis, twenty eight, is the new assistant in the First Clinic."

**Stiff hedge and passive voice.** Both put a wall between the narrator and the listener.

- "There, it is said, the guards beat him."
- "A doctor is led into an asylum." (Who led him? The sentence hides the actor.)

**Repeated phrases in consecutive lines.** Written text hides this; spoken text exposes it.

- "But most doctors of his day rejected it." followed at once by "In his day, every doctor knew..."
- "Next door" three times: "Next door, midwives do." "Next door, one in thirty six." "...sends the mothers next door."

**Turn words that do not turn.** "But" should flip the situation. These do not.

- "But Kolletschka's body shows the same disease as the dying mothers." This is a step forward, not a reversal.
- "But the women know the difference." The women were never in doubt, so nothing flips.

**Unclear lines.** A listener cannot re-read.

- "The mothers deliver on their side, as the midwives do." Which side, and who is the subject of the test?

**No air.** There are no contractions, no spoken connectors ("Now," "So," "And," "Here's the thing"), and nothing
addressed to the viewer. Every sentence is complete, formal and equal in weight. That is how text sounds read aloud.

**A shock opening, not a puzzle.** The pilot opens on an asylum and a death. That is dramatic, but it gives the
viewer nothing to wonder about. The real puzzle (one clinic, one hospital, one air, very different death rates)
arrives about a third of the way in.

## 3 Findings from the study

A web study of published transcripts of Fern and Veritasium, plus two pieces on Derek Muller's method. Veritasium
sentence lengths below are estimates only: the transcripts are unpunctuated auto-captions, so sentence breaks were
inferred.

### Fern

Openings cold-open on a named person or place, in present tense, with no title card or dateline.

- "Yenni is working the night shift at a cash depot in Sweden." then "But suddenly, a new sound starts to creep in."
  (The Bank Heist of the Century)
- "This is the most dangerous child in the world." then "At first glance, she looks like any other girl her age."
  then "But her future is anything but ordinary." (The World's Deadliest Child)
- "Look at this map of Afghanistan. That's the Vakhan Corridor." (We Investigated China's Secret Highway)
- A one-word fragment: "Police!" (How China's Biggest Scammer Got Caught)

Habits:

- Sentences of 4-12 words, with an occasional 15-19 word payoff.
- Fragments at beats ("Heat." "Confirmed.").
- Present tense for scenes.
- "But" is the main pivot; "So" is for conclusions.
- "You" is rare, and used as an invitation ("Look at this map").
- Hedges are tied to a source ("according to...", "reportedly"), never a bare "it is said".
- People are introduced with a name plus a role.
- Deictics point at archive material ("This is...", "Look at this map").

### Veritasium

Openings speak to the viewer, often by voicing their objection or setting a trap.

- Voicing the objection: "I know what you're thinking: clickbait." (Why No One Has Measured The Speed Of Light)
- A thought experiment, then the question: "Imagine you're an astronaut...", then "So why does this happen?"
  (The Biggest Misconception in Physics)
- A bold claim, then a named person in a dated scene (The Man Who Accidentally Killed The Most People In History).
- A paradox about a person (the Haber film).

Habits:

- Uses "I" and "you".
- Anticipates objections out loud.
- "You would think..." sets up a misconception before it is broken.
- "Now," "so," "but" as spoken connectors.
- One long explanatory sentence alternating with abrupt short ones.
- Superlatives are concrete numbers, not adjectives.

### Muller's research

Derek Muller's own work on science video found that a clear explanation alone can leave the viewer's misconception
intact. Stating the misconception first, letting the viewer feel confused, then correcting it, works better. This is
the scientific basis for the guess loop below, and it matches the user's direction.

### Sources

- https://sozai.app/transcripts/channel/fern/
- https://sozai.app/transcript/bank-heist-century/
- https://sozai.app/transcript/worlds-deadliest-child/
- https://sozai.app/transcript/china-secret-highway-investigation/
- https://sozai.app/transcript/chinas-biggest-scammer-caught/
- https://rosetta.to/u/veritasium/the-man-who-accidentally-killed-the-most-people-in-history
- https://rosetta.to/u/veritasium/why-no-one-has-measured-the-speed-of-light
- https://rosetta.to/u/veritasium/the-biggest-misconception-in-physics
- https://www.scientificamerican.com/article/how-youtube-star-derek-muller-of-veritasium-is-challenging-scientific/
- https://brendonmarotta.com/1000/persuasion-lessons-veritasium/
- Project note: [reference-script-craft.md](reference-script-craft.md)

## 4 The curiosity structure: the viewer's guess loop

The aim is a viewer who wonders, guesses, and is surprised. In order:

1. **Open on the anomaly.** One concrete moment where something does not add up. Not the death, the puzzle.
2. **Hand over clues before the explanation.** Numbers, places, a comparison. The viewer collects them.
3. **State the belief everyone held.** What every doctor knew. The viewer adopts it, so it can later be broken.
4. **Invite the guess out loud.** One host moment: "So what would you blame?" Then leave a beat.
5. **Test the likely guesses on screen, one by one.** Each fails in a short fragment ("Bad air? Same air. Nothing.").
   The viewer's own guesses are the ones being tested.
6. **Drop the clue the viewer did not see coming.** The one fact that none of the tested guesses covered.
7. **Let the viewer arrive a beat before the narrator.** Hold the last clue, ask the question, and let the picture
   do the work. The narrator confirms what the viewer already half-knows.
8. **End on the open question (pilot) or the payoff (full film).**

Example for Semmelweis, in outline: open on the two clinics and the two death rates (anomaly). Give the numbers
(clues). Say everyone blamed bad air (belief). Ask what the viewer would blame (guess). Test air, crowding, the
priest's bell, the birth position, each failing in a fragment (tests). Then Kolletschka's knife and the autopsy
(unseen clue). End on "What were their hands carrying?" (open question).

## 5 The twelve rules

1. Open cold on one concrete moment, present tense, a person or a place. No dateline sentences; a date goes inside a
   sentence ("It's the summer of eighteen sixty five, and...").
2. Median sentence 9-13 words, about 20% under 7 words, a one- or two-word fragment at each turn ("Nothing." "Bad
   air.").
3. Contractions everywhere ("he's", "didn't", "it's"); spoken connectors allowed ("Now," "So," "And," "Here's the
   thing"); "But" opens each reversal; "So" only for a question or a conclusion.
4. "You" 2-3 times, each a host moment: the misconception ("If you'd asked any doctor..."), the guess before the
   reveal, the closing question. No "I" except one host aside if it earns it.
5. A person is introduced once, full name and role in one clause.
6. Every number with a comparison, spoken plainly ("one mother in nine... next door, one in thirty six").
7. State the belief first, then the anomaly, then the question (misconception first).
8. No filler adjectives (incredible, fascinating, shocking).
9. Don't describe the picture, except a short "This is..." on an archive image.
10. Read-aloud test: any line you'd breathe in the middle of gets split.
11. End on the open question in a pilot; the payoff in a full film.
12. Real words stay real: quote the person's documented words; every line cites a verified claim; no invented facts.

Rule 12 is the guard on all the others. Spoken air (contractions, connectors, "you") is style. It never licenses an
invented fact, motive or quote. The voice ladder in `.claude/skills/story-film/references/script.md` still governs
who may say what.

## 6 The blend voice

The film uses two voices on purpose.

- **Scenes are told the Fern way.** Third person, present tense, short sentences, a fragment at each turn, people
  introduced with name and role, deictics on archive images. This carries the story.
- **Key moments are told the Veritasium way.** At the misconception, the guess and the closing question, the
  on-screen explorer turns to the viewer: "You'd think the air did it." "So what would you blame?" "Same hospital.
  Same air. What's different?" These are the 2-3 host moments of rule 4.

The switch is the signal. When the explorer says "you", the viewer knows a guess is wanted. Used more often, it
stops working and the film starts to sound like a lecture; used never, it sounds like a documentary being read.

## 7 How to check a script

- Read it aloud once, at speaking pace. Mark every place you breathe mid-sentence and split it (rule 10).
- Count: median sentence length, share under 7 words, number of "you" moments (2-3), number of "But" that really
  reverse the situation.
- Search for repeated phrases within 5 lines, dateline sentences, "it is said", and filler adjectives.
- Ask: where is the viewer's guess? If the script never asks, and never tests a wrong answer, it is explaining, not
  telling.
