"""Probe for the transform semantics of common.add_box.

add_box is used by every beat script, and it calls transform_apply. That operator's
`location` and `rotation` flags default to True, so `transform_apply(scale=True)` bakes
the world position into the mesh and leaves the object at the origin. Every caller that
sets rotation_euler afterwards then rotates that baked mesh about the world origin and
lands the part at twice the angle it asked for.

Run the same way as surfaces_probe.py:

    blender -b --factory-startup --python tools/blender/techniques/transforms_probe.py
"""
import json
import math
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import add_box  # noqa: E402


def measure():
    ang = 0.91
    radius = 2.0
    want = (radius * math.cos(ang), radius * math.sin(ang), 0.85)
    ob = add_box("Probe", want, (0.10, 0.55, 0.42))
    out = {
        "location": [round(c, 4) for c in ob.location],
        "wanted_location": [round(c, 4) for c in want],
        "scale": [round(c, 4) for c in ob.scale],
        "local_centre": None,
        "local_extent": [round(max(v.co[i] for v in ob.data.vertices)
                               - min(v.co[i] for v in ob.data.vertices), 4) for i in range(3)],
        "world_centre_after_rotate": None,
    }
    # The mesh's own centre, in local space: baked scale must not carry the offset.
    cx = sum(v.co.x for v in ob.data.vertices) / 8
    cy = sum(v.co.y for v in ob.data.vertices) / 8
    cz = sum(v.co.z for v in ob.data.vertices) / 8
    out["local_centre"] = [round(c, 4) for c in (cx, cy, cz)]

    ob.rotation_euler = (0.0, 0.0, ang)
    bpy.context.view_layer.update()
    wc = ob.matrix_world.translation
    out["world_centre_after_rotate"] = [round(c, 4) for c in wc]
    out["angle_after_rotate"] = round(math.atan2(wc.y, wc.x), 4)
    out["wanted_angle"] = round(ang, 4)
    return out


print("TRANSFORMS_JSON " + json.dumps(measure()))
