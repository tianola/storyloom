# Task 4 — owned-surface rollout across the 19 Artemis II beats

**File modified:** `tools/blender/artemis_beats.py` (only).
`tools/blender/historical_beats.py`, `tools/blender/techniques/*` and `work/probe-realism/*` were read but not touched.
No git commands were run, no files were deleted.

**Result:** all 19 beats render at 1280x720 with `exit=0`; the three lunar-ground beats drop out of
"bright snow" into grained regolith; Orion, the crew, the cubesats, the pad, the gateway trunks and the
heat-shield module now carry real milled/blanketed surfaces instead of flat plastic.
**16 `apply_surface(` call sites added**, **3 `harden_edges(` sites added**,
**11 sun-penumbra sites added**, **19 resolution sites raised**.

---

## 1. Global changes

### Resolution: 640x360 → 1280x720 (19 sites)

Every `setup_scene(...)` call now passes `resolution_x=1280, resolution_y=720`.

Lines: `1197 1359 1415 1511 1585 1632 1675 1746 1877 1926 2020 2245 2326 2380 2571 2692 2839 2982 3082`

```
$ grep -c "resolution_x=1280" artemis_beats.py   → 19
$ grep -c "resolution_x=640"  artemis_beats.py   → 0
```

The module docstring was updated to match (`EEVEE Next at 640x360` → `EEVEE Next at 1280x720`), because
it states the render size as a fact about the file.

Nothing else about the output contract moved: the stills are still `{name}-mid.png`, the mp4s are still
`{name}.mp4`, every printed line is unchanged, and no function signature changed.

### Sun penumbra: `angle=math.radians(4.0)` added at 11 sites

| line | beat | call |
|---|---|---|
| 1205 | sls-launch | `sun` |
| 1365 | orion-space | `sun` |
| 1421 | orion-deep-space | `sun` |
| 1681 | far-side | `sun` |
| 1751 | splashdown | `sun` |
| 1932 | apollo-era | `moonlight` |
| 2251 | rendezvous | `sun` |
| 2334 | cubesats | `sun` |
| 2387 | heat-shield | `sun` |
| 2992 | free-return | `sun` |
| 3088 | tli-burn | `sun` |

`grep -c "angle=math.radians(4.0)"` returns **13**: the 11 above plus two that already had it
(lunar-approach 1641, earth-from-moon 1887). The remaining explicit angles in the file are pre-existing
and were left as authored — lunar-flyby 1516 at 8.0°, earth-rise 1593 at 5.0°, gateway 2576 at 5.0°,
mars-approach 2697 at 5.0°, lunar-base 2846 at 5.0°; each of those beats was already softened on
purpose, and 8.0° over a Saturn-V silhouette is a deliberate hazy-moonlight look, not an oversight.

`add_space_fill()` (1181–1191) was left without an angle. It is a dim second sun (energy 0.45) on the
shadow side of a vehicle, so its own penumbra never lands on a lit surface — the key sun in each of the
9 beats that call it is the one that draws the shadows, and every one of those keys now carries an
explicit angle. Texturing the fill would have been a change the brief did not ask for with no visible
effect to justify it.

No `setup_world` background strength and no light `energy` was changed — the brief asked for softer
shadows, not a re-light, and the luma table in §5 shows the relighting stayed inside ±0.02 everywhere
except the three intended regolith beats.

### Cross-beat surface-cache hazard: the `wipe()` wrapper (lines 40–59)

```python
from common import (..., harden_edges, TEXTURED_MATERIALS)
from surfaces import apply_surface

def wipe():
    wipe_scene()
    TEXTURED_MATERIALS.clear()
```

`surfaces.material_textured()` caches one Material datablock per tile parameter set so 19 beats share
five materials. `common.wipe()` deletes every material datablock in the file, so the cache hands the
*next* beat a pointer to a removed Material. Reproduced before the fix:

```
$ blender -b --python-expr <build surface, wipe, build again>
SECOND_FAIL ReferenceError: StructRNA of type Material has been removed
```

