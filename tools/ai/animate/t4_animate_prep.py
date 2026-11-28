"""On a free Kaggle T4: everything Wan2.2-Animate needs, so the TPU session only generates.

Inputs (private dataset): beat06-mothers-10s.mp4, solo_mid_rgb.mp4, solo_mid_alpha.mp4, still_mid.png.
Writes /kaggle/working/animate_in/: src_pose.mp4, src_face.mp4, src_bg.mp4, src_mask.mp4, check_frame0.png,
ref_seed*.png (pick one as the reference), and a zip of it all.
"""
import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = "/kaggle/working/animate_in"
os.makedirs(OUT, exist_ok=True)


def run(*cmd):
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


run(sys.executable, "-m", "pip", "-q", "install", "onnxruntime-gpu", "moviepy", "loguru", "decord",
    "diffusers>=0.34", "transformers", "accelerate", "huggingface_hub")
if not os.path.isdir("/kaggle/working/Wan2.2"):
    run("git", "clone", "--depth", "1", "https://github.com/Wan-Video/Wan2.2.git", "/kaggle/working/Wan2.2")

from huggingface_hub import snapshot_download  # noqa: E402

ckpt = snapshot_download("Wan-AI/Wan2.2-Animate-14B", local_dir="/kaggle/working/animate_ckpt",
                         allow_patterns=["process_checkpoint/det/*", "process_checkpoint/pose2d/*"])
ckpt = os.path.join(ckpt, "process_checkpoint")


def find(name):
    return glob.glob(f"/kaggle/input/**/{name}", recursive=True)[0]


run(sys.executable, os.path.join(HERE, "prep_replace.py"),
    "--solo", find("solo_mid_rgb.mp4"), "--alpha", find("solo_mid_alpha.mp4"),
    "--full", find("beat06-mothers-10s.mp4"), "--ckpt", ckpt, "--wan", "/kaggle/working/Wan2.2",
    "--out", OUT, "--fps", "30")

run(sys.executable, os.path.join(HERE, "make_reference.py"), "--png", find("still_mid.png"), "--out", OUT,
    "--prompt", "35 mm film photograph, waist-up portrait of a young poor Austrian woman in Vienna 1846, "
    "white linen blouse, long white apron over a grey skirt, dark hair in a bun, worried expression, "
    "natural skin with pores, soft overcast daylight, plain grey backdrop, realistic, sharp focus")
run("bash", "-c", f"cd {OUT} && zip -q -r /kaggle/working/animate_in.zip . && ls -la {OUT}")
