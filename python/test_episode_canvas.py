# -*- coding: utf-8 -*-
"""The Blender beats and the assembler must declare the same canvas.

`artemis_beats.py` renders each beat at `setup_scene(resolution_x=..., resolution_y=...)`
and `assemble_episode.py` composites at module-level `WIDTH`/`HEIGHT` with
`scale=...:force_original_aspect_ratio=decrease,pad=...`, which silently *downscales* a
larger beat instead of failing. Raising the beats to 720p while the assembler stayed at
640x360 would have produced an episode that looked untouched and cost a multi-hour render
to find out — so the agreement between the two files is asserted here, without starting
Blender.

The `layer` tests add the other half of the same hazard, seen from the source side: a
clip authored *above* the canvas is also thrown away by that scale+pad, and no existing
test noticed that the manim diagrams are rendered at 1920x1080 into a 1280x720 episode.

The walk over those clips takes its list of layers from the contract, and each layer's clips from
`workflow/episode.py`'s answer for that layer, because the archival layer's render directory is
contract data that only coincidentally matches the `renders/<layer>` convention: a loop naming three
layers probes three, reports a clean sheet, and never once looks at the footage most likely to
arrive at a scan resolution.
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from workflow.config import style_contract  # noqa: E402
from workflow.episode import layers, render_dir  # noqa: E402

CONTRACT = style_contract(ROOT)
ARTEMIS = ROOT / "work" / "episode-artemis-ii"


def assembler_canvas():
    import assemble_episode
    return assemble_episode.WIDTH, assemble_episode.HEIGHT




class TestEpisodeCanvas(unittest.TestCase):
    def test_the_rollout_names_the_canvas_it_measures(self):
        """Cost evidence labelled with a resolution it did not render is worthless later."""
        src = (ROOT / "tools" / "rollout_render.py").read_text(encoding="utf-8").splitlines()
        stale = [f"{i}: {line.strip()}" for i, line in enumerate(src, 1)
                 if re.search(r"720p|720", line) and "_pre-720-stash" not in line]
        self.assertEqual(stale, [],
                         "these labels still claim a canvas the rollout no longer renders; "
                         "the stash path is exempt because it names the era its evidence came from")

    def test_the_scene_card_ink_scales_with_the_canvas(self):
        """A card drawn larger than its design canvas must not lose relative ink."""
        import assemble_episode as A
        from PIL import Image
        # a scratch folder: writing into work/ changed committed files on every test run
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        out = Path(scratch.name)
        paths = []
        original = (A.WIDTH, A.HEIGHT, A.SCALE)
        cw, ch = contract_canvas()
        try:
            # Measured against the contract, not a hardcoded 1280: whatever the canvas
            # becomes, the card has to keep its proportions at it. The card loads the
            # house font from tools/fonts; a silent fallback to a fixed-size bitmap font
            # would shrink the ink and no absolute-pixel test would notice.
            for scale, size in ((1.0, (640, 360)), (cw / 640.0, (cw, ch))):
                A.WIDTH, A.HEIGHT, A.SCALE = size[0], size[1], scale
                p = A.make_scene_card(("u000", "process", "Trans-lunar injection",
                                       "Burn 1 | Coast | Burn 2"),
                                      out / f"ink-{size[0]}.png")
                paths.append(p)
        finally:
            # Leaving the module at 1280x720 makes every later canvas assertion
            # measure this test's scratch state instead of the assembler's.
            A.WIDTH, A.HEIGHT, A.SCALE = original
        ratios = []
        for p in paths:
            im = Image.open(p).convert("L")
            w, h = im.size
            ink = sum(1 for v in im.tobytes()[::7] if v > 40) / (w * h)
            ratios.append(ink)
        self.assertGreater(ratios[0], 0.0, "the card painted nothing at 640x360")
        # Same proportions at both sizes: within 20%, not half.
        self.assertLess(abs(ratios[1] / ratios[0] - 1.0), 0.2,
                        f"card ink changed with the canvas: {ratios}")


def contract_canvas():
    style = json.loads((ROOT / "workflow" / "style.json").read_text(encoding="utf-8"))
    return style["canvas"]["width"], style["canvas"]["height"]


def layer_clips(episode=ARTEMIS):
    """Every clip of every declared layer, keyed by layer, at the directory that layer owns.

    A layer with nothing in it is an empty list rather than a missing key: "this film ships no
    archival shots" and "this walk never looked for them" are different statements, and only the
    first is a measurement.
    """
    return {layer: sorted(render_dir(episode, layer, CONTRACT).glob("*.mp4"))
            for layer in layers(CONTRACT)}


def probe_size(clip):
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", str(clip)],
        capture_output=True, text=True)
    w, h = (int(v) for v in proc.stdout.strip().split(",")[:2])
    return w, h


def layer_sizes(episode=ARTEMIS):
    """Native size of every rendered source clip keyed by size, plus the walk that found them."""
    walked, found = layer_clips(episode), {}
    for layer, clips in walked.items():
        for clip in clips:
            found.setdefault(probe_size(clip), []).append(f"{layer}/{clip.name}")
    return found, walked


def discarded(sizes):
    """The clips whose authored pixels the contract's scale+pad throws away."""
    cw, ch = contract_canvas()
    return {size: names for size, names in sizes.items()
            if size[0] > cw or size[1] > ch}


