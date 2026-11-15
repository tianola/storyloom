"""The episode gate: does the shipped master obey the style contract, measured on pixels?

Every number here is a measurement, not a taste. The motion bounds were calibrated on
`work/episode-artemis-ii/episode-artemis-ii.mp4` on 2026-11-10 using the gate's own
`measure_motions()` — mean absolute greyscale difference between frames **one second apart**,
across all 32 shots:

    manim reentry-angle      0.618   <- a still
    card process             0.622   <- a still (static PNG by construction)
    card bar-chart           0.666   <- a still
    manim distance           0.937   <- a still
    3d heat-shield (x3)      1.685 1.752 1.766   <- slowest real camera move
    3d earth-from-moon ...   2.580 - 2.995
    3d lunar-flyby          17.520   <- fastest

The two populations do not touch: stills end at 0.937, camera moves start at 1.685. That empty
band is where `motion_static_max` lives, and the second gap (1.766 to 2.580) is where
`motion_slow_max` lives. `look_pass` adds film grain to every frame, so a frozen image scores
0.62 rather than 0.0 — a near-zero bound would have passed all four stills.

An earlier pass calibrated these constants on a ~3 s span and produced a 2.0 bound that flagged
the heat-shield trio as photographs. Same tool, wrong span, wrong answer: the constants and the
measurement must come from one function, which is what `test_the_motion_bounds_sit_in_the_measured_gap`
now enforces.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import qc_episode  # noqa: E402
import assemble_episode  # noqa: E402
from loudness import loudnorm_filter, measure as delivery_measure  # noqa: E402
from workflow.config import style_contract  # noqa: E402

CONTRACT = style_contract(ROOT)

# Measured on the shipped Artemis II master over a one-second span, 2026-11-10.
HIGHEST_STILL = 0.937         # manim distance: the stillest shot that is not a card
LOWEST_CAMERA_MOVE = 1.685    # heat-shield: the slowest shot that is still a camera move
HIGHEST_SLOW = 1.766          # the top of the slow band
LOWEST_NORMAL = 2.580         # the bottom of the band nobody would call slow

# Measured on the real 470.6 s Artemis II narration with the gate's own floor measurer,
# 2026-11-12. Both programmes are pushed to the delivery target first, because a floor read at
# -25 LUFS and one read at -14 are not the same number.
NARRATION_FLOOR = -30.0        # the bare narration's p5 momentary floor at the target
FLOOR_LIFT_WITH_BED = 4.2     # the same narration with the generated bed laid under it
FLOOR_LIFT_WITHOUT_BED = 0.0  # the delivered master, matched the bare narration to 0.01 dB


def shot(uid, kind, name, start, duration):
    return qc_episode.Shot(id=uid, kind=kind, name=name, start=start, duration=duration)


class MotionBoundCalibration(unittest.TestCase):
    def test_the_motion_bounds_sit_in_the_measured_gap(self):
        static_max = CONTRACT["rhythm"]["motion_static_max"]
        self.assertGreater(static_max, HIGHEST_STILL,
                           "bound is inside the still population: real stills would pass")
        self.assertLess(static_max, LOWEST_CAMERA_MOVE,
                        "bound is above the slowest camera move: moving shots would be flagged")

    def test_the_slow_bound_sits_in_the_second_measured_gap(self):
        slow_max = CONTRACT["rhythm"]["motion_slow_max"]
        self.assertGreater(slow_max, HIGHEST_SLOW,
                           "bound is inside the slow band: the slowest shots would not be reported")
        self.assertLess(slow_max, LOWEST_NORMAL,
                        "bound is above the normal band: ordinary shots would be called slow")

    def test_the_measurement_span_is_the_one_the_bounds_were_calibrated_on(self):
        self.assertEqual(qc_episode.MOTION_SPAN, 1.0,
                         "the constants above were measured over one second; changing the span "
                         "without recalibrating them silently changes what the gate means")


class StaticHoldRule(unittest.TestCase):
    """The brief's rule: no image holds without motion for longer than ten seconds."""

    def test_names_the_shot_that_holds_a_still_past_the_bound(self):
        shots = [shot("u010", "manim", "distance", 0.0, 17.9)]
        findings = qc_episode.check_static_holds(shots, {"u010": 0.937}, CONTRACT)
        errors = [f for f in findings if f.severity == "error"]
        self.assertEqual(len(errors), 1)
        self.assertIn("distance", errors[0].subject)
        self.assertIn("17.9", errors[0].message)

    def test_a_static_card_over_the_bound_is_an_error_not_a_warning(self):
        shots = [shot("u023", "cards", "process", 300.0, 16.9)]
        findings = qc_episode.check_static_holds(shots, {"u023": 0.622}, CONTRACT)
        self.assertEqual([f.severity for f in findings], ["error"])

    def test_a_short_still_is_allowed(self):
        shots = [shot("u099", "cards", "title", 0.0, 4.0)]
        self.assertEqual(qc_episode.check_static_holds(shots, {"u099": 0.65}, CONTRACT), [])

    def test_a_slow_but_moving_shot_is_not_a_static_hold(self):
        shots = [shot("u017", "3d", "heat-shield", 0.0, 14.9)]
        findings = qc_episode.check_static_holds(shots, {"u017": 1.685}, CONTRACT)
        self.assertEqual([f for f in findings if f.severity == "error"], [])

    def test_a_slow_shot_is_still_reported_as_slow(self):
        shots = [shot("u017", "3d", "heat-shield", 0.0, 14.9)]
        findings = qc_episode.check_slow_shots(shots, {"u017": 1.685}, CONTRACT)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "warn")
        self.assertIn("heat-shield", findings[0].subject)

    def test_a_fast_shot_is_neither_static_nor_slow(self):
        shots = [shot("u009", "3d", "lunar-flyby", 0.0, 15.2)]
        self.assertEqual(qc_episode.check_slow_shots(shots, {"u009": 17.52}, CONTRACT), [])

    def test_a_shot_with_no_measurement_is_reported_not_silently_passed(self):
        shots = [shot("u010", "manim", "distance", 0.0, 17.9)]
        findings = qc_episode.check_static_holds(shots, {}, CONTRACT)
        self.assertEqual(len(findings), 1)
        self.assertIn("no motion measurement", findings[0].message)


