"""Camera-relative key placement, shared by every beat that has to read as a photograph.

Pure arithmetic on purpose: no bpy import, so the geometry is unit-testable without
starting Blender, and the rule it encodes can be asserted against the whole beat list.

The rule is worth spelling out because eighteen of nineteen Artemis II beats broke it.
A sun lamp renders its direction only (see common.add_sun_light), so a call site is free
to pick an azimuth that nobody checks against the camera. Every `(5, -10, 15)`-style
location in this project was chosen to look good as a *vector*, and the camera in all of
those beats looks along roughly the same horizontal direction the light travels in. Front
light is not a softer look, it is a shadowless one: each shadow falls behind the object
that cast it, so a 5 cm rock and a 30 cm rock return the same grey and no amount of
subdivided terrain survives the shot. Raking light is the only thing that makes relief
legible, and raking means perpendicular to the view axis, which is what `key_location`
computes instead of trusting the eye.
"""
import math

# Past twenty degrees toward the lens the key is back inside the camera's quadrant and the
# shadows start hiding behind their casters again. Rim bias (positive yaw) is unbounded
# here because a back-lit beat is a deliberate choice, not an accident.
MAX_FRONT_YAW = -20.0

# A habitat throws a shadow several times its own height at this elevation, which is what
# the Apollo site surveys measure; higher suns flatten the ground no matter the azimuth.
LUNAR_KEY_ELEVATION = 17.0


def key_location(cam_location, cam_target, elevation=LUNAR_KEY_ELEVATION, side=1.0,
                 yaw=0.0, distance=14.0):
    """World position for a sun that grazes the frame instead of lighting it from the lens.

    `side` picks frame-right (+1) or frame-left (-1); choose it so specular panels catch a
    glint rather than the mirror reflection of the whole disc into the lens. `yaw` leans the
    key off exactly-perpendicular: positive toward the far side of the subject for rim.
    `distance` is meaningless to a sun and exists only so the returned vector stays honest
    about its own elevation.
    """
    if yaw < MAX_FRONT_YAW:
        raise ValueError(
            f"yaw {yaw:+.1f} deg puts the key {abs(yaw):.1f} deg inside the camera's own "
            "quadrant, which is the flat shadowless look this helper exists to prevent")
    vx = cam_target[0] - cam_location[0]
    vy = cam_target[1] - cam_location[1]
    view = math.hypot(vx, vy)
    if view < 1e-6:
        # Looking straight down: every azimuth is perpendicular, so pick one and stay stable.
        vx, vy = 0.0, 1.0
    else:
        vx, vy = vx / view, vy / view
    # Frame-right is the view axis turned a quarter turn, and it is perpendicular by
    # construction, which is the entire point.
    rx, ry = vy, -vx
    lean = math.radians(yaw)
    sx = side * rx * math.cos(lean) + vx * math.sin(lean)
    sy = side * ry * math.cos(lean) + vy * math.sin(lean)
    norm = math.hypot(sx, sy)
    if norm < 1e-9:
        raise ValueError("key direction collapsed to zero — check cam_location and cam_target")
    sx, sy = sx / norm, sy / norm
    elev = math.radians(elevation)
    return (sx * distance * math.cos(elev),
            sy * distance * math.cos(elev),
            distance * math.sin(elev))


def front_light(cam_location, cam_target, sun_location):
    """How much the key travels the way the lens looks: +1 shadowless, 0 raking, -1 rim."""
    vx = cam_target[0] - cam_location[0]
    vy = cam_target[1] - cam_location[1]
    view = math.hypot(vx, vy)
    travel_x, travel_y = -sun_location[0], -sun_location[1]
    travel = math.hypot(travel_x, travel_y)
    if view < 1e-9 or travel < 1e-9:
        return 0.0
    return (vx / view) * (travel_x / travel) + (vy / view) * (travel_y / travel)
