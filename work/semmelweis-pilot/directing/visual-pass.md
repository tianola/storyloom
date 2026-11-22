# Semmelweis pilot v6: visual pass (directing and retention)

Status: proposal for review. Nothing in `script/`, `vo/`, `renders/` or `tools/` is changed, no voice credits are spent, nothing is rendered. Companion files in this folder: `cut.proposed.json`, `storyboard.proposed.json`, `narration.proposed.md`, `timeline.png`, `validate_proposal.py`.

Where the approved plan and the built cut differ, the cut (`cut.proposed.json`) wins. Times below are on the projected film clock (measured voice rate) unless a column says otherwise.

## 1. Summary

- v5 has the right narration but the pictures do not carry it: the numbers first arrive at 0:27, the hypotheses are shown over generic ward footage, Kolletschka's death plays over a still portrait for 11 s, and the film ends on a generic wide shot.
- v6 re-cuts the picture into **51 shots** (median 2.5 s) in two visual modes (Fern for the story, Veritasium for the investigation) plus a separate archive treatment on a mat. The film projects to **152.72 s** against 151.63 s of narration in v5.
- The hook is restructured so the anomaly comes first: both ratios are heard by 19.96 s (measured) or 21.72 s (conservative), and the tallies are fully on screen at 14.70 s. This needs two new voiced lines, u003′ and u005′ (about 160 characters).
- An evidence board recurs in five different forms (H1-H5), and the last one leaves the board and walks into the world.
- Curiosity loops 0, A, B and C, the Kolletschka answer and an open final loop give the film a belief, an experiment, a result and a next question throughout.
- One 23.3 s held moving shot (s46) carries the chain from the morgue to the mother in a single move. Its continuity is the argument.
- Every shot is tagged for provenance and claim ids; nothing is shown that the sources do not support.

**The user must approve:**

1. **The shot list (section 8) and the storyboard (section 9).**
2. **The text of u003′ and u005′** (section 3), because they need new voice.
3. **The architecture** (section 14): the graphics system and the cut-list timing schema, before any code is written.

## 2. Timecoded critique of v5

v5 clock (from `vo/manifest.json` and `storyboard.json`). Shot ids in the last column refer to section 8, on the v6 clock.

| Time (v5) | Line | On screen in v5 | Problem | Fix in v6 |
|---|---|---|---|---|
| 0:00-0:05 | u001 | Hospital engraving, still, 5.2 s | The film opens on a static image. No woman, no motion, no stakes. | Moving open: a woman in labour walks to the gate (s01), push on the hospital (s02). The engraving moves under u003 on the archive mat, 2.3 s (s05). |
| 0:05-0:11 | u002 | Roofs, then the court (beat-01) | 'Any doctor will tell you why. Bad air.' No doctor, no air. The belief is only said. | A top-hatted doctor waves at the drain and smoke (s03), then the foul court on 'Bad air' (s04). Loop 0 belief. |
| 0:11-0:16.5 | u003 | Street, then the doors | The question ('which day') arrives before any anomaly. Nothing yet to wonder about. | The question moves to u004, after the numbers. The doors with tallies fill the 13.7-16.8 s window (s06), then the ratios (s07). |
| 0:16.5-0:27 | u004, u005 | Court-wide glide, 20 s | Two clinics and who runs them are told over a long empty glide. It informs nothing. | Doors with alternating day labels (s10); matched-framing clue shots (s11, s12). |
| 0:27-0:33 | u006 | Same court glide | **The numbers arrive at 0:27** and are only said. 11 in 100 against 3 in 100 is never seen. | Numbers move to u003′ at 11.4 s and are shown three ways: tallies (s06), a figure grid (s07), the host at the board (s08). Visual contrast on screen by 14.7 s. |
| 0:33-0:38.7 | u007 | Court glide, then the doors | 'The women beg on their knees': no woman, no knees. | A woman kneels at the First Clinic door (s13), then a close on the mother before her line (s14). |
| 0:38.7-0:47.6 | u008, u009 | Doors, then rooftops | 'Please. Not the first clinic' over roofs: no face. 'Same air' over roofs: no air. | Close on the mother (s14); 'Same building / city / air' as three short shots with smoke on the last (s15-s17); H2 hands the guess to the viewer (s18). |
| 0:47.6-0:55 | u010 | 1860 portrait of Semmelweis, still, 7.5 s | A portrait of the older man shown on 'he's twenty eight'. Wrong age, static, 7.5 s. | The young 3D Semmelweis steps into the ward (s19), face close (s20). The portrait moves to u028, 'change medicine' (s49). |
| 0:55-1:01 | u011 | Desk, one held push | One shot for six seconds. 'Everything was in question' has no object. | Desk (s21), then the death ledger, a column of crosses (s22). The ledger becomes a recurring motif. |
| 1:01-1:13.8 | u012, u013 | Ward aisle, one slow move, 12.6 s | The plan to test guesses is illustrated by a generic ward. The street-birth evidence is not shown. | H3 lays out three cards (s23); AIR card (s24); a street birth (s25); the empty ledger column (s26). Loop A. |
| 1:13.8-1:19.4 | u014 | Ward bed | 'They lie on their side' has no comparison and no result. | POSITION card overlay on the door shot (s27); matched framing of the Second Clinic bed (s28); First Clinic turned onto its side (s29). Loop B. |
| 1:19.4-1:20.5 | u015 | Ward door | 'Nothing changes' is not shown to change nothing. | The ledger takes another cross, with the bell heard under it (s30, J-cut). |
| 1:20.5-1:46.8 | u016-u019 | Eleven generic ward views (beat-05) | Fear, bell, reroute and 'still dying' all look the same. No route is shown; the reroute and its failure are only said. | FEAR card (s31); the procession and mothers turning (s32-s35); a schematic route plan (s36); the quiet priest (s37); the ledger (s38); H4 empties the board (s39, s40). Loop C. |
| 1:46.8-1:58.2 | u020 | Kolletschka's portrait, still, 11.4 s | **The central event, the cut and the death, plays over a static portrait for 11 s.** Nothing is shown happening. | Dissecting room (s41); portrait on the mat for 3.5 s (s42); scalpel, cut hand, sickbed (s43-s45). |
| 1:58-2:10 | u021, u022 | Dissecting room, quick looks and jars | Jars and rooms. 'Same disease as the mothers' is not connected to the mothers. | One continuous move from the body to a mother's bed (s46). |
| 2:10-2:31.6 | u023-u029 | Aisle move, then a hold and a pull-back wide | The chain 'morgue to mother' is told in words over a ward. The film ends on a generic wide shot with no question left on screen. | s46 carries the chain; s47 the question in the hands; s48 he looks at his hands; s49 the portrait; s50 the hands push open the next door; s51 black. |

## 3. The hook

The opening now follows the Veritasium order: belief, anomaly (the numbers), question, clue. Only u003′ and u005′ need new voice.

### Line table (v5 against v6)

| v6 id | v6 text | v5 source | Status |
|---|---|---|---|
| u001 | It's eighteen forty six, and a woman in labour arrives at Vienna General Hospital. | u001 | kept, voiced |
| u002 | If she gets a fever after the birth and dies, any doctor here will tell you why. Bad air. | u002 | kept, voiced |
| **u003′** | **The hospital has two maternity clinics. In the first, one mother in nine dies. Yet in the second, it's one in thirty six.** | new; replaces the numbers of v5 u006 and the 'two clinics' of v5 u004 | new, 23 words |
| u004 | But here's what nobody can explain: why does it matter so much which day she walks in? | v5 u003, text and audio reused | kept, voiced |
| **u005′** | **They take women in on alternate days.** | new; replaces the 'alternate days' of v5 u004 | new, 7 words |
| u006 | Doctors and medical students run the first one, and midwives run the second. | v5 u005, text and audio reused | kept, voiced |
| u007-u029 | unchanged | same ids, same audio | kept, voiced |

