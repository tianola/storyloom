"""4 Manim animations for the Artemis II episode.

Scenes:
  1. TrajectoryScene     — TLI burn: Earth-to-Moon trajectory arc
  2. FreeReturnScene     — Free-return figure-8 path around the Moon
  3. DistanceScene       — Record distance 252,756 mi from Earth
  4. ReentryAngleScene   — Direct vs skip reentry corridor

Render (from project root, with .venv active):
    manim -qh --format=mp4 tools/manim/artemis_manim.py TrajectoryScene
    manim -qh --format=mp4 tools/manim/artemis_manim.py FreeReturnScene
    manim -qh --format=mp4 tools/manim/artemis_manim.py DistanceScene
    manim -qh --format=mp4 tools/manim/artemis_manim.py ReentryAngleScene
"""
import math
import shutil
from pathlib import Path

import numpy as np

from manim import (
    Scene, Text, MathTex, Circle, Dot, Line, Arrow, Arc,
    Create, Write, FadeIn, FadeOut, DrawBorderThenFill,
    MoveAlongPath, Rotate, AnimationGroup, LaggedStart, Succession, Wait, linear,
    MoveToTarget,
    UP, DOWN, LEFT, RIGHT, ORIGIN, OUT, IN,
    config, PI, TAU,
    Rectangle, RoundedRectangle, DashedLine, Angle,
    GrowArrow, Transform, ReplacementTransform,
    VGroup, Square,
)
from manim import RED, BLUE, WHITE, GREY, YELLOW, GOLD, GREEN, ORANGE, DARK_GREY, LIGHT_GREY

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
OUTPUT_DIR = PROJECT_ROOT / "work" / "episode-artemis-ii" / "renders" / "manim"

BG = "#06081A"
AMBER = "#FFB347"
CYAN = "#5FD4FF"
EARTH_BLUE = "#2855AE"
MOON_GREY = "#888888"
FLAME_ORANGE = "#FF8C1A"
WHITE_C = "#FFFFFF"
GOLD_C = "#D4A843"


def _setup():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def scan_sweep(total, color=CYAN, opacity=0.12, width=4.0):
    """A wide translucent band that crosses the frame once over the whole shot.

    A diagram is almost empty space: a zoom or a pan moves only thin strokes, so the shot
    still measures as a still — 0.62 on the episode gate, indistinguishable from a frozen PNG.
    Motion a viewer registers needs *area* changing, and a band this wide travelling this fast
    changes roughly sixty thousand pixels a second. It is also the house device for cards
    (assemble_episode.make_scene_card_clip), so sparse content moves the same way everywhere.
    """
    band = Rectangle(width=width, height=16.0, stroke_width=0,
                     fill_color=color, fill_opacity=opacity)
    band.move_to(LEFT * 10.0)
    band.generate_target()
    band.target.move_to(RIGHT * 10.0)
    # MoveToTarget with explicit kwargs, not `band.animate...set_run_time()`: in manim 0.22.1
    # the builder's set_run_time is silently ignored and builds a 1 s animation, which sent an
    # earlier version of this sweep across the frame in one second — gone before any of the
    # gate's measurement windows opened.
    return band, MoveToTarget(band, run_time=total, rate_func=linear)


class TrajectoryScene(Scene):
    """TLI burn: curved trajectory from Earth to Moon."""

    def construct(self):
        self.camera.background_color = BG
        _setup()

        earth = Dot(point=LEFT * 4.5, radius=0.45, color=EARTH_BLUE)
        earth_label = Text("Earth", font_size=18, color=WHITE_C).next_to(earth, DOWN, buff=0.25)

        moon = Dot(point=RIGHT * 4.5, radius=0.2, color=MOON_GREY)
        moon_label = Text("Moon", font_size=18, color=WHITE_C).next_to(moon, DOWN, buff=0.25)

        traj = Arc(
            radius=5.5,
            start_angle=PI + 0.35,
            angle=PI - 0.7,
            color=AMBER,
            stroke_width=2.5,
        ).shift(UP * 0.3)

        ship = Dot(radius=0.08, color=CYAN)
        ship.move_to(traj.point_from_proportion(0))

        title = Text("Trans-Lunar Injection", font_size=28, color=GOLD_C)
        title.to_edge(UP, buff=0.3)

        burn_label = Text("TLI Burn: 5 min 49 s", font_size=20, color=AMBER)
        burn_label.to_edge(DOWN, buff=0.4)

        self.play(Write(title), run_time=0.8)
        self.play(FadeIn(earth), FadeIn(earth_label), run_time=0.6)
        self.play(FadeIn(moon), FadeIn(moon_label), run_time=0.6)
        self.play(Create(traj), run_time=1.5)
        self.play(
            MoveAlongPath(ship, traj),
            run_time=2.5,
        )
        self.play(FadeIn(burn_label), run_time=0.5)
        self.wait(0.5)

        self._save("trajectory")

    def _save(self, name):
        pass


