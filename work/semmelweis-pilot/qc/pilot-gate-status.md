# Semmelweis pilot: gate status (2026-11-21, v4 with Poly Haven assets)

**Master:** `semmelweis-pilot.mp4`, 116.0 s, 1080p, 173.6 MB.

**Voices** (all ElevenLabs v3):
- explorer/narrator: the user's own clone;
- Semmelweis: Lajos;
- mother: Ana.

**New in v4:**
- **Assets:** CC0 Poly Haven textures (plaster, cobbles, brick, planks, roof tiles), HDRI light, and props in the vienna, asylum and ward scenes (`workflow/assets.json`, `tools/blender/models/assets.py`).
- **Camera:** travels are governed to the pan limit. A too-fast travel lands short instead of rushing (`camera_plan.govern_travel`).
- **Cuts:** faster cutaways in beats 01, 05 and 06 to meet the cut-rhythm gate.

## Script gate (`qc/script-qc.json`): 2 errors, both expected for a pilot

| Gate | Result | Why it is expected |
|---|---|---|
| `length` | about 131 s against 600-900 s | The pilot is a short sample by the user's decision. |
| `story` payoff | no payoff line | The pilot ends on the open question. The answer, chlorine washing, belongs to the full film. |

**Warnings:** three chapters run under 45 s. This also follows from the pilot's length.

## Episode QC (`qc/qc-report.json`): PASS, 0 errors, 2 warnings

**Warnings, both deliberate:**
- `slow_shot` beat-01 u003: the slow drift during the whispered thought.
- `slow_shot` beat-05 u017: the slow drift in the ward.

**Fixed in this pass:**
- The cut-rhythm failure (median 4.1 s, 5% short shots) is gone after the cutaways.
- `empty_shot` 87.3 s: the second `at:bell` cutaway in beat-05 framed a bare wall after the altar boy had moved on. It is now a `ward-bed` lock on the students crowding the bed.
- `empty_shot` 13.1 s: the old v3 black `bars` shot no longer fires.

## Notes

- **Render interruption:** the full run was killed at beat-07 frame 80, when the session was interrupted at 22:22. Blender and its watcher stopped together, with no error in the log. Beat-07 was re-rendered alone with `--beat beat-07`. The partial file is in `renders/partial/`.
- **Earlier outputs:** the v3 render without assets is in `renders/3d-v3-noassets/` and `renders/semmelweis-pilot-v3-noassets.mp4`.
- **For the next pass:**
  - The cell window in beat-01 blows out to white under the new HDRI light.
  - The Kenney and Quaternius packs (`docs/research/asset-packs-catalog.md`) are not wired in yet.
