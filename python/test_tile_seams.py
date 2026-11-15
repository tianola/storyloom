"""Tests for the tile seam repair.

The owned tiles came out of FLUX schnell, which is excellent at "material scan" and useless
at "edges match perfectly". Measured before this tool existed, mli-silver-s523 jumped
117/255 from its last row to its first against a natural column-to-column step of 8, and
hull-panel-s307 jumped 53 against 0.4 — so every wrapped body (Orion's service module, the
SLS casings, Gateway's hull) drew a hard grid line no amount of surfacing geometry could
hide. regolith-s214 jumps 24 against 16, which is why it was left alone.

These tests hold the line on the repair: the wrap must reach natural step levels, the
grain must survive the band that gets rebuilt, and the rest of the tile must be untouched
so the recorded seed still describes the asset.
"""
import sys
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.tile_seams import make_seamless, seam_report  # noqa: E402

TILES = ROOT / "media" / "pbr"
SURFACES = ROOT / "tools" / "blender" / "techniques" / "surfaces.py"
# The three hardware tiles that measured a wrap step 4-130x their own interior contrast.
REPAIRED = ["hull-panel", "mli-kapton", "mli-silver"]


def luma(a):
    return np.asarray(Image.open(a).convert("L"), dtype=np.float64)


def pair(stem):
    """(source, repaired) for one tile family."""
    files = sorted(TILES.glob(f"{stem}-s*.webp"))
    fixed = [p for p in files if p.stem.endswith("-seam")]
    source = [p for p in files if p not in fixed]
    return source[0], fixed[0]


def bad_tile(size=256, start=(71, 33)):
    """A texture that is locally continuous everywhere and jumps where it wraps in both axes.

    Cutting a square out of a field whose periods (500 and 12 across, 200 and 10 down) do not
    divide `size` is exactly the defect the shipped tiles have: nothing inside is wrong, and the
    two edges disagree. Rolling a genuinely periodic image would not do — a cyclic shift of a
    seamless tile is still seamless, and the test would pass against a tool that changed nothing.
    """
    x = np.arange(start[0], start[0] + size, dtype=float)
    y = np.arange(start[1], start[1] + size, dtype=float)
    fx = (120.0 + 60.0 * np.sin(2 * np.pi * x / 500.0 + 0.3)
          + 25.0 * np.sin(2 * np.pi * x / 12.0 + 0.7))
    fy = 30.0 * np.sin(2 * np.pi * y / 200.0 + 0.3) + 18.0 * np.sin(2 * np.pi * y / 10.0)
    img = fx[None, :, None] + fy[:, None, None]
    return np.concatenate([img] * 3, axis=2)


class SyntheticStep(unittest.TestCase):
    """The property that makes the repair safe to run at all."""

    def test_the_fixture_is_seamless_in_the_middle_and_broken_at_the_wrap(self):
        report = seam_report(bad_tile())
        self.assertGreater(report["wrap_v"], 3.0 * report["interior_step"])
        self.assertGreater(report["wrap_v"], 10.0)
        self.assertGreater(report["wrap_h"], 10.0)

    def test_the_wrap_jump_is_reduced_to_the_texture_s_own_step(self):
        out = make_seamless(bad_tile(), band=48)
        report = seam_report(out)
        ceiling = 2.0 * report["interior_step"] + 0.5
        self.assertLessEqual(report["wrap_v"], ceiling)
        self.assertLessEqual(report["wrap_h"], ceiling)
        # Measured: the repaired band's worst column step is 2.0x the texture's own mean step,
        # against a fixture whose worst step is 12x it — the band must not become the new line.
        self.assertLessEqual(report["worst_column_step"], 2.5 * report["interior_step"])

    def test_pixels_outside_the_rebuilt_cross_are_untouched(self):
        a = np.random.default_rng(4).random((256, 256, 3)) * 255.0
        out = make_seamless(a, band=48)
        h, w = a.shape[:2]
        rolled = np.roll(np.roll(a, h // 2, axis=0), w // 2, axis=1)
        keep = np.ones((h, w), bool)
        keep[:, w // 2 - 24:w // 2 + 24] = False
        keep[h // 2 - 24:h // 2 + 24] = False
        self.assertLess(np.abs(out - rolled)[keep].max(), 1e-9)

    def test_grain_survives_the_rebuilt_band(self):
        """A blurred stripe is a regression dressed as a fix, so the band keeps its texture."""
        rng = np.random.default_rng(9)
        a = rng.random((256, 256, 3)) * 255.0
        out = make_seamless(a, band=48)
        h, w = a.shape[:2]
        band = out[h // 2 - 8:h // 2 + 8, w // 2 - 8:w // 2 + 8]
        plain = out[h // 2 - 8:h // 2 + 8, w // 2 - 96:w // 2 - 80]
        self.assertGreater(band.std(), 0.45 * plain.std())



class ShippedTiles(unittest.TestCase):
    def test_the_repaired_derivatives_wrap(self):
        for stem in REPAIRED:
            with self.subTest(tile=stem):
                _, fixed = pair(stem)
                report = seam_report(luma(fixed))
                self.assertLessEqual(report["wrap_v"],
                                     max(2.0 * report["interior_step"], 1.0))
                self.assertLessEqual(report["wrap_h"],
                                     max(2.0 * report["interior_step"], 1.0))
                self.assertLess(report["wrap_v"], 20.0)
                self.assertLess(report["wrap_h"], 20.0)

    def test_repairing_did_not_leave_the_wrap_worse_than_half_its_source(self):
        for stem in REPAIRED:
            with self.subTest(tile=stem):
                source, fixed = pair(stem)
                self.assertLess(seam_report(luma(fixed))["wrap"],
                                0.5 * seam_report(luma(source))["wrap"])

    def test_surfaces_points_at_the_seamless_derivatives(self):
        text = SURFACES.read_text(encoding="utf-8")
        for stem in REPAIRED:
            with self.subTest(tile=stem):
                self.assertIn(f"{stem}-", text)
        for line in text.splitlines():
            if 'tile=TILES / "' not in line:
                continue
            for stem in REPAIRED:
                if f"{stem}-" in line:
                    self.assertIn("-seam.webp", line,
                                f"SURFACES still uses the unrepaired {stem} tile")

    def test_every_surface_tile_exists(self):
        text = SURFACES.read_text(encoding="utf-8")
        names = [s for s in text.split('tile=TILES / "')[1:] for s in [s.split('"')[0]]]
        # Five shipped photographs, not five palette entries: cabin_deck is the hull-panel
        # tile read as an unbleached interior. The invariant this guards is that no new
        # tile file enters the palette without going through the seam repair and the
        # licence ledger, and a palette entry sharing an existing tile does not break it.
        self.assertEqual(len(set(names)), 5)
        for name in names:
            with self.subTest(tile=name):
                self.assertTrue((TILES / name).exists(), f"missing {name}")


if __name__ == "__main__":
    unittest.main()
