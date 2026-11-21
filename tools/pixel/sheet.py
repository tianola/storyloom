"""Contact sheet of the cast, for review before any of it goes into a 3D set.

    python tools/pixel/sheet.py --out work/X/qc/sprites.png [--scale 6]

Row 1: every character standing, neutral. Then, per character, its poses; then the expressions and
mouths of the busts (the close-ups where they talk). Nearest-neighbour scaling, on a mid grey so
the outline reads.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import people  # noqa: E402
from sprites import sprite  # noqa: E402

from PIL import Image, ImageDraw  # noqa: E402

BG = (72, 70, 80, 255)


def strip(cells, scale, gap=4):
    imgs = [sprite(c).resize((sprite(c).width * scale, sprite(c).height * scale), Image.NEAREST) for c in cells]
    w = sum(i.width for i in imgs) + gap * scale * (len(imgs) + 1)
    h = max(i.height for i in imgs) + 2 * gap * scale
    out = Image.new("RGBA", (w, h), BG)
    x = gap * scale
    for i in imgs:
        out.alpha_composite(i, (x, h - gap * scale - i.height))
        x += i.width + gap * scale
    return out


def build(scale=6):
    rows = []
    keys = list(people.CHARACTERS)
    rows.append(("cast", strip([people.cell(k) for k in keys], scale)))
    for k in keys:
        rows.append((f"{k}: poses", strip([people.cell(k, pose=p) for p in people.poses_of(k)], scale)))
    for k in keys:
        rows.append((f"{k}: faces", strip([people.cell(k, expression=x) for x in people.EXPRESSIONS] +
                                          [people.cell(k, mouth=m) for m in people.MOUTHS[1:]] +
                                          [people.cell(k, eyes="blink")], scale)))
    for k in [k for k, c in people.CHARACTERS.items() if c["bust"]]:
        rows.append((f"{k}: bust", strip([people.cell(k, pose=p, size="bust") for p in people.BUST_POSES] +
                                         [people.cell(k, expression=x, size="bust") for x in people.EXPRESSIONS[1:]], scale)))
        rows.append((f"{k}: talking", strip([people.cell(k, mouth=m, size="bust") for m in people.MOUTHS] +
                                            [people.cell(k, eyes=e, size="bust") for e in people.EYES[1:]], scale)))
    label_h = 18
    w = max(img.width for _, img in rows)
    h = sum(img.height + label_h for _, img in rows)
    sheet = Image.new("RGBA", (w, h), BG)
    draw = ImageDraw.Draw(sheet)
    y = 0
    for label, img in rows:
        draw.text((8, y + 3), label, fill=(230, 228, 220, 255))
        sheet.alpha_composite(img, (0, y + label_h))
        y += img.height + label_h
    return sheet


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--scale", type=int, default=6)
    args = ap.parse_args(argv)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    build(args.scale).convert("RGB").save(args.out)
    print(args.out)


if __name__ == "__main__":
    main()
