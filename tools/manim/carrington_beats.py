from manim import *
import numpy as np

# House style constants
BG_COLOR = "#060810"
AMBER = "#ffb347"
CYAN = "#5fd4ff"
SUN_ORANGE = "#ff8c00"
SUN_YELLOW = "#ffd700"
EARTH_BLUE = "#4488cc"
FIELD_BLUE = "#4488ff"
FIELD_RED = "#ff4444"
WIRE_GOLD = "#daa520"
DANGER_RED = "#ff3333"

config.background_color = BG_COLOR

config.pixel_width = 1920
config.pixel_height = 1080
config.frame_width = 16
config.frame_height = 9


class Beat1_SolarFlare(Scene):
    """Beat 1: Solar Flare — magnetic reconnection on the Sun's surface.
    Shows magnetic field lines twisting, reconnecting, and releasing energy."""

    def construct(self):
        self.camera.background_color = BG_COLOR

        # Title
        title = Text("SOLAR FLARE", font_size=56, color=AMBER, weight=BOLD)
        title.to_edge(UP, buff=0.4)
        subtitle = Text("Magnetic Reconnection on the Sun's Surface",
                       font_size=28, color=WHITE)
        subtitle.next_to(title, DOWN, buff=0.2)
        self.play(Write(title), FadeIn(subtitle, shift=UP*0.2))
        self.wait(1)

        # Sun surface (large arc at bottom)
        sun_arc = Arc(radius=5, start_angle=PI+0.3, angle=PI-0.6,
                      color=SUN_ORANGE, stroke_width=6)
        sun_arc.shift(DOWN * 4.5)
        sun_glow = Arc(radius=5.1, start_angle=PI+0.3, angle=PI-0.6,
                       color=SUN_YELLOW, stroke_width=2, stroke_opacity=0.4)
        sun_glow.shift(DOWN * 4.5)
        sun_label = Text("Sun's Surface (Photosphere)", font_size=20, color=SUN_ORANGE)
        sun_label.next_to(sun_arc, DOWN, buff=0.3)

        self.play(Create(sun_arc), Create(sun_glow))
        self.play(FadeIn(sun_label, shift=UP*0.2))
        self.wait(1)

        # Pre-flare: twisted magnetic field lines
        field_lines = VGroup()
        colors = [FIELD_BLUE, CYAN, FIELD_BLUE, CYAN, FIELD_BLUE]
        x_positions = [-3, -1.5, 0, 1.5, 3]

        for i, (x, color) in enumerate(zip(x_positions, colors)):
            points = []
            for t in np.linspace(0, PI, 60):
                px = x + 1.2 * np.sin(t) * (1 + 0.3 * np.sin(3*t + i))
                py = -4.5 + 4.5 * np.cos(t) * 0.8 + 0.5 * np.sin(2*t)
                points.append([px, py, 0])
            line = VMobject(color=color, stroke_width=3)
            line.set_points_smoothly(points)
            field_lines.add(line)

        field_label = Text("Twisted Magnetic Field Lines",
                          font_size=22, color=CYAN)
        field_label.to_edge(LEFT, buff=0.5).shift(UP*2)

        self.play(*[Create(l) for l in field_lines], run_time=2)
        self.play(Write(field_label))
        self.wait(1.5)

        # Reconnection: lines converge to X-point
        x_point = Dot(UP * 0.5, color=AMBER, radius=0.12)
        x_label = Text("Reconnection Point", font_size=22, color=AMBER)
        x_label.next_to(x_point, RIGHT, buff=0.3)

        # Animate field lines snapping to reconnection configuration
        new_field_lines = VGroup()
        for i, (x, color) in enumerate(zip(x_positions, colors)):
            points = []
            for t in np.linspace(0, PI, 60):
                if t < PI/2:
                    px = x + 0.5 * np.sin(2*t)
                    py = -4.5 + 5 * np.cos(t) * 0.5 + 0.5
                else:
                    px = x - 0.5 * np.sin(2*(t-PI/2))
                    py = -4.5 + 5 * np.cos(t) * 0.5 + 0.5
                points.append([px, py, 0])
            line = VMobject(color=color, stroke_width=3)
            line.set_points_smoothly(points)
            new_field_lines.add(line)

        self.play(
            *[Transform(old, new) for old, new in zip(field_lines, new_field_lines)],
            FadeIn(x_point, scale=2),
            Write(x_label),
            run_time=2
        )
        self.wait(1)

        # Energy release: flash + particles
        flash = Circle(radius=0.5, color=AMBER, fill_opacity=1, stroke_width=0)
        flash.move_to(x_point)
        flash_label = Text("ENERGY RELEASE", font_size=28, color=AMBER, weight=BOLD)
        flash_label.next_to(x_point, UP, buff=0.8)

        particles = VGroup()
        for angle in np.linspace(0, 2*PI, 12, endpoint=False):
            p = Dot(color=SUN_YELLOW, radius=0.06)
            p.move_to(x_point)
            particles.add(p)

        self.play(
            GrowFromCenter(flash),
            flash.animate.scale(4).set_opacity(0),
            *[p.animate.move_to(x_point.get_center() + 3.5 * np.array([np.cos(a), np.sin(a), 0]))
              for p, a in zip(particles, np.linspace(0, 2*PI, 12, endpoint=False))],
            Write(flash_label),
            run_time=1.5
        )
        self.wait(1)

        # Temperature label
        temp = Text("10-20 Million Kelvin", font_size=22, color=FIELD_RED)
        temp.next_to(flash_label, DOWN, buff=0.3)
        self.play(FadeIn(temp, shift=UP*0.2))
        self.wait(1)

        # Summary arrow
        summary = Text("Solar Flare → X-rays + Energetic Particles",
                      font_size=24, color=WHITE)
        summary.to_edge(DOWN, buff=0.5)
        self.play(Write(summary))
        self.wait(2)

        self.play(*[FadeOut(m) for m in self.mobjects])
        self.wait(0.5)