class TestLayersFitTheContract(unittest.TestCase):
    """A clip authored above the canvas is downscaled into mush, silently.

    The contract's own rule says a canvas mismatch is "a silent downscale, not an error",
    so nothing else in the suite treats it as one — including when the whole manim layer
    is 1920x1080 and the episode ships at 1280x720.
    """

    def test_the_assembler_declares_the_contract_canvas(self):
        self.assertEqual(assembler_canvas(), contract_canvas())

    def test_no_source_layer_is_authored_above_the_contract_canvas(self):
        sizes, _ = layer_sizes()
        oversized = discarded(sizes)
        self.assertFalse(
            oversized,
            f"canvas {contract_canvas()} discards authored pixels: "
            + "; ".join(f"{w}x{h} -> {', '.join(names[:3])}"
                        for (w, h), names in oversized.items()))

    def test_the_layer_walk_covers_every_layer_the_contract_declares(self):
        """Four layers in the taxonomy, four keys out of the walk. A `for` loop naming three of
        them measures the three it named and reports no finding, which reads as the fourth having
        been checked and passed."""
        _, walked = layer_sizes()
        self.assertEqual(set(walked), set(layers(CONTRACT)))
        self.assertGreater(len(walked), 3,
                           "the archival layer is not being walked at all, so nothing below can "
                           "see an oversized scan sitting in its directory")

    def test_a_layer_this_film_ships_without_is_still_walked_at_its_own_path(self):
        """The missing-layer case, made explicit: an empty layer must be empty *at the directory
        the contract gives it*, because a walk that looks in `renders/archive` while the ingest
        writes to the contract's path reports a clean, empty, wrong directory."""
        _, walked = layer_sizes()
        for layer, clips in walked.items():
            directory = render_dir(ARTEMIS, layer, CONTRACT)
            self.assertEqual([c.name for c in clips],
                             sorted(p.name for p in directory.glob("*.mp4")),
                             f"{layer} was measured somewhere other than {directory}")
            if not clips:
                self.assertFalse(list(directory.glob("*")),
                                 f"{layer} holds files but reported no clips")

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not on PATH")
    def test_an_oversized_archival_clip_is_the_rule_being_able_to_fire(self):
        """The guard, not the fixture: a 3840x2160 one-frame stand-in dropped at the archival
        layer's contract path must reach `discarded()`. It fails against a three-name loop, which
        is the whole reason this file stopped naming layers — and it is what makes the clean verdict
        on Artemis II above a measurement rather than an absence of evidence."""
        _, walked = layer_sizes()
        self.assertTrue(walked.get("archive") is not None)
        with tempfile.TemporaryDirectory() as tmp:
            directory = render_dir(Path(tmp), "archive", CONTRACT)
            directory.mkdir(parents=True)
            clip = directory / "kubrick-scan.mp4"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                            "-i", "color=c=0x808080:s=3840x2160:r=1", "-frames:v", "1",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
                            str(clip)], check=True)
            sizes, walked = layer_sizes(Path(tmp))
        self.assertEqual([n for names in sizes.values() for n in names],
                         [f"archive/{clip.name}"])
        flagged = discarded(sizes)
        self.assertEqual(list(flagged.values()), [[f"archive/{clip.name}"]],
                         "the archival layer is walked but its oversize is not judged")


if __name__ == "__main__":
    unittest.main()
