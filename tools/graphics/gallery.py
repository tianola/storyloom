"""A contact sheet of every primitive, mid-build and final, for judging the look at a glance.

    python tools/graphics/gallery.py --out sheet.png

Overlays are composited over a neutral mid-grey so their plates and text are judged the way they
will be seen: over footage, not over their own transparency.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw  # noqa: E402

from tools.graphics import PRESETS, PRIMITIVES, get  # noqa: E402
from tools.graphics.common import load_font  # noqa: E402
from tools.graphics.tokens import load_tokens  # noqa: E402

CLINICS = {"left": {"label": "First Clinic", "marks": 11, "per": 100},
           "right": {"label": "Second Clinic", "marks": 3, "per": 100},
           "build": {"left": [0.15, 0.7], "right": [0.5, 0.35]},
           "source": "1846 · Semmelweis 1861", "type": {"label": 0.06, "number": 0.1}}


def sample_image(path, size=(1200, 900)):
    """A stand-in archive still: period-toned bands and shapes, so the mat has something to frame."""
    img = Image.new("RGB", size, (150, 136, 112))
    d = ImageDraw.Draw(img)
    for i in range(6):
        d.rectangle([0, i * size[1] // 6, size[0], (i + 1) * size[1] // 6],
                    fill=(150 - i * 9, 136 - i * 8, 112 - i * 7))
    d.rectangle([size[0] * 0.15, size[1] * 0.3, size[0] * 0.45, size[1] * 0.9], fill=(88, 78, 64))
    d.ellipse([size[0] * 0.55, size[1] * 0.2, size[0] * 0.85, size[1] * 0.6], fill=(196, 182, 150))
    img.save(path)
    return str(path)


def fixtures(image_path):
    """name -> (spec, t_mid, t_final). t is chosen to land mid-build for the animated parts."""
    labelled = {"cycle": [["MON", "first"], ["TUE", "second"], ["WED", "first"]], "step": 0.8}
    out = {
        "big_number": ({"value": "1846", "label": "the year the deaths began", "build": [0, 0.6],
                        "source": "Semmelweis 1861"}, 0.3, 2.0),
        "ratio_compare": (PRESETS["ratio-1846"][1], 0.7, 2.0),
        "bar_compare": ({"bars": [{"label": "First Clinic", "value": 11.4},
                                  {"label": "Second Clinic", "value": 2.7}], "unit": "%",
                         "build": [0.0, 1.0], "source": "1846"}, 0.6, 2.0),
        "tally": (CLINICS, 0.8, 2.0),
        "figure_grid": ({"total": 36, "highlight": 4, "label": "4 of every 36", "build": [0.0, 1.2]}, 0.7, 2.0),
        "timeline": ({"start": 1844, "end": 1850,
                      "events": [{"date": 1846, "label": "Semmelweis starts", "build": [0.2, 0.3]},
                                 {"date": 1847, "label": "Kolletschka dies", "build": [0.8, 0.3]},
                                 {"date": 1848, "label": "Handwashing", "build": [1.4, 0.3]}],
                      "now": {"from": 1844, "to": 1849, "build": [0.2, 2.0]}}, 1.0, 2.6),
        "map_plan": (PRESETS["ward-plan-routes"][1], 1.6, 6.0),
        "board": ({"cards": [{"id": "a", "title": "Fever", "x": 0.2, "y": 0.3, "build": [0.0, 0.3]},
                             {"id": "b", "title": "Dirty hands", "x": 0.7, "y": 0.35, "build": [0.5, 0.3]},
                             {"id": "c", "title": "Miasma", "x": 0.45, "y": 0.75, "build": [0.9, 0.3],
                              "cross_out": [1.4, 0.5]}],
                   "strings": [{"from": "a", "to": "b", "build": [0.9, 0.4]}]}, 1.6, 2.4),
        "board_card": ({"title": "POSITION", "pin": True, "corner": "top-right"}, 0.25, 1.0),
        "split": ({"n": 2, "labels": ["First Clinic", "Second Clinic"]}, 0.5, 1.0),
        "archive_mat": ({"image": image_path, "credit": "Wellcome Collection / Public domain", "seconds": 6.0},
                        1.5, 6.0),
        "source_card": ({"credit": "Public domain / Wikimedia Commons, scan of an 1850s print"}, 0.5, 1.0),
        "label": ({"text": "Vienna General Hospital"}, 0.15, 1.0),
        "callout": ({"text": "The aisle", "target": [0.62, 0.55], "pos": [0.3, 0.18]}, 0.25, 1.0),
        "lower_third": ({"title": "Ignaz Semmelweis", "subtitle": "Assistant, First Clinic"}, 0.2, 1.0),
        "underline": ({"box": [0.3, 0.4, 0.7, 0.5]}, 0.2, 1.0),
        "circle": ({"center": [0.5, 0.5], "rx": 0.14, "ry": 0.22}, 0.3, 1.0),
        "date_stamp": ({"text": "March 1847", "at": 0.2}, 0.3, 1.0),
        "day_labels": (labelled, 1.0, 2.4),
    }
    return out


def contact_sheet(out_path, tile=(480, 270), columns=4, render_canvas=(1920, 1080)):
    tokens = load_tokens()
    tmp = tempfile.mkdtemp(prefix="graphics-gallery-")
    image = sample_image(Path(tmp) / "still.png")
    fx = fixtures(image)
    missing = sorted(set(PRIMITIVES) - set(fx))
    if missing:
        raise SystemExit(f"gallery has no fixture for {missing}")
    cells = []
    for name, (spec, t_mid, t_end) in fx.items():
        prim = get(name)
        for tag, t in (("mid", t_mid), ("final", t_end)):
            frame = prim.frame_at(spec, t, canvas=render_canvas, tokens=tokens)
            if prim.OVERLAY:
                back = Image.new("RGBA", frame.size, (96, 104, 112, 255))
                back.alpha_composite(frame)
                frame = back
            cells.append((f"{name} · {tag}", frame.convert("RGB").resize(tile, Image.LANCZOS)))
    rows = -(-len(cells) // columns)
    cap = 26
    sheet = Image.new("RGB", (columns * tile[0], rows * (tile[1] + cap)), (24, 24, 28))
    d = ImageDraw.Draw(sheet)
    font = load_font(tokens["fonts_abs"]["regular"], 16)
    for i, (title, im) in enumerate(cells):
        r, c = divmod(i, columns)
        x, y = c * tile[0], r * (tile[1] + cap)
        sheet.paste(im, (x, y + cap))
        d.text((x + 6, y + 4), title, fill=(230, 230, 230), font=font)
    sheet.save(out_path)
    return out_path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="contact sheet PNG to write")
    ap.add_argument("--tile-width", type=int, default=480)
    args = ap.parse_args(argv)
    tw = args.tile_width
    path = contact_sheet(args.out, tile=(tw, round(tw * 9 / 16)))
    print(path)


if __name__ == "__main__":
    main()