class FreeReturnScene(Scene):
    """Free-return trajectory: figure-8 loop around the Moon."""

    def construct(self):
        self.camera.background_color = BG
        _setup()

        earth = Dot(point=LEFT * 5, radius=0.35, color=EARTH_BLUE)
        earth_label = Text("Earth", font_size=16, color=WHITE_C).next_to(earth, DOWN, buff=0.2)

        moon = Dot(point=RIGHT * 2, radius=0.15, color=MOON_GREY)
        moon_label = Text("Moon", font_size=16, color=WHITE_C).next_to(moon, DOWN, buff=0.2)

        outbound = Arc(
            radius=5, start_angle=PI + 0.2, angle=0.8,
            color=AMBER, stroke_width=2,
        ).shift(UP * 0.5 + RIGHT * 0.5)

        loop = Arc(
            radius=1.5, start_angle=-0.5, angle=PI + 1.0,
            color=CYAN, stroke_width=2.5,
        ).move_to(RIGHT * 2 + UP * 0.3)

        inbound = Arc(
            radius=6, start_angle=0.3, angle=-0.8,
            color=AMBER, stroke_width=2,
        ).shift(DOWN * 0.5 + RIGHT * 0.5)

        ship = Dot(radius=0.07, color=WHITE_C)

        title = Text("Free-Return Trajectory", font_size=28, color=GOLD_C)
        title.to_edge(UP, buff=0.3)

        subtitle = Text("Like Apollo 13 — gravity does the work", font_size=18, color=AMBER)
        subtitle.to_edge(DOWN, buff=0.4)

        self.play(Write(title), run_time=0.8)
        self.play(FadeIn(earth), FadeIn(earth_label), run_time=0.5)
        self.play(FadeIn(moon), FadeIn(moon_label), run_time=0.5)
        self.play(Create(outbound), run_time=1.2)
        self.play(Create(loop), run_time=1.5)
        self.play(Create(inbound), run_time=1.2)
        self.play(FadeIn(subtitle), run_time=0.5)
        self.wait(0.5)


