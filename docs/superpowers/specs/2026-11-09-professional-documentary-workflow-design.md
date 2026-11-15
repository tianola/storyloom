# Professional Documentary Workflow (v3) — Design Spec

**Date:** 2026-11-09
**Project:** `F:\AI-PROJECTS\longform-explainer`
**Status:** Approved direction (user mandate 2026-11-09: full research, install everything feasible, start)
**Supersedes:** ad-hoc per-episode pipeline used for episode-cables v1/v2

---

## 1. Goal

Produce solo, long-form, fern-style documentary episodes at a professional level:
recreated UI/screenshots as vector animation, kinetic typography, archival-driven
visuals, detailed 3D explainer beats wherever they improve understanding,
licensed-music sound bed, fast cutting.

**Target format (locked with user):**
- Duration: **10–15 minutes** per episode (~200–300 shots)
- Language: **English**
- Narration: **Kokoro TTS** (existing pipeline; quality gap vs human VO accepted for now, revisitable)
- Pace: **15–18 cuts/min** (fern measured 18, Veritasium 10.6, our v2 was ~10)
- Cadence: realistic solo target **1 episode / 2 weeks**
- Rendering: CPU-only + AMD EEVEE (RX 580 4GB, no CUDA/ROCm), ffmpeg AMF encode available

**Reference productions analyzed (2026-11-08/09):**
- Veritasium `NiCgcUTL9_Q` (34:32, 365 cuts): presenter-led, crew + experts — not solo-replicable; we adopt its mechanism-explanation depth, not its physical production.
- fern `dU7gCt-7kKk` (46:53, 845 cuts): research → script → VO → motion design over archival — this is our model.

---

## 2. The 9-phase episode workflow

| Phase | Output | Tools | Time budget | Quality gate |
|---|---|---|---|---|
| 1. Research | `research/sources.md` (every claim → citation), `research/facts.json` | deep-research skill, WebSearch/WebFetch, firecrawl, yt-dlp transcripts | 1–2 days | Every factual claim has ≥1 source; contested claims ≥2 |
| 2. Story | `story/beat-sheet.md`: hook + 3 acts + payoff; per-beat visual idea | templates in `workflow/templates/` | 0.5–1 day | Each act ends on a tension/reveal; no act is a fact list |
| 3. Script | `script/narration.md` with per-line visual notes + shot list draft | ai-video-script / content-research-writer | 1 day | Read-aloud pass; per-line visual assigned |
| 4. Visual sourcing | `assets/` + `assets/license-manifest.json` (§5) | sourcing tools §6, preview/screenshot policy §5 | 1–2 days | Every shot has media or a build task; every external asset logged |
| 5. VO | `vo/*.wav` per line + timings | Kokoro TTS (existing), auto-editor cleanup | <1 hour | No clipped words; line durations feed timeline |
| 6. Motion design | HyperFrames sections, Blender beats, Ken Burns plates, recreated UI | HyperFrames + new skills (§4), Blender 4.5 (§3) | 3–7 days | Per-section QA; 3D beats per §3 policy |
| 7. Edit | `final.mp4` 1080p30, music bed + ducking, SFX | existing assemble.py cumulative-frame pipeline, numpy mix | 1–2 days | 15–18 cuts/min; no static shot >8s without motion |
| 8. QC | Contact sheets, loudness −16±1 LUFS, frame counts, caption checks | existing QA suite + transition-midpoint snapshots | 0.5 day | All checks green; user watches preview cut |
| 9. Packaging | Thumbnail, title, description, chapters, public sources link, **license purchase list** | Photopea/ImageGen, manifest → purchase list export | 0.5 day | **No upload until all `preview` assets purchased/swapped (§5)** |

Phases 1–4 and 6 deliberately get MORE time than the old pipeline — user directive:
better research, more detailed techniques, more motion-design/edit effort.

---

## 3. Detailed 3D explainer beats — policy and technique library

**Policy (user directive):** 3D beats and diagrams are NOT reserved for rare
"expert moments". Insert a detailed 3D explainer beat **whenever a mechanism,
process, structure, or spatial relationship would be clearer in 3D than in any
other shot type**. Budget per 10–15 min episode: **4–10 Blender beats** (up from
3 in cables-v2), each 5–20s.

### 3.1 Technique library (reusable, versioned scene scripts)

