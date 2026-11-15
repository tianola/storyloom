"""Throwaway harness for python/test_lunar_ground.py. Prints LUNARGROUND_JSON.

It builds the real `beat_lunar_base` scene with the render stubbed out and then measures
that scene from the camera's point of view, because every number the test asserts is a
number about what the lens actually sees:

  * where the ground's silhouette crosses the frame (the horizon line),
  * how much that line curls between the middle of the frame and its sides (the "small
    ball" signature),
  * whether any column of the frame loses the ground before its bottom edge (the tell
    that a terrain patch ended before the true horizon),
  * how far that silhouette sits below the horizon predicted from the body's own tangent cone.
    A patch narrower than the cone shows a straight cut edge instead of a horizon, and no
    ray-cast sees it: a ray grazing the surface lands scores of units nearer than the boundary
    it is testing, so the predictor has to come from somewhere else.
  * how far apart the ground's vertices are in the band the camera is looking at, which
    floors the smallest crater the mesh can excavate.

Nothing here reads a constant off the beat. The radius, the centre and the camera height
are all recovered from the built mesh and the built camera, so a beat that quietly goes
back to standing a 40-unit sphere in for a plain fails instead of reporting the new
numbers.
"""
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))


def world_points(obj):
    """Every vertex of `obj` in world space, as numpy — mathutils refuses to multiply an
    ndarray, so the matrix is copied out first."""
    n = len(obj.data.vertices)
    co = np.empty(n * 3, dtype=np.float64)
    obj.data.vertices.foreach_get("co", co)
    hom = np.hstack([co.reshape(n, 3), np.ones((n, 1))])
    return (np.asarray(obj.matrix_world) @ hom.T)[:3, :].T, n


def ground_object(cam):
    """The surface the camera is standing on, found by firing a real ray straight down.

    Not "the biggest mesh": the starfield is a 400-unit shell, so it always wins a volume
    contest and the probe would report the backdrop's curvature as if it were the ground.
    """
    import mathutils
    deps = bpy.context.evaluated_depsgraph_get()
    ok, point, normal, index, obj, _ = bpy.context.scene.ray_cast(
        deps, cam.matrix_world.translation, mathutils.Vector((0.0, 0.0, -1.0)))
    if not ok:
        raise RuntimeError("nothing under the camera — the ground does not cover the shot")
    return obj, point


def camera_object():
    for obj in bpy.data.objects:
        if obj.type == "CAMERA":
            return obj
    raise RuntimeError("the beat built no camera")


def half_fov_deg(cam):
    """Vertical and horizontal half fields, honouring Blender's AUTO sensor fit."""
    scene = bpy.context.scene
    res_x, res_y = scene.render.resolution_x, scene.render.resolution_y
    lens, sensor = cam.data.lens, cam.data.sensor_width
    if res_x >= res_y:
        sensor_h = sensor * res_y / res_x
        sensor_w = sensor
    else:
        sensor_w = sensor * res_x / res_y
        sensor_h = sensor
    return (math.degrees(math.atan(sensor_h / 2.0 / lens)),
            math.degrees(math.atan(sensor_w / 2.0 / lens)))


def silhouette(ground, cam, cols=15):
    """Per-column elevation of the highest ground vertex inside the frame, measured in the
    camera's own coordinates, plus the columns that hold ground down to the frame's floor.

    Camera space, not world: the shot's defect is where the ground line sits *in the frame*,
    and the world elevation of that line depends on how the camera happens to be pitched. A
    horizon at 0 degrees world is mid-frame on a level shot and off the top of a tilted one.
    """
    pts, _ = world_points(ground)
    cam_pos = np.asarray(cam.matrix_world.translation)
    rel = pts - cam_pos

    # Rotate only, never re-translate. `rel` is already camera-centred, and adding the
    # inverse matrix's translation on top subtracts the camera position a second time, tilting
    # every elevation by however far the camera sits off the world origin — here 25 units,
    # 2 degrees. Camera space is x right, y up, -z forward.
    p = rel @ np.asarray(cam.matrix_world.to_3x3())
    ahead = p[:, 2] < 0.0
    half_v, half_h = half_fov_deg(cam)
    az = np.degrees(np.arctan2(p[:, 0], -p[:, 2]))
    el = np.degrees(np.arctan2(p[:, 1], -p[:, 2]))
    inframe = ahead & (np.abs(az) <= half_h) & (np.abs(el) <= half_v)
    az, el = az[inframe], el[inframe]

    edges = np.linspace(-half_h, half_h, cols + 1)
    top, bottom = [], []
    for i in range(cols):
        band = (az >= edges[i]) & (az < edges[i + 1])
        if not band.any():
            top.append(float("nan"))
            bottom.append(float("nan"))
            continue
        # The horizon is the highest ground in the column; the floor of the frame needs the
        # lowest, which only exists if the terrain reaches down past the frame's bottom edge.
        top.append(float(el[band].max()))
        bottom.append(float(el[band].min()))
    return np.array(top), np.array(bottom), (half_v, half_h), len(el)


