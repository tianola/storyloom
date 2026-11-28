# AI video-to-video over our 3D renders: free routes only (checked 2026-11-27)

**Project rule:** every tool and service must be free. Paid services, paid credits and paid tiers are
out, so the paid options of the previous version of this page (Runway, Luma, fal.ai) are dropped.

**Goal:** keep our motion, timing and camera from Blender, and have an open model repaint the picture so
it looks real.

**Status:**
- Run once on 2026-11-28 in the owner's free Kaggle account (T4). Only the 10 s clip was uploaded, as a
  private dataset. The result is `work/semmelweis-10min/renders/motion/ai-test/wan_vace_out.mp4`, with a
  side-by-side comparison in `.../ai-test/compare/`. See "Result of the first run" below.
- Test clip: `work/semmelweis-10min/renders/motion/ai-test/beat06-mothers-10s.mp4` (10 s, 1280x720,
  30 fps, no sound): the three mothers, the plea and the head shake.
- Notebook: `tools/ai/wan_vace_v2v_free.ipynb`, fixed for a 16 GB T4 during the first run.

## The model: Wan2.1-VACE-1.3B (open, free)

Checked on its [model card](https://huggingface.co/Wan-AI/Wan2.1-VACE-1.3B) on 2026-11-27.
- **Licence:** Apache-2.0, so commercial use is allowed.
- **Resolution:** built for 480p (832x480). The card says 720p works but is "generally less stable".
- **Video-to-video:** done with a control video (depth, pose and so on); the depth or pose is computed
  first.
- **Frames:** the frame count must be 4k+1, with about 81 frames per call (about 5 s at 16 fps). A 10 s clip
  therefore needs two calls.
- **VRAM:** not stated for VACE. *Unverified:* about 8 GB is reported for the related T2V-1.3B model, and
  the VACE transformer file alone is about 7 GB, so a 16 GB GPU is comfortable and 8 GB is tight.
- **Depth model:** [Depth-Anything-V2-Small](https://huggingface.co/depth-anything/Depth-Anything-V2-Small-hf),
  Apache-2.0, 25M parameters.
- **Library:** the `WanVACEPipeline` of [Diffusers](https://huggingface.co/docs/diffusers/main/en/api/pipelines/wan).
  In the mask, black is kept and white is generated.

## Free route 1 (recommended): Kaggle Notebooks, free GPU

| | |
|---|---|
| What you get | A free Jupyter notebook with an NVIDIA GPU, in your own Kaggle account (a phone-verified account is needed for GPUs). |
| Limits | Checked in the owner's account settings on 2026-11-28: 30 GPU hours a week, sessions up to 12 hours, GPU T4 x2 (16 GB each). P100 was not offered. A saved "Run All" version can wait in the queue for a long time (45+ minutes on 2026-11-28); an interactive session started sooner. |
| Fits | Yes, with the T4 fixes in the notebook: 4 pieces of up to 49 frames at 480p. Measured: 37 s per step, about 1 h 35 min for the 10 s clip, so about 1.6 GPU hours per 10 s. |
| Your footage | Uploaded to Kaggle (Google) as a private dataset in your account. |
| Cost | Free. |

**Steps** (they are also at the top of the notebook):
1. kaggle.com → New Notebook → File → Import notebook → `tools/ai/wan_vace_v2v_free.ipynb`.
2. Add data → Upload → `beat06-mothers-10s.mp4` as a private dataset.
3. Settings → Accelerator → GPU T4. Settings → Internet → On.
4. Run all. Then download `wan_vace_out.mp4` from Output.
5. Optional, on the PC: `ffmpeg -i wan_vace_out.mp4 -vf "minterpolate=fps=30,scale=1280:720:flags=lanczos" out30.mp4`.

## Result of the first run (2026-11-28)

What the T4 needed (all in the notebook now): `av` for imageio; 49-frame pieces and VAE tiling (81 frames
ran out of memory); the `_native_efficient` attention backend in fp16 (the default asked for 18 GB); the
prompt encoded once and the 11 GB text encoder moved to the CPU; a stop when fewer than 5 frames are left
(the loop otherwise repeated 1-frame pieces forever).

- **Looks real:** yes, far more than our renders: skin, cloth, stone and light read as filmed.
- **Motion and camera:** kept. The camera, the three positions and the big gestures (hand to chest) follow
  the depth of our clip.
- **Faces and people:** not kept. The model invents new faces, and they and the dresses, the bonnets and the
  building change at every piece join (about every 3 s). The women also do not look like our cast.
- **Verdict:** not usable for the film as it is. It is worth one more test with the same free setup:
  give VACE a reference image of each woman and of the set, condition each piece on the last frames of the
  one before (instead of starting fresh), and name the look in the prompt more tightly.

## Free route 2: Google Colab, free tier

Checked on the [Colab FAQ](https://research.google.com/colaboratory/faq.html) on 2026-11-27.
- "Colab is free of charge to use."
- GPUs are "not guaranteed and not unlimited", and the GPU type varies.
- A free notebook runs for "at most 12 hours" and stops when idle. Colab does not publish its limits.
- **Catch:** the FAQ says free runtimes doing "content generation" "commonly experience runtime terminations".
  The same notebook runs there, but a run may be cut off. Use it only as a fallback.
- Your footage goes to Google Drive or the Colab runtime in your account.

## Free route 3: Hugging Face Spaces, ZeroGPU

Checked on the [ZeroGPU docs](https://huggingface.co/docs/hub/spaces-zerogpu) on 2026-11-27.
- "available to use for free to all users", with a daily GPU quota of 2 minutes (no account) or 5 minutes
  (free account).
- The GPU is half an RTX Pro 6000 with 48 GB. A call can run 60 s by default.
- **Verdict:** 5 minutes a day is enough for perhaps one 5 s piece at 480p, using a public Space that
  already runs Wan VACE (which Space is still to find, *unverified*). It is fine to see the look once,
  but too little for the film.
- Your footage goes to the Space's owner and Hugging Face.

## On this PC (RX 580, 8 GB): not usable

- **No GPU route for Wan.** PyTorch on AMD under Windows needs ROCm, and AMD's
  [Windows support matrix](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/compatibility/compatibilityrad/windows/windows_compatibility.html)
  lists only the RX 7000/9000 series and Ryzen AI, not Polaris (RX 580). ZLUDA, the CUDA-on-AMD
  translation layer, also targets newer AMD cards.
- **The older path is possible but poor.** ComfyUI with DirectML (torch-directml) can run Stable Diffusion
  1.5 with ControlNet and an AnimateDiff-style motion module. My estimate (*unverified*, not measured
  here) is minutes per frame at 512x288 for a 10 s clip, so hours, with visible flicker from frame to
  frame and faces that change. That is worse than our renders, so it is not recommended.
- **Wan VACE 1.3B on the CPU (Ryzen 7 5700X)** would run in principle, but at many hours per second of
  video. That is not practical.

## Recommendation

Use **Kaggle**: free and the most room. The first run passed on motion and realism and failed on keeping the
same people (see above). Fix that first. At the measured speed, the 2.5-minute test would need about 24 GPU
hours, almost all of one week's quota, so only process it once a 10 s test keeps the faces.

## Sources (checked 2026-11-27)
- [Wan2.1-VACE-1.3B model card](https://huggingface.co/Wan-AI/Wan2.1-VACE-1.3B)
- [Diffusers Wan pipelines](https://huggingface.co/docs/diffusers/main/en/api/pipelines/wan)
- [Depth-Anything-V2-Small](https://huggingface.co/depth-anything/Depth-Anything-V2-Small-hf)
- [Colab FAQ](https://research.google.com/colaboratory/faq.html)
- [Hugging Face ZeroGPU](https://huggingface.co/docs/hub/spaces-zerogpu)
- [Kaggle notebooks docs](https://www.kaggle.com/docs/notebooks) (did not load)
- [Free Cloud GPUs in 2026 (gpuperhour)](https://gpuperhour.com/blog/free-cloud-gpus-and-credits) (third party, for the Kaggle quota)
- [AMD ROCm Windows support matrix](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/compatibility/compatibilityrad/windows/windows_compatibility.html)
