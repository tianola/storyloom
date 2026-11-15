# PROJECT
- Root: `F:/AI-PROJECTS/longform-explainer`; local studio for research, narrated documentary and engineering explainer videos.
- Stack: Python 3 + Blender 4.5 + FFmpeg for documentary episodes; Node 24/TypeScript + Zod + SQLite + `@resvg/resvg-js` for the separate deterministic SVG pipeline; Kokoro ONNX narration adapter.
- Main layout: `workflow/` episode/archive/style contracts; `tools/blender/models/` reusable 3D kit; `tools/blender/*_beats.py` episode builders; `tools/assemble_episode.py` assembler; `tools/qc_episode.py` master QC; `python/` tests and adapters; `src/` TypeScript app.
- Jensen episode: `work/jensen-huang/`; current GPU explainer pilot: `work/explainer-pilot/inside-gpu.mp4`.
- Blender shot style: `tools/blender/models/look.py` explainer look; validated data/style contract in `workflow/style.json`.
- Git initialized; commits are used for checkpoints. Large media, environments and model assets are ignored.
- Keep this file limited to stable architecture/stack changes. Current work belongs in `STATE.md` and `HANDOFF.md`.
