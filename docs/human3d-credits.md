# 3D people: asset credits

**Project rule: free only.** Every tool, asset and service this project uses must be free. Free means
open-source software (Blender, MPFB2, ffmpeg), assets under CC0 or CC-BY, open model weights, and free
tiers that need no payment. CC-BY assets are credited in the film's end credits. Nothing paid goes in:
no paid assets, no paid credits, no paid cloud.

## Fabric detail on the clothes (added 2026-11-27)
These three Poly Haven textures are CC0 1.0 (https://polyhaven.com/license): free for any use, no credit
required. `tools/fetch_assets.py` fetches them through workflow/assets.json. They are used as detail
normal maps under the garment creases in `human3d._cloth_wrinkles`.

| Texture | Used for |
|---|---|
| `caban` | wool coats |
| `poly_wool_herringbone` | suits, jackets, trousers |
| `rough_linen` | blouses, aprons, dresses, skirts, bonnets |

## Eyes
The irises use the MakeHuman eye textures (CC0, MakeHuman system assets) in place of MPFB's procedural
eye group, which does not build in Blender 4.5.

## Other free sources checked
- ambientCG: all CC0.
- BlenderKit: its free items are royalty-free, but the licence differs per item and an account is
  needed. Not used yet; each item would be checked before use.
- Poly Haven has no CC0 hair or skin textures. The skins stay MakeHuman's own (CC0).

The dressed 3D people of tools/blender/human3d_mpfb.py are built with
[MPFB2](https://static.makehumancommunity.org/mpfb.html) (MakeHuman for Blender, GPL code; the characters it
makes are not covered by the GPL) from MakeHuman assets. None of the assets are stored in this repository:
`python tools/human3d_assets.py --dest <dir>` downloads them.

- MakeHuman system assets (base mesh, targets, skins, eyes, eyebrows, eyelashes, teeth, short hair styles):
  CC0, makehumancommunity.org.
- Community asset packs from the MakeHuman asset repository, as listed below. CC-BY 4.0 assets must be
  credited in the film's end credits, for example: "3D clothing by Elvaerwyn, punkduck and grinsegold
  (MakeHuman community, CC-BY 4.0)".

| Asset | Author | Licence | Pack |
|---|---|---|---|
| elvs_dirty_lil_maid_bonnet | Elvaerwyn | CC-BY 4.0 | `hats03` |
| elvs_ladies_apron | Elvaerwyn | CC-BY 4.0 | `dress02` |
| elvs_male_shirt_tie_tucked1 | Elvaerwyn | CC-BY 4.0 | `shirts02` |
| elvs_reverse_french_braid_bun | Elvaerwyn | CC0 | `hair01` |
| elvs_ruffle_sleeve_peasant_blouse_1 | Elvaerwyn | CC-BY 4.0 | `shirts03` |
| grinsegold_beard_sigmund_wip | grinsegold | CC0 | `bodyparts05` |
| grinsegold_full_beard | grinsegold | CC-BY 4.0 | `bodyparts06` |
| punkduck_medieval_dress | punkduck | CC-BY 4.0 | `dress03` |
| punkduck_winter_coat | punkduck | CC-BY 4.0 | `dress03` |
| rehmanpolanski_hair_bun_brown | RehmanPolanski | CC0 | `hair01` |
| toigo_ankle_boots_female | MargaretToigo | CC0 | `shoes01` |
| toigo_ankle_boots_male | MargaretToigo | CC0 | `shoes01` |
| toigo_long_full_skirt | MargaretToigo | CC0 | `skirts01` |
| toigo_male_suit_tie_and_jacket | MargaretToigo | CC0 | `suits01` |
| toigo_suit_with_jacket_and_bowtie | MargaretToigo | CC0 | `suits01` |
| toigo_wool_pants | MargaretToigo | CC0 | `pants01` |
| wdg_scruffy_beard | WDG | CC0 | `bodyparts05` |