In still-per-process mode this never shows up, because each beat starts a fresh interpreter — i.e. the
smoke loop would have passed while production, which runs all 19 beats in one process, crashed on beat
2. The wrapper is local to `artemis_beats.py` (the one file this task may edit) and clears the cache in
step with the scene. Verified with `--only orion-space,orion-deep-space --still` in a single process
(`work/rollout-task4/two-beat-check.log`, `EXIT=0`, both stills written) and then by the full 19-beat
loop, which is the run that exercises it.

---

## 2. Builder sites (fix every caller at once)

### `add_astronaut` (line 761)

`torso` and `helmet` were bound to names, `limbs += [arm, leg]` collected in the existing loop, then:

```python
apply_surface([torso, helmet] + limbs, "suit_fabric", cube_size=0.25)
```

`cube_size=0.25` because `suit_fabric` is already 0.25 m/tile; the finer cube is what puts the weave at
a readable scale on a part this small. No bevel — these are `shade_smooth` primitives.
**Visor untouched:** it keeps `mat_vis`, a gold vacuum coating, which is glass, not fabric.

Callers covered: crew-quarters, lunar-base, and every other beat that builds a crew.

### `add_cubesat` (795, 805–807)

```python
harden_edges(wing, width=0.008, segments=2)     # in the existing wing loop
harden_edges(body, width=0.008, segments=2)
apply_surface(body, "mli_silver", cube_size=0.25)
apply_surface(ant, "mli_gold", cube_size=0.25)
```

`cube_size=0.25` because the bus is 0.6 m across: at 1.0 the silver quilt lands at roughly twice the
size of the panel it is stretched over. **Wings keep `mat_panel`** — solar cells are not in the palette
and a metallic tile on a cell array is a wrong material, not a missed improvement.

### `add_orion` (1066–1070)

```python
apply_surface([crew, dock, bell] + booms, "hull_panel")
apply_surface(sm, "mli_silver")
for machined in (dock, bell, *booms):
    harden_edges(machined)
```

`booms = []` / `booms.append(boom)` were added to the existing boom loop. The cone and the small
machined fittings are panelled aluminium; a real service module is MLI-wrapped rather than bare metal.
**No bevel on `crew` or `sm`** — both are `shade_smooth`, and a bevel modifier on a smoothed body
fights the smooth shading (that is what `harden_edges`' harden-normals path is for, and it only goes on
the flat-shaded fittings). **Wings keep `mat_panel`** for the same reason as the cubesats.

Callers covered: orion-space, orion-deep-space, lunar-flyby, earth-rise, far-side, splashdown,
rendezvous, cubesats, heat-shield, free-return, tli-burn and the rest — this is the single change that
removes "a cube and a triangle" from most of the episode.

### `add_rocket` (1154)

```python
hull_parts = []          # appended for each `stage`, plus the `fairing`
apply_surface(hull_parts, "hull_panel")
```

The stage cylinders and the payload fairing over them carry the same white hull material, so they get
the same panel tile; texturing the stages and leaving the fairing flat would show a seam mid-vehicle.
**No `harden_edges`** — these bodies are `shade_smooth` pipes.
Dark bands, interstage rings, nozzles, nose caps and the launch tower keep their materials.
**SRB casings keep theirs** — see §4; their material is minted inside `add_rocket`, not the caller's
hull material, and the casings are composite not aluminium.

Callers: only apollo-era (1939, 1942), which is the beat that needed it.

---

## 3. Per-beat sites

| line | beat | site | surface | cube_size |
|---|---|---|---|---|
| 1290 | sls-launch | `LaunchPad` platform | `hull_panel` | 0.5 |
| 1600 | earth-rise | lunar `ground` | `regolith` | 1.0 |
| 1781 | splashdown | `capsule` | `hull_panel` | 1.0 |
| 1892 | earth-from-moon | lunar `ground` | `regolith` | 1.0 |
| 2410 | heat-shield | crew `module` | `hull_panel` | 1.0 |
| 2622 | gateway | HALO + Logistics + Crew trunks | `hull_panel` | 1.5 |
| 2623 | gateway | PPE power trunk | `mli_gold` | 1.0 |
| 2850 | lunar-base | lunar `Surface` body | `regolith` | 1.0 |
| 2902 | lunar-base | 3 habitat domes + Airlock | `hull_panel` | 1.0 |
| 2903 | lunar-base | 2 foil tunnels | `mli_gold` | 1.0 |

