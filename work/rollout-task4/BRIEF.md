# Task 4 brief — roll owned surfaces, bevels and 720p across the 19 Artemis II beats

Repo: `F:\AI-PROJECTS\longform-explainer` (NOT a git repository — never run git here).
Single file to modify: `tools/blender/artemis_beats.py` (~3176 lines). Do not touch
`tools/blender/historical_beats.py`, `tools/blender/techniques/*`, or `work/probe-realism/*`.

## What already exists and is verified GREEN (use it, do not reinvent it)

`tools/blender/techniques/surfaces.py`:

```python
SURFACES = {"regolith", "hull_panel", "mli_gold", "mli_silver", "suit_fabric"}
surface_material(key)                      # -> cached bpy.types.Material
apply_surface(obj_or_objs, key, cube_size=1.0)   # cube-projects UVs + assigns the material
```

`tools/blender/techniques/common.py`:

```python
apply_cube_uv(objs, cube_size=1.0)   # handles hidden objects, restores visibility
harden_edges(ob, width=0.010, segments=3, angle_deg=40.0)   # bevel modifier, harden normals
material_textured(name, tile, *, metres_per_tile, metallic, roughness, bump, tint,
                  saturate, bump_distance)                   # the layer under surface_material
```

`artemis_beats.py` already puts `techniques/` on `sys.path` (line 37) and imports from
`common`. Add to the existing import block / near it:

```python
from surfaces import apply_surface, surface_material
from common import apply_cube_uv, harden_edges
```

## The semantics you must respect

- `metres_per_tile` in the palette is world scale because `apply_cube_uv(cube_size=1.0)`
  makes one UV unit equal one metre. To get finer grain on a small object, pass a smaller
  `cube_size` to `apply_surface` (e.g. `cube_size=0.25` on a 0.6 m CubeSat bus). To get
  coarser grain on a huge body, pass a larger one. Never edit the palette for one beat.
- Cube-project BEFORE any parent scale is animated. All the builders here model parts at
  the origin and parent them to an unscaled empty, so applying inside the builder is safe.
- `apply_surface` clears the object's material slots. On any object with more than one
  slot, do not use it — pick the parts that are single-slot, or apply to a list of parts.
- Textured surfaces go on **solid hardware and ground only**. Never on:
  `material_emissive`, `material_xray_shell`, `set_transparent`, `blend_shell`,
  `plasma_material`, `plasma_volume_material`, `atmosphere_material`, `cloud_material`,
  `maria_material`, `earth_material`, `moon_material`, `mars_material`, sky domes,
  starfields, ocean, window/visor glass, labels, and anything with Alpha < 1.0.
  Planet bodies keep their procedural noise surfaces — except the three lunar *ground*
  bodies listed below.
- Keep every function signature, every printed line, every output filename identical.
  The assembler reads `{name}.mp4` and `{name}-mid.png`; it must not notice this change.

## Changes to make

### 1. Resolution — all 19 beats
`setup_scene(fps=30, frame_end=SHOT_FRAMES, resolution_x=640, resolution_y=360)`
→ `resolution_x=1280, resolution_y=720`. There are exactly 19 occurrences of
`resolution_x=640`; after the change `grep -c resolution_x=640` must be 0 and
`grep -c resolution_x=1280` must be 19.

### 2. Sun penumbra — every beat with a hard sun
Blender's default sun angle is 0.526°, which throws hard-edged black silhouettes.
Add `, angle=math.radians(4.0)` to these `add_sun_light(...)` calls, which currently
pass no angle (line numbers as of writing): 1154 sls-launch, 1310 orion-space,
1365 orion-deep-space, 1621 far-side, 1690 splashdown, 1867 apollo-era `moonlight`,
2185 rendezvous, 2267 cubesats, 2319 heat-shield, 2900 free-return, 2995 tli-burn.
Leave the calls that already pass an angle (8.0/5.0/4.0°) alone, and leave
`add_space_fill()` alone — a dim fill wants its default hard disc, it only lifts a
dark face and its shadow is not visible.
Do NOT change any `setup_world(...)` strength: production already runs 0.25–1.0, and
lowering the interior/pad beats would darken the shadows, which is the opposite of the
finding the probe made.

### 3. The shared builders (one edit each, covers many beats)

**`add_orion(prefix, location, mat_hull, mat_metal, mat_panel)`** (~line 977).
After all parts exist and before/after parenting to the rig (either is fine), apply:
- `crew` (the cone) and `dock`, `bell`, both `boom`s → `hull_panel`
- `sm` (the service module cylinder) → `mli_silver`  (a real Orion SM is blanket-wrapped)
- the two `wing`s → leave on `mat_panel` (solar cells are not in the palette)
Also `harden_edges(dock)`, `harden_edges(bell)`, `harden_edges(boom)` — small machined
parts; do not bevel the crew cone or the SM (they are already shade-smoothed cones and
cylinders; a bevel on a smoothed body fights the smooth shading).
The `mat_hull`/`mat_metal` arguments become unused for the parts you re-surface; keep the
parameters (callers still pass them) and pass `mat_panel` to the wings as before.

**`add_astronaut(prefix, location, mat_suit, mat_vis)`** (~line 705).
This is the fix for "the crew read as white clipart dummies".
- torso, helmet, both arms, both legs → `apply_surface(..., "suit_fabric", cube_size=0.25)`
  (the suit tile is 0.25 m/tile already, so a *body-sized* figure needs the finer cube_size
  only if the part is smaller than ~1 m — use 0.25 and check the still).
- `visor` → leave on `mat_vis`.
- add `harden_edges` to nothing here; instead give the torso a subdivision-free smoother:
  leave the geometry alone. Do not add modifiers to the suited figure.

