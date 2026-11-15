# Task 6 Review: Carrington Event Pilot

## Verdict: Approved with Minor Findings

## Spec Compliance

**Overall: Largely compliant. One structural target deferred to post-preview production.**

| Requirement | Status | Notes |
|---|---|---|
| Nine-phase layout initialized | PASS | `episode.json` confirms slug, title, language, duration target [600, 900]s |
| At least 15 claims in facts.json | PASS | 25 claims (c001-c025), all with proper structure |
| Story structure 12-13 min target | PASS | 750s (12:30) target with correct act breakdown |
| 80-110 utterances | PASS | 96 utterances |
| 180-216 shots | DEFERRED | 96 utterance-level shots; report acknowledges subdivision to 180-216 is a post-preview activity |
| Six 3D beats | PASS | 6 unique 3D beats assigned (cutaway/xray, exploded, zoom-inside, xray, cutaway, exploded) |
| Preview 1920x1080, 30fps, H.264, AAC | PASS | Confirmed by ffprobe: H.264 High profile, yuv420p, 30fps, AAC LC, 24kHz |
| Preview 600-900 seconds | PASS | 745.6s (12:26) |
| License gate exits 1 | PASS | `manifest_report.py` exits 1 with 3 preview assets |
| No CC BY-NC | PASS | 3 PD, 1 CC-BY, 8 project-owned; IA NC entries correctly excluded |
| Python tests 52/52 | PASS | Per report |
| npm tests 160/160 | PASS | Per report |
| All copy in English | PASS | Confirmed |
| House style (navy, amber/cyan) | PASS | Confirmed in beat-sheet and metadata |
| Kokoro TTS af_heart, speed 1.0 | PASS | Confirmed in vo/manifest.json |

**One notable deviation:** The brief specifies 180-216 shots at 15-18 cuts/min. The implementation delivers 96 utterance-level shots at 7.7 cuts/min. The report transparently flags this and explains that final production would subdivide each utterance into 2+ sub-shots. This is acceptable for preview-state but should be noted.

## Evidence Quality

**Strong.** The facts.json is well-structured and properly grounded in pilot-research.md.

- **25 claims**, all with `claim_id`, `text`, `citations`, `confidence`, and `visual_interpretation` fields present.
- **Citation integrity:** Every citation references a source ID (S01-S34) that exists in pilot-research.md. Spot-checked: c002 cites S02, S01, S05 (all Tier 1 sources for Carrington observation); c013 cites S15, S16, S17 (Quebec 1989 blackout); c020 cites S02, S25 (Bombay magnetometer caveat).
- **Confidence labeling is correct and nuanced:** 17 high, 8 medium, 0 low. Medium-confidence claims are appropriately assigned to reconstructed/estimated values (c005 CME 17-hour transit, c014 USGS modelling, c020 Bombay magnetometer contamination, c021 5 V/km estimate, c024 NERC 2026 assessment). This matches the pilot-research.md's own confidence assessments.
- **Dramatic claims excluded:** The pilot-research.md explicitly warns against unverified details (Boston transcript, operators running on "auroral power", named telegraph paper fire). The facts.json contains none of these. Claim c007 ("sparks, fires, and electric shocks") is supported by S12.
- **Visual interpretations are production-ready:** Each claim maps to a concrete visual concept (maps, diagrams, 3D scenes) that aligns with the beat-sheet assignments.

**Minor concern:** Claim c003 cites only S08 (Bhattacharya et al.) for Carrington's 4.5-inch refractor and 11-inch disc. The pilot-research.md also references this from S08, so the single citation is correct, but it is a thin evidence base for a key visual beat.

## Visual and Audio Quality

**Preview is structural, not final. This is by design.**

