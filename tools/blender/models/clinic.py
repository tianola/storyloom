"""The v6 Semmelweis sets: the explorer's evidence board, the death ledger, and the wing.

* `board`    the investigation, made physical (Veritasium mode): a cork board on a dark wall with
             the two clinic doors sketched on cards and their tallies, a calendar strip between them,
             the three hypothesis cards (AIR, POSITION, FEAR) pinned, struck and pulled down, and a
             desk below where the plan is laid out. `stage` says which of those states the beat opens
             in; the actions move it to the next. The explorer is a storyboard cast member.
* `ledger`   an insert set: the clinic's death register open on a desk by an oil lamp. The pages hold
             tally crosses only — no legible names, dates or words, which the sources would not
             support — under two column marks (I, II) and, for the street-births comparison, a third
             column under a small drawn street (`columns: street`). Action `tally` adds a cross.
* `wing`     the dissecting room, a corridor and the First Clinic's ward built as one place, so the
             held shot can follow the doctors from the morgue to a mother's bed without a cut: the
             continuity is the argument (c12, c15). It reuses `world.ward` (with its far door open)
             and `world.anatomy` (without Kolletschka, whose body is now the one on the table).
"""
import math
import random

import bpy
from mathutils import Vector

import characters
import kit
import look
import world
from kit import FPS, placed

PERSON_H = world.PERSON_H


def frames(seconds):
    return max(1, round(seconds * FPS))


def _light(name, loc, energy, color, size=None, kind="POINT"):
    data = bpy.data.lights.new(name, kind)
    data.energy = energy
    data.color = color
    if size is not None:
        data.shadow_soft_size = size
    ob = kit._link(bpy.data.objects.new(name, data))
    ob.location = loc
    return ob


def _tree(ob):
    out, stack = [], [ob]
    while stack:
        o = stack.pop()
        out.append(o)
        stack.extend(o.children)
    return out


def _hide_tree(ob):
    for o in _tree(ob):
        o.hide_render = True


def _show_from(ob, frame, total):
    """Hidden until `frame`, then shown (for cards that are pinned during a beat)."""
    ob.hide_render = frame > 1
    ob.keyframe_insert("hide_render", frame=1)
    if frame > 1:
        ob.hide_render = False
        ob.keyframe_insert("hide_render", frame=frame)


# ---------------------------------------------------------------------------
# The evidence board
# ---------------------------------------------------------------------------

STAGES = ("h1", "h2", "h3", "air", "position", "fear", "h4")


def _card(name, centre, size, paper, ink, title=None, text_size=0.07):
    """A paper card flat on the board (the board faces -y), optionally titled; returns its group."""
    x, y, z = centre
    w, h = size
    parts = [kit.box(f"{name}-paper", (x, y, z), (w, 0.004, h), paper, bevel=0)]
    if title:
        t = kit.flat_text(f"{name}-title", title, (x, y - 0.006, z + h * 0.22), text_size, ink,
                          rot=(math.pi / 2, 0, 0), extrude=0.0005)
        t["cut_ok"] = True
        parts.append(t)
    return kit.group(name, parts)


