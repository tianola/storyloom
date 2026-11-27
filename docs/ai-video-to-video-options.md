# AI video-to-video over our 3D renders: free routes only (checked 2026-11-27)

**Project rule:** every tool and service must be free. Paid services, paid credits and paid tiers are
out, so the paid options of the previous version of this page (Runway, Luma, fal.ai) are dropped.

**Goal:** keep our motion, timing and camera from Blender, and have an open model repaint the picture so
it looks real.

**Status:**
- Prepared, not run. Nothing has been uploaded and no account has been made: the owner runs it in his
  own free account.
- Test clip: `work/semmelweis-10min/renders/motion/ai-test/beat06-mothers-10s.mp4` (10 s, 1280x720,
  30 fps, no sound): the three mothers, the plea and the head shake.
- Ready-to-run notebook: `tools/ai/wan_vace_v2v_free.ipynb`. It is untested, because this PC has no
  NVIDIA GPU.

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
| Limits | *Unverified* (Kaggle's [docs page](https://www.kaggle.com/docs/notebooks) did not load for checking; the figures are from third-party guides): about 30 GPU hours a week, sessions up to about 12 hours, GPU 1-2x NVIDIA T4 with 16 GB each. Your account settings show the real quota. |
| Fits | Yes: the 10 s clip at 480p in two pieces of 81 frames. Rough estimate 10-30 minutes on a T4 (*unverified*). |
| Your footage | Uploaded to Kaggle (Google) as a private dataset in your account. |
| Cost | Free. |

**Steps** (they are also at the top of the notebook):
1. kaggle.com → New Notebook → File → Import notebook → `tools/ai/wan_vace_v2v_free.ipynb`.
2. Add data → Upload → `beat06-mothers-10s.mp4` as a private dataset.
3. Settings → Accelerator → GPU T4. Settings → Internet → On.
4. Run all. Then download `wan_vace_out.mp4` from Output.
5. Optional, on the PC: `ffmpeg -i wan_vace_out.mp4 -vf "minterpolate=fps=30,scale=1280:720:flags=lanczos" out30.mp4`.

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

Use **Kaggle**: free and the most room. Run the notebook on the 10 s clip and judge three things: is the
motion kept, do the faces stay the same people, does it read as real. Only if it passes, process the
2.5-minute test piece by piece within the weekly quota (about 30 pieces of 5 s).

## Sources (checked 2026-11-27)
- [Wan2.1-VACE-1.3B model card](https://huggingface.co/Wan-AI/Wan2.1-VACE-1.3B)
- [Diffusers Wan pipelines](https://huggingface.co/docs/diffusers/main/en/api/pipelines/wan)
- [Depth-Anything-V2-Small](https://huggingface.co/depth-anything/Depth-Anything-V2-Small-hf)
- [Colab FAQ](https://research.google.com/colaboratory/faq.html)
- [Hugging Face ZeroGPU](https://huggingface.co/docs/hub/spaces-zerogpu)
- [Kaggle notebooks docs](https://www.kaggle.com/docs/notebooks) (did not load)
- [Free Cloud GPUs in 2026 (gpuperhour)](https://gpuperhour.com/blog/free-cloud-gpus-and-credits) (third party, for the Kaggle quota)
- [AMD ROCm Windows support matrix](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/compatibility/compatibilityrad/windows/windows_compatibility.html)
