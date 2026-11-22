# -*- coding: utf-8 -*-
"""What the archival ingest has to do to a source file, proved on real pixels.

`workflow/archive.py` validates the metadata. This file proves the *encode* obeys it, because
every rule below is invisible to a metadata check: a clip can declare `motion_mode:
"period_motion"` and still be re-timed as though it said the other value, and nothing in the
record says whether the black bars actually arrived.

The rules under test, all of them from `workflow/style.json`:

* `archive_motion`: an undeclared rate is refused; `retime_to_natural` keeps the source's own
  wall-clock duration, `period_motion` deliberately does not. They differ by canvas_fps /
  native_fps, which is the measurable form of "the comic fast-walk".
* `archive_aspect`: `pillarbox_visible_edge` letterboxes with no crop anywhere in the chain.
  `designed_container` needs the matte and its rectangle declared, because the third state the
  contract rejects — an accidental edge crop of the 4:3 frame — is exactly what a silent
  fallback would ship.
* `cohesion.light_direction`: a flip is allowed only when the sides disagree *and* OCR finds no
  readable text. A scanner that did not run cannot report "no text", so it refuses the flip.
* `archive_motion.stills_never_dead`: a still gets a move with both a pan and a scale change,
  terminating rather than looping — the same thing the card gate already demands of a card.
* `archive.source_card`: the credit line is on screen from the in-point for the declared
  seconds, sized from the contract rather than guessed.
* `cohesion.archival_audio_rule`: the stock's own embedded audio never reaches the master.

Fixtures are built with PIL rather than `drawtext` so the text in the image is drawn by the
same font stack the card layer uses, and so a missing fontconfig makes nothing skip.
"""
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

import archive_ingest as AI  # noqa: E402
from workflow.archive import key_side  # noqa: E402
from workflow.config import style_contract  # noqa: E402

CONTRACT = style_contract(ROOT)
CANVAS = (int(CONTRACT["canvas"]["width"]), int(CONTRACT["canvas"]["height"]))
CANVAS_FPS = float(CONTRACT["canvas"]["fps"])
NATIVE_FPS = 16.0
SOURCE_FRAMES = 48          # 3.0 s at 16 fps, 1.6 s at 30 — the pair the retime rule turns on
SOURCE_SIZE = (320, 240)    # 4:3, the shape the aspect rule is about
FONT = ROOT / "tools" / "fonts" / "Inter-Bold.ttf"

RECORD = {
    "asset": "assets/archive/apollo_boot_1969.mp4",
    "licence": "arch-001",
    "form": "clip",
    "native_fps": NATIVE_FPS,
    "motion_mode": "retime_to_natural",
    "aspect": "pillarbox_visible_edge",
    "treatment": "keep_distinct",
}
ROW = {
    "id": "arch-001",
    "provider": "NASA",
    "license": "PD-US-NO-RESTRICTION",
    "url": "https://archive.org/details/nasa-apollo-boot",
    "file": "assets/archive/apollo_boot_1969.mp4",
    "source_archive": "NASA Image Library",
    "rights_basis": "us_federal_public_domain",
    "credit_line": "NASA, Apollo 11 EVA (1969)",
    "retrieval_url": "https://archive.org/download/nasa-apollo-boot/apollo_boot_1969.mp4",
    "retrieved_date": "2026-11-13",
}

OPPOSITE_SIDE = "left" if key_side(CONTRACT) == "right" else "right"


def record(**changes):
    out = dict(RECORD)
    for key, value in changes.items():
        if value is None:
            out.pop(key, None)
        else:
            out[key] = value
    return out


def row(**changes):
    out = dict(ROW)
    for key, value in changes.items():
        if value is None:
            out.pop(key, None)
        else:
            out[key] = value
    return out


# ------------------------------------------------------------------ the graph, no encoder