class HookRule(unittest.TestCase):
    def test_a_frozen_opening_fails_the_hook(self):
        findings = qc_episode.check_hook(0.618, CONTRACT)
        self.assertEqual([f.severity for f in findings], ["error"])

    def test_a_moving_opening_passes(self):
        self.assertEqual(qc_episode.check_hook(11.242, CONTRACT), [])


class AudioRule(unittest.TestCase):
    """Measured on the shipped master: -25.3 LUFS integrated, -3.4 dBFS true peak, mono 24 kHz."""

    def test_the_shipped_master_is_too_quiet_for_broadcast(self):
        findings = qc_episode.check_loudness(-25.3, -3.4, CONTRACT)
        codes = {f.code for f in findings}
        self.assertIn("loudness_off_target", codes)
        self.assertTrue(any(f.severity == "error" for f in findings))

    def test_a_master_at_the_platform_target_passes(self):
        self.assertEqual(qc_episode.check_loudness(-14.0, -1.5, CONTRACT), [])

    def test_a_clipping_master_fails_on_true_peak(self):
        findings = qc_episode.check_loudness(-14.0, 0.4, CONTRACT)
        self.assertIn("true_peak_over", {f.code for f in findings})

    def test_mono_low_rate_audio_is_reported(self):
        findings = qc_episode.check_audio_format(channels=1, sample_rate=24000, contract=CONTRACT)
        codes = {f.code for f in findings}
        self.assertIn("audio_mono", codes)
        self.assertIn("audio_sample_rate_low", codes)

    def test_stereo_48k_audio_is_clean(self):
        self.assertEqual(qc_episode.check_audio_format(channels=2, sample_rate=48000,
                                                      contract=CONTRACT), [])