| Technique | Use for | Implementation |
|---|---|---|
| Zoom-inside | reveal internals of device/cable/structure | camera dolly through shell, fade/clip outer mesh |
| Boolean cutaway | show cross-sections | animated `Difference` cutter, Exact solver, bevel after Boolean |
| Exploded view | assemblies, part relationships | Geometry Nodes separation node group (per-part offset) |
| X-ray / ghost shell | mechanism inside housing | transparent BSDF mix on shell, animated factor |
| Staggered assembly | construction sequences | Commotion addon F-Curve/NLA offsets |
| Mechanism animation | repeaters, gears, signals, light paths | keyframed drivers, curve-follow for signal/light |
| 3D-anchored labels | callouts that track parts | existing leader-line system (cables-v2), keep ≥28px equivalent |
| Map/globe beats | routes, geopolitics, networks | globe mesh + arc curves (or three.js/R3F if data-driven) |
| Data-driven scene | parameterized networks/timelines | three.js/R3F rendered via headless Chrome (optional track) |

### 3.2 Blender versions

- **Production: Blender 4.5.15 LTS** (`tools/blender-4.5.15-windows-x64/`) — EEVEE Next
  (screen-space GI/reflections, virtual shadow maps, EEVEE motion blur) = visibly
  better glass/metal/water/volumetrics than 4.1.
- **Evaluation: Blender 5.2.3 LTS** (`tools/blender-5.2.3-windows-x64/`) — tested in
  parallel on one real beat before any switch.
- **Legacy: Blender 4.1.0** kept untouched for reproducing old episodes.
- RX 580 = Polaris/GCN4: passes official baseline; verify one real `.blend` with
  glass + shadows + volumetrics on 4.5 before first production beat (driver-dependent).
- Upgrade protocol: render the SAME beat on 4.1 and 4.5, compare contact frames,
  then switch `BLENDER_EXE` in pipeline config. Old episode scripts stay on 4.1.

### 3.3 Asset libraries (all free)

| Source | License | Account | Use |
|---|---|---|---|
| Poly Haven | CC0 | none | HDRIs, PBR metal/wood/floors, studio lighting |
| ambientCG | CC0 | none | brushed metal, rubber, plastic, concrete materials |
| Sketchfab (Downloadable + CC0/CC-BY filter) | CC0/CC-BY | **free account (user)** | devices, vehicles, historical objects, globes |
| Kenney | CC0 | none | low-poly blockouts, stylized props |
| Quaternius | CC0 | none | environments, animated low-poly |
| BlenderKit free assets | per-asset | free login | in-Blender props/materials |
| Mixamo | free w/ Adobe ID | **user** | human beats (only if ever needed) |
| Meshy/Tripo free credits | per-site | **user, optional** | blockout props only — never dimension-critical mechanisms |

No local AI-3D generation (Hunyuan3D needs ~10–29GB VRAM — impossible on RX 580 4GB).

### 3.4 Add-ons / helpers downloaded or available

- **Commotion** (`tools/blender-addons/commotion.zip`) — staggered reveals, offset animation;
  archive downloaded, installation into the portable 4.5 configuration is roadmap item 3.
- **Mograph GN presets** (`tools/mograph-gn-presets/`) — clones/falloffs; repository downloaded
  as an idea library only. No root license file was present on 2026-11-09, so its `.blend`
  assets and node groups are not cleared for production reuse.
- **Add Camera Rigs** — bundled in Blender, enable per scene.
- **blender-mcp** — already installed as skill; supervised scene building only,
  localhost, safe mode, versioned Python scene scripts (never unattended production).

---

## 4. Motion design / renderer decision

**Decision: KEEP HyperFrames as the primary renderer.** Research verdict: the
current HTML/CSS/GSAP approach is technically suited; Remotion is the only serious
alternative (free for solo, official agent skills, captions package, strong
maintenance) but a migration is not justified while HyperFrames covers the work.
Motion Canvas/Revideo were rejected for this use case (no real DOM/CSS — faithful
forum/website recreation, the core fern technique, is harder). Manim stays a
specialist for math/graph diagrams; D3 for data charts inside HyperFrames sections.

**Remotion evaluation track (optional):** `remotion-best-practices` skill installed.
One 20–30s spike section only if HyperFrames hits a concrete limitation; no
production migration without user approval.

### 4.1 HyperFrames skills installed this session (official heygen-com/hyperframes)

| Skill | Role in documentary workflow |
|---|---|
| `hyperframes` (updated) | core renderer skill |
| `hyperframes-cli`, `hyperframes-registry` | CLI + animation block registry (title/camera blocks) |
| `media-use` | media asset handling (archival plates, screenshots) |
| `captions-overlay` | caption systems |
| `motion-doctrine` | motion design principles |
| `reverse-any-video` | reverse-engineer a reference shot into HyperFrames — our fern/Veritasium mimicry tool |
| `style-sampling` | extract style from reference frames |
| `cut-the-curve` | pacing/cutting technique |
| `seam-craft` | seamless transitions |
| `remotion-best-practices` (remotion-dev) | optional evaluation track |

