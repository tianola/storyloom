"""What happens in a living place, decided without Blender (so it can be tested): which windows
light and when, the lamplighter's round, who walks down the street and who stops to greet whom.
All seeded: the same beat renders the same evening every time."""
import random

WALKERS = ["townsman", "townswoman", "baker", "student", "townswoman", "townsman", "midwife", "doctor"]
WALK_SPEED = 1.25          # m/s, an unhurried walk


def window_schedule(keys, seconds, *, share=0.6, seed=0, start=0.05, end=0.6, already=0.25, later_off=0.12):
    """{key: (on_seconds, off_seconds or None)} for the lit share of `keys`. Some are lit from the
    first frame, the rest come on one after another between `start` and `end` (fractions of the
    beat); a few go dark again afterwards (a neighbour going to bed)."""
    rnd = random.Random(seed)
    keys = list(keys)
    lit = [k for k in keys if rnd.random() < share]
    out = {}
    for k in lit:
        if rnd.random() < already:
            on = 0.0
        else:
            on = (start + (end - start) * rnd.random()) * seconds
        off = None
        if on > 0 and rnd.random() < later_off:
            off = min(seconds, on + (0.25 + 0.5 * rnd.random()) * (seconds - on))
            if off - on < 1.0:
                off = None
        out[k] = (round(on, 2), round(off, 2) if off else None)
    return out


def window_lives(keys, seconds, seed, share=1 / 6, *, schedule=None, min_span=1.5):
    """Someone crossing a lit room: {key: [(t0, t1, direction)]} for about `share` of `keys`, one or
    two crossings each (direction -1 or +1 along the window). With `schedule`
    ({key: (on, off or None)}, from window_schedule) only lit keys can have a life and every
    crossing falls inside the time the window is lit. Seeded, so the same evening every time."""
    rnd = random.Random(seed * 7919 + 13)
    out = {}
    for k in sorted(keys):
        pick, n_legs, first = rnd.random(), rnd.choice((1, 1, 2)), rnd.choice((-1, 1))
        jit = [rnd.random() for _ in range(4)]
        if pick >= share:
            continue
        if schedule is not None:
            if k not in schedule:
                continue
            lo, hi = schedule[k][0], schedule[k][1] or seconds
        else:
            lo, hi = 0.0, seconds
        span = (hi - lo) / n_legs
        if span < min_span:
            n_legs, span = 1, hi - lo
        if span < min_span:
            continue
        legs = []
        for j in range(n_legs):
            dur = min(span * 0.8, 2.2 + 1.6 * jit[j])
            t0 = lo + j * span + (span - dur) * jit[j + 2]
            legs.append((round(t0, 2), round(min(hi, t0 + dur), 2), first * (-1) ** j))
        out[k] = legs
    return out


def lamplighter_order(xs, seconds, *, start=0.08, end=0.55):
    """Lighting time for each lamp, by x along the street (lamps at the same x light together)."""
    xs = sorted(xs)
    stops = sorted(set(xs))
    if not stops:
        return []
    step = (end - start) * seconds / max(1, len(stops) - 1)
    at = {x: round(start * seconds + i * step, 2) for i, x in enumerate(stops)}
    return [at[x] for x in xs]


def street_people(seconds, *, seed=0, count=8, x_range=(-55.0, 25.0), lanes=(-2.8, -1.4, 1.4, 2.8)):
    """Walkers on the main street (y between the kerbs at +-4): [{"who", "legs": [(path, t0, t1)],
    "greet": seconds or None}]. The first two walk towards each other on one lane, stop when they
    meet, greet (hat tipped), and walk on."""
    rnd = random.Random(seed)
    out = []
    lo, hi = x_range
    if count >= 2:
        y = lanes[1]
        meet_x = lo + (hi - lo) * (0.45 + 0.2 * rnd.random())
        tm = seconds * (0.35 + 0.25 * rnd.random())
        pause = 1.6
        for k, sign in enumerate((-1, 1)):
            far = meet_x + sign * WALK_SPEED * tm
            stand = meet_x + sign * 0.55
            after = stand - sign * WALK_SPEED * max(0.0, seconds - tm - pause)
            legs = [([(far, y, 0), (stand, y, 0)], 0.0, tm),
                    ([(stand, y, 0), (after, y, 0)], tm + pause, seconds)]
            out.append({"who": ("townsman", "baker")[k], "legs": legs, "greet": tm + 0.1})
    for k in range(max(0, count - 2)):
        y = lanes[rnd.randrange(len(lanes))] + (rnd.random() - 0.5) * 0.4
        x0 = lo + (hi - lo) * rnd.random()
        direction = rnd.choice((-1, 1))
        # most are already on their way when the shot opens; a few step in a little later
        t0 = seconds * 0.15 * rnd.random() if k % 3 == 2 else 0.0
        x1 = x0 + direction * WALK_SPEED * (seconds - t0)
        out.append({"who": WALKERS[(k + 2) % len(WALKERS)], "legs": [([(x0, y, 0), (x1, y, 0)], t0, seconds)],
                    "greet": None})
    return out


GROUP_PEOPLE = ["townswoman", "townsman", "baker", "townswoman", "student", "doctor", "midwife"]


def chatter(seconds, *, seed=0, people=2, turn=(0.9, 2.4)):
    """Who is talking when, in a group that stands and talks: [(t, k)], k the talker from t on.
    Turns pass to someone else each time, so a group of two goes back and forth."""
    rnd = random.Random(seed)
    out, t, k = [], rnd.random() * 0.8, rnd.randrange(people)
    while t < seconds:
        out.append((round(t, 2), k))
        t += turn[0] + (turn[1] - turn[0]) * rnd.random()
        k = (k + 1 + rnd.randrange(max(1, people - 1))) % people
    return out


def street_groups(seconds, *, seed=0, count=3, x_range=(-55.0, 25.0), sides=(-3.3, 3.3)):
    """People standing and talking by the house fronts (out of the walking lanes):
    [{"who": [keys], "at": [(x, y, 0)], "turns": chatter(...)}], groups of two or three."""
    rnd = random.Random(seed + 101)
    lo, hi = x_range
    out = []
    for g in range(count):
        size = 2 + (rnd.random() < 0.35)
        x = lo + (hi - lo) * (g + 0.2 + 0.6 * rnd.random()) / max(1, count)
        y = rnd.choice(sides)
        at = [(round(x + 0.75 * i, 2), y + (0.25 if i % 2 else 0.0) * (1 if y < 0 else -1), 0) for i in range(size)]
        who = [GROUP_PEOPLE[(g * 3 + i) % len(GROUP_PEOPLE)] for i in range(size)]
        out.append({"who": who, "at": at, "turns": chatter(seconds, seed=seed + g, people=size)})
    return out