class CanvasRule(unittest.TestCase):
    def test_the_contract_canvas_is_the_one_the_assembler_renders(self):
        import assemble_episode
        canvas = CONTRACT["canvas"]
        self.assertEqual((canvas["width"], canvas["height"]),
                         (assemble_episode.WIDTH, assemble_episode.HEIGHT))
        self.assertEqual(canvas["fps"], assemble_episode.FPS)

    def test_a_wrong_resolution_is_an_error(self):
        canvas = CONTRACT["canvas"]
        wrong = 640 if canvas["width"] != 640 else 320
        findings = qc_episode.check_canvas(width=wrong, height=wrong // 2, fps="30/1",
                                           contract=CONTRACT)
        self.assertIn("canvas_resolution", {f.code for f in findings})

    def test_a_wrong_frame_rate_is_an_error(self):
        canvas = CONTRACT["canvas"]
        findings = qc_episode.check_canvas(canvas["width"], canvas["height"], "24000/1001",
                                           CONTRACT)
        self.assertIn("canvas_fps", {f.code for f in findings})

    def test_the_contract_canvas_passes_its_own_check(self):
        """Derived from the contract, so raising the canvas never edits this test again.

        An assertion that read `1280, 720` here would have failed on the *guard*, not on the
        gate, the day the contract moved to 1080p — which is the same class of bug the gate
        itself exists to catch: two files that each encode the canvas.
        """
        canvas = CONTRACT["canvas"]
        self.assertEqual(qc_episode.check_canvas(canvas["width"], canvas["height"],
                                                f"{canvas['fps']}/1", CONTRACT), [])


class TimelineRules(unittest.TestCase):
    def test_an_utterance_without_a_shot_is_an_error(self):
        manifest_ids = ["u001", "u002"]
        shots = [shot("u001", "3d", "sls-launch", 0.0, 16.5)]
        findings = qc_episode.check_coverage(shots, manifest_ids, CONTRACT)
        self.assertEqual(len(findings), 1)
        self.assertIn("u002", findings[0].message)

    def test_full_coverage_is_clean(self):
        shots = [shot("u001", "3d", "sls-launch", 0.0, 16.5)]
        self.assertEqual(qc_episode.check_coverage(shots, ["u001"], CONTRACT), [])

    def test_a_shot_longer_than_the_bound_is_reported(self):
        shots = [shot("u004", "3d", "crew-quarters", 0.0, 44.0)]
        findings = qc_episode.check_long_shots(shots, CONTRACT)
        self.assertEqual(len(findings), 1)
        self.assertIn("crew-quarters", findings[0].subject)

    def test_the_total_of_the_timeline_matches_the_video(self):
        findings = qc_episode.check_duration(measured=470.6, expected=470.6, contract=CONTRACT)
        self.assertEqual(findings, [])
        findings = qc_episode.check_duration(measured=430.0, expected=470.6, contract=CONTRACT)
        self.assertIn("duration_mismatch", {f.code for f in findings})

    def test_missing_captions_are_reported_not_assumed(self):
        findings = qc_episode.check_captions(subtitle_streams=0, contract=CONTRACT)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "warn")
        self.assertEqual(qc_episode.check_captions(subtitle_streams=1, contract=CONTRACT), [])


class LicenceRules(unittest.TestCase):
    def test_a_malformed_entry_is_an_error(self):
        findings = qc_episode.check_licence_entries([{"provider": "x"}], CONTRACT)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "error")

    def test_a_well_formed_entry_passes(self):
        entry = {"id": "a", "provider": "p", "license": "Apache-2.0", "url": "https://e.x/a",
                 "file": "media/pbr/a.webp", "shots": ["s"], "notes": ""}
        self.assertEqual(qc_episode.check_licence_entries([entry], CONTRACT), [])

    def test_an_empty_manifest_is_allowed_because_owned_assets_need_no_entry(self):
        self.assertEqual(qc_episode.check_licence_entries([], CONTRACT), [])


class ShotMapArtefact(unittest.TestCase):
    def test_the_shipped_episode_publishes_a_shot_map_the_gate_can_read(self):
        path = ROOT / "work/episode-artemis-ii/shots.json"
        self.assertTrue(path.is_file(), f"{path} missing - the assembler must publish it")
        data = json.loads(path.read_text(encoding="utf-8"))
        manifest = json.loads((ROOT / "work/episode-artemis-ii/vo/manifest.json")
                              .read_text(encoding="utf-8"))
        self.assertEqual(sorted(data), sorted(u["id"] for u in manifest["utterances"]))
        for uid, entry in data.items():
            # One vocabulary: the kinds in the shot table are the layers the contract budgets
            # screen seconds over, so the mix gate needs no translation layer to be invented.
            self.assertIn(entry["kind"],
                          tuple(CONTRACT["archive"]["episode_profile"]["mix"]["layers"]), uid)
            self.assertTrue(entry["name"], uid)

    def test_the_timeline_loader_reads_manifest_and_shot_map_together(self):
        episode = ROOT / "work/episode-artemis-ii"
        shots = qc_episode.load_timeline(episode)
        self.assertEqual(len(shots), 32)
        self.assertEqual(shots[0].id, "u001")
        self.assertAlmostEqual(shots[0].duration, 395216 / 24000, places=3)
        # starts are cumulative, so the last shot ends where the audio ends
        total = shots[-1].start + shots[-1].duration
        manifest = json.loads((episode / "vo/manifest.json").read_text(encoding="utf-8"))
        self.assertAlmostEqual(total, manifest["totalSamples"] / 24000, delta=0.01)


