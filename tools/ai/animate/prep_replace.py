"""Wan2.2-Animate inputs for one character in "replace" mode, from our own Blender passes.

Wan's preprocessing finds the character with a pose detector and SAM2, which is made for one-person
videos. We render the character alone (RGBA) from Blender instead, so the pose detector sees one person
and the mask is the exact alpha. This writes, at 1280x720 and the clip's frame rate:
  src_pose.mp4   the skeleton drawn by Wan's own code
  src_face.mp4   512x512 face crops
  src_bg.mp4     the full shot with the character's (enlarged) mask blacked out
  src_mask.mp4   that mask, white = character

Usage:
  python prep_replace.py --solo DIR_OF_RGBA_PNGS --full FULL_SHOT.mp4 --ckpt PROCESS_CHECKPOINT_DIR
                         --wan WAN2.2_REPO --out OUT_DIR [--fps 30]
"""
import argparse
import glob
import os
import sys

import cv2
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--solo", required=True, help="folder of RGBA PNGs, or a video of the character on grey")
ap.add_argument("--alpha", help="with a --solo video: the alpha as a grey video")
ap.add_argument("--full", required=True)
ap.add_argument("--ckpt", required=True)
ap.add_argument("--wan", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--fps", type=float, default=30)
ap.add_argument("--grey", type=int, default=128, help="backdrop for the pose detector")
ap.add_argument("--iterations", type=int, default=3)
ap.add_argument("--k", type=int, default=7)
args = ap.parse_args()

sys.path.insert(0, os.path.join(args.wan, "wan", "modules", "animate", "preprocess"))
from pose2d import Pose2d  # noqa: E402
from pose2d_utils import AAPoseMeta  # noqa: E402
from utils import get_face_bboxes, get_aug_mask, get_mask_body_img  # noqa: E402
from human_visualization import draw_aapose_by_meta_new  # noqa: E402

try:
    import moviepy.editor as mpy
except ImportError:
    import moviepy as mpy

os.makedirs(args.out, exist_ok=True)

def read_video(path):
    cap, out = cv2.VideoCapture(path), []
    while True:
        ok, fr = cap.read()
        if not ok:
            return out
        out.append(fr[:, :, ::-1].copy())


# the character alone, on grey, and its alpha: a folder of RGBA PNGs, or two videos
# (--solo the character on grey, --alpha its alpha as grey levels)
solo, alpha = [], []
if os.path.isdir(args.solo):
    for p in sorted(glob.glob(os.path.join(args.solo, "*.png"))):
        im = cv2.imread(p, cv2.IMREAD_UNCHANGED)          # BGRA
        a = im[:, :, 3:4].astype(np.float32) / 255.0
        rgb = im[:, :, 2::-1].astype(np.float32)
        solo.append((rgb * a + args.grey * (1 - a)).astype(np.uint8))
        alpha.append((im[:, :, 3] > 127).astype(np.uint8))
else:
    solo = read_video(args.solo)
    alpha = [(f[:, :, 0] > 127).astype(np.uint8) for f in read_video(args.alpha)]

# the full shot, frame for frame
full = read_video(args.full)
n = min(len(solo), len(full))
print(f"{len(solo)} solo frames, {len(full)} full frames -> {n}")
solo, alpha, full = solo[:n], alpha[:n], full[:n]
H, W = solo[0].shape[:2]
assert full[0].shape[:2] == (H, W), (full[0].shape, (H, W))
assert H % 16 == 0 and W % 16 == 0, (W, H)

pose2d = Pose2d(checkpoint=os.path.join(args.ckpt, "pose2d", "vitpose_h_wholebody.onnx"),
                detector_checkpoint=os.path.join(args.ckpt, "det", "yolov10m.onnx"))
metas = pose2d(solo)

faces = []
for i, meta in enumerate(metas):
    x1, x2, y1, y2 = get_face_bboxes(meta["keypoints_face"][:, :2], scale=1.3, image_shape=(H, W))
    faces.append(cv2.resize(full[i][y1:y2, x1:x2], (512, 512)))

poses = []
for meta in metas:
    poses.append(draw_aapose_by_meta_new(np.zeros((H, W, 3), np.uint8), AAPoseMeta.from_humanapi_meta(meta)))

bgs, masks = [], []
for fr, m in zip(full, alpha):
    _, body = get_mask_body_img(fr, m, iterations=args.iterations, k=args.k)
    aug = get_aug_mask(body, w_len=1, h_len=1)
    bgs.append((fr * (1 - aug[:, :, None])).astype(np.uint8))
    masks.append(np.repeat((aug * 255).astype(np.uint8)[:, :, None], 3, axis=2))


def write(frames, name):
    path = os.path.join(args.out, name)
    mpy.ImageSequenceClip(frames, fps=args.fps).write_videofile(path, logger=None)
    print("wrote", path, len(frames))


write(poses, "src_pose.mp4")
write(faces, "src_face.mp4")
write(bgs, "src_bg.mp4")
write(masks, "src_mask.mp4")
cv2.imwrite(os.path.join(args.out, "check_frame0.png"),
            np.concatenate([full[0], poses[0], masks[0]], axis=1)[:, :, ::-1])