def frame_ground(ground, cam, top):
    """Ray-cast the rendered surface down the frame in every column, and report what is hit.

    Vertices cannot answer the coverage question. The mesh samples the ground every third of
    a unit, so a column can hold terrain right down to the last pixel row and still have its
    lowest *vertex* two degrees above the frame's bottom edge — on the cap the first version
    of this measurement reported ten empty columns out of fifteen on a plain that rendered as
    dirt. A ray is the surface's own test.

    Three things can come back: the ground itself, or any other dirt in front of it (a rock, a
    rut, a painted crater floor) — the frame is holding ground; the starfield shell, or nothing
    at all — space is showing where terrain should be; or the patch's own edge, which is a
    straight step inside the shot rather than a hole. The distance of the hit from the patch
    centre is returned for the report only. It cannot decide the third case on its own, because
    a ray just under the horizon lands scores of units nearer than the boundary it is testing —
    `predicted_horizon` is what settles that one.
    """
    import mathutils
    half_v, half_h = half_fov_deg(cam)
    deps = bpy.context.evaluated_depsgraph_get()
    origin = mathutils.Vector(cam.matrix_world.translation)
    rot = cam.matrix_world.to_3x3()
    cols = len(top)
    edges = np.linspace(-half_h, half_h, cols + 1)
    centre = np.array([ground.location.x, ground.location.y])

    def cast(az_rad, el_deg):
        """(status, chebyshev distance from the patch centre) for the ray through camera-space
        (az, el). Inverse of the silhouette's own az/el: camera space is x right, y up, -z
        forward."""
        d = mathutils.Vector((math.tan(az_rad), math.tan(math.radians(el_deg)), -1.0))
        ok, point, _, _, hit, _ = bpy.context.scene.ray_cast(deps, origin, rot @ d.normalized())
        if not ok:
            return "space", float("nan")
        if hit == ground or not hit.name.lower().startswith("star"):
            return "ground", float(np.max(np.abs(np.array([point.x, point.y]) - centre)))
        return "space", float("nan")

    bottom, line, reach = [], [], []
    for i in range(cols):
        az = math.radians((edges[i] + edges[i + 1]) / 2.0)
        # The bottom edge is where a patch that stops short shows space under the terrain.
        status, dist = cast(az, -half_v + 0.15)
        bottom.append(0.0 if status == "space" else 1.0)
        # And below the ground line, where a patch narrower than the horizon ring shows space
        # *above* the terrain — or, if the patch ends inside the shot, its own straight edge
        # instead of the horizon's curve. A tenth of a degree would be enough for a plain, but
        # the crater rims stand 0.2 above the surface and the top of the silhouette is a rim,
        # not the horizon, so this cast has to clear them.
        if np.isfinite(top[i]):
            status, dist = cast(az, top[i] - 0.15)
            line.append(0.0 if status == "space" else 1.0)
            if np.isfinite(dist):
                reach.append(dist)
        else:
            line.append(float("nan"))
    return bottom, line, (max(reach) if reach else float("nan"))


def body_sphere(ground):
    """The sphere the patch was projected onto, recovered from the built mesh.

    A median rather than the radius the beat passed in, because the crater field displaces
    vertices: the predictor is derived from what exists, so a beat that goes back to a
    40-unit ball predicts a 40-unit ball's horizon.
    """
    pts, _ = world_points(ground)
    centre = np.asarray(ground.location)
    return centre, float(np.median(np.linalg.norm(pts - centre, axis=1)))