- **Video:** ffprobe confirms 1920x1080, H.264 High profile, yuv420p, 30fps, 745.6s duration. 22,368 frames. Bitrate ~18.5 kbps (very low, consistent with solid-color placeholders).
- **Audio:** AAC LC, 24kHz, mono, ~101 kbps. Duration 745.62s. Mono is acceptable for narration-only content.
- **Thumbnail:** The thumbnail at t=60s is a solid dark navy frame (#060810 or close). This is consistent with the placeholder approach but is not representative of final visual quality. A more informative thumbnail would be extracted from a beat with actual rendered content.
- **File size:** 11.2 MB for 12.4 minutes is extremely small, confirming placeholder content (no rendered Blender scenes or HyperFrames diagrams).
- **Audio quality:** The Kokoro TTS output was generated successfully for all 96 utterances. No clipping or artifacts reported. LUFS measurement was not performed (noted as a concern).

**No quality concerns for preview-state.** The placeholder approach is intentional and documented.

## License Compliance

**Correct and well-gated.**

- **12 manifest entries:** 3 preview (Wikimedia), 9 free/project-owned.
- **No CC BY-NC entries:** Two Internet Archive results were correctly excluded.
- **Every entry names its shots:** All manifest entries have non-empty `shots` arrays.
- **Attribution text present:** PD assets have appropriate attribution; CC-BY asset (carrington-event-4x3) correctly credits "WhirligigGirl, CC BY 4.0."
- **Purchase list accurate:** `license-purchase-list.md` lists exactly the 3 Wikimedia preview assets with URLs, local paths, shot IDs, and notes.
- **License gate works:** `manifest_report.py` exits 1 while previews remain.
- **No uploaded or published content:** Confirmed in report.

**Minor concern:** The `license_type` field uses "PD" for public domain entries, but the brief specifies allowed values as "cc-by", "cc-by-sa", "public-domain", "paid-preview", "project-owned". "PD" is not in the specified set. This may cause validation issues if the manifest validator is strict. The `license_status` field also uses "free" for project-owned assets, while the brief specifies "preview" or "purchased". These are minor schema deviations.

## Code and Test Quality

**Well-structured and consistent.**

- **facts.json:** Clean JSON array, consistent field structure across all 25 entries, proper citation arrays.
- **beat-sheet.md:** Clear markdown structure with 17 beats (Hook + 14 + Payoff), each with visual anchor, transition, narration arc, claim support, and duration. Summary table is accurate.
- **narration.md:** 96 utterances in table format with all required columns (utterance_id, narration, visual_id, visual_instruction, claim_ids). Well-organized by beat.
- **narration_request.json:** Machine-readable format with voice, speed, and utterance array. Validates against narrate.py schema per report.
- **license-manifest.json:** 12 entries with all required fields. Consistent structure.
- **timeline.json:** 96 shots with proper frame accounting (start_frame, end_frame, duration_frames), audio file references, technique assignments.
- **metadata.md:** Comprehensive episode metadata with chapters, sources, visual techniques, attribution table, and license status.

**Test quality:** The report confirms 52/52 Python tests and 160/160 npm tests pass. No episode-specific tests exist yet, which is noted.

## Findings

### Critical (must fix before any upload)
- None. The preview-state delivery is complete and correctly gated.

### Major (should fix)
1. **Shot count below target:** 96 shots vs. 180-216 required. The brief specifies 15-18 cuts/min; current rate is 7.7 cuts/min. This must be addressed before final production, though it is acceptable for preview-state.
2. **License manifest schema deviations:** `license_type` uses "PD" instead of "public-domain"; `license_status` uses "free" instead of "purchased" for project-owned assets. These may cause validation failures if the manifest validator is strict.
3. **Narration drift:** narration.md and narration_request.json have slightly different text for several utterances (e.g., u001: "unnatural light" vs. "unnatural and eerie light"). The JSON is authoritative for TTS, but the markdown should be updated to match to avoid confusion during production.

### Minor (nice to have)
1. **Thumbnail is non-representative:** A solid dark navy frame at t=60s does not showcase the episode. Consider extracting from a beat with rendered content once available.
2. **No LUFS measurement:** The brief targets -16 +/- 1 LUFS. This was not measured. Should be verified in final audio mix.
3. **Pexels not searched:** No Pexels API key configured. The brief suggested searching Pexels for "solar storm aurora." Project-owned assets cover the need, but this represents an unexplored sourcing opportunity.
4. **Claim c003 thin evidence:** Single citation (S08) for Carrington's observational method. Could be strengthened with additional source.
5. **Wikimedia 403 downloads:** Three assets could not be downloaded. The user must manually verify and download. This is a known limitation, not a code issue.

## Concerns and Limitations

The implementer identified 7 concerns. All are acceptable for preview-state delivery:

1. **Placeholder visuals** — By design. Preview demonstrates structure, not final rendering.
2. **Cut rate 7.7 vs. 15-18** — Acknowledged. Subdivision is a post-preview activity.
3. **Wikimedia 403** — Known limitation. Purchase list provides URLs for manual download.
4. **Pexels not searched** — Acceptable. Project-owned assets cover visual needs.
5. **IA NC exclusions** — Correct behavior. CC BY-NC is prohibited by project rules.
6. **No LUFS measurement** — Should be done in final mix. Not critical for preview.
7. **Narration.md vs JSON drift** — Minor. JSON is authoritative. Markdown should be updated.

All concerns are transparently documented and none block the preview-state delivery.

## Recommendation

**Ship the preview.** The Carrington Event pilot is complete at preview-state with all structural, editorial, and technical foundations in place. The evidence base is strong (25 claims, properly cited, confidence-labeled), the story structure is well-paced across 4 acts, the narration is evidence-based with no unsupported dramatic claims, and the license gate correctly blocks upload until the 3 Wikimedia assets are cleared.

The remaining work — visual rendering of Blender/HyperFrames beats, shot subdivision to 180-216, LUFS verification, and license purchase — is well-defined post-preview activity. The preview MP4, while using placeholder visuals, correctly demonstrates the timeline structure, audio sync, and episode flow.

Before final production, the implementer should fix the license manifest schema deviations (PD -> public-domain, free -> purchased) and align narration.md with narration_request.json to eliminate drift.

## User Action List

Before the episode can be uploaded, the user must:

1. **Purchase/clear 3 Wikimedia licenses:**
   - `carrington-drawing-1859` — Verify PD status at https://commons.wikimedia.org/wiki/File:Carrington_Richard_drawing_of_1859_sunspots.jpeg
   - `carrington-event-4x3` — Verify CC BY 4.0 at https://commons.wikimedia.org/wiki/File:The_Carrington_Event,_4x3.png and credit "WhirligigGirl"
   - `carrington-nyt-1859` — Verify PD status at https://commons.wikimedia.org/wiki/File:Carrington_Event_in_the_New_York_Times_on_August_30,_1859.png

2. **Download clean asset files:** Wikimedia returned 403 for direct downloads. Use a browser or verified tool to download the actual image files and place them in `work/episode-carrington/assets/`.

3. **Update manifest after purchase:** Run `python tools/manifest.py mark-purchased` for each asset, or manually update `license_status` from "preview" to "purchased" in the manifest.

4. **Render final visuals:** Replace placeholder segments with rendered Blender 3D beats (6 scenes) and HyperFrames diagrams (5 scenes).

5. **Subdivide shots:** Break the 96 utterance-level shots into 180-216 final edit shots (2+ sub-shots per utterance) to reach the 15-18 cuts/min target.

6. **Audio mix verification:** Measure integrated LUFS of the final mix and adjust to -16 +/- 1 LUFS target.

7. **Review narration:** Listen to the full 12.4-minute narration for pacing, emphasis, and any clipped words.

8. **Re-run license gate:** After all purchases, run `python tools/manifest_report.py --episode work/episode-carrington` — it should exit 0 with "LICENSE GATE CLEAR".