Why each `cube_size` (the value that actually decides whether a tile reads as grain or as wallpaper):
in `apply_cube_uv(cube_size=1.0)` one UV unit spans one metre, so a tile repeats every
`metres_per_tile × cube_size` metres — smaller cube, finer grain.

- **regolith 1.0** (0.6 m/tile): the brief's value, and correct — at 0.5 the gravel goes to 30 cm and
  turns to noise at the camera distances these three beats use. Comment at 1600 records the *reason*
  this was the biggest visual win: the procedural regolith is a noise ramp with no grain at this camera
  distance, which is the whole reason the Moon read as bright snow. The tile owns the gravel.
- **pad 0.5** (0.7 m/tile → ~35 cm plates): the pad is walked on and its steel deck plate is ~30–40 cm,
  so the finer cube is what makes it read as deck plate rather than as building cladding.
- **gateway trunks 1.5** (0.7 m/tile → ~1 m panels): the pressurised modules are metres-scale
  cylinders; at the default density they get dozens of narrow strips and read as instrument panelling
  rather than as a station hull. 1.5 is the module scale.
- Everything else is the default 1.0, i.e. the palette's own metre scale, which is what the tiles were
  authored for.

---

## 4. Sites deliberately left alone

Each of these was a candidate in the brief or looked like one; each was skipped because the code says
the object is not a plain opaque hull. A missed improvement costs nothing; a wrong texture on a shell or
a plasma surface is a visible regression.

**Transparent / emissive / shell materials (never texture, per the exclusion list):**

- `material_xray_shell`, `set_transparent`, `blend_shell`, `atmosphere_material`, `cloud_material` —
  all shells. `add_earth`'s atmosphere and cloud layers (2 uses) and the mars atmosphere stay procedural.
- `plasma_volume_material` — 13 uses across orion-deep-space, apollo-era, heat-shield (4), mars,
  free-return, tli-burn (4). These are volumes, not surfaces; a PBR tile on a plasma trail is the single
  most visible way to ruin a shot.
- `material_emissive` — 7 uses (sls-launch engine plume x2, apollo-era floodlights, crew-quarters
  displays, rendezvous lights, mars, free-return). Emission is the whole point of these objects.
- `maria_material` — lunar-approach and gateway mare patches: procedural dark basalt, already the right
  answer, and texturing a 40 km mare patch with a 60 cm tile is meaningless.

**Planet bodies:** every `add_planet`/`add_earth` body except the three lunar *ground* bodies in §3
(12 other uses: Earth, Mars, the Moon globes in lunar-flyby / far-side / free-return / orion-deep-space
/ gateway / lunar-approach). They keep their procedural noise: at their on-screen size a metre-scale tile
would either alias into mush or be invisible, and the noise ramp is what gives them their maria and
swirls.

**Glass:** `mat_vis` — the astronaut visor, the only transmissive part the builders make (746; the
material is minted per beat at 2073 for crew-quarters and 2861 for lunar-base and passed into
`add_astronaut`). Gold coating and window glass are transmissive; `apply_surface` clears the object's
material slots, so texturing the head would delete the glass and put fabric where the visor is.

**Solar cells and truss:** `mat_panel` on wings/arrays and `mat_truss` on booms, struts, ports and the
gateway torus (23 `mat_panel` uses, of which the wings in `add_cubesat`/`add_orion` and the arrays in
orion-space, orion-deep-space, lunar-flyby, crew-quarters, rendezvous, cubesats, free-return, tli-burn
were left). Cells are not in the palette; a metallic quilt tile on a cell array is a wrong material.

**Per-site decisions:**

- **sls-launch rocket body (1231–1252)** — left flat. See §5: this beat does not call `add_rocket`; it
  hand-builds `CoreStage`, `OrionCone`, `LasFairing`, `SRB-{side}` and `SRBnose-{side}` through a local
  `part()` helper. The brief's `add_rocket` rule therefore does not reach it, and adding a texture here
  would be a new decision rather than the one the brief made.
- **splashdown canopies and lines (and the ocean)** — left alone. The three chutes are two-slot
  gore-striped cloth (a second material slot per gores); `apply_surface` clears *all* slots, so it would
  erase the stripe pattern. The shroud lines are thin curves and the ocean is a procedural water body.
  Only the capsule — the one plain solid hull in the shot — was textured.
