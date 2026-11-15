"""Reusable people, places and diagrams-in-space. Same contract as hardware.py: each
builder returns the pieces a beat may want to move.
"""
import math

import kit
from kit import placed


def figure(name, loc, facing=0.0, jacket=None, seated=False, scale=1.0):
    """A low-poly person: faceted head, tapered torso, arms and legs. Deliberately not
    a likeness of anyone: the narration names people, the picture only stands for them."""
    jacket = jacket or kit.slate()
    skin = kit.mat("kit-skin", (0.62, 0.45, 0.34), roughness=0.75)
    trousers = kit.mat("kit-trousers", (0.05, 0.055, 0.065), roughness=0.8)
    hip = 0.55 if seated else 0.95
    parts = []
    torso = kit.cyl(f"{name}-torso", (0, 0, hip + 0.36), 0.20, 0.72, jacket, verts=8, radius2=0.27)
    torso.scale = (1.0, 0.62, 1.0)
    neck = kit.cyl(f"{name}-neck", (0, 0, hip + 0.76), 0.07, 0.10, skin, verts=8)
    head = kit.ico(f"{name}-head", (0, 0, hip + 0.95), 0.155, skin, subdivisions=1)
    head.scale = (0.92, 1.0, 1.12)
    hair = kit.ico(f"{name}-hair", (0, 0.015, hip + 1.01), 0.158, kit.mid(), subdivisions=1)
    hair.scale = (0.95, 1.0, 0.80)
    parts += [torso, neck, head, hair]
    for sx in (-1, 1):
        arm = kit.cyl(f"{name}-arm{sx}", (sx * 0.31, -0.10 if seated else 0.0, hip + 0.40), 0.065, 0.62, jacket,
                      verts=6, radius2=0.08)
        arm.rotation_euler = (math.radians(50 if seated else 6), math.radians(-8 * sx), 0)
        hand = kit.ico(f"{name}-hand{sx}", (sx * 0.34, -0.36 if seated else -0.03, hip + (0.20 if seated else 0.07)),
                       0.06, skin, subdivisions=1)
        if seated:
            thigh = kit.cyl(f"{name}-thigh{sx}", (sx * 0.12, -0.24, hip - 0.02), 0.09, 0.52, trousers, verts=6,
                            rot=(math.radians(90), 0, 0))
            shin = kit.cyl(f"{name}-shin{sx}", (sx * 0.12, -0.48, hip * 0.5 - 0.02), 0.075, hip, trousers, verts=6)
            parts += [thigh, shin]
        else:
            leg = kit.cyl(f"{name}-leg{sx}", (sx * 0.12, 0, hip / 2), 0.075, hip, trousers, verts=6, radius2=0.10)
            parts.append(leg)
        shoe = kit.box(f"{name}-shoe{sx}", (sx * 0.12, -0.54 if seated else -0.06, 0.04), (0.12, 0.28, 0.08),
                       kit.epoxy(), bevel=0.02)
        parts += [arm, hand, shoe]
    # jacket collar: two lapel wedges
    for sx in (-1, 1):
        lapel = kit.box(f"{name}-lapel{sx}", (sx * 0.09, -0.155, hip + 0.60), (0.11, 0.03, 0.26), jacket, bevel=0.01)
        lapel.rotation_euler = (math.radians(-8), math.radians(18 * sx), 0)
        parts.append(lapel)
    g = kit.group(name, parts)
    g.location = loc
    g.rotation_euler = (0, 0, facing)
    g.scale = (scale, scale, scale)
    return g


