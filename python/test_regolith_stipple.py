"""The lunar ground carries grain in its geometry, or it reads as a printed sheet.

Between the photographic regolith tile and the crater bowls the ground has nothing. `apply_
surface` puts the tile at 0.6 units per repeat, so its pebbles land three to five pixels wide
in the near band, and `add_crater_field` puts bowls at a quarter unit to four. A four-pixel
albedo dot with no shadow attached to it is ink on paper. `add_regolith_stipple` is the answer:
it displaces the mesh that is already there at the finest wavelength that mesh can carry, so the
same speckle gets a lit flank and a dark one, at no cost in vertices, faces, samples or pixels.

This file is the gate on that claim, and it exists because the helper shipped with a docstring,
a validation script and *zero call sites*. Nothing in the pipeline would have noticed if it had
stayed that way: the beats render, the episode assembles, and the ground keeps reading as a
sheet. So the first test below is about call sites, and the second is about which beats are
allowed not to have them.

The rest is mesh-level, measured by `_scratch/stipple/stipple_probe.py`, which builds every
stippled beat twice — once with the real function and once with it stubbed — and hands back an
exact before/after pair for the surface its own camera stands on:

  * vertices outside the masked arc window are bit-identical, so the effect cannot leak onto
    the silhouette or onto the far field, where one unit of ground is a handful of pixels;
  * the vertex and face counts hold, and no custom-data layer is left behind, so the helper
    displaces the mesh it was given instead of building a new one (the `BMLayerItem` bug this
    round fixed wrote three named float layers into every ground it touched);
  * the mesh-local high-pass inside the band goes up, which is the difference between relief
    and a painted pattern;
  * the same call applied twice lands bit-for-bit, so a rollout cannot shimmer between frames.

Bounds are calibrated with the measurer that checks them, on this machine, on these meshes.
Both blocks below are the `STIPPLEPROBE TABLE` that `_scratch/stipple/stipple_probe.py` prints
itself — Blender 4.5.15, factory startup, the beats' own mid frame — and that run is saved in
`_scratch/stipple/stipple_probe-fixed.log` (2026-11-12, after the noise cycle was measured rather
than assumed). The table is printed by the probe rather than kept here because a table that has
to be copied by hand drifts: the version this docstring carried quoted "before" medians of
0.000162 and 0.000173 for the two caps, which no probe run has ever produced on those meshes, and
the bounds were set against them. `pf` is the full-weight zone, arc <= `arc[0]`; every other
column is the whole masked window, cosine fade included.

    beat              ground          masked     full   spacing wavelength     amp    max_up   mean_off rms_slope p99_slope
    beat_lunar_flyby  MoonSurface      14663     7295    0.7932     3.9660   0.080   0.07544   0.000157    0.0289    0.0778
    beat_earth_rise   RiseCap         104535    32390    0.0664     0.3318   0.024   0.02282  -0.000011    0.0792    0.2298
    beat_earth_from_moon EarthViewCap    130404    39507    0.1235     0.6174   0.028   0.02518   0.000001    0.0496    0.1446

    beat              before_p50  after_p50  before_pf   after_pf  ratio_pf field/amp field/ampf      rose rose_plain
    beat_lunar_flyby   0.0010399  0.0073940  0.0011879  0.0090394      7.61   0.04700    0.06725    0.7653   0.8529
    beat_earth_rise    0.0000014  0.0013553  0.0000014  0.0026912   1934.89   0.05186    0.11147    0.9374   0.9908
    beat_earth_from_moon  0.0000021  0.0016825  0.0000805  0.0031028     38.53   0.05086    0.10570    0.8990   0.9777

The first block is what the helper worked with, read off the info dict its call returns; the
second is what the mesh ended up carrying, measured by building each beat twice — once with the
function and once with it stubbed — and taking `|r_i - mean(r of the 1-ring)|` off the result.
The full-weight columns are the reason this round exists. `amp` is the half-height where the mask
is 1.0, and only 30-50 % of the masked window ever reaches that weight; the rest is the cosine
fade, which receives a fraction of the grain *on purpose*, so reading amp-relative statistics over
the window measured the helper's own fade-out as missing relief. The same statistic is 0.0074 /
0.0014 / 0.0017 across the window and 0.0090 / 0.0027 / 0.0031 at full weight, and the field per
`amp` is 0.047-0.052 against 0.067-0.111.

The middle columns of the second block are why the relief bound is a median and not a p99. The
head of that distribution belongs to the crater rims: on the flyby the untouched one-edge
difference there runs 0.0840 units at p99, against a stipple field whose own strongest vertex
reaches 0.0196, so grain cannot move the head of the list whatever it does to the body of it —
earth-from-moon's p99 moves by 8.5 % (0.011649 -> 0.012642) while its full-weight median moves by
a factor of 38.5. The median is where ordinary ground in the band lives, and that is the population
the claim is about. The same argument is why `rose` is counted twice,
once over the whole band and once over the plain (untouched residual at or below that band's p75):
on the flyby the band's own upper quartile of untouched roughness is 0.020683 units, more than the
stipple's field puts in at its *strongest* vertex (field p99 0.019641), so a quarter of that mesh
cannot gain structure from this call at any amplitude that is still grain, and the whole-band
fraction sits at 0.765 where the plain fraction is 0.853.

Relief per `amp` is bounded rather than relief in units, because the three grounds differ 12x in
edge spacing (0.0664 / 0.1235 / 0.7932) and a displaced mesh hands a fixed *fraction* of `amp` to
one edge: 0.048 of the field's own peak at five vertices per cycle, 0.124 at two and a half
(`_scratch/stipple/noise_scale.py`, synthetic grid). Read in bare units, the inherited 0.0020 was
not one requirement but three — 0.25 % of a spacing on the flyby, 3.0 % on the rise cap, 1.6 % on
the view cap — and scored across the window population it asked for an `amp` of 0.035 on the rise
cap and 0.033 on the view cap, against the 0.024 and 0.028 the calls actually use. Only the first
is forbidden outright: 0.035 of half-height is 0.071 of peak-to-trough grain, deeper than the
shallowest bowl in that cap's own crater field (0.052 units), which is the condition the helper's
docstring makes on raising `amp`; the view cap's bowls are 0.26 deep, so 0.033 there would have
been legal. Both numbers are the fade's doing rather than the grain's, and that is the point — the
same bare figure was demanding different things of three beats. So the absolute bound moved to the
population where `amp` means what it says, and the amp-relative bound next to it is the one that
compares the three beats.

There is deliberately no bound here on what the render looks like. That is judged on the sheet,
against the pre-change band measurements in `_scratch/stipple/baseline.txt`, which
`_scratch/stipple/measure_band.py` recomputes from whatever stills the controller renders next;
this file can only prove the geometry did what the helper says it does.
"""
import ast
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from workflow.config import blender_executable  # noqa: E402

