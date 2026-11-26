# AI video-to-video over our 3D renders: options (2026-11-26)

**Goal:** keep our motion, timing and camera from Blender, and have a model repaint the picture so the
people and sets look photoreal.

**Status:** prepared, nothing tried. No footage has been uploaded anywhere, no account has been made and
no money has been spent. Choosing a service is the owner's decision.

**Test clip:** `work/semmelweis-10min/renders/motion/ai-test/beat06-mothers-10s.mp4`.
- 10 s, 1280x720, 30 fps, no audio. It is cut from the motion-pass render at 100.5-110.5 s of the 2:33 test.
- It shows the three mothers at the First Clinic door. One clasps her hands and shakes her head on
  "Please. Not the first clinic"; the others react.
- No depth, normal or pose pass was exported. Rendering one costs another Blender run of the beat,
  about 20 minutes. Do it only for a service that takes one as a control input (Wan VACE does; Runway
  and Luma do not).

## Can it run on this PC? No, not in a usable way

The PC has a Ryzen 7 5700X, 64 GB RAM and a Radeon RX 580 (Polaris, gfx803).

- **No GPU path.** PyTorch on Windows runs on AMD only through ROCm, and AMD's Windows support matrix
  covers RDNA3/RDNA4 cards (RX 7000/9000) and Ryzen AI APUs. Polaris (gfx803) is not on it, so the RX 580
  cannot run these models at all. (The same card is also why Blender's Cycles cannot use it.)
- **Too little memory.** The open model that best keeps motion is Wan 2.1 VACE 14B. Its fp16 weights are
  about 32 GB, and third-party estimates put inference at about 38 GB of VRAM at fp16, or about 9-10 GB
  with an INT4 GGUF build. The RX 580 has 8 GB.
- **CPU is far too slow.** The small 1.3B model would run on the CPU, but at many hours per second of
  video, which is impractical.
- **The practical route is a hosted service,** or a rented cloud GPU (24-80 GB) running the open Wan
  VACE model.

## Hosted options

Costs below are list prices seen on 2026-11-26. One pass over the 153 s test is the minimum; real use
needs 2-3 passes per shot to choose from.

| | Runway Aleph 2.0 (Edit Studio / API) | Luma Ray 2 Modify ("Modify Video") | Wan VACE 14B on fal.ai (open model) |
|---|---|---|---|
| What it does | Edits or restyles an existing clip from a text prompt (and a reference image). Keeps the motion and the camera. | Restyles a clip; keeps motion and camera; strength settings from "adhere" to "reimagine". | Repaints a clip from a control input (pose, depth or the video itself) plus a prompt; the control keeps motion and camera exactly. |
| Price | 28 credits/s = **$0.28/s**, minimum $0.56 per generation | **$0.35/s** on fal.ai; Luma's API charges per pixel (720p 5 s ≈ $1.75). Ray 3.2 Modify via WaveSpeed is listed at $0.019/s, a different model on a reseller. | **$0.08/s** at 720p (pose endpoint; 16 fps output) |
| One pass of 153 s | about **$43** | about **$54** (Ray 3.2 via WaveSpeed about $3) | about **$12** |
| With 3 tries per shot | about $130 | about $160 | about $37 |
| Clip length | short generations (seconds), so the 153 s is cut into shots | up to 10 s (Ray 2), 30 s (Ray 3.2 on WaveSpeed) per generation | a few seconds per call, so long clips are cut into pieces |
| Footage uploaded to | Runway (USA) | Luma, or fal.ai / WaveSpeed as resellers | fal.ai (USA); or a GPU we rent, which keeps it off any model company's servers |
| Ownership and training | Runway's terms say it claims no ownership of inputs or outputs. Third-party summaries say non-Enterprise inputs and outputs may be used to train its models: check the current terms (updated 2026-05-11) first. | Paid Luma plans allow commercial use; check the data-use clause before uploading. | The Wan weights are open (Apache-2.0). fal.ai's terms govern the upload. Self-hosting on a rented GPU means no third-party model training. |
| What it is good at | The best "keep everything, make it real" edits today; the simplest to use. | Strong restyling; the strength setting controls how far it may drift. | The cheapest, the most control (it can use our depth or pose passes), and it can be self-hosted later. |
| Risks | Faces can change between shots (the same person looks different); costs add up with retries. | Same face-drift risk; less exact motion when the strength is high. | Needs more setup (workflow, passes); 16 fps output needs interpolating to 30. |

## Recommendation for a first try

1. Run the 10 s clip through **Wan VACE on fal.ai**: about $1 for a few tries, and the footage goes only to
   fal.ai. Then run it through **Runway Aleph**: about $3-9 for 1-3 tries.
2. Compare them on three things: is the motion kept, do the faces stay the same person, does it read as
   real. Only then decide on the whole 2.5 minutes.
3. To keep the footage away from any model company, rent a cloud GPU (24-48 GB, about $0.5-2/hour)
   and run Wan VACE there.

## Sources
- [Runway API pricing](https://docs.dev.runwayml.com/guides/pricing/)
- [Runway help: Aleph](https://help.runwayml.com/hc/en-us/articles/43176400374419)
- [Runway terms of use](https://runwayml.com/terms-of-use)
- [terms.law on Runway output rights](https://terms.law/ai-output-rights/runway/)
- [Luma Ray 2 Modify on fal.ai](https://fal.ai/models/fal-ai/luma-dream-machine/ray-2/modify)
- [Luma Modify Video API changelog](https://lumalabs.ai/changelog/modify-video-api-release)
- [Luma Modify Video on WaveSpeed](https://wavespeed.ai/models/luma/modify-video)
- [Wan VACE 14B pose on fal.ai](https://fal.ai/models/fal-ai/wan-vace-14b/pose/llms.txt)
- [Wan2.1 VACE 14B on Hugging Face](https://huggingface.co/Wan-AI/Wan2.1-VACE-14B)
- [ComfyUI VACE tutorial](https://docs.comfy.org/tutorials/video/wan/vace)
- [Spheron GPU guide for Wan VACE GGUF](https://www.spheron.network/tools/gpu-recommender/QuantStack/Wan2.1_14B_VACE-GGUF/)
- [AMD ROCm Windows support matrix](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/compatibility/compatibilityrad/windows/windows_compatibility.html)
