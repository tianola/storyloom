"""Free Kaggle T4 run, version 2: same people all through, no jumps, 1080p out.

1. One photographic reference per character, from the clip itself: crop the character from a frame and
   repaint it with SDXL img2img (CreativeML Open RAIL++-M), keeping build, pose and clothes.
2. Wan2.1-VACE-1.3B (Apache-2.0) video-to-video on depth, with those references and with each piece
   starting from the last frames of the one before (vace_refs_t4.py).
3. 2x Real-ESRGAN (BSD-3) and a resize to 1920x1080.
Everything is written to OUT (default /kaggle/working/v2).
"""
import glob
import os
import subprocess
import sys

OUT = os.environ.get("OUT", "/kaggle/working/v2")
os.makedirs(OUT, exist_ok=True)
subprocess.run([sys.executable, "-m", "pip", "-q", "install", "diffusers>=0.34", "transformers", "accelerate",
                "imageio", "imageio-ffmpeg", "ftfy", "av", "spandrel"], check=True)

import numpy as np  # noqa: E402
import torch  # noqa: E402
import imageio.v3 as iio  # noqa: E402
from PIL import Image  # noqa: E402

CLIP = glob.glob("/kaggle/input/**/beat06-mothers-10s.mp4", recursive=True)[0]
REF_FRAME = 84                     # clip frame where all three stand clear (beat frame 100)
# boxes on the 1280x720 clip, from the Blender alpha of each woman at that frame
BOXES = {"left": (158, 364, 346, 719), "mid": (459, 352, 649, 719), "right": (804, 446, 948, 719)}
LOOKS = {
    "left": "a white linen blouse with puffed sleeves, a long grey wool skirt and a small white bonnet",
    "mid": "a white linen blouse, a long white apron over a grey skirt, dark hair in a bun",
    "right": "a blue-grey wool shawl over a white blouse, a white apron, light brown hair in a bun",
}

# ---- 1. references -------------------------------------------------------------------------------
frame = Image.fromarray(iio.imread(CLIP, index=REF_FRAME, plugin="pyav")).convert("RGB")
from diffusers import AutoPipelineForImage2Image, AutoencoderKL  # noqa: E402

vae = AutoencoderKL.from_pretrained("madebyollin/sdxl-vae-fp16-fix", torch_dtype=torch.float16)
sdxl = AutoPipelineForImage2Image.from_pretrained("stabilityai/stable-diffusion-xl-base-1.0", vae=vae,
                                                  torch_dtype=torch.float16, variant="fp16").to("cuda")
refs = []
for name, (x0, y0, x1, y1) in BOXES.items():
    pad = 24
    crop = frame.crop((max(0, x0 - pad), max(0, y0 - pad), min(1280, x1 + pad), 720))
    s = 1216 / crop.height
    crop = crop.resize((int(crop.width * s) // 8 * 8, 1216), Image.LANCZOS)
    canvas = Image.new("RGB", (832, 1216), (150, 150, 150))
    canvas.paste(crop, ((832 - crop.width) // 2, 0))
    canvas.save(f"{OUT}/ref_{name}_init.png")
    prompt = (f"35 mm film photograph, waist-up portrait of a young poor Austrian woman in Vienna 1846, "
              f"{LOOKS[name]}, worried expression, natural skin with pores and freckles, soft overcast "
              f"daylight, cobbled street behind her, realistic, sharp focus")
    neg = ("cartoon, CGI, 3D render, doll, porcelain skin, plastic, waxy, airbrushed, painting, "
           "illustration, deformed, extra fingers, blurry, text, watermark, modern clothes")
    img = sdxl(prompt=prompt, negative_prompt=neg, image=canvas, strength=0.55, num_inference_steps=40,
               guidance_scale=6.0, generator=torch.Generator("cuda").manual_seed(7)).images[0]
    img.save(f"{OUT}/ref_{name}.png")
    refs.append(f"{OUT}/ref_{name}.png")
    print("reference", name, flush=True)
del sdxl, vae
torch.cuda.empty_cache()

# ---- 2. VACE with references and overlapping pieces -----------------------------------------------
here = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else "/kaggle/working"
vace = os.path.join(here, "vace_refs_t4.py")
subprocess.run([sys.executable, vace, "--clip", CLIP, "--refs", *refs, "--out", f"{OUT}/vace_refs_480p.mp4"],
               check=True)

# ---- 3. 2x Real-ESRGAN, then 1920x1080 --------------------------------------------------------------
import urllib.request  # noqa: E402
from spandrel import ModelLoader  # noqa: E402

wpath = "/kaggle/working/RealESRGAN_x2plus.pth"
if not os.path.exists(wpath):
    urllib.request.urlretrieve(
        "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth", wpath)
model = ModelLoader().load_from_file(wpath).cuda().eval().half()
up = []
for f in iio.imiter(f"{OUT}/vace_refs_480p.mp4", plugin="pyav"):
    t = torch.from_numpy(f).permute(2, 0, 1)[None].half().cuda() / 255
    with torch.no_grad():
        y = model(t).clamp(0, 1)[0].permute(1, 2, 0).float().cpu().numpy()
    up.append(np.array(Image.fromarray((y * 255).round().astype(np.uint8)).resize((1920, 1080), Image.LANCZOS)))
iio.imwrite(f"{OUT}/vace_refs_1080p.mp4", np.stack(up), fps=16, codec="libx264", plugin="pyav")
print("wrote", f"{OUT}/vace_refs_1080p.mp4", len(up), "frames", flush=True)
