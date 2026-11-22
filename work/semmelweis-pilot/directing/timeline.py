import json, os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "tools", "fonts"))
d = json.load(open(os.path.join(HERE, "cut.proposed.json"), encoding="utf-8"))
DUR = d["clock"]["duration"]
W, H = 3600, 1020
LM, RM = 170, 40
PX = (W - LM - RM) / DUR
X = lambda t: LM + t * PX


def F(sz, bold=False):
    p = os.path.join(FONTS, "Inter-Bold.ttf" if bold else "Inter-Regular.ttf")
    if not os.path.exists(p):
        p = os.path.join(FONTS, "Inter-Bold.ttf")
    return ImageFont.truetype(p, sz)


img = Image.new("RGB", (W, H), "white")
g = ImageDraw.Draw(img)
INK = (25, 25, 30)
MODE = {"F": ((242, 169, 59), INK), "V": ((59, 125, 216), "white"),
        "A": ((139, 107, 74), "white"), "G": ((63, 166, 107), "white")}
MODE_NAME = {"F": "F  Fern / story", "V": "V  Veritasium / investigation",
             "A": "A  archive", "G": "G  graphic"}


def tw(t, f):
    return g.textlength(t, font=f)


def ctext(cx, y, t, f, fill):
    g.text((cx - tw(t, f) / 2, y), t, font=f, fill=fill)


g.text((LM, 14), "Semmelweis pilot v6 — proposed cut (projected clock)", font=F(38, True), fill=INK)
g.text((W - RM - 260, 24), "duration %.2f s" % DUR, font=F(22), fill=INK)

R_LINES = (250, 325)
R_SHOTS = (345, 465)
R_OV = (485, 555)
R_LOOP = (575, 690)
R_HOST = (710, 770)
BOTTOM = R_HOST[1] + 10


def rowlabel(r, t):
    g.text((12, (r[0] + r[1]) / 2 - 13), t, font=F(24, True), fill=INK)


for r, t in [(R_LINES, "Lines"), (R_SHOTS, "Shots"), (R_OV, "Overlays"), (R_LOOP, "Loops"), (R_HOST, "Host")]:
    g.rectangle([LM, r[0] - 4, W - RM, r[1] + 4], fill=(246, 246, 248))
    rowlabel(r, t)

