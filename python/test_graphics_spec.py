"""Spec validator, tokens, and the contract every registered primitive must meet."""
import inspect
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_graphics_support import SMALL, TOKENS, ink_outside_margin  # noqa: E402

from tools.graphics import OVERLAY, PRIMITIVES, get  # noqa: E402
from tools.graphics.common import Ctx, contrast, hex_rgb  # noqa: E402
from tools.graphics.gallery import fixtures, sample_image  # noqa: E402
from tools.graphics.spec import obj, validate  # noqa: E402
from tools.graphics.tokens import load_tokens  # noqa: E402


class SpecValidator(unittest.TestCase):
    def test_refuses_wrong_type_missing_and_unknown(self):
        schema = obj({"n": {"type": "integer", "minimum": 1}, "b": {"type": "build"}}, required=["n"])
        validate({"n": 2, "b": [0, 1]}, schema)
        validate({"n": 2, "b": {"at": 0.1, "dur": 1}}, schema)
        for bad, word in (({}, "missing"), ({"n": "x"}, "expected"), ({"n": 0}, "minimum"),
                          ({"n": 1, "zzz": 1}, "unknown"), ({"n": 1, "b": [1]}, "build")):
            with self.assertRaises(ValueError, msg=str(bad)) as cm:
                validate(bad, schema)
            self.assertIn(word, str(cm.exception))

    def test_bool_is_not_a_number(self):
        with self.assertRaises(ValueError):
            validate(True, {"type": "number"})


class Tokens(unittest.TestCase):
    def test_block_has_what_the_brief_lists(self):
        t = load_tokens()
        for k in ("ink", "paper", "accent", "warm", "cool", "data_a", "data_b", "danger", "mat"):
            self.assertRegex(t["palette"][k], r"^#[0-9a-fA-F]{6}$")
        self.assertEqual(t["type"]["number"], 0.10)
        self.assertEqual(t["type"]["label"], 0.06)
        self.assertEqual(t["type"]["caption"], 0.045)
        self.assertEqual(t["mobile_floor"], {"label": 0.06, "number": 0.10})
        self.assertEqual(t["safe_margin_fraction"], 0.05)
        for p in t["fonts_abs"].values():
            self.assertTrue(Path(p).is_file(), p)

    def test_look_may_replace_palette_only(self):
        t = load_tokens(overrides={"palette": {"accent": "#112233"}})
        self.assertEqual(t["palette"]["accent"], "#112233")
        self.assertEqual(load_tokens()["palette"]["accent"], TOKENS["palette"]["accent"])
        for bad in ({"type": {"label": 0.01}}, {"palette": {"nope": "#000000"}},
                    {"palette": {"ink": "red"}}, {"safe_margin_fraction": 0}):
            with self.assertRaises(ValueError, msg=str(bad)):
                load_tokens(overrides=bad)

    def test_type_below_mobile_floor_is_refused(self):
        with self.assertRaises(ValueError):
            Ctx(SMALL, TOKENS, {"type": {"label": 0.04}})
        with self.assertRaises(ValueError):
            Ctx(SMALL, TOKENS, {"type": {"number": 0.08}})

    def test_text_colours_in_use_reach_wcag_aa(self):
        p = {k: hex_rgb(v) for k, v in TOKENS["palette"].items()}
        for fg, bg in (("ink", "paper"), ("paper", "mat"), ("danger", "paper"), ("paper", "ink"),
                       ("data_a", "paper"), ("data_b", "paper")):
            self.assertGreaterEqual(contrast(p[fg], p[bg]), 4.5, (fg, bg))


class Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.fx = fixtures(sample_image(Path(cls.tmp.name) / "s.png"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_primitive_has_a_fixture_and_the_brief_names(self):
        self.assertEqual(set(self.fx), set(PRIMITIVES))
        for name in ("big_number", "ratio_compare", "bar_compare", "tally", "figure_grid", "timeline",
                     "map_plan", "board", "board_card", "split", "archive_mat", "source_card", "label",
                     "callout", "lower_third", "underline", "circle", "date_stamp", "day_labels"):
            self.assertIn(name, PRIMITIVES)
        for name, prim in PRIMITIVES.items():
            self.assertEqual(prim.OVERLAY, name in OVERLAY)
            self.assertIsInstance(prim.SCHEMA, dict)

    def test_bad_spec_is_refused_with_value_error(self):
        for name, (spec, _, _) in self.fx.items():
            with self.assertRaises(ValueError, msg=name):
                get(name).frame_at({**spec, "bogus_field": 1}, 0.5, SMALL)
            with self.assertRaises(ValueError, msg=name):
                get(name).render({**spec, "bogus_field": 1}, 1, SMALL)

    def test_deterministic_bytes(self):
        for name, (spec, tm, te) in self.fx.items():
            a = get(name).frame_at(spec, te, SMALL).tobytes()
            b = get(name).frame_at(spec, te, SMALL).tobytes()
            self.assertEqual(a, b, name)

    def test_render_is_a_lazy_generator_of_the_right_length_matching_frame_at(self):
        for name, (spec, tm, te) in self.fx.items():
            gen = get(name).render(spec, 0.5, SMALL, 10)
            self.assertTrue(inspect.isgenerator(gen), name)
            self.assertIs(iter(gen), gen)
            frames = [next(gen) for _ in range(5)]
            self.assertEqual(list(gen), [])
            ref = get(name).frame_at(spec, 3 / 10, SMALL)
            self.assertEqual(frames[3].tobytes(), ref.tobytes(), name)

    def test_nothing_drawn_outside_the_safe_margin(self):
        for name, (spec, tm, te) in self.fx.items():
            spec = dict(spec)
            if name == "split":
                spec["dividers"] = False  # dividers separate video panes and span the frame by design
            prim = get(name)
            for t in (tm, te):
                img = prim.frame_at(spec, t, SMALL)
                if prim.OVERLAY:
                    self.assertEqual(ink_outside_margin(img), 0, (name, t))
                else:
                    bg = "mat" if name in ("board", "archive_mat") else "paper"
                    self.assertEqual(ink_outside_margin(img, TOKENS["palette"][bg]), 0, (name, t))

    def test_overlays_are_transparent_and_full_frames_opaque(self):
        for name, (spec, tm, te) in self.fx.items():
            img = get(name).frame_at(spec, te, SMALL)
            alpha = img.getchannel("A")
            if get(name).OVERLAY:
                self.assertEqual(alpha.getextrema()[0], 0, name)
            else:
                self.assertEqual(alpha.getextrema(), (255, 255), name)


if __name__ == "__main__":
    unittest.main()
