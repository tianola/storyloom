#!/bin/bash
# Wan2.2-Animate-14B (Apache-2.0) in "replace" mode on a free Kaggle TPU v5e-8, through Google's
# MaxDiffusion (JAX). Inputs come from prep_replace.py and make_reference.py.
#   bash run_animate_tpu.sh INPUT_DIR REF_PNG OUT_DIR [NUM_FRAMES] [FPS]
# INPUT_DIR holds src_pose.mp4, src_face.mp4, src_bg.mp4, src_mask.mp4.
set -euo pipefail
IN=$1; REF=$2; OUT=$3; FRAMES=${4:-300}; FPS=${5:-30}
WORK=${WORK:-/kaggle/working}
export HF_HUB_CACHE=${HF_HUB_CACHE:-/tmp/hf}
export HF_HUB_ENABLE_HF_TRANSFER=1

if [ ! -d "$WORK/maxdiffusion" ]; then
  git clone --depth 1 https://github.com/AI-Hypercomputer/maxdiffusion.git "$WORK/maxdiffusion"
  cd "$WORK/maxdiffusion"
  python -m pip install -q -U uv hf_transfer
  UV_SYSTEM_PYTHON=1 python -m uv pip install -q \
      -r dependencies/requirements/generated_requirements/requirements.txt
  UV_SYSTEM_PYTHON=1 python -m uv pip install -q 'jax[tpu]>0.4' \
      -f https://storage.googleapis.com/jax-releases/libtpu_releases.html
  python -m pip install -q -e . --no-deps
fi
cd "$WORK/maxdiffusion"
python -c "import jax; print(jax.devices())"

LIBTPU_INIT_ARGS="--xla_tpu_enable_async_collective_fusion=true \
--xla_tpu_enable_async_collective_fusion_fuse_all_reduce=true \
--xla_tpu_enable_async_collective_fusion_multiple_steps=true \
--xla_tpu_overlap_compute_collective_tc=true --xla_enable_async_all_reduce=true" \
python src/maxdiffusion/generate_wan_animate.py src/maxdiffusion/configs/base_wan_animate.yml \
  run_name=storyloom_animate output_dir="$OUT" seed=1846 \
  mode=replace reference_image_path="$REF" \
  pose_video_path="$IN/src_pose.mp4" face_video_path="$IN/src_face.mp4" \
  background_video_path="$IN/src_bg.mp4" mask_video_path="$IN/src_mask.mp4" \
  height=720 width=1280 num_frames="$FRAMES" fps="$FPS" \
  prompt="A young Austrian woman in 1846, plain linen dress, white apron and bonnet, standing in a cobbled street at dawn, photorealistic 35 mm film, natural skin, soft light"
