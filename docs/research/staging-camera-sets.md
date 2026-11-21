# Staging, camera and set-dressing rules for our low-poly story documentaries

Status: research brief, 2026-11-21. Web verification was limited (search snippets only, nothing downloaded). Tags: [V] = confirmed by a web source this session; [C] = standard craft practice from the named books/talks as I know them (not re-verified); [H] = heuristic number I propose for tuning, not a published standard. Calibrate [H] values against the pilot.

Verified sources: RED "Panning Speed Best Practices" (red.com/red-101/camera-panning-speed); Murch Rule of Six summaries (studiobinder.com/blog/walter-murch-rule-of-six, nofilmschool.com 2016 "6 Rules for Good Cutting"); GDC 2010 "What Happened Here? Environmental Storytelling", Worch and Smith (gdcvault.com/play/1012647); Ralph Eggleston colour scripts (awn.com "Ralph Eggleston talks Inside Out", moma.org Eggleston interview); Cinemetrics / Barry Salt on average shot length (cinemetrics.uchicago.edu); Williams, Animator's Survival Kit (anticipation, moving holds chapters). Not retrieved: Block, Brown and channel-specific (Kurzgesagt, Veritasium) details; those come from memory and are tagged [C].

---

## 1. Camera movement

Principle [C] (Block, Brown): a move needs a motivation (a subject moves, new information is revealed, emotion rises). Unmotivated drift reads as a "dumb camera". The default is a locked frame; a move is an event.

When to move:
- Follow: a character travels. Camera leads slightly (look-room ahead of the subject), never lags so the subject leaves frame.
- Reveal: move from a detail to what it implies (door handle -> person waiting). End on the new information, then hold.
- Push-in: slow dolly toward a face or object as emotion or importance rises. Never push in on neutral information.
- Pull-out: reveals context or isolation (small figure in a big empty room); use for loneliness or the end of a beat.
- Stay still: dialogue exchanges, shots with several moving elements, shots shorter than about 3 s, jokes (a locked frame lets a gag land).

Speeds:
- Pan limit [V]: RED's rule of thumb is no faster than one image width per 7 s (about 14% of width per second) at 24 fps and 180 degree shutter to avoid judder. It is not a cliff; longer lenses and no motion blur make it stricter. Use it as the hard cap for any pan across static scenery.
- Slow "felt" pan across a tableau: one frame width over 8-14 s [H].
- Following pan on a walking subject: camera speed equals subject speed; ease in 0.5-0.8 s after the subject starts, ease out 0.5-1.0 s before it stops [H].
- Slow push-in: 8-15% framing change over 4-8 s; an emotional push is 15-25% over 3-5 s [H].
- Dolly/truck through a room set: 0.3-0.6 m/s apparent at human scale (a 6 m room takes 10-20 s) [H].
- Crane/tilt-up reveal (building, sky): 3-6 s, eased both ends, for establishing or emotional release only [H].
- Orbit: avoid in story scenes; allow only for object/diorama reveals at <= 15 deg/s [H]. Orbits around people read as a game camera.
- Whip pan: 4-8 frames at 24 fps, hidden by blur, scene transitions only [C]. (RED notes a whip is the one pan too fast for the eye to register judder [V].)
- Ease: every move eases in and out (smoothstep or cubic). Linear reads mechanical. Slightly shorter ease-in than ease-out suits follows [H].
- Hold after arriving: 1.0-2.0 s before the cut or next move; longer if new information must be read (see section 2) [C][H]. Hold 0.5-1.0 s before a move starts so the composition is read first [H].
- Breathing/handheld drift: a "living" locked frame uses 0.1-0.3% of frame width at 0.05-0.15 Hz and 0.1-0.3 deg roll, below conscious notice. 0.5-1% is handheld tension. For a stylised low-poly look prefer locked or <= 1% over 10 s [H].
- One dominant move per shot; secondary components under 20% of it [H].
- Parallax: with billboard sprites, prefer camera translation (dolly) over rotation (pan); a flat pan across cards at distance reads as a cardboard slide [H].

Channel observation [C]: Kurzgesagt/Veritasium-style explainers rely mostly on locked frames, slow scale push-ins (about 2-6% over a shot), pans only to follow an object, and fast moves only as match-cut transitions. The motion lives in the content, not the camera.

---

## 2. Shot grammar and coverage

