# Staging, camera, places and acting

Source: `docs/research/staging-camera-sets.md` (rule numbers in brackets refer to its checklist). Numbers marked
there as [H] are proposals to calibrate on the pilot with the owner, not laws.

## 1 Camera

- **Motivate every move**: follow (a person walks), reveal (a place or an object comes into view), push-in (emotion
  rises, a thought, a realisation), pull-out (consequence, loneliness, scale). No motive means a **locked frame** with at most
  a barely visible breathing drift (0.1-0.3% of frame). [2, 9]
- **Speed**: no pan across scenery faster than one frame width per 7 s; a push-in changes framing 8-15% over 4-8 s;
  an orbit only to reveal an object or a diorama, at most 15° a second, never around people. [1, 4, 7]
- **Ease** every move in and out; **hold** 1-2 s after a move lands before the cut, and 0.5-1 s before it starts. [3, 6]
- **One dominant move per shot**; with billboard characters in frame, dolly or truck (camera travels) rather than pan,
  so the parallax sells the depth. [5, 8]
- **Follow shots** keep a third of the frame as look-room ahead of the subject and never let them leave. [10]
- **A drift that ignores the shot length is a bug**: the amount of movement scales with the time on screen; a 1.5 s
  insert is locked.
- In this project: `"to"` makes a travel shot (a motivated move), `"glide": "log"` the long descent. Avoid alternating
  drifts cut to cut; the builder's default drift must be small and duration-aware.

## 2 Shot grammar and coverage

- **A new place opens on an establishing wide** of 5-8 s showing the time of day and three period markers. [11]
- Then **wide, then medium, then close** as the scene goes on; a skipped step needs a reason (shock, withholding).
  A first close-up needs a wide and a medium before it. [12, 13]
- **Minimum lengths**: wide 4 s, medium 3 s, close-up 1.5 s, insert 1 s, dialogue single = the line + 0.5 s;
  reaction 1.5-3 s. In a calm scene, no more than four shots in a row under 2.5 s; the longest shot of a scene is at
  least twice its shortest. [19, 20]
- **Montage** (1.2-2.6 s cuts) belongs to the hook and to tension, nowhere else.
- **Explanation is one held, motivated move** (the references hold 35-170 s); something must change inside it.
- **Cut for emotion first**, then story, then rhythm (Murch); cut on an action or a pause, not mid-word. [21, 22]
- **Dialogue**: open on a 2-4 s two-shot, then singles or over-the-shoulder; a reaction after the key line every 3-5
  turns, 0.5-1.5 s after it lands. Keep the 180° line and screen direction; sprites face whoever they talk to. [14-18]

## 3 Who speaks when

- With the sound off, the viewer can tell who is speaking at every moment. [23]
- The speaker is **on screen at least 0.5 s before the first word** unless it is a deliberate J-cut. [24]
- Off-screen lines last under 4 s and come from someone shown in the previous shot. [25]
- About half of the speaker changes use a J-cut (sound leads by 0.3-0.8 s) or an L-cut (sound trails by 0.5-1.5 s). [26]
- **The narrator** has a fixed screen position and scale (a corner, the same side all film), a distinct look and voice;
  story characters keep their idle while he speaks. He appears at the start of a section, at a turn and at a
  question, not in every shot. [27]
- **Inner thought**: closed mouth, a slow 3-6% push-in, the background dimmed 10-20%, the voice 3-6 dB lower and
  closer, the face held 0.5-1 s after the line. [28]
- **Speaking characters** must be big enough for the lips to read (at least 18% of frame height, else lip sync is
  wasted) and the brightest, sharpest element, on a third with look-room. [29]

## 4 Composition

- Every wide has **foreground, midground and background**; a foreground object overlaps 10-20% of an edge. [30]
- A leading line or a frame within the frame (a door, a window, an arch) points at the subject. [31]
- At most **three things moving at once**; background movers at half speed and low contrast. [32]
- The horizon is never on the centre line; eyes near the upper third. [33]
- Each key pose reads as a silhouette at thumbnail size. [34]

## 5 Places (set dressing)

Write the place into `story/world.md` before it is built, then check the render against it.

- **Every room**: one dominant use, one personal object, one sign of wear, one practical light, one window or door. [35]
- **Every home or workplace**: 3-5 objects from the person's story, one tied to the theme or foreshadowing. [37]
- **Objects belong together**: the cup by the chair, the coat by the door; each placement answers "what happened
  here?". Clutter is clustered where people work; at least 30% of surfaces stay clear. [36, 38]
- **Density** per shot: wide 3-5 foreground / 8-15 midground / 5-10 background elements; medium 1-3 / 6-10 / 3-6;
  close-up the subject plus 2-4 soft items. [39]
- **Period**: each establishing shot shows three correct era markers (gas or oil lamps, dress, carts, signs, tools) and
  nothing from the era's banned list (no electric light before its time, no modern windows). [40]
- **Extras have tasks** (selling, carrying, sweeping, waiting, talking), loop 6-12 s with offsets, never cross in
  front of the speaker, 3-5 per wide. [41]
- **No identical buildings** more than twice in a frame; every house differs in roof, colour and ground-floor props,
  with 3+ props at ground level. [42]
- **Windows are lives, not rectangles**: at night 30-50% lit, a room visible behind the glass (a wall colour, a shelf,
  a lamp, a curtain, now and then a silhouette that moves), a few going dark as people go to bed. [43]

## 6 Light and colour

- **A colour script before building**: one swatch per scene, read in sequence; the colour follows the story's emotion
  (warm = human and safe, cool = isolated and threatened). [45, 48]
- **Every interior shot has a visible or implied practical light** (lamp, candle, window) that motivates the key. [44]
- Key-to-fill: day 2-3:1, domestic evening 3-4:1, dusk 4:1, night 6-8:1 with fill at least 10-15% of key; dawn 3:1 and
  15-25% less saturated. [46]
- Sprite faces stay within 10-20% of a target brightness across scenes so the lips read. [47]

## 7 Acting with sprite rigs

- **Idle is alive**: blink every 2-5 s at random, a breathing or weight shift every 4-8 s; no identical pose held
  longer than 4 s while speaking. [49]
- **Anticipation** of 2-12 frames before a big action; a reaction starts 4-12 frames after what caused it. [50]
- **No twins**: two characters never share pose and timing; offset 6-12 frames, vary pose, height and facing. [51]
- Mouth shapes hold at least 2-3 frames; closed on m/b/p (the lip sync already does this). [52]
- Characters do the task the world bible gives them; a speaker gestures on the words that matter (`acts` with
  `word:` cues), the listener reacts after the line.