AX_Y = 215
g.line([LM, AX_Y, W - RM, AX_Y], fill=INK, width=2)
t = 0
while t <= DUR:
    x = X(t)
    g.line([x, R_LINES[0] - 4, x, BOTTOM], fill=(225, 225, 230), width=1)
    g.line([x, AX_Y, x, AX_Y + 12], fill=INK, width=2)
    ctext(x, AX_Y + 14, "%d:%02d" % (int(t) // 60, int(t) % 60), F(20), INK)
    t += 10
for tt in range(0, int(DUR) + 1, 5):
    if tt % 10:
        g.line([X(tt), AX_Y, X(tt), AX_Y + 6], fill=INK, width=1)


def hatch(box, col, bg):
    x0, y0, x1, y1 = box
    g.rectangle(box, fill=bg)
    wd, ht = int(x1 - x0) + 1, int(y1 - y0) + 1
    tile = Image.new("RGBA", (wd, ht), (0, 0, 0, 0))
    td = ImageDraw.Draw(tile)
    for k in range(-ht, wd, 12):
        td.line([k, ht, k + ht, 0], fill=col, width=4)
    img.paste(tile, (int(x0), int(y0)), tile)


for ln in d["lines"]:
    x0, x1 = X(ln["start"]), X(ln["end"])
    box = (x0 + 1, R_LINES[0], x1 - 1, R_LINES[1])
    if ln["voiced"]:
        g.rectangle(box, fill=(210, 222, 240), outline=(90, 110, 150))
    else:
        hatch(box, (230, 120, 30, 255), (255, 232, 200))
        g.rectangle(box, outline=(200, 90, 10), width=3)
    f = F(20, True)
    if x1 - x0 >= tw(ln["id"], f) + 6:
        g.text(((x0 + x1) / 2 - tw(ln["id"], f) / 2, R_LINES[0] + 6), ln["id"], font=f, fill=INK)
    if not ln["voiced"]:
        fn = F(18, True)
        bw = tw("NEW", fn) + 10
        cx = (x0 + x1) / 2
        g.rounded_rectangle([cx - bw / 2, R_LINES[0] + 34, cx + bw / 2, R_LINES[0] + 62], 5, fill=(200, 70, 0))
        g.text((cx - bw / 2 + 5, R_LINES[0] + 36), "NEW", font=fn, fill="white")

shots = d["shots"]
for s in shots:
    x0, x1 = X(s["start"]), X(s["end"])
    black = s["source"].get("name") == "black"
    fill, tc = ((0, 0, 0), "white") if black else MODE[s["mode"]]
    g.rectangle([x0, R_SHOTS[0], x1, R_SHOTS[1]], fill=fill)
    g.line([x1, R_SHOTS[0], x1, R_SHOTS[1]], fill="white", width=2)
    w = x1 - x0
    if w >= 28:
        f = F(20, True)
        if tw(s["id"], f) <= w - 2:
            g.text(((x0 + x1) / 2 - tw(s["id"], f) / 2, R_SHOTS[0] + 6), s["id"], font=f, fill=tc)
        elif tw(s["id"], F(18, True)) <= w - 2:
            g.text(((x0 + x1) / 2 - tw(s["id"], F(18, True)) / 2, R_SHOTS[0] + 6), s["id"], font=F(18, True), fill=tc)
        nm = s["source"].get("view") or s["source"].get("name") or ""
        if black:
            nm = ""
        fn = F(18)
        if nm and tw(nm, fn) <= w - 4:
            g.text(((x0 + x1) / 2 - tw(nm, fn) / 2, R_SHOTS[0] + 34), nm, font=fn, fill=tc)
        elif nm:
            tmp = Image.new("RGBA", (int(tw(nm, fn)) + 4, 26), (0, 0, 0, 0))
            ImageDraw.Draw(tmp).text((2, 0), nm, font=fn, fill=tc)
            rot = tmp.rotate(90, expand=True)
            if rot.size[0] <= w and rot.size[1] <= (R_SHOTS[1] - R_SHOTS[0] - 36):
                img.paste(rot, (int((x0 + x1) / 2 - rot.size[0] / 2), R_SHOTS[0] + 32), rot)
        sn = s["source"].get("name", "")
        if sn and nm != sn and not black and tw(sn, fn) <= w - 4:
            g.text(((x0 + x1) / 2 - tw(sn, fn) / 2, R_SHOTS[0] + 90), sn, font=fn, fill=tc)
g.rectangle([LM, R_SHOTS[0], W - RM, R_SHOTS[1]], outline=INK, width=1)

fo = F(18)
for s in shots:
    for o in s["overlays"]:
        x0, x1 = X(o["start"]), X(o["end"])
        g.rectangle([x0, R_OV[0] + 6, max(x1, x0 + 4), R_OV[0] + 30], fill=(150, 70, 170))
        g.text((x0, R_OV[0] + 34), o["graphic"], font=fo, fill=INK)

LOOPC = {"0": (230, 120, 110), "A": (240, 180, 80), "B": (140, 200, 110), "C": (110, 190, 210),
         "K": (170, 140, 220), "open": (200, 200, 120)}
runs = []
for s in shots:
    lp = s.get("loop")
    if lp is None:
        continue
    if runs and runs[-1]["loop"] == lp and abs(runs[-1]["end"] - s["start"]) < 1e-3:
        runs[-1]["end"] = s["end"]
        runs[-1]["shots"].append(s)
    else:
        runs.append({"loop": lp, "start": s["start"], "end": s["end"], "shots": [s]})
BAND = (R_LOOP[0], R_LOOP[0] + 40)
fl = F(20, True)
fr = F(18)
for r in runs:
    x0, x1 = X(r["start"]), X(r["end"])
    g.rectangle([x0, BAND[0], x1, BAND[1]], fill=LOOPC[r["loop"]], outline="white", width=2)
    lab = "loop " + r["loop"]
    if tw(lab, fl) > x1 - x0 - 6:
        lab = r["loop"]
    g.text((x0 + 6, BAND[0] + 7), lab, font=fl, fill=INK)
    prev = None
    lvl = 0
    for s in r["shots"]:
        rl = s.get("role")
        if rl and rl != prev:
            x = X(s["start"])
            y = BAND[1] + 4 + lvl * 24
            g.line([x, BAND[1], x, y + 4], fill=INK, width=2)
            g.text((x + 3, y), rl, font=fr, fill=INK)
            lvl = (lvl + 1) % 3
            prev = rl

for s in shots:
    h = s.get("host")
    if not h:
        continue
    cx = (X(s["start"]) + X(s["end"])) / 2
    cy = (R_HOST[0] + R_HOST[1]) / 2
    g.rectangle([X(s["start"]), cy - 4, X(s["end"]), cy + 4], fill=(120, 60, 60))
    g.polygon([(cx, cy - 15), (cx + 15, cy), (cx, cy + 15), (cx - 15, cy)], fill=(190, 40, 60), outline="white")
    ctext(cx, cy + 17, h["id"], F(22, True), INK)

tally = next(s for s in shots if any(o["graphic"] == "tally" for o in s["overlays"]))
# the same numbers validate_proposal.py checks: tallies fully built; ratios heard at the
# conservative 2.36 words/s estimate (the end of 'nine' and of 'six' in the new u003)
_ov = next(o for o in tally["overlays"] if o["graphic"] == "tally")
_built = _ov["start"] + max(a + d for a, d in _ov["spec"]["build"].values())
_w = d["words_new"]["u003"]["conservative"]
_nine = next(w for w in _w if w["w"].startswith("nine"))["e"]
_six = next(w for w in _w if w["w"].startswith("six"))["e"]
mk = [(_built, f"contrast on screen {_built:.1f}s", 0),
      (_nine, f"1 in 9 heard {_nine:.1f}s (conservative)", 1),
      (_six, f"1 in 36 heard {_six:.1f}s (conservative)", 2)]
fm = F(20, True)
for t, lab, lv in mk:
    x = X(t)
    y = 82 + lv * 30
    for yy in range(y + 24, BOTTOM, 14):
        g.line([x, yy, x, min(yy + 7, BOTTOM)], fill=(200, 30, 30), width=2)
    g.text((x + 5, y), lab, font=fm, fill=(200, 30, 30))

hs = max(shots, key=lambda s: s["end"] - s["start"])
x0, x1 = X(hs["start"]), X(hs["end"])
by = 175
g.line([x0, by, x1, by], fill=INK, width=3)
g.line([x0, by, x0, by + 14], fill=INK, width=3)
g.line([x1, by, x1, by + 14], fill=INK, width=3)
ctext((x0 + x1) / 2, by - 34, "held shot %.1f s (%s)" % (hs["end"] - hs["start"], hs["id"]), F(24, True), INK)

ly = 805
g.text((LM, ly), "Mode", font=F(22, True), fill=INK)
x = LM + 90
for m in "FVAG":
    g.rectangle([x, ly + 2, x + 34, ly + 32], fill=MODE[m][0])
    g.text((x + 44, ly + 3), MODE_NAME[m], font=F(22), fill=INK)
    x += 44 + tw(MODE_NAME[m], F(22)) + 40
g.rectangle([x, ly + 2, x + 34, ly + 32], fill=(0, 0, 0))
g.text((x + 44, ly + 3), "black", font=F(22), fill=INK)
x += 160
hatch((x, ly + 2, x + 34, ly + 32), (230, 120, 30, 255), (255, 232, 200))
g.text((x + 44, ly + 3), "NEW line (not yet voiced)", font=F(22), fill=INK)
x += 330
g.rectangle([x, ly + 2, x + 34, ly + 32], fill=(210, 222, 240), outline=(90, 110, 150))
g.text((x + 44, ly + 3), "voiced line", font=F(22), fill=INK)
g.text((LM, ly + 50), "Red dashed = hook markers (the numbers validate_proposal.py checks). Loops: 0, A, B, C, K, open; small labels = role changes (belief / experiment / result / next ...).",
       font=F(20), fill=INK)
img = img.crop((0, 0, W, 900))
img.save(os.path.join(HERE, "timeline.png"))
print("held", hs["id"], hs["end"] - hs["start"])