def predicted_horizon(cam, centre, radius, cols):
    """Elevation, in camera space, at which the ground body stops covering the sky in each of
    `cols` columns spread evenly across the frame's width.

    This is the independent half of the coverage test. The ray-cast boundary cannot do it on
    its own: near the horizon the surface and the line of sight are almost parallel, so a ray a
    fraction of a degree under the silhouette lands scores of units nearer, and a shrunken
    patch hid behind that effect — the mutation that quartered `half=` reported a boundary well
    inside its own edge and the assertion passed on a scene that visibly fails. The tangent
    cone says plainly where the horizon has to be; the mesh's silhouette says what the shot
    actually shows; a silhouette *under* the cone means the patch ran out before the horizon.

    A ray hits the body iff the angle between it and the direction to the centre is inside
    `asin(radius / distance)`. That angle falls monotonically as the ray is depressed, so each
    column has exactly one crossing and a bisection finds it.
    """
    inv = np.asarray(cam.matrix_world.inverted())
    w = inv[:3, :3] @ (centre - np.asarray(cam.matrix_world.translation))
    distance = float(np.linalg.norm(w))
    if radius >= distance:
        raise RuntimeError("the camera is inside the ground body — there is no horizon to find")
    w_hat, cone = w / distance, math.asin(radius / distance)

    # Same column edges as `silhouette`, so the two arrays compare entry for entry.
    half_h = half_fov_deg(cam)[1]
    edges = np.linspace(-half_h, half_h, cols + 1)
    tan_az = np.tan(np.radians((edges[:-1] + edges[1:]) / 2.0))
    lo, hi = np.full(cols, -89.0), np.full(cols, 89.0)
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        d = np.column_stack([tan_az, np.tan(np.radians(mid)), -np.ones(cols)])
        cos_theta = (d @ w_hat) / np.linalg.norm(d, axis=1)
        inside = np.arccos(np.clip(cos_theta, -1.0, 1.0)) < cone
        lo, hi = np.where(inside, mid, lo), np.where(inside, hi, mid)
    return 0.5 * (lo + hi), {"distance": distance, "cone_deg": math.degrees(cone),
                             "axis_az_deg": math.degrees(math.atan2(w_hat[0], -w_hat[2])),
                             "axis_el_deg": math.degrees(math.atan2(w_hat[1], -w_hat[2]))}


def near_band_spacing(ground, at, band_r=8.0):
    """Vertex spacing, and the roughness left after a smooth surface is fitted out, over the
    disc of radius `band_r` around the point the camera stands over.

    The band is deliberately tight, and it is measured in 3D rather than horizontally. A
    horizontal disc takes in the *far* side of a small body as well — on the radius-42 ball
    this beat shipped with, the lower hemisphere sat 73 units under the camera and its
    vertices fell inside the same x,y circle, so the fit reported the body's own thickness as
    surface roughness. Spacing comes from the band's projected area, which only equals the
    surface area when the surface is nearly flat inside it.
    """
    pts, _ = world_points(ground)
    centre = np.asarray([at.x, at.y, at.z])
    r = np.linalg.norm(pts - centre, axis=1)
    inside = r <= band_r
    count = int(inside.sum())
    if count < 2:
        return float("inf"), count, float("inf")
    area = math.pi * band_r * band_r
    spacing = math.sqrt(area / count)
    # Relief: how far the band's vertices sit from the smoothest quartic that fits them. A
    # quartic absorbs the body's own curvature to fourth order, so what is left is bowls and
    # rims — on a plain that is only curved the residual is ~1e-6.
    x, y, z = pts[inside, 0] - centre[0], pts[inside, 1] - centre[1], pts[inside, 2] - centre[2]
    design = [np.ones_like(x), x, y, x * x, y * y, x * y]
    for order in (3, 4):
        for i in range(order + 1):
            design.append(x ** i * y ** (order - i))
    design = np.column_stack(design)
    coef, *_ = np.linalg.lstsq(design, z, rcond=None)
    resid = np.abs(design @ coef - z)
    p99 = float(np.percentile(resid, 99.0))
    return spacing, count, p99


