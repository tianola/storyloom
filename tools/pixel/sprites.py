"""Pixel-art sprites for the explainer's characters, drawn by hand as character grids.

Each sprite is a list of equal-width strings; every character is a palette key, '.' is clear.
`sprite()` turns one into an RGBA image and adds a one-pixel dark outline around the silhouette,
so the grids hold only the fill and the inner detail.

Original designs: a hard-hat worker (awake, sleepy, asleep on the desk), an explorer with a pith
helmet and headlamp, a round critter carrying one token of text, and a little flatbed truck.
"""
PALETTE = {
    "K": "#14101e", "k": "#2b2438", "w": "#8b86a0", "W": "#f2efe6",
    "S": "#f5c6a0", "s": "#d08f6c", "R": "#e5566a", "r": "#a8304a",
    "Y": "#ffcf3d", "y": "#d6901a", "L": "#fff2a6",
    "B": "#4a78e0", "b": "#2f4ea3", "G": "#6fa046", "g": "#44702a",
    "T": "#e8d49c", "t": "#b59a5c", "N": "#8a5530", "n": "#5a3420",
    "O": "#ff9c33", "o": "#d2641c", "H": "#ffd88a",
    "C": "#66f2ff", "c": "#2399b5", "P": "#ff8a3a", "p": "#9c4320",
    "D": "#161b2b", "d": "#1f2639", "e": "#2c3550", "F": "#c9a24a", "f": "#7c6330",
    "M": "#b8743a", "m": "#6e3f1c", "V": "#0d0b14",
}


def rgb(key):
    h = PALETTE[key].lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def grid(rows, width=None):
    width = width or max(len(r) for r in rows)
    return [r.ljust(width, ".")[:width] for r in rows]


