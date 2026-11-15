"""The lunar base stands on a plain, not on a ball.

`beat_lunar_base` used to model the ground its camera photographs as a radius-42 sphere, with
the camera sixteen units over it. Measured through the beat's own lens, that ball puts the
surface line at half the frame's height, curls it 3.8 degrees from the middle to the sides,
and loses the ground in 46 of the seventy-five columns the horizon ray is cast down: the limb
of a small body, not a horizon. The same sphere decides the mesh. Its rings are latitude
circles, so the ground the camera resolves is sampled at 0.36 units, and the relief left in the
band under the camera measures 0.0003 units — a smooth grey sheet.

The replacement is a radius-1200 patch reaching 170 units to its edge at a third of a unit
spacing. Measured the same way, it gives a line 10.6 % into the frame, level to half a degree
across the width, ground in every column, and 0.35 units of relief.

The probe builds the real scene, steps every pose the dolly passes through, and measures
through the real camera, so these bounds are about the rendered frame, not about constants in
the file. Coverage is ray-cast rather than counted: the mesh samples the ground every third
of a unit, so a column can hold dirt right to the last pixel row and still have no *vertex*
down there. Whether the patch reaches far enough to *be* the horizon cannot be answered that
way, and is answered instead against the tangent cone of the body the mesh was projected onto.
What the bowls themselves look like is judged on the still, not here.

Every bound below is drawn against a measured regression, each taken with this same measurer
so the number and the gate agree by construction. One row per defect, and what it measures:

    ground back to a radius-42 ball    sky 0.510, curl 3.82 deg, relief 0.0003,
                                       spacing 0.361, 46 horizon-ray misses
    terrain patch halved (half=85)     shortfall 0.322 deg, everything else in bounds
    terrain patch quartered (42.5)     shortfall 2.981 deg, 37 horizon misses
    crater field deleted               relief 0.0001, everything else in bounds

There is deliberately no bound on the crater floor on its own. `add_crater_field`'s rule is
that a bowl needs 1.6 vertex spacings, so a floor bound is the spacing bound times a constant;
one version of this file carried both, with the constant (0.60) looser than 1.6 x MAX_SPACING,
which made the second assertion impossible to fail on its own. The spacing gate is the one
that carries the information.

One gate is recorded as unexercised rather than quietly trusted. No patch size fails
`test_ground_holds_the_bottom_of_the_frame` on this shot: the camera stands 23 units out from
the patch pole while the frame's bottom edge meets the ground seven units *nearer* it, so every
patch that reaches the camera reaches the bottom edge too, and shrinking past that point takes
the camera off the plain, which the probe reports as a hard error. The assertion stays because
a longer dolly would make it live; this scene has not shown that it needs it.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from workflow.config import blender_executable

PROBE = ROOT / "tools" / "blender" / "lunar_ground_probe.py"

# Bounds. The module docstring carries the measured defect each one is drawn against.
MAX_CURL_DEG = 3.0
SKY_BAND_MIN = 0.06
SKY_BAND_MAX = 0.35
MAX_SPACING = 0.35
# The smallest bowl this field excavates is 0.9 units of radius, and `add_crater_relief`
# digs 0.42 of that: 0.38 units deep. Measured residual comes back at 0.35, which is that
# depth seen through a quartic. A painted floor patch cannot reach a hundredth of it, so
# half the smallest bowl's depth separates real relief from a drawn one.
MIN_RELIEF = 0.15
# How far the shown ground line may fall below the horizon the body's tangent cone demands.
# Measured with this exact measurer: the shipped cap gives 0.000 deg, a patch halved to
# `half=85` gives 0.322, and quartered to 42.5 gives 2.981. At this lens a degree is twenty-five
# pixels of frame height, so the quartered patch lands the ground's own cut edge seventy-five
# pixels — a tenth of the frame — below the line the Moon demands, and the halved one is eight
# pixels short. The bound sits a tenth of a degree over the shipped scene and under both.
MAX_SHORTFALL_DEG = 0.10
MAX_FACES = 1_200_000


class TestLunarBaseGround(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = subprocess.run(
            [str(blender_executable(ROOT)), "--background", "--factory-startup",
             "--python-exit-code", "1", "--python", str(PROBE)],
            capture_output=True, text=True, timeout=3600)
        if proc.returncode != 0:
            raise AssertionError(
                f"blender exited {proc.returncode}\n{proc.stdout[-4000:]}\n{proc.stderr[-4000:]}")
        marker = [ln for ln in proc.stdout.splitlines() if ln.startswith("LUNARGROUND_JSON ")]
        if not marker:
            raise AssertionError(f"no LUNARGROUND_JSON line in output:\n{proc.stdout[-4000:]}")
        cls.d = json.loads(marker[0].split("LUNARGROUND_JSON ", 1)[1])

    def test_horizon_runs_straight_across_the_frame(self):
        """The ball signature: a circular limb inside a rectangular frame."""
        self.assertLessEqual(self.d["horizon_curl_deg"], MAX_CURL_DEG,
                             f"the ground line falls {self.d['horizon_curl_deg']} deg from the "
                             f"middle of the frame to its sides")

    def test_the_frame_keeps_a_sky_band(self):
        """The ground line has to sit inside the frame, not at its top and not past it. Below
        the minimum the plain fills the shot and there is no sky, no stars and no Earth; above
        it the camera is looking over the edge of the body it stands on."""
        self.assertGreaterEqual(self.d["sky_band_frac"], SKY_BAND_MIN,
                                f"the ground fills {1 - self.d['sky_band_frac']:.0%} of the frame")
        self.assertLessEqual(self.d["sky_band_frac"], SKY_BAND_MAX,
                             f"the horizon is {self.d['sky_band_frac']:.0%} down the frame")

    def test_ground_holds_the_bottom_of_the_frame(self):
        """The terrain has to reach the frame's lower edge in every column, or the patch ended
        inside the shot and space shows under the plain. Ray-cast, not vertex-counted: a mesh
        sampled every third of a unit cannot put a vertex in the last pixel row of a column
        that is completely covered, and the first version of this measurement reported ten
        empty columns out of fifteen on a plain that rendered as dirt."""
        self.assertEqual(self.d["frame_bottom_misses"], 0,
                         f"{self.d['frame_bottom_misses']} pose-column rays fall through the "
                         f"bottom of the frame")

    def test_ground_reaches_past_the_horizon_line(self):
        """A patch narrower than the horizon: the shot carries the patch's own cut edge, or
        space, where the horizon should be.

        Measured against the body's tangent cone rather than against where the ray-cast
        boundary landed. The boundary cannot answer this: just under the horizon the line of
        sight is nearly parallel to the surface, so a ray a tenth of a degree under the
        silhouette strikes the ground scores of units nearer than the edge it is probing, and a
        quarter-size cap hid behind that (it reported a boundary well inside its own edge and
        this assertion passed on a scene that visibly fails). The cone is independent of the
        mesh, so the difference between the two is the height of the step.
        """
        self.assertEqual(self.d["horizon_misses"], 0,
                         f"{self.d['horizon_misses']} pose-column rays escape past the ground")
        self.assertLessEqual(self.d["horizon_shortfall_deg"], MAX_SHORTFALL_DEG,
                             f"the ground line sits {self.d['horizon_shortfall_deg']} deg below "
                             f"its own horizon: the {self.d['cap_half']}-unit patch runs out "
                             f"before the tangent ring and the frame shows its cut edge")

    def test_vertices_sit_where_the_camera_is(self):
        self.assertLessEqual(self.d["near_band_spacing"], MAX_SPACING,
                             f"the ground under the camera is sampled at "
                             f"{self.d['near_band_spacing']} units")

    def test_near_band_is_not_a_smooth_sheet(self):
        """The residual left after the quartic fits the body's curvature out. A plain carrying
        painted floor patches only measures the tile, which is under a millimetre here; the
        0.35 units this band gives back are displaced bowls, and that is the difference between
        excavated dirt and a grey sheet with circles drawn on it."""
        self.assertGreaterEqual(self.d["relief_p99"], MIN_RELIEF,
                                f"the ground under the camera holds {self.d['relief_p99']} "
                                f"units of relief")

    def test_terrain_stays_inside_the_starfield(self):
        self.assertEqual(self.d["outside_starfield"], 0)

    def test_face_budget(self):
        self.assertLessEqual(self.d["ground_faces"], MAX_FACES,
                             f"{self.d['ground_faces']} faces in the ground mesh")


if __name__ == "__main__":
    unittest.main()
