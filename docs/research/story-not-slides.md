# Story, not slides: what fern and Veritasium do that the ask-chatgpt cut did not

Measured 2026-11-17 after the owner rejected the ask-chatgpt cut as "a presentation" with archive that
"looks random and AI slop". Six reference films were downloaded at 720p (deleted afterwards), cut-detected,
contact-sheeted shot by shot, and their transcripts read in full. The same measurements were run on our cut.

| id | channel | film | length |
| --- | --- | --- | --- |
| -a29Ygyzc2c | fern | The $1 Billion Coca-Cola Machine | 16:45 |
| -1DvXSsWKLI | fern | Why the U.S. President Is Almost Impossible to Kill | 27:12 |
| HauQtcj7UTM | fern | The Dumb Design of Modern Cars | 25:11 |
| NiCgcUTL9_Q | Veritasium | Fiber Optics are so much cooler than I thought | 34:32 |
| kS-CGkiPetQ | Veritasium | Google Maps is unreasonably fast | 29:54 |
| QtxVdC7pBQM | Veritasium | The Ridiculous Engineering Of Jet Engines | 39:34 |

## 1 Numbers

Cut rhythm (ffmpeg scdet, threshold 10, 320 px; PySceneDetect agrees in shape):

| film | median shot | shots < 1.5 s | longest shot |
| --- | --- | --- | --- |
| fern Coca-Cola | 1.48 s | 51% | 53 s |
| fern Secret Service | 1.92 s | 39% | 66 s |
| fern cars | 1.68 s | 45% | 77 s |
| Veritasium fiber | 3.25 s | 17% | 72 s |
| Veritasium Google Maps | 3.13 s | 27% | 228 s |
| Veritasium jet engines | 2.84 s | 23% | 78 s |
| **ask-chatgpt (rejected)** | **5.53 s** | **7%** | 15.6 s (PySceneDetect) |

Script shape (same regexes on the transcripts and on our narration):

| | numeric sentences | longest numeric run | turns / min | questions / min |
| --- | --- | --- | --- | --- |
| references | 16-32% | 2-6 | 1.47-3.10 | 0.35-0.73 |
| **ask-chatgpt** | **47%** | **10** | **0.90** | **0.27** |

On-screen text: our storyboard put 30 labels, 27 HUD lines and 3 counters into about nine minutes of 3D
(6.5 a minute) plus four bar-chart beats. fern shows chapter cards, a place/date card and nothing else; a
revenue bar chart in the Coca-Cola film is on screen for 1.0 s and 2.4 s. Veritasium labels parts inside an
animation ("Aluminium", "Nickel", "Dislocation") and sets big numbers into footage ("$70 Billion" over 1960s
phone-exchange film, "10^220 possible routes" over a map, "10^200 years" over road footage).

## 2 What they do (from the frames and transcripts)

1. **A question that sounds impossible, inside 30 s.** "Runs 250 °C hotter than the melting point of its
   materials - why doesn't it melt?"; "10^220 routes, yet the phone answers in four seconds"; "A shooter is
   taking aim at the president". Ours had a good one ("the chip is waiting") but then toured facts.
2. **Every step breaks the last answer.** Problem, attempt, new problem: copper hits 65 MHz, so light; light
   needs a source, so the laser; glass loses 1000 dB/km, so... Turns come 1.5-3 times a minute.
3. **People make the decisions.** Kao, Maurer, Keck ("Whoopie" in the lab notebook); Dijkstra on a café
   terrace with his fiancée; Clint Hill at the Cellar till 2:45 a.m.; the fern team's spreadsheet analyst.
   Our film had nobody in it.
4. **Someone the viewer follows through a place.** fern's "you" in the cinema lobby goes back to the same
   machine again and again; the Secret Service film returns to the same rally stage. Veritasium follows the
   host into the lab and the factory.
5. **Archive is evidence of the named thing, never illustration of a noun.** The real Reagan shooting, the
   real Hinckley and Jodie Foster, Coca-Cola's own adverts, the real Freestyle machine, the ARMAC computer,
   a patent drawing, AT&T's logo and a quote card. Often in bursts of 0.4-1.5 s, or put inside a designed
   container (polaroids on a desk, film strips, a letter). Our 27 records were generic: rows of racks,
   cables, chillers, a keyboard, an AMD Fiji and an NVIDIA P100 standing in for chips the narration never
   named - which is what reads as random.
6. **Explanation is one held, moving shot.** The Google Maps algorithm runs 64 s and 168 s without a cut;
   the turbine-blade crystal 42 s and 35 s; the Secret Service reconstruction flies over the city for 15 s.
   Tension and the hook are fast montage. Our builder cut every 4.5 s everywhere, so both jobs got the same
   even pace - the uniform-pacing slop tell.
7. **Numbers get a picture, not a chart.** A leaky truck losing sand (dB/km); an ice cube surviving eight
   hours in an oven (turbine blade); two double-decker buses hanging off each blade (centripetal force).
8. **Different art styles in one world are fine when each has a job.** Veritasium draws its historical
   people as illustrations and shoots the present on camera; fern mixes 3D reconstruction, a mannequin
   metaphor sequence and real footage. The style changes with the kind of truth on screen.

## 3 What the pipeline now enforces

| rule | where | threshold | basis |
| --- | --- | --- | --- |
| numeric sentences | `tools/qc_script.py` | <= 32% | reference max |
| numeric run | `tools/qc_script.py` | <= 6 (warn > 4) | reference max |
| turns a minute | `tools/qc_script.py` | >= 1.4 | reference min 1.47 |
| questions a minute | `tools/qc_script.py` (warn) | >= 0.35 | reference min |
| `script/story.json`: question by 30 s, payoff in last fifth, the followed thing in 60% of chapters, >= 2 named people | `tools/qc_script.py` | | section 2 points 1-4 |
| archive is evidence: `depicts` names a specific thing and the line says it; no stock categories; no share floor | `tools/plan_shots.py`, `plan_storyboard.py --check`, `style.json archive.evidence`, `mix.min_share.archive = 0` | | point 5 |
| text on screen | `plan_storyboard.py` | <= 2 a minute of 3D | a third of the rejected cut |
| chart beats | `plan_storyboard.py` | <= 1 a film | point 7 |
| beat cutting: `travel` (default, continuous move), `montage`, `steady`; >= 1 montage, >= 40% travel | `storyboard_beats.py`, `plan_storyboard.py` | | point 6 |
| cut rhythm of the master: median <= 3.5 s, >= 12% shots under 1.5 s, a held shot >= 20 s | `tools/qc_episode.py` | | section 1 table |

Not machine-checked (left to the writer and the planner prompt): analogies for every big number, archive in
designed containers, the cast acting inside the scene rather than standing beside a diagram.
