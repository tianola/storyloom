"""Measure whether a per-frame SD img2img pass can be bolted onto this pipeline at all.

The user asked for video-to-video («θέλω το video-to-video, να γίνεται χαμένο και να
καταλαβαίνει ο άλλος εύκολα τι βλέπει»). Two halves of that sentence pull against each
other, and only a measurement settles it: a diffusion pass at any useful strength
invents texture, and invented texture that changes from frame to frame is flicker —
the opposite of "easy to read what I'm looking at".

What is already known, from the verified OpenVINO run on this card (D-018):
512x512 txt2img is **0.43 s/it** warm. So the arithmetic for the whole episode is
12 480 frames x 20 steps x 0.43 s = **~30 h**, before counting that img2img encodes the
source too. Episode-wide v2v is therefore out on this hardware, and this probe exists to
answer the only question that is still open: on a *hero insert*, does the result look
better, and how much does it flicker?

Flicker is measured, not judged: mean absolute difference between consecutive frames,
generated against original. A ratio near 1.0 means the pass is temporally as stable as
the render; much above it and the shot boils.

Usage (only with the GPU free — it loads a 2 GB fp32 model into a 6 GB card):
    python tools/v2v_probe.py --beat gateway --start 200 --frames 12
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import statistics
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BEATS = ROOT / "work" / "episode-artemis-ii" / "renders" / "3d"
QC = ROOT / "work" / "episode-artemis-ii" / "qc"
WEBUI = Path(r"C:\Program Files (x86)\AI QuickSet_Intel\stable-diffusion-webui")
PYTHON = WEBUI / "venv" / "Scripts" / "python.exe"
PORT = 7861
API = f"http://127.0.0.1:{PORT}/sdapi/v1"

# The look the pass is chasing: real footage of hardware in sunlight, not a render of it.
PROMPT = ("photorealistic space photograph, NASA documentary still, "
          "multi-layer insulation foil, machined aluminium hull, hard sunlight, "
          "deep black space, sharp focus, high detail")
NEGATIVE = ("cartoon, anime, drawing, sketch, text, watermark, logo, blurry, "
            "deformed, extra objects, plastic, lowres")


def b64(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def post(route: str, payload: dict) -> dict:
    req = urllib.request.Request(f"{API}/{route}", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as resp:
        return json.loads(resp.read())


def wait_for_api(proc, limit=900):
    t0 = time.time()
    while time.time() - t0 < limit:
        if proc.poll() is not None:
            raise RuntimeError(f"webui exited {proc.returncode}; see {QC / 'v2v-webui.log'}")
        try:
            post("options", {})
            return time.time() - t0
        except (urllib.error.URLError, ConnectionError):
            time.sleep(5)
    raise RuntimeError("webui never answered")


def serve_webui() -> subprocess.Popen:
    """Start A1111 headless with the API on.

    Three things this has to get right or it hangs instead of failing: a regular empty
    file on stdin (a console stdin makes an isatty-guarded prompt block forever in a
    window nobody can see), the session's proxy variables cleared (`NO_PROXY` carrying
    `[::1]` breaks gradio's import), and the OpenVINO device exported, because the
    script's own default is CPU. `--nowebui` is deliberately NOT used: it makes launch.py
    read commands from stdin, and an empty stdin file means it exits before serving.
    """
    empty = QC / "v2v-stdin-empty.txt"
    empty.write_bytes(b"")
    env = {k: v for k, v in os.environ.items()
           if not k.lower().startswith(("http_proxy", "https_proxy", "no_proxy", "all_proxy"))}
    root = WEBUI.parent
    env.update({
        "PATH": ";".join([str(root / "python"), str(root / "python" / "Scripts"),
                          str(root / "git" / "cmd"), env["PATH"]]),
        "USE_OPENVINO": "1",
        "OPENVINO_TORCH_BACKEND_DEVICE": "GPU",
        "PYTORCH_TRACING_MODE": "TORCHFX",
        "PIP_CONSTRAINT": r"C:\ProgramData\qoder\sdweb-constraints.txt",
    })
    log = open(QC / "v2v-webui.log", "w", encoding="utf-8")
    return subprocess.Popen(
        [str(PYTHON), "launch.py",
         "--skip-torch-cuda-test", "--precision", "full", "--no-half",
         "--api", "--listen", "127.0.0.1", "--port", str(PORT)],
        cwd=str(WEBUI), env=env, stdout=log, stderr=subprocess.STDOUT,
        stdin=open(str(empty), "r"))


def flicker(paths: list[Path]) -> float:
    """Mean absolute luma difference between consecutive frames, 0..255."""
    frames = [np.asarray(Image.open(p).convert("L"), dtype=np.int16) for p in paths]
    return float(np.mean([np.abs(b - a).mean() for a, b in zip(frames, frames[1:])])) \
        if len(frames) > 1 else 0.0


def probe(beat: str, start: int, n: int, denoise: float, steps: int) -> int:
    src = [BEATS / beat / f"frame-{i:04d}.png" for i in range(start, start + n)]
    missing = [p for p in src if not p.exists()]
    if missing:
        print(f"no frames on disk for {beat} at {start}..{start+n-1} ({len(missing)} missing)")
        return 2
    out = QC / f"v2v-{beat}-{start}"
    out.mkdir(parents=True, exist_ok=True)

    proc = serve_webui()
    try:
        up = wait_for_api(proc)
        print(f"webui up in {up:.0f}s (first request also pays the graph compile)", flush=True)
        gen = []
        times = []
        for i, p in enumerate(src):
            img = Image.open(p)
            feed = p
            if img.size != (832, 464):
                feed = out / f"src-{p.name}"
                img.resize((832, 464), Image.LANCZOS).save(feed)
            t0 = time.time()
            r = post("img2img", {
                "init_images": [b64(feed)],
                "prompt": PROMPT, "negative_prompt": NEGATIVE,
                "denoising_strength": denoise, "steps": steps,
                "width": 832, "height": 464, "sampler_name": "Euler a",
                "cfg_scale": 7.0, "batch_size": 1,
                "script_1": "scripts/openvino_accelerate.py", "script_arg_1": 2,
            })
            secs = time.time() - t0
            dest = out / src[i].name
            dest.write_bytes(base64.b64decode(r["images"][0].split(",", 1)[1]))
            print(f"  frame {i + 1}/{n}: {secs:.1f}s ({secs / steps:.2f} s/it)", flush=True)
            times.append(secs)
            gen.append(dest)
        # The first request pays the OpenVINO graph compile; projecting the episode from
        # it would overstate the cost by an order of magnitude.
        warm = statistics.fmean(times[1:]) if len(times) > 1 else times[0]
        a, b = flicker(src), flicker(gen)
        print(f"\nmeasured {len(times)} frames at 832x464 / {steps} steps, denoise {denoise}")
        print(f"  warm {warm:.1f} s/frame -> the 12480-frame episode would take "
              f"{12480 * warm / 3600:.1f} h on this card")
        print(f"  flicker (mean |Δ| between consecutive frames): "
              f"original {a:.2f} vs generated {b:.2f} = {b / max(a, 1e-6):.2f}x")
        print(f"  frames: {out}")
    finally:
        proc.terminate()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--beat", default="gateway")
    ap.add_argument("--start", type=int, default=200)
    ap.add_argument("--frames", type=int, default=12)
    ap.add_argument("--denoise", type=float, default=0.30)
    ap.add_argument("--steps", type=int, default=20)
    a = ap.parse_args()
    return probe(a.beat, a.start, a.frames, a.denoise, a.steps)


if __name__ == "__main__":
    raise SystemExit(main())