class MusicBedFloorCalibration(unittest.TestCase):
    """Integrated loudness cannot see a bed: `loudnorm` lands a bedless and a bed-bearing mix on
    the same -14 LUFS. The gate reads the floor between the words instead, so the bound it judges
    against has to sit in the gap the same measurer measured on real media.
    """

    def test_the_floor_bound_sits_in_the_measured_gap(self):
        bound = CONTRACT["audio"]["music_floor_lift_min_db"]
        self.assertGreater(bound, FLOOR_LIFT_WITHOUT_BED,
                           "bound is at or below a bedless master: a dropped bed would pass")
        self.assertLess(bound, FLOOR_LIFT_WITH_BED,
                        "bound is above a mastered-with-bed measurement: real beds would be "
                        "reported as missing")

    def test_the_floor_is_the_percentile_the_bound_was_calibrated_on(self):
        self.assertEqual(qc_episode.MUSIC_FLOOR_PERCENTILE, 5,
                         "the numbers above are p5 of the momentary track; a different "
                         "percentile silently redefines what the bound means")


class MusicBedRule(unittest.TestCase):
    def test_a_master_as_quiet_between_the_words_as_the_narration_has_no_bed(self):
        findings = qc_episode.check_music_bed(NARRATION_FLOOR, NARRATION_FLOOR, CONTRACT)
        self.assertEqual([f.code for f in findings], ["music_bed_missing"])
        self.assertEqual(findings[0].severity, "error")

    def test_a_master_whose_floor_the_bed_lifted_passes(self):
        self.assertEqual(
            qc_episode.check_music_bed(NARRATION_FLOOR + FLOOR_LIFT_WITH_BED,
                                       NARRATION_FLOOR, CONTRACT), [])

    def test_a_master_whose_floor_could_not_be_read_is_reported_not_passed(self):
        self.assertEqual([f.code for f in qc_episode.check_music_bed(None, NARRATION_FLOOR, CONTRACT)],
                         ["music_bed_unmeasurable"])

    def test_a_narration_that_is_not_on_disk_is_reported_not_passed(self):
        self.assertEqual([f.code for f in qc_episode.check_music_bed(-25.0, None, CONTRACT)],
                         ["music_bed_unmeasurable"])


NARRATION_SR = 24000


