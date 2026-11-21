"""A 16-bit style frame of the chip as a factory floor, at 384x216 and scaled 5x to 1920x1080.

The memory tower stands on the left, a road runs from it to the factory gate, a truck brings a load of
weights, and rows of workers sit at desks of multipliers, most of them asleep. The explorer and the
token watch from beside the road, and a dialogue box carries the line being narrated.

    python tools/pixel/factory.py out.png [--palette gb]
"""
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sprites as sp  # noqa: E402

W, H = 384, 216
SCALE = 5


def c(key):
    return (*sp.rgb(key), 255)


def floor(img, rng):
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, H), fill=c("D"))
    for y in range(0, H, 16):
        for x in range(0, W, 16):
            d.line((x, y, x + 15, y), fill=c("d"))
            d.line((x, y, x, y + 15), fill=c("d"))
            d.point((x + 1, y + 1), fill=c("e"))
            if rng.random() < 0.18:
                vx, vy = x + rng.randint(4, 11), y + rng.randint(4, 11)
                d.rectangle((vx, vy, vx + 1, vy + 1), fill=c("f"))
                d.point((vx, vy), fill=c("F"))
            if rng.random() < 0.25:
                ty = y + rng.choice((5, 10))
                d.line((x + 2, ty, x + 13, ty), fill=c("e"))


def wall(img):
    """The metal layers above: copper lines stacked with dark gaps, vias between them."""
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, 30), fill=c("V"))
    for k, y in enumerate((3, 9, 15, 21)):
        d.rectangle((0, y, W, y + 3), fill=c("m"))
        d.line((0, y, W, y), fill=c("M"))
        for x in range((k * 7) % 24, W, 24):
            d.rectangle((x, y + 4, x + 1, y + 5), fill=c("w"))
    d.rectangle((0, 27, W, 30), fill=c("k"))
    d.line((0, 31, W, 31), fill=c("K"))


def tower(img, x0, y0, layers=8):
    """The memory stack in 3/4 view: a lit top face, then the DRAM dies one above the other."""
    d = ImageDraw.Draw(img)
    w = 60
    d.polygon([(x0 + 6, y0), (x0 + w + 6, y0), (x0 + w, y0 + 8), (x0, y0 + 8)], fill=c("w"), outline=c("K"))
    y = y0 + 8
    for k in range(layers):
        d.rectangle((x0, y, x0 + w, y + 11), fill=c("k"), outline=c("K"))
        d.line((x0 + 1, y + 1, x0 + w - 1, y + 1), fill=c("w"))
        d.polygon([(x0 + w, y), (x0 + w + 6, y - 8), (x0 + w + 6, y + 3), (x0 + w, y + 11)], fill=c("K"))
        for bx in range(x0 + 4, x0 + w - 2, 6):
            d.point((bx, y + 9), fill=c("F"))
        y += 12
    d.rectangle((x0 - 3, y, x0 + w + 3, y + 7), fill=c("e"), outline=c("K"))
    return y + 7


def label(img, text, xy, fg="W", bg="V", font=None):
    d = ImageDraw.Draw(img)
    d.fontmode = "1"
    box = d.textbbox((0, 0), text, font=font)
    x, y = xy
    d.rectangle((x - 2, y - 1, x + box[2] + 2, y + box[3] + 1), fill=c(bg), outline=c("w"))
    d.text((x, y), text, fill=c(fg), font=font)


def road(img, x0, x1, y):
    d = ImageDraw.Draw(img)
    d.rectangle((x0, y, x1, y + 14), fill=c("k"))
    d.line((x0, y, x1, y), fill=c("c"))
    d.line((x0, y + 14, x1, y + 14), fill=c("c"))
    for x in range(x0 + 2, x1, 10):
        d.line((x, y + 7, x + 4, y + 7), fill=c("C"))


def gate(img, x, y):
    d = ImageDraw.Draw(img)
    for px in (x, x + 22):
        d.rectangle((px, y - 30, px + 3, y + 14), fill=c("e"), outline=c("K"))
    d.rectangle((x - 2, y - 34, x + 27, y - 30), fill=c("C"), outline=c("c"))


