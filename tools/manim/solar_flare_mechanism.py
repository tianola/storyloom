from manim import *
import numpy as np

class SolarFlareMechanism(Scene):
    """Demonstrates Manim's capability for scientific visualization.
    Shows magnetic field lines reconnecting during a solar flare."""

    def construct(self):
        # Title
        title = Text("Solar Flare Mechanism", font_size=48, color=YELLOW)
        title.to_edge(UP)
        self.play(Write(title))
        self.wait(0.5)

        # Create sun surface (partial circle)
        sun_surface = Arc(radius=3, start_angle=PI, angle=PI, color=ORANGE, stroke_width=8)
        sun_surface.shift(DOWN * 2)

        self.play(Create(sun_surface))
        self.wait(0.5)

        # Magnetic field lines (before reconnection)
        field_lines = VGroup()
        for i in range(-2, 3):
            x_pos = i * 0.8
            # Curved field lines emerging from sun
            points = []
            for t in np.linspace(0, PI, 50):
                x = x_pos + 1.5 * np.sin(t)
                y = -2 + 2.5 * np.cos(t) + 0.5 * np.sin(2*t)
                points.append([x, y, 0])
            line = VMobject(color=BLUE)
            line.set_points_smoothly(points)
            field_lines.add(line)

        self.play(*[Create(line) for line in field_lines], run_time=2)
        self.wait(1)

        # Label: Magnetic Field Lines
        label1 = Text("Magnetic Field Lines", font_size=24, color=BLUE)
        label1.next_to(field_lines[2], RIGHT, buff=0.5)
        self.play(Write(label1))
        self.wait(1)

        # Reconnection event (X-point)
        reconnection_point = np.array([0, 0.5, 0])
        x_point = Dot(reconnection_point, color=RED, radius=0.1)
        x_label = Text("Reconnection Point", font_size=20, color=RED)
        x_label.next_to(x_point, UR, buff=0.2)

        self.play(FadeIn(x_point), Write(x_label))
        self.wait(1)

        # Energy release (particles shooting out)
        particles = VGroup()
        for angle in [PI/4, 3*PI/4, 5*PI/4, 7*PI/4]:
            particle = Dot(color=YELLOW, radius=0.05)
            particle.move_to(reconnection_point)
            particles.add(particle)

        self.play(
            *[particle.animate.move_to(
                reconnection_point + 3 * np.array([np.cos(a), np.sin(a), 0])
            ) for particle, a in zip(particles, [PI/4, 3*PI/4, 5*PI/4, 7*PI/4])],
            run_time=1.5
        )

        # Energy label
        energy_label = Text("Energy Release", font_size=24, color=YELLOW)
        energy_label.next_to(particles[0], UR, buff=0.3)
        self.play(Write(energy_label))
        self.wait(1)

        # CME ejection (coronal mass ejection)
        cme = VMobject(color=RED_D, fill_opacity=0.4)
        cme_points = [
            np.array([-1, 1, 0]),
            np.array([0, 2.5, 0]),
            np.array([1, 1, 0]),
            np.array([0, 1.5, 0]),
        ]
        cme.set_points_as_corners(cme_points + [cme_points[0]])
        cme.shift(UP * 2)

        cme_label = Text("CME Ejection", font_size=24, color=RED)
        cme_label.next_to(cme, RIGHT, buff=0.5)

        self.play(FadeIn(cme), Write(cme_label))
        self.wait(1)

        # Final summary
        summary = Text(
            "Solar Flare → CME → Geomagnetic Storm",
            font_size=28,
            color=WHITE
        )
        summary.to_edge(DOWN, buff=0.5)
        self.play(Write(summary))
        self.wait(2)

        # Fade out
        self.play(*[FadeOut(mob) for mob in self.mobjects])
        self.wait(0.5)

if __name__ == "__main__":
    # Render with: manim -pql tools/manim/solar_flare_mechanism.py SolarFlareMechanism
    pass