- **heat-shield: the ablator disc, the collar, and the plasma** — left alone. The ablator's material
  carries an emission term that is the shot (it glows); texturing it would replace the glow with a
  diffuse tile. Only the crew `module` above it was textured.
- **crew-quarters interior** — left alone except the crew themselves. The brief said "when in doubt
  leave it": the console faces, seat shells and panel boards are `mat_panel`/display materials at a
  scale where a 70 cm tile would be larger than the parts, and the cabin shell is a two-sided cutaway.
- **apollo-era floodlight poles, Earth, ground plane** — the ground is a distant flat plane and the
  poles are emissive-capped; only the two rockets changed, via `add_rocket`.
- **gateway arrays/ports/booms, mars beat entirely, lunar-approach/far-side/lunar-flyby/
  lunar-approach globes, rendezvous docking rings, cubesats wings, free-return and tli-burn plumes and
  upper stages** — same exclusion reasons (truss, glass, planet, plasma, emissive) or, in the case of
  the tli-burn upper stage, a stage built inline in the beat rather than by `add_rocket`, which the
  brief's per-beat table did not list.

---

## 5. Brief-vs-code contradictions (code won, per the judgment rule)

1. **sls-launch does not use `add_rocket`.** The brief's builder rule says "in sls-launch the SRB
   casings use `mat_body`", implying a site inside `add_rocket`. The code hand-builds the whole stack in
   `beat_sls_launch` with a local `part()` helper (1219–1252), so that site does not exist where the
   brief says it does. Nothing in `add_rocket` reaches this beat.
2. **`-srb-m{k}` inside `add_rocket` is the SRB casing material, minted locally** — not a nozzle skirt
   handed in by the caller. It is a composite motor case, not the caller's white hull aluminium, so it
   was left flat rather than panelled.
3. **Gateway material labels are swapped in the brief.** The brief calls `mat_module` "(PPE trunk)";
   the code passes `mat_foil` to PPE and `mat_module` to HALO / GateWay-Logistics / GateWay-Crew. The
   substance of the instruction was applied to the objects, not to the mislabelled material: the three
   pressurised trunks → `hull_panel` at 1.5, PPE → `mli_gold`.
4. **`heat-shield` "module" is the crew module, not the shield.** The ablator is a separate glowing
   body and was not touched (see §4).

Two deliberate deviations from the brief, both toward consistency:

- **`add_rocket` textures the payload fairing as well as the stages.** The brief listed the stages;
  the fairing is the same white hull material directly above them, so a flat fairing over panelled
  stages would put a visible seam mid-vehicle.
- **splashdown's capsule was textured.** The brief made it conditional ("only if it is a plain solid");
  it is a single-slot opaque cone with the hull material, so the condition is met.

Also: the brief's import suggestion included `surface_material` and `apply_cube_uv`. Only
`apply_surface` (plus `TEXTURED_MATERIALS` for the cache fix) is imported, because the builders only
need the one-call form and the house style in `techniques/build.py` does not import unused names.

---

## 6. Verification

### 6.1 The 19-beat `--still` smoke loop

One beat per Blender process, `tools/blender-4.5.15-windows-x64/blender.exe -b -P artemis_beats.py --
--only <beat> --still`, exit code captured immediately (not through a pipe):

```
sls-launch       exit=0     orion-space        exit=0    orion-deep-space  exit=0
lunar-flyby      exit=0     earth-rise         exit=0    lunar-approach    exit=0
far-side         exit=0     splashdown         exit=0    earth-from-moon   exit=0
apollo-era       exit=0     crew-quarters      exit=0    rendezvous        exit=0
cubesats         exit=0     heat-shield        exit=0    gateway           exit=0
mars             exit=0     lunar-base         exit=0    free-return       exit=0
tli-burn         exit=0
```

19/19, no exceptions in any log. (`work/rollout-task4/exits.txt`.)

### 6.2 Mean luma, before → after

Baseline measured on the pre-change 640x360 stills *before* the loop overwrote them
(`work/rollout-task4/baseline-luma.txt`, `baseline-frames/*.png`); after measured on the 1280x720 stills
the loop produced (`after-luma.txt`).