def diner_booth(name="booth"):
    """A diner booth seen from the aisle: two benches, a table, a window, a hanging lamp.
    Returns the table-top height and the group for the lamp glow."""
    seat = kit.mat("kit-vinyl", (0.33, 0.07, 0.05), roughness=0.6)
    for sy, tag in ((-1, "a"), (1, "b")):
        y = sy * 1.25
        kit.box(f"{name}-seat-{tag}", (0, y, 0.40), (3.0, 0.75, 0.26), seat, bevel=0.08)
        kit.box(f"{name}-plinth-{tag}", (0, y, 0.14), (2.9, 0.65, 0.28), kit.slate(), bevel=0.01)
        back = kit.box(f"{name}-back-{tag}", (0, y + sy * 0.42, 0.95), (3.0, 0.24, 1.25), seat, bevel=0.10)
        kit.boxes(f"{name}-tufts-{tag}", [placed((-1.2 + k * 0.6, y + sy * 0.29, 1.05), (0.03, 0.02, 0.85))
                                           for k in range(5)], kit.slate())
        del back
    kit.box(f"{name}-table", (0, 0, 0.80), (2.6, 1.15, 0.07), kit.base(), bevel=0.03)
    kit.box(f"{name}-table-edge", (0, 0, 0.775), (2.64, 1.19, 0.035), kit.steel(), bevel=0.01)
    kit.cyl(f"{name}-pedestal", (0, 0, 0.40), 0.09, 0.76, kit.steel(), verts=20)
    kit.cyl(f"{name}-foot", (0, 0, 0.03), 0.42, 0.06, kit.steel(), verts=32)
    # wall with a window band behind the booth
    kit.box(f"{name}-wall-low", (1.75, 0, 0.55), (0.14, 4.6, 1.1), kit.slate(), bevel=0.01)
    kit.box(f"{name}-wall-top", (1.75, 0, 2.75), (0.14, 4.6, 0.5), kit.slate(), bevel=0.01)
    kit.boxes(f"{name}-mullions", [placed((1.75, y, 1.8), (0.10, 0.07, 1.4)) for y in (-2.25, -0.75, 0.75, 2.25)],
              kit.steel())
    kit.box(f"{name}-night", (2.6, 0, 1.8), (0.05, 6.0, 2.2), kit.mat("kit-night", (0.02, 0.03, 0.06), roughness=0.9),
            bevel=0)
    # on the table: three mugs, plates, a napkin with a sketch on it
    for k, (x, y) in enumerate(((-0.8, -0.3), (0.55, 0.32), (-0.75, 0.3))):
        kit.cyl(f"{name}-mug{k}", (x, y, 0.895), 0.065, 0.12, kit.base(), verts=20)
        kit.cyl(f"{name}-coffee{k}", (x, y, 0.953), 0.055, 0.006, kit.mat("kit-coffee", (0.05, 0.03, 0.02)), verts=20)
    kit.cyl(f"{name}-plate", (0.75, -0.28, 0.842), 0.17, 0.014, kit.base(), verts=32)
    napkin = kit.box(f"{name}-napkin", (0.0, -0.05, 0.838), (0.50, 0.36, 0.006), kit.base(), bevel=0)
    sketch = kit.glow(f"{name}-sketch-ink", 0.0)
    marks = [placed((0.0, -0.05, 0.843), (0.20, 0.20, 0.004))]
    marks += [placed((0.0 + sx * 0.14, -0.05 + (k - 2) * 0.04, 0.843), (0.07, 0.012, 0.004))
              for sx in (-1, 1) for k in range(5)]
    marks += [placed((0.0 + (k - 2) * 0.04, -0.05 + sy * 0.14, 0.843), (0.012, 0.07, 0.004))
              for sy in (-1, 1) for k in range(5)]
    kit.boxes(f"{name}-sketch", marks, sketch)
    # pendant lamp
    kit.cyl(f"{name}-cord", (0, 0, 2.75), 0.012, 1.3, kit.epoxy(), verts=6)
    kit.cyl(f"{name}-shade", (0, 0, 2.05), 0.42, 0.26, kit.slate(), verts=32, radius2=0.10)
    bulb = kit.glow(f"{name}-bulb", 9.0, color=(1.0, 0.78, 0.50))
    kit.cyl(f"{name}-bulb", (0, 0, 1.93), 0.30, 0.02, bulb, verts=32)
    del napkin
    return {"sketch_ink": sketch, "table_top": 0.84, "napkin_xyz": (0.0, -0.05, 0.85)}


