"""Repair a near-tileable texture so that it actually wraps.

    python tools/tile_seams.py --check                 # measure every tile in media/pbr
    python tools/tile_seams.py --write mli-silver-s523  # emit <stem>-seam.webp

FLUX schnell answers "seamless tileable material texture, edges match perfectly" with an
excellent material and a broken promise. Measured across the wrap, mli-silver-s523 jumps
117/255 from its last row to its first and hull-panel-s307 jumps 53, against a natural
adjacent-column step of 8 and 0.4 respectively — a hard grid line wherever the tile repeats,
which is what drew the "knit sweater" verdict on Orion's MLI and the vertical streaks on the
SLS casings. regolith-s214 jumps 24 against a natural step of 16, so its grain hides the wrap
and it is left alone.

Why rolling comes first: the discontinuity sits between the last and the first column, where
nothing can be reconstructed, because there is no correct content outside the tile. Rolling by
half the image moves that jump into the middle of the image, where both sides of it are real
pixels — and the borders themselves become ordinary interior steps, so the tile wraps by
construction once the cross is rebuilt.

How the cross is rebuilt: the interior of each band is replaced by the harmonic continuation
of its two boundary lines, computed per Fourier mode of the perpendicular axis, where a
feature of wavelength L penetrates about L/2pi into the band. That is what an unbroken surface
would do across a narrow strip: the quilt cells and panel lines reach in and fade out, while
the 2-pixel grain dies within a pixel of the edge. So the band ends up smooth, and a blur
stripe is a regression dressed as a fix — the tile's own high frequency, shifted by an odd
number of rows and columns so it cannot reinsert the seam it replaced, is laid back over it.

Nothing outside the cross is modified, so the asset keeps its character and the seed recorded
in media/pbr/LICENSES.md still describes it.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
TILES = ROOT / "media" / "pbr"
# The wrap is only a defect when it dwarfs the texture's own local contrast, so both are
# reported together rather than the raw difference alone.
SEAM_TO_SOURCE = "-seam"


def load(path):
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float64)


def save(path, a):
    Image.fromarray(np.clip(a, 0.0, 255.0).round().astype(np.uint8)).save(
        path, format="WEBP", quality=92, method=6)


def grey(a):
    g = np.asarray(a, dtype=np.float64)
    if g.ndim == 3:
        g = g[..., 0] * 0.299 + g[..., 1] * 0.587 + g[..., 2] * 0.114
    return g


def seam_report(a):
    """Wrap jump, natural local contrast, and the worst column step anywhere in the image."""
    g = grey(a)
    h, w = g.shape
    wrap_v = float(np.abs(g[:, -1] - g[:, 0]).mean())
    wrap_h = float(np.abs(g[-1] - g[0]).mean())
    step_x = np.abs(np.diff(g, axis=1)).mean()
    step_y = np.abs(np.diff(g, axis=0)).mean()
    columns = np.abs(np.diff(np.concatenate([g, g[:, :1]], axis=1), axis=1)).mean(axis=0)
    return {"wrap": max(wrap_v, wrap_h), "wrap_v": wrap_v, "wrap_h": wrap_h,
            "interior_step": float((step_x + step_y) / 2.0),
            "worst_column_step": float(columns.max())}


def _blur(a, sigma):
    """Periodic Gaussian, in the Fourier domain: a tile has no edge to be nervous about."""
    h, w = a.shape[:2]
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.fftfreq(w)[None, :]
    gain = np.exp(-2.0 * (math.pi ** 2) * sigma ** 2 * (fy ** 2 + fx ** 2))
    full = np.fft.fft2(a, axes=(0, 1)) * gain[:, :, None]
    return np.fft.ifft2(full, axes=(0, 1)).real


def _fill_strip(a, i0, i1, axis):
    """Replace the open strip between two boundary lines by their harmonic continuation."""
    n = i1 - i0
    if n < 2:
        return
    b = a if axis == 1 else a.swapaxes(0, 1)
    m = b.shape[0]
    lo, hi = np.fft.fft(b[:, i0], axis=0), np.fft.fft(b[:, i1], axis=0)
    k = 2.0 * math.pi * np.abs(np.fft.fftfreq(m))[:, None] * n
    t = np.arange(1, n)[None, :] / n
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        denom = 1.0 - np.exp(-2.0 * k)
        wl = np.exp(-k * t) * (1.0 - np.exp(-2.0 * k * (1.0 - t))) / denom
        wr = np.exp(-k * (1.0 - t)) * (1.0 - np.exp(-2.0 * k * t)) / denom
    flat = (k[:, 0:1] == 0.0)
    wl = np.where(flat, 1.0 - t, wl)
    wr = np.where(flat, t, wr)
    b[:, i0 + 1:i1] = np.fft.ifft(lo[:, None, :] * wl[:, :, None]
                                  + hi[:, None, :] * wr[:, :, None], axis=0).real


def make_seamless(a, band=48, detail_sigma=2.0, grain=0.85, passes=2):
    """Return a copy of `a` that wraps; the cross of width `band` is rebuilt, rest untouched."""
    out = np.asarray(a, dtype=np.float64)
    h, w = out.shape[:2]
    out = np.roll(np.roll(out, h // 2, axis=0), w // 2, axis=1)
    half = band // 2
    cx, cy = w // 2, h // 2
    source = out.copy()
    for _ in range(passes):
        _fill_strip(out, cx - half, cx + half, 1)
        _fill_strip(out, cy - half, cy + half, 0)
    # The grain is the detail of the *repaired* image, which has no seam left in it, shifted by
    # an odd number of rows and columns so the band is filled from somewhere else in the tile.
    # Taking it from the source instead would move the seam's own high frequency into the band
    # and draw the line back, one quarter of the way across the image.
    grain_field = out - _blur(out, detail_sigma)
    grain_field = np.roll(np.roll(grain_field, h // 3, axis=0), (3 * w) // 7, axis=1)
    out[:, cx - half:cx + half] += grain * grain_field[:, cx - half:cx + half]
    out[cy - half:cy + half] += grain * grain_field[cy - half:cy + half]
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("tiles", nargs="*", help="tile file stems (default: all in media/pbr)")
    ap.add_argument("--band", type=int, default=48)
    ap.add_argument("--write", action="store_true", help="emit <stem>-seam.webp derivatives")
    ap.add_argument("--check", action="store_true", help="report the wrap for every tile")
    args = ap.parse_args(argv)
    paths = [TILES / f"{t}.webp" for t in args.tiles] or sorted(TILES.glob("*.webp"))
    for path in paths:
        report = seam_report(load(path))
        print(f"{path.stem:26s} wrap={report['wrap']:7.2f} v={report['wrap_v']:7.2f} "
              f"h={report['wrap_h']:7.2f} local={report['interior_step']:6.2f} "
              f"ratio={report['wrap'] / max(report['interior_step'], 0.05):6.1f}")
        if args.write:
            stem = path.stem
            stem = stem.removesuffix(SEAM_TO_SOURCE)
            fixed = make_seamless(load(path), band=args.band)
            save(TILES / f"{stem}{SEAM_TO_SOURCE}.webp", fixed)
            after = seam_report(fixed)
            print(f"{'':26s} -> wrap={after['wrap']:6.2f} "
                  f"local={after['interior_step']:5.2f} worst_col={after['worst_column_step']:5.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
