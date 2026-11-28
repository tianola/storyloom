"""A photographic reference image of one character for Wan2.2-Animate, made from our Blender render of
that character, so build, pose and clothes match the 3D figure.

SDXL base 1.0 (CreativeML Open RAIL++-M, commercial use allowed) img2img on a free Kaggle T4, fp16.
It crops the character from an RGBA Blender frame, puts it on a plain backdrop and repaints it at a
strength that keeps the shapes. Several seeds; pick the best by eye.

  python make_reference.py --png FRAME.png --out DIR --prompt "..." [--strength 0.55] [--seeds 1 2 3 4]
"""
import argparse
import os

import numpy as np
import torch
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("--png", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--prompt", required=True)
ap.add_argument("--negative", default="cartoon, CGI, 3D render, doll, porcelain skin, plastic, waxy, "
                "smooth skin, airbrushed, painting, illustration, deformed, extra fingers, blurry, "
                "text, watermark, modern clothes")
ap.add_argument("--strength", type=float, default=0.55)
ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3, 4])
ap.add_argument("--grey", type=int, default=150)
args = ap.parse_args()

im = Image.open(args.png).convert("RGBA")
a = np.array(im)[:, :, 3]
ys, xs = np.nonzero(a > 10)
x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
pad = int(0.08 * (y1 - y0))
box = (max(0, x0 - pad), max(0, y0 - pad), min(im.width, x1 + pad), min(im.height, y1 + pad))
crop = im.crop(box)
# portrait canvas 832x1216 (an SDXL size), character centred, plain backdrop
W, H = 832, 1216
scale = min(W * 0.9 / crop.width, H * 0.95 / crop.height)
crop = crop.resize((int(crop.width * scale), int(crop.height * scale)), Image.LANCZOS)
canvas = Image.new("RGBA", (W, H), (args.grey,) * 3 + (255,))
canvas.alpha_composite(crop, ((W - crop.width) // 2, H - crop.height))
init = canvas.convert("RGB")
os.makedirs(args.out, exist_ok=True)
init.save(os.path.join(args.out, "init.png"))

from diffusers import AutoPipelineForImage2Image, AutoencoderKL  # noqa: E402

dev = "cuda" if torch.cuda.is_available() else "cpu"
dtype = torch.float16 if dev == "cuda" else torch.float32    # CPU: fp32 (slow, ~10 min an image)
vae = AutoencoderKL.from_pretrained("madebyollin/sdxl-vae-fp16-fix", torch_dtype=dtype)
pipe = AutoPipelineForImage2Image.from_pretrained("stabilityai/stable-diffusion-xl-base-1.0", vae=vae,
                                                  torch_dtype=dtype, variant="fp16").to(dev)
for s in args.seeds:
    img = pipe(prompt=args.prompt, negative_prompt=args.negative, image=init, strength=args.strength,
               num_inference_steps=40, guidance_scale=6.0,
               generator=torch.Generator(dev).manual_seed(s)).images[0]
    path = os.path.join(args.out, f"ref_seed{s}.png")
    img.save(path)
    print("wrote", path)