def campus_building(name="hq"):
    """A low, wide technology campus building: a triangular plan with rounded corners,
    a glazed band, and a roof made of triangular skylight panels. Returns roof panels."""
    R = 7.0
    roof_z = 2.3
    def tri(r):
        return kit.rounded_polygon([(r * math.cos(math.radians(a)), r * math.sin(math.radians(a)))
                                    for a in (90, 210, 330)], 1.3)

    kit.prism(f"{name}-body", tri(R), 0.0, roof_z, kit.base())
    kit.prism(f"{name}-glass", tri(R * 1.012), roof_z * 0.20, roof_z * 0.74,
              kit.mat("kit-glazing", (0.05, 0.08, 0.11), metallic=0.3, roughness=0.42))
    kit.prism(f"{name}-roof", tri(R * 1.07), roof_z, roof_z + 0.14, kit.base())
    # triangular skylights tiled across the roof
    import bmesh
    import bpy
    from mathutils import Matrix
    bm_a, bm_b = bmesh.new(), bmesh.new()
    side = 0.95
    hgt = side * math.sqrt(3) / 2
    verts3 = [(R * math.cos(math.radians(a)), R * math.sin(math.radians(a))) for a in (90, 210, 330)]

    def inside(px, py, margin=0.78):
        for i in range(3):
            ax, ay = verts3[i]
            bx, by = verts3[(i + 1) % 3]
            cross = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
            if cross < margin * math.hypot(bx - ax, by - ay):
                return False
        return True

    count = 0
    for row in range(-12, 13):
        for col in range(-24, 25):
            up = (row + col) % 2 == 0
            cx = col * side / 2
            cy = row * hgt + (hgt / 3 if up else 2 * hgt / 3) - hgt / 2
            if not inside(cx, cy):
                continue
            m = (Matrix.Translation((cx, cy, roof_z + 0.17))
                 @ Matrix.Rotation(math.radians(90 if up else 270), 4, "Z"))
            bmesh.ops.create_cone(bm_a if (row * 7 + col * 3) % 5 else bm_b, cap_ends=True, segments=3,
                                  radius1=side * 0.50, radius2=side * 0.50, depth=0.06, matrix=m)
            count += 1
    panels = []
    for bm, material, tag in ((bm_a, kit.mid(), "a"), (bm_b, kit.accent(), "b")):
        me = bpy.data.meshes.new(f"{name}-skylights-{tag}")
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(me.name, me)
        bpy.context.scene.collection.objects.link(ob)
        ob.data.materials.append(material)
        panels.append(ob)
    # grounds: paths and trees
    kit.boxes(f"{name}-paths", [placed((0, -R * 0.5 - 4.0, 0.012), (1.4, 8.0, 0.02)),
                                placed((-7.5, -1.5, 0.012), (7.0, 1.2, 0.02), 0.5),
                                placed((7.5, -1.5, 0.012), (7.0, 1.2, 0.02), -0.5)], kit.mid())
    tree_mat = kit.mat("kit-tree", (0.10, 0.20, 0.13), roughness=0.85)
    trunks, n = [], 0
    for k in range(38):
        a = k * 2.399963 + 0.4
        r = 9.0 + (k * 37 % 11) * 0.62
        x, y = math.cos(a) * r, math.sin(a) * r
        if abs(x) < 1.3 and y < 0:
            continue
        trunks.append(((x, y, 0.3), 0.07, 0.6))
        crown = kit.ico(f"{name}-tree{n}", (x, y, 1.05 + (k % 3) * 0.12), 0.55 + (k % 4) * 0.08, tree_mat,
                        subdivisions=1)
        crown.scale = (1.0, 1.0, 1.25)
        n += 1
    kit.cylinders(f"{name}-trunks", trunks, kit.mat("kit-bark", (0.12, 0.09, 0.07), roughness=0.9), segments=6)
    return {"panels": panels, "roof_z": roof_z, "count": count}


def neural_network(name="net", layers=(4, 6, 6, 6, 3), spacing=2.3, gap=1.0):
    """A feed-forward network standing in the XZ plane, facing -Y. Each layer has its
    own emissive material so a beat can run a signal through it. Returns per-layer
    materials, node positions and the edge object."""
    mats, positions, edges = [], [], []
    x0 = -(len(layers) - 1) * spacing / 2
    for li, count in enumerate(layers):
        m = kit.glow(f"{name}-layer{li}", 0.15)
        mats.append(m)
        pts = [(x0 + li * spacing, 0.0, 0.9 + (ni - (count - 1) / 2) * gap + (max(layers) - 1) * gap / 2)
               for ni in range(count)]
        positions.append(pts)
        kit.balls(f"{name}-nodes{li}", pts, 0.26, m)
    for li in range(len(layers) - 1):
        edges += [(a, b) for a in positions[li] for b in positions[li + 1]]
    wires = kit.rods(f"{name}-edges", edges, 0.012, kit.mid())
    return {"layers": mats, "positions": positions, "edges": wires}
