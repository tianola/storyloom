"""Every text label's box in the Artemis II diagrams, measured where the scene put it.

Run with the interpreter that has manim installed (the project `.venv`), from the project root:

    .venv/Scripts/python.exe tools/manim/label_probe.py

Prints one `MANIMLABELS_JSON {...}` line: for each scene class in `artemis_manim.py`, every
`Text` mobject the scene would show, with the axis-aligned box it occupies in frame units.
`python/test_manim_labels.py` turns that into the assertions.

`construct()` is really run, with `play` and `wait` replaced by a recorder that only notes
which mobjects each animation would have shown. Nothing is rendered, so the boxes are the
layout the renderer will draw and the probe costs a second instead of a minute.

This exists because a label collision is invisible where it is created. Each `next_to` call is
reasonable on its own; it is the pair that lands on top of itself, and the only place that
shows it is the rendered frame — which nobody inspects pixel by pixel at 96 shots.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from manim import Animation, Scene, Text  # noqa: E402

import artemis_manim  # noqa: E402

SCENES = ["TrajectoryScene", "FreeReturnScene", "DistanceScene", "ReentryAngleScene"]


def texts_shown(arg, seen):
    """Every Text mobject reachable from one positional argument of `play()`.

    An argument is either a mobject or an animation over one; `AnimationGroup` and `Succession`
    keep their children in `.animations` as well as in a combined `.mobject`, so both routes are
    walked and identity-deduplicated through `seen`.
    """
    if isinstance(arg, Animation):
        for child in getattr(arg, "animations", ()):
            yield from texts_shown(child, seen)
        arg = getattr(arg, "mobject", None)
    if arg is None or not hasattr(arg, "get_family"):
        return
    for mobject in arg.get_family():
        if isinstance(mobject, Text) and id(mobject) not in seen:
            seen.add(id(mobject))
            yield mobject


def layout(scene_name):
    """Build a scene's labels by running its own `construct()`; return their boxes."""
    scene = getattr(artemis_manim, scene_name)()
    seen = set()
    labels = []

    def record(*args, **kwargs):
        for arg in args:
            for text in texts_shown(arg, seen):
                corner_lo = text.get_corner((-1, -1, 0))
                corner_hi = text.get_corner((1, 1, 0))
                labels.append({
                    "text": getattr(text, "original_text", None) or str(text),
                    "x0": round(float(corner_lo[0]), 4),
                    "x1": round(float(corner_hi[0]), 4),
                    "y0": round(float(corner_lo[1]), 4),
                    "y1": round(float(corner_hi[1]), 4),
                })

    scene.play = record
    scene.wait = lambda *a, **k: None
    scene.construct()
    return labels


def main():
    from manim import config

    report = {
        "frame": {"width": float(config.frame_width), "height": float(config.frame_height)},
        "scenes": {name: layout(name) for name in SCENES},
    }
    print("MANIMLABELS_JSON " + json.dumps(report), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