class TestRetime(unittest.TestCase):
    def test_natural_play_keeps_the_source_s_own_frame_spacing(self):
        """Frame i of a 16 fps source really was exposed 1/16 s after frame i-1, so the honest
        canvas-rate version shows each frame for canvas/native output frames and runs as long
        as the source did. Re-timing the PTS as well as the rate is what makes the fast walk."""
        chain = AI.retime_filter(record(motion_mode="retime_to_natural"), CONTRACT)
        self.assertIn(f"fps={CANVAS_FPS:g}", ",".join(chain))
        self.assertFalse([f for f in chain if "setpts" in f],
                         f"{chain} re-times the timeline as well as the rate")

    def test_period_motion_deliberately_compresses_the_timeline(self):
        """The other honest answer: one source frame per canvas frame, 1.875x faster than shot,
        which reads as period. Declaring it is the difference between a choice and a bug."""
        chain = AI.retime_filter(record(motion_mode="period_motion"), CONTRACT)
        graph = ",".join(chain)
        self.assertIn("setpts=", graph)
        self.assertIn(f"fps={CANVAS_FPS:g}", graph)

    def test_an_undeclared_mode_never_reaches_the_encoder(self):
        with self.assertRaises(ValueError) as caught:
            AI.retime_filter(record(motion_mode=None), CONTRACT)
        self.assertIn("motion_mode", str(caught.exception))

    def test_the_two_modes_differ_by_exactly_the_rate_ratio(self):
        # A guard test cannot tell these fixtures apart if the ratio is 1; the canvas rate is
        # not the archival rate, and that is the whole reason the pair exists.
        self.assertAlmostEqual((SOURCE_FRAMES / NATIVE_FPS) / (SOURCE_FRAMES / CANVAS_FPS),
                               CANVAS_FPS / NATIVE_FPS, places=6)
        self.assertGreater(CANVAS_FPS / NATIVE_FPS, 1.5)


class TestAspect(unittest.TestCase):
    def test_pillarbox_fits_and_pads_and_never_crops(self):
        graph = ",".join(AI.aspect_filter(record(aspect="pillarbox_visible_edge"),
                                          CONTRACT, CANVAS))
        self.assertIn("force_original_aspect_ratio=decrease", graph)
        self.assertIn("pad=", graph)
        self.assertNotIn("crop=", graph)
        self.assertIn(f"{CANVAS[0]}:{CANVAS[1]}", graph)

    def test_pillarbox_bars_are_a_declared_colour_not_whatever_the_encoder_gives(self):
        # Measured on this build: an undeclared pad on yuv420p happens to land at 0/0/0, which is
        # the same value the contract declares. So the encoder default is not what this test is
        # guarding — a chain that dropped `color=` would still pass a "the bars are black" pixel
        # check, and the number would be the encoder's rather than the film's. D-017: any value
        # reaching the screen is contract data.
        pad = [f for f in AI.aspect_filter(record(), CONTRACT, CANVAS) if f.startswith("pad=")]
        self.assertEqual(len(pad), 1, pad)
        declared = CONTRACT["archive"]["archive_aspect"]["bar_colour"]
        self.assertIn(f"color={declared}", pad[0])

    def test_a_designed_container_has_to_say_what_the_container_is(self):
        """`designed_container` means the old footage is projected onto a period object, so a
        record with no matte and no rectangle is not that treatment — it is the accidental crop
        the contract calls the third failure."""
        with self.assertRaises(ValueError) as caught:
            AI.aspect_filter(record(aspect="designed_container"), CONTRACT, CANVAS)
        message = str(caught.exception)
        self.assertIn("designed_container", message)
        self.assertIn("container_image", message)

    def test_a_designed_container_scales_into_its_rect_inside_the_canvas(self):
        rec = record(aspect="designed_container", container_image="assets/archive/projector.png",
                     container_rect=[640, 180, 640, 480])
        graph = ",".join(AI.aspect_filter(rec, CONTRACT, CANVAS))
        self.assertIn("scale=640:480", graph)
        self.assertIn("overlay=640:180", graph)
        self.assertNotIn("pad=", graph, "a container that also letterboxes is a crop in disguise")

    def test_a_container_rect_reaching_outside_the_canvas_is_refused(self):
        rec = record(aspect="designed_container", container_image="assets/archive/projector.png",
                     container_rect=[1400, 180, 640, 480])
        with self.assertRaises(ValueError) as caught:
            AI.aspect_filter(rec, CONTRACT, CANVAS)
        self.assertIn("canvas", str(caught.exception))

    def test_a_container_only_graph_hands_the_encoder_one_balanced_output_label(self):
        """The last stage relabels itself `[vout]` by cutting off the label it just wrote.

        Cutting at the final `]` instead keeps the `[` of that label, which shipped
        `overlay=...[proj[vout]` and died as "Output with label 'vout' does not exist" — a graph
        error the encoder reports but no metadata check can see. Pinning the whole token sequence
        is the point: an assertion on `endswith("[vout]")` alone passes the broken string.
        """
        graph = AI._graph(["fps=30", "scale=800:600"], "overlay=400:100:shortest=1", None, 1, None)
        self.assertEqual(re.findall(r"\[[^\]]*\]", graph),
                         ["[0:v]", "[foot]", "[1:v]", "[foot]", "[vout]"], graph)


