# Semmelweis pilot: gate status (2026-11-21)

**Master:** `semmelweis-pilot.mp4`, 99.7 s, 1080p.

**Voices:**
- explorer/narrator: the user's own clone;
- Semmelweis: Lajos;
- mother: Ana.

All three are ElevenLabs v3.

## Script gate (`qc/script-qc.json`): 2 errors, both expected for a pilot

| Gate | Result | Why it is expected |
|---|---|---|
| `length` | about 98 s against 600-900 s | The pilot is a 60-90 s sample by the user's decision. |
| `story` payoff | no payoff line | The pilot ends on the open question ("What are they carrying?"). The answer, chlorine washing, belongs to the full film. |

**Warnings:**
- Two chapters (1865 and Vienna 1846) run under 45 s. This also follows from the pilot's length.

**Passing:**
- hook (shock, with a cited claim);
- gap;
- guess (u004) and reversal (u014);
- turns and questions;
- named people (2);
- every line sourced (c1-c15);
- every character line has a dramatisation entry.

## Episode QC (`qc/qc-report.json`): PASS, 0 errors, 2 warnings

- **`empty_shot` at 13.1 s:** the `bars` shot in the night cell (beat-01) is almost black. It is real and worth fixing: light the bars or the moonlight patch, or cut the shot.
- **`slow_shot` beat-01 u003:** the slow drift during the whispered thought is deliberate.

## Notes

- **Archive:** `episode.json` still enables archive, but the pilot has no archive shots. No placeholder media is used. The archive-share gate did not fire on this run.
- **Loudness:** the narration measures -20.2 LUFS before finishing, and the master passes the loudness gate.
- **Re-rendered beats:** beats 01-03 were re-rendered after a stale Blender from the stopped run wrote them with the old timing. The old files are in `renders/3d-old-voices/`.