class DistanceScene(Scene):
    """Record distance: 252,756 miles from Earth.

    The shot is 17.8 s of narration over this clip, and the assembler fills a short clip by
    `-stream_loop`-ing it, so a 6 s scene restarts three times inside one sentence and the
    diagram visibly wipes itself. The build below runs to the shot length instead: content
    keeps arriving until ~10 s, then the craft drifts aft for the rest.
    """

    def construct(self):
        self.camera.background_color = BG
        _setup()

        # Left, not below: the "everything in Earth orbit" caption hangs under the axis from
        # x -5.0 rightward, which is exactly where a caption under this dot lands.
        earth = Dot(point=LEFT * 5, radius=0.4, color=EARTH_BLUE)
        earth_label = Text("Earth", font_size=18, color=WHITE_C).next_to(earth, LEFT, buff=0.25)

        distance_line = DashedLine(
            LEFT * 4.3, RIGHT * 3.5,
            color=AMBER, stroke_width=2, dash_length=0.15,
        )

        # Clear of the dashed line and of the arrow head at the right end; at buff 0.3 the
        # digits sat on the line and the tail clipped "mi".
        dist_text = Text("252,756 mi", font_size=36, color=GOLD_C)
        dist_text.next_to(distance_line, UP, buff=0.55).shift(LEFT * 1.4)

        record_label = Text("NEW RECORD", font_size=22, color=CYAN)
        record_label.next_to(dist_text, UP, buff=0.25)

        arrow_tip = Arrow(
            RIGHT * 3.2, RIGHT * 4.2,
            color=AMBER, stroke_width=3, buff=0,
        )

        ship = Dot(radius=0.08, color=CYAN).move_to(RIGHT * 3.8)

        # The Moon sits at 238,855 of 252,756 miles, i.e. 94.5% along the line. Marking it
        # is what turns a dot-and-a-line into a scale the viewer can actually read.
        moon_x = -4.3 + 0.945 * 7.8
        moon = Dot(radius=0.13, color=MOON_GREY).move_to(np.array([moon_x, 0, 0]))
        moon_label = Text("Moon", font_size=16, color=MOON_GREY)
        moon_label.next_to(moon, DOWN, buff=0.45)

        # Everything humanity had put in orbit before this crew fits inside the first 9% of
        # this line. That band is the point of the shot, and it fills the dead left third.
        geo_band = Rectangle(width=0.72, height=0.5, color=CYAN, stroke_width=2,
                             fill_opacity=0.14).move_to(np.array([-3.94, 0, 0]))
        geo_label = Text("everything in Earth orbit", font_size=14, color=CYAN)
        geo_label.next_to(geo_band, DOWN, buff=0.55)

        title = Text("Farthest Humans from Earth", font_size=26, color=GOLD_C)
        title.to_edge(UP, buff=0.3)

        # One 18 s shot, one 18 s animation group: the sweep runs under everything for the
        # whole duration, the reveals land in the first nine seconds, and the craft drift
        # carries the back half. The timings sum to TOTAL on purpose — a Succession that runs
        # short leaves a hold at the end, which is exactly what the gate flags.
        TOTAL = 18.0
        sweep, sweep_anim = scan_sweep(TOTAL)
        reveals = Succession(
            Write(title).set_run_time(0.8),
            FadeIn(earth, earth_label).set_run_time(0.5),
            Create(distance_line).set_run_time(1.0),
            AnimationGroup(FadeIn(ship), GrowArrow(arrow_tip)).set_run_time(0.8),
            Write(dist_text).set_run_time(1.0),
            FadeIn(record_label).set_run_time(0.6),
            FadeIn(moon, moon_label).set_run_time(0.7),
            AnimationGroup(DrawBorderThenFill(geo_band),
                           FadeIn(geo_label)).set_run_time(1.0),
            Wait(1.6),
            # MoveAlongPath needs a mobject with its own points and DashedLine stores them in
            # 26 dash children, so the path has to be a plain Line over the same span.
            MoveAlongPath(ship, Line(RIGHT * 3.8, RIGHT * 6.6)).set_run_time(8.0),
            Wait(2.0),
        )
        self.play(AnimationGroup(sweep_anim, reveals, lag_ratio=0))