Registry blocks available: `canopy-part-title`, `code-slice-hero`, `cuboid-carousel`,
`frost-sequence-camera-orbit`, `glass-shard-title`, `orbit-card`, `wireframe-portal-title`.

### 4.2 Fern-style shot recipes to build as reusable sections

1. **Recreated UI** (forum/website/chat): semantic HTML/CSS replica, cursor/typing
   animation, highlight/zoom on the quoted element. Never raw low-res screenshots
   when a rebuild is feasible; raw screenshot allowed for ephemera.
2. **Kinetic quote typography**: source-styled quote cards with word/line reveals.
3. **Ken Burns plates**: archival photo + slow zoom/pan (ffmpeg zoompan or
   HyperFrames transform), subtle parallax on layered cutouts for hero images.
4. **News/footage inserts**: licensed clip with source lower-third.
5. **Diagrams/charts**: existing HyperFrames diagrams + D3 when data-heavy;
   Manim for math.
6. **3D beats**: §3.
7. **Meme/ephemera**: as-is with caption context (documentary fair-dealing review
   per item at license stage).

**Pacing rule:** target 15–18 cuts/min; every shot carries new information or a
visual change at least every 3–4s (motion, push-in, highlight — not static holds).

---

## 5. Archive sourcing & licensing policy (USER DIRECTIVE)

1. **Download now, license before upload.** Source the best available media for the
   cut immediately: watermarked previews, official comp downloads, or screenshots.
   Place them in the edit normally (preview cut WILL contain watermarks — intended).
2. **Every externally sourced asset is logged** in `assets/license-manifest.json`
   at download time (schema §5.1) — no asset enters the timeline untracked.
3. **Before upload**, the user purchases licenses from the generated purchase list
   (provider + asset ID + URL). Clean files replace previews **at the same path**;
   only affected shots re-render (manifest lists shot IDs per asset).
4. **Fallback rule:** if an item cannot be accessed or even screenshotted → use a
   free alternative instead. Applies generally to all media.
5. **Free-first for ephemera:** Internet Archive, Wikimedia Commons, Library of
   Congress, NASA/NOAA/ESA, Smithsonian OA, US/UK National Archives, Europeana,
   Rijksmuseum, NYPL, Pexels/Pixabay/Mixkit, Pond5 Public Domain collection.
6. **Hard license rules:**
   - CC BY-NC material is **banned** (monetized channel).
   - CC BY / CC BY-SA → attribution text goes into manifest + video description.
   - BBC Sound Effects (RemArc) = personal/educational only → **treated as paid**
     (commercial via Pro Sound Effects), never as free.
   - Editorial-only assets (Getty/AP/Reuters) only in genuinely editorial context.
   - Artlist/Epidemic/Storyblocks downloads need subscription → in practice use
     free music (below) unless user subscribes; subscriptions are user's choice.

### 5.1 `license-manifest.json` schema (per asset)

```json
{
  "id": "a0042",
  "file": "assets/archival/pathe_dday_1944.jpg",
  "kind": "photo|video|music|sfx|screenshot",
  "provider": "british-pathe|wikimedia|pexels|shutterstock|...",
  "asset_id": "1089.12",
  "url": "https://...",
  "watermarked": true,
  "license_status": "preview|free|purchased|fair-dealing-review",
  "license_type": "preview-comp|CC0|CC-BY|CC-BY-SA|PD|editorial|paid-standard",
  "attribution": "required text or empty",
  "shots": ["s12", "s13"],
  "downloaded_at": "2026-11-09",
  "notes": "replace with HD comp after purchase"
}
```

### 5.2 Purchase list export

`python tools/manifest_report.py --episode X` → `dist/license-purchase-list.md`:
grouped by provider, asset ID + URL + local file + shots, only `license_status=preview`.
After user drops clean files at the same paths: set `license_status=purchased`,
`watermarked=false`, re-render listed shots, run QC again.

### 5.3 Provider preview cheat-sheet (verified Nov 2026; "unverified" = needs one browser test at first use)

- All major stock photo providers (Shutterstock, Adobe Stock, Getty, iStock, Alamy,
  Dreamstime, Depositphotos, 123RF): public watermarked preview page → screenshot
  always possible; asset ID in URL; official comp download unverified per provider.
- **Pond5**: official "Download Preview" button; plus free Public Domain collection.
- **British Pathé / CriticalPast / AP Archive / Historic Films**: public preview
  players → screen capture or screenshot; clip/film ID + exact title + timecode
  into manifest notes for purchase.
- **Music (free):** Pixabay Music, Mixkit, YouTube Audio Library, FreePD,
  incompetech (CC BY credit), Free Music Archive (per-track CC check, no NC),
  **Uppbeat free tier = 3 downloads/month** (free account — user).
- **SFX (free):** freesound.org (CC0/CC-BY filter), Mixkit SFX, Pixabay SFX,
  Zapsplat (free with credit).