class Beat2_CMETravel(Scene):
    """Beat 2: CME Travel — coronal mass ejection traveling from Sun to Earth.
    Shows the 17-hour journey across 150 million km."""

    def construct(self):
        self.camera.background_color = BG_COLOR

        # Title
        title = Text("CME TRAVEL", font_size=56, color=AMBER, weight=BOLD)
        title.to_edge(UP, buff=0.4)
        subtitle = Text("Coronal Mass Ejection: Sun → Earth in ~17 Hours",
                       font_size=28, color=WHITE)
        subtitle.next_to(title, DOWN, buff=0.2)
        self.play(Write(title), FadeIn(subtitle, shift=UP*0.2))
        self.wait(1)

        # Sun (left side)
        sun = Circle(radius=1.2, color=SUN_ORANGE, fill_opacity=0.9,
                    stroke_color=SUN_YELLOW, stroke_width=3)
        sun.shift(LEFT * 6)
        sun_label = Text("Sun", font_size=22, color=SUN_ORANGE)
        sun_label.next_to(sun, DOWN, buff=0.3)

        self.play(FadeIn(sun, scale=0.5), FadeIn(sun_label))
        self.wait(0.5)

        # Earth (right side)
        earth = Circle(radius=0.5, color=EARTH_BLUE, fill_opacity=0.8,
                      stroke_color=CYAN, stroke_width=2)
        earth.shift(RIGHT * 6)
        earth_label = Text("Earth", font_size=22, color=CYAN)
        earth_label.next_to(earth, DOWN, buff=0.3)

        self.play(FadeIn(earth, scale=0.5), FadeIn(earth_label))
        self.wait(0.5)

        # Distance line
        dist_line = DashedLine(sun.get_right(), earth.get_left(),
                               color=WHITE, stroke_width=1, stroke_opacity=0.3)
        dist_label = Text("150 million km (1 AU)", font_size=20, color=WHITE)
        dist_label.next_to(dist_line, UP, buff=0.2)
        self.play(Create(dist_line), Write(dist_label))
        self.wait(1)

        # CME ejection from sun
        cme_cloud = VGroup()
        for i in range(8):
            blob = Circle(radius=0.3 + 0.1*np.random.random(),
                         color=FIELD_RED, fill_opacity=0.3,
                         stroke_color=AMBER, stroke_width=1)
            blob.move_to(sun.get_right() + RIGHT*0.5 + UP*(i-4)*0.3)
            cme_cloud.add(blob)

        cme_label = Text("CME\n(Billion tons\nof plasma)", font_size=18,
                        color=AMBER)
        cme_label.next_to(cme_cloud, UP, buff=0.3)

        self.play(FadeIn(cme_cloud, shift=RIGHT*0.5), Write(cme_label))
        self.wait(1)

        # Animate CME traveling to Earth
        speed_label = Text("Speed: ~1,000 km/s\n(20x faster than solar wind)",
                          font_size=20, color=CYAN)
        speed_label.to_edge(DOWN, buff=1)

        self.play(
            cme_cloud.animate.shift(RIGHT * 10),
            cme_label.animate.shift(RIGHT * 10),
            Write(speed_label),
            run_time=3
        )
        self.wait(1)

        # Timeline (manual, no LaTeX)
        timeline_base = Line(LEFT*5, RIGHT*5, color=WHITE, stroke_width=2)
        timeline_base.to_edge(DOWN, buff=0.8)
        timeline_base.shift(DOWN*0.3)
        tick_marks = VGroup()
        time_labels = VGroup()
        for h in range(0, 18, 3):
            x_pos = -5 + (h / 17) * 10
            tick = Line(UP*0.1, DOWN*0.1, color=WHITE, stroke_width=2).shift(RIGHT*x_pos + timeline_base.get_center())
            tick_marks.add(tick)
            label = Text(str(h), font_size=16, color=WHITE).next_to(tick, DOWN, buff=0.1)
            time_labels.add(label)
        timeline_label = Text("Hours after flare", font_size=18, color=WHITE)
        timeline_label.next_to(timeline_base, DOWN, buff=0.5)

        time_dot = Dot(color=AMBER, radius=0.1)
        time_dot.move_to(timeline_base.get_left())

        self.play(
            FadeOut(speed_label),
            Create(timeline_base), Create(tick_marks),
            FadeIn(timeline_label), *[FadeIn(l) for l in time_labels],
            FadeIn(time_dot, scale=2)
        )
        self.play(time_dot.animate.move_to(timeline_base.get_right()), run_time=2)
        self.wait(1)

        # Impact
        impact_text = Text("CME IMPACTS EARTH'S MAGNETOSPHERE",
                          font_size=28, color=DANGER_RED, weight=BOLD)
        impact_text.move_to(earth).shift(UP*1.5)

        self.play(Write(impact_text),
                  earth.animate.set_stroke(color=DANGER_RED, width=4))
        self.wait(2)

        self.play(*[FadeOut(m) for m in self.mobjects])
        self.wait(0.5)


