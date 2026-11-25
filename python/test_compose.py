"""tools/compose: pure argv builders, plus runs of the argv on tiny fixtures to prove the output."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.compose import (Canvas, Overlay, Mat, frame_of, segment_args, transition_args,  # noqa: E402
                           concat_list, concat_args, split_args)

C = Canvas(320, 180, 30)


def run(argv):
    r = subprocess.run([str(a) for a in argv], capture_output=True)
    assert r.returncode == 0, r.stderr.decode(errors="replace")[-1500:]


def frames_of(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                        "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True, check=True)
    return int(r.stdout.strip().rstrip(","))


def pixel(path, index, x, y, w=320, h=180):
    """RGB of pixel (x, y) in frame `index`."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"select=eq(n\\,{index})",
                        "-vframes", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       capture_output=True, check=True)
    off = (y * w + x) * 3
    return tuple(r.stdout[off:off + 3])


def solid(path, colour, d=2, size="320x180"):
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={colour}:s={size}:r=30:d={d}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast", path])


class PureArgs(unittest.TestCase):
    def test_frame_of_rounds_half_up(self):
        self.assertEqual([frame_of(t, 2) for t in (0.25, 0.75, 1.25)], [1, 2, 3])  # round() gives 0, 2, 2
        self.assertEqual(frame_of(1.0, 30), 30)

    def test_segment_shape(self):
        a = segment_args("in.mp4", 1.5, 17, C, "out.mp4")
        self.assertEqual(a[a.index("-frames:v") + 1], "17")
        self.assertIn("-an", a)
        self.assertLess(a.index("-ss"), a.index("-i"))
        self.assertNotIn("-stream_loop", a)
        for k, v in (("-c:v", "libx264"), ("-pix_fmt", "yuv420p"), ("-preset", "ultrafast"),
                     ("-crf", "23"), ("-r", "30")):
            self.assertEqual(a[a.index(k) + 1], v)
        self.assertIn("-stream_loop", segment_args("in.mp4", 0, 5, C, "o.mp4", loop=True))
        s = segment_args("a.png", 0, 5, C, "o.mp4", still=True)
        self.assertIn("-loop", s)
        self.assertNotIn("-ss", s)

    def test_overlay_window(self):
        a = segment_args("in.mp4", 0, 15, C, "o.mp4", overlays=[Overlay("ov.png", 5, 10, 4, 6)])
        g = a[a.index("-filter_complex") + 1]
        self.assertIn("between(n,5,9)", g)
        self.assertIn("setpts=PTS+5/(30*TB)", g)
        self.assertIn("overlay=4:6", g)

    def test_transition_args(self):
        d = transition_args("a.mp4", 0, "b.mp4", 0, 15, "dip", C, "o.mp4")
        self.assertIn("xfade=custom:expr=", d[d.index("-filter_complex") + 1])
        d = transition_args("a.mp4", 0, "b.mp4", 0, 15, "dissolve", C, "o.mp4")
        self.assertIn("transition=fade:", d[d.index("-filter_complex") + 1])
        with self.assertRaises(ValueError):
            transition_args("a.mp4", 0, "b.mp4", 0, 15, "cut", C, "o.mp4")

    def test_concat_list_quoting(self):
        t = concat_list([r"C:\a b\x'y.mp4", "caf\u00e9.mp4"])
        self.assertEqual(t.splitlines()[0], "file 'C:/a b/x'\\''y.mp4'")
        self.assertIn("caf\u00e9", t)
        self.assertEqual(concat_args("l.txt", "o.mp4")[-5:], ["-i", "l.txt", "-c", "copy", "o.mp4"])