**`add_cubesat(location, index)`** (~line 745).
- `body` (0.6 × 0.42 × 0.42) → `mli_silver` with `cube_size=0.25`
- `ant` → `mli_gold` with `cube_size=0.25`
- `wing`s → leave on `mat_panel`
- `harden_edges(body, width=0.008, segments=2)` and the same on each wing.

**`add_rocket(prefix, location, stages, radius, srbs, tower, mat_dark)`** (~line 1030).
- each `stage` cylinder → `hull_panel` (they ARE the white hull); keep `shade_smooth`.
  `harden_edges` on stage cylinders only if the stage carries flat panels — skip it, the
  smooth-shaded pipe already reads correctly.
- `band`s, `nozzle`s (`mat_dark`) and SRBs → SRB cases: `mat_body` is passed by the
  caller per stage, so SRBs stay as they are unless the beat's SRB material is a plain
  `material_principled` white — in sls-launch the SRB casings use `mat_body`; re-surface
  those SRB cylinders with `hull_panel` too, but leave `-srb-m{k}` nozzle skirts alone.

### 4. Per-beat sites (only these; everything else stays as-is)

| Beat | Site | Change |
| --- | --- | --- |
| sls-launch | `mat_pad` "pad" (~1224) launch pad deck | `apply_surface(pad_obj, "hull_panel", cube_size=0.5)` — concrete/steel deck reads as machined panel; do NOT touch "shoulder", "scorched", "steam", "truss", the tower |
| orion-space / orion-deep-space / lunar-flyby / rendezvous / cubesats / free-return / tli-burn / mars | only via `add_orion` | no extra edits |
| earth-rise (1541) | `ground = add_planet("LunarGround", 40.0, ... regolith_material(...), segments=512, rings=256)` | keep the `add_planet` call, then `apply_surface(ground, "regolith", cube_size=1.0)` — this is the fix for "the Moon reads as bright snow" |
| earth-from-moon (1827) | same pattern, radius 60.0 | same |
| lunar-base (2767) | `surface = add_planet("Surface", 42.0, ... regolith_material(...))` | same |
| lunar-base | `mat_habitat` (~2774) and `mat_foil` (~2775) | habitat → `hull_panel`; foil → `mli_gold`; `mat_solar`, `mat_truss`, `mat_vis`, `mat_suit` per the builder rules above (`mat_suit` flows into `add_astronaut`, which now handles it) |
| apollo-era | `mat_white` / `mat_cream` rocket hulls (~1869-1870) | these are passed into `add_rocket` as stages, so they are covered there — no separate edit unless the beat builds a hull outside `add_rocket` |
| heat-shield (2338) | `module` cylinder (ROCKET_WHITE) | `hull_panel`; the `shield` ablator (2324), `collar` (2344) and every plasma volume stay untouched |
| crew-quarters (1976) | `mat_hull` "capsule-int" cabin interior | leave as-is if the object is the x-ray/cutaway shell; re-surface only the interior *frame/locker/seat-panel* solid boxes with `hull_panel` and `cube_size=0.4` if and only if they are plain single-slot `material_principled` solids — when in doubt leave it, the suit fix is what this beat needs |
| gateway (2519-2522) | `mat_module` (PPE trunk), `mat_foil` | module → `hull_panel` with `cube_size=1.5` (it is a large cylinder), foil → `mli_gold`; `mat_solar`, `mat_truss` untouched |
| splashdown (1692) | `mat_capsule` "capsule" | leave: the capsule there is re-surfaced only if it is a plain solid; parachutes (`chute*`), lines, ocean stay untouched |

Where the table says "if and only if" / "when in doubt leave it", leaving it is the
correct answer — a wrong texture on a shell is a regression, a missing texture is only a
missed improvement.

### 5. Comment discipline
One short comment where the WHY is non-obvious (why a part keeps its procedural surface,
why a `cube_size` is not 1.0). No banner comments, no per-line narration, no "CHANGED"
markers.

## Acceptance — run these and paste the real output into your report

```bash
cd /f/AI-PROJECTS/longform-explainer
grep -c "resolution_x=640" tools/blender/artemis_beats.py   # 0
grep -c "resolution_x=1280" tools/blender/artemis_beats.py  # 19
grep -c "apply_surface(" tools/blender/artemis_beats.py
for b in sls-launch orion-space orion-deep-space lunar-flyby earth-rise lunar-approach \
         far-side splashdown earth-from-moon apollo-era crew-quarters rendezvous \
         cubesats heat-shield gateway mars lunar-base free-return tli-burn; do
  tools/blender-4.5.15-windows-x64/blender.exe -b -P tools/blender/artemis_beats.py \
      -- --only "$b" --still > "work/episode-artemis-ii/qc/rollout-$b.log" 2>&1
  echo "$b exit=$?"
done
```

All 19 must be `exit=0`. Then check every produced still is not black and not a
regression, by reporting the mean pixel value:

```bash
.venv/Scripts/python.exe -c "
from PIL import Image; import glob, statistics
for f in sorted(glob.glob('work/episode-artemis-ii/renders/3d/*-mid.png')):
    im = Image.open(f).convert('L'); px = list(im.getdata())[::37]
    print(f'{statistics.mean(px)/255:.3f}  {f}')
"
```

Report: the exit codes, the mean-luma table, `grep -n "apply_surface" tools/blender/artemis_beats.py`,
every place you decided to leave a material alone, and any beat whose still looks black,
empty or obviously wrong compared to the previous one (they exist in the same folder
before you start — look at them first if you want a baseline).
Do not render the full animation. Do not delete anything. Do not run git.