---

## 6. Tool & download stack

### 6.1 Downloaded or installed this session

CLI/version checks passed for the tools below. Blender EEVEE rendering, Commotion
activation, and media-provider behavior remain separate runtime gates in §7.

| Tool | Version | Purpose |
|---|---|---|
| gallery-dl | 1.32.19 | bulk image/gallery download (Flickr, Behance, Reddit, etc.) |
| internetarchive (`ia`) | 5.12.1 | Internet Archive search/metadata/download |
| auto-editor | 29.3.1 | narration silence cleanup (first pass only — creative cuts stay manual) |
| mwclient | pip latest | Wikimedia Commons category bulk enumeration |
| single-file-cli | npm global | full-page HTML snapshots for UI recreation reference |
| Blender 4.5.15 LTS | portable in `tools/`; `--version` passed | candidate production 3D, pending EEVEE render |
| Blender 5.2.3 LTS | portable in `tools/`; `--version` passed | evaluation 3D |
| Commotion addon | master zip in `tools/blender-addons/` | staggered animation; activation pending |
| Mograph GN presets | `tools/mograph-gn-presets/` | uncleared-license idea library, not production assets |
| 10 HyperFrames skills + remotion-best-practices | user scope | §4.1 |

Already present from before: yt-dlp, Kokoro TTS, HyperFrames, Blender 4.1,
ffmpeg(+AMF), playwright MCP, firecrawl MCP, obsidian vault, QA suite.

### 6.2 USER ACTION LIST (cannot be done by agent)

**Free accounts / API keys (10–20 min total):**
1. **Sketchfab** account — CC0/CC-BY 3D model downloads (https://sketchfab.com)
2. **Uppbeat** free account — 3 music downloads/month (https://uppbeat.io)
3. **Pexels + Pixabay** API keys (free, instant) — programmatic stock search
4. **Rijksmuseum** API key, **NYPL Digital Collections** token, **Europeana** API key — only if/when those collections are used
5. **Adobe ID** for Mixamo — only if human beats are needed
6. **BlenderKit** free login — optional in-Blender asset browser

**Optional paid (user's call; free alternatives documented in §5):**
- **Artlist** (~$15–30/mo, exact 2026 price unverified — pricing page blocked) — the
  single highest-impact paid upgrade: fern used ~60 Artlist tracks in one video.
- Pond5/British Pathé/CriticalPast/Shutterstock **per-asset purchases** — pay only
  for what the final cut actually uses (from purchase list).
- Storyblocks/Envato stock subscription — only if free stock proves limiting.
- **ElevenLabs** — only if Kokoro VO quality is revisited later.

**Not needed:** Ruby + wayback-machine-downloader gem (we will use IA CDX API via
Python instead), After Effects (programmatic pipeline covers it), local AI-3D models
(VRAM), CUDA anything.

**Optional GUI for manual finishing:** Kdenlive (free) — for occasional hand-tuned
edits/color outside the programmatic pipeline. Not required; install on demand.

---

## 7. Implementation roadmap (what gets built)

1. **Workflow scaffolding** (`workflow/`): templates for sources doc, beat sheet,
   narration script with visual notes; episode init script creating the 9-phase
   directory layout + empty license manifest.
2. **Sourcing toolkit** (`tools/sourcing/`): manifest writer/validator,
   purchase-list exporter, Wikimedia/IA/Pexels search-download helpers,
   screenshot helper (playwright) for preview pages.
3. **Blender upgrade verification**: same-beat render 4.1 vs 4.5 comparison +
   `BLENDER_EXE` config switch; Commotion install into 4.5 portable.
4. **Fern shot-recipe library**: recreated-UI section template, kinetic quote card,
   Ken Burns plate generator, news lower-third; each with QA snapshot.
5. **3D beat technique pack**: cutaway/exploded/x-ray/zoom-inside starter `.blend`
   scenes + label system ported to 4.5.
6. **First pilot episode** on the new workflow: `episode-carrington`, an English
   10–15 minute documentary about the 1859 Carrington Event, selected under the
   user's full-creative-license mandate. Run all 9 phases, ending at preview cut +
   purchase list (never auto-upload).

QC invariants carried over: cumulative per-shot frame counts, tpad clone tail,
contact sheets incl. transition midpoints, loudness target, no upload action ever.

---

## 8. Explicitly out of scope (for now)

- Remotion production migration (evaluation spike only if HyperFrames blocks us)
- Human VO / hired narrator (Kokoro locked by user)
- Live-action/presenter production (Veritasium model — not solo-replicable)
- Weekly cadence (team-scale; solo target is 2 weeks/episode)
- AI video-generation beats (no local VRAM; cloud = paid, needs separate approval)
