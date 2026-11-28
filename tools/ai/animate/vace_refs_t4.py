"""Wan2.1-VACE-1.3B video-to-video on a free Kaggle T4, second version.

Changes from tools/ai/wan_vace_v2v_free.ipynb, aimed at what the first run got wrong:
- the same people all through: one photographic reference image per character goes in as VACE
  `reference_images`;
- no jumps at the joins: every piece after the first starts with the last OVERLAP frames the previous
  piece made, kept as they are (black mask), and only the rest follows the depth;
- one seed for all pieces.
The T4 fixes of the first run stay: fp16, model CPU offload, VAE tiling, the `_native_efficient`
attention backend, the prompt encoded once and the text encoder moved to the CPU, 4k+1 frames per piece.

  python vace_refs_t4.py --clip CLIP.mp4 --refs a.png b.png c.png --out OUT.mp4 [--chunk 41]
"""
import argparse

import numpy as np
import torch
import imageio.v3 as iio
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("--clip", required=True)
ap.add_argument("--refs", nargs="*", default=[])
ap.add_argument("--out", required=True)
ap.add_argument("--chunk", type=int, default=41)
ap.add_argument("--overlap", type=int, default=5, help="1 + 4k frames kept from the previous piece")
ap.add_argument("--steps", type=int, default=30)
ap.add_argument("--seed", type=int, default=1846)
ap.add_argument("--prompt", default=(
    "Vienna 1846, dawn, a cobbled street before the heavy oak door of a hospital. Three poor young "
    "Austrian women in plain linen dresses, white aprons and bonnets stand side by side. The woman in the "
    "middle clasps her hands and pleads, then shakes her head; the others look at her, worried. "
    "Photorealistic 35 mm film still, natural skin with pores, soft overcast light, muted colours."))
ap.add_argument("--negative", default=(
    "cartoon, CGI, 3D render, plastic skin, doll, porcelain, oversaturated, blurry, deformed hands, "
    "extra fingers, text, numbers, signs, watermark, subtitles, worst quality, low quality"))
args = ap.parse_args()
assert (args.chunk - 1) % 4 == 0 and (args.overlap - 1) % 4 == 0

W, H, FPS = 832, 480, 16

meta = iio.immeta(args.clip, plugin="pyav")
src_fps = meta.get("fps", 30)
frames = [Image.fromarray(f).convert("RGB") for f in iio.imiter(args.clip, plugin="pyav")]
step = src_fps / FPS
frames = [frames[min(len(frames) - 1, round(i * step))] for i in range(int(len(frames) / step))]
frames = [f.resize((W, H), Image.LANCZOS) for f in frames]
print(len(frames), "frames at", FPS, "fps")

from transformers import pipeline as hf_pipeline  # noqa: E402

depth_pipe = hf_pipeline(task="depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf", device=0)
depth = []
for f in frames:
    d = np.array(depth_pipe(f)["depth"]).astype(np.float32)
    d = (255 * (d - d.min()) / max(1e-6, d.max() - d.min())).astype(np.uint8)
    depth.append(Image.fromarray(d).convert("RGB").resize((W, H)))
del depth_pipe
torch.cuda.empty_cache()

refs = [Image.open(p).convert("RGB") for p in args.refs]
print(len(refs), "reference images")

from diffusers import AutoencoderKLWan, WanVACEPipeline  # noqa: E402
from diffusers.schedulers.scheduling_unipc_multistep import UniPCMultistepScheduler  # noqa: E402
from diffusers.utils import export_to_video  # noqa: E402

model_id = "Wan-AI/Wan2.1-VACE-1.3B-diffusers"
vae = AutoencoderKLWan.from_pretrained(model_id, subfolder="vae", torch_dtype=torch.float32)
pipe = WanVACEPipeline.from_pretrained(model_id, vae=vae, torch_dtype=torch.float16)
pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config, flow_shift=3.0)
pipe.enable_model_cpu_offload()
pipe.vae.enable_tiling()
pipe.transformer.set_attention_backend("_native_efficient")

PE, NE = torch.no_grad()(pipe.encode_prompt)(prompt=args.prompt, negative_prompt=args.negative,
                                             do_classifier_free_guidance=True, device=torch.device("cuda"))
pipe.text_encoder.to("cpu")
torch.cuda.empty_cache()
pipe.encode_prompt = lambda *a, **k: (PE, NE)

white, black = Image.new("L", (W, H), 255), Image.new("L", (W, H), 0)
out, start = [], 0
while start < len(depth) - 1:
    keep = args.overlap if out else 0
    n = min(args.chunk, keep + len(depth) - start)
    n = 4 * ((n - 1) // 4) + 1
    if n - keep < 4:                       # nothing new left worth a call
        break
    video = out[-keep:] + depth[start:start + n - keep] if keep else depth[start:start + n]
    mask = [black] * keep + [white] * (n - keep)
    print(f"piece: frames {start}..{start + n - keep - 1}, {keep} kept + {n - keep} new", flush=True)
    result = pipe(video=video, mask=mask, reference_images=refs or None, prompt=args.prompt,
                  negative_prompt=args.negative, height=H, width=W, num_frames=n,
                  num_inference_steps=args.steps, guidance_scale=5.0,
                  generator=torch.Generator("cpu").manual_seed(args.seed), output_type="pil").frames[0]
    out.extend(result[keep:])
    start += n - keep
    torch.cuda.empty_cache()
export_to_video(out, args.out, fps=FPS)
print("wrote", args.out, len(out), "frames", flush=True)