class TestStillsMove(unittest.TestCase):
    def base(self, **changes):
        # Merged rather than passed as keywords: `record(seconds=2.0, **{"seconds": None})` is a
        # duplicate-kwarg TypeError, so an override of any field the default sets would die here
        # instead of reaching the rule under test.
        fields = {"form": "still", "native_fps": None, "motion_mode": None, "seconds": 2.0}
        fields.update(changes)
        return record(**fields)

    def test_a_still_is_given_screen_time_by_its_move(self):
        rec = self.base(still_move={"pan_deg": 2.0, "zoom_from": 1.0, "zoom_to": 1.12})
        graph = ",".join(AI.still_filter(rec, CONTRACT, CANVAS, 2.0))
        self.assertIn("zoompan=", graph)
        self.assertIn("d=60", graph)          # 2 s at the canvas rate, not a source frame count

    def test_a_pan_with_no_scale_change_is_refused(self):
        """`still_move_requires` names both halves. A pure pan of a still is the sliding-photo
        effect the motion gate already fails a card for, and the score proves it."""
        with self.assertRaises(ValueError) as caught:
            AI.still_filter(self.base(still_move={"pan_deg": 2.0}), CONTRACT, CANVAS, 2.0)
        self.assertIn("zoom", str(caught.exception).lower())

    def test_a_looping_still_move_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            AI.still_filter(self.base(still_move={"pan_deg": 2.0, "zoom_from": 1.0,
                                                  "zoom_to": 1.12, "cycle": True}),
                            CONTRACT, CANVAS, 2.0)
        self.assertIn("terminating", str(caught.exception))

    def test_the_fov_that_turns_degrees_into_pixels_is_the_blender_default_not_a_guess(self):
        """`still_move` declares its pan in degrees because the rate cap is in degrees, so the
        conversion needs a horizontal FOV. If that number drifts from what the renderer actually
        uses, the same declared pan sweeps a different distance on screen than the contract
        promises — and the still starts moving at a rate the 3D camera would be refused for."""
        import math
        declared = float(CONTRACT["camera"]["horizontal_fov_deg"])
        sensor_width, default_lens = 36.0, 50.0
        self.assertAlmostEqual(declared, math.degrees(2 * math.atan(sensor_width / 2 / default_lens)),
                               places=2,
                               msg="horizontal_fov_deg no longer matches Blender's 50 mm on 36 mm")

    def test_the_move_stays_inside_the_camera_rate_the_contract_set(self):
        # camera.max_deg_per_second is the rate the 3D camera is allowed to travel at; a still
        # panning faster than that reads as a different programme.
        limit = float(CONTRACT["camera"]["max_deg_per_second"])
        with self.assertRaises(ValueError) as caught:
            AI.still_filter(self.base(still_move={"pan_deg": limit * 2.0 + 0.5,
                                                  "zoom_from": 1.0, "zoom_to": 1.1}),
                            CONTRACT, CANVAS, 2.0)
        self.assertIn("max_deg_per_second", str(caught.exception))

    def test_a_still_without_a_declared_duration_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            AI.still_filter(self.base(seconds=None, still_move={"pan_deg": 2.0,
                                                                "zoom_from": 1.0,
                                                                "zoom_to": 1.1}),
                            CONTRACT, CANVAS, None)
        self.assertIn("seconds", str(caught.exception))


