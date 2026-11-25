# Semmelweis pilot: gate status (2026-11-22, v5: new narration and archive)

**Master:** `semmelweis-pilot.mp4`, 151.6 s, 1080p, 299 MB. Tests: 791 OK.

**Voices:** ElevenLabs v3, the same cast as v4:
- explorer/narrator: the user's own clone;
- Semmelweis: Lajos;
- mother: Ana.

## What changed in v5

### The narration was rewritten
- Built on the **guess loop**: the viewer is given a puzzle, forms a guess, then finds out it was wrong. The study and its rules are in `docs/research/narration-voice.md`.
- The user approved the English text before any voice was spent.

**How the story now runs:**
1. **The puzzle.** Two clinics in the same hospital, under the same roof and breathing the same air, take women in on alternate days. One in nine mothers dies in the first, one in thirty-six in the second.
2. **The viewer's guess.** "If you were the doctor here, what would you check first?"
3. **Semmelweis tests the likely guesses, one by one, and each fails:** the air, the delivery position, fear of the priest's bell.
4. **Kolletschka's death.**
5. **The viewer gets there a beat before the narrator:** who does the autopsies, and with which hands.
6. **The ending is an open question.**

**The voice is a blend:**
- the scenes are told in Fern's way: third person, present tense, short sentences;
- at the key moments the explorer speaks to the viewer directly, in Veritasium's way.

**Size:** 29 lines, 436 words, 151.6 s voiced.

### Real archive (Wikimedia Commons, `pd_expired`)
Each still has a Ken Burns move and a credit plate.

| Shot | Line | What it shows |
|---|---|---|
| `akh-engraving` | u001 | Vienna General Hospital, Schaffer engraving, about 1784 |
| `semmelweis-portrait` | u010 | Semmelweis, after Doby, 1860 |
| `kolletschka-portrait` | u020 | Kolletschka, Kriehuber lithograph, 1844 |

- **Rights:** the rows are in `assets/archive-licence.json`.
- **Unused:** row arch-003 (the 1861 *Aetiologie* title page) stays in the ledger, because no line in the pilot mentions the book.

## Script gate (`qc/script-qc.json`): 2 errors, both expected for a pilot

| Gate | Result | Why it is expected |
|---|---|---|
| `length` | about 185 s against 600-900 s | The pilot is a short sample by the user's decision. |
| `story` payoff | no payoff line | The pilot ends on the open question; the answer belongs to the full film. |

| Measure | v5 value |
|---|---|
| Turns | 1.62 a minute (gate at least 1.4) |
| Questions | 0.97 a minute |
| Guess line | u002 |
| Question line | u003 |
| Reversal line | u013 |
| Sourced lines | every line |

## Episode QC (`qc/qc-report.json`): PASS, 0 errors

**Advisories:**
- `archival_shot_long`: Kolletschka is held for 11.4 s and the Semmelweis portrait for 7.5 s, against a ceiling of 6 s. This is advisory until the first archival episode calibrates the ceiling. Both stills sit under full lines that name the person; cutting them mid-sentence would put the 3D scene under his name.
- `slow_shot` beat-05 u017: the slow drift while Semmelweis speaks about the bell. It is deliberate.

## Fixed along the way

### The first v5 master failed the cut-rhythm gate
- **The failure:**
  - the median shot was 4.0 s, against a limit of 3.5 s;
  - no shot was held for 20 s or more.
- **The fix:**
  - beat-02 is now a 20.5 s held glide across the clinic court;
  - beat-05 has more cutaways (11 shots);
  - beat-06 became a five-shot montage.

### Ingest of jpg stills
- **The bug:** ffmpeg `-ss` on an image decodes no frame at all, even at `-ss 0`, so every still came back empty.
- **The fix:** `archive_ingest._seek` gives no seek for an image.

### Credit plates
- **The bug:** every credit ran off the right edge ("… / Wikimedia Comm").
- **The fix:**
  - `archive_ingest.card_lines` now breaks the credit at its own phrases (" / ", then ", ") so every line stays inside both margins;
  - a pixel test checks the plate on the real font.

### HUD label
- **The bug:** the courtyard bollard covered "First" in "First Clinic: 1 in 9" during the glide. The HUD sits 1 m in front of the lens, and the bollard passes closer than that.
- **The fix:** the label moved from x 0.30 to 0.40.
- **Why not move the HUD nearer the lens:** with the camera's depth of field on, that would blur it about nine times as much.

### Framing
- **Midwife:** her walk now starts at x 9.0 instead of 3.0, so she no longer crosses the lens of the door-end ward views.
- **Explorer bust:** back on the `roofs` view.
- **Desk view:** `drift` instead of `push`.
- **beat-07:** opens on `ward-wide`.

## Earlier outputs
- v4 with the old script: `renders/3d-v4-oldscript/` and `renders/semmelweis-pilot-v4-oldscript.mp4`.
- First v5 beats and the clips with overflowing credits: `renders/partial/`.