MODULE = ROOT / "tools" / "blender" / "artemis_beats.py"
PROBE = ROOT / "_scratch" / "stipple" / "stipple_probe.py"

# Beats whose near foreground is ordinary terrain, so grain belongs on it.
STIPPLED_BEATS = ("beat_lunar_flyby", "beat_earth_rise", "beat_earth_from_moon")

# `beat_lunar_base` has a near ground and is deliberately NOT stippled. Its arc window is
# measured from the sub-camera point, and on this shot the camera stands 23 units out from the
# patch pole while the graded pad reaches 11 units in from it — so the pad sits at arc 12 to 34
# from the camera, and the measurement band's own ground is arc 18 to 29. No camera-centred
# window can hold the band without also holding the pad, and the beat is explicit that the pad
# must stay flat ("a displaced bowl under a habitat ring drops the floor out from under it").
# The exemption is pinned rather than omitted: `test_pad_exempt_beats_are_not_stippled` fails
# if the beat half-wires it, and `test_every_regolith_ground_beat_is_accounted_for` fails if a
# new regolith ground joins neither list.
PAD_EXEMPT_BEATS = ("beat_lunar_base",)

# --- bounds, each set by a row of the calibration table above ------------------------------
MIN_CALL_SITES = 3
# The median one-edge residual of the FULL-WEIGHT zone after the stipple, in units: the vertices
# at arc <= `arc[0]`, where the mask is 1.0 and `amp` therefore means the half-height actually
# applied. The three wired beats measure 0.00904 / 0.00269 / 0.00310 there; the same statistic
# across the whole masked window is 0.0074 / 0.0014 / 0.0017, because the cosine fade spends half
# its vertices at a fraction of `amp` by design, which is the helper working as documented rather
# than grain going missing. The value is inherited: two thousandths was already below every
# working call and above every mesh that got nothing, and it stays both — the untouched
# full-weight median is 0.001188 on the flyby and 1.4e-6 / 8.1e-5 on the two caps.
MIN_RESID_P50_ABS = 0.0020
# How many times over the stipple multiplied that median, on the same zone: 7.6 / 1935 / 38.5.
# The flyby is the weak one — its mesh is twelve times coarser than the rise cap's and its ground
# is already rough, so the same grain competes with terrain for the median — and the bound therefore
# sits under 7.6 rather than anywhere near the caps' figures. A stipple that did nothing scores 1.00
# on all three. The value is inherited and was never reachable before this round: the helper that
# shipped sampled the noise at `1 / wavelength` on the assumption that one unit of the noise
# coordinate is one visible cycle, measured at 2.5, and scored 2.74 here instead of 7.6.
MIN_RESID_P50_RATIO = 4.0
# The same claim with the denominator removed: `resid_after_full_p50 - resid_before_full_p50` is
# 0.0078515 / 0.0026898 / 0.0030223 on the three wired beats, so every one of them adds at least
# this file's own minimum real roughness in bare units. The value is inherited rather than tuned --
# it is `MIN_RESID_P50_ABS` again, read as a difference -- and #133 is the reason it is spelled out:
# on `beat_earth_rise` the untouched full-weight median is 1.4e-06, so its 1934.89x ratio measures
# how flat the cap was before the call, not what the call put into it. The absolute bound above
# already stops that cap from passing with nothing, but ABS and ratio together still let a mesh
# through whose roughness was already there: 0.0005 -> 0.0020 clears both (exactly 4.00x, exactly
# at the bound) while adding 0.0015, and `TestResidGainIsAbsolute` pins that case. A stipple that
# did nothing scores 0.0000000 here.
MIN_RESID_GAIN_ABS = MIN_RESID_P50_ABS
# …and how much of the band gained structure rather than merely moved, counted over the plain
# rather than the whole band: 0.853 / 0.991 / 0.978, against 0.817 / 0.977 / 0.948 with the cycle
# constant assumed to be 1 — the bound does catch the defect, it simply was never reached before
# this round, because every run aborted on the absolute bound above it. Plain is the ground between
# the bowls — vertices whose untouched one-edge residual is at or below the band's p75 — which is
# the population the sentence in the helper's docstring is about. Counting crater rims into it holds
# the flyby at 0.736-0.789 however the helper is tuned (swept across a 4.5x range of the cycle
# constant), because a quarter of that mesh sits where the terrain's own difference runs 0.0207 to
# 0.0840 units against a grain whose p99 is 0.0196: on those vertices no amplitude that is still
# grain rather than dunes can win. The shipped flyby clears this bound by 0.0029, the thinnest
# margin of the five, so it is the first number to re-read if the probe moves under a re-render.
MIN_RESID_ROSE_FRAC = 0.85
# The stipple's own one-edge grain, measured off the displacement field alone so the existing
# terrain cannot dilute it, at full weight, as a fraction of the `amp` asked for: 0.067 / 0.111 /
# 0.106. The inherited 0.12 was unreachable at the wavelength this same file demands, and it too
# had never been evaluated: every pre-fix run aborted two asserts earlier. A field from
# `mathutils.noise.noise` keeps 0.048 of its own peak across one edge at five vertices per cycle
# and 0.124 at two and a half (`_scratch/stipple/noise_scale.py`), so 0.12 asks for the
# sub-Nyquist shimmer `MIN_VERTS_PER_CYCLE` forbids — the two bounds contradicted each other, and
# the only configuration measured here that beat 0.12 (0.167 on the view cap, the `cyc = 4.5` row
# of `_scratch/stipple/cyc_sweep2.log`) did it with 3.3 of this function's spacing edges inside one
# delivered cycle, which is the shimmer. 0.05 sits just above the theoretical carry limit at the
# floor, clears every measurement the shipped package scored (0.0237 / 0.0276 / 0.0265, the
# `cyc = 1` rows of `_scratch/stipple/cyc_sweep.log` and `cyc_sweep2.log`) by 1.8x, and is 25 %
# under the weakest beat.
MIN_FIELD_P50_FRAC = 0.05
# `amp` is the half-height at full mask weight and the field's peak does not always sit inside
# `arc[0]`, so the measured peak is at or below it — never above, which is the half of the claim
# that protects the `lift` keeping a terrain cap off the sphere underneath it.
MAX_UP_OVER_AMP = 1.0 + 1e-6
# `scale = amp / peak` is taken over the masked vertices, so the largest move the field reaches
# sits just under `amp` and everything inside the cosine fade sits further under it: measured
# max_up/amp of 0.94 / 0.95 / 0.90 and max_down/amp of 0.86 / 1.00 / 0.89 as shipped, against
# 0.75 / 0.93 / 0.89 from the pre-fix probe. Nothing this round ever fell under 0.70, and the
# bound says so rather than pretending to be a near miss: it is inherited, and what it guards is a
# normalisation taken against anything other than the masked peak — a fixed assumption about the
# noise's range, or a peak measured over the whole mesh instead of over the window — which would
# deliver a fraction of the grain the call asked for while still sitting under `MAX_UP_OVER_AMP`.
MIN_UP_OVER_AMP = 0.70
# A one-sided field would inflate the patch; re-centring against the masked vertices holds the
# mean offset at 0.0020 / 0.0005 / 0.00004 of `amp` on the three wired beats, against 0.0033 /
# 0.0027 / 0.0015 from the pre-fix probe (the two-octave field was the one-sided one). The bound
# is ten times the shipped worst case and two thirds over the pre-fix worst case: it is a leak
# detector for the re-centring, not a measurement of the grain.
MAX_MEAN_OFFSET_FRAC = 0.02
# The function floors one cycle at `verts_per_cycle` of the 99th percentile of the masked edges
# and reports `wavelength / spacing` back, so what this asserts is that the call sites asked for
# the floor the helper documents: all three get exactly 5.0, and a beat that passed 2.5 would fail
# here. The margin the bound is really buying is that same count against the band's *median* edge
# — 5.5 / 5.6 / 5.8 vertices per cycle as shipped, against 6.1 / 6.8 / 6.9 when a single
# crater-wall edge set the spacing, which was the mesh being under-used rather than over-used.
# Below the floor the surface averages the wave away and what is left is a shimmer between frames.
MIN_VERTS_PER_CYCLE = 5.0


