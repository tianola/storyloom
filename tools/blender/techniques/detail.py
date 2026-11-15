"""Micro-geometry: what separates a machine from a primitive.

A cylinder straight out of `primitive_cylinder_add` is analytically perfect. Its silhouette
is an exact straight edge, its specular highlight does not move as the camera orbits, and
the eye reads that in a fraction of a second as "3D placeholder" — which is the complaint
this module exists to answer. Real hardware oil-cans between stringers, shows weld rolls,
has spray-pass texture in foam and buckles in foil.

Everything here displaces the *mesh*, not the shading. A bump map can only bend a normal;
it cannot bend a silhouette, and it cannot break a specular highlight that runs the whole
length of a tank. Both of those need vertices.

Amplitude and wavelength are fractions of the object's own bounding-box diagonal rather
than metres, so one call reads the same on a 1 m cubesat and a 90 m pad instead of needing
a per-object magic number.
"""
import bmesh
import math

import bpy
from mathutils import Vector, noise

TAU = 2 * math.pi


def _diagonal(obj):
    """Size of the mesh in its *own* local space, used to make every number scale-free.

    Read off the vertices rather than `bound_box`/`dimensions`: those are depsgraph-evaluated
    and are stale for the objects this helper meets, which were created a line earlier and
    have not been through a view-layer update.

    Local, not world: several bodies here carry their size as an object scale (the cubesat
    bus is a unit cube at scale 0.6) and displacement written into the mesh has to be
    measured against the mesh, or the noise wavelength stretches with the transform instead
    of with the part.
    """
    verts = obj.data.vertices
    if not verts:
        return 1e-4
    xs = [v.co.x for v in verts]
    ys = [v.co.y for v in verts]
    zs = [v.co.z for v in verts]
    return max(1e-4, math.dist((min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))))


def surface_relief(obj, *, amplitude=0.004, wavelength=0.30, cuts=2, seed=(0.0, 0.0, 0.0),
                   turbulence=0.0, smooth=True):
    """Subdivide, then push the surface along its own normals with a noise field.

    `cuts` is how many extra edge loops per existing edge — the vertex budget is
    (cuts+1)^2 per quad, so 2 is the default and 3 is only worth it on a hero body.
    `turbulence` layers multi-fractal noise on top of the base wave; that is what makes a
    buckled tank read as sprayed foam rather than as a sine wave wrapped around a pipe.
    """
    size = _diagonal(obj)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    # Cylinder and cone caps arrive as n-gons. Subdividing one leaves its interior without
    # vertices, so the noise moves the rim while the face itself stays rigid and the cap
    # tears away from the wall it belongs to. Triangles first means every vertex the field
    # writes has somewhere to go.
    ngons = [f for f in bm.faces if len(f.verts) > 4]
    if ngons:
        bmesh.ops.triangulate(bm, faces=ngons)
    if cuts > 0:
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True)
    bm.normal_update()
    freq = 1.0 / max(wavelength * size, 1e-4)
    amp = amplitude * size
    offset = Vector(seed)
    for v in bm.verts:
        p = v.co * freq + offset
        d = noise.noise(p)
        if turbulence > 0.0:
            # The third argument is a bool, not a float. hard=True sums |noise|, which folds
            # the field along its zero crossings and gives ridges — the crease lines a quilted
            # foil blanket and a rolled tank seam actually have. It is one-sided (measured
            # mean +0.43), so it is re-centred here; left as-is it inflates every body it
            # touches instead of creasing it.
            d += (noise.turbulence(p * 2.7, 3, True, amplitude_scale=0.55) - 0.43) * turbulence
        v.co += v.normal * (d * amp)
    bm.to_mesh(obj.data)
    bm.free()
    # BMFace has no use_smooth — the flag lives on the mesh polygon after the write-back.
    # (bpy.ops.object.shade_smooth would need EDIT mode, which an object hidden from the
    # view layer cannot enter, and several beats hide a stage or a cutaway wall.)
    if smooth:
        for poly in obj.data.polygons:
            poly.use_smooth = True
    obj.data.update()
    return obj


def stiffener_rings(prefix, *, center, radius, count, spacing, width=0.035,
                    material=None):
    """Raised rings down a vertical tank: the detail that lets an eye measure it.

    A 45 m booster with no joint features is one seamless extrusion. Real segmented casings
    and stringer-run tanks carry a visible roll every few metres, and those rolls are what
    the highlight travels along.
    """
    rings = []
    for i in range(count):
        loc = Vector(center)
        loc.z += (i - (count - 1) / 2.0) * spacing
        bpy.ops.mesh.primitive_torus_add(major_radius=radius, minor_radius=width,
                                         location=loc,
                                         major_segments=48, minor_segments=8)
        ring = bpy.context.active_object
        ring.name = f"{prefix}-stiff{i}"
        if material:
            ring.data.materials.append(material)
        bpy.ops.object.shade_smooth()
        rings.append(ring)
    return rings


def bolt_circle(prefix, *, center, radius, count, bolt_radius, material=None, normal="Z"):
    """Fasteners around a flange. Small, cheap, and the strongest scale cue there is."""
    bolts = []
    for i in range(count):
        a = i * TAU / count
        u, v = radius * math.cos(a), radius * math.sin(a)
        loc = Vector(center)
        if normal == "Z":
            loc.x += u
            loc.y += v
        elif normal == "X":
            loc.y += u
            loc.z += v
        else:
            loc.x += u
            loc.z += v
        bpy.ops.mesh.primitive_cylinder_add(radius=bolt_radius, depth=bolt_radius * 2.2,
                                            location=loc, vertices=6,
                                            rotation=((0, math.radians(90), 0)
                                                      if normal == "X" else
                                                      (math.radians(-90), 0, 0)
                                                      if normal == "Y" else (0, 0, 0)))
        bolt = bpy.context.active_object
        bolt.name = f"{prefix}-bolt{i}"
        if material:
            bolt.data.materials.append(material)
        bolts.append(bolt)
    return bolts


def add_glare(scene, *, glare_type="BLOOM", threshold=1.0, size=7, mix=0.0):
    """Compositor bloom: the highlight roll-off that makes emissives read as light.

    EEVEE Next dropped the old in-engine bloom, so without a compositor node an engine
    plume is a bright *shape* rather than a bright *source* — the surrounding pad stays
    equally dark, and the picture loses exactly the glow that sells fire.

    `mix` is the glare node's own balance, not an opacity: 0 keeps the render and adds the
    glare, -1 is the bare render, +1 is glare only.
    """
    scene.use_nodes = True
    tree = scene.node_tree
    for node in list(tree.nodes):
        tree.nodes.remove(node)
    render = tree.nodes.new("CompositorNodeRLayers")
    glare = tree.nodes.new("CompositorNodeGlare")
    composite = tree.nodes.new("CompositorNodeComposite")
    glare.glare_type = glare_type
    glare.quality = "HIGH"
    glare.threshold = threshold
    glare.size = size
    glare.mix = mix
    tree.links.new(render.outputs["Image"], glare.inputs["Image"])
    tree.links.new(glare.outputs["Image"], composite.inputs["Image"])
    return glare