def pixels(rows, outline=True):
    """-> (width, height, {(x, y): (r, g, b)}) with y counted from the top; no imaging library needed,
    so Blender can build the same sprite as an image of its own."""
    rows = grid(rows)
    pad = 1 if outline else 0
    w, h = len(rows[0]) + 2 * pad, len(rows) + 2 * pad
    out = {}
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != ".":
                out[(x + pad, y + pad)] = rgb(ch)
    if outline:
        ink = rgb("K")
        solid = set(out)
        for x in range(w):
            for y in range(h):
                if (x, y) not in solid and any((x + dx, y + dy) in solid for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    out[(x, y)] = ink
    return w, h, out


def sprite(rows, outline=True):
    from PIL import Image
    rows = grid(rows)
    h, w = len(rows), len(rows[0])
    pad = 1 if outline else 0
    img = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    px = img.load()
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != ".":
                px[x + pad, y + pad] = (*rgb(ch), 255)
    if outline:
        ink = (*rgb("K"), 255)
        solid = {(x, y) for x in range(img.width) for y in range(img.height) if px[x, y][3]}
        for x in range(img.width):
            for y in range(img.height):
                if (x, y) in solid:
                    continue
                if any((x + dx, y + dy) in solid for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    px[x, y] = ink
    return img


def overlay(rows, at, patch):
    """Paint `patch` (rows) onto `rows` with its top-left at (x, y); '.' in the patch leaves it."""
    rows = [list(r) for r in rows]
    x0, y0 = at
    for dy, prow in enumerate(patch):
        for dx, ch in enumerate(prow):
            if ch != ".":
                y, x = y0 + dy, x0 + dx
                while y >= len(rows):
                    rows.append(["."] * len(rows[0]))
                if 0 <= x < len(rows[y]):
                    rows[y][x] = ch
    return ["".join(r) for r in rows]


def flip(rows):
    return [r[::-1] for r in rows]


# ---------------------------------------------------------------------------
# the worker
# ---------------------------------------------------------------------------

HARD_HAT = [
    "....YYYYYY....",
    "...YLLYYYYy...",
    "..YLYYYYYYYy..",
    "..YYYYYYYYYy..",
    "yyyyyyyyyyyyyy",
]

FACES = {
    "sleepy": [
        "..SSSSSSSSSS..",
        "..SSSSSSSSSS..",
        "..SkkkSSkkkS..",
        "..SWKSSSSWKS..",
        "..SRRSSSSRRS..",
        "..sSSSKKSSSs..",
        "...sSSKKSSs...",
        "....ssssss....",
    ],
    "awake": [
        "..SSSSSSSSSS..",
        "..SKKSSSSKKS..",
        "..SWKSSSSWKS..",
        "..SKKSSSSKKS..",
        "..SRSSSSSSRS..",
        "..sSSKKKKSSs..",
        "...sSSSSSSs...",
        "....ssssss....",
    ],
    "dozing": [
        "..SSSSSSSSSS..",
        "..SSSSSSSSSS..",
        "..SSSSSSSSSS..",
        "..SKKKSSKKKS..",
        "..SRRSSSSRRS..",
        "..sSSSSKSSSs..",
        "...sSSSSSSs...",
        "....ssssss....",
    ],
    "shocked": [
        "..SSSSSSSSSS..",
        "..SWWSSSSWWS..",
        "..SWKSSSSWKS..",
        "..SWWSSSSWWS..",
        "..SRSSKKSSRS..",
        "..sSSKRRKSSs..",
        "...sSSKKSSs...",
        "....ssssss....",
    ],
}

OVERALLS = [
    "..BBBBBBBBBB..",
    ".BBBWBBBBWBBB.",
    "BBBBWBBBBWBBBB",
    "BBBBBBBBBBBBBB",
    "SBBBBBYYBBBBBS",
    "S.bBBBBBBBBb.S",
    "..bbbbbbbbbb..",
    "..bbb....bbb..",
    "..nnn....nnn..",
]


def worker(face="awake"):
    return grid(HARD_HAT + FACES[face] + OVERALLS)


# asleep with the head down on the desk: hat, a strip of forehead, folded arms
WORKER_ASLEEP = grid([
    "....YYYYYY....",
    "...YLLYYYYy...",
    "..YLYYYYYYYy..",
    "..YYYYYYYYYy..",
    "yyyyyyyyyyyyyy",
    ".BBsSSSSSSsBB.",
    "BBBBSSSSSSBBBB",
    "BBBBBBBBBBBBBB",
])

# chin in hand, waiting
WORKER_BORED = grid(HARD_HAT + [
    "..SSSSSSSSSS..",
    "..SSSSSSSSSS..",
    "..SkkkSSkkkS..",
    "..SKWSSSSKWS..",
    "..SRSSSSSSRS..",
    "..sSSSkkkSSs..",
    "...sSSSSSSs...",
    "....sSSSSs....",
    "..BBBSSSSBBB..",
    ".BBBBBSSBBBBB.",
    "BBBBWBBBBWBBBB",
    "BBBBBBBBBBBBBB",
])

MUG = grid([
    ".w.w..",
    "w.w...",
    "WWWW..",
    "WkkWW.",
    "WWWW.W",
    "WWWWW.",
    "wwww..",
])

ZZZ = grid([
    ".......WWWW",
    ".........W.",
    "........W..",
    ".......WWWW",
    "WWWWW......",
    "...W.......",
    "..W........",
    ".W.........",
    "WWWWW......",
])

# ---------------------------------------------------------------------------
# the explorer
# ---------------------------------------------------------------------------

PITH = [
    "....tTTTTt....",
    "...TTTCCTTt...",
    "..TTTTCCTTTt..",
    "..tTTTTTTTTt..",
    "tttttttttttttt",
]

EXPLORER_BODY = [
    "..SSSSSSSSSS..",
    "..SKKSSSSKKS..",
    "..SWKSSSSWKS..",
    "..SSSSSSSSSS..",
    "..SRSSSSSSRS..",
    "..sSKSSSSKSs..",
    "...sSKKKKSs...",
    "....ssssss....",
    "..RRRRRRRRRR..",
    "GGGNGGGGGGNGGG",
    "GGGGNGGGGNGGGG",
    "GGGGGNGGNGGGGG",
    "SGGGGGNNGGGGG.",
    "S.gGGGGGGGGg..",
    "..gNNNNNNNNg..",
    "..nnn....nnn..",
    "..nnn....nnn..",
]


def explorer():
    rows = grid(PITH + EXPLORER_BODY)
    rows = ["..." + r for r in rows]
    # the right arm raised, pointing up past the brim
    arm = {(0, 0): "S", (1, 0): "S", (1, 1): "S", (0, 1): "S", (1, 2): "S", (0, 2): "S",
           (1, 3): "G", (2, 3): "G", (1, 4): "G", (2, 4): "G", (2, 5): "G", (2, 6): "G",
           (2, 7): "G", (2, 8): "G", (2, 9): "G", (2, 10): "G", (2, 11): "G", (2, 12): "G",
           (2, 13): "G", (3, 14): "G"}
    rows = [list(r) for r in rows]
    for (x, y), ch in arm.items():
        rows[y][x] = ch
    rows[14][3] = "G"
    rows[17][3] = "."
    rows[18][3] = "."
    return ["".join(r) for r in rows]


# ---------------------------------------------------------------------------
# the token
# ---------------------------------------------------------------------------

FONT3 = {
    "c": ["...", ".##", "#..", "#..", ".##"],
    "a": ["...", "##.", ".##", "#.#", ".##"],
    "t": [".#.", "###", ".#.", ".#.", "..#"],
    "o": ["...", ".#.", "#.#", "#.#", ".#."],
    "g": ["...", ".##", "#.#", ".##", "##."],
    "d": ["..#", ".##", "#.#", "#.#", ".##"],
    "y": ["...", "#.#", "#.#", ".##", "##."],
    "m": ["...", "##.", "###", "#.#", "#.#"],
    "e": ["...", ".#.", "###", "#..", ".##"],
    "s": ["...", ".##", "##.", "..#", "##."],
}

TOKEN_BODY = grid([
    "..oO..........Oo..",
    "..OHO........OOo..",
    "..OHOOOOOOOOOOOo..",
    ".OHHOOOOOOOOOOOOo.",
    ".OHOOOOOOOOOOOOOo.",
    "OOOWWWOOOOOOWWWOOo",
    "OOWWWKOOOOOOWWWKOo",
    "OOWWKKOOOOOOWWKKOo",
    "OOOWWWOOOOOOWWWOOo",
    "ORROOOOOKKOOOOORRo",
    "OOOOOOOKRRKOOOOOOo",
    "OOOOOOOOKKOOOOOOOo",
    "oOwwwwwwwwwwwwwwOo",
    "oOwWWWWWWWWWWWWwOo",
    "oOwWWWWWWWWWWWWwOo",
    "oOwWWWWWWWWWWWWwOo",
    "oOwWWWWWWWWWWWWwOo",
    "oOwWWWWWWWWWWWWwOo",
    ".oOwwwwwwwwwwwwOo.",
    "..oooooooooooooo..",
    "...oo........oo...",
])


def token(word="cat"):
    rows = list(TOKEN_BODY)
    width = sum(4 for _ in word) - 1
    x = 2 + (14 - width) // 2
    for ch in word:
        glyph = [g.replace("#", "K") for g in FONT3.get(ch, FONT3["o"])]
        rows = overlay(rows, (x, 13), glyph)
        x += 4
    return rows


# ---------------------------------------------------------------------------
# the truck (seen from the side, cab on the right)
# ---------------------------------------------------------------------------

TRUCK = grid([
    "..CCCCCCCCCCCCC...........",
    "..CcCcCcCcCcCcC...WWWWWW..",
    "..CCCCCCCCCCCCC..WWccccWw.",
    "..CcCcCcCcCcCcC..WWccccWWw",
    "..CCCCCCCCCCCCC..WWWWWWWWw",
    "kkkkkkkkkkkkkkkkkWWWWWWWWw",
    "kwwwwwwwwwwwwwwwkWWWRRWWWw",
    "kkkkkkkkkkkkkkkkkkkkkkkkkk",
    "..kKKk...........kKKk.....",
    "..KwwK...........KwwK.....",
    "...KK.............KK......",
])