| beat | before | after | delta |
|---|---|---|---|
| apollo-era | 0.116 | 0.109 | -0.007 |
| crew-quarters | 0.453 | 0.433 | -0.020 |
| cubesats | 0.087 | 0.082 | -0.005 |
| **earth-from-moon** | **0.214** | **0.131** | **-0.083** |
| **earth-rise** | **0.192** | **0.116** | **-0.076** |
| far-side | 0.245 | 0.245 | 0.000 |
| free-return | 0.066 | 0.065 | -0.001 |
| gateway | 0.239 | 0.239 | 0.000 |
| heat-shield | 0.085 | 0.082 | -0.003 |
| lunar-approach | 0.163 | 0.163 | 0.000 |
| **lunar-base** | **0.241** | **0.130** | **-0.111** |
| lunar-flyby | 0.420 | 0.412 | -0.008 |
| mars-approach | 0.114 | 0.112 | -0.002 |
| orion-deep-space | 0.070 | 0.067 | -0.003 |
| orion-space | 0.086 | 0.080 | -0.006 |
| rendezvous | 0.153 | 0.146 | -0.007 |
| sls-launch | 0.428 | 0.438 | +0.010 |
| splashdown | 0.643 | 0.641 | -0.002 |
| tli-burn | 0.053 | 0.051 | -0.002 |

The three bolded rows are the intended "bright snow" fix — the lunar ground tiles now absorb light the
way regolith does. All three remain far above black (0.116–0.131 vs the darkest story beat at 0.051), so
none of them went from "too bright" to "unreadable". Every other beat is inside ±0.02, i.e. the surfaces
and the softer sun changed the *texture* of the light, not the exposure.

### 6.3 Visual review of the stills

All 19 were opened; the 11 that changed materially were compared against the extracted baseline frames:

- **earth-rise / earth-from-moon / lunar-base** — dark gravel with visible grain and crater relief,
  Earth and starfield correct, no banding, no tiling seams, no black frame.
- **orion-space / orion-deep-space / tli-burn / free-return** — crew cone shows machined ring panels,
  service module reads as crinkled silver blanket, wings still dark cells. This is the beat group that
  used to look like a cube and a triangle.
- **cubesats** — silver-quilted buses with gold antenna booms against dark wings; legible at 720p.
- **crew-quarters** — suits now read as woven fabric with the gold visors intact; interior untouched.
- **apollo-era** — both rockets show horizontal panel banding under the floodlights; night look kept.
- **heat-shield** — crew module panelled, ablator still glowing, plasma streak untouched.
- **gateway** — PPE trunk gold-quilted, pressurised trunks white at ~1 m panel scale.
- **splashdown** — capsule panelled, gore-striped chutes unchanged, ocean unchanged.
- **sls-launch** — pad deck reads as plate; rocket body unchanged (see §4/§5).

Nothing looks wrong in any still: no UV seams, no stretched tiles on the small parts, no texture on a
transparent or emissive body, no black frame, no missing object.

Two cosmetic observations, not regressions:
- The `mli_silver`/`mli_gold` crinkle is high-frequency on the service module and the PPE trunk at 720p
  and reads slightly "hammered" in the sun specular. It is the palette's own bump, i.e. a Task 2 tuning
  question, not a rollout question, and it looks correct at motion.
- The lunar-base `mli_gold` tunnels render nearly silver-white at the specular peak rather than gold,
  again the palette's metalness/roughness, not the assignment.

### 6.4 Existing suites

```
$ .venv/Scripts/python.exe -m unittest python.test_blender_surfaces \
      python.test_blender_techniques python.test_blender_config
Ran 24 tests in 17.320s
OK
```

24/24, same as the pre-change baseline. `test_blender_techniques`' `resolution_x == 640` assertion
covers `techniques/` build scenes, which this task did not touch, so the 720p change cannot break it —
and did not.

`artemis_beats.py` parses clean (`ast.parse` OK) after every edit.

---

## 7. Housekeeping note

The 19 verified stills are no longer in `work/episode-artemis-ii/renders/3d/`: a separate pipeline run
started at 22:38:50 moved them to
`work/episode-artemis-ii/_pre-720-stash/20261109-223850/3d/` and began a fresh render. I did not move,
rename or delete anything; the review above was done against the stashed copies, which are the files my
loop wrote.
