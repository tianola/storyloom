# -*- coding: utf-8 -*-
"""The look pass is the difference between a 3D render and a shot.

Everything upstream produces is *clean*: flat black space, sharp polygon edges, no
atmosphere, no lens. That cleanliness is exactly what reads as fake next to real footage,
which has halated highlights, grain, and corners that fall off. `tools/look_pass.py` adds
those three things plus a contrast grade in one ffmpeg pass over the assembled master.

Two failure modes are pinned here because both were live hazards in this pipeline:

* The pass must not resize. The assembler already had a `scale=...:force_original_aspect
  _ratio=decrease,pad=...` chain that silently rescaled the beats, and a look pass that
  rescales again would cost the episode its legibility — the one thing the user asked to
  keep («να καταλαβαίνει ο άλλος εύκολα τι βλέπει»).
* The pass must run on the assembled video, not on the per-utterance segments. Segments
  are a cache keyed on their own filename; grading inside the cache would re-encode all
  ~400 of them, double-compress every slice, and make an already-long rollout longer.
"""
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import look_pass as L  # noqa: E402


def knots(vf):
    body = re.search(r"curves=master='([^']*)'", vf).group(1)
    return [tuple(float(v) for v in pair.split("/")) for pair in body.split()]


class TestFilterGraph(unittest.TestCase):
    def setUp(self):
        self.vf = L.build_vf()

    def test_the_picture_is_never_resized(self):
        self.assertNotIn("scale=", self.vf)
        self.assertNotIn("pad=", self.vf)

    def test_bloom_draws_only_from_the_highlights(self):
        # A whole-frame screen-blur washes mid-grey space into milk and undoes the
        # contrast the grade just bought, so the curve must floor everything below the
        # plasma glow: the last knot that still outputs black has to sit high in luma.
        black = [x for x, y in knots(self.vf) if y == 0.0]
        self.assertTrue(black, "no black point, so the bloom is coming from the whole frame")
        self.assertGreaterEqual(max(black), 0.6,
                                f"bloom black point at {max(black):.2f} catches the hull")

    def test_bloom_is_blurred_then_screened(self):
        self.assertIn("gblur=", self.vf)
        self.assertIn("blend=all_mode=screen", self.vf)

    def test_the_bloom_composites_in_rgb_not_yuv(self):
        # blend works plane by plane. On the default yuv420p the U/V planes — centred at
        # 128, not at 0 — get screened as if they were light, and the first sheet this
        # filter ever touched came out magenta.
        self.assertIn("format=gbrp,split", self.vf)

    def test_grain_moves_with_the_footage(self):
        # allf=t is temporal noise. Without it the grain is a frozen screendoor and the
        # shot looks like it has a dirty lens lying on top of it.
        self.assertRegex(self.vf, r"noise=[^,;]*allf=t")

    def test_grain_comes_after_the_sharpen(self):
        self.assertLess(self.vf.index("unsharp="), self.vf.index("noise="),
                        "sharpening film grain amplifies it into sparkle")

    def test_the_vignette_runs_last(self):
        last = self.vf.split(";")[-1].strip().split(",")[-1]
        self.assertTrue(last.startswith("vignette="),
                        "anything after the vignette re-lights the corners it fell off")

    def test_the_vignette_darkens_gently(self):
        angle = float(re.search(r"vignette=([\d.]+)", self.vf).group(1))
        self.assertLess(angle, 0.85, "the corners are being crushed to black")

    def test_an_element_turned_off_leaves_the_graph(self):
        # The user judges this by looking, and being able to dial one element out of the
        # graph — rather than leave a zero-strength filter doing nothing — is what makes
        # the pass reviewable.
        self.assertNotIn("gblur", L.build_vf(bloom=0.0))
        self.assertNotIn("noise=", L.build_vf(grain=0.0))
        self.assertNotIn("vignette", L.build_vf(vignette=0.0))


class TestApply(unittest.TestCase):
    """One ffmpeg call, in-place on the master, source file untouched.

    The fake encoder creates the destination, because that is what the encoder does and the pass
    now digests the file it wrote: a stand-in that returns success without producing a file would
    let the evidence claim a grade that never happened.
    """

    class Ran:
        def __init__(self):
            self.calls = []

        def __call__(self, argv, **kw):
            self.calls.append([str(a) for a in argv])
            destination = Path(argv[-1])
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"encoded")

            class Done:
                returncode = 0
            return Done()

    def setUp(self):
        self.orig = L.subprocess.run
        self.tmp = tempfile.TemporaryDirectory()
        self.episode = Path(self.tmp.name)
        self.src = self.episode / "concat.mp4"
        self.src.write_bytes(b"concatenated")
        self.dst = self.episode / "video-graded.mp4"

    def tearDown(self):
        L.subprocess.run = self.orig
        self.tmp.cleanup()

    def test_it_returns_the_graded_path_and_encodes_once(self):
        ran = self.Ran()
        L.subprocess.run = ran
        out = L.apply(self.src, self.dst)
        self.assertEqual(out, self.dst)
        self.assertEqual(len(ran.calls), 1, "the master must be encoded in a single pass")
        argv = ran.calls[0]
        self.assertEqual(argv[argv.index("-i") + 1], str(self.src))
        self.assertEqual(argv[-1], str(self.dst))

    def test_the_audio_is_carried_not_re_encoded(self):
        # The graded file is later muxed with the narration; re-encoding audio here would
        # put two lossy generations between the voice and the deliverable.
        ran = self.Ran()
        L.subprocess.run = ran
        L.apply(self.src, self.dst)
        argv = ran.calls[0]
        self.assertEqual(argv[argv.index("-c:a") + 1], "copy")

    def test_it_does_not_reach_into_the_segment_cache(self):
        src = (ROOT / "tools" / "assemble_episode.py").read_text(encoding="utf-8")
        # The needle stops at the open paren: main() grew injectable parameters so the preflight
        # can be tested, and pinning its signature here would only ever say "the call order
        # inside main", which is what this actually checks.
        main = src[src.index("def main("):]
        for pair in (("concat_segments", "look_pass"), ("look_pass", "mux_final")):
            self.assertLess(main.index(pair[0]), main.index(pair[1]),
                            f"the look must sit between {pair[0]} and {pair[1]}")


if __name__ == "__main__":
    unittest.main()