def _beat_functions(tree):
    return {n.name: n for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name.startswith("beat_")}


def _calls_in(node):
    return [c for c in ast.walk(node)
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)]


def resid_gain_full_p50(d):
    """Roughness the stipple itself added at full mask weight, in units, not as a quotient.

    `resid_p50_ratio_full` divides by the untouched median, which on a flat terrain cap is
    1.4e-06 -- a hundred times under this file's own floor for real roughness -- so the quotient
    grows by praising the base. Subtracting removes the base instead of dividing by it.
    """
    return d["resid_after_full_p50"] - d["resid_before_full_p50"]


def regolith_ground_beats():
    """Every beat that prints the regolith tile on a surface — the beats the stipple is for.

    Read off the module, not off a list, so a new lunar ground cannot join the file unnoticed.
    """
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    out = []
    for name, fn in _beat_functions(tree).items():
        for c in _calls_in(fn):
            if c.func.id != "apply_surface":
                continue
            keys = [a.value for a in c.args if isinstance(a, ast.Constant) and
                    isinstance(a.value, str)]
            if "regolith" in keys:
                out.append(name)
                break
    return sorted(set(out))


def stipple_call_sites():
    """Call sites of `add_regolith_stipple`, excluding its own `def` and every mention inside
    a docstring or comment."""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == "add_regolith_stipple":
            hits.append(node)
    return hits