class Beat3_MagnetosphereCompression(Scene):
    """Beat 3: Magnetosphere Compression — Earth's magnetic shield being
    compressed by the CME's magnetic field."""

    def construct(self):
        self.camera.background_color = BG_COLOR

        # Title
        title = Text("MAGNETOSPHERE COMPRESSION", font_size=48, color=AMBER, weight=BOLD)
        title.to_edge(UP, buff=0.4)
        subtitle = Text("Earth's Magnetic Shield Under Attack",
                       font_size=26, color=WHITE)
        subtitle.next_to(title, DOWN, buff=0.2)
        self.play(Write(title), FadeIn(subtitle, shift=UP*0.2))
        self.wait(1)

        # Earth (center)
        earth = Circle(radius=0.8, color=EARTH_BLUE, fill_opacity=0.9,
                      stroke_color=CYAN, stroke_width=2)
        earth_label = Text("Earth", font_size=20, color=CYAN)
        earth_label.move_to(earth)

        self.play(FadeIn(earth, scale=0.5), Write(earth_label))
        self.wait(0.5)

        # Normal magnetosphere (before CME)
        mag_lines_before = VGroup()
        for angle in np.linspace(-PI*0.8, PI*0.8, 7):
            points = []
            r_base = 2.5
            for t in np.linspace(0, 2*PI, 80):
                r = r_base * (1 + 0.3 * np.cos(t))
                px = r * np.cos(t) * 0.8 + r_base * 0.2 * np.cos(angle)
                py = r * np.sin(t) * 0.6
                points.append([px, py, 0])
            line = VMobject(color=FIELD_BLUE, stroke_width=2, stroke_opacity=0.6)
            line.set_points_smoothly(points)
            line.shift(RIGHT * np.sin(angle) * 0.5)
            mag_lines_before.add(line)

        mag_label = Text("Normal Magnetosphere", font_size=22, color=FIELD_BLUE)
        mag_label.to_edge(LEFT, buff=0.5).shift(UP*1)
        mag_label2 = Text("(Extends ~60,000 km)", font_size=18, color=WHITE)
        mag_label2.next_to(mag_label, DOWN, buff=0.2)

        self.play(*[Create(l) for l in mag_lines_before], run_time=2)
        self.play(Write(mag_label), Write(mag_label2))
        self.wait(1.5)

        # CME arriving from left
        cme_arrow = Arrow(LEFT*7, LEFT*4, color=FIELD_RED, stroke_width=6,
                         buff=0, max_tip_length_to_length_ratio=0.15)
        cme_text = Text("CME\nMagnetic\nField", font_size=20, color=FIELD_RED)
        cme_text.next_to(cme_arrow, LEFT, buff=0.3)

        cme_pressure = Text("Dynamic Pressure:\n~100 nPa", font_size=20,
                           color=AMBER)
        cme_pressure.next_to(cme_text, DOWN, buff=0.5)

        self.play(GrowArrow(cme_arrow), Write(cme_text), Write(cme_pressure))
        self.wait(1)

        # Compress magnetosphere (day side)
        mag_lines_after = VGroup()
        for angle in np.linspace(-PI*0.8, PI*0.8, 7):
            points = []
            for t in np.linspace(0, 2*PI, 80):
                # Asymmetric: compressed on left (day side), stretched on right
                compression = 0.5 if np.cos(t) < 0 else 1.3
                r_base = 2.5 * compression
                r = r_base * (1 + 0.2 * np.cos(t))
                px = r * np.cos(t) * 0.8
                py = r * np.sin(t) * 0.6
                points.append([px, py, 0])
            line = VMobject(color=CYAN, stroke_width=2, stroke_opacity=0.7)
            line.set_points_smoothly(points)
            mag_lines_after.add(line)

        compress_label = Text("COMPRESSED", font_size=26, color=DANGER_RED, weight=BOLD)
        compress_label.shift(LEFT*3 + UP*2)
        compress_label2 = Text("(Day side: ~30,000 km)", font_size=18, color=WHITE)
        compress_label2.next_to(compress_label, DOWN, buff=0.2)

        stretch_label = Text("STRETCHED", font_size=22, color=AMBER)
        stretch_label.shift(RIGHT*3 + UP*2)
        stretch_label2 = Text("(Magnetotail: ~1,000,000 km)", font_size=16, color=WHITE)
        stretch_label2.next_to(stretch_label, DOWN, buff=0.2)

        self.play(
            *[Transform(old, new) for old, new in zip(mag_lines_before, mag_lines_after)],
            Write(compress_label), Write(compress_label2),
            Write(stretch_label), Write(stretch_label2),
            run_time=2
        )
        self.wait(1.5)

        # Reconnection label at boundary
        recon_dot = Dot(LEFT*2.2, color=AMBER, radius=0.1)
        recon_label = Text("Magnetic Reconnection\nat Magnetopause",
                          font_size=20, color=AMBER)
        recon_label.next_to(recon_dot, UR, buff=0.3)

        self.play(FadeIn(recon_dot, scale=2), Write(recon_label))
        self.wait(1)

        # Consequence
        consequence = Text("Result: Energy injected into magnetosphere\n→ Geomagnetic Storm",
                          font_size=24, color=WHITE)
        consequence.to_edge(DOWN, buff=0.6)
        self.play(Write(consequence))
        self.wait(2)

        self.play(*[FadeOut(m) for m in self.mobjects])
        self.wait(0.5)


