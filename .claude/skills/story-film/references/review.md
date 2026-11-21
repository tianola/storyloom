# Review passes (in this order, after the first full draft)

## 1 First-time viewer read

Read the narration aloud from the top as someone who knows nothing.

- Is there a question I want answered by 30 s? Do I know whose story this is?
- Every 4-5 minutes, is there a new reason to keep watching?
- Did any line make me ask "why are you telling me this?" Cut it or give it a reason from the story.
- Did any explanation arrive before I knew who needed it?
- Does the ending answer the opening question and point back to the opening image?

## 2 Seam read

Read only the beat sheet's seams. Each one is **but** or **therefore**. Rewrite every "and then".

## 3 Voice read

- Every character line: which rung of the voice ladder (script.md §4)? Is there a higher rung available? Is it
  in `dramatisation.json` with a basis?
- No real person states a fact, a number, a discovery or a motive that the record does not hold.
- No two character lines in a row; none over 25 words.

## 4 Sound-off picture read (on the storyboard, then on stills)

- For every line: who is on screen, who is speaking, is the speaker visible 0.5 s before and big enough to read?
- For every place: does the establishing shot show the time of day and three period markers? Is the world bible
  visible (use, people at tasks, practical light, personal objects)? Are windows lives, not rectangles?
- For every move: what motivates it? Is it slower than a frame width per 7 s? Does it land and hold?
- For every shot: is it at least its minimum length? Does something change inside it if it is long?
- Montage only in the hook and in tension; explanations in one held move.

## 5 Accuracy read

- Every factual line has verified claims; numbers carry a comparison or a date; contested facts are said as
  contested; misconceptions are named as such.
- Period details in the picture (lighting, dress, transport, tools) match the year.

## 6 Cut pass

Cut 10-20% of the words. The cheapest words are those that describe the picture, repeat the previous line, or
announce what is coming ("Let's look at...").

## 7 Gates and stills

Run `qc_script`, `plan_storyboard --check`, then render stills at the start, middle and end of every beat and check
them against the world bible and the staging rules before the full render.