Dropped: v5 u004 ("The hospital has two maternity clinics, and they take women in on alternate days."), split between u003′ and u005′; and v5 u006 ("That year, one mother in nine dies in the first clinic. In the second, it's one in thirty six."), whose numbers move into u003′. The film keeps 29 lines. The remap touches only u003-u006 in `claims.json` (u003′: c7; u004: c6, c7; u005′: c6; u006: c5), `story.json` (question u004, guess u002), `chapters.json` and `dramatisation.json`. The new text is 158 characters in total.

**Why each change.** u003′ puts the anomaly before the question, so the viewer has something to wonder about by 14 s instead of 27 s. u005′ gives the alternating admission days their own short line, which s10 shows with alternating day labels. Reusing the v5 audio of u003 and u005 for u004 and u006 keeps the paid voice work.

### Timing math

Rates: **measured** 2.88 words/s (the v5 narrator at speed 1.15; example: v5 u006, 18 words in 6.25 s) and **conservative** 2.36 words/s (the `qc_script` estimate). The voice speed is not changed. Both include a 0.3 s pause at each sentence end. u003′ starts at 11.37 s and has 23 words; 'one mother in nine' is words 10-13, 'one in thirty six' is words 20-23.

| Point | Words | Measured (2.88 w/s) | Conservative (2.36 w/s) |
|---|---|---|---|
| 'The hospital has two maternity clinics.' ends | 1-6 | 13.45 s | 13.91 s |
| 'one in nine' heard by | 10-13 | **16.18 s** | **17.18 s** |
| 'Yet' begins (first gap word) | 15 | 16.83 s | 17.90 s |
| 'one in thirty six' heard by | 20-23 | **19.96 s** | **21.72 s** |
| u003′ ends (with sentence pause); u004 starts | | 20.26 s | 22.02 s |
| Tallies fully on screen (s06, built from 13.85 s) | | 14.70 s | 14.70 s |

- Both ratios are heard by about 20-22 s at either rate. The visual contrast is on screen before either ratio is spoken: the engraving runs under 'two maternity clinics' (s05, 11.4-13.7 s), then the doors with tallies (s06) show 11 against 3 per 100 (c7).
- **Effect on the rest of the film.** On the measured clock every later line is within 0.1 s of v5: the narration ends at 151.72 s against 151.63 s, and the film is 152.72 s with its 1 s black tail. On the conservative clock u004 starts 1.76 s later and every line from u006 on starts 2.30 s later. The proposal uses the measured clock; the cut-list anchors to words, so it survives either rate once the real voice is measured.

### Why 'Yet'

`qc_script`'s hook rule needs a gap word within 20 s at its 2.36 w/s estimate. Without 'Yet' the first gap word came in u004, at 22.9 s. With 'Yet' in front of 'in the second', the first gap word comes at 17.90 s conservative (16.83 s measured). It also does real work in the sentence: it marks the second figure as the surprise.

## 4. Two visual modes and the archive treatment

| Mode | Code | Look | Used for | Shots | Screen time |
|---|---|---|---|---|---|
| FERN, the story | F | Full-bleed pixel-art 3D reconstruction in warm period light. No host. Composed wide, medium and close shots; every move is motivated. Atmospheric sound. | The mystery, the wards, the court, Kolletschka's death, the held shot, the ending | 38 | 118.0 s |
| VERITASIUM, the investigation | V | The explorer speaks to the lens. Cooler key light, shallow focus. The board, data and schematics appear here. | The five host moments H1-H5 and the card inserts | 8 | 21.3 s |
| Graphic | G | Full-frame graphic from the graphics system, opaque background; Veritasium side | The ratio comparison (s07) and the ward route plan (s36) | 2 | 5.0 s |
| ARCHIVE | A | Never in pixel art. A dark mat inside a thin border with paper texture; the credit sits on the mat and never covers the picture. 6 s or shorter including transitions. | Three real documents | 3 | 8.5 s |

The viewer tells the modes apart by light (warm against cool), depth of field (deep against shallow), and who looks at the lens. Archive is the third, clearly separate treatment, so a real document is never mistaken for a reconstruction. The tally in s06 is an overlay on a Fern shot, so it is counted as Fern.

**Archive placement**

| Still | Shot, start | Under | Screen time | Ledger row |
|---|---|---|---|---|
| Schaffer engraving of the hospital (c. 1784) | s05, 0:11.4 | 'The hospital has two maternity clinics' (u003) | 2.3 s | arch-002 |
| Kolletschka portrait (Kriehuber, 1844) | s42, 1:50.4 | 'his friend Jakob Kolletschka...' (u020) | 3.5 s | arch-004 |
| Semmelweis, 1860 (after Doby) | s49, 2:25.8 | 'change medicine' (u028) | 2.6 s | arch-001 |

arch-003 is unused. arch-001 shows Semmelweis at about 42, so it is not placed on 'he's twenty eight' (u010).

## 5. The evidence board

One device, five purposes. No two host moments share a framing or an interaction; the validator refuses a repeat.

| # | Line | Shots | Start | Purpose | Framing | Interaction |
|---|---|---|---|---|---|---|
| H1 | u004 | s08, s09 | 0:20.3 | turn the anomaly into a mystery | 3/4 low angle, medium-wide; insert, calendar strip | door sketches with tallies; flips the calendar strip; calendar strip flips day |
| H2 | u009 | s18 | 0:44.4 | hand the guess to the viewer | tight close-up, board out of focus | holds a blank card and pencil out to the lens |
| H3 | u012 | s23 | 1:01.3 | lay out the investigation plan | top-down on the desk, hands only | lays three cards: AIR, POSITION, FEAR |
| H4 | u019 | s39, s40 | 1:40.7 | the verdict: the void | over the shoulder, behind the host; he turns to the lens, medium | three struck cards; pulls the last down; turns to lens on 'wrong' |
| H5 | u023 | s46, inside the held shot | 1:58.3 | leave the board: the investigation enters the world | on location in the corridor, inside the continuous shot | walks beside the students, turns to the lens |

- H1 (s08, s09): the two door sketches with their tallies are pinned; on 'which day' his hand flips the calendar strip between them.
- H2 (s18): tight close-up, board fully out of focus, eyes to lens; he holds a blank card and a pencil out to the viewer; a held 1 s silence.
- H3 (s23): top-down on the desk, hands only; he lays three cards in a row, AIR, POSITION, FEAR.
- H4 (s39, s40): over the shoulder from behind; the three struck cards; he pulls the last one down so only the door sketches are left; he turns to the lens on 'wrong'.
- H5 (s46): **leaves the board.** On location in the corridor, inside the continuous shot, he walks beside the students and turns to the lens at 'Now think about who does the autopsies...' (u023).

**Card inserts and overlay.** Between the host moments the board returns in a different form each time:

| Card | Form | Shot | Start | Time on screen | Sets up |
|---|---|---|---|---|---|
| AIR | 3D board insert, card pinned | s24 | 1:05.3 | 1.33 s | Loop A |
| POSITION | **Overlay on the door shot** (`board_card`, top-right, pinned), not a cutaway | s27 | 1:12.9 (overlay from 1:13.2) | 1.28 s overlay | Loop B |
| FEAR | 3D board insert, card pinned | s31 | 1:20.6 | 1.33 s | Loop C |

The board therefore recurs in three further forms (insert, overlay, insert) besides the five host moments. The beat notes for s24 and s31 target a 0.7 s pin, while the cut gives each 1.33 s of screen time (the validator's limit is 1.5 s); reconcile when the beats are timed.

## 6. Curiosity loops

Each loop runs belief, experiment, result, next question. Shot ids come from the cut's `loop`, `role` and `also` fields. A shot can serve two loops: s27 is Loop B's belief and Loop A's next question; s30 is Loop B's result and its next question.

### Loop 0: the mystery (u001-u009)

| Part | Content | Shots |
|---|---|---|
| Belief | Bad air (u002); a doctor in the court waves at the drain and smoke | s03, s04 |
| Anomaly | Tallies at the two doors, then the numbers (u003′) | s06, s07 |
| Question | 'Which day?' H1 flips the calendar strip | s08, s09 |
| Clue, planted | Matched framing: First Clinic doctors and students cross the court from the anatomy wing in aprons; midwives stand at the Second Clinic. Shown, never pointed out (c5, c12) | s10, s11, s12 |
| Stakes | The mothers beg (u007, u008) | s13, s14 |
| Next question | H2 hands the guess to the viewer | s18 |

### Loop A: air (u013)

| Belief | Experiment | Result | Next question |
|---|---|---|---|
| The AIR card: the fever comes from foul air (s24) | An observation, not a trial: a woman gives birth on the cobbles outside the gate, in the dirtiest air in Vienna (c9) (s25) | Unexpected: she is fine. The street-births ledger column stays empty while the First Clinic's fills (s26) | 'So it's something inside': the camera follows a midwife through the First Clinic door; it shuts. The same shot is Loop B's belief (s27) |

Setup: H3 lays out the plan (s23).

### Loop B: position (u014-u015)

| Belief | Experiment | Result | Next question |
|---|---|---|---|
| The POSITION card, as an overlay on the door shot. Matched framing: a Second Clinic mother on her side (s27, s28) | A wide First Clinic as the mothers are turned onto their side, so every bed matches the Second Clinic (c24) (s29) | Disappointing: 'Nothing changes.' The ledger takes another cross at the same pace (s30) | A J-cut: the bell is heard under 'Nothing changes' before it is seen. What is that sound? (s30) |

### Loop C: fear (u016-u019)

| Belief | Experiment | Result | Next question |
|---|---|---|---|
| The FEAR card; the priest and bell come down the aisle, mothers turn to watch (existing `bell` action, c18); Semmelweis at his door, for his own words (c19) (s31, s32, s33, s34, s35) | A schematic ward plan, labelled 'schematic', with the old route against a quieter one; then the priest comes by the quiet route, no bell, and nobody turns (s36, s37) | 'But the mothers keep dying': the ledger (s38) | H4 empties the board. If it isn't the air, the body or the fear, then what? (s39, s40) |

### Answer: Kolletschka (u020-u026)

| Belief / setup | Experiment | Result | Next question |
|---|---|---|---|
| After H4 the board is empty: nothing explains it (s39, s40) | The cut happens to a doctor, in the room the students came from in u006: scalpel, slip, cut hand, sickbed (s41-s45) | His autopsy shows the mothers' disease (c23); then the continuous shot walks back along the path planted at s11 (s46) | 'So what are those hands carrying?' (s47, s48) |

s41-s46 all carry `loop: K, role: answer`. The clue shot s11 (at 0:28.2) comes before the chain shot s46 (at 1:58.3), so the answer lands on something the viewer has already seen.

### Open loop (u025-u029)

| Belief | Experiment | Result | Next question |
|---|---|---|---|
| The hands are the vehicle (end of s46) | The hands in silhouette; Semmelweis looks at his own hands; his portrait (s47, s48, s49) | The answer (chlorine) is never shown | The same hands push open the next door toward another mother; it swings shut; black (s50) |

## 7. Sequence, shot and held shot

**Definitions** (also used by the validator):

- **Shot:** the picture between two cuts, as `scdet` measures it on the master.
- **Sequence:** a dramatic unit in one place and time, made of one or more shots. Example: the Kolletschka sequence, 11.4 s across 5 shots (s41-s45); the plan counted six.
- **Held shot:** one uninterrupted **moving** shot that explains something by its continuity. The existing gate `rhythm.cuts.held_shot_min_seconds` = 20 s ("nothing is explained in one held, moving shot") asks for one. It is never a static frame: the still rule caps any motionless image at 10 s.

**The held shot is s46**, 1:58.3 to 2:21.6 (23.3 s), scene `wing`, one travel move from `wing-table` to `wing-ward-bed`, entered through a 0.8 s dip to black from the sickbed. It runs from u021 to the end of u025, and H5 is inside it at u023:

1. Under Semmelweis's thought (u021), the camera finds the covered body in the dissecting room.
2. Doctors examine it: 'the same disease that's killing the mothers'.
3. The camera follows the doctors and students from the table, out the door, down the corridor, past the host (H5, u023), and in through the First Clinic door to a mother's bed.
4. It ends pushing into the bare hands on 'With the same bare hands.' (u025).

**Why the continuity is the argument.** Because the camera never cuts, the viewer sees that nothing happens between the morgue and the mother: no basin, no break (c12, c15). A cut anywhere on that path would let the viewer assume something happened off screen. If the shot did not serve this, the gate would be argued in the report, not padded.

**Other rhythm targets** (validator, on the projected shots): median shot 2.50 s over 50 pictures; 20% of shots under 1.5 s (requirement at least 12%); longest shot s46 at 23.30 s; no other shot over 10 s; every shot at least 2 frames. Most informational shots run 2-4 s; montage only in the loops' experiment inserts.

## 8. Proposed shot list

All 51 shots from `cut.proposed.json`. Modes: F Fern, V Veritasium, A archive, G graphic. Start is on the projected film clock (m:ss.s). 'Build' marks shots that need new work (section 12).

| Id | Start | Len (s) | Mode | Source (view / archive / graphic) | Lines | Provenance | What it shows | Build |
|---|---|---|---|---|---|---|---|---|
| s01 | 0:00.0 | 2.57 | F | v6-01-vienna / gate-approach | u001 | reconstruction | dawn street; a woman in labour, held by a midwife, walks toward the hospital gate; her face, close | yes |
| s02 | 0:02.6 | 2.60 | F | v6-01-vienna / hospital | u001 | reconstruction | she looks up at the facade; low angle push on the hospital | — |
| s03 | 0:05.2 | 5.07 | F | v6-01-vienna / court-low | u002 | reconstruction | a top-hatted doctor in the court explains to a student, waving at the drain and the smoke | yes |
| s04 | 0:10.2 | 1.13 | F | v6-01-vienna / court | u002 | reconstruction | the foul drain and chimney smoke over the court: 'Bad air.' | — |
| s05 | 0:11.4 | 2.33 | A | archive: akh-engraving (mat) | u003 | archive | the real hospital: Schaffer engraving on the archive mat, slow push; credit on the mat | — |
| s06 | 0:13.7 | 3.07 | F | v6-02-vienna / doors | u003 | reconstruction | both doors in one frame; under each a tally builds: 11 marks against 3 per 100 births | — |
| s07 | 0:16.8 | 3.50 | G | graphic: ratio-1846 | u003, u004 | graphic-data | full-frame ratio_compare: 9 figures, 1 dark, 'about 1 in 9' / 36 figures, 1 dark, 'about 1 in 36'; right side... | — |
| s08 | 0:20.3 | 3.63 | V | v6-03-board / h1-low34 | u004 | reconstruction | host at the board's edge; the two door sketches with tallies pinned | yes |
| s09 | 0:23.9 | 1.53 | V | v6-03-board / h1-calendar | u004, u005 | reconstruction | insert: his hand flips the calendar strip between the two doors | yes |
| s10 | 0:25.4 | 2.73 | F | v6-04-vienna / doors | u005, u006 | reconstruction | the two doors; day labels alternate the open door; the queue of women moves door to door | — |
| s11 | 0:28.2 | 3.50 | F | v6-04-vienna / first-door | u006 | reconstruction | matched framing A: doctors and students cross the court from the anatomy wing, aprons on, into the First Clinic... | yes |
| s12 | 0:31.7 | 1.70 | F | v6-04-vienna / second-door | u006, u007 | reconstruction | matched framing B: midwives in blue and white at the Second Clinic, same lens and angle | yes |
| s13 | 0:33.4 | 4.37 | F | v6-04-vienna / first-door | u007 | reconstruction | a woman kneels at the First Clinic door, pleading with the porter | yes |
| s14 | 0:37.7 | 3.53 | F | v6-04-vienna / at:first | u007, u008 | reconstruction | close on the mother (on screen before her line) | — |
| s15 | 0:41.3 | 0.73 | F | v6-04-vienna / hospital | u009 | reconstruction | 'Same building.' | — |
| s16 | 0:42.0 | 1.07 | F | v6-04-vienna / roofs | u009 | reconstruction | 'Same city.' | — |
| s17 | 0:43.1 | 1.33 | F | v6-04-vienna / court-low | u009 | reconstruction | 'Same air.' smoke | — |
| s18 | 0:44.4 | 3.30 | V | v6-05-board / h2-close | u009, u010 | reconstruction | host close, eyes to lens; the blank card held out; holds into the start of u010 | yes |
| s19 | 0:47.7 | 3.97 | F | v6-06-ward / ward-door | u010 | reconstruction | young Semmelweis (the 3D character) steps into the First Clinic ward | — |
| s20 | 0:51.7 | 3.50 | F | v6-06-ward / semmelweis-close | u010 | reconstruction | his face, close: twenty-eight, new to the job | yes |
| s21 | 0:55.2 | 1.87 | F | v6-07-vienna / desk | u011 | reconstruction | night, his desk, his face | — |
| s22 | 0:57.0 | 4.30 | F | v6-07-vienna / ledger | u011, u012 | reconstruction | insert: the death ledger, a column of crosses (tally marks only, no legible text) | yes |
| s23 | 1:01.3 | 3.93 | V | v6-08-board / h3-top | u012 | reconstruction | top-down: his hands lay three cards in a row | yes |
| s24 | 1:05.3 | 1.33 | V | v6-08-board / card-air | u013 | reconstruction | insert 0.7 s: the AIR card pinned | yes |
| s25 | 1:06.6 | 4.60 | F | v6-09-vienna / street-birth | u013 | reconstruction | the dirtiest air in Vienna: a woman gives birth on the cobbles outside the gate; a midwife kneels by her; carts... | yes |
| s26 | 1:11.2 | 1.70 | F | v6-09-vienna / ledger-street | u013, u014 | reconstruction | the ledger: the street-births column stays empty while the First Clinic's fills | yes |
| s27 | 1:12.9 | 1.63 | F | v6-09-vienna / first-door | u014 | reconstruction | Loop A's next question, 'so it's something inside': follow a midwife through the First Clinic door as it shuts; the POSITION card pins at the corner (overlay) | — |
| s28 | 1:14.5 | 2.53 | F | v6-10-ward / second-bed | u014 | reconstruction | matched framing A: a Second Clinic mother lies on her side | yes |
| s29 | 1:17.1 | 2.47 | F | v6-10-ward / ward-wide | u014 | reconstruction | wide First Clinic: the mothers are turned onto their side; every bed now matches | yes |
| s30 | 1:19.5 | 1.07 | F | v6-11-vienna / ledger | u015, u016 | reconstruction | 'Nothing changes.' a hand adds a cross to the ledger; the bell is HEARD under it (J-cut) | yes |
| s31 | 1:20.6 | 1.33 | V | v6-12-board / card-fear | u016 | reconstruction | insert 0.7 s: the FEAR card pinned | yes |
| s32 | 1:21.9 | 5.03 | F | v6-13-ward / ward-wide | u016 | reconstruction | the priest and the bell come down the aisle (existing bell action, route: aisle) | — |
| s33 | 1:27.0 | 1.77 | F | v6-13-ward / at:bell | u016 | reconstruction | the boy's bell, close; mothers turning toward it | — |
| s34 | 1:28.7 | 2.40 | F | v6-13-ward / ward-door | u016, u017 | reconstruction | Semmelweis at his door, hearing it (on screen before his line) | — |
| s35 | 1:31.1 | 5.20 | F | v6-13-ward / semmelweis-close | u017, u018 | reconstruction | his face as the bell passes | yes |
| s36 | 1:36.3 | 1.50 | G | graphic: ward-plan-routes | u018 | graphic-schematic | map_plan, labelled 'schematic': old route down the aisle (red) vs a quieter route (white) | — |
| s37 | 1:37.8 | 2.17 | F | v6-14-ward / ward-wide | u018 | reconstruction | the priest by the quieter route, no bell; nobody turns | yes |
| s38 | 1:40.0 | 0.73 | F | v6-15-vienna / ledger | u018, u019 | reconstruction | the ledger: another cross | yes |
| s39 | 1:40.7 | 5.33 | V | v6-16-board / h4-ots | u019 | reconstruction | behind the host: AIR, POSITION, FEAR struck; he pulls the last one down; only the doors remain | yes |
| s40 | 1:46.1 | 0.87 | V | v6-16-board / h4-turn | u019, u020 | reconstruction | he turns to the lens on 'wrong' | yes |
| s41 | 1:46.9 | 3.50 | F | v6-17-vienna / anatomy | u020 | reconstruction | the dissecting room: Kolletschka lecturing at the table (existing staging) | — |
| s42 | 1:50.4 | 3.50 | A | archive: kolletschka-portrait (mat) | u020 | archive | his real portrait on the mat (Kriehuber 1844), through 'professor of forensic medicine' | — |
| s43 | 1:53.9 | 1.57 | F | v6-18-vienna / scalpel | u020 | reconstruction | a student's scalpel over the table, close | yes |
| s44 | 1:55.5 | 1.80 | F | v6-18-vienna / cut-hand | u020 | reconstruction | the blade slips; a cut on his hand, a red drop | yes |
| s45 | 1:57.3 | 1.00 | F | v6-18-vienna / sickbed | u020, u021 | reconstruction | Kolletschka fevered in a sickbed; dip to black on 'he dies' | yes |
| s46 | 1:58.3 | 23.30 | F | v6-19-wing / wing-table → wing-ward-bed | u021, u022, u023, u024, u025 | reconstruction | THE HELD SHOT: body in the dissecting room, doctors examine it, camera follows them down the corridor past the host (H5), through the First Clinic door to a bed, pushes into the bare hands | yes |
| s47 | 2:21.6 | 2.13 | F | v6-20-ward / hands-window | u026 | symbolic | the hands frozen in silhouette against the window light; dust drifts in the beam; slow push | yes |
| s48 | 2:23.7 | 2.10 | F | v6-20-ward / semmelweis-hands | u027, u028 | reconstruction | Semmelweis looks down at his own hands | yes |
| s49 | 2:25.8 | 2.63 | A | archive: semmelweis-portrait (mat) | u028 | archive | his real portrait (after Doby, 1860; the older man) on the mat | — |
| s50 | 2:28.5 | 3.27 | F | v6-21-ward / hands-door | u029 | reconstruction | the same unwashed hands push open the next ward door toward another mother; it swings shut | yes |
| s51 | 2:31.7 | 1.00 | F | black | u029 | black | black tail | — |

Transitions are cuts except s05 (0.3 s dissolve into the engraving), s46 (0.8 s dip) and s51 (0.6 s dip to black). s30 carries a J-cut: the bell is heard 0.8 s before it is seen. Overlays: s06 tally, s10 day labels, s27 POSITION card, s41 'March 1847' date stamp.

## 9. Storyboard

One row per beat of `storyboard.proposed.json` (21 3D beats). Existing scenes are `vienna` and `ward`; `board` and `wing` are new. The last column lists what the beat needs that does not exist yet.

| Beat | Scene | Shots (view @ start in the beat, s) | New scenes or views |
|---|---|---|---|
| v6-01-vienna | vienna | gate-approach @ 0.0; hospital @ 2.6; court-low @ 5.2; court @ 10.2 | yes: view gate-approach; staging labour-arrival (mother + midwife walk); staging doctor-explains (doctor + student, point at drain) |
| v6-02-vienna | vienna | doors @ 0.0 | no, existing views |
| v6-03-board | board | h1-low34 @ 0.0; h1-calendar @ 3.6 | yes: scene board; view h1-low34; view h1-calendar |
| v6-04-vienna | vienna | doors @ 0.0; first-door @ 2.7; second-door @ 6.2; first-door @ 7.9; at:first @ 12.3; hospital @ 15.8; roofs @ 16.6; court-low @ 17.6 | yes: staging students-from-anatomy (group walks anatomy wing -> first door); view second-door matched to first-door (same lens/height/angle, mirrored); pose kneel; actor porter |
| v6-05-board | board | h2-close @ 0.0 | yes: scene board; view h2-close |
| v6-06-ward | ward | ward-door @ 0.0; semmelweis-close @ 4.0 | yes: view semmelweis-close |
| v6-07-vienna | vienna | desk @ 0.0; ledger @ 1.9 | yes: prop death-ledger on the desk; view ledger; action tally (adds a cross) |
| v6-08-board | board | h3-top @ 0.0; card-air @ 3.9 | yes: scene board; view h3-top; view card-air |
| v6-09-vienna | vienna | street-birth @ 0.0; ledger-street @ 4.6; first-door @ 6.3 | yes: pose give-birth; staging street-birth; view street-birth; view ledger-street (two columns) |
| v6-10-ward | ward | second-bed @ 0.0; ward-wide @ 2.5 | yes: pose lie-side; view second-bed (matched to ward-bed); ward param lie: side (all patients) |
| v6-11-vienna | vienna | ledger @ 0.0 | yes: view ledger |
| v6-12-board | board | card-fear @ 0.0 | yes: scene board; view card-fear |
| v6-13-ward | ward | ward-wide @ 0.0; at:bell @ 5.0; ward-door @ 6.8; semmelweis-close @ 9.2 | yes: view semmelweis-close |
| v6-14-ward | ward | ward-wide @ 0.0 | yes: bell params route/ring |
| v6-15-vienna | vienna | ledger @ 0.0 | yes: view ledger |
| v6-16-board | board | h4-ots @ 0.0; h4-turn @ 5.3 | yes: scene board; view h4-ots; view h4-turn |
| v6-17-vienna | vienna | anatomy @ 0.0 | no, existing views |
| v6-18-vienna | vienna | scalpel @ 0.0; cut-hand @ 1.6; sickbed @ 3.4 | yes: prop scalpel; view scalpel; action cut; view cut-hand; pose sick; set sickbed; view sickbed |
| v6-19-wing | wing | wing-table @ 0.0 → wing-ward-bed | yes: scene wing (anatomy + corridor + ward joined); views wing-table..wing-ward-bed; explorer full figure on location; close on hands at the end of the move |
| v6-20-ward | ward | hands-window @ 0.0; semmelweis-hands @ 2.1 | yes: sprite hands (large); view hands-window; dust in window beam; view semmelweis-hands; pose look-hands |
| v6-21-ward | ward | hands-door @ 0.0 | yes: view hands-door; action door-swing |

## 10. Mute test

For every concrete fact there is a shot that shows it working, so a muted viewer would still get it. The validator refuses a fact with no shot tagged `demonstrates`. Facts and shot ids are the cut's `demonstrates` tags.

| Fact | Demonstrating shots |
|---|---|
| belief: bad air | s04 |
| two clinics side by side | s06 |
| the death difference (tallies) | s06 |
| the death difference (ratios) | s07 |
| admission on alternate days | s10 |
| who staffs each clinic | s11, s12 |
| students come from the anatomy wing (planted) | s11 |
| women beg not to go to the First Clinic | s13 |
| the deaths are counted (ledger motif) | s22 |
| belief: air | s24 |
| street births: worse air | s25 |
| street births: rarely fever (empty column) | s26 |
| belief: position | s27 |
| Second Clinic: mothers on their side | s28 |
| First Clinic: mothers turned onto their side | s29 |
| position changed nothing (ledger same pace) | s30 |
| belief: fear | s31 |
| the priest's procession through the ward | s32 |
| mothers turn in fear | s33 |
| the route changed | s36 |
| the priest comes quietly; mothers don't turn | s37 |
| rerouting changed nothing (ledger) | s38 |
| a student's scalpel at the autopsy | s43 |
| the cut on Kolletschka's hand | s44 |
| Kolletschka falls ill and dies | s45 |
| same disease: body then mother in one move | s46 |
| the chain: morgue to mother, no break | s46 |
| the same bare hands | s46 |
| the question: what are the hands carrying | s47 |
| the hands go on to the next mother | s50 |

The validator additionally checks 12 headline facts (two clinics side by side; alternate days; who staffs each clinic; the death difference; street births; position; rerouting; Kolletschka's cut; his death; same disease; the chain; the bare hands).

## 11. Accuracy and provenance

**Provenance tags on the 51 shots**

| Tag | Meaning | Shots |
|---|---|---|
| `reconstruction` | Pixel 3D | 44 |
| `archive` | Real document on the mat, with a credit | 3 |
| `graphic-data` | Numbers from c7, with a 'Semmelweis 1861 · 1846 figures' tag | 1 |
| `graphic-schematic` | Labelled 'schematic' | 1 |
| `symbolic` | At most two across the film | 1 |
| `black` | Black tail | 1 |

Overlays carry their own tags: the tally (s06) and the date stamp (s41) are `graphic-data`; the day labels (s10) and the POSITION card (s27) are `graphic-schematic`. Counting the full-frame route plan s36, the validator finds 3 schematic graphics. The two symbolic devices are the dust in the window beam (s47) and the dip to black (s46). No candle and no germ imagery.

**Rules**

- The ledger prop shows only tally marks: no legible invented names, dates or text.
- The ward plan is labelled 'schematic'. The source says only 'a less obvious route' (c18), so no specific door is claimed.
- The figure grid is labelled 'about 1 in 9 / about 1 in 36' against the exact 11.4% and 2.8% of c7.
- The archive is checked again against the Commons pages: author, date, depicted subject and public-domain status. arch-001 shows Semmelweis at about 42, so it goes on u028, not on 'he's twenty eight'. The Kolletschka portrait plays under 'his friend Jakob Kolletschka...' (3.5 s) and the hospital engraving under 'The hospital has two maternity clinics' (2.3 s). All three are 6 s or shorter.
- arch-003 is unused. Ledger rows in use: arch-002 (Schaffer engraving, c. 1784, via Dorotheum), arch-004 (Kriehuber lithograph, 1844, photographed at the Albertina), arch-001 (after Doby, engraving 1860).

**Claim ids used per act** (shots grouped by their first line)

| Act | Shots | Claim ids |
|---|---|---|
| I. The mystery (u001-u009) | s01 to s18 | c4, c5, c6, c7, c8, c10, c20, c26 |
| II. The tests (u010-u019) | s19 to s40 | c4, c7, c9, c10, c11, c17, c18, c19, c21, c24, c26 |
| III. The turn and the held shot (u020-u025) | s41 to s46 | c5, c11, c12, c13, c15, c21, c22, c23 |
| IV. The open loop (u026-u029) | s47 to s51 | c12, c13, c14, c25 |

Every claim id appears in `research/sources.md`, and every line with a claim has a shot over it.

## 12. Assets to create or source

**Nothing new to source.** All pictures already exist (three archive stills and the Poly Haven assets). Re-verify the three Commons pages (arch-001, arch-002, arch-004) for author, date, subject and licence before the render. Everything below is built in the pipeline.

| Kind | Item | Shots / use |
|---|---|---|
| scene | board | s08, s09, s18, s23, s24, s31, s39, s40 |
| scene | set: sickbed | s45 |
| scene | wing (anatomy + corridor + ward joined) | s46 |
| view | gate-approach | s01 |
| view | h1-low34 | s08 |
| view | h1-calendar | s09 |
| view | second-door matched to first-door (same lens/height/angle, mirrored) | s12 |
| view | h2-close | s18 |
| view | semmelweis-close | s20, s35 |
| view | ledger | s22, s30, s38 |
| view | h3-top | s23 |
| view | card-air | s24 |
| view | street-birth | s25 |
| view | ledger-street (two columns) | s26 |
| view | second-bed (matched to ward-bed) | s28 |
| view | card-fear | s31 |
| view | h4-ots | s39 |
| view | h4-turn | s40 |
| view | scalpel | s43 |
| view | cut-hand | s44 |
| view | sickbed | s45 |
| view | wing-table..wing-ward-bed | s46 |
| view | close on the hands at the end of the held move | s46 |
| view | hands-window | s47 |
| view | semmelweis-hands | s48 |
| view | hands-door | s50 |
| pose | kneel | s13 |
| pose | give-birth | s25 |
| pose | lie-side | s28 |
| pose | sick | s45 |
| pose | look-hands | s48 |
| prop | death-ledger on the desk | s22 |
| prop | scalpel | s43 |
| prop | large hands sprite | s47 |
| action | tally (adds a cross) | s22 |
| action | ward parameter: lie = side for all patients | s29 |
| action | bell parameters: route and ring (existing `bell` action) | s37 |
| action | cut | s44 |
| action | door-swing | s50 |
| staging | labour-arrival (mother + midwife walk) | s01 |
| staging | doctor-explains (doctor + student, point at drain) | s03 |
| staging | students-from-anatomy (group walks anatomy wing -> first door) | s11 |
| staging | actor: porter | s13 |
| staging | street-birth | s25 |
| staging | explorer full figure on location (H5) | s46 |
| staging | dust drifting in the window beam | s47 |
| graphic primitive | tally | s06; door-sketch tallies on the board (H1) |
| graphic primitive | ratio_compare with figure_grid | s07 |
| graphic primitive | day_labels | s10; not in the plan's primitive table, needs a home (labels family or a `label` variant) |
| graphic primitive | board_card | s27 overlay; card textures for H1-H4, s24, s31 |
| graphic primitive | map_plan | s36 |
| graphic primitive | date_stamp | s41 |
| graphic primitive | archive_mat | s05, s42, s49 |
| graphic primitive | source_card | credits on the three archive shots |

The cut lists 46 distinct `to_build` entries (grouped above); 30 of the 51 shots need some build work.

## 13. Narration lines needing visual changes

One row per v5 line id. The v6 id differs only for the lines moved by the hook change. v5 visuals are from `storyboard.json` on the v5 clock.

| v5 id | v6 id | v5 visual | v6 visual (shots) |
|---|---|---|---|
| u001 | u001 | engraving still, 5.2 s | s01, s02 |
| u002 | u002 | roofs, then the court | s03, s04 |
| u003 | u004 | street, then the doors | H1 at the board, calendar strip (s07, s08, s09) |
| u004 | dropped | court-wide glide | content moves to u003′ (s05, s06, s07) and u005′ (s09, s10) |
| u005 | u006 | court-wide glide | matched framing, doctors against midwives (s10, s11, s12) |
| u006 | dropped | court-wide glide | numbers move to u003′ (s05, s06, s07) |
| u007 | u007 | court-wide glide, then the doors | s12, s13, s14 |
| u008 | u008 | doors, then rooftops | s14 |
| u009 | u009 | rooftops | s15, s16, s17, s18 |
| u010 | u010 | 1860 portrait still, 7.5 s | s18, s19, s20 |
| u011 | u011 | desk, one held push | s21, s22 |
| u012 | u012 | ward aisle, slow move | s22, s23 |
| u013 | u013 | ward aisle, slow move | s24, s25, s26 |
| u014 | u014 | aisle, then ward bed | s26, s27, s28, s29 |
| u015 | u015 | ward door | s30 |
| u016 | u016 | wide ward, bed, door | s30, s31, s32, s33, s34 |
| u017 | u017 | door, priest, door | s34, s35 |
| u018 | u018 | bed, aisle, wide | s35, s36, s37, s38 |
| u019 | u019 | wide, bed, aisle | s38, s39, s40 |
| u020 | u020 | Kolletschka portrait still, 11.4 s | s40, s41, s42, s43, s44, s45 |
| u021 | u021 | anatomy room, table | s45, s46 |
| u022 | u022 | anatomy close, jars, table | s46 |
| u023 | u023 | ward wide | s46 |
| u024 | u024 | ward aisle move | s46 |
| u025 | u025 | ward aisle move | s46 |
| u026 | u026 | ward aisle move | s47 |
| u027 | u027 | ward aisle move | s48 |
| u028 | u028 | aisle, then bed | s48, s49 |
| u029 | u029 | bed, then generic wide | s50, s51 |

## 14. Design specs: graphics system and cut-list timing schema

Both are specs to review before any code. The graphics system is project-wide, not a Semmelweis feature.

### 14.1 Graphics: one reusable visual system for every episode

**Where it lives:** `tools/graphics/`, documented in `docs/graphics.md`. A gallery script, `tools/graphics/gallery.py`, renders every primitive with fixture data onto one contact sheet, so a change to the house look is visible at a glance.

**Tokens, not literals.** Every primitive draws from one `graphics` block in `workflow/style.json`:

- palette: ink, paper, accent, warm, cool, data-a, data-b, danger;
- type scale: display, number, label and caption, as fractions of frame height, with a mobile floor of 0.06 for labels and 0.10 for numbers;
- stroke, corner radius, safe margins, the motion curves (ease-in, ease-out, settle) and the build stagger;
- the house font, `Inter`.

An episode may override the palette only through its own `look` file, so the system stays consistent across films.

**The primitive contract.** Every primitive is a pure function that streams its frames:

```
render(spec: dict, seconds: float, canvas=(1920,1080), fps=30, tokens) -> Iterator[Frame]
frame_at(spec, t, canvas, tokens) -> Frame      # one frame, for stills, tests and the gallery
```

**Streaming and memory rule.** Frames are produced one at a time by a generator and written straight to ffmpeg's stdin (`-f rawvideo -pix_fmt rgba -s WxH -r fps -i -`). They are never collected in a list.

- *Why:* a 20 s animation at 30 fps is 600 frames, and one 1920x1080 RGBA frame is about 8.3 MB, so 600 frames held in memory would be about 5 GB. Streamed, only one frame and the static layers are held: about 20-40 MB.
- Static layers (background, mat, unchanging cards) are drawn once, cached per spec, and copied into each frame. Only what moves is redrawn.
- The sink is `tools/graphics/encode.py: stream_to_mp4(frames, out, fps, alpha)`. It writes ProRes 4444 or PNG-in-MOV for overlays that need alpha, and H.264 for opaque full-frame graphics. A failed or killed encode leaves no half-written output file: the encode writes to a temp file, then renames.
- **Tests:** `render` returns an iterator, not a list; peak memory measured with `tracemalloc` while streaming a 20 s 1080p spec stays under 200 MB; the encoded frame count equals `round(seconds x fps)`.
- The spec is validated by a JSON schema that lives in the module.
- Times inside a spec are local to the graphic, in seconds from 0. Builds are given as `{at, dur}`.
- Each primitive returns RGBA frames: full-frame primitives on an opaque background, overlays on a transparent one.

One module per family:

| Family | Primitives |
|---|---|
| Statistics and comparisons | `big_number`; `ratio_compare` (A against B, with optional 'about' and a source tag); `bar_compare`; `tally` (marks per N) |
| Figure grids | `figure_grid`: N icons, K highlighted, staggered build. Icons can be the house pixel people or generic shapes. |
| Timelines | `timeline`: a dated axis, events, a moving 'now' marker |
| Maps and route diagrams | `map_plan`: a schematic plan from rectangles and labels, routes as animated polylines with arrowheads, a required 'schematic' tag |
| Evidence boards | `board`: cards with title and optional image, pins, strings between cards, cross-out, card add and remove. Renders as a 2D overlay or exports card textures for the 3D board set. |
| Split screens | `split`: 2-4 panes, each a video source; divider, labels, synced or offset in-points |
| Archival documents and source cards | `archive_mat`: the still or document on a mat with border and paper tone, optional highlight box, credit on the mat. `source_card`: the credit line, wrapped inside its margins. The existing `card_lines` moves here. |
| Labels and annotations | `label` (text with plate); `callout` (a leader line to a point); `lower_third`; `underline` and `circle` marks; `date_stamp` |

**Tests**, one file per family: the spec schema; determinism (the same spec gives the same frames); pixel checks (the mobile type floor, contrast at least 4.5:1, nothing outside the safe margins, credits off the picture area); build timing (an element is visible at its `at` and not one frame before).

**Within this episode:** `ratio_compare` with `tally` and `figure_grid` for the hook; `map_plan` for Loop C; `board` card textures for H1-H4; `archive_mat` and `source_card` for every still; `split` is available, but the match is made in camera inside the continuous shot. `day_labels` (s10) is used by the cut but is not in the family table above and needs a home before the build.

### 14.2 Cut-list timing schema (`cutlist/1`)

**One clock.** Everything is on the film clock in seconds, measured from the first sample of the narration master (`vo/manifest.json` `startSample` / `endSample` at its sample rate). Frames are derived from it, never stored.

**Frame rule.** `frame(t) = round(t x fps)`, where fps comes from the contract (30). A shot covers the frames `[frame(start), frame(end))`. Each time is rounded once, on the film clock, not per segment, because v5 measured per-segment rounding drifting the picture 0.65 s behind the voice by the 10th minute (the `build_segments` note). The validator refuses a shot shorter than 2 frames.

**Shot entry**

```
{ id, start, end,                      # film clock, s; end exclusive
  start_anchor?, end_anchor?,          # "word:<w>@uNNN[:start|:end]" | "line:uNNN[:start|:end]" | seconds
  source: { kind: 3d|archive|graphic|black, name,
            in, out? },                # source clock, s; out defaults to in + (end - start)
  speed: 1.0,                          # source seconds per film second; not 1 only for graphics/3d, never archive
  transition_in: { type: cut|dissolve|dip|match, dur },   # centred on `start`
  overlays: [ { graphic, start, end, z, anchor? } ],       # film clock, must sit inside [start, end)
  audio: { j_cut?, l_cut? },           # lead or lag of the shot's own sound, s
  provenance, claims[], demonstrates[], loop? }
```

The proposal file also carries `mode`, `lines`, `role`, `also`, `host`, `to_build` and `note` for review; the renderers ignore them.

**Anchors and narration sync**

- Anchors resolve through the alignment: `word:<w>@u020` is the start of the first matching word in u020's `align.json`, plus the line's start on the film clock. `:end` gives the end of the word. A repeated word is addressed by occurrence, as in `word:Same@u009#2`.
- A cut on a word lands 2 frames before the word's onset (`lead_frames` = 2), so the picture leads the sound, the house rule for a cut on meaning.
- A resolved anchor that misses the alignment is an error, never a guess.
- A voice change re-resolves every anchor, so the cut list survives re-voicing.

**Transitions and overlap**

- A transition of duration `d` at a cut point `t` overlaps the outgoing and incoming shots over `[t - d/2, t + d/2)`.
- Both sources must have material there: the outgoing shot needs `out + d/2` and the incoming shot `in - d/2`. The resolver checks this against the source's length and refuses a transition that would run past either end.
- `cut`: d = 0. `dissolve`: d between 0.2 and 1.0 s. `dip`: to black, d between 0.3 and 1.2 s, half out and half in. `match`: a dissolve of d at most 0.3 s, or a hard cut, for matched framing.
- The shots themselves never overlap. Only transition windows do, so the timeline stays gap-free with each shot's `end` equal to the next shot's `start`.

**Archive timing.** For an archive shot, `end - start` is the screen time, including half of each transition. It must be at most `archive_rhythm.max_archival_shot_seconds` (6.0). The source card holds for `source_card.seconds` from the shot's start, or for the whole shot if that is shorter. A still's Ken Burns move is sized to the screen time.

**Overlay timing.** An overlay's `[start, end)` must sit inside its host shot. Builds inside the graphic run on the overlay's local clock (0 at the overlay's start). An overlay that spans a cut is two overlays, one per shot.

**Renderer lengths.** The resolver writes, for each 3D beat and graphic, `seconds = max over its shots of (out)` plus the transition handles. Shot changes inside a beat come from the storyboard's own timings, now driven by `in` points rather than per-line sums.

**Legacy.** `legacy.py` maps a `shots.json` line to one shot `[line.start, line.end)`. Its `in` is the running sum of earlier lines on the same beat, exactly as `build_segments` does today, and every transition is a `cut`. An episode with no `cut.json` assembles unchanged.

**Modules** (each pure and tested on its own): `tools/edit/cutlist.py` (schema, anchors, validation, lengths); `tools/edit/legacy.py` (adapter, with a regression test against today's assembler); `tools/graphics/` (14.1); `tools/compose/` (ffmpeg filter-graph builder: `overlay`, `xfade` for dissolves and dips, mats, split; returns arguments and does no I/O); `assemble_episode` reads `cut.json` or the adapter; composable Blender sets (a `wing` layout joining anatomy room, corridor and ward; parameterised actions such as `bell.route` and `bell.ring`; new poses and props).

**Tests** (`python/test_cutlist.py`, `test_compose.py`, `test_legacy.py`)

- Timing: anchors resolve including the 2-frame lead; a 10-minute fixture keeps zero drift against the narration clock; gaps and overlaps are refused.
- Transitions: window maths; handle checks; dissolve and dip filter graphs; frame-exact output length on a fixture (a dissolve between two coloured clips, blend measured at the midpoint).
- Audio sync: an assembled fixture with clicks on words, picture marks within +-1 frame of the clicks; J- and L-cut offsets.
- Archive: a 6.0 s shot passes and a 6.1 s shot fails, with transitions counted; the card hold; the Ken Burns move sized to screen time.
- Overlays: an overlay outside its shot is refused; the overlay clock starts at the shot.
- Legacy: the v5 Semmelweis `shots.json` and one older episode convert, and segment boundaries equal today's `build_segments` to the frame.

## 15. Validation report

# Validation report: v6 directing proposal

Projected film: 152.72 s, 51 shots (50 pictures + black tail), 21 3D beats.

| Section | Check | Result | Detail |
|---|---|---|---|
| Hook | visual contrast complete by 15.0 s | PASS | tallies fully built at 14.70 s (s06) |
| Hook | 'one in nine' heard by 18 s (measured) | PASS | ends 16.18 s |
| Hook | 'one in thirty six' heard by 22 s (measured) | PASS | ends 19.96 s |
| Hook | 'one in nine' heard by 18 s (conservative) | PASS | ends 17.18 s |
| Hook | 'one in thirty six' heard by 22 s (conservative) | PASS | ends 21.72 s |
| Loops | Loop A (air): belief, experiment, result, next question, in order | PASS | plan: s23 / belief: s24 / experiment: s25 / result: s26 / next: s27 |
| Loops | Loop B (position): belief, experiment, result, next question, in order | PASS | belief: s27,s28 / experiment: s29 / result: s30 / next: s30 |
| Loops | Loop C (fear): belief, experiment, result, next question, in order | PASS | belief: s31,s32,s33,s34,s35 / experiment: s36,s37 / result: s38 / next: s39,s40 |
| Loops | Kolletschka answers the planted clue (clue shot before the chain shot) | PASS | clue s11 at 28.166667 s; chain s46 at 118.3 s |
| Board | five host moments H1-H5 | PASS | H1, H2, H3, H4, H5 |
| Board | no two host moments share framing, interaction or purpose | PASS |  |
| Board | H5 is on location, off the board | PASS |  |
| Board | card inserts are short (<=1.5 s) and each different | PASS | card-air 1.33s, card-fear 1.33s |
| Rhythm | median shot <= 3.5 s | PASS | 2.50 s over 50 shots |
| Rhythm | share under 1.5 s >= 12% | PASS | 20% |
| Rhythm | one held MOVING shot >= 20 s | PASS | s46 23.30 s, travel wing-table -> wing-ward-bed |
| Rhythm | no other shot over 10 s (no static hold) | PASS | none |
| Rhythm | every shot at least 2 frames | PASS |  |
| Archive | akh-engraving: screen time <= 6 s (transitions included) | PASS | 2.33 s |
| Archive | akh-engraving: on the mat (credit off the picture) | PASS |  |
| Archive | akh-engraving: ledger row arch-002 public domain | PASS | Joseph and Peter Schaffer, c. 1784 (via Dorotheum) / Wikimedia Commons (public domain) |
| Archive | kolletschka-portrait: screen time <= 6 s (transitions included) | PASS | 3.50 s |
| Archive | kolletschka-portrait: on the mat (credit off the picture) | PASS |  |
| Archive | kolletschka-portrait: ledger row arch-004 public domain | PASS | Josef Kriehuber (lithograph, 1844), photographed at the Albertina / Wikimedia Commons (public domain) |
| Archive | semmelweis-portrait: screen time <= 6 s (transitions included) | PASS | 2.63 s |
| Archive | semmelweis-portrait: on the mat (credit off the picture) | PASS |  |
| Archive | semmelweis-portrait: ledger row arch-001 public domain | PASS | After Jenő Doby (engraving, 1860), scan from Benedek 1983 / Wikimedia Commons (public domain) |
| Archive | (info) unused ledger rows | PASS | arch-003 |
| Archive | the 1860 portrait is not under 'he's twenty eight' (u010) | PASS | on ['u028'] |
| Mute test | shown, not only said: two clinics side by side | PASS | s06 |
| Mute test | shown, not only said: admission on alternate days | PASS | s10 |
| Mute test | shown, not only said: who staffs each clinic | PASS | s11, s12 |
| Mute test | shown, not only said: the death difference | PASS | s06, s07 |
| Mute test | shown, not only said: street births are safer | PASS | s26 |
| Mute test | shown, not only said: position changed nothing | PASS | s30 |
| Mute test | shown, not only said: rerouting changed nothing | PASS | s38 |
| Mute test | shown, not only said: Kolletschka's cut | PASS | s44 |
| Mute test | shown, not only said: Kolletschka's death | PASS | s45 |
| Mute test | shown, not only said: same disease as the mothers | PASS | s46 |
| Mute test | shown, not only said: the chain, morgue to mother | PASS | s46 |
| Mute test | shown, not only said: the bare hands | PASS | s46 |
| Provenance | every shot tagged | PASS | 51 shots |
| Provenance | every claim id exists in research/sources.md | PASS | all known |
| Provenance | at most 2 symbolic devices | PASS | s47, s46(dip) |
| Provenance | schematics tagged schematic, data graphics tagged data | PASS | 6 graphics |
| Provenance | every claim line has a shot over it | PASS | 27 lines |
| Mobile | graphic type >= 0.06 (labels) / 0.10 (numbers) of frame height | PASS | 6 graphic specs |
| Ending | the last picture is on the hands | PASS | s50 hands-door |
| Ending | no payoff shown (no basin, chlorine or washing in the last 4 shots) | PASS |  |
| Schema | no gaps or overlaps (end == next start) | PASS | contiguous |
| Schema | cut points on whole frames | PASS | all |
| Schema | transition types and durations in range | PASS | all |
| Schema | (info) transition handles the renderers must add | PASS | s05 needs 0.15 s pre-roll in akh-engraving; s46 needs 0.40 s pre-roll in v6-19-wing |
| Schema | overlays sit inside their shot | PASS | all |
| Script | draft narration has 29 lines and matches the cut's line texts | PASS | 29 lines |
| Script | qc_script: only the pilot's expected errors (length, story payoff) | PASS | errors: ['length', 'story'] |
| Script | turns >= 1.4 a minute | PASS | 1.96 |
| Script | (info) qc_script warnings | PASS | none |
| Planning | storyboard.validate on proposed beats: no errors beyond planned new scenes/views | PASS | 21 findings, all planned builds |

**59 of 59 checks pass.**