class ReentryAngleScene(Scene):
    """Direct reentry vs skip reentry comparison."""

    def construct(self):
        self.camera.background_color = BG
        _setup()

        title = Text("Reentry: Direct vs Skip", font_size=26, color=GOLD_C)
        title.to_edge(UP, buff=0.3)

        earth_arc = Arc(
            radius=6, start_angle=-0.35, angle=0.7,
            color=EARTH_BLUE, stroke_width=40, stroke_opacity=0.3,
        ).shift(DOWN * 5.5)

        earth_surface = Arc(
            radius=6, start_angle=-0.35, angle=0.7,
            color=EARTH_BLUE, stroke_width=3,
        ).shift(DOWN * 5.5)

        direct_path = Line(
            LEFT * 4 + UP * 3, RIGHT * 0.5 + DOWN * 2.2,
            color=AMBER, stroke_width=2.5,
        )
        direct_label = Text("Direct", font_size=18, color=AMBER)
        direct_label.next_to(direct_path.get_start(), UP, buff=0.2)

        skip_path_in = Line(
            RIGHT * 4 + UP * 3, RIGHT * 0.5 + DOWN * 0.5,
            color=CYAN, stroke_width=2.5,
        )
        skip_path_out = Line(
            RIGHT * 0.5 + DOWN * 0.5, RIGHT * 3 + DOWN * 2.2,
            color=CYAN, stroke_width=2.5,
        )
        skip_label = Text("Skip", font_size=18, color=CYAN)
        skip_label.next_to(skip_path_in.get_start(), UP, buff=0.2)

        bounce_dot = Dot(radius=0.1, color=WHITE_C).move_to(RIGHT * 0.5 + DOWN * 0.5)
        bounce_text = Text("atmospheric skip", font_size=14, color=LIGHT_GREY)
        bounce_text.next_to(bounce_dot, RIGHT, buff=0.3)

        angle_arc = Arc(
            radius=1.2, start_angle=PI + 0.35, angle=0.55,
            color=YELLOW, stroke_width=2,
        ).shift(RIGHT * 0.5 + DOWN * 2.2)
        angle_label = Text("~6.5°", font_size=24, color=YELLOW)
        angle_label.next_to(angle_arc, LEFT, buff=0.2).shift(DOWN * 0.3)

        # 15 s shot, 15 s animation group. The corridors are drawn in the first six seconds,
        # the two capsule runs are slowed to carry the middle, and the sweep keeps the frame
        # alive for the whole duration — the old build held still for its last four seconds.
        TOTAL = 15.0
        sweep, sweep_anim = scan_sweep(TOTAL)
        cab_direct = Dot(radius=0.09, color=WHITE_C).move_to(direct_path.get_start())
        cab_skip = Dot(radius=0.09, color=WHITE_C).move_to(skip_path_in.get_start())
        reveals = Succession(
            Write(title).set_run_time(0.8),
            # earth_arc was built and never played, so the shot had a hairline where the
            # planet should be. The atmosphere band is what the corridors draw against.
            AnimationGroup(FadeIn(earth_arc),
                           Create(earth_surface)).set_run_time(1.0),
            AnimationGroup(Create(direct_path),
                           FadeIn(direct_label)).set_run_time(1.2),
            AnimationGroup(Create(skip_path_in), Create(skip_path_out),
                           FadeIn(skip_label)).set_run_time(1.4),
            AnimationGroup(FadeIn(bounce_dot),
                           FadeIn(bounce_text)).set_run_time(0.7),
            AnimationGroup(Create(angle_arc),
                           Write(angle_label)).set_run_time(0.9),
            MoveAlongPath(cab_direct, direct_path).set_run_time(3.0),
            MoveAlongPath(cab_skip, skip_path_in).set_run_time(2.0),
            MoveAlongPath(cab_skip, skip_path_out).set_run_time(2.0),
            Wait(2.0),
        )
        self.play(AnimationGroup(sweep_anim, reveals, lag_ratio=0))


def render_all():
    """Render all scenes to the output directory."""
    _setup()
    scenes = [TrajectoryScene, FreeReturnScene, DistanceScene, ReentryAngleScene]
    names = ["trajectory", "free-return", "distance", "reentry-angle"]

    for scene_cls, name in zip(scenes, names):
        print(f"\n=== Rendering {name} ===", flush=True)
        scene = scene_cls()
        scene.render()

        src = Path(config.media_dir) / "videos" / scene_cls.__name__ / "1080p60" / f"{scene_cls.__name__}.mp4"
        if not src.exists():
            src = Path(config.media_dir) / "videos" / scene_cls.__name__ / "1080p60" / f"{scene_cls.__name__}.mp4"
            if not src.exists():
                for candidate in Path(config.media_dir).rglob(f"{scene_cls.__name__}.mp4"):
                    src = candidate
                    break

        dst = OUTPUT_DIR / f"{name}.mp4"
        if src.exists():
            shutil.copy2(str(src), str(dst))
            size_mb = dst.stat().st_size / 1024 / 1024
            print(f"  Copied to {dst} ({size_mb:.1f} MB)", flush=True)
        else:
            print(f"  WARNING: output not found for {name}", flush=True)


if __name__ == "__main__":
    render_all()