class TestMirrorGuard(unittest.TestCase):
    def test_a_still_image_is_read_at_frame_zero(self):
        # ffprobe gives a jpg one 0.04 s frame; reading its "middle" at 0.02 s decoded nothing and
        # the guard raised "has no frame" for every still whose light side disagreed
        for name in ("engraving.jpg", "portrait.JPEG", "scan.png", "page.tif"):
            self.assertEqual(AI._readable_time(Path(name)), 0.0, name)

    def test_an_image_is_read_without_a_seek(self):
        # this ffmpeg decodes no frame from a jpg given `-ss`, even `-ss 0`
        self.assertEqual(AI._seek(Path("engraving.jpg"), 0.0), [])
        self.assertEqual(AI._seek(Path("clip.mp4"), 1.5), ["-ss", "1.5000"])

    def test_agreeing_sides_need_no_flip_at_all(self):
        allowed, why = AI.mirror_decision(record(light_side=key_side(CONTRACT)), CONTRACT,
                                          text_found=False, ocr_available=True)
        self.assertFalse(allowed, why)

    def test_disagreeing_sides_and_no_text_is_the_one_case_that_flips(self):
        allowed, _ = AI.mirror_decision(record(light_side=OPPOSITE_SIDE), CONTRACT,
                                        text_found=False, ocr_available=True)
        self.assertTrue(allowed)

    def test_readable_text_refuses_the_flip(self):
        allowed, why = AI.mirror_decision(record(light_side=OPPOSITE_SIDE), CONTRACT,
                                          text_found=True, ocr_available=True)
        self.assertFalse(allowed)
        self.assertIn("text", why.lower())

    def test_a_scanner_that_did_not_run_refuses_the_flip_rather_than_assuming_no_text(self):
        other = "left" if key_side(CONTRACT) == "right" else "right"
        allowed, why = AI.mirror_decision(record(light_side=other), CONTRACT,
                                          text_found=None, ocr_available=False)
        self.assertFalse(allowed)
        self.assertIn("ocr", why.lower())

    def test_no_declared_side_is_no_flip(self):
        allowed, _ = AI.mirror_decision(record(light_side=None), CONTRACT,
                                        text_found=False, ocr_available=True)
        self.assertFalse(allowed)