def desk(img, x, y, lit=False):
    """A desk in 3/4 view: a top of multiplier cells, then the dark front."""
    d = ImageDraw.Draw(img)
    d.rectangle((x, y, x + 25, y + 6), fill=c("e"), outline=c("K"))
    for i in range(6):
        for j in range(2):
            d.rectangle((x + 2 + i * 4, y + 2 + j * 2, x + 4 + i * 4, y + 2 + j * 2), fill=c("P" if lit else "p"))
    d.rectangle((x, y + 7, x + 25, y + 15), fill=c("k"), outline=c("K"))
    d.line((x + 1, y + 8, x + 24, y + 8), fill=c("e"))


def clock(img, x, y):
    d = ImageDraw.Draw(img)
    d.ellipse((x, y, x + 14, y + 14), fill=c("W"), outline=c("K"))
    d.line((x + 7, y + 7, x + 7, y + 3), fill=c("K"))
    d.line((x + 7, y + 7, x + 10, y + 9), fill=c("R"))


def dialogue(img, who, lines, font):
    d = ImageDraw.Draw(img)
    d.fontmode = "1"
    x0, y0, x1, y1 = 6, 160, W - 7, H - 5
    d.rectangle((x0, y0, x1, y1), fill=c("V"), outline=c("W"))
    d.rectangle((x0 + 2, y0 + 2, x1 - 2, y1 - 2), outline=c("w"))
    face = sp.sprite(sp.grid(who)[:14])
    d.rectangle((x0 + 6, y0 + 6, x0 + 6 + face.width + 3, y0 + 6 + face.height + 3), fill=c("k"), outline=c("w"))
    img.alpha_composite(face, (x0 + 8, y0 + 8))
    for k, line in enumerate(lines):
        d.text((x0 + 36, y0 + 8 + k * 12), line, fill=c("W"), font=font)
    d.polygon([(x1 - 12, y1 - 9), (x1 - 6, y1 - 9), (x1 - 9, y1 - 6)], fill=c("W"))


def put(img, rows, x, y):
    s = sp.sprite(rows)
    img.alpha_composite(s, (x, y))
    return s


def frame(gb=False):
    rng = random.Random(4)
    img = Image.new("RGBA", (W, H))
    floor(img, rng)
    wall(img)
    font = ImageFont.load_default_imagefont()
    base = tower(img, 12, 44)
    label(img, "MEMORY", (22, 34), font=font)
    road(img, 76, 204, 132)
    gate(img, 204, 132)
    put(img, sp.TRUCK, 112, 127)
    clock(img, 300, 8)
    # the factory: four desks across, three rows deep; back rows first
    poses = ["asleep", "bored", "asleep", "asleep",
             "asleep", "asleep", "sleepy", "asleep",
             "bored", "asleep", "asleep", "asleep"]
    k = 0
    for row, dy in enumerate((48, 84, 120)):
        for col, dx in enumerate((256, 288, 320, 352)):
            pose = poses[k]
            x = dx - 13
            if pose == "bored":
                put(img, sp.WORKER_BORED, x + 5, dy - 18)
            elif pose != "asleep":
                put(img, sp.worker("sleepy"), x + 5, dy - 18)
            desk(img, x, dy)
            if pose == "asleep":
                put(img, sp.WORKER_ASLEEP, x + 5, dy - 5)
                put(img, sp.ZZZ, x + 18, dy - 16)
            k += 1
    put(img, sp.MUG, 246 + 13, 116)
    # the explorer and the token, watching the road
    put(img, sp.explorer(), 132, 92)
    put(img, sp.token("cat"), 156, 106)
    dialogue(img, sp.explorer(), ["Each worker finishes its sums in 4 µs.",
                                  "Then it naps for 600 µs, until the truck",
                                  "brings the next load from memory."], font)
    out = img.convert("RGB")
    if gb:
        greens = [(15, 56, 15), (48, 98, 48), (139, 172, 15), (155, 188, 15)]
        px = out.load()
        for y in range(H):
            for x in range(W):
                r, g, b = px[x, y]
                lum = 0.3 * r + 0.59 * g + 0.11 * b
                px[x, y] = greens[min(3, int(lum / 64))]
    return out.resize((W * SCALE, H * SCALE), Image.NEAREST)


if __name__ == "__main__":
    out = Path(sys.argv[1])
    frame(gb="--palette" in sys.argv and "gb" in sys.argv).save(out)
    print(out)