class Beat4_GroundInducedCurrent(Scene):
    """Beat 4: Ground-Induced Currents (GIC) — changing magnetic field
    induces electric currents in the ground and long conductors."""

    def construct(self):
        self.camera.background_color = BG_COLOR

        # Title
        title = Text("GROUND-INDUCED CURRENTS (GIC)", font_size=48, color=AMBER, weight=BOLD)
        title.to_edge(UP, buff=0.4)
        subtitle = Text("Faraday's Law: Changing B-field → Electric Current",
                       font_size=26, color=WHITE)
        subtitle.next_to(title, DOWN, buff=0.2)
        self.play(Write(title), FadeIn(subtitle, shift=UP*0.2))
        self.wait(1)

        # Cross-section of Earth
        ground_line = Line(LEFT*7, RIGHT*7, color="#8B4513", stroke_width=4)
        ground_line.shift(DOWN*1)
        ground_label = Text("Earth's Surface", font_size=20, color="#CD853F")
        ground_label.next_to(ground_line, RIGHT, buff=0.3).shift(DOWN*0.3)

        ground_fill = Rectangle(width=14, height=4, fill_color="#3D2B1F",
                               fill_opacity=0.5, stroke_width=0)
        ground_fill.next_to(ground_line, DOWN, buff=0)

        self.play(Create(ground_line), FadeIn(ground_fill), Write(ground_label))
        self.wait(0.5)

        # Changing magnetic field (wavy arrows from above)
        b_field_arrows = VGroup()
        for x in np.linspace(-5, 5, 6):
            arrow = Arrow(UP*3, UP*0.5, color=FIELD_BLUE, stroke_width=3,
                         buff=0, max_tip_length_to_length_ratio=0.15)
            arrow.shift(RIGHT * x)
            b_field_arrows.add(arrow)

        b_label = Text("Changing Magnetic Field (dB/dt)", font_size=22, color=FIELD_BLUE)
        b_label.shift(UP*3.5)

        self.play(*[GrowArrow(a) for a in b_field_arrows], Write(b_label), run_time=2)
        self.wait(1)

        # Induced electric field (horizontal arrows below ground)
        e_field_arrows = VGroup()
        for y in np.linspace(-1.5, -3, 3):
            arrow = Arrow(LEFT*5, RIGHT*5, color=CYAN, stroke_width=2,
                         buff=0, max_tip_length_to_length_ratio=0.08)
            arrow.shift(DOWN * abs(y) + UP*1)
            e_field_arrows.add(arrow)

        e_label = Text("Induced Electric Field (E)", font_size=22, color=CYAN)
        e_label.shift(DOWN*2.5)

        self.play(*[GrowArrow(a) for a in e_field_arrows], Write(e_label), run_time=2)
        self.wait(1)

        # Faraday's law equation (text, no LaTeX)
        equation = Text("∇ × E = −∂B/∂t", font_size=36, color=AMBER)
        equation.to_edge(RIGHT, buff=1).shift(UP*1)
        eq_label = Text("Faraday's Law", font_size=18, color=WHITE)
        eq_label.next_to(equation, DOWN, buff=0.2)

        self.play(Write(equation), FadeIn(eq_label))
        self.wait(1.5)

        # Current flowing through ground conductor
        current_path = VMobject(color=WIRE_GOLD, stroke_width=4)
        current_points = [
            np.array([-5, -1, 0]),
            np.array([-3, -1.5, 0]),
            np.array([0, -1.2, 0]),
            np.array([3, -1.5, 0]),
            np.array([5, -1, 0]),
        ]
        current_path.set_points_smoothly(current_points)

        current_label = Text("GIC flows through\nground & conductors",
                            font_size=20, color=WIRE_GOLD)
        current_label.next_to(current_path, DOWN, buff=0.5)

        # Animated current dots
        current_dots = VGroup()
        for i in range(8):
            dot = Dot(radius=0.08, color=WIRE_GOLD)
            dot.move_to(current_points[0])
            current_dots.add(dot)

        self.play(Create(current_path), Write(current_label),
                  FadeIn(current_dots))

        # Animate current flow
        self.play(
            *[dot.animate.move_to(current_points[-1]) for dot in current_dots],
            run_time=2
        )
        self.wait(1)

        # Key numbers
        numbers = VGroup(
            Text("Typical GIC: 10-100 A", font_size=20, color=WHITE),
            Text("Ground resistivity: 10-10,000 Ω·m", font_size=20, color=WHITE),
            Text("Affected area: 1000+ km scale", font_size=20, color=WHITE),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.2)
        numbers.to_edge(LEFT, buff=0.5).shift(DOWN*2)
        numbers_label = Text("Key Parameters", font_size=22, color=AMBER)
        numbers_label.next_to(numbers, UP, buff=0.3)

        self.play(Write(numbers_label), *[FadeIn(n, shift=RIGHT*0.3) for n in numbers])
        self.wait(2)

        self.play(*[FadeOut(m) for m in self.mobjects])
        self.wait(0.5)


