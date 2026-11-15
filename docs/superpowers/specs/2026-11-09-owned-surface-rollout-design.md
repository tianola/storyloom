# Owned-surface rollout — design

**Status:** approved by the user in chat on 2026-11-09 — «ωραία απλά βάλε όλα τα καλύτερα
πράγματα να φαίνεται τέλειο και επαγγελματικό».
**Evidence:** `work/probe-realism/FINDINGS.md`, `work/probe-realism/renders/comparison-sheet.png`.

## The problem

`tools/blender/artemis_beats.py` builds every 3D beat from `material_principled()`, which
takes **numbers only** — a flat base-colour tuple, one metallic value, one roughness value.
Nothing in the production pipeline can reach a texture, so every surface is uniform and
every edge is a mathematically sharp 90° corner. That is why the user reads the result as
«ένας κύβος και ένα τρίγωνο» rather than as hardware.

## What the probe proved

Measured on this machine at production settings, the full look costs *less* render time
than the current house style (V4 0.197 s/frame vs V0 0.371/0.243 s/frame), because one
image lookup is cheaper per sample than the chained procedural node graphs. The price is
not compute. It is one shared interface plus a batch of hosted generation calls.

The five surfaces that moved the needle, in order of how much they fixed:

1. dark coarse **regolith** — the current ground reads as snow (task #72)
2. riveted **hull panels** — the single biggest "this is a machine" cue
3. **gold MLI** quilt and **silver Mylar** quilt — thermal hardware, unmistakably spacecraft
4. **pressure-suit fabric** — fixes the white clipart crew (task #73)
5. a 4° solar disc and 0.30 world strength — hard black shadow blobs are their own tell

## Design

### 1. Assets are project-owned, not third-party

The six usable tiles move from the spike into `assets/pbr/generated/` with a
`LICENSES.md` beside them recording, per file: model, model licence, Space, prompt, seed,
resolution, date. The channel is monetised, so **only Apache-2.0 models** may ship; FLUX.1
[schnell] is Apache-2.0, FLUX.1 dev/Krea are not. Rejected tiles stay in the spike
directory and never enter `assets/`.

### 2. One texture-capable material, cached by parameters

`common.py` gains `material_textured(name, tile, *, metres_per_tile, metallic, roughness,
bump, tint, saturate)`. It builds the node graph the probe validated — Image → Hue/Sat →
Multiply-tint → Base Color, the same Image re-used as height through RGB→BW → Bump — and
caches the result in a module-level dict keyed by the full parameter tuple. Without the
cache, 19 beats would load the same PNG dozens of times and blow up the datablock count.

Two probe lessons are load-bearing and must not be re-derived:

- **Never load the tile twice.** Images load with `check_existing=True`, so a second load
  for the height channel returns the *same* datablock; setting it to Non-Color would
  desaturate the albedo. The height input re-uses the colour node.
- **Texel density is metres, not a magic number.** Cube-projecting at `cube_size=1.0`
  makes one UV unit one metre, so `metres_per_tile` maps directly to world scale. At ~2 m
  per tile nothing was visible; 0.4–0.7 m per tile read as real material.

### 3. UVs are applied per object, by the surface call

`apply_surface(obj, key)` cube-projects that object and assigns the cached material from a
named palette. Projection happens on the object because UVs are per-mesh, while the
material is shared. It runs **before** any parent-scale packing, which is the ordering the
probe proved.

### 4. A named palette so beats stay declarative

`tools/blender/techniques/surfaces.py` exports `SURFACES` and `apply_surface`. A beat reads
`apply_surface(hull, "hull_panel")`, not a node graph. Adding a surface later means one
palette entry, not another 71 call sites.

### 5. Rollout is bounded by material class

Textured surfaces go on **solid hardware and ground only**. Emissive, volume, plasma,
atmosphere, cloud, transparent-shell and x-ray materials keep their current procedural
path — the probe never tested them and a tile on a plasma shell is a regression, not an
improvement. Bevels and 4°/0.30 lighting apply to every beat.

### 6. Output goes to 720p

Production renders at 1280×720 instead of 640×360. At the measured 0.2 s/frame the whole
3D layer costs roughly 40 minutes unattended, which is affordable and is what "professional"
requires at the pixel level.

## Non-goals

- No generated **footage** of identifiable vehicles. The probe generated a cinematic lunar
  scene and it drew a lander, not Orion. Hosted text-to-image is for mood plates and
  abstract inserts only, and any such shot needs the YouTube synthetic-media disclosure.
- No local diffusion. RX 580 has no CUDA; the Arc A380 is bought but not installed, and
  nothing in this design waits on it.
- No hosted video. Both Wan 2.2 Spaces returned `ZeroGPU quota exceeded` on this account.
- The spike directory stays throwaway; nothing in production imports from it.

## Testing

An integration test runs Blender in background mode, the way `python/test_blender_techniques.py`
already does. It asserts, for each palette key: the material exists, it has an Image
Texture node pointing at the shipped file, the object gained a UV layer, the image
datablock count equals the number of distinct tiles (the cache works), and a low-sample
render is not black. Then the real gate: re-render the 19 beats, re-assemble, and pull
frames for the user to judge.