def narration_fixture(path, seconds=12.0):
    """Four two-second bursts of speech-shaped noise with one-second gaps, as a mono 24 kHz stem.

    The gaps are the whole point: they are where a bed has to be audible. They are not digital
    silence — the real Artemis II narration falls to about -42 LUFS between its words, and a bed
    measured against a silence it never had is a different case from one filling a gap.
    """
    n = int(seconds * NARRATION_SR)
    rng = np.random.default_rng(4)
    samples = rng.standard_normal(n) * 1e-4
    for start in (0.0, 3.0, 6.0, 9.0):
        stop = int((start + 2.0) * NARRATION_SR)
        samples[int(start * NARRATION_SR):stop] = 0.25 * rng.standard_normal(stop - int(start * NARRATION_SR))
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(NARRATION_SR)
        fh.writeframes(pcm.tobytes())
    return path


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not on PATH")
class MusicBedOnRealAudio(unittest.TestCase):
    """The gate has to catch a dropped bed on media, through the assembler's own mix step."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        work = Path(cls.tmp.name)
        cls.episode = work / "ep"
        (cls.episode / "vo").mkdir(parents=True)
        cls.narration = narration_fixture(cls.episode / "vo/full-audio.wav")
        cls.with_bed = cls._delivered(work / "delivered-with-bed.wav", bed=True)
        cls.no_bed = cls._delivered(work / "delivered-no-bed.wav", bed=False)
        cls.narration_floor = qc_episode.narration_floor(cls.episode, CONTRACT)

    @classmethod
    def _delivered(cls, dst, bed):
        """Mix, if this is the bed-bearing one, then apply the contract's delivery gain."""
        src = cls.narration
        if bed:
            src = assemble_episode.add_music_bed(src, dst.parent / "bed.wav",
                                                 dst.parent / "mixed.wav")
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(src),
             "-af", loudnorm_filter(delivery_measure(src, CONTRACT["audio"]), CONTRACT["audio"]),
             "-c:a", "pcm_s16le", str(dst)], check=True)
        return dst

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_floor_of_the_bare_narration_is_measurable(self):
        self.assertIsInstance(self.narration_floor, float)

    def test_the_gate_passes_a_master_the_bed_is_actually_in(self):
        findings = qc_episode.check_music_bed(qc_episode.momentary_floor(self.with_bed),
                                              self.narration_floor, CONTRACT)
        self.assertEqual(findings, [])

    def test_the_gate_fails_a_master_the_bed_never_reached(self):
        findings = qc_episode.check_music_bed(qc_episode.momentary_floor(self.no_bed),
                                              self.narration_floor, CONTRACT)
        self.assertEqual([f.code for f in findings], ["music_bed_missing"])


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not on PATH")
class MeasurementOnRealPixels(unittest.TestCase):
    """Guard tests with a fixture that can actually trigger them: a frozen, quiet clip."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.clip = Path(cls.tmp.name) / "frozen.mp4"
        # Thirteen seconds of one colour, and a sine pushed down to about -34 dB, so the fixture
        # trips both the static-hold rule and the loudness rule instead of accidentally passing
        # one of them. A guard test whose fixture cannot fail the guard proves nothing.
        subprocess.run([
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi", "-i", "color=c=0x203050:s=320x180:d=13:r=30",
            "-f", "lavfi", "-i", "sine=frequency=220:duration=13",
            "-filter:a", "volume=0.02",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "24000", "-ac", "1", str(cls.clip)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_a_frozen_clip_measures_below_the_still_bound(self):
        self.assertLess(qc_episode.motion(self.clip, 0.5, 1.0),
                        CONTRACT["rhythm"]["motion_static_max"])

    def test_loudness_is_parsed_as_numbers(self):
        integrated, peak, _ = qc_episode.loudness(self.clip)
        self.assertIsInstance(integrated, float)
        self.assertIsInstance(peak, float)
        # a 220 Hz sine at ffmpeg's default level is nowhere near the -14 LUFS target
        self.assertTrue(qc_episode.check_loudness(integrated, peak, CONTRACT))

    def test_probe_reports_the_canvas_and_the_audio_shape(self):
        streams = qc_episode.probe(self.clip)
        self.assertEqual((streams["width"], streams["height"]), (320, 180))
        self.assertEqual(streams["audio_channels"], 1)
        self.assertEqual(streams["audio_sample_rate"], 24000)
        self.assertEqual(streams["subtitle_streams"], 0)

    def test_the_whole_gate_fails_a_frozen_quiet_clip_and_says_why(self):
        episode = Path(self.tmp.name) / "ep"
        (episode / "vo").mkdir(parents=True)
        (episode / "vo/manifest.json").write_text(json.dumps({
            "sampleRate": 24000, "voice": "af_heart", "totalSamples": 288000,
            "utterances": [{"id": "u001", "file": "u001.wav", "text": "x",
                            "samples": 288000, "startSample": 0, "endSample": 288000}]}),
            encoding="utf-8")
        (episode / "shots.json").write_text(json.dumps(
            {"u001": {"kind": "cards", "name": "frozen"}}), encoding="utf-8")
        (episode / "assets").mkdir()
        (episode / "assets/license-manifest.json").write_text("[]", encoding="utf-8")

        report = qc_episode.run(episode=episode, master=self.clip)
        codes = {f.code for f in report}
        self.assertIn("static_hold", codes, sorted(codes))
        self.assertIn("loudness_off_target", codes)
        self.assertIn("canvas_resolution", codes)
        self.assertTrue(any(f.severity == "error" for f in report))
        text = qc_episode.render(report)
        self.assertIn("frozen", text)


if __name__ == "__main__":
    unittest.main()
