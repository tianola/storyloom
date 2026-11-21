# Online skills and guides for long-form story-driven scripts

Research date: 2026-11-21. Read-only; pages were read via search and fetch, nothing installed. Several pages (Medium, podwise, recapio, skillsmp) refused fetch or returned empty summaries, so some digests rest on search snippets and are marked "secondhand".

Headline finding: the packaged "YouTube script" skills are almost all generic retention/SEO templates (hook, CTA, pattern interrupt every N seconds). None targets documentary narration with dramatised characters. The most useful material for this project comes from craft sources (but/therefore, Veritasium misconception-first, Kurzgesagt process, Johnny Harris promise/payoff), not from the skill packs.

## Candidates

### 1. mohitagw15856/pm-claude-skills : youtube-script-writer
- URL: https://raw.githubusercontent.com/mohitagw15856/pm-claude-skills/main/skills/youtube-script-writer/SKILL.md (listing says MIT, ~1.2k stars; the SKILL.md itself states no licence)
- What: retention-focused SKILL.md for explainers, video essays, talking heads.
- Rules:
  - Fixed arc: hook (0:00-0:30, deliver value immediately, no greeting) -> stakes/re-hook (0:30-1:00, name the problem and the "villain") -> 3-5 chapters each with a micro-payoff -> payoff at ~90-95% that fulfils the hook promise -> seamless bridge to the next video, never signal the end.
  - Always produce 3 hook variants (contrarian, story, pattern-interrupt) with visual direction plus spoken line.
  - Two-column script table: video cues vs audio cues.
  - Visual change every 4-8 s (pattern interrupt); visual direction at least every 10 s.
  - Quality checks: no filler opening ("welcome back"), no "in conclusion", short conversational sentences, minimal jargon.
  - Missing inputs are filled with labelled assumptions rather than blocking.
- Value for us: low-medium. Structure is a sound skeleton; the clickbait title/thumbnail/metadata parts are irrelevant.

### 2. ailabs-393/ai-labs-claude-skills : script-writer
- URL: https://claudeskills.info/skills/ailabs-393/ai-labs-claude-skills/script-writer/ (MIT, ~470 stars)
- What: preference-collecting script writer that persists preferences and past scripts in a JSON file.
- Rules/techniques:
  - Word budgets at ~150 wpm: 7-12 min = 1,050-1,800 words; 15-30 min = 2,250-4,500 words.
  - Story template: hook -> setup (characters, situation, stakes) -> problem and tension -> journey with setbacks -> climax -> resolution -> lesson.
  - Retention: teasers of what is coming, callbacks, deliberate information gaps, anticipated objections, vary sentence length, follow through on every promised payoff.
  - Bracketed production notes ([B-roll: ...], [Pause]).