class Beat5_TelegraphCircuit(Scene):
    """Beat 5: Telegraph Circuit — how GIC affected 1859 telegraph systems.
    Shows the circuit, the induced current, and the effects."""

    def construct(self):
        self.camera.background_color = BG_COLOR

        # Title
        title = Text("TELEGRAPH CIRCUIT — 1859", font_size=48, color=AMBER, weight=BOLD)
        title.to_edge(UP, buff=0.4)
        subtitle = Text("How GIC Disrupted the World's Communication Network",
                       font_size=26, color=WHITE)
        subtitle.next_to(title, DOWN, buff=0.2)
        self.play(Write(title), FadeIn(subtitle, shift=UP*0.2))
        self.wait(1)

        # Telegraph wire (top)
        wire_top = Line(LEFT*6, RIGHT*6, color=WIRE_GOLD, stroke_width=4)
        wire_top.shift(UP*1.5)
        wire_label = Text("Telegraph Wire", font_size=20, color=WIRE_GOLD)
        wire_label.next_to(wire_top, UP, buff=0.2)

        # Ground return (bottom)
        wire_bottom = Line(LEFT*6, RIGHT*6, color="#8B4513", stroke_width=3)
        wire_bottom.shift(DOWN*1.5)
        ground_label = Text("Ground Return (through Earth)", font_size=18, color="#CD853F")
        ground_label.next_to(wire_bottom, DOWN, buff=0.2)

        self.play(Create(wire_top), Create(wire_bottom),
                  Write(wire_label), Write(ground_label))
        self.wait(1)

        # Battery (left side)
        battery = VGroup(
            Line(UP*0.4, DOWN*0.4, stroke_width=4, color=WHITE),
            Line(UP*0.2, DOWN*0.2, stroke_width=2, color=WHITE).shift(RIGHT*0.15),
        )
        battery.shift(LEFT*5)
        bat_label = Text("Battery", font_size=18, color=WHITE)
        bat_label.next_to(battery, DOWN, buff=0.3)

        # Connect battery to wires
        bat_connect_top = Line(battery.get_top(), wire_top.get_left(),
                               color=WIRE_GOLD, stroke_width=2)
        bat_connect_bottom = Line(battery.get_bottom(), wire_bottom.get_left(),
                                  color=WIRE_GOLD, stroke_width=2)

        self.play(FadeIn(battery), Write(bat_label),
                  Create(bat_connect_top), Create(bat_connect_bottom))
        self.wait(0.5)

        # Telegraph key (middle)
        key_base = Rectangle(width=0.8, height=0.2, color=WHITE, stroke_width=2)
        key_arm = Line(ORIGIN, RIGHT*0.8, color=WHITE, stroke_width=3)
        key_arm.shift(UP*0.15)
        key_dot = Dot(key_arm.get_right(), color=AMBER, radius=0.08)
        key_group = VGroup(key_base, key_arm, key_dot)
        key_group.shift(LEFT*1 + DOWN*0.0)
        key_label = Text("Telegraph Key", font_size=18, color=WHITE)
        key_label.next_to(key_group, DOWN, buff=0.3)

        # Connect key
        key_top = Line(key_group.get_top(), wire_top.get_left() + RIGHT*4.5,
                      color=WIRE_GOLD, stroke_width=2)

        self.play(FadeIn(key_group), Write(key_label), Create(key_top))
        self.wait(0.5)

        # Receiver/sounder (right side)
        receiver = VGroup(
            Circle(radius=0.3, color=CYAN, fill_opacity=0.3, stroke_width=2),
            Text("R", font_size=20, color=CYAN).move_to(ORIGIN),
        )
        receiver.shift(RIGHT*5)
        recv_label = Text("Receiver", font_size=18, color=CYAN)
        recv_label.next_to(receiver, DOWN, buff=0.3)

        # Connect receiver
        recv_top = Line(receiver.get_top(), wire_top.get_right(),
                       color=WIRE_GOLD, stroke_width=2)
        recv_bottom = Line(receiver.get_bottom() + DOWN*0.3, wire_bottom.get_right(),
                          color=WIRE_GOLD, stroke_width=2)

        self.play(FadeIn(receiver), Write(recv_label),
                  Create(recv_top), Create(recv_bottom))
        self.wait(1)

        # GIC injection (arrows from above)
        gic_arrows = VGroup()
        for x in [-3, 0, 3]:
            arrow = Arrow(UP*3.5, UP*2, color=FIELD_RED, stroke_width=3,
                         buff=0, max_tip_length_to_length_ratio=0.15)
            arrow.shift(RIGHT * x)
            gic_arrows.add(arrow)

        gic_label = Text("GIC Induced\nby Geomagnetic Storm", font_size=22,
                        color=FIELD_RED)
        gic_label.shift(UP*4)

        self.play(*[GrowArrow(a) for a in gic_arrows], Write(gic_label), run_time=2)
        self.wait(1)

        # Effects list
        effects = VGroup(
            Text("• Sparks from equipment", font_size=22, color=AMBER),
            Text("• Telegraph paper caught fire", font_size=22, color=AMBER),
            Text("• Operators received electric shocks", font_size=22, color=AMBER),
            Text("• Lines unusable for 8+ hours", font_size=22, color=DANGER_RED),
            Text("• Some operated WITHOUT battery power!", font_size=22, color=CYAN),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.15)
        effects.to_edge(DOWN, buff=0.4).shift(LEFT*2)
        effects_label = Text("Documented Effects:", font_size=24, color=WHITE, weight=BOLD)
        effects_label.next_to(effects, UP, buff=0.3)

        self.play(Write(effects_label),
                  *[FadeIn(e, shift=RIGHT*0.3) for e in effects],
                  run_time=2)
        self.wait(2)

        self.play(*[FadeOut(m) for m in self.mobjects])
        self.wait(0.5)