class TestRegolithStipple(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not PROBE.exists():
            raise AssertionError(
                f"missing probe script: {PROBE}\n"
                "This test is not skippable: the defect it exists to catch is a stipple helper "
                "that nobody calls, and a silent skip is how that stayed true for a round.")
        proc = subprocess.run(
            [str(blender_executable(ROOT)), "-b", "--factory-startup",
             "--python-exit-code", "1", "--python", str(PROBE), "--",
             *STIPPLED_BEATS, *(f"no:{b}" for b in PAD_EXEMPT_BEATS)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=5400)
        if proc.returncode != 0:
            raise AssertionError(
                f"blender exited {proc.returncode}\n{proc.stdout[-4000:]}\n{proc.stderr[-2000:]}")
        marker = [ln for ln in proc.stdout.splitlines() if ln.startswith("STIPPLEPROBE_JSON ")]
        if not marker:
            raise AssertionError(f"no STIPPLEPROBE_JSON line in output:\n{proc.stdout[-4000:]}")
        cls.report = json.loads(marker[0].split("STIPPLEPROBE_JSON ", 1)[1])
        cls.by_beat = {b["beat"]: b for b in cls.report["beats"]}
        for beat in (*STIPPLED_BEATS, *PAD_EXEMPT_BEATS):
            if beat not in cls.by_beat:
                raise AssertionError(f"the probe said nothing about {beat}")
        cls.errors = {e[0]: e[1] for e in cls.report["errors"]}

    # ---------------------------------------------------------------- call sites, the bug

    def test_helper_is_called_somewhere(self):
        """The inherited defect: the function existed and nothing called it."""
        sites = stipple_call_sites()
        self.assertGreaterEqual(
            len(sites), MIN_CALL_SITES,
            f"add_regolith_stipple has {len(sites)} call site(s) in {MODULE.name}; the helper "
            f"is dead code and the near ground is still a printed sheet")

    def test_every_regolith_ground_beat_is_accounted_for(self):
        """A new lunar ground must be stippled or explicitly exempted, never quietly skipped."""
        found = set(regolith_ground_beats())
        expected = set(STIPPLED_BEATS) | set(PAD_EXEMPT_BEATS)
        self.assertEqual(
            found, expected,
            f"beats that print the regolith tile: {sorted(found)}; beats this test knows about: "
            f"{sorted(expected)}. Add the stipple call, or add a reasoned exemption.")
        self.assertGreaterEqual(len(found), 4,
                                "the scan found almost nothing, which would make the check "
                                "above vacuous")

    def test_stippled_beats_reach_the_ground_under_their_camera(self):
        """Not "the beat contains the call": the call has to land on the surface the lens is on.

        earth-rise and earth-from-moon each tile two surfaces — the body and the terrain cap
        lifted over it — and only the cap is what the camera stands on.
        """
        for beat in STIPPLED_BEATS:
            with self.subTest(beat=beat):
                d = self.by_beat[beat]
                self.assertTrue(d.get("stippled_ground"),
                                f"{beat} built {d['ground']} under its camera and never "
                                f"stippled it; calls recorded on: {d['stipple_calls']}")

    def test_pad_exempt_beats_are_not_stippled(self):
        """The lunar base's graded pad must stay flat, so its ground must stay unstippled.

        Pinned in both directions: the exemption is a decision with a measured reason, not an
        oversight, and if someone wires the stipple there the pad under the habitat rings starts
        to ripple.
        """
        for beat in PAD_EXEMPT_BEATS:
            with self.subTest(beat=beat):
                d = self.by_beat[beat]
                self.assertFalse(d.get("stippled_ground"),
                                 f"{beat} is exempt because its arc window cannot exclude the "
                                 f"graded pad, yet it called the stipple on "
                                 f"{d['ground']} ({d['stipple_calls']})")

    # ------------------------------------------------------------------ the mesh itself

    def test_nothing_outside_the_window_moves(self):
        for beat in STIPPLED_BEATS:
            with self.subTest(beat=beat):
                d = self.by_beat[beat]
                self.assertGreater(d["outside_window_verts"], 0,
                                   f"{beat}: the window covered the whole mesh, so there was "
                                   f"no outside to test")
                self.assertEqual(d["outside_window_moved"], 0,
                                 f"{beat}: {d['outside_window_moved']} vertices beyond arc "
                                 f"{d['arc_window'][1]} moved, by up to "
                                 f"{d['max_move_outside']:.6f} units — the far field and the "
                                 f"silhouette are not untouched")

    def test_it_displaces_the_mesh_instead_of_adding_one(self):
        for beat in STIPPLED_BEATS:
            with self.subTest(beat=beat):
                d = self.by_beat[beat]
                self.assertEqual(d["verts_after"], d["verts_before"],
                                 f"{beat}: vertex count changed {d['verts_before']} -> "
                                 f"{d['verts_after']}")
                self.assertEqual(d["faces_after"], d["faces_before"],
                                 f"{beat}: face count changed {d['faces_before']} -> "
                                 f"{d['faces_after']}")

    def test_it_leaves_no_private_layers_in_the_mesh(self):
        """The bmesh float layers this helper used to create rode along in every mesh copy."""
        for beat in STIPPLED_BEATS:
            with self.subTest(beat=beat):
                d = self.by_beat[beat]
                for layers in (d["mesh_layers"], d["layers_after"]):
                    self.assertEqual([n for n in layers if n.startswith("stipple")], [],
                                     f"{beat}: stipple custom-data layers left in the mesh")

    def test_residual_roughness_in_the_band_goes_up(self):
        """The whole point: ordinary ground in the band has structure at a few vertices' scale.

        Measured as a median and a count, not as a p99. The head of that distribution is crater
        rim, whose untouched one-edge difference on the flyby runs 0.0840 units at p99 against a
        stipple field whose strongest vertex is 0.0196 — four times out of this call's reach — so
        the head barely moves while the body of the list doubles: earth-from-moon's window p99 goes
        0.011649 -> 0.012642, +8.5 %, while the same call multiplies its full-weight median by 38.5.
        A bound on the p99 would be a bound on the craters.

        All four are read on the full-weight zone, arc <= `arc[0]`. `amp` is defined there, and
        the masked window also contains the cosine fade, whose vertices receive a fraction of the
        grain on purpose; counting them is what made the inherited absolute and field bounds read
        as though the stipple were doing 52 to 82 % of what it does (window median over full-weight
        median: 0.0074/0.0090, 0.0014/0.0027, 0.0017/0.0031).
        """
        for beat in STIPPLED_BEATS:
            with self.subTest(beat=beat):
                d = self.by_beat[beat]
                self.assertGreater(d["band_verts"], 100,
                                   f"{beat}: only {d['band_verts']} vertices inside the window, "
                                   f"so nothing below is a population statistic")
                self.assertGreater(d["full_verts"], 100,
                                   f"{beat}: only {d['full_verts']} vertices at full mask weight, "
                                   f"so the bounded population is too small to be a statistic")
                self.assertGreaterEqual(d["resid_after_full_p50"], MIN_RESID_P50_ABS,
                                        f"{beat}: the full-weight median one-edge residual is "
                                        f"only {d['resid_after_full_p50']:.6f} units after the "
                                        f"stipple ({d['resid_after_p50']:.6f} across the whole "
                                        f"window, fade included)")
                self.assertGreaterEqual(d["resid_p50_ratio_full"], MIN_RESID_P50_RATIO,
                                        f"{beat}: the stipple multiplied the full-weight median "
                                        f"roughness by only {d['resid_p50_ratio_full']:.2f}x "
                                        f"({d['resid_before_full_p50']:.6f} -> "
                                        f"{d['resid_after_full_p50']:.6f})")
                self.assertGreaterEqual(d["resid_rose_plain"], MIN_RESID_ROSE_FRAC,
                                        f"{beat}: only {d['resid_rose_plain']:.3f} of the "
                                        f"{d['resid_plain_verts']} plain band vertices gained "
                                        f"structure rather than merely moving "
                                        f"({d['resid_rose_frac']:.3f} counted over the whole "
                                        f"band, crater rims included)")
                self.assertGreaterEqual(resid_gain_full_p50(d), MIN_RESID_GAIN_ABS,
                                        f"{beat}: the stipple added "
                                        f"{resid_gain_full_p50(d):.6f} units of full-weight "
                                        f"roughness ({d['resid_before_full_p50']:.7f} -> "
                                        f"{d['resid_after_full_p50']:.7f}), which is "
                                        f"{resid_gain_full_p50(d) / MIN_RESID_GAIN_ABS:.2f}x the "
                                        f"bound; its ratio reads "
                                        f"{d['resid_p50_ratio_full']:.2f}x, and on a base of "
                                        f"{d['resid_before_full_p50']:.7f} that figure is a "
                                        f"statement about how flat the cap was, not about grain")
                self.assertGreaterEqual(d["resid_field_full_p50"], MIN_FIELD_P50_FRAC * d["amp"],
                                        f"{beat}: the displacement field on its own carries "
                                        f"{d['resid_field_full_p50']:.6f} of grain at one edge at "
                                        f"full weight, against an amp of {d['amp']} "
                                        f"({d['resid_field_full_p50'] / d['amp']:.4f} of it) — "
                                        f"the mesh is averaging this wavelength out, which is the "
                                        f"shimmer `add_regolith_blocks` was written to avoid")

    def test_deterministic_for_a_fixed_seed_and_frame(self):
        for beat in STIPPLED_BEATS:
            with self.subTest(beat=beat):
                d = self.by_beat[beat]
                self.assertTrue(d["deterministic_same_mesh"],
                                f"{beat}: applying the same call to the same mesh twice gave "
                                f"different vertices")
                self.assertTrue(d["deterministic_across_builds"],
                                f"{beat}: the beat's own call and a replay of it on a fresh "
                                f"build disagree, worst vertex off by "
                                f"{d.get('max_build_diff')} units")

    def test_amp_is_the_measured_half_height(self):
        """`amp` bounds the grain's half-height; it is reached only where the mask is at full
        weight, so a field whose peak happens to fall inside the fade comes out under it.

        The upper half is the load-bearing one. A call that over-shot `amp` would lift a terrain
        cap into the `lift` keeping it off the sphere underneath, which is the failure
        `add_terrain_cap` documents, and the lower half is what says the re-scaling is doing its
        job at all rather than writing noise two orders of magnitude too small.
        """
        for beat in STIPPLED_BEATS:
            with self.subTest(beat=beat):
                d = self.by_beat[beat]
                up = d["info"]["max_up"] / d["amp"]
                down = abs(d["info"]["max_down"]) / d["amp"]
                self.assertLessEqual(up, MAX_UP_OVER_AMP,
                                     f"{beat}: displaced {d['info']['max_up']:.6f} upward on an "
                                     f"amp of {d['amp']} — the field overshoots its own bound")
                self.assertLessEqual(down, MAX_UP_OVER_AMP,
                                     f"{beat}: displaced {d['info']['max_down']:.6f} downward on "
                                     f"an amp of {d['amp']}")
                self.assertGreaterEqual(up, MIN_UP_OVER_AMP,
                                        f"{beat}: the largest upward move was only "
                                        f"{d['info']['max_up']:.6f} against an amp of {d['amp']} "
                                        f"({up:.3f}x), so the re-scaling is not delivering the "
                                        f"grain the call asked for")

    def test_it_does_not_inflate_the_surface(self):
        """A one-sided field would lift a terrain cap into the `lift` that keeps it off the
        sphere underneath, and `add_terrain_cap` is explicit about what that costs."""
        for beat in STIPPLED_BEATS:
            with self.subTest(beat=beat):
                d = self.by_beat[beat]
                self.assertLessEqual(abs(d["info"]["mean_offset"]),
                                     MAX_MEAN_OFFSET_FRAC * d["amp"],
                                     f"{beat}: mean offset {d['info']['mean_offset']:.6f} on "
                                     f"amp {d['amp']}")

    def test_wavelength_is_one_the_mesh_can_carry(self):
        for beat in STIPPLED_BEATS:
            with self.subTest(beat=beat):
                d = self.by_beat[beat]
                self.assertGreaterEqual(d["info"]["verts_per_cycle"], MIN_VERTS_PER_CYCLE,
                                        f"{beat}: {d['info']['verts_per_cycle']} vertices per "
                                        f"cycle at spacing {d['spacing']}")
                self.assertGreater(d["max_move_inside"], 0.0,
                                   f"{beat}: nothing inside the window moved at all")

    # --------------------------------------------------------------------- refusal cases

    def test_it_refuses_a_window_that_masks_nothing(self):
        self.assertTrue(self.errors["nothing inside the window"],
                        "an empty arc window must raise, not silently no-op: a beat whose "
                        "stipple misses its ground entirely is the bug this whole file exists "
                        "to catch")

    def test_it_refuses_an_arc_that_does_not_reach_outward(self):
        self.assertTrue(self.errors["arc not reaching outward"])

    def test_it_refuses_a_camera_at_the_body_centre(self):
        self.assertTrue(self.errors["camera at the body centre"])


class TestResidGainIsAbsolute(unittest.TestCase):
    """A ratio whose denominator is the flatness of the base is not evidence of grain.

    No Blender: this is the arithmetic of the bound itself, and it is the half of #133 that can be
    checked in a second. The live meshes are covered by
    ``TestRegolithStipple.test_residual_roughness_in_the_band_goes_up``.
    """

    def test_a_stipple_that_added_nothing_fails_here_though_both_inherited_bounds_pass(self):
        added_nothing = {"resid_before_full_p50": 0.0005, "resid_after_full_p50": MIN_RESID_P50_ABS}
        self.assertGreaterEqual(added_nothing["resid_after_full_p50"], MIN_RESID_P50_ABS,
                                "fixture must sit on the absolute bound, not under it")
        self.assertGreaterEqual(added_nothing["resid_after_full_p50"]
                                / added_nothing["resid_before_full_p50"], MIN_RESID_P50_RATIO,
                                "fixture must clear the ratio bound too, or it proves nothing")
        self.assertLess(resid_gain_full_p50(added_nothing), MIN_RESID_GAIN_ABS,
                        f"a stipple that added "
                        f"{resid_gain_full_p50(added_nothing):.6f} units at full weight passes the "
                        f"absolute bound and the ratio bound together; only the gain can see it")


if __name__ == "__main__":
    unittest.main()