class TestSourceCard(unittest.TestCase):
    def test_the_card_is_held_from_the_in_point_for_the_declared_seconds(self):
        seconds = float(CONTRACT["archive"]["source_card"]["seconds"])
        graph = ",".join(AI.card_filter(Path("card.png"), CONTRACT, CANVAS))
        self.assertIn(f"between(t,0,{seconds:g})", graph)

    def test_the_card_text_is_the_ledger_credit_line_and_nothing_else(self):
        # A card built from the provider name alone would pass a "a card exists" check and still
        # not say where the footage came from.
        self.assertEqual(AI.card_text(row(), CONTRACT), ROW["credit_line"])

    def test_a_fair_use_quotation_cannot_borrow_another_field_for_the_card(self):
        with self.assertRaises(ValueError):
            AI.card_text(row(rights_basis="fair_use_quotation", credit_line="  "), CONTRACT)

    def test_the_card_font_is_a_fraction_of_the_canvas_not_a_pixel_count(self):
        fraction = float(CONTRACT["archive"]["source_card"]["height_fraction"])
        self.assertEqual(AI.card_font_size(CONTRACT, CANVAS), round(fraction * CANVAS[1]))

    def test_the_position_the_contract_names_is_the_position_drawn(self):
        position = CONTRACT["archive"]["source_card"]["position"]
        x, y = AI.card_position(CANVAS, (600, 60), position, CONTRACT)
        self.assertLess(x, CANVAS[0] // 2, f"{position} drew on the right half")
        self.assertGreater(y, CANVAS[1] // 2, f"{position} drew above the middle")
        other = "top-right" if position != "top-right" else "bottom-left"
        ox, oy = AI.card_position(CANVAS, (600, 60), other, CONTRACT)
        self.assertGreater(ox, x)
        self.assertLess(oy, y)

    def test_the_card_keeps_the_margin_the_contract_set_off_the_canvas_edge(self):
        # The margin is a fraction of the canvas, so it scales with the format; a hard-coded
        # pixel inset would put the card in a different place the moment the canvas moved.
        margin = float(CONTRACT["archive"]["source_card"]["edge_margin_fraction"])
        position = CONTRACT["archive"]["source_card"]["position"]
        x, y = AI.card_position(CANVAS, (600, 60), position, CONTRACT)
        self.assertEqual(x, round(margin * CANVAS[0]))
        self.assertEqual(y, CANVAS[1] - 60 - round(margin * CANVAS[1]))


    def test_a_long_credit_breaks_at_its_own_phrases_not_mid_name(self):
        # The Semmelweis pilot's credits ran off the right edge on one line. A width budget of
        # 40 characters stands in for the pixel one.
        text = ("Joseph and Peter Schaffer, c. 1784 (via Dorotheum) / "
                "Wikimedia Commons (public domain)")
        lines = AI.card_lines(text, lambda line: len(line) <= 40)
        self.assertTrue(all(len(line) <= 40 for line in lines), lines)
        self.assertEqual(" ".join(lines), text, "a word went missing in the wrap")
        self.assertEqual(lines[-1], "Wikimedia Commons (public domain)")

    def test_a_credit_that_fits_stays_on_one_line(self):
        self.assertEqual(AI.card_lines("Wikimedia Commons", lambda line: True),
                         ["Wikimedia Commons"])

    def test_the_drawn_plate_keeps_its_text_inside_both_margins(self):
        # Pixel proof on the real font: nothing opaque in the margin strips on either side.
        from PIL import Image
        font = AI.resolve_path(AI.ROOT, CONTRACT["archive"]["source_card"]["font_file"])
        if not Path(font).exists():
            self.skipTest("card font not present")
        text = ("After Jenő Doby (engraving, 1860), scan from Benedek 1983 / "
                "Wikimedia Commons (public domain)")
        with tempfile.TemporaryDirectory() as tmp:
            plate = AI.write_card_png(Path(tmp) / "card.png", text, CONTRACT, CANVAS, font=font)
            alpha = Image.open(plate).getchannel("A")
        margin = round(float(CONTRACT["archive"]["source_card"]["edge_margin_fraction"])
                       * CANVAS[0])
        left, _, right, _ = alpha.getbbox()
        self.assertGreaterEqual(left, margin - 1)
        self.assertLessEqual(right, CANVAS[0] - margin + 1)


class TestEncodeArguments(unittest.TestCase):
    def test_the_source_s_own_audio_never_reaches_the_master(self):
        # Rule 17: stock footage arrives with library music baked in. The bed is rebuilt from the
        # film's own palette, so the ingest drops the source audio rather than mixing it low.
        args = AI.encode_args(Path("in.mp4"), Path("out.mp4"), ["fps=30"], CONTRACT)
        self.assertIn("-an", args)
        self.assertNotIn("-c:a", args)

    def test_the_output_rate_and_size_are_the_contract_canvas(self):
        # Token assertions, not substring: "30" is inside "130", inside a crf value, and inside
        # the height 1080 of some other build. A guard that passes on an accidental substring is
        # a guard that stays green when someone changes the rate.
        args = AI.encode_args(Path("in.mp4"), Path("out.mp4"), ["fps=30"], CONTRACT)
        self.assertIn("-r", args)
        self.assertIn(f"{CANVAS_FPS:g}", args[args.index("-r") + 1:])
        self.assertIn("-s", args)
        self.assertIn(f"{CANVAS[0]}x{CANVAS[1]}", args[args.index("-s") + 1:])

    def test_the_ingest_never_hands_ffmpeg_a_keyboard_to_wait_on(self):
        # An ingest runs inside an unattended queue. ffmpeg's interactive key reader otherwise
        # attaches to whatever stdin it inherited, which is a way for a step to be waiting on a
        # person who is not at the machine rather than doing work.
        args = AI.encode_args(Path("in.mp4"), Path("out.mp4"), ["fps=30"], CONTRACT)
        self.assertEqual(args[1], "-nostdin")


class TestUnboundedWork(unittest.TestCase):
    """Both defects the first run of this module actually produced, generalized to the rule class.

    Neither is a wrong number: an overlay without shortest=1 never finishes, and a subprocess with
    no ceiling never reports that it didn't. Both fail as a silent machine, which is the one
    failure mode an unattended rollout cannot see.
    """

    def test_every_overlay_the_ingest_emits_ends_with_the_footage(self):
        # Swept over every overlay the module can produce rather than fixed per site: the plate and
        # the matte both arrive as `-loop 1` inputs, so a second one added later inherits the same
        # unbounded graph. Measured: without shortest=1 the carded ingest was killed at 90 s having
        # written no moov atom; with it the same chain finished in 1.9 s at exactly 180 frames.
        container = record(aspect="designed_container", container_image="assets/archive/matte.png",
                           container_rect=[640, 180, 640, 480])
        overlays = [AI.card_enable(CONTRACT),
                    AI.aspect_filter(container, CONTRACT, CANVAS)[-1]]
        self.assertTrue(all(o.startswith("overlay=") for o in overlays), overlays)
        for overlay in overlays:
            self.assertIn("shortest=1", overlay,
                          f"{overlay} composites a looped plate with no end condition")

    def test_a_step_that_outlives_its_ceiling_fails_instead_of_running_forever(self):
        message = ""
        try:
            AI._run([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.5)
        except RuntimeError as caught:
            message = str(caught)
        self.assertIn("still running after 0.5s", message,
                      "the ceiling was reached but nothing named it — the run would hang silently")

    def test_the_ceiling_is_loose_enough_for_the_slowest_honest_encode(self):
        # The guard must not become a new failure mode. Measured here: a carded 6 s ingest at the
        # contract's crf 17 finishes in 1.9 s, so the ceiling for that clip is over a hundred times
        # the work it allows.
        ceiling = AI.encode_ceiling(6.0)
        self.assertGreaterEqual(ceiling, 60.0 * 6.0)
        self.assertGreaterEqual(ceiling / 1.9, 100.0)
        self.assertEqual(AI.encode_ceiling(0.0), AI.ENCODE_CEILING_FLOOR)


# ------------------------------------------------------------------ real pixels

@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not on PATH")
class RealPixels(unittest.TestCase):
    """The rules only an encoder can answer: how long the clip came out, where the black bars
    are, whether the flip actually ran, and whether the card can really be read."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.work = Path(cls.tmp.name)
        cls.ocr = AI.resolve_ocr(ROOT)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    # -- fixtures ---------------------------------------------------------------
    def frame_png(self, name, *, block=(10, 100), text=None, size=SOURCE_SIZE):
        path = self.work / (name + ".png")
        AI.write_fixture_frame(path, size=size, block=block, text=text, font=FONT)
        return path

    def clip(self, name, *, fps=NATIVE_FPS, frames=SOURCE_FRAMES, block=(10, 100), text=None):
        """A 4:3 archival stand-in: a flat period-coloured frame with one white square.

        The square is what makes the mirror test falsifiable. A symmetric test pattern cannot
        tell a flip from no flip, and a guard test whose fixture cannot fail the guard proves
        nothing.
        """
        png = self.frame_png(name, block=block, text=text)
        path = self.work / (name + ".mp4")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", str(fps),
                        "-i", str(png), "-frames:v", str(frames),
                        "-vf", f"scale={size_arg(png)}:flags=neighbor,noise=alls=6:allf=t",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
                        "-crf", "18", str(path)], check=True)
        return path

    def still(self, name, *, block=(20, 100)):
        return self.frame_png(name, block=block)

    def ingest(self, source, rec, r=None, **kwargs):
        out = self.work / (source.stem + "-out.mp4")
        return AI.ingest_clip(source, out, record=rec, licence_row=r if r is not None else row(),
                              contract=CONTRACT, root=ROOT, **kwargs)

    # -- retime -----------------------------------------------------------------
    def test_natural_play_keeps_the_seconds_the_source_was_exposed_for(self):
        result = self.ingest(self.clip("natural"), record(motion_mode="retime_to_natural"))
        self.assertAlmostEqual(result["duration_s"], SOURCE_FRAMES / NATIVE_FPS, delta=0.15,
                               msg="retime_to_natural sped the footage up")

    def test_period_motion_is_the_faster_cut_by_the_rate_ratio(self):
        result = self.ingest(self.clip("period"), record(motion_mode="period_motion"))
        self.assertAlmostEqual(result["duration_s"], SOURCE_FRAMES / CANVAS_FPS, delta=0.15,
                               msg="period_motion did not compress the timeline")
        natural = self.ingest(self.clip("natural-again"),
                              record(motion_mode="retime_to_natural"))["duration_s"]
        self.assertLess(result["duration_s"], natural - 0.5)

    def test_both_modes_land_on_the_canvas_rate(self):
        for mode in ("retime_to_natural", "period_motion"):
            result = self.ingest(self.clip("rate-" + mode.replace("_", "-")),
                                 record(motion_mode=mode))
            self.assertAlmostEqual(AI.probe_fps(result["path"]), CANVAS_FPS, delta=0.05,
                                   msg=mode)

    # -- aspect -----------------------------------------------------------------
    def test_a_4_3_source_keeps_its_edge_inside_the_16_9_canvas(self):
        result = self.ingest(self.clip("pillarbox"), record(aspect="pillarbox_visible_edge"))
        self.assertEqual(AI.probe_size(result["path"]), CANVAS)
        picture_w = round(CANVAS[1] * SOURCE_SIZE[0] / SOURCE_SIZE[1] / 2) * 2
        bar = (CANVAS[0] - picture_w) // 2
        mid_y = CANVAS[1] // 2
        probe = AI.pixel
        self.assertLess(sum(probe(result["path"], 0.5, 4, mid_y)), 24,
                        "the left bar is not black, so the frame was stretched to fill")
        self.assertLess(sum(probe(result["path"], 0.5, bar - 6, mid_y)), 24,
                        "the bars do not reach the picture edge")
        self.assertGreater(sum(probe(result["path"], 0.5, bar + 12, mid_y)), 60,
                           "no picture where the 4:3 frame should start — the edge was cropped")

    def test_a_designed_container_lands_where_the_record_put_it(self):
        matte = self.work / "projector.png"
        AI.write_fixture_frame(matte, size=CANVAS, block=None, text=None, font=FONT,
                               colour=(12, 12, 14))
        rec = record(aspect="designed_container", container_image=str(matte),
                     container_rect=[400, 100, 800, 600])
        result = self.ingest(self.clip("container"), rec)
        self.assertEqual(AI.probe_size(result["path"]), CANVAS)
        inside = sum(AI.pixel(result["path"], 0.5, 800, 400))
        outside = sum(AI.pixel(result["path"], 0.5, 120, 400))
        self.assertGreater(inside, outside + 60,
                           f"the footage did not land in its container: {inside} vs {outside}")

    # -- mirror -----------------------------------------------------------------
    def test_a_textless_clip_against_the_key_is_flipped(self):
        result = self.ingest(self.clip("flip-yes"), record(light_side=OPPOSITE_SIDE))
        self.assertTrue(result["flipped"], result["flip_reason"])
        self.assertGreater(AI.find_block_x(result["path"], 0.5, canvas=CANVAS), CANVAS[0] // 2,
                           "the fixture square stayed on its own side — no hflip reached the file")

    def test_a_clip_carrying_readable_text_is_not_flipped(self):
        if self.ocr is None:
            self.skipTest("no OCR binary; the refusal path is the same as the scanner-failure "
                          "test below, so this fixture would prove nothing either way")
        src = self.clip("flip-no", text="APOLLO 11")
        # Premise: the caption has to be readable off the fixture before this can be read as a
        # guard working. A caption tesseract cannot see at all makes the assertion fire on a
        # no-flip path that is really the scanner failing, which is the opposite of the rule.
        premise = (AI.ocr_text(AI.grab_frame(src, 0.5, scale_to=CANVAS), self.ocr) or "").upper()
        self.assertIn("APOLLO", premise,
                      f"the fixture caption does not OCR off the source ({premise!r}); the mirror "
                      "guard cannot be tested against a frame nothing can read")
        result = self.ingest(src, record(light_side=OPPOSITE_SIDE))
        self.assertFalse(result["flipped"],
                         f"a caption-bearing frame was mirrored: {result['flip_reason']}")
        self.assertLess(AI.find_block_x(result["path"], 0.5, canvas=CANVAS), CANVAS[0] // 2)

    def test_no_scanner_means_no_flip_even_when_the_sides_disagree(self):
        result = self.ingest(self.clip("flip-unknown"), record(light_side=OPPOSITE_SIDE),
                             ocr=None)
        self.assertFalse(result["flipped"])
        self.assertIn("ocr", result["flip_reason"].lower())
        self.assertLess(AI.find_block_x(result["path"], 0.5, canvas=CANVAS), CANVAS[0] // 2)

    def test_a_clip_already_on_the_key_side_is_left_alone(self):
        result = self.ingest(self.clip("flip-agree"), record(light_side=key_side(CONTRACT)))
        self.assertFalse(result["flipped"])

    # -- stills -----------------------------------------------------------------
    def test_a_still_moves_and_does_not_come_back_to_where_it_started(self):
        rec = record(form="still", native_fps=None, motion_mode=None, seconds=2.0,
                     still_move={"pan_deg": 2.0, "zoom_from": 1.0, "zoom_to": 1.18})
        result = self.ingest(self.still("moving"), rec)
        self.assertAlmostEqual(result["duration_s"], 2.0, delta=0.2)
        early = AI.frame_diff(result["path"], 0.05, 0.55, canvas=CANVAS)
        self.assertGreater(early, 0.002, "the still is a frozen frame; the motion gate fails it")
        self.assertGreater(AI.frame_diff(result["path"], 1.0, 1.9, canvas=CANVAS), 0.0005,
                           "the move stopped early")
        # A looping move returns to its opening framing; a terminating one does not, and the
        # distance between the first and last frames is what separates them.
        self.assertGreater(AI.frame_diff(result["path"], 0.05, 1.9, canvas=CANVAS), early * 0.5,
                           "the last frame is near the first — the move cycles")

    def test_a_still_reaches_the_canvas_with_its_frame_edge_intact(self):
        rec = record(form="still", native_fps=None, motion_mode=None, seconds=1.0,
                     still_move={"pan_deg": 1.0, "zoom_from": 1.05, "zoom_to": 1.15})
        result = self.ingest(self.still("still-aspect"), rec)
        self.assertEqual(AI.probe_size(result["path"]), CANVAS)

    # -- source card ------------------------------------------------------------
    def test_the_credit_line_is_legible_at_the_in_point_and_gone_afterwards(self):
        if self.ocr is None:
            self.skipTest("no OCR binary to read the card back with")
        seconds = float(CONTRACT["archive"]["source_card"]["seconds"])
        # 96 frames at the source's 16 fps is six wall-clock seconds. The default fixture is
        # three, so the "afterwards" sample would land past the last frame and grab_frame would
        # raise rather than prove the card went away — a guard whose failure mode is an error
        # instead of an assertion is not a guard.
        result = self.ingest(self.clip("carded", frames=96), record(), card=True)
        early = AI.ocr_text(AI.grab_frame(result["path"], 0.4, canvas=CANVAS), self.ocr) or ""
        late = AI.ocr_text(AI.grab_frame(result["path"], seconds + 0.6, canvas=CANVAS),
                           self.ocr) or ""
        self.assertIn("Apollo", early,
                      f"the source card did not OCR back any of the credit line: {early!r}")
        self.assertNotIn("Apollo", late, f"the card outlived its declared window: {late!r}")

    def test_a_shot_with_no_credit_to_show_gets_no_card(self):
        """An empty card would draw a black box over the record, which is the opposite of the
        rule's purpose."""
        result = self.ingest(self.clip("nocard"), record(), r=row(credit_line=""), card=True)
        self.assertFalse(result["card"], result["card_reason"])

    # -- audio ------------------------------------------------------------------
    def test_the_source_audio_is_dropped_not_mixed_down(self):
        src = self.work / "with-audio.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error",
                        "-f", "lavfi", "-i", f"testsrc=size=320x240:rate={NATIVE_FPS}",
                        "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                        "-frames:v", str(SOURCE_FRAMES), "-shortest",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
                        "-c:a", "aac", str(src)], check=True)
        result = self.ingest(src, record())
        self.assertEqual(AI.probe_streams(result["path"], "a"), [],
                         "an archival clip reached the master carrying its own library music")


def size_arg(png):
    from PIL import Image
    with Image.open(png) as im:
        return f"{im.width}x{im.height}"


if __name__ == "__main__":
    unittest.main()