class Beat6_ModernTransformer(Scene):
    """Beat 6: Modern Transformer Response — how GIC affects modern
    power grid infrastructure, especially large power transformers."""

    def construct(self):
        self.camera.background_color = BG_COLOR

        # Title
        title = Text("MODERN TRANSFORMER RESPONSE", font_size=48, color=AMBER, weight=BOLD)
        title.to_edge(UP, buff=0.4)
        subtitle = Text("GIC Threat to Today's Power Grid",
                       font_size=26, color=WHITE)
        subtitle.next_to(title, DOWN, buff=0.2)
        self.play(Write(title), FadeIn(subtitle, shift=UP*0.2))
        self.wait(1)

        # Transformer diagram
        # Core (rectangular)
        core = Rectangle(width=2, height=3, color="#666666", fill_opacity=0.4,
                        stroke_width=3)
        core.shift(LEFT*2)
        core_label = Text("Iron Core", font_size=18, color=WHITE)
        core_label.move_to(core)

        # Primary winding (left coil)
        primary = VGroup()
        for i in range(5):
            arc = Arc(radius=0.4, start_angle=PI*0.5, angle=PI,
                     color=WIRE_GOLD, stroke_width=3)
            arc.shift(LEFT*3.2 + UP*(1-i*0.5))
            primary.add(arc)
        prim_label = Text("Primary\nWinding", font_size=18, color=WIRE_GOLD)
        prim_label.next_to(primary, LEFT, buff=0.3)

        # Secondary winding (right coil)
        secondary = VGroup()
        for i in range(5):
            arc = Arc(radius=0.4, start_angle=PI*0.5, angle=PI,
                     color=CYAN, stroke_width=3)
            arc.shift(LEFT*0.8 + UP*(1-i*0.5))
            secondary.add(arc)
        sec_label = Text("Secondary\nWinding", font_size=18, color=CYAN)
        sec_label.next_to(secondary, RIGHT, buff=0.3)

        self.play(FadeIn(core), Write(core_label),
                  FadeIn(primary), Write(prim_label),
                  FadeIn(secondary), Write(sec_label))
        self.wait(1)

        # Power lines (long conductors on ground)
        ground = Line(LEFT*7, RIGHT*7, color="#8B4513", stroke_width=3)
        ground.shift(DOWN*3)

        power_line = Line(LEFT*7, RIGHT*7, color=WIRE_GOLD, stroke_width=2)
        power_line.shift(DOWN*2)
        pl_label = Text("Long Power Line (100+ km)", font_size=18, color=WIRE_GOLD)
        pl_label.next_to(power_line, UP, buff=0.1).shift(LEFT*2)

        # Ground connection
        gnd_conn = Line(power_line.get_right() + RIGHT*0.5, ground.get_right() + RIGHT*0.5,
                       color=WIRE_GOLD, stroke_width=2)

        self.play(Create(ground), Create(power_line), Write(pl_label),
                  Create(gnd_conn))
        self.wait(1)

        # GIC flowing in
        gic_arrow = Arrow(LEFT*5, RIGHT*5, color=FIELD_RED, stroke_width=4,
                         buff=0).shift(DOWN*2)
        gic_label = Text("GIC (Direct Current)", font_size=20, color=FIELD_RED)
        gic_label.next_to(gic_arrow, DOWN, buff=0.2)

        self.play(GrowArrow(gic_arrow), Write(gic_label))
        self.wait(1)

        # Core saturation effect
        sat_text = Text("CORE SATURATION", font_size=28, color=DANGER_RED, weight=BOLD)
        sat_text.shift(RIGHT*4 + UP*2)

        # Half-cycle saturation waveform
        axes = Axes(x_range=[0, 4, 1], y_range=[-2, 2, 1],
                   x_length=4, y_length=2,
                   axis_config={"color": WHITE, "stroke_width": 2, "include_numbers": False},
                   tips=False)
        axes.shift(RIGHT*4 + DOWN*0.5)

        # Normal flux (sine wave)
        normal = axes.plot(lambda x: 1.5 * np.sin(x * PI), color=CYAN, stroke_width=2)
        normal_label = Text("Normal Φ", font_size=16, color=CYAN)
        normal_label.next_to(axes, UR, buff=0.1)

        # Saturated flux (clipped sine)
        saturated = axes.plot(
            lambda x: 1.5 * np.sin(x * PI) if abs(1.5 * np.sin(x * PI)) < 1.0
            else np.sign(1.5 * np.sin(x * PI)) * 1.0,
            color=DANGER_RED, stroke_width=2
        )
        sat_label = Text("Saturated Φ", font_size=16, color=DANGER_RED)
        sat_label.next_to(normal_label, DOWN, buff=0.1)

        self.play(Write(sat_text), Create(axes), Create(normal), Create(saturated),
                  Write(normal_label), Write(sat_label))
        self.wait(1.5)

        # Consequences
        consequences = VGroup(
            Text("• Half-cycle saturation → harmonic distortion",
                font_size=20, color=AMBER),
            Text("• Reactive power consumption spikes",
                font_size=20, color=AMBER),
            Text("• Hot-spot heating (150-200°C in minutes)",
                font_size=20, color=DANGER_RED),
            Text("• Transformer damage: months to replace",
                font_size=20, color=DANGER_RED),
            Text("• Cascading blackout risk",
                font_size=22, color=DANGER_RED, weight=BOLD),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.12)
        consequences.to_edge(DOWN, buff=0.3)

        cons_label = Text("Consequences:", font_size=22, color=WHITE, weight=BOLD)
        cons_label.next_to(consequences, UP, buff=0.2)

        self.play(Write(cons_label),
                  *[FadeIn(c, shift=RIGHT*0.3) for c in consequences],
                  run_time=2)
        self.wait(2)

        self.play(*[FadeOut(m) for m in self.mobjects])
        self.wait(0.5)