class Runs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.td = tempfile.TemporaryDirectory()
        cls.d = Path(cls.td.name)
        d = cls.d
        solid(d / "red.mp4", "red")
        solid(d / "blue.mp4", "blue")
        solid(d / "red1.mp4", "red", d=1)
        solid(d / "blue1.mp4", "blue", d=1)
        (d / "l.txt").write_text(concat_list([d / "red1.mp4", d / "blue1.mp4"]), encoding="utf-8")
        run(concat_args(d / "l.txt", d / "rb.mp4"))
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=white:s=40x40,format=rgba,"
             "pad=320:180:100:60:color=black@0", "-frames:v", "1", d / "sq.png"])

    @classmethod
    def tearDownClass(cls):
        cls.td.cleanup()

    def test_segment_count_and_src_in(self):
        d = self.d
        run(segment_args(d / "rb.mp4", 0, 17, C, d / "s17.mp4"))
        self.assertEqual(frames_of(d / "s17.mp4"), 17)
        run(segment_args(d / "rb.mp4", 1.0, 20, C, d / "sb.mp4"))
        r, g, b = pixel(d / "sb.mp4", 0, 160, 90)
        self.assertGreater(b, 200)
        self.assertLess(r, 60)
        r, g, b = pixel(d / "s17.mp4", 0, 160, 90)
        self.assertGreater(r, 200)

    def test_loop_and_still(self):
        d = self.d
        run(segment_args(d / "red.mp4", 0, 100, C, d / "loop.mp4", loop=True))  # 2 s source, 3.3 s needed
        self.assertEqual(frames_of(d / "loop.mp4"), 100)
        run(segment_args(d / "sq.png", 0, 12, C, d / "still.mp4", still=True))
        self.assertEqual(frames_of(d / "still.mp4"), 12)

    def test_dissolve(self):
        d = self.d
        run(transition_args(d / "red.mp4", 0.5, d / "blue.mp4", 0, 15, "dissolve", C, d / "dis.mp4"))
        self.assertEqual(frames_of(d / "dis.mp4"), 15)
        r0, _, b0 = pixel(d / "dis.mp4", 0, 160, 90)
        r1, _, b1 = pixel(d / "dis.mp4", 14, 160, 90)
        rm, _, bm = pixel(d / "dis.mp4", 7, 160, 90)
        self.assertGreater(r0, 200)
        self.assertGreater(b1, 200)
        self.assertLess(abs(rm - 128), 25)
        self.assertLess(abs(bm - 128), 25)

    def test_dip(self):
        d = self.d
        run(transition_args(d / "red.mp4", 0, d / "blue.mp4", 0, 15, "dip", C, d / "dip.mp4"))
        self.assertEqual(frames_of(d / "dip.mp4"), 15)
        self.assertLess(max(pixel(d / "dip.mp4", 7, 160, 90)), 40)
        self.assertGreater(pixel(d / "dip.mp4", 0, 160, 90)[0], 200)
        self.assertGreater(pixel(d / "dip.mp4", 14, 160, 90)[2], 150)

    def test_transition_with_loop_source(self):
        d = self.d
        run(transition_args(d / "red.mp4", 1.9, d / "blue.mp4", 0, 15, "dissolve", C,
                            d / "dl.mp4", out_loop=True))
        self.assertEqual(frames_of(d / "dl.mp4"), 15)

    def test_overlay(self):
        d = self.d
        run(segment_args(d / "red.mp4", 0, 15, C, d / "ov.mp4",
                         overlays=[Overlay(d / "sq.png", 5, 10)]))
        self.assertEqual(frames_of(d / "ov.mp4"), 15)

        def white(i):
            r, g, b = pixel(d / "ov.mp4", i, 120, 80)
            return g > 180 and b > 180
        self.assertEqual([white(i) for i in (4, 5, 9, 10)], [False, True, True, False])
        self.assertGreater(pixel(d / "ov.mp4", 7, 10, 10)[0], 200)  # transparent elsewhere

    def test_overlay_mov_and_mat(self):
        d = self.d
        run(["ffmpeg", "-y", "-loop", "1", "-framerate", "30", "-i", d / "sq.png", "-frames:v", "6",
             "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", d / "sq.mov"])
        run(segment_args(d / "red.mp4", 0, 15, C, d / "ovm.mp4", overlays=[Overlay(d / "sq.mov", 2, 8)],
                         mat=Mat("0x0000ff", 20)))
        self.assertEqual(frames_of(d / "ovm.mp4"), 15)
        self.assertGreater(pixel(d / "ovm.mp4", 5, 5, 5)[2], 200)    # mat margin is blue
        self.assertGreater(pixel(d / "ovm.mp4", 0, 160, 90)[0], 200)  # picture inside
        self.assertLess(pixel(d / "ovm.mp4", 1, 120, 80)[1], 100)     # overlay not yet on
        self.assertGreater(pixel(d / "ovm.mp4", 4, 120, 80)[1], 180)  # on

    def test_concat_three(self):
        d = self.d
        names = []
        for i, n in enumerate((10, 15, 5)):
            p = d / f"caf\u00e9 {i}.mp4"
            run(segment_args(d / "red.mp4", 0, n, C, p))
            names.append(p)
        (d / "c3.txt").write_text(concat_list(names), encoding="utf-8")
        run(concat_args(d / "c3.txt", d / "c3.mp4"))
        self.assertEqual(frames_of(d / "c3.mp4"), 30)

    def test_split(self):
        d = self.d
        run(split_args([(d / "red.mp4", 0), (d / "blue.mp4", 0)], 12, C, d / "sp.mp4"))
        self.assertEqual(frames_of(d / "sp.mp4"), 12)
        self.assertGreater(pixel(d / "sp.mp4", 3, 40, 90)[0], 200)
        self.assertGreater(pixel(d / "sp.mp4", 3, 280, 90)[2], 200)
        run(split_args([(d / "red.mp4", 0)] * 4, 6, C, d / "sp4.mp4"))
        self.assertEqual(frames_of(d / "sp4.mp4"), 6)


if __name__ == "__main__":
    unittest.main()
