"""Streaming encode: frame counts, alpha, atomic output, and bounded memory."""
import subprocess
import sys
import tempfile
import tracemalloc
import unittest
import weakref
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_graphics_support import SMALL  # noqa: E402

from PIL import Image  # noqa: E402

from tools.graphics import get  # noqa: E402
from tools.graphics.encode import render_to_file, stream_to_mp4  # noqa: E402
from tools.graphics.presets import get_preset  # noqa: E402

TALLY = {"left": {"label": "First Clinic", "marks": 11, "per": 100},
         "right": {"label": "Second Clinic", "marks": 3, "per": 100},
         "build": {"left": [0.15, 0.7], "right": [0.5, 0.35]}, "source": "1846"}


def probe_frames(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                        "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True, check=True)
    return int(r.stdout.strip().rstrip(","))


def first_frame_rgba(path):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-frames:v", "1", "-f", "rawvideo",
                        "-pix_fmt", "rgba", "-"], capture_output=True, check=True)
    return Image.frombytes("RGBA", SMALL, r.stdout)


class Encode(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_two_second_mp4_has_exactly_60_frames(self):
        out = self.dir / "t.mp4"
        frames = get("tally").render(TALLY, 2.0, SMALL, 30)
        self.assertEqual(stream_to_mp4(frames, out, 30, SMALL), 60)
        self.assertEqual(probe_frames(out), 60)
        self.assertEqual([p.name for p in self.dir.iterdir()], ["t.mp4"])

    def test_alpha_mov_keeps_transparency(self):
        out = self.dir / "t.mov"
        n = stream_to_mp4(get("tally").render(TALLY, 2.0, SMALL, 30), out, 30, SMALL, alpha=True)
        self.assertEqual(n, 60)
        self.assertEqual(probe_frames(out), 60)
        a = first_frame_rgba(out)
        self.assertEqual(a.getchannel("A").getextrema()[0], 0)

    def test_alpha_requires_mov(self):
        with self.assertRaises(ValueError):
            stream_to_mp4([], self.dir / "x.mp4", alpha=True)

    def test_generator_that_raises_midstream_leaves_nothing_behind(self):
        out = self.dir / "t.mp4"

        def broken():
            for i, f in enumerate(get("tally").render(TALLY, 2.0, SMALL, 30)):
                if i == 10:
                    raise RuntimeError("boom")
                yield f

        with self.assertRaises(RuntimeError) as cm:
            stream_to_mp4(broken(), out, 30, SMALL)
        self.assertIn("boom", str(cm.exception))
        self.assertEqual(list(self.dir.iterdir()), [])

    def test_wrong_size_frame_is_refused_and_cleaned_up(self):
        out = self.dir / "t.mp4"
        with self.assertRaises(ValueError):
            stream_to_mp4([Image.new("RGBA", (10, 10))], out, 30, SMALL)
        self.assertEqual(list(self.dir.iterdir()), [])

    def test_existing_output_survives_a_failed_run(self):
        out = self.dir / "t.mp4"
        out.write_bytes(b"previous")
        with self.assertRaises(ValueError):
            stream_to_mp4([Image.new("RGBA", (10, 10))], out, 30, SMALL)
        self.assertEqual(out.read_bytes(), b"previous")

    def test_render_to_file_picks_alpha_by_overlay_and_accepts_presets(self):
        n = render_to_file("tally", TALLY, 1.0, self.dir / "o.mov", 30, SMALL)
        self.assertEqual(n, 30)
        prim, spec = get_preset("ratio-1846")
        n = render_to_file("ratio-1846", {}, 1.0, self.dir / "p.mp4", 30, SMALL)
        self.assertEqual(n, 30)
        self.assertEqual(probe_frames(self.dir / "p.mp4"), 30)


class Memory(unittest.TestCase):
    def test_twenty_second_1080p_stream_is_pulled_lazily_and_stays_small(self):
        spec = get_preset("ward-plan-routes")[1]
        alive, peak_alive, pulled = [], [0], [0]

        def watched():
            for img in get("map_plan").render(spec, 20.0, (1920, 1080), 30):
                pulled[0] += 1
                alive.append(weakref.ref(img))
                peak_alive[0] = max(peak_alive[0], sum(1 for r in alive if r() is not None))
                yield img

        tracemalloc.start()
        try:
            n = stream_to_mp4(watched(), None or Path(tempfile.gettempdir()) / "unused.mp4", 30,
                              (1920, 1080), preset="ultrafast", _null=True)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertEqual(n, 600)
        self.assertEqual(pulled[0], 600)
        self.assertLess(peak / 1e6, 200, f"traced peak {peak / 1e6:.0f} MB")
        self.assertLessEqual(peak_alive[0], 3, "frames must not accumulate")


if __name__ == "__main__":
    unittest.main()
