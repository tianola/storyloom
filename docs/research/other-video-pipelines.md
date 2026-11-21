# Other video-making pipelines, and what we should take from them

2026-11-18. Read for the owner's question: who else builds explainer videos in code, what do they do
better, and how. Sources were read on that date; repository READMEs change, so numbers quoted from
papers are the papers' own.

## What was looked at

| Project | What it is | Source |
|---|---|---|
| Code2Video (showlab) | Planner / Coder / Critic agents that write Manim lessons; 6x6 "visual anchor" grid; VLM critic on rendered video; TeachQuiz metric | [repo](https://github.com/showlab/Code2Video), [paper](https://arxiv.org/abs/2510.01174) |
| TheoremExplainAgent (TIGER-AI-Lab) | Planner + coding agent for 5+ minute Manim explanations; retries, RAG over Manim docs; 5-dimension LLM evaluation | [paper](https://arxiv.org/abs/2502.19400), [site](https://tiger-ai-lab.github.io/TheoremExplainAgent) |
| MoneyPrinterTurbo | Topic to short video: LLM script, stock footage by keyword, TTS, subtitles, music, FFmpeg | [repo](https://github.com/harry0703/MoneyPrinterTurbo) |
| manim-voiceover | Manim plugin: animations sized to the voiceover, bookmarks fire animations at a word (Whisper word timing) | [docs](https://voiceover.manim.community/en/stable/) |
| Motion Canvas / Revideo | TypeScript code animation with an editor where timing "events" are dragged against the voiceover | [time events](https://motioncanvas.io/docs/time-events), [Revideo](https://docs.re.video/) |
| SceneCraft, BlenderAlchemy | LLM writes Blender Python; a vision model looks at the render and revises the script | [SceneCraft](https://arxiv.org/abs/2403.01248), [BlenderAlchemy](https://arxiv.org/abs/2404.17672) |
| PySceneDetect | Cut detection; AdaptiveDetector compares each frame change with its neighbours to survive camera motion | [detectors](https://www.scenedetect.com/docs/api/detectors.html) |

None of them makes long-form 3D explainers with story gates; the closest in purpose (Code2Video,
TheoremExplainAgent) are 2D Manim lessons. Their useful parts are mechanisms, not looks.

## What we already do as well or better

- **Layout slots.** Code2Video's critic places elements on a 6x6 anchor grid with an occupancy table.
  `look.auto_tag` already chooses a free edge slot and `look.reserve` keeps the occupancy; the
  builder also checks, geometrically, that each label's anchor is on screen and cuts to a close-up
  when it is not (`storyboard_beats.build_beat_framed`).
- **Reusing unchanged work.** MoneyPrinterTurbo reuses unchanged renders; `rollout_render` renders only
  missing beats and the assembler's segment stamps rebuild only what changed.
- **Measured story rules.** None of the projects gates the script on story shape; ours is calibrated
  on six reference films (`docs/research/story-not-slides.md`).
- **Owned media.** MoneyPrinterTurbo's README tells users to delete music if copyright problems
  arise; our bed and sound design are synthesised, and archive is evidence with a licence ledger.
- **Trusting measurements over LLM judges.** TheoremExplainAgent's own study found its LLM judge
  agreed with people on visual relevance (rho 0.72) but barely on depth (0.14) or logical flow (0.16).
  That supports keeping our content gates measured, and using model judges only for layout-type questions.

## What they do better, and what to take (ranked by gain for the effort)

### 1. Real word timings instead of estimates
- **Them:** manim-voiceover fires animations at a word using Whisper word timings; MoneyPrinterTurbo
  offers a Whisper mode because TTS-boundary timing is less accurate; the PyTorch `kokoro` pipeline
  exposes per-token `start_ts`/`end_ts` for English (third-party README, not official docs).
- **Us:** `tools/captions.py` places each word by its letter count inside the voiced span ("good to a
  few tenths of a second"). Every `word:` time in the storyboard, every action pop in
  `sound_design.py` and the captions inherit that error. We use `kokoro-onnx` 0.6.1, which returns
  audio only.
- **Smallest step:** measure first. Align 20 lines with a forced aligner (torchaudio's MMS_FA is the
  documented offline option, but its API is deprecated from torchaudio 2.8; faster-whisper is the
  other) and compare with the estimates. Switch only if the median error is above about 0.15 s, by
  replacing the estimator inside `captions.py` (its outputs stay the same files).

### 2. An automatic frame critic for the faults we now find by eye
- **Them:** Code2Video's critic looks at the rendered section for overlap, text covered by animation,
  and large empty regions, then rewrites the code. Removing the critic cost 21 points of their quiz
  score. They also report that video LLMs miss brief occlusions.
- **Us:** the faults found in the last two reviews were all found by hand: text cut at the frame edge
  ("Why does my c..."), near-black frames with one small object, and a cat sprite stuck on the face of a rack.
- **Smallest step:** stay geometric, since we know the scene. Extend the existing FRAMING report to
  (a) project each text object's bounding box and flag any that leave the frame, and (b) score each
  review still for emptiness (share of near-black pixels and the area of the brightest object).
  A vision model can come later for what geometry cannot see.

### 3. Measure our own cut rhythm from the edit we know
- **Them:** PySceneDetect's AdaptiveDetector compares a frame change with its neighbours so a camera
  move is not a cut.
- **Us:** QC finds cuts with ffmpeg `scdet` at threshold 10. On our dark master that found 33 of 47 real
  cuts. The references were measured the same way, so the gate is consistent, but the reading is
  noisy, and we already know every cut exactly (`sound_design.plan_events`).
- **Smallest step:** in `qc_episode.check_cut_rhythm`, also compute the rhythm from the known cut
  list and report how many of the known cuts the detector found. Keep the gate on the detector, for
  comparability with the references, and warn when its recall drops below about 70%.

### 4. Music that ducks under the voice
- **Them:** editors duck music automatically under dialogue (DaVinci Resolve, Audition); FFmpeg has
  `sidechaincompress` for it.
- **Us:** the bed sits at a fixed loudness 9 LU under the voice (`music_bed.mix_under`), so it cannot
  rise in pauses, and the reversal drop is the only movement.
- **Smallest step:** feed the narration as the side-chain of the bed in `mix_under`, and lift the bed's
  base level by the amount the compressor takes off under speech. The existing `music_floor_lift_min_db`
  check measures whether the gaps got louder. Give the synthesised effects a short synthetic room
  reverb (a numpy convolution), so they sit in a space instead of on top of it.

### 5. Repair only what failed when an LLM plans the storyboard
- **Them:** Code2Video's ScopeRefine fixes the failing line, then the block, and only then regenerates
  the section. Against full retries it costs 2.8x less time and 1.6x fewer tokens.
  TheoremExplainAgent retries up to 5 times and found that hallucinated API calls are the main failure.
- **Us:** `plan_storyboard.plan` sends the whole board back with all errors; the 7B local trial failed
  after 2 repairs with invented actions and anchors.
- **Smallest step:** when `problems()` names beats, ask again only for those beats and keep the valid
  ones. The catalog digest in the prompt already plays the role of their documentation retrieval.

### 6. Test whether the film teaches (later)
- **Them:** TeachQuiz asks a model ten questions about a topic first with the topic blocked, then
  after watching the video. The score is the gain.
- **Us:** nothing measures whether a viewer learns the mechanism.
- **Smallest step:** generate questions from `research/sources.md` claims. Ask a model with the
  script plus review stills against a model with neither, and report the gain per chapter. It is
  advice, not a gate, until it is calibrated.

### 7. Editable timing events (optional)
- **Them:** Motion Canvas puts each `waitUntil` event on a timeline that a person drags against the
  voiceover. Moving one shifts the later ones.
- **Us:** times live in `storyboard.json` as fractions or `word:` marks.
- **Possible step:** the TypeScript studio could show a beat's waveform with its `at` marks and write
  back `word:` or seconds. This is worth doing only if hand-tuning timing becomes routine.

## Not worth taking

- **Stock footage by keyword (MoneyPrinterTurbo).** It is exactly the "random archive" the owner
  rejected; our archive must depict what the line says.
- **LLM-written scene code at render time (SceneCraft, Code2Video's Coder).** Hand-built scenes with a
  data storyboard keep physics accurate and renders reproducible. The model plans; it does not draw.
- **Word-by-word pop subtitles.** They are a short-form convention, not a long-form one.