def _door_sketch(name, centre, ink, mark, n_marks):
    """A door drawn on a card in ink, its clinic numeral over it, and `n_marks` tally strokes under."""
    x, y, z = centre
    lines = [placed((x, y - 0.004, z + 0.13), (0.16, 0.002, 0.006)),
             placed((x - 0.08, y - 0.004, z + 0.02), (0.006, 0.002, 0.22)),
             placed((x + 0.08, y - 0.004, z + 0.02), (0.006, 0.002, 0.22)),
             placed((x + 0.05, y - 0.004, z + 0.0), (0.012, 0.002, 0.012))]
    door = kit.boxes(f"{name}-door", lines, ink)
    marks = []
    for k in range(n_marks):
        group, i = divmod(k, 5)
        gx = x - 0.13 + 0.075 * (group % 4)
        gz = z - 0.16 - 0.07 * (group // 4)
        if i < 4:
            marks.append(placed((gx + 0.012 * i, y - 0.004, gz), (0.004, 0.002, 0.05)))
        else:
            marks.append(placed((gx + 0.018, y - 0.004, gz), (0.06, 0.002, 0.004), 0.0))
    tally = kit.boxes(f"{name}-tally", marks, mark) if marks else None
    return door, tally


def board(p, seconds):
    """The explorer's evidence board. `stage`: h1 (doors, tallies, calendar) | h2 | h3 (cards laid on
    the desk) | air | position | fear (that card pinned) | h4 (all three struck). Actions: `flip`
    (the calendar strip turns to the other day), `lay` (three cards onto the desk), `pin` (the
    stage's card pressed onto the board), `pull` (the struck cards come down, one by one)."""
    from scenes import Set
    s = Set(seconds)
    s.lighting = "world"
    s.lens = 35.0
    n = s.frames
    stage = p.get("stage", "h1")
    if stage not in STAGES:
        raise ValueError(f"board stage {stage!r} is not one of {STAGES}")
    wall = kit.mat("board-wall", (0.10, 0.075, 0.06), roughness=0.9)
    cork = kit.mat("board-cork", (0.42, 0.30, 0.17), roughness=0.95)
    frame_wood = kit.mat("board-frame", (0.12, 0.07, 0.035), roughness=0.6)
    paper = kit.mat("board-paper", (0.86, 0.82, 0.72), roughness=0.9)
    ink = kit.mat("board-ink", (0.06, 0.05, 0.05), roughness=0.6)
    red = kit.mat("board-red", (0.55, 0.05, 0.04), roughness=0.5)
    pin_m = kit.mat("board-pin", (0.65, 0.08, 0.06), roughness=0.3)
    wood = kit.mat("board-desk", (0.16, 0.09, 0.045), roughness=0.6)
    floor = kit.mat("board-floor", (0.08, 0.055, 0.04), roughness=0.9)
    kit.box("board-wall", (0, 0.12, 2.0), (8.0, 0.2, 4.0), wall, bevel=0)
    kit.box("board-floor", (0, -2.0, -0.02), (8.0, 4.4, 0.04), floor, bevel=0)
    kit.box("board-cork", (0, 0.0, 1.62), (2.4, 0.03, 1.36), cork, bevel=0)
    kit.boxes("board-frame", [placed((0, -0.02, 1.62 + d * 0.7), (2.5, 0.05, 0.05)) for d in (-1, 1)]
              + [placed((d * 1.22, -0.02, 1.62), (0.05, 0.05, 1.45)) for d in (-1, 1)], frame_wood)
    # the desk under the board
    kit.boxes("board-desk", [placed((0, -0.55, 0.78), (1.9, 0.75, 0.05))]
              + [placed((dx, -0.55 + dy, 0.38), (0.05, 0.05, 0.76)) for dx in (-0.9, 0.9) for dy in (-0.32, 0.32)], wood)
    # the two clinic doors, sketched, with the 1846 tallies (11 against 3 per 100 births, c7)
    y = -0.02
    for k, (x, numeral, marks) in enumerate(((-0.62, "I", 11), (0.62, "II", 3))):
        _card(f"board-doorcard{k}", (x, y, 1.82), (0.46, 0.62), paper, ink, title=numeral, text_size=0.08)
        _door_sketch(f"board-doors{k}", (x, y - 0.002, 1.84), ink, red, marks)
        kit.cylinders(f"board-pin-d{k}", [((x, y - 0.03, 2.1), 0.012, 0.03)], pin_m)
    # the calendar strip between them: one day face, flipping to the next (alternate days)
    strip = kit.box("board-strip", (0, y - 0.004, 1.86), (0.3, 0.004, 0.16), paper, bevel=0)
    day_a = kit.flat_text("board-day-a", "MON", (0, y - 0.01, 1.86), 0.07, ink, rot=(math.pi / 2, 0, 0), extrude=0.0005)
    day_b = kit.flat_text("board-day-b", "TUE", (0, y - 0.01, 1.86), 0.07, ink, rot=(math.pi / 2, 0, 0), extrude=0.0005)
    for t in (day_a, day_b):
        t["cut_ok"] = True
    day_b.hide_render = True
    arrow = kit.boxes("board-arrow", [placed((-0.2, y - 0.005, 1.74), (0.12, 0.002, 0.008))], red)
    # red string between the door cards and the calendar
    kit.boxes("board-strings", [placed((-0.31, y - 0.012, 1.98), (0.32, 0.003, 0.004), 0.0),
                                placed((0.31, y - 0.012, 1.98), (0.32, 0.003, 0.004), 0.0)], red)
    s.pin("board", (0, -0.02, 1.62))
    s.pin("calendar", (0, -0.02, 1.86))
    # the three hypothesis cards, pinned in a row under the doors as the investigation goes on
    hyp = {}
    order = ("air", "position", "fear")
    reached = {"h1": 0, "h2": 0, "h3": 0, "air": 1, "position": 2, "fear": 3, "h4": 3}[stage]
    for k, word in enumerate(order):
        x = -0.75 + 0.75 * k
        g = _card(f"board-{word}", (x, y - 0.002, 1.18), (0.5, 0.3), paper, ink, title=word.upper(), text_size=0.075)
        pin = kit.cylinders(f"board-pin-{word}", [((x, y - 0.03, 1.3), 0.012, 0.03)], pin_m)
        pin.parent = g
        strike = kit.box(f"board-strike-{word}", (x, y - 0.01, 1.18), (0.52, 0.002, 0.02), red, bevel=0)
        strike.rotation_euler = (0, math.radians(-12), 0)
        strike.parent = g
        strike.hide_render = stage != "h4"
        hyp[word] = g
        if k >= reached:
            _hide_tree(g)
        s.pin(word, (x, y - 0.02, 1.18))
    # the desk cards (h3): laid one by one
    desk_cards = []
    for k, word in enumerate(order):
        x = -0.55 + 0.55 * k
        c = kit.box(f"desk-{word}", (x, -0.55, 0.81), (0.42, 0.26, 0.004), paper, bevel=0)
        t = kit.flat_text(f"desk-{word}-t", word.upper(), (x, -0.55, 0.815), 0.06, ink, extrude=0.0005)
        t["cut_ok"] = True
        t.parent = c
        t.location = (0, 0, 0.005)
        desk_cards.append(c)
        if stage != "h3":
            c.hide_render = True
            t.hide_render = True
    s.pin("desk", (0, -0.55, 0.82))
    # the blank card and pencil held to the lens (h2): a card in the near foreground
    if stage == "h2":
        blank = kit.box("h2-card", (0.25, -2.35, 1.38), (0.3, 0.004, 0.2), paper, bevel=0)
        blank.rotation_euler = (math.radians(12), 0, math.radians(-8))
        kit.cyl("h2-pencil", (0.42, -2.36, 1.32), 0.007, 0.2, kit.mat("h2-pencil", (0.75, 0.55, 0.12), roughness=0.5),
                rot=(0, math.radians(60), 0), verts=8)
    # light: a warm desk lamp, a cool key from the camera side, a rim on the wall
    lamp_m = look.neon("board-lamp", (1.0, 0.72, 0.42), 12.0)
    kit.ico("board-bulb", (-0.85, -0.45, 1.15), 0.05, lamp_m, subdivisions=2, smooth=True)
    _light("board-lamp", (-0.85, -0.5, 1.2), 90.0, (1.0, 0.7, 0.4), size=0.2)
    key = kit.common.add_area_light("board-key", (1.6, -3.2, 2.6), 260.0, color=(0.75, 0.82, 1.0), size=2.0)
    kit.common.aim(key, (0, 0, 1.5))
    fill = kit.common.add_area_light("board-fill", (-2.2, -2.4, 1.8), 70.0, color=(1.0, 0.85, 0.7), size=2.5)
    kit.common.aim(fill, (0, 0, 1.4))
    s.sky = world.sky_world("night", seconds)

    # views: camera = target + radius * (cos az, sin az) at `height`; the camera side is -y (az near -90)
    s.view("h1-low34", (0.15, -0.1, 1.55), 3.5, -58, 1.0)
    s.view("h1-calendar", (0.0, -0.02, 1.84), 0.75, -95, 1.88)
    s.view("h2-close", (0.3, -1.4, 1.5), 1.6, -92, 1.55)
    s.view("h3-top", (0.0, -0.55, 0.8), 0.18, -90, 2.35)
    s.view("h4-ots", (0.0, 0.0, 1.45), 3.2, -63, 1.75)
    s.view("h4-turn", (0.95, -1.3, 1.45), 2.5, -80, 1.5)
    s.view("card-air", (-0.75, -0.02, 1.2), 0.85, -96, 1.28)
    s.view("card-position", (0.0, -0.02, 1.2), 0.85, -84, 1.28)
    s.view("card-fear", (0.75, -0.02, 1.2), 0.85, -84, 1.28)
    s.floor_grid = 0

    def act_flip(t0, t1):
        fm = frames((t0 + t1) / 2)
        for ob, show_before in ((day_a, True), (day_b, False)):
            ob.hide_render = not show_before
            ob.keyframe_insert("hide_render", frame=1)
            ob.hide_render = show_before
            ob.keyframe_insert("hide_render", frame=fm)
        strip.rotation_euler = (0, 0, 0)
        strip.keyframe_insert("rotation_euler", frame=frames(t0))
        strip.rotation_euler = (math.pi, 0, 0)
        strip.keyframe_insert("rotation_euler", frame=frames(t1))
        arrow.location = (0, 0, 0)
        arrow.keyframe_insert("location", frame=frames(t0))
        arrow.location = (0.4, 0, 0)
        arrow.keyframe_insert("location", frame=frames(t1))

    def act_lay(t0, t1):
        for k, c in enumerate(desk_cards):
            f0 = frames(t0 + (t1 - t0) * k / 3)
            f1 = frames(t0 + (t1 - t0) * (k + 0.8) / 3)
            home = c.location.copy()
            c.location = home + Vector((0, -0.6, 0.12))
            c.keyframe_insert("location", frame=1)
            c.keyframe_insert("location", frame=f0)
            c.location = home
            c.keyframe_insert("location", frame=f1)

    def act_pin(t0, t1):
        word = stage if stage in hyp else None
        if not word:
            return
        g = hyp[word]
        for part in _tree(g):
            if part.name.startswith("board-strike"):
                continue
            _show_from(part, frames(t0), n)
        home = g.location.copy()
        g.location = home + Vector((0, -0.25, 0))
        g.keyframe_insert("location", frame=frames(t0))
        g.location = home
        g.keyframe_insert("location", frame=frames(t1))

    def act_pull(t0, t1):
        if stage != "h4":
            return
        for k, word in enumerate(order):
            g = hyp[word]
            f0 = frames(t0 + (t1 - t0) * k / 3)
            f1 = frames(t0 + (t1 - t0) * (k + 1) / 3)
            g.keyframe_insert("location", frame=f0)
            g.keyframe_insert("rotation_euler", frame=f0)
            g.location = g.location + Vector((0, -0.15, -1.1))
            g.rotation_euler = (math.radians(70), 0, math.radians(25 * (k - 1)))
            g.keyframe_insert("location", frame=f1)
            g.keyframe_insert("rotation_euler", frame=f1)

    if stage == "h1":
        s.action("flip", act_flip, at=0.55, span=0.5)
    if stage == "h3":
        s.action("lay", act_lay, at=0.1, span=2.4)
    if stage in ("air", "position", "fear"):
        s.action("pin", act_pin, at=0.15, span=0.35)
    if stage == "h4":
        s.action("pull", act_pull, at=0.45, span=1.8)
    return s


# ---------------------------------------------------------------------------
# The death ledger
# ---------------------------------------------------------------------------

def ledger(p, seconds):
    """The clinic's death register open on a desk. `columns`: clinics (I, II) | street (I, II, and a
    third column under a drawn street). `first` and `second` / `street` are how many crosses each
    column holds at the start; `adds` more appear in column I over the beat (action `tally`)."""
    from scenes import Set
    s = Set(seconds)
    s.lighting = "world"
    s.lens = 40.0
    n = s.frames
    cols = p.get("columns", "clinics")
    rnd = random.Random(int(p.get("seed", 3)))
    wood = kit.mat("ledger-desk", (0.13, 0.07, 0.035), roughness=0.55)
    page = kit.mat("ledger-page", (0.80, 0.74, 0.60), roughness=0.9)
    cover = kit.mat("ledger-cover", (0.22, 0.08, 0.05), roughness=0.7)
    ink = kit.mat("ledger-ink", (0.07, 0.05, 0.045), roughness=0.5)
    rule = kit.mat("ledger-rule", (0.48, 0.40, 0.30), roughness=0.9)
    kit.box("ledger-desk", (0, 0, 0.74), (2.2, 1.4, 0.06), wood, bevel=0.01)
    kit.box("ledger-cover", (0, 0, 0.778), (0.86, 0.6, 0.016), cover, bevel=0.004)
    for side in (-1, 1):
        kit.box(f"ledger-page{side:+d}", (side * 0.205, 0, 0.79), (0.4, 0.56, 0.01), page, bevel=0)
    # ruled columns on the right page; crosses only — nothing legible
    n_cols = 3 if cols == "street" else 2
    x0, x1 = 0.03, 0.39
    width = (x1 - x0) / n_cols
    rules = [placed((x0 + width * k, 0, 0.796), (0.002, 0.5, 0.001)) for k in range(1, n_cols)]
    rules += [placed((0.21, 0.2, 0.796), (0.36, 0.002, 0.001))]
    kit.boxes("ledger-rules", rules, rule)
    centres = [x0 + width * (k + 0.5) for k in range(n_cols)]
    heads = [kit.flat_text("ledger-head-I", "I", (centres[0], 0.235, 0.797), 0.03, ink, extrude=0.0003),
             kit.flat_text("ledger-head-II", "II", (centres[1], 0.235, 0.797), 0.03, ink, extrude=0.0003)]
    if cols == "street":     # a little street: two house fronts and the cobbles between
        cx = centres[2]
        kit.boxes("ledger-head-street", [placed((cx - 0.025, 0.24, 0.7966), (0.02, 0.025, 0.0006)),
                                         placed((cx + 0.025, 0.24, 0.7966), (0.02, 0.025, 0.0006)),
                                         placed((cx, 0.222, 0.7966), (0.07, 0.004, 0.0006))], ink)
    for h in heads:
        h["cut_ok"] = True

    def cross(name, x, y):
        a = placed((x, y, 0.7965), (0.022, 0.0025, 0.0006), math.radians(45))
        b = placed((x, y, 0.7965), (0.022, 0.0025, 0.0006), math.radians(-45))
        return kit.boxes(name, [a, b], ink)

    def slot(col, k):
        per_row = 3
        r, c = divmod(k, per_row)
        return centres[col] - 0.03 + 0.03 * c + 0.003 * rnd.random(), 0.17 - 0.032 * r

    counts = [int(p.get("first", 9)), int(p.get("second", 2))] + ([int(p.get("street", 0))] if cols == "street" else [])
    for col, cnt in enumerate(counts):
        for k in range(cnt):
            cross(f"ledger-x{col}-{k}", *slot(col, k))
    adds = int(p.get("adds", 1))
    added = [cross(f"ledger-add-{k}", *slot(0, counts[0] + k)) for k in range(adds)]
    for ob in added:
        ob.hide_render = True
    # the lamp, a quill, an inkwell
    kit.cylinders("ledger-inkwell", [((-0.62, 0.32, 0.8), 0.04, 0.07)], ink)
    quill = kit.boxes("ledger-quill", [placed((0.5, -0.12, 0.81), (0.32, 0.012, 0.004), math.radians(30))],
                      kit.mat("ledger-feather", (0.78, 0.74, 0.66), roughness=0.9))
    kit.ico("ledger-flame", (-0.7, -0.35, 1.0), 0.03, look.neon("ledger-flame", (1.0, 0.66, 0.3), 25.0), subdivisions=1)
    kit.cylinders("ledger-lamp", [((-0.7, -0.35, 0.86), 0.06, 0.14)], kit.mat("ledger-brass", (0.55, 0.40, 0.12),
                                                                             metallic=0.5, roughness=0.4))
    lamp = _light("ledger-lamp", (-0.6, -0.3, 1.1), 40.0, (1.0, 0.64, 0.32), size=0.15)
    for fr in range(1, n + 1, 5):
        lamp.data.energy = 40.0 * (0.85 + 0.3 * rnd.random())
        lamp.data.keyframe_insert("energy", frame=fr)
    fill = kit.common.add_area_light("ledger-fill", (0.6, -1.2, 1.8), 25.0, color=(0.7, 0.78, 1.0), size=1.5)
    kit.common.aim(fill, (0, 0, 0.8))
    s.sky = world.sky_world("night", seconds)
    s.pin("page", (0.21, 0.0, 0.8))
    s.pin("cross", (centres[0], 0.1, 0.8))
    s.view("ledger", (0.2, 0.05, 0.8), 0.75, -70, 1.32)
    s.view("ledger-street", (0.21, 0.04, 0.8), 0.9, -90, 1.45)
    s.floor_grid = 0

    def act_tally(t0, t1):
        for k, ob in enumerate(added):
            f = frames(t0 + (t1 - t0) * k / max(1, len(added)))
            _show_from(ob, f, n)
        quill.keyframe_insert("location", frame=max(1, frames(t0) - 4))
        quill.location = quill.location + Vector((-0.28, 0.2, 0.01))
        quill.keyframe_insert("location", frame=frames(t0))
        quill.location = quill.location + Vector((0.28, -0.2, -0.01))
        quill.keyframe_insert("location", frame=frames(t1))

    if adds:
        s.action("tally", act_tally, at=0.3, span=0.4)
    return s


# ---------------------------------------------------------------------------
# The wing: dissecting room -> corridor -> First Clinic ward
# ---------------------------------------------------------------------------

CORRIDOR = (world.WARD_L + 0.4, world.WARD_L + 12.0)   # x span of the corridor behind the far door
ANAT_X0 = CORRIDOR[1] + 7.0                          # the dissecting room's centre


def wing(p, seconds):
    """The morgue and the ward as one place. The camera starts on the covered body, doctors and
    students examine it, then walk out of the west door, down the corridor (past the explorer, a
    cast member) and in through the ward's far door to a mother's bed near the door end. `walk_from`
    and `walk_to` are fractions of the beat for the walk; the views follow the same path."""
    params = dict(p)
    params.update(through=True, bell=False)
    s = world.ward(params, seconds)
    n = s.frames
    seed = int(p.get("seed", 5))
    # the corridor: plaster walls, a flagstone floor, two small windows, one lamp
    plaster = kit.mat("wing-plaster", (0.58, 0.54, 0.46), roughness=0.95)
    flags = kit.mat("wing-floor", (0.30, 0.28, 0.25), roughness=0.9)
    x0, x1 = CORRIDOR
    mid = (x0 + x1) / 2
    length = x1 - x0
    kit.boxes("wing-corridor", [placed((mid, -1.3, 1.5), (length, 0.2, 3.0)), placed((mid, 1.3, 1.5), (length, 0.2, 3.0)),
                                placed((mid, 0, 3.05), (length, 2.8, 0.1))], plaster)
    kit.box("wing-floor", (mid, 0, -0.03), (length, 2.6, 0.06), flags, bevel=0)
    win = look.neon("wing-window", (0.62, 0.7, 0.88), 1.2)
    kit.boxes("wing-windows", [placed((x0 + length * f, 1.19, 1.9), (0.8, 0.04, 1.0)) for f in (0.3, 0.7)], win)
    lamp = _light("wing-lamp", (mid, 0, 2.6), 120.0, (1.0, 0.7, 0.42), size=0.3)
    kit.ico("wing-lampglass", (mid, 0, 2.7), 0.06, look.neon("wing-lampglass", (1.0, 0.7, 0.4), 10.0), subdivisions=1)
    # the dissecting room beyond, opening west onto the corridor; no Kolletschka: his is the body
    body = world.anatomy(s, n, seed, x0=ANAT_X0, use_assets=bool(p.get("assets", True)), people=False, west_door=True)
    # the men who examined him: a doctor and two students at the table, then the walk to the ward
    walk_from = float(p.get("walk_from", 0.22))
    walk_to = float(p.get("walk_to", 0.8))
    bed_x, bed_y = world.WARD_BEDS_X[0], -2.85
    path_end = [(bed_x + 1.05, bed_y + 0.25, 0), (bed_x + 1.45, bed_y - 0.45, 0), (bed_x - 0.95, bed_y + 0.3, 0)]
    starts = [(ANAT_X0 - 0.4, -0.5, 0), (ANAT_X0 + 0.6, -0.4, 0), (ANAT_X0 - 1.2, 1.4, 0)]
    for k, (who, a, b) in enumerate(zip(("doctor", "student", "student"), starts, path_end)):
        ob = characters.actor(f"wing-{who}-{k}", who, a, PERSON_H, pose="point" if k == 0 else "stand",
                              expression="worried")
        characters.blinks(ob, n, seed + 500 + k)
        lane = 0.35 * (k - 1)
        path = [a, (ANAT_X0 - 6.0, lane, 0), (x0 - 0.2, lane, 0), (world.WARD_L - 1.5, lane, 0),
                (bed_x + 2.0 + 0.5 * k, -1.2 + lane, 0), b]
        f0 = frames(walk_from * seconds + 0.35 * k)
        f1 = frames(walk_to * seconds + 0.2 * k)
        characters.walk(ob, path, f0, f1, steps_per_second=1.9)
        characters.key_cell(ob, f1 + 2, pose="stand", expression="neutral")
    # anchors along the path, and the views a held move travels through
    s.pin("body", (ANAT_X0, 0.6, 1.05), hold=[body])
    s.pin("corridor", (mid, 0, 1.5))
    s.pin("hands", (bed_x + 0.6, bed_y + 0.3, 1.0))
    s.view("wing-table", (ANAT_X0, 0.4, 1.0), 4.2, 180, 1.9)
    s.view("wing-door", (ANAT_X0 - 7.0, 0.0, 1.3), 4.0, 0, 1.6)
    s.view("wing-corridor", (mid - 1.0, 0.0, 1.35), 5.0, 180, 1.6)
    s.view("wing-ward-door", (world.WARD_L - 1.0, 0.0, 1.3), 6.0, 180, 1.65)
    s.view("wing-aisle", (bed_x + 3.0, -0.8, 1.2), 4.2, 160, 1.6)
    s.view("wing-ward-bed", (bed_x + 0.4, bed_y + 0.1, 0.95), 2.4, 125, 1.45)
    s.view("wing-hands", (bed_x + 0.6, bed_y + 0.3, 1.0), 1.1, 120, 1.25)
    return s


SCENES = {"board": board, "ledger": ledger, "wing": wing}
