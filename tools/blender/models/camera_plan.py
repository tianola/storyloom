"""Camera movement rules that need no Blender, so they can be unit-tested.

The numbers come from .claude/skills/story-film/references/staging.md section 1: a drift that
ignores the length of the shot is a bug, a move eases in and out and holds before and after, and no
pan crosses scenery faster than one frame width per 7 s.
"""
import hashlib
import math

MOVES = ("drift", "lock", "push", "pull")
LOCK_UNDER = 2.5            # seconds: a shot shorter than this is a locked frame
DRIFT_AZIMUTH_RATE = 0.6    # degrees per second, capped per shot at DRIFT_AZIMUTH_CAP
DRIFT_AZIMUTH_CAP = 4.0
DRIFT_PUSH_RATE = 0.01      # fraction of the distance per second, capped at DRIFT_PUSH_CAP
DRIFT_PUSH_CAP = 0.08
PUSH_RATE = 0.02            # a deliberate push or pull: 2%/s, so 8% at 4 s, 15% at 7.5 s and longer
PUSH_CAP = 0.15
CLOSE_AZIMUTH_OFFSET = 5.0  # a close-up keeps the angle of the shot before, at most this far off
HOLD_START = (0.6, 0.10)    # (seconds, share of the shot): the camera stands still before a travel
HOLD_END = (1.2, 0.15)      # ... and after it, so the move lands before the cut
MAX_PAN = 1.0 / 7.0         # frame widths per second


def check_move(move, where="shot"):
    """Raise a ValueError naming the allowed values when `move` is not one of them (None is fine)."""
    if move is not None and move not in MOVES:
        raise ValueError(f"{where}: move must be one of {list(MOVES)}, got {move!r}")
    return move


def stable_sign(key):
    """+1 or -1 from a stable hash of `key` (not Python's salted hash(), so a rebuild repeats it):
    every shot of a beat drifts the same way instead of swinging back and forth cut to cut."""
    return 1.0 if hashlib.md5(str(key).encode("utf-8")).digest()[0] % 2 == 0 else -1.0


def drift_amount(duration, move=None):
    """(azimuth degrees, radius factor) the camera moves over a held shot of `duration` seconds.

    Positive azimuth is to be multiplied by the beat's sign by the caller. A shot under LOCK_UNDER
    seconds does not move at all, whatever it asks for: a 1.2 s insert that jerks 7 degrees reads as
    a mistake. "drift" breathes at <= 0.6 deg/s and 1%/s (capped 4 deg and 8%); "push" and "pull"
    are the deliberate moves of 2%/s up to 15%."""
    move = check_move(move) or "drift"
    if move == "lock" or duration < LOCK_UNDER:
        return 0.0, 1.0
    if move == "drift":
        return (min(DRIFT_AZIMUTH_RATE * duration, DRIFT_AZIMUTH_CAP),
                1.0 - min(DRIFT_PUSH_RATE * duration, DRIFT_PUSH_CAP))
    share = min(PUSH_RATE * duration, PUSH_CAP)
    return 0.0, (1.0 - share) if move == "push" else (1.0 + share)


def travel_keys(duration, moving_keys=9):
    """[(time fraction, progress)] for a travel shot: still for the first min(0.6 s, 10%) and the
    last min(1.2 s, 15%), eased (smoothstep) in between. The first two and the last two keys have
    equal progress, so the camera holds there; with linear keys between them that is a true hold."""
    a = min(HOLD_START[0] / duration, HOLD_START[1]) if duration > 0 else 0.0
    b = min(HOLD_END[0] / duration, HOLD_END[1]) if duration > 0 else 0.0
    keys = [(0.0, 0.0)]
    for k in range(moving_keys):
        x = k / (moving_keys - 1)
        keys.append((a + (1.0 - a - b) * x, x * x * (3 - 2 * x)))
    keys.append((1.0, 1.0))
    return keys


def orbit_point(target, radius, azimuth_deg, height):
    """Mirror of kit._orbit_point on plain tuples."""
    a = math.radians(azimuth_deg)
    return (target[0] + radius * math.cos(a), target[1] + radius * math.sin(a), height)


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _norm(a):
    return math.sqrt(_dot(a, a))


def camera_speed(pos0, target0, pos1, target1, duration, lens=50.0, sensor=36.0):
    """How fast the picture pans between two camera states over `duration` seconds.

    -> {"angular_deg_s": turn of the view direction per second,
        "pan_frames_s": the larger of that turn and the camera's sideways shift at the target's
                        distance, both in frame widths per second (horizontal FOV from `lens`)}.
    Zero duration gives an infinite speed unless nothing moves."""
    fov = 2 * math.atan((sensor / 2) / lens)
    d0, d1 = _sub(target0, pos0), _sub(target1, pos1)
    n0, n1 = _norm(d0), _norm(d1)
    if n0 == 0 or n1 == 0:
        return {"angular_deg_s": 0.0, "pan_frames_s": 0.0}
    cos = max(-1.0, min(1.0, _dot(d0, d1) / (n0 * n1)))
    turn = math.acos(cos)
    # sideways shift of the camera across the mean view direction, relative to the frame width there
    mean = tuple(x / n0 + y / n1 for x, y in zip(d0, d1))
    m = _norm(mean) or 1.0
    mean = tuple(x / m for x in mean)
    shift = _sub(pos1, pos0)
    along = _dot(shift, mean)
    lateral = _norm(tuple(s - along * u for s, u in zip(shift, mean)))
    width = 2 * ((n0 + n1) / 2) * math.tan(fov / 2)
    frames = max(turn / fov, lateral / width)
    if duration <= 0:
        return {"angular_deg_s": 0.0 if turn == 0 else math.inf, "pan_frames_s": 0.0 if frames == 0 else math.inf}
    return {"angular_deg_s": math.degrees(turn) / duration, "pan_frames_s": frames / duration}


def shot_speed(entry, duration, lens=50.0):
    """camera_speed of one `look.shoot` shot dict over its moving part (a travel holds at both ends,
    so only the time between the holds counts)."""
    t0 = (entry["target"])
    t1 = entry.get("target_to", entry["target"])
    r, az, h = entry["radius"], entry["azimuth"], entry["height"]
    if "target_to" in entry:
        hold = min(HOLD_START[0], HOLD_START[1] * duration) + min(HOLD_END[0], HOLD_END[1] * duration)
        duration = max(duration - hold, 0.1)
    p0, p1 = orbit_point(t0, r[0], az[0], h[0]), orbit_point(t1, r[1], az[1], h[1])
    return camera_speed(p0, t0, p1, t1, duration, lens)