- Value: low-medium. Useful word-count arithmetic (note: documentary pace is slower, see #7).

### 3. cdeistopened/skill-stack : youtube-scriptwriting
- URL: https://www.skills.sh/cdeistopened/skill-stack/youtube-scriptwriting (~30 stars; only the opening was readable, checkpoint list hidden; GitHub raw paths 404)
- What: checkpoint-gated workflow from rough ideas to script.
- Readable idea: "reality must beat expectations" (the title/thumbnail promise sets expectation; the content must exceed it).
- Value: one useful principle; rest unverified.

### 4. jscraik/Agent-Skills : youtube-hooks-scripts
- URL: https://tessl.io/registry/skills/github/jscraik/Agent-Skills/youtube-hooks-scripts/review (licence not stated)
- What: six-step workflow with a payoff check and a fail-fast check; claims must be evidence-bound.
- Useful ideas: step 1 is "identify the opening promise, viewer tension, concrete payoff"; a final payoff check verifies the ending delivers what the hook promised; claims are evidence-bound. Reviewer notes it has no concrete examples.
- Value: low as text, but the promise/tension/payoff triple is a good lint.

### 5. Kapwing "7 Claude Skills for YouTubers"
- URL: https://www.kapwing.com/resources/best-claude-skills-for-youtubers/ (zip downloads, needs vidIQ/Kapwing; not read, not downloaded)
- What: /youtube-script-researcher analyses top videos' transcripts and comments into a brief (hooks, structure, timestamped key points, recurring audience questions, content gaps); /footage-check compares recorded audio to the script line by line.
- Useful idea only: research brief of "recurring audience questions and content gaps" before writing. Mostly product marketing and packaging/upload tooling. Low value.

### 6. revfactory/harness-100 : 09-documentary-research (story-architect, narrator agents, narrative-structure skill)
- URL: https://skillsmp.com/skills/revfactory-harness-100-en-09-documentary-research-claude-skills-narrative-structure-skill-md (page returned 403; digest is from search listing only)
- What: multi-agent documentary pipeline: story-architect makes a three-act treatment and narrative arc; narrator writes script with tone and rhythm.
- Idea worth borrowing: separate roles. One pass for treatment/arc, a separate pass for narration voice. Contents unverified. Closest existing thing to documentary scripting, but could not confirm quality.

### 7. yonatangross/orchestkit : narration-scripting
- URL: https://skills.sh/yonatangross/orchestkit/narration-scripting (licence not stated)
- Principle: "Narration = Visual Support + Comprehension Timing + Emotional Arc": words should land when the viewer needs context, pacing follows cognitive load, narration supports rather than competes with the picture. A listing elsewhere gives documentary pace of about 110-130 wpm with natural pauses (secondhand).
- Value: the 110-130 wpm figure matters for word budgets (the 150 wpm in #2 is too fast for documentary).

### 8. worldwonderer/video-recap-skills (zenstory-ai) : video-script
- URL: https://www.skills.sh/worldwonderer/video-recap-skills/video-script (licence not stated, ~645 stars)
- Techniques:
  - Decide from five viewpoints in order: director, story editor, picture editor, sound/narration editor, first-time viewer.
  - Plan picture and sound together; record decisions before writing the timeline.
  - Mechanical validation script: text must fit its time window, segments sorted by time, order/count/pauses preserved; failing segments go back to the writer.
- Value: medium for process. The "text must fit its time window" gate and "first-time viewer" read-through are directly adoptable.

### 9. Trey Parker / Matt Stone "but / therefore" rule
- URL: https://perell.com/note/but-therefore-rule/ (essay; not a skill)
- Rules:
  - Between every pair of beats the link must be "but" (complication) or "therefore" (consequence), never "and then".
  - Write beats on cards, check each seam, rewrite seams that only read "and then".
  - Each scene should create a problem for the next or follow causally from the previous.
- Value: high. Cheap, checkable, and fits a "science explained through events" brief.

### 10. Veritasium / Derek Muller approach
- URLs: https://gist.ly/youtube-summarizer/the-secrets-behind-veritasiums-viral-success (auto summary, secondhand, unsourced figures); https://www.scientificamerican.com/article/how-youtube-star-derek-muller-of-veritasium-is-challenging-scientific/ (reliable but little on scripting)
- Techniques:
  - Start from the viewer's likely misconception (it must itself be true to the evidence) and dismantle it; do not open with the answer.
  - Force a prediction before a reveal; some discomfort is where learning happens (Muller's own statement via SciAm). His doctoral comparison found struggle-containing video outperformed a polished explanation (SciAm).
  - Alternate an "A plot" (story/spectacle) with a "B plot" (technical explanation); return to the A plot when the B plot gets dense.
  - Title/thumbnail pose a question rather than summarise.
  - Make the explanation the payoff of a paradox, not the opening.
- Caveat: the "doubled test scores" and view-count figures on the gist.ly page are unverified; do not repeat them.

### 11. Kurzgesagt process (official)
- URL: https://kurzgesagt.org/youtube/
- Technique digest:
  - Deep dive on books and primary papers first; consult experts; every video has a public source sheet.
  - Script is the backbone; about a dozen drafts, cutting what does not earn its place.
  - Balance facts with an engaging story; give a fresh perspective without forcing a moral.
  - Narration recorded first and sets timing; animators build scenes around the voiceover.
- Value: high as process: voice-first timing, source sheet, many cut-driven drafts.

### 12. Johnny Harris (secondhand only)
- URLs: https://castbox.fm/episode/Johnny-Harris%3A-Master-Storytelling-on-YouTube-|-How-I-Write-id5563709-id787324282 (David Perell "How I Write" episode; show notes only, could not read); Medium and recapio summaries were not retrievable.
- From search snippets: scripts are conceived visual-first; line of narration paired with a visual direction; big visual anchors in the first 30-60 s; the opening is a promise that the rest must pay off; heavy research (one video had a 188-page doc); chapter titled "Every Story is a Promise".
- Treat as hints, not verified rules.

### 13. TED-Ed / animated-explainer guidance
- URLs: https://edsurge.com/news/2018-08-16-behind-the-scenes-of-ted-ed-s-wildly-popular-youtube-channel-for-students and https://www.kqed.org/education/474416/the-student-produced-ted-ed-lesson-a-lesson-worth-sharing
- No official guideline text found. Known: 3-5 minute lessons, ~800-900 words, "simple and direct", sources are checked, scriptwriter + animator + voice actor workflow. Generic e-learning pages suggest briefing first (learning objective, audience, style, core message). Low value.

## Best ideas to adopt (prioritised, deduplicated)

1. But/therefore seam check on the beat sheet (#9). Every scene boundary must read "but" or "therefore"; list the seams in the plan and fail any "and then". Applies to both narration beats and event chains of the protagonist.
2. Misconception-first, answer-as-payoff (#10). Open each science segment on what a viewer wrongly believes, let the protagonist or a character hold that belief, then let events break it. Keep the misconception factually grounded so the hook is not itself wrong.
3. Force a prediction before each reveal (#10). A character states a guess; the event contradicts or refines it. This gives natural dialogue and a reason for the explanation.
4. Two-track A/B structure (#10): A plot = human protagonist and events; B plot = mechanism explanation. Cut back to A when B gets dense; B should be delivered as consequence of A events ("therefore").
5. Promise, payoff and lint (#1, #4, #12): write the opening promise, the tension and the exact payoff in one line each; a final check confirms the ending delivers it and that every teased loop is closed (also #2 "follow through on every payoff promised").
6. Open loops and re-hook around 0:30-1:00 (#1, #2): name stakes and the problem early, then plant a teaser for the next beat at the end of each chapter; each chapter ends with a micro-payoff plus a new question.
7. Voice-first timing (#11, #8): lock narration, then derive scene timing; validator that each line fits its time window and segments are time-ordered. Use 110-130 wpm for documentary pace (#7), not 150 (#2), for word budgets.
8. Picture-and-sound planned together; narration should not describe what is already visible (#7, #8, #12): each line carries a paired visual direction; words land when the viewer needs context.
9. Role-separated passes (#6, #8): treatment/arc pass, then narration pass, then a "first-time viewer" read-through, then a cut pass. Kurzgesagt-style many drafts (about 12) with cuts as the main edit (#11).
10. Source sheet per episode with every factual claim traceable (#11, #4); claims evidence-bound.
11. Variety of hooks: write 3 candidate cold opens (contrarian, story moment, odd visual) and pick one (#1). Useful for the protagonist's first scene.
12. Visual change cadence as a check, not a quota: visual direction at least every ~10 s (#1); only a lint, keep animation purposeful.
13. Reality beats expectation (#3): the title-level promise should be modest enough that the video clearly exceeds it.
14. Pacing variety: vary sentence length, strategic pauses, alternate energy (#2); no "in conclusion", no recap closing, end on the payoff or a bridge (#1).

## Avoid

- Clickbait packaging machinery: three curiosity-gap titles, thumbnail scoring, SEO metadata, tags (#1, #5). Irrelevant and encourages overpromising.
- Forced pattern interrupt every 4-8 s with pop-up text, sound effects, zooms (#1): conflicts with a calm documentary look and with "little on-screen text".
- Pitching "villain and hero" framing for a topic (#1): can warp accuracy; the antagonist should be the physical problem, not a manufactured enemy.
- Shock-value hooks and contrarian-for-its-own-sake openings (#1, #2): risk factually wrong or exaggerated claims.
- Retention-via-fake-teasers: teasers that never pay off, or "you won't believe" phrasing (#2 warns against unpaid payoffs; keep that, drop the rest).
- Generic structure: statistics, social proof, CTA, "like and subscribe", end-of-video recaps (#2, #1).
- Persisting "preferences" JSON and stylistic personas (#2): pushes toward a homogeneous voice and AI-sounding output; the project should keep its own voice document.
- Unverified numbers from auto-summary sites (e.g. Veritasium test-score and view-count claims on #10's gist.ly page).
- 150 wpm word budgets for narration (#2): too fast for documentary delivery.
- Treating misconception-first as licence to open with an inaccurate claim; the misconception must be labelled as one by the narrative.

## Source reliability summary
- Reliable first-party: Kurzgesagt process page; Scientific American on Muller; Perell note on but/therefore.
- Skill packs read in full: #1, #2 (plus its script_formats reference). Partial: #3, #4, #7, #8. Not retrievable: #6 and Harris/Medium material.
- No licence text confirmed for most; only #2 (MIT) and the alterlab video-essay skill (MIT, content unread) show MIT on registry pages. Do not copy text; ideas only.