def main() -> int:
    import artemis_beats as AB

    AB.SHOT_FRAMES = AB._shot_frames_for("beat_lunar_base")
    rendered = []
    AB.render_animation = lambda out, name: rendered.append(name)

    out = ROOT / "work" / "probe-lunar-ground"
    out.mkdir(parents=True, exist_ok=True)
    AB.beat_lunar_base(out)

    cam = camera_object()
    bpy.context.scene.frame_set(max(1, AB.SHOT_FRAMES // 2))
    bpy.context.view_layer.update()
    ground, hit = ground_object(cam)
    if ground.name.lower().startswith("star"):
        raise RuntimeError("the surface under the camera is the starfield, not terrain")
    spacing, band_count, relief_p99 = near_band_spacing(ground, hit)
    centre_of_body, radius = body_sphere(ground)

    # The dolly moves the camera 4 units forward and 2.5 down while it runs, and how far the
    # visible ground reaches depends on how high it is standing. A patch sized for the middle
    # of the shot can be too small at its ends, so measure every pose, not one.
    poses = sorted({1, AB.SHOT_FRAMES // 4, AB.SHOT_FRAMES // 2,
                    (3 * AB.SHOT_FRAMES) // 4, AB.SHOT_FRAMES})
    columns = []
    horizon, heights, reach, shortfall = [], [], [], []
    bottom_misses = line_misses = 0
    worst_curl, best_sky = [], []
    for frame in poses:
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        top, _, (half_v, half_h), visible = silhouette(ground, cam)
        centre = len(top) // 2
        # How much the line falls away toward the sides of the frame. A plain keeps it level;
        # a small ball is a circle, and a circle inside a rectangle is the shot that says
        # "diorama".
        worst_curl.append(float(np.nanmax(top) - np.nanmin(top)))
        horizon.append(float(top[centre]))
        # The sky band is the part of the frame above the horizon line, as a fraction of height.
        best_sky.append((half_v - top[centre]) / (2 * half_v))
        # How far the shown ground line falls below the one the body's own tangent cone
        # demands. Zero means the patch reaches past the horizon; degrees mean its cut edge is
        # what the frame is carrying.
        cone_el, why = predicted_horizon(cam, centre_of_body, radius, len(top))
        short = cone_el - top
        shortfall.append(float(np.nanmax(short)))
        # A fresh downward cast per pose: it also proves the patch is under the camera at
        # every one of them, which is the same coverage question from the other side.
        _, surface_at = ground_object(cam)
        heights.append(float(cam.matrix_world.translation.z - surface_at.z))
        bottom, line, this_reach = frame_ground(ground, cam, top)
        bottom_misses += int(np.sum(np.array(bottom) < 0.5))
        line_misses += int(np.sum(np.array(line) < 0.5))
        reach.append(this_reach)
        columns.append({"frame": frame, "horizon": round(float(top[centre]), 3),
                        "shortfall": round(shortfall[-1], 3),
                        "shown": [round(float(v), 2) for v in top],
                        "cone": [round(float(v), 2) for v in cone_el],
                        "cone_info": {k: round(v, 3) for k, v in why.items()},
                        "bottom_misses": int(np.sum(np.array(bottom) < 0.5)),
                        "line_misses": int(np.sum(np.array(line) < 0.5)),
                        "reach": round(this_reach, 1) if np.isfinite(this_reach) else None,
                        "visible_ground_points": visible})

    starfield = max((o.dimensions.x for o in bpy.data.objects
                     if o.name.lower().startswith("star")), default=0.0) / 2.0
    pts, n = world_points(ground)
    outside_shell = int(np.sum(np.linalg.norm(pts, axis=1) > starfield)) if starfield else 0
    cap_half = float(np.max(np.abs(pts[:, 0] - ground.location.x)))

    report = {
        "poses": columns,
        "ground": ground.name,
        "camera_height": round(max(heights), 3),
        "hit_xy": [round(float(hit.x), 1), round(float(hit.y), 1)],
        "ground_vertices": n,
        "ground_faces": len(ground.data.polygons),
        "cap_half": round(cap_half, 1),
        "body_radius": round(radius, 1),
        "horizon_el_deg": round(max(horizon), 3),
        "horizon_curl_deg": round(max(worst_curl), 3),
        "horizon_shortfall_deg": round(max(shortfall), 3),
        "sky_band_frac": round(min(best_sky), 4),
        "frame_bottom_misses": bottom_misses,
        "horizon_misses": line_misses,
        "ground_reach": round(max(reach), 1) if reach else None,
        "near_band_spacing": round(float(spacing), 4),
        "near_band_vertices": band_count,
        "relief_p99": round(float(relief_p99), 4),
        "outside_starfield": outside_shell,
        "starfield_radius": round(float(starfield), 2),
        "half_fov_v": round(half_v, 3),
        "half_fov_h": round(half_h, 3),
    }
    print("LUNARGROUND_JSON " + json.dumps(report), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