Progression [C]: establish (wide: where, when) -> medium (who, doing what) -> close-up (feeling or key detail) -> wide again to release or relocate. Break it to shock (jump to close-up) or to withhold (stay wide so a character looks small).

Dialogue coverage [C]:
- Two-shot (medium wide) to open, 2-4 s, establishes geography.
- Over-the-shoulder or medium-close singles; the speaker has about 1/3 frame of look-room.
- Close-ups reserved for the emotional line; a close-up is earned.
- Reaction shot on the key beat of a line, not every line: about one per 3-5 speaking turns, 0.5-1.5 s after the line lands [H]. For sprite characters, reactions are where acting carries story.
- Do not change angle on every line; two lines can share a shot.

180 degree rule and screen direction [C]: keep characters on the same sides of frame through a scene (A left facing right, B right facing left). Travelling characters keep direction across cuts (exit right, enter left). Crossing the axis needs a neutral shot or an in-shot cross. With billboards, flip the sprite horizontally to keep eyelines; never let a sprite face away from its addressee.

Eyelines [C]: match height (look slightly up at taller, down at shorter); eyes point to the other character's side of frame; an off-screen speaker is on the side the sprite faces.

Cutting [V Murch Rule of Six]: emotion 51%, story 23%, rhythm 10%, eye-trace 7%, 2D plane 5%, 3D space 4% (Murch's own weights as reported by summaries). Sacrifice continuity before feeling. A critique notes eye-trace matters more at fast pace.
- Cut on action: mid-gesture or mid-turn so motion carries the eye [C].
- Cutting on dialogue: cut just before a line ends (next shot starts on the last 2-6 frames) for tight pace, or after line plus reaction for weight. For narration, J-cuts (audio leads picture 0.3-1.0 s) and L-cuts (audio tails 0.5-1.5 s) avoid a slide-change feel [C][H].
- Cut on a natural pause, the "blink" point where the eye settles [C].

Shot durations: Salt's ASL is a descriptive tool and successors prefer ranges over one number [V]; per-size figures were not found, so these are [H] from reading time (about 1 s to orient plus 0.5-1 s per significant new element):
- Location-opening establishing wide: 5-8 s; other wides with much detail: 4-7 s.
- Medium shot with an action: 3-5 s.
- Dialogue single: line length + 0.5 s, minimum 2 s.
- Face reaction: 1.5-3 s; emotional beat 3-5 s.
- Insert/detail: 1-2.5 s; text insert 0.3 s per word + 1 s.
- Calm story-doc ASL 4-6 s; comic montage or tension 2-3 s. Avoid more than four consecutive shots under 2.5 s in a calm scene. Vary lengths; rhythm is variation [V Murch].

---

## 3. Who speaks when

Showing the speaker [C]:
- On-camera line: speaker visible, mouth animating, framed on a third, brightest/sharpest, facing into frame.
- Off-camera line: listener on screen as reaction; keep under 4 s and only from a speaker seen in the previous shot(s). Pan the voice 20-40% toward their side with subtle room reverb [H].
- Voice-over on B-roll: the narrator sounds different from in-scene voices (drier, closer, no room, consistent loudness). B-roll illustrates or counterpoints, never merely duplicates.
- J-cut: next speaker's voice starts 0.3-0.8 s early. L-cut: voice continues 0.5-1.5 s over the listener [H].
- Introduce each new speaker visibly, in a clean single or OTS, on their first line.

Narrator character on screen with story characters [C]:
- Fixed screen home (corner, desk, or recurring spot), fixed scale, distinct render treatment (rim light, flatter, or slightly in front of the plane), so the narrator reads as storyteller, not participant.
- Narrator speaks while story characters hold idle (moving hold); non-speaking background loops are fine.
- When the narrator enters the story world, mark the boundary with a transition (pose change, spotlight, frame shift).

Inner thoughts [C][H]:
- Voice: closer mic, no room, 3-6 dB quieter, slight high-pass and short reverb tail; mouth closed.
- Picture: 3-6% push-in over the line, character still except breathing/blink, background dimmed 10-20% or softened, gaze to middle distance or down.
- Hold the face 0.5-1.0 s after the thought, then break. Use sparingly.

Sound-off test: viewer can say who speaks from the picture alone. A speaker should be on screen at least 0.5 s before their first word unless it is a deliberate J-cut [H].

---

## 4. Staging and blocking

Composition [C] (Block's visual components; Brown):
- Subject on a third line or power point; look-room about 1/3 frame in the direction faced.
- Three depth layers in every wide: foreground framing (10-20% of frame edge, dark or soft), midground subject, background setting. Overlap and size gradient are depth cues (Block).
- Leading lines (roads, floorboards, rooflines, fences) point at the subject. Frame-in-frame (doors, windows) for interiors.
- Horizon on a third, never centred. Eyes near the upper third.

Directing the eye [C] (Block: attention follows the greatest contrast in tone, colour, size, motion, sharpness):
- The speaker is the highest-contrast element: brightest, most saturated, sharpest, or the only thing moving.
- Listeners hold quiet poses; background figures dimmed or silhouetted.
- Silhouette test: key poses read in flat black; exaggerate head/hand outlines for sprites.
- At most 3 things move at once (1 primary, 1 secondary, ambient loops) [H].
- Two equal-size, equal-brightness characters compete; give the speaker scale, light, or proximity advantage.
- One accent colour reserved for the key subject; the rest restricted palette [C].

---

## 5. Set dressing and environmental storytelling

Core idea [V]: Worch and Smith define it as staging space with props that read as a meaningful whole, with the audience inferring the story; when placing set dressing, work out how pieces connect to each other. Every object implies a past action.

Making a place lived-in and specific [C]:
- History of use: wear where hands and feet go (worn handle area, scuffed path door-to-chair, sun-faded patch, sofa dent).
- Clutter with logic: clusters around activity zones (kettle, cup rings, bread bin; desk with papers, lamp, mug) with clear voids elsewhere. Even scatter reads as noise.
- Personal objects: 3-5 per room that say who lives there (photos, a distinctive coat, an instrument, a child's drawing); at least one ties to the story theme or foreshadows.
- A deliberate mismatch (expensive item in a poor room) invites curiosity.
- Time and season: light colour and shadow angle, steam from a cup, lit lamps, breakfast vs dinner dishes, wet windows, coats on hooks, firewood.
- Period accuracy: keep an era reference set (materials, appliances, packaging, signage typefaces, vehicles, clothing silhouettes) and a banned-anachronism list (plastic bottles, LED lights, modern road markings, flat TVs in earlier eras). Show at least 3 unmistakable period markers in each establishing shot [H].

Density targets [H] (readable objects, not polygons):
- Wide/establishing: foreground 3-5 (fence, planter, bike, puddle), midground 8-15 (building details, signs, vehicles, trees, extras), background 5-10 (skyline, hills, distant buildings, lights).
- Medium: 1-3 / 6-10 / 3-6. Close-up: subject plus 2-4 soft items; nothing busy in the face plane.
- Keep 30-40% of the frame calm around the speaker.
- Every room: one dominant use, one personal marker, one wear marker, one practical light, one window or door to elsewhere.

Practical light and windows [C]:
- Every interior shot has a visible or clearly implied practical (lamp, window, candle, TV glow, stove) motivating the key.
- Windows show outside time (sky colour, a neighbour's lit window at night). Seeing lit interiors with silhouettes from outside makes a town populated.
- Exterior night: 30-50% of houses with lit windows, street lamps with halos, one dark house if the story needs it [H].

Background life [C]: extras with tasks and routes (person carrying shopping to a door, delivery cyclist, dog at a fence, shopkeeper raising a shutter); 6-12 s loops with offsets; 3-5 movers per wide at most, none crossing in front of the speaker; background motion at about half the subject's speed and low contrast [H].

Houses and towns (the pilot problem: empty, generic) [H]: each building gets a unique silhouette variation (roof pitch, chimney, porch), colour pair, at least 3 ground-level props (bins, bike, planter, mailbox, hose), one sign of occupant (curtains, washing line, car), and a district theme; the same model must not appear identically 3+ times in one shot.

---

## 6. Lighting for mood

Colour scripts [V]: Eggleston's Pixar colour scripts map colour and light to emotion across the whole story as small panels; Inside Out and Nemo mute colours for dark beats and brighten for happy ones. Make one colour/key swatch per scene before building, and review the sequence as an arc.

Key/fill and temperature [C][H]:
- Day, neutral or comic: 2:1 to 3:1, soft.
- Warm domestic evening: 3:1 to 4:1; lamp key 2700-3000 K, cool sky fill.
- Dusk: 4:1; warm practicals against cool blue ambient; sky about 30-40% of day luminance.
- Night: 6:1 to 8:1, but keep a cool fill at least 10-15% of key so faces read; practicals are the warm keys; moonlight blue-cyan.
- Dawn: low cool-to-warm gradient, long shadows, mist, about 3:1, saturation 15-25% below midday.
- Tension: higher contrast, side or low key, narrower light; relief: softer, warmer, wider.
- Warm = safe/human, cool = isolated/threat; warm interior vs cool exterior at night.
- Keep sprite face luminance within about 10-20% of a target so lip sync reads in every scene; a faint light pool or vignette around the speaker with background 15-30% darker.

---

## 7. Character acting with sprite rigs

From Williams and standard principles [V that anticipation and moving holds are core chapters; numbers C/H]:
- Anticipation: a significant action (step, turn, reach, punch line) is preceded by an opposite pose for 2-6 frames at 24 fps (small 2-3, large 6-12). Williams notes it is usually made too small and too short.
- Holds: simple pose 6-12 frames; expression change 12-24 frames; emotional beat 1-2 s [H].
- Moving hold [V]: never fully freeze; breathing, blink, 1-2 px shifts or 0.5-1 deg tilt on a 2-3 s cycle.
- Reaction timing: begins 4-12 frames after stimulus; surprise 3-5 frames; thoughtful 12-24; double take = pose, bigger pose, settle [H].
- Pose change: while speaking change something every 1.5-3 s (head tilt, brows, hand) and one clear pose per sentence or emphasis; never hold an identical pose over 4 s [H].
- Idle: blink every 2-5 s (randomised), breathing 3-4 s cycle, weight shift every 4-8 s [H].
- Twinning: avoid mirrored poses and identical timing between two characters; offset by 6-12 frames and vary pose, height, facing [C].
- Lip sync with 4-6 mouth shapes: key on stressed syllables, close on M/B/P, hold each shape at least 2-3 frames (0.08-0.12 s); drop shapes in fast speech instead of flapping [H].
- Eyes lead the head by 2-4 frames. Listeners do the smallest acting (nod, glance) on beats.

---

# Rules for our storyboard/staging skill (checkable)

Camera
1. No pan across static scenery faster than one frame-width per 7 s (about 14% width/s) unless it is a whip transition of <= 8 frames. [V RED]
2. Every camera move declares its motivation (follow / reveal / push-in / pull-out); otherwise the shot is locked. [C Block, Brown]
3. Every move eases in and out (smoothstep or cubic); no linear camera interpolation. [C]
4. A slow push-in changes framing 8-15% over 4-8 s; faster than 25% in 3 s needs an "emotional spike" tag. [H]
5. At most one dominant move per shot; secondary components under 20% of it. [H]
6. Hold 1.0-2.0 s of stillness after a move ends before the cut, and 0.5-1.0 s before it begins. [C Murch][H]
7. Orbit only for object/diorama reveals, at <= 15 deg/s; never around people. [H]
8. With billboard sprites in frame prefer dolly/truck over pan to keep parallax. [H]
9. Locked-frame drift is 0 or 0.1-0.3% at 0.05-0.15 Hz; above 1% requires a "handheld/tension" tag. [H]
10. Follow shots leave about 1/3 frame look-room ahead; camera speed matches subject speed and never lets the subject exit. [C]

Shot grammar
11. Each new location opens with an establishing wide held 5-8 s showing at least 3 place/period markers and the time of day. [C][H]
12. Within a scene sizes progress wide -> medium -> close; any skipped step carries a logged reason (shock or withhold). [C]
13. A first close-up in a scene needs at least one wide and one medium before it. [C]
14. Dialogue scenes open with a 2-4 s two-shot, then singles/OTS; a speaker is introduced in a clean single or OTS on their first line. [C]
15. Reaction shot after the key line, at least once per 3-5 speaking turns, 0.5-1.5 s after the line lands, 1.5-3 s long. [H]
16. 180 degree rule: character screen sides and facing do not swap within a scene without a neutral shot or in-shot axis cross. [C]
17. Travelling characters keep screen direction across cuts. [C]
18. Sprites face their addressee in every shot (flip horizontally; never facing away). [C]
19. Duration floors: wide 4 s, medium 3 s, close-up 1.5 s, insert 1 s, dialogue single = line + 0.5 s. [H]
20. No more than four consecutive shots under 2.5 s in a calm scene; longest:shortest shot in a scene >= 2:1. [V Murch rhythm][H]
21. Cut for emotion first; continuity breaks must carry an emotional or story reason. [V Murch Rule of Six]
22. Prefer cutting mid-action or on a pause, not at action peak or mid-word. [C Murch]

Who speaks
23. With sound off, the speaker is identifiable from the picture at every moment. [C]
24. A speaker is on screen at least 0.5 s before their first word unless flagged as a deliberate J-cut. [H]
25. Off-camera lines are under 4 s, from a speaker shown in the previous shot(s), panned 20-40% toward their side. [H]
26. At least half of the speaker changes in a narrated scene use a J-cut (0.3-0.8 s) or L-cut (0.5-1.5 s). [C][H]
27. The narrator has fixed screen position/scale, distinct render and voice treatment; story characters hold idle while the narrator speaks. [C]
28. Inner-thought lines: closed mouth, 3-6% push-in, background dimmed 10-20%, voice 3-6 dB lower with close-mic treatment, 0.5-1.0 s face hold after. [H]

Composition and attention
29. The speaker sits on a third line or power point with about 1/3 frame look-room and is the highest-contrast element (brightest/sharpest/most saturated). [C Block]
30. Every wide has foreground, midground and background layers, with a foreground overlap covering 10-20% of an edge. [C Block][H]
31. Each establishing/wide shot has a leading line or frame-in-frame element pointing at the subject. [C]
32. At most 3 distinct things move at once; background movers run at about half subject speed and low contrast. [H]
33. Horizon is never on the centre line; eyes sit near the upper third. [C]
34. Each key pose passes the silhouette test (distinct outline at thumbnail size). [C Williams]

Set dressing
35. Every room has: one dominant use, one personal marker, one wear marker, one practical light, one window/door. [C][H]
36. Clutter is clustered at activity zones; at least 30% of surfaces stay clear; no uniform scatter. [C]
37. Every home has 3-5 personal objects from the occupant's backstory, one tied to the story theme or foreshadowing. [V Worch and Smith][C]
38. Every placed prop connects to another (cup near chair, coat near door); each placement answers "what happened here?". [V Worch and Smith]
39. Density: wides 3-5 foreground / 8-15 mid / 5-10 background elements; mediums 1-3 / 6-10 / 3-6; close-ups subject + 2-4 soft items. [H]
40. Period check: each establishing shot shows at least 3 correct era markers and none from the era's banned-anachronism list. [C][H]
41. Extras have tasks and 6-12 s loops with offsets; none crosses in front of the speaker; at most 3-5 per wide. [C][H]
42. The same house/building model does not appear identically more than twice in one frame; each has roof/colour/prop variation and 3+ ground-level props. [H]
43. Windows show outside time; at night 30-50% of houses have lit windows. [H]

Lighting and colour
44. Every interior shot has a visible or clearly implied practical light that motivates the key. [C Brown]
45. A colour script (one swatch per scene) exists before build and is reviewed as a sequence with a deliberate emotional arc. [V Eggleston]
46. Key:fill targets: day 2-3:1, domestic evening 3-4:1, dusk 4:1, night 6-8:1 with fill >= 10-15% of key, dawn 3:1 with saturation 15-25% lower. [C][H]
47. Sprite face luminance stays within about 10-20% of target across scenes so lip sync reads. [H]
48. Warm practicals against cool ambient at dusk/night; warm = human/safe, cool = isolated. [C]

Acting
49. Every sprite has idle: blink every 2-5 s (randomised), breathing 3-4 s cycle, weight shift every 4-8 s; no identical pose held over 4 s while speaking. [V moving hold][H]
50. Significant actions have 2-12 frames of anticipation scaled to size; reactions begin 4-12 frames after stimulus. [C Williams][H]
51. No twinning: two characters never share pose and timing; offset >= 6-12 frames and vary pose/height/facing. [C]
52. Lip-sync mouth shapes hold >= 2-3 frames; closed on M/B/P; eyes lead head turns by 2-4 frames. [H]

---

Calibration notes
- All [H] numbers are proposals. Run the pilot with 2-3 variants of rules 1, 4, 6, 19 and 39 and let the owner pick.
- Implement as a lint over the shot list (move speed, hold times, shot lengths, speaker on screen before line, practical-light flag, per-layer object counts).
- Unresolved: per-shot-size ASL data (Cinemetrics/Salt not retrieved), Block's exact formulations (from memory), Kurzgesagt/Veritasium specifics (qualitative only).
