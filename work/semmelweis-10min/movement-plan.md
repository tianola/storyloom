# Semmelweis 3D test, beats 01-08: movement plan

Every movement has a reason in the story, and the gestures are timed on the words they carry (times
are seconds in the beat, from `word_timing.json`).
- Code: `tools/blender/models/human3d.py` (`gesture`, `reach`, `point_at`, `gaze`, `eye_aim`, `bend`,
  `pen_in_hand`, `lean`, `stride_speed`, `idle`, `blinks`) and `tools/blender/storyboard_beats.py`
  (`gestures`, `walk_to`, `look`, `apply_gaze`).
- Storyboard: the `gestures` key on each cast entry.

Everyone, all the time:
- breathing, a slow shift of weight, a face that is never quite still;
- blinks every 2.5-5.5 s, and one with each head turn;
- relaxed fingers.

Nobody shares a timing. A look starts with the eyes; the head follows a few frames later, then the
neck, then part of the shoulders. A gesture gathers before it moves (anticipation) and settles after it.

| Beat | Who | Action | Why (the words) | When |
|---|---|---|---|---|
| 01 | Narrator, at the asylum gate | Open hand toward the camera | "taken through the gate of a mental asylum" | 2.6-4.4 |
| 01 | Narrator | Hand to the chest | "The guards beat him" | 5.4-6.0 |
| 01 | Narrator | Open hand | "how does a man whose idea..." | 13.1-14.6 |
| 01 | Narrator | Hand to the chest | "cut the deaths" | 14.85-15.9 |
| 02 | Mother and midwife | Walk to the hospital gate, face it, and stop there | She has come to give birth; the midwife brings her. They walk at about 1.15 m/s. | 0-7 |
| 03 | Registrar | Bends over the register, writes with a quill in the right hand; the left hand holds the page | He enters the deaths: "their deaths were counted there" | 0.2-3.3 and 12-17.9 |
| 04 | Doctor | Lectures with open hands | "run by doctors and medical students", "an imperial decree" | 1.3-2.9, 3.3-5.0, 12.6-14.9 |
| 04 | Student | Nods | "...and medical students" | 4.7 |
| 04 | Midwife | Looks at the doctor, nods | "by midwives" | 6.9 |
| 04 | Student | Walks to the Second Clinic's door and stops there | Students come and go. | from 0 |
| 05 | Semmelweis | Hand to the chin, thinking | "no more skilful or conscientious" | 3.7-6.7 |
| 05 | Semmelweis | Points at the calendar strip | "Admissions rotate, changing every twenty four hours" | 7.3-8.9 |
| 06 | Mother who speaks | Clasps her hands | "They kneel and beg..." | 2.6-4.5 |
| 06 | Mother who speaks | Clasps her hands again | "Please." | 5.3-6.0 |
| 06 | Mother who speaks | Shakes her head | "Not the first clinic." | 6.0-6.95 |
| 06 | Mother left | Hand to her chest, worried | "...beg not to be sent to the first clinic" | 2.2-4.9 |
| 06 | Mother right | Clasped hands, then a hand to her mouth | The plea, then shock at the refusal | 2.9-4.6, 6.2-7.6 |
| 06 | The two listeners | Turn to the speaker a moment after she starts, then turn back | They listen. | 5.5-8.5 |
| 07 | Midwife | Crosses the court to the First Clinic's door and stops there | Her round. | 9-16 |
| 08 | Doctor | Rests both hands on the edge of the dissecting table, looks down at the covered body | He has come from the dissection. | 0.3-8.8 |
| 08 | Student | Looks at the body; hand to his chest | "mothers die" | 6.4-8.6 |

## Still not natural (honest)
- The arm moves by IK, but each hand keeps its rest orientation, so a palm does not always turn the
  right way (a hand on the chest can look like the back of the hand).
- The head shake and the nod are keyed head rotations; the shoulders and the face do not join in.
- In a walk the feet stay planted on average (the clip is slowed to match the travel), but there is no
  foot IK lock, so a small slide can remain. Turning on the spot is not animated: walkers start already
  facing where they go.
- Nobody kneels in beats 01-08: the mothers are framed as busts, and a kneel would take them out of
  frame. The "kneel and beg" line is carried by the clasped hands.
- The doors stay shut: nobody walks through one in these beats, and the clinic doors are one solid
  piece.
- At the registrar's wide shot the quill is small and the crosses are added only in the close-up of the
  page.
