"""Pixel-art people who act and talk: one drawer, many characters.

`sprites.py` holds single hand-drawn grids. A character who speaks needs the same body with
different mouths, eyes, brows and arms, so here a figure is *drawn by code* from a costume
description (skin, hair, hat, coat, legs) into the same kind of palette-key grid, in layers:

    body (legs, coat, arms for the pose) -> head -> hair -> hat -> brows (expression) -> eyes -> mouth

Two sizes are drawn from one costume:
  figure  16 x 30 px  the whole person, for the world (walking, greeting, standing in a crowd)
  bust    30 x 34 px  head and shoulders, for the close-ups where the narrator or a character talks;
                      a figure's mouth is 4 px wide and reads only when the figure is large
  bed     32 x 16 px  one person lying in a bed (the `patient`, her only size; `kolletschka` has it too),
                      poses lie / lie-turn / lie-side / sick
  hands   48 x 32 px  a pair of bare hands and dark cuffs (semmelweis, doctor, student), poses open / reach /
                      hold; no face, so mouth, eyes and expression are ignored and every one maps to the same cell

`cell(key, pose, expression, mouth, eyes, size)` returns one grid; `CHARACTERS` is the registry
(costume plus which poses each one has); `atlas_layout` says where every cell sits in the atlas
image the Blender builder makes from it (columns: mouth x eyes, rows: pose x expression).

Palette keys come from sprites.PALETTE plus the extras below; '.' is clear.
"""
from sprites import PALETTE, grid

PALETTE.update({
    "A": "#e9b48f", "a": "#b97a58",        # fair skin, shade
    "Q": "#c98c63", "q": "#8e5a3c",        # darker skin, shade
    "h": "#3a2a22", "j": "#6b4a32",        # dark brown hair, mid brown hair
    "x": "#b9b4ae", "X": "#e4e0d8",        # grey hair, white hair
    "U": "#1c2030", "u": "#2e3548",        # black coat, its light edge
    "Z": "#5b4a3c", "z": "#3e3229",        # brown coat
    "I": "#4c5a6e", "i": "#323d4d",        # grey-blue coat (guard, lamplighter)
    "E": "#7a2e3a", "v": "#53202a",        # maroon dress
    "J": "#2f4e78", "l": "#203654",        # dark blue dress (midwife)
    "1": "#efe9dc", "2": "#cfc6b4",        # linen white, its shade (shirts, aprons, gowns)
    "3": "#d9b34a",                        # brass (buttons, lamp)
    "4": "#e7a87e",                        # lips
    "9": "#6a3a8a", "8": "#47285f",        # purple stole, its shade
    "7": "#b02a2e", "6": "#7a1c22",        # red cassock (altar boy), its shade
    "5": "#aab8a2", "0": "#7f8f7c",        # sick skin: pale grey-green, its shade
    "%": "#d6f0f6",                        # a bead of sweat
})

MOUTHS = ["rest", "closed", "half", "open", "wide"]
EYES = ["open", "blink", "narrow"]
EXPRESSIONS = ["neutral", "worried", "shocked", "angry", "sad", "smile"]
POSES = ["stand", "talk", "point", "walk1", "walk2", "walk3", "walk4", "tip-hat", "hands-head",
         "plead", "wash", "drink", "kneel", "give-birth", "look-hands"]
LOW_POSES = ("kneel", "give-birth")      # the body is lowered onto the ground: no standing legs, a shorter figure
BUST_POSES = ["stand", "talk", "point"]
CLERIC_POSES = ["stand", "talk", "walk1", "walk2", "walk3", "walk4"]
BED_POSES = ["lie", "lie-turn", "lie-side", "sick"]
HANDS_POSES = ["open", "reach", "hold"]

FIG_W, FIG_H = 16, 30
BUST_W, BUST_H = 30, 34
BED_W, BED_H = 32, 16      # a patient in a hospital bed seen from the side: wider than tall, a billboard over a bed
HANDS_W, HANDS_H = 48, 32  # a close-up of a doctor's bare hands and coat cuffs: no face, one cell per pose


class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = [["."] * w for _ in range(h)]

    def put(self, x, y, ch):
        if ch and ch != "." and 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = ch

    def rect(self, x0, y0, x1, y1, ch):
        """Fill x0..x1, y0..y1 inclusive."""
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.put(x, y, ch)

    def clear(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = "."

    def stamp(self, x0, y0, rows):
        for dy, row in enumerate(rows):
            for dx, ch in enumerate(row):
                self.put(x0 + dx, y0 + dy, ch)

    def rows(self):
        return ["".join(r) for r in self.px]


# ---------------------------------------------------------------------------
# costumes
# ---------------------------------------------------------------------------

# skin, shade; hair style and colour; hat; coat and its edge; shirt; legs (trousers or a skirt)
CHARACTERS = {
    "explorer": dict(skin="S", shade="s", hair="short", hair_c="j", hat="pith", coat="jacket", coat_c="G", edge="g",
                     shirt="R", legs="trousers", legs_c="N", shoes="n", role="the guide, a fictional narrator"),
    "semmelweis": dict(skin="A", shade="a", hair="whiskers", hair_c="h", hat=None, coat="frock", coat_c="U", edge="u",
                       shirt="1", cravat="k", legs="trousers", legs_c="U", shoes="K", bust=True, extra=["hands"],
                       role="Ignaz Semmelweis, assistant at the First Clinic from 1846"),
    "kolletschka": dict(skin="A", shade="a", hair="balding", hair_c="x", hat=None, coat="frock", coat_c="Z", edge="z",
                        shirt="1", cravat="k", legs="trousers", legs_c="z", shoes="K", extra=["bed"],
                        role="Jakob Kolletschka, professor of forensic medicine, his friend"),
    "student": dict(skin="S", shade="s", hair="short", hair_c="j", hat=None, coat="frock", coat_c="d", edge="e",
                    shirt="1", cravat="k", legs="trousers", legs_c="d", shoes="K", extra=["hands"],
                    role="a medical student"),
    "doctor": dict(skin="A", shade="a", hair="short", hair_c="x", hat="top", hat_c="U", coat="frock", coat_c="U",
                   edge="u", shirt="1", cravat="k", legs="trousers", legs_c="U", shoes="K", beard=True,
                   extra=["hands"], role="a senior doctor"),
    "midwife": dict(skin="Q", shade="q", hair="bun", hair_c="h", hat="cap", hat_c="1", coat="dress", coat_c="J",
                    edge="l", shirt="1", apron="1", legs="skirt", legs_c="J", shoes="K", role="a midwife of the Second Clinic"),
    "mother": dict(skin="A", shade="a", hair="long", hair_c="j", hat=None, coat="gown", coat_c="1", edge="2",
                   shirt="1", shawl="E", legs="skirt", legs_c="1", shoes="a", role="a mother about to give birth"),
    "townsman": dict(skin="Q", shade="q", hair="short", hair_c="h", hat="cap", hat_c="z", coat="jacket", coat_c="Z",
                     edge="z", shirt="1", legs="trousers", legs_c="i", shoes="K", role="a man of the street"),
    "townswoman": dict(skin="S", shade="s", hair="bun", hair_c="j", hat="bonnet", hat_c="F", coat="dress", coat_c="E",
                       edge="v", shirt="1", shawl="J", legs="skirt", legs_c="E", shoes="K", role="a woman of the street"),
    "baker": dict(skin="S", shade="s", hair="short", hair_c="x", hat="cap", hat_c="1", coat="jacket", coat_c="1",
                  edge="2", shirt="1", apron="1", legs="trousers", legs_c="z", shoes="K", role="the baker on the corner"),
    "lamplighter": dict(skin="A", shade="a", hair="short", hair_c="x", hat="cap", hat_c="i", coat="jacket", coat_c="I",
                        edge="i", shirt="1", legs="trousers", legs_c="i", shoes="K", pole=True,
                        role="the lamplighter on his round"),
    "guard": dict(skin="A", shade="a", hair="short", hair_c="h", hat="cap", hat_c="i", coat="jacket", coat_c="I",
                  edge="i", shirt="I", buttons="3", legs="trousers", legs_c="i", shoes="K", beard=True,
                  role="an asylum guard, 1865"),
    # clergy of 1846: a cassock to the shoes, a white surplice to the knee, a stole round the neck
    "priest": dict(skin="A", shade="a", hair="short", hair_c="x", hat=None, coat="cassock", coat_c="U", edge="u",
                   shirt="1", legs="skirt", legs_c="U", shoes="K", surplice=True, stole="9", carry=True,
                   poses=CLERIC_POSES, role="a Catholic priest carrying the viaticum to a dying patient"),
    "acolyte": dict(skin="S", shade="s", hair="short", hair_c="j", hat=None, coat="cassock", coat_c="7", edge="6",
                    shirt="1", legs="skirt", legs_c="7", shoes="K", surplice=True, surplice_end=21, bell=True, child=True,
                    poses=CLERIC_POSES + ["ring"], role="the altar boy who rings the bell before the priest"),
    "patient": dict(skin="A", shade="a", hair="long", hair_c="j", hat=None, coat="gown", coat_c="X", edge="x",
                    shirt="1", legs="skirt", legs_c="X", shoes="a", bed=True, poses=BED_POSES,
                    role="a woman lying in a ward bed, a billboard for the beds"),
}
# the same man dressed for the street (1840s: nobody respectable went out bareheaded)
CHARACTERS["semmelweis-out"] = {**CHARACTERS["semmelweis"], "hat": "top", "hat_c": "U", "bust": False,
                                "role": "Semmelweis outdoors"}
for _k, _c in CHARACTERS.items():
    _c.setdefault("poses", POSES)
    _c.setdefault("bust", _k == "explorer")
    _c.setdefault("bed", False)
    _c.setdefault("extra", [])


# ---------------------------------------------------------------------------
# the whole figure, 16 x 30
# ---------------------------------------------------------------------------
# head x 3..12, y 4..13; eyes at y 8 (x 5-6 and 9-10), brows y 7, mouth x 6..9, y 11..12;
# shoulders y 15; torso y 15..23; legs y 24..29 (shoes on y 29)

def _legs(c, pose, k):
    lc, sh = k["legs_c"], k["shoes"]
    lift_l = pose == "walk1"
    lift_r = pose == "walk3"
    if k["legs"] == "skirt":
        # a skirt flares from the waist; the feet show under the hem and step in turn
        for y in range(21, 29):
            spread = (y - 21) // 3
            c.rect(3 - spread, y, 12 + spread, y, lc)
        c.rect(1, 28, 14, 28, k.get("edge", lc))
        c.rect(5, 29 - lift_l, 6, 29 - lift_l, sh)
        c.rect(9, 29 - lift_r, 10, 29 - lift_r, sh)
        return
    c.rect(4, 24, 7, 28 - lift_l, lc)
    c.rect(8, 24, 11, 28 - lift_r, lc)
    c.clear(7, 26), c.clear(8, 26), c.clear(7, 27), c.clear(8, 27), c.clear(7, 28), c.clear(8, 28)
    c.rect(3, 29 - lift_l, 6, 29 - lift_l, sh)
    c.rect(9, 29 - lift_r, 12, 29 - lift_r, sh)


def _arm(c, k, side, pose):
    """One arm in the pose: side -1 is the figure's right (viewer's left), +1 its left."""
    cc, edge, skin = k["coat_c"], k["edge"], k["skin"]
    x = 1 if side < 0 else 13             # the sleeve column pair x, x+1
    hand = lambda hx, hy: c.rect(hx, hy, hx + 1, hy, skin)
    raised = (pose in ("point", "tip-hat", "talk") and side > 0) or pose == "hands-head"
    if pose == "ring" and side > 0:
        # the bell held up at the head, the sleeve falling back
        c.rect(x, 10, x + 1, 16, cc)
        c.rect(x, 8, x + 1, 9, skin)
        c.put(14, 3, "3"), c.rect(13, 4, 15, 6, "3"), c.rect(13, 7, 15, 7, "y")
        c.put(12, 2, "L"), c.put(15, 2, "L")
        return
    if k.get("carry") and not (pose == "talk" and side > 0):
        # both hands bring the vessel in front of the chest
        c.rect(x, 15, x + 1, 19, cc)
        c.rect(3 if side < 0 else 10, 19, 5 if side < 0 else 12, 20, cc)
        return
    if pose in ("walk1", "walk3"):
        swing = 2 if (pose == "walk1") == (side > 0) else 0      # arms swing against the legs
        c.rect(x, 15, x + 1, 22 - swing, cc)
        c.rect(x + (1 if side > 0 else 0), 15, x + (1 if side > 0 else 0), 22 - swing, edge)
        c.rect(3 if side < 0 else 12, 17, 3 if side < 0 else 12, 22 - swing, "k")
        hand(x + (1 if side > 0 else -1) * (swing > 0), 23 - swing)
        return
    if not raised and pose not in ("plead", "wash", "drink", "kneel", "look-hands"):
        c.rect(x, 15, x + 1, 22, cc)
        c.rect(x + (1 if side > 0 else 0), 16, x + (1 if side > 0 else 0), 22, edge)
        # a dark seam between the sleeve and the body, so the arm reads as an arm
        c.rect(3 if side < 0 else 12, 17, 3 if side < 0 else 12, 22, "k")
        hand(x, 23)
        return
    if pose == "point":
        c.rect(x, 9, x + 1, 16, cc)
        c.put(x + 1, 7, skin), c.put(x + 1, 6, skin), c.rect(x, 8, x + 1, 8, skin)
        return
    if pose == "tip-hat":
        c.rect(x, 8, x + 1, 16, cc)
        c.rect(11, 3, 13, 4, skin)                   # the hand on the brim
        c.put(12, 5, cc)
        return
    if pose == "talk":
        # forearm out to the side, open palm up
        c.rect(x, 15, x + 1, 18, cc)
        c.rect(x + 1, 18, x + 2, 19, cc)
        c.rect(x + 2, 16, x + 2, 17, skin)
        c.put(x + 1, 17, skin)
        return
    if pose == "hands-head":
        c.rect(x + (0 if side < 0 else 1), 9, x + (0 if side < 0 else 1), 16, cc)
        c.rect(x + (1 if side < 0 else 0), 9, x + (1 if side < 0 else 0), 15, cc)
        c.rect(2 if side < 0 else 12, 7, 3 if side < 0 else 13, 8, skin)
        return
    if pose == "look-hands":
        # elbows out, both forearms raised before the chest, cupped palms up under the chin
        shade = k["shade"]
        if side < 0:
            c.rect(1, 15, 2, 20, cc), c.rect(3, 20, 5, 21, cc), c.rect(3, 19, 4, 19, cc)
            c.rect(4, 19, 7, 19, "1")                      # the shirt cuff
            c.rect(4, 17, 7, 18, skin), c.rect(5, 17, 6, 17, shade), c.put(4, 16, skin), c.put(6, 16, skin), c.put(7, 16, skin)
        else:
            c.rect(13, 15, 14, 20, cc), c.rect(10, 20, 12, 21, cc), c.rect(11, 19, 12, 19, cc)
            c.rect(8, 19, 11, 19, "1")
            c.rect(8, 17, 11, 18, skin), c.rect(9, 17, 10, 17, shade), c.put(8, 16, skin), c.put(9, 16, skin), c.put(11, 16, skin)
        return
    if pose in ("plead", "kneel"):
        # both hands clasped at the chest
        c.rect(x, 15, x + 1, 18, cc)
        c.rect(5 if side < 0 else 9, 18, 7 if side < 0 else 10, 19, cc)
        c.rect(7, 17, 8, 18, skin)
        return
    if pose == "wash":
        c.rect(x, 15, x + 1, 19, cc)
        c.rect(4 if side < 0 else 10, 20, 7 if side < 0 else 11, 21, cc)
        c.rect(7, 21, 8, 22, skin)
        return
    if pose == "drink":
        if side < 0:
            c.rect(x, 15, x + 1, 22, cc), hand(x, 23)
            return
        c.rect(x, 15, x + 1, 17, cc)
        c.rect(11, 14, 12, 16, cc)
        c.rect(10, 11, 12, 13, "W")                # the mug at the lips
        c.put(13, 12, "W")
        return


def _body(c, k, pose):
    cc, edge, shirt = k["coat_c"], k["edge"], k.get("shirt", "1")
    low = pose in LOW_POSES
    if not low:
        _legs(c, pose, k)                            # a kneeling or sitting body gets its legs in `_lower`
    # torso
    c.rect(3, 15, 12, 23, cc)
    c.rect(2, 16, 2, 23, cc) if k["coat"] != "gown" else None
    c.rect(13, 16, 13, 23, cc) if k["coat"] != "gown" else None
    c.rect(12, 16, 12, 23, edge)
    if k["coat"] == "frock":
        if not low:
            c.rect(3, 24, 12, 26, cc)                # the tails over the trousers
            c.clear(7, 25), c.clear(8, 25), c.clear(7, 26), c.clear(8, 26)
            c.rect(12, 24, 12, 26, edge)
        c.rect(6, 15, 9, 18, shirt)                  # shirt front between the lapels
        c.put(6, 18, cc), c.put(9, 18, cc)
        c.rect(7, 19, 8, 22, edge)
    elif k["coat"] == "jacket":
        c.rect(6, 15, 9, 16, shirt)
        c.rect(7, 17, 8, 23, edge)
        c.rect(3, 23, 12, 23, k.get("belt", edge))
    elif k["coat"] in ("dress", "gown"):
        c.rect(6, 15, 9, 16, shirt)
        c.rect(3, 20, 12, 20, edge)                  # the waist
    elif k["coat"] == "cassock":
        c.rect(6, 15, 9, 16, shirt)                  # the white collar
        c.rect(7, 17, 8, 23, edge)                   # the row of buttons down the front
    if k.get("cravat"):
        c.rect(7, 15, 8, 16, k["cravat"])
    if k.get("buttons"):
        for y in (17, 19, 21):
            c.put(7, y, k["buttons"])
    if k.get("apron"):
        c.rect(4, 18, 11, 27 if k["legs"] == "skirt" else 25, k["apron"])
        c.rect(4, 18, 11, 18, "2")
    if k.get("shawl"):
        c.rect(2, 15, 13, 17, k["shawl"])
        c.rect(4, 18, 11, 18, k["shawl"])
        c.rect(6, 19, 9, 19, k["shawl"])
    if k.get("surplice"):
        end = k.get("surplice_end", 25)              # to the knee, lace on the hem
        c.rect(3, 18, 12, end, "1")
        c.rect(12, 18, 12, end, "2")
        for x in range(3, 13, 2):
            c.put(x, end, "2")
    if pose != "give-birth":                         # her arms are drawn in `_lower`, after the body is lowered
        _arm(c, k, -1, pose)
        _arm(c, k, +1, pose)
    if k.get("surplice"):
        for y in range(18, 24):                      # the wide white sleeves
            for x in (1, 2, 13, 14):
                if c.px[y][x] == cc:
                    c.px[y][x] = "1"
    if k.get("stole"):
        for x0, x1 in ((4, 5), (10, 11)):
            c.rect(x0, 15, x1, 24, k["stole"])
            c.rect(x1 if x0 == 4 else x0, 15, x1 if x0 == 4 else x0, 24, "8")
            c.rect(x0, 24, x1, 25, "3")              # gold fringe
    if k.get("carry"):                               # the small covered vessel, held in both hands
        c.put(7, 17, "3"), c.put(8, 17, "3")
        c.rect(6, 18, 9, 18, "1")
        c.rect(6, 19, 9, 21, "3")
        c.rect(7, 19, 8, 19, "1")
        c.rect(6, 21, 9, 21, "f")
        c.put(5, 20, k["skin"]), c.put(10, 20, k["skin"])
    if k.get("bell") and pose not in ("ring", "talk"):
        hy = 21 if pose == "walk1" else 23           # the hand at his side, the bell hanging from it
        c.put(14, hy + 1, "3"), c.rect(13, hy + 2, 15, hy + 3, "3"), c.rect(13, hy + 4, 15, hy + 4, "y")
    if k.get("pole") and not low:
        x = 15
        c.rect(x, 0, x, 24, "f")                    # the lamplighter's pole, held at the side
        c.put(x, 0, "3")
        if pose in ("stand", "talk", "point", "walk2", "walk4"):
            c.rect(13, 21, 14, 22, k["skin"])


def _head(c, k):
    skin, shade = k["skin"], k["shade"]
    c.rect(3, 5, 12, 13, skin)
    c.rect(4, 4, 11, 4, skin)
    c.clear(3, 13), c.clear(12, 13)
    c.rect(4, 14, 11, 14, shade) if False else None
    c.rect(6, 14, 9, 14, shade)                      # neck
    c.rect(4, 13, 11, 13, shade)                     # under the jaw
    c.put(2, 9, skin), c.put(13, 9, skin)            # ears
    c.put(2, 10, shade), c.put(13, 10, shade)
    c.put(7, 10, shade)                              # nose
    c.put(4, 10, "R") if k.get("blush", True) and k["skin"] in ("S", "A") else None
    c.put(11, 10, "R") if k.get("blush", True) and k["skin"] in ("S", "A") else None


def _hair(c, k):
    h, style = k["hair_c"], k["hair"]
    if style in ("short", "whiskers", "bun", "long"):
        c.rect(4, 3, 11, 4, h)
        c.rect(3, 5, 12, 5, h)
        c.rect(3, 6, 3, 7, h), c.rect(12, 6, 12, 7, h)
        c.put(4, 6, h), c.put(11, 6, h)
    if style == "balding":
        c.rect(3, 6, 3, 9, h), c.rect(12, 6, 12, 9, h)
        c.put(4, 5, h), c.put(11, 5, h)
    if style == "whiskers":
        c.rect(3, 8, 3, 11, h), c.rect(12, 8, 12, 11, h)
        c.put(4, 11, h), c.put(11, 11, h), c.put(4, 12, h), c.put(11, 12, h)
    if style == "bun":
        c.rect(6, 1, 9, 2, h)
    if style == "long":
        c.rect(2, 6, 2, 16, h), c.rect(13, 6, 13, 16, h)
        c.rect(3, 8, 3, 15, h), c.rect(12, 8, 12, 15, h)
    if k.get("beard"):
        c.rect(4, 12, 5, 13, h), c.rect(10, 12, 11, 13, h)
        c.rect(5, 13, 10, 14, h)


def _hat(c, k):
    hat, hc = k.get("hat"), k.get("hat_c", "k")
    if hat == "top":
        c.rect(5, 0, 10, 3, hc)
        c.rect(5, 3, 10, 3, "k")
        c.rect(2, 4, 13, 4, hc)
    elif hat == "cap":
        c.rect(4, 2, 11, 4, hc)
        c.rect(3, 4, 13, 4, hc)
        c.put(13, 4, "k")
    elif hat == "bonnet":
        c.rect(3, 2, 12, 4, hc)
        c.rect(2, 4, 2, 11, hc), c.rect(13, 4, 13, 11, hc)
        c.rect(3, 5, 3, 6, hc), c.rect(12, 5, 12, 6, hc)
        c.put(4, 13, "R"), c.put(11, 13, "R")        # the ribbon
    elif hat == "pith":
        c.stamp(1, 0, ["....tTTTTt....", "...TTTCCTTt...", "..TTTTCCTTTt..", "..tTTTTTTTTt..",
                       "tttttttttttttt"])


BROWS = {    # (left brow, right brow) as two 2-px rows each, drawn at y 6..7 over the eyes
    "neutral": (["..", "hh"], ["..", "hh"]),
    "worried": (["..", "hh"], ["..", "hh"]),      # tilted below
    "shocked": (["hh", ".."], ["hh", ".."]),
    "angry":   (["h.", ".h"], [".h", "h."]),
    "sad":     ([".h", "h."], ["h.", ".h"]),
    "smile":   (["..", "hh"], ["..", "hh"]),
}


def _face(c, k, expression, mouth, eyes, dy=0):
    """The face on the head; `dy` lowers eyes, brows and mouth on the head (a head tilted down)."""
    h = k["hair_c"] if k["hair"] != "balding" else "k"
    left, right = BROWS[expression]
    if expression == "worried":
        left, right = ([".h", "h."], ["h.", ".h"])
    c.stamp(5, 6 + dy, [r.replace("h", h) for r in left])
    c.stamp(9, 6 + dy, [r.replace("h", h) for r in right])
    # eyes: white and pupil, both pupils turned the same way (a figure looks somewhere)
    if eyes == "open":
        wide = expression == "shocked"
        c.stamp(5, 8 + dy, ["WK"]), c.stamp(9, 8 + dy, ["WK"])
        if wide:
            c.stamp(5, 9 + dy, ["WW"]), c.stamp(9, 9 + dy, ["WW"])
    elif eyes == "blink":
        c.stamp(5, 8 + dy, ["kk"]), c.stamp(9, 8 + dy, ["kk"])
    else:
        c.stamp(5, 8 + dy, ["KK"]), c.stamp(9, 8 + dy, ["KK"])
    # mouth, x 6..9, y 11..12
    if mouth == "rest":
        shape = {"smile": ["k..k", ".kk."], "sad": [".kk.", "k..k"], "shocked": [".KK.", ".KK."],
                 "angry": ["kkkk", "...."], "worried": [".kk.", "...."]}.get(expression, ["....", ".kk."])
    else:
        shape = {"closed": ["KKKK", "...."], "half": [".KK.", ".rr."], "open": ["KKKK", "KrrK"],
                 "wide": ["KKKK", "KrrK"]}[mouth]
    c.stamp(6, 11 + dy, shape)
    if mouth == "wide" and not dy:
        c.stamp(6, 13, [".KK."])


def _lower(rows, k, pose):
    """Kneeling and giving birth: the standing body (head, shoulders, a short torso) is moved down the
    cell and the legs are drawn under it, the lowest row staying on the ground line (row 29)."""
    cv = Canvas(FIG_W, FIG_H)
    cc, edge, skin = k["coat_c"], k["edge"], k["skin"]
    lc, sh = k["legs_c"], k["shoes"]
    skirt = k["legs"] == "skirt"
    if pose == "kneel":
        for y, r in enumerate(rows[:21]):
            cv.stamp(0, y + 6, [r])
        if skirt:                                    # the skirt pools round the knees
            cv.rect(2, 27, 13, 27, lc), cv.rect(1, 28, 14, 28, lc), cv.rect(0, 29, 15, 29, k.get("edge", lc))
            cv.rect(5, 29, 6, 29, sh), cv.rect(9, 29, 10, 29, sh)
        else:
            cv.rect(3, 27, 12, 27, lc)               # thighs, foreshortened
            cv.rect(2, 28, 6, 28, lc), cv.rect(9, 28, 13, 28, lc)
            cv.rect(2, 29, 6, 29, sh), cv.rect(9, 29, 13, 29, sh)
        return cv.rows()
    # give-birth: seated low on the ground, knees up and apart, leaning back on one arm
    for y, r in enumerate(rows[:20]):
        cv.stamp(1, y + 8, [r])
    for sx, sx1, inner in ((1, 3, 3), (12, 14, 12)):  # the two raised legs: knees up at chest height, shins below
        cv.rect(sx, 23, sx1, 29, lc), cv.rect(sx, 22, sx1, 22, edge)
        cv.rect(inner, 23, inner, 28, edge)
        cv.rect(4 if sx < 5 else 11, 23, 4 if sx < 5 else 11, 28, "k")     # the dark gap between leg and body
        if skirt:                                    # the hem rides up: bare shins below the knees
            cv.rect(sx, 27, sx1, 28, skin), cv.rect(inner, 27, inner, 28, k["shade"])
            cv.rect(sx, 26, sx1, 26, edge)
        cv.rect(sx, 29, sx1, 29, sh)
    cv.rect(4, 28, 11, 29, lc)                       # the lap between the knees
    cv.rect(4, 28, 11, 28, edge)
    # the supporting arm braced on the ground at her side (bare forearm, hand flat), the other hand on the belly
    cv.rect(0, 24, 1, 25, cc), cv.rect(0, 26, 1, 28, skin), cv.rect(0, 29, 2, 29, skin)
    cv.rect(14, 23, 15, 25, cc), cv.rect(11, 25, 14, 26, cc), cv.rect(7, 25, 10, 27, skin), cv.put(9, 27, k["shade"])
    return cv.rows()


def figure(key, pose="stand", expression="neutral", mouth="rest", eyes="open"):
    k = CHARACTERS[key]
    c = Canvas(FIG_W, FIG_H)
    _body(c, k, pose)
    if pose == "look-hands":
        # the head tilted down: drawn on its own and set one row lower, the face lower still on it
        hc = Canvas(FIG_W, FIG_H)
        _head(hc, k)
        _hair(hc, k)
        _face(hc, k, expression, mouth, eyes, dy=1)
        _hat(hc, k)
        c.stamp(0, 1, hc.rows())
        return c.rows()
    _head(c, k)
    _hair(c, k)
    _face(c, k, expression, mouth, eyes)
    _hat(c, k)
    if pose in LOW_POSES:
        return _lower(c.rows(), k, pose)
    if pose == "drink":                              # the mug is in front of the mouth
        c.rect(10, 11, 12, 13, "W"), c.put(13, 12, "W")
    if pose == "tip-hat" and k.get("hat"):
        _arm(c, k, +1, pose)                         # the hand over the brim
    rows = c.rows()
    if k.get("child"):
        # a boy: the head keeps its size, the trunk and legs lose seven rows (23 of 30 px, 0.77)
        rows = ["." * FIG_W] * 7 + [r for y, r in enumerate(rows) if y not in (17, 19, 21, 23, 25, 26, 27)]
    return rows


# ---------------------------------------------------------------------------
# the bust, 30 x 34: head 18 x 17 (x 6..23, y 4..20), shoulders below
# ---------------------------------------------------------------------------

def _bust_head(c, k):
    skin, shade = k["skin"], k["shade"]
    c.rect(7, 5, 22, 19, skin)
    c.rect(8, 4, 21, 4, skin)
    c.rect(8, 20, 21, 20, skin)
    c.rect(10, 21, 19, 21, skin)
    c.rect(8, 20, 9, 20, shade), c.rect(20, 20, 21, 20, shade)
    c.rect(10, 21, 19, 21, shade)
    c.rect(12, 22, 17, 23, shade)                    # neck
    c.rect(5, 11, 6, 14, skin), c.rect(23, 11, 24, 14, skin)       # ears
    c.put(5, 13, shade), c.put(24, 13, shade)
    c.rect(14, 12, 15, 14, shade)                    # nose: a bridge and a shadow
    c.put(16, 14, shade)
    if k["skin"] in ("S", "A"):
        c.rect(9, 15, 10, 15, "R"), c.rect(19, 15, 20, 15, "R")


def _bust_hair(c, k):
    h, style = k["hair_c"], k["hair"]
    if style in ("short", "whiskers", "bun", "long"):
        c.rect(8, 2, 21, 4, h)
        c.rect(7, 4, 22, 6, h)
        c.rect(7, 7, 7, 10, h), c.rect(22, 7, 22, 10, h)
        c.rect(8, 7, 9, 7, h), c.rect(19, 7, 21, 7, h)
        c.put(12, 7, h), c.put(16, 7, h)             # a parted fringe
    if style == "whiskers":
        c.rect(7, 11, 8, 18, h), c.rect(21, 11, 22, 18, h)
        c.rect(8, 18, 9, 19, h), c.rect(20, 18, 21, 19, h)
    if style == "balding":
        c.rect(6, 8, 7, 13, h), c.rect(22, 8, 23, 13, h)
    if style == "bun":
        c.rect(12, 0, 17, 2, h)
    if style == "long":
        c.rect(5, 6, 6, 26, h), c.rect(23, 6, 24, 26, h)


def _bust_hat(c, k):
    hat, hc = k.get("hat"), k.get("hat_c", "k")
    if hat == "pith":
        c.rect(9, 0, 20, 3, "T")
        c.rect(10, 0, 19, 0, "t")
        c.rect(13, 1, 16, 2, "C")                    # the headlamp
        c.rect(4, 4, 25, 5, "t")
        c.rect(7, 3, 22, 3, "T")
    elif hat == "top":
        c.rect(9, 0, 20, 3, hc)
        c.rect(5, 4, 24, 4, hc)
    elif hat == "cap":
        c.rect(8, 1, 21, 4, hc)
        c.rect(7, 4, 25, 5, hc)


def _bust_body(c, k, pose):
    cc, edge, shirt = k["coat_c"], k["edge"], k.get("shirt", "1")
    c.rect(4, 24, 25, 33, cc)
    c.rect(2, 26, 3, 33, cc), c.rect(26, 26, 27, 33, cc)
    c.rect(24, 25, 25, 33, edge)
    if k["coat"] == "frock":
        c.rect(11, 24, 18, 33, shirt)
        c.rect(10, 24, 10, 33, edge), c.rect(19, 24, 19, 33, edge)
        c.rect(9, 27, 11, 29, cc), c.rect(18, 27, 20, 29, cc)        # lapels
    else:
        c.rect(11, 24, 18, 26, shirt)
        c.rect(14, 27, 15, 33, edge)
    if k.get("cravat"):
        c.rect(13, 24, 16, 26, k["cravat"])
        c.rect(14, 27, 15, 28, k["cravat"])
    if k.get("shirt") and k["coat"] == "jacket" and k.get("shirt") == "R":
        c.rect(10, 24, 19, 25, "R")                  # the explorer's scarf
    skin = k["skin"]
    if pose == "talk":
        c.rect(22, 25, 25, 33, cc)
        c.rect(23, 21, 26, 24, skin)                 # an open hand raised beside the chin
        c.rect(26, 19, 26, 21, skin), c.put(24, 20, skin)
    elif pose == "point":
        c.rect(23, 14, 26, 33, cc)
        c.rect(24, 8, 25, 13, skin), c.rect(25, 6, 25, 7, skin)


def _bust_face(c, k, expression, mouth, eyes):
    h = k["hair_c"] if k["hair"] != "balding" else "k"
    brow_y = 9
    lb, rb = [(9, brow_y), (10, brow_y), (11, brow_y), (12, brow_y)], [(17, brow_y), (18, brow_y), (19, brow_y), (20, brow_y)]
    # the inner ends of the brows (nearest the nose) go up for worry and sadness, down for anger
    inner = {"worried": -1, "sad": -1, "angry": +1}.get(expression, 0)
    lift = -1 if expression == "shocked" else 0
    for i, ((lx, ly), (rx, ry)) in enumerate(zip(lb, rb)):
        c.put(lx, ly + lift + (inner if i >= 2 else 0), h)
        c.put(rx, ry + lift + (inner if i < 2 else 0), h)
    # eyes 3 x 3 with a highlight; lids for blink and narrow
    for x0 in (9, 18):
        if eyes == "blink":
            c.rect(x0, 12, x0 + 2, 12, "k")
            continue
        c.rect(x0, 11, x0 + 2, 13, "W")
        c.rect(x0 + 1, 11, x0 + 2, 13, "K")
        c.put(x0 + 1, 11, "W")                       # the catch light
        if eyes == "narrow" or expression == "angry":
            c.rect(x0, 11, x0 + 2, 11, k["shade"])
        if expression == "shocked":
            c.rect(x0, 10, x0 + 2, 10, "W")
    # mouth, x 12..17, y 16..19
    if mouth == "rest":
        shape = {"smile": ["K....K", ".KKKK.", "......"], "sad": ["......", ".KKKK.", "K....K"],
                 "shocked": ["..KK..", ".KrrK.", "..KK.."], "angry": ["KKKKKK", "......", "......"],
                 "worried": ["......", ".KKKK.", "......"]}.get(expression, ["......", ".KKKK.", "......"])
    else:
        shape = {"closed": ["......", "KKKKKK", "......"],
                 "half": [".KKKK.", ".KrrK.", "..KK.."],
                 "open": [".KKKK.", "KrrrrK", "KrrrrK", ".KKKK."],
                 "wide": ["KKKKKK", "KrWWrK", "KrrrrK", "KrrrrK", ".KKKK."]}[mouth]
    c.stamp(12, 16, shape)


def bust(key, pose="stand", expression="neutral", mouth="rest", eyes="open"):
    k = CHARACTERS[key]
    c = Canvas(BUST_W, BUST_H)
    _bust_body(c, k, pose)
    _bust_head(c, k)
    _bust_hair(c, k)
    _bust_face(c, k, expression, mouth, eyes)
    _bust_hat(c, k)
    return c.rows()


# ---------------------------------------------------------------------------
# the bed, 32 x 16: a person lying with the head on the pillow (left), under a grey-white blanket
# ---------------------------------------------------------------------------
# lie: on the back, seen in profile, face up; lie-turn: the head turned to the camera (7 x 7 px face);
# lie-side: on her side facing the camera, knees drawn up under the blanket; sick: on the back, head
# turned a little to the camera, the face grey-green, sweat on it, the eyes heavy-lidded

BLANKET_BACK = {10: 8, 11: 7, 12: 7, 13: 6, 14: 6, 15: 6, 16: 6, 17: 7, 18: 7, 19: 7, 20: 7, 21: 6, 22: 6, 23: 6,
                24: 6, 25: 7, 26: 8, 27: 9, 28: 9, 29: 9, 30: 9, 31: 10}
# on her side the hips make the highest hill, the drawn-up knees a second one, the shins fall away short of the foot
BLANKET_SIDE = {10: 8, 11: 7, 12: 7, 13: 8, 14: 8, 15: 7, 16: 6, 17: 5, 18: 5, 19: 5, 20: 5, 21: 5, 22: 6, 23: 6,
                24: 7, 25: 8, 26: 9, 27: 10, 28: 11, 29: 11, 30: 11, 31: 11}
# a sick man barely lifts the blanket: the chest, a long flat body, the feet
BLANKET_SICK = {10: 9, 11: 8, 12: 8, 13: 8, 14: 8, 15: 8, 16: 8, 17: 8, 18: 8, 19: 8, 20: 8, 21: 8, 22: 8, 23: 8,
                24: 8, 25: 8, 26: 8, 27: 8, 28: 9, 29: 9, 30: 9, 31: 10}


def _bed_blanket(c, hands, skin="A", profile=BLANKET_BACK, folds=(15, 20, 24, 28)):
    c.rect(1, 6, 9, 10, "1")                         # the pillow
    c.rect(1, 10, 9, 10, "2"), c.rect(9, 6, 9, 10, "2")
    # the blanket: shoulders, the rise of the knees, the feet, then it hangs over the bed's side
    for x, top in profile.items():
        c.rect(x, top, x, 14, "X")
        c.put(x, top, "x") if x in (10, 13, 21) else None
    c.rect(10, profile[10] + 1, 13, profile[10] + 1, "x")     # the folded edge at the chest
    c.rect(10, 13, 31, 14, "x")                      # the hem hanging down
    c.rect(10, 12, 31, 12, "X")
    for x in folds:
        c.rect(x, max(10, profile[x] + 2), x, 12, "x")        # the folds
    if hands == "chest":
        c.rect(14, 5, 16, 5, skin)
    elif hands == "edge":
        c.rect(10, 7, 12, 8, skin)


def _bed_mouth(expression, mouth):
    """3 x 3 rows of palette keys for the mouth."""
    if mouth == "rest":
        return {"smile": ["...", "k.k", ".k."], "sad": ["...", ".k.", "k.k"], "shocked": [".K.", "KrK", ".K."],
                "angry": ["...", "kkk", "..."], "worried": ["...", ".k.", "..."]}.get(expression, ["...", "kkk", "..."])
    return {"closed": ["...", "KKK", "..."], "half": ["...", "KrK", ".K."],
            "open": [".K.", "KrK", ".K."], "wide": ["KKK", "KrK", "KKK"]}[mouth]


BED_BROWS = {"neutral": [(4, 3), (5, 3), (7, 3), (8, 3)], "worried": [(4, 3), (5, 2), (7, 2), (8, 3)],
             "shocked": [(4, 2), (5, 2), (7, 2), (8, 2)], "angry": [(4, 2), (5, 3), (7, 3), (8, 2)],
             "sad": [(4, 3), (5, 2), (7, 2), (8, 3)], "smile": [(4, 3), (5, 3), (7, 3), (8, 3)]}


def _bed_face(c, k, pose, expression, mouth, eyes):
    h, style = k["hair_c"], k["hair"]
    skin, shade = k["skin"], k["shade"]
    longhair = style == "long"
    if pose == "sick":
        skin, shade = "5", "0"                       # pale and grey-green
    if pose == "lie":
        # in profile, face up: forehead to the left, nose bump on top, mouth to the right
        c.rect(3, 3, 9, 8, skin), c.rect(4, 2, 8, 2, skin)
        c.clear(3, 3), c.clear(3, 8), c.clear(9, 8)
        c.put(7, 1, skin), c.put(7, 2, shade)        # the nose
        c.rect(9, 3, 9, 7, shade)                    # the chin and cheek in shade
        if style == "balding":                       # bare on top, a fringe behind the ear
            c.rect(2, 4, 3, 9, h)
        else:
            c.rect(2, 2, 4, 9, h), c.rect(3, 1, 5, 1, h)
        if longhair:
            c.rect(1, 9, 3, 11, h)                   # long hair down over the pillow
        brows = {"neutral": [(5, 3), (6, 3)], "worried": [(5, 2), (6, 3)], "shocked": [(5, 2), (6, 2)],
                 "angry": [(5, 3), (6, 2)], "sad": [(5, 3), (6, 4)], "smile": [(5, 3), (6, 3)]}[expression]
        for x, y in brows:
            c.put(x, y, h)
        if eyes == "open":
            c.put(5, 4, "W"), c.put(6, 4, "K")
        elif eyes == "blink":
            c.put(5, 4, "k"), c.put(6, 4, "k")
        else:
            c.put(5, 4, "K"), c.put(6, 4, "K")
        for dy, row in enumerate(_bed_mouth(expression, mouth)):
            for dx, ch in enumerate(row):
                c.put(7 + dx, 5 + dy, ch)
        return
    # turned to the camera (lie-turn, lie-side, sick)
    c.rect(3, 3, 9, 8, skin)
    c.clear(3, 8), c.clear(9, 8)
    if style == "balding":                           # bare on top, a fringe at the sides
        c.rect(2, 3, 2, 8, h), c.rect(10, 3, 10, 8, h)
        c.rect(3, 2, 9, 2, skin), c.rect(4, 1, 8, 1, skin)
        c.put(3, 3, h), c.put(9, 3, h)
    else:
        c.rect(2, 1, 10, 2, h), c.rect(2, 3, 2, 9, h), c.rect(10, 3, 10, 9, h)
        c.put(3, 3, h), c.put(9, 3, h)
        if longhair:
            c.rect(1, 9, 3, 11, h), c.rect(9, 9, 11, 11, h)
    if pose == "sick":
        c.put(7, 6, shade)                           # the nose, the head turned a little away
        c.rect(3, 5, 3, 7, shade)                    # the far cheek in shade
        c.put(4, 5, shade), c.put(8, 5, shade)       # shadows under the eyes
        for x, y in ((6, 3), (3, 4), (9, 6), (4, 8), (8, 2)):
            c.put(x, y, "%")                         # sweat
    else:
        c.put(6, 6, shade)                           # the nose
        c.put(3, 5, "R"), c.put(9, 5, "R")
    for x, y in BED_BROWS[expression]:
        c.put(x, y, h)
    for ex, (a, b) in ((4, ("W", "K")), (7, ("K", "W"))):
        if eyes == "open":
            if pose == "sick":                       # heavy lids: half the white covered
                a, b = (shade, "K") if ex == 4 else ("K", shade)
            c.put(ex, 4, a), c.put(ex + 1, 4, b)
        elif eyes == "blink":
            c.put(ex, 4, "k"), c.put(ex + 1, 4, "k")
        else:
            c.put(ex, 4, "K"), c.put(ex + 1, 4, "K")
    for dy, row in enumerate(_bed_mouth(expression, mouth)):
        for dx, ch in enumerate(row):
            c.put(5 + dx, 6 + dy, ch)


def bed(key, pose="lie", expression="neutral", mouth="rest", eyes="open"):
    k = CHARACTERS[key]
    c = Canvas(BED_W, BED_H)
    if pose == "lie-side":
        _bed_blanket(c, "edge", k["skin"], BLANKET_SIDE, folds=(14, 19, 22, 25))
    elif pose == "sick":
        _bed_blanket(c, None, "5", BLANKET_SICK, folds=(15, 21, 26))
    else:
        _bed_blanket(c, "chest" if pose == "lie" else "edge", k["skin"])
    _bed_face(c, k, pose, expression, mouth, eyes)
    return c.rows()


# ---------------------------------------------------------------------------
# the hands, 48 x 32: a pair of bare hands coming out of dark coat cuffs, seen from above and in front
# ---------------------------------------------------------------------------
# open: both palms up, fingers a little spread, thumbs out; reach: one hand forward, flat, back to the
# camera (pushing a door); hold: both hands loosely together, the fingertips darkened with dirt

def _cuff(c, k, x0, x1, y0=23):
    """A forearm's end: skin at the wrist, a white shirt cuff, the dark coat sleeve to the cell's edge."""
    cc, edge = k["coat_c"], k["edge"]
    c.rect(x0 + 1, y0 - 3, x1 - 1, y0, k["skin"])
    c.rect(x0 + 1, y0, x1 - 1, y0, k["shade"])
    c.rect(x0, y0 + 1, x1, y0 + 2, "1"), c.rect(x0, y0 + 2, x1, y0 + 2, "2")
    c.rect(x0 - 1, y0 + 3, x1 + 1, HANDS_H - 1, cc)
    c.rect(x1 + 1, y0 + 3, x1 + 1, HANDS_H - 1, edge)
    c.put(x0 + 1, y0 + 5, "3"), c.put(x0 + 1, y0 + 6, "3")    # a brass cuff button


def _hand(c, k, x0, flip=False, back=False, dirt=False, spread=True, curl=0):
    """One hand, palm 12 px wide at x0.., y 13..21, fingers above, thumb to the side (mirrored when
    flip). back: the back of the hand towards us (knuckles instead of palm creases), fingers together."""
    skin, shade = k["skin"], k["shade"]

    def put(x, y, ch):
        c.put(x0 + 11 - x if flip else x0 + x, y, ch)

    for y in range(13, 22):
        for x in range(12):
            put(x, y, skin)
    for x in (0, 11):
        put(x, 21, ".")
    for x in range(2, 10):
        put(x, 22, skin)
    if back:
        for x in (1, 4, 7, 10):
            put(x, 13, shade)                        # the knuckles
        for x in (5, 6):
            put(x, 20, shade)                        # a fold at the wrist
    else:
        for x in range(2, 6):
            put(x, 17, shade)                        # the heart line
        for x in range(5, 10):
            put(x, 19, shade)                        # the life line
    # fingers: left edge, length, lean (the outer ones fan a little when spread)
    for fx, length, lean in ((0, 6, -1), (3, 8, 0), (6, 8, 0), (9, 5, 1)):
        lean = lean if spread else 0
        length -= curl                               # curled fingers show shorter
        for r in range(length):
            xs = fx + (lean if r >= length // 2 else 0)
            put(xs, 12 - r, skin), put(xs + 1, 12 - r, skin)
            if spread and r == length // 2 - 1:
                put(xs + 2, 12 - r, shade) if fx < 9 else None
        if not spread:
            for r in range(length):
                put(fx + 2, 12 - r, shade) if fx < 9 else None
        if dirt:
            put(fx + lean, 13 - length, "q")
    # the thumb: out to the side of the palm, rising
    for tx, ty in ((-1, 19), (-2, 18), (-2, 17), (-3, 16), (-3, 15), (-3, 14)):
        put(tx, ty, skin), put(tx + 1, ty, skin)
    put(-3, 14, shade)


def hands(key, pose="open", expression="neutral", mouth="rest", eyes="open"):
    """No face: expression, mouth and eyes do not change the picture."""
    k = CHARACTERS[key]
    c = Canvas(HANDS_W, HANDS_H)
    if pose == "open":
        _cuff(c, k, 9, 18), _cuff(c, k, 29, 38)
        _hand(c, k, 8), _hand(c, k, 28, flip=True)
    elif pose == "reach":
        _cuff(c, k, 19, 28)
        _hand(c, k, 18, back=True, spread=False)
    elif pose == "hold":
        _cuff(c, k, 13, 22), _cuff(c, k, 25, 34)
        _hand(c, k, 12, back=True, spread=False, dirt=True, curl=3)
        _hand(c, k, 24, flip=True, back=True, spread=False, dirt=True, curl=3)
        for y in range(13, 22):
            c.put(24, y, k["shade"])
    return c.rows()


def _size(key, size):
    return "bed" if CHARACTERS[key].get("bed") else size


def cell(key, pose="stand", expression="neutral", mouth="rest", eyes="open", size="figure"):
    size = _size(key, size)
    draw = {"bust": bust, "bed": bed, "hands": hands}.get(size, figure)
    return grid(draw(key, pose, expression, mouth, eyes))


def sizes_of(key):
    """The cell sizes a character is drawn at: the patient only lies in a bed; some also have a bed or hands."""
    c = CHARACTERS[key]
    if c.get("bed"):
        return ["bed"]
    return ["figure"] + (["bust"] if c["bust"] else []) + list(c["extra"])


def poses_of(key, size="figure"):
    size = _size(key, size)
    if size == "bust":
        return BUST_POSES
    if size == "bed":
        return BED_POSES
    if size == "hands":
        return HANDS_POSES
    return CHARACTERS[key]["poses"]


def atlas_layout(key, size="figure"):
    """Where each cell sits in the character's atlas: column = mouth * len(EYES) + eyes,
    row = pose * len(EXPRESSIONS) + expression. -> {"cols", "rows", "w", "h", "col", "row"}.
    The hands have no face: one column and one row per pose, every mouth/eyes/expression pointing at it."""
    size = _size(key, size)
    w, h = {"bust": (BUST_W, BUST_H), "bed": (BED_W, BED_H), "hands": (HANDS_W, HANDS_H)}.get(size, (FIG_W, FIG_H))
    poses = poses_of(key, size)
    if size == "hands":
        return {"cols": 1, "rows": len(poses), "w": w + 2, "h": h + 2,
                "col": {(m, e): 0 for m in MOUTHS for e in EYES},
                "row": {(p, x): poses.index(p) for p in poses for x in EXPRESSIONS}}
    return {"cols": len(MOUTHS) * len(EYES), "rows": len(poses) * len(EXPRESSIONS), "w": w + 2, "h": h + 2,
            "col": {(m, e): MOUTHS.index(m) * len(EYES) + EYES.index(e) for m in MOUTHS for e in EYES},
            "row": {(p, x): poses.index(p) * len(EXPRESSIONS) + EXPRESSIONS.index(x) for p in poses for x in EXPRESSIONS}}
