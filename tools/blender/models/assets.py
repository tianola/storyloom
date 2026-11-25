"""CC0 assets (Poly Haven, downloaded by tools/fetch_assets.py into assets/polyhaven/) for the world scenes.

The look stays flat and matte: a texture never replaces a palette colour, it only adds tone variation
and a little relief to it. `textured` multiplies the material's own base colour by the texture's
luminance (normalised to a mean of 1, so the palette brightness is kept) and blends that over the plain
colour at `influence`. Roughness never goes below what the material already had. Everything here is a
safe no-op when a file is missing (one warning line per asset), so `{"assets": false}` and a machine
without the downloads both give today's look.

The top half of this file is plain Python (rules, paths, the HDRI plan) and is unit-tested without
Blender (python/test_assets.py); `bpy` is imported only inside the functions that need it.
"""
import re
from collections import namedtuple
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ASSET_ROOT = ROOT / "assets" / "polyhaven"

Rule = namedtuple("Rule", "pattern texture scale influence")

# Mean linear luminance of each 1k diffuse map (measured), so the texture can be normalised to a mean
# of 1 and leave the palette brightness alone.
MEAN_LUM = {
    "castle_brick_07": 0.110, "cobblestone_floor_01": 0.236, "dark_wooden_planks": 0.072,
    "herringbone_brick": 0.052, "plaster_brick_pattern": 0.341, "roof_tiles": 0.307,
    "rough_plaster_03": 0.238,
}

# Material name (regex, case-insensitive, searched) -> texture, metres per texture tile, texture
# influence. Names are the real ones from kit.mat / world.py. First match wins.
RULES = [
    # streets and yards (world.cobbles(): "cobbles", "asy-cobbles")
    Rule(r"^(asy-)?cobbles(\.\d+)?$", "cobblestone_floor_01", 2.0, 0.55),
    Rule(r"^kerb$", "castle_brick_07", 1.6, 0.40),
    Rule(r"^akh-court$", "herringbone_brick", 1.8, 0.60),
    # townhouses (Town.mat keys: wall0.., roof0.., plinth, chimney, door, step)
    Rule(r"^town-wall\d+$", "rough_plaster_03", 2.5, 0.60),
    Rule(r"^town-roof\d+$", "roof_tiles", 2.2, 0.55),
    Rule(r"^town-plinth$", "castle_brick_07", 1.6, 0.45),
    Rule(r"^town-step$", "castle_brick_07", 1.2, 0.45),
    Rule(r"^town-chimney$", "plaster_brick_pattern", 1.0, 0.50),
    Rule(r"^town-door$", "dark_wooden_planks", 1.0, 0.50),
    # the general hospital and its court
    Rule(r"^akh-wall$", "plaster_brick_pattern", 3.0, 0.60),
    Rule(r"^akh-roof$", "roof_tiles", 2.5, 0.50),
    Rule(r"^door-stone$", "castle_brick_07", 1.5, 0.45),
    Rule(r"^prop-stone$", "castle_brick_07", 1.5, 0.45),
    Rule(r"^(door|prop)-wood$", "dark_wooden_planks", 1.2, 0.55),
    # the lit room behind the window (room_behind(name="room"))
    Rule(r"^room-wall$", "rough_plaster_03", 2.5, 0.50),
    Rule(r"^room-wood$", "dark_wooden_planks", 1.2, 0.55),
    # dissecting room, asylum (yard wall, building, cell)
    Rule(r"^anat-wall$", "castle_brick_07", 2.0, 0.45),
    Rule(r"^anat-wood$", "dark_wooden_planks", 1.2, 0.55),
    Rule(r"^asy-wall$", "castle_brick_07", 2.2, 0.45),
    Rule(r"^asy-wood$", "dark_wooden_planks", 1.2, 0.55),
    # the ward
    Rule(r"^ward-wall$", "rough_plaster_03", 3.0, 0.50),
    Rule(r"^ward-floor$", "dark_wooden_planks", 1.5, 0.60),
    Rule(r"^ward-beam$", "dark_wooden_planks", 1.2, 0.55),
    Rule(r"^ward-wood$", "dark_wooden_planks", 1.2, 0.55),
]


def rule_for(name, rules=None):
    """The first Rule whose pattern matches a material name, or None."""
    for rule in (RULES if rules is None else rules):
        if re.search(rule.pattern, name or "", re.I):
            return rule
    return None


def texture_files(texture_id, root=None):
    """{"diff", "rough", "nor"} paths of a texture (rough / nor are None when absent), or None when the
    diffuse map is missing."""
    base = Path(root or ASSET_ROOT) / "textures" / texture_id
    diff = base / f"{texture_id}_diff_1k.jpg"
    if not diff.is_file():
        return None
    out = {"diff": diff}
    for key, suffix in (("rough", "rough"), ("nor", "nor_gl")):
        f = base / f"{texture_id}_{suffix}_1k.jpg"
        out[key] = f if f.is_file() else None
    return out


def hdri_path(hdri_id, root=None):
    f = Path(root or ASSET_ROOT) / "hdris" / hdri_id / f"{hdri_id}_1k.hdr"
    return f if f.is_file() else None


def model_path(model_id, root=None):
    f = Path(root or ASSET_ROOT) / "models" / model_id / f"{model_id}_1k.gltf"
    return f if f.is_file() else None


def gain_for(texture_id):
    """Multiplier that brings a texture's luminance to a mean of 1."""
    return 1.0 / MEAN_LUM.get(texture_id, 0.25)


# Environment lighting by kind of place and time of day: (hdri, strength). Strengths are deliberately
# low: the sun/moon and lamps stay the key, the HDRI only adds the soft sky-and-bounce they lack.
HDRI_PLAN = {
    "street": {"day": ("farmland_overcast", 0.45), "dawn": ("farmland_overcast", 0.30),
               "dusk": ("belfast_sunset_puresky", 0.40), "night": (None, 0.0)},
    "ward": {"day": ("hospital_room", 0.30), "dawn": ("hospital_room", 0.20),
             "dusk": ("hospital_room", 0.12), "night": ("hospital_room", 0.04)},
    "asylum": {"night": (None, 0.0)},
}


def hdri_plan(kind, time):
    """(hdri id, strength at the start, strength at the end) for a place and a `time` ("dusk",
    "dusk>night"), or None for no environment light. A fade to a time with no HDRI fades it out."""
    table = HDRI_PLAN.get(kind, {})
    a, _, b = (time or "").partition(">")
    b = b or a
    ha, sa = table.get(a, (None, 0.0))
    hb, sb = table.get(b, (None, 0.0))
    hid = ha or hb
    if not hid or (sa <= 0 and sb <= 0):
        return None
    return hid, sa if ha else 0.0, sb if hb else 0.0


# ---------------------------------------------------------------------------
# Blender side
# ---------------------------------------------------------------------------

_WARNED = set()


def _warn(key, text):
    if key not in _WARNED:
        _WARNED.add(key)
        print(f"[assets] {text}")


def _load_image(path, srgb=True):
    import bpy
    img = bpy.data.images.load(str(path), check_existing=True)
    img.colorspace_settings.name = "sRGB" if srgb else "Non-Color"
    return img


def textured(mat, texture_id, scale_m, influence=0.55, normal=0.3):
    """Upgrade a material in place: its base colour times the texture's tone (mean 1) at `influence`,
    a little bump relief (`normal`), roughness at least the texture's. Box-projected object coordinates,
    `scale_m` metres per tile, so merged boxes without UVs map cleanly. Returns True when applied."""
    if mat is None or not mat.use_nodes or mat.get("assets_texture"):
        return False
    files = texture_files(texture_id)
    if files is None:
        _warn(("tex", texture_id), f"texture '{texture_id}' not found under {ASSET_ROOT}; material '{mat.name}' unchanged")
        return False
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        return False
    nodes, links = nt.nodes, nt.links
    # the colour the material already has: a linked node (cobbles) or the plain value
    inp = bsdf.inputs["Base Color"]
    base_src = inp.links[0].from_socket if inp.links else None
    base_val = tuple(inp.default_value)

    coord = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (1.0 / scale_m,) * 3
    links.new(coord.outputs["Object"], mapping.inputs["Vector"])

    def image_node(path, srgb):
        n = nodes.new("ShaderNodeTexImage")
        n.image = _load_image(path, srgb)
        n.projection = "BOX"
        n.projection_blend = 0.2
        links.new(mapping.outputs["Vector"], n.inputs["Vector"])
        return n

    diff = image_node(files["diff"], True)
    bw = nodes.new("ShaderNodeRGBToBW")
    links.new(diff.outputs["Color"], bw.inputs["Color"])
    norm = nodes.new("ShaderNodeMath")
    norm.operation = "MULTIPLY"
    norm.inputs[1].default_value = gain_for(texture_id)
    links.new(bw.outputs["Val"], norm.inputs[0])
    tone = nodes.new("ShaderNodeMixRGB")                  # palette colour x texture tone
    tone.blend_type = "MULTIPLY"
    tone.inputs["Fac"].default_value = 1.0
    blend = nodes.new("ShaderNodeMixRGB")                 # plain colour -> toned colour at `influence`
    blend.blend_type = "MIX"
    blend.inputs["Fac"].default_value = influence
    if base_src is not None:
        links.new(base_src, tone.inputs["Color1"])
        links.new(base_src, blend.inputs["Color1"])
    else:
        tone.inputs["Color1"].default_value = base_val
        blend.inputs["Color1"].default_value = base_val
    links.new(norm.outputs["Value"], tone.inputs["Color2"])
    links.new(tone.outputs["Color"], blend.inputs["Color2"])
    links.new(blend.outputs["Color"], inp)

    # relief: a bump from the same tone, chained after any bump the material already had
    nrm = bsdf.inputs["Normal"]
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = normal
    bump.inputs["Distance"].default_value = 0.03
    links.new(bw.outputs["Val"], bump.inputs["Height"])
    if nrm.links:
        links.new(nrm.links[0].from_socket, bump.inputs["Normal"])
    links.new(bump.outputs["Normal"], nrm)

    # roughness only ever goes up: the larger of the material's own and the texture's
    rin = bsdf.inputs["Roughness"]
    if files["rough"] and not rin.links:
        rough = image_node(files["rough"], False)
        hi = nodes.new("ShaderNodeMath")
        hi.operation = "MAXIMUM"
        hi.inputs[1].default_value = rin.default_value
        links.new(rough.outputs["Color"], hi.inputs[0])
        links.new(hi.outputs["Value"], rin)
    mat["assets_texture"] = texture_id
    return True


def upgrade_materials(rules=None):
    """Apply `textured` to every material in the file whose name matches a rule. Returns the count."""
    import bpy
    done = 0
    for m in list(bpy.data.materials):
        rule = rule_for(m.name, rules)
        if rule and textured(m, rule.texture, rule.scale, rule.influence):
            done += 1
    return done


def hdri_light(hdri_id, strength, end_strength=None, n_frames=None, rotation_z=0.0):
    """Light the scene from an HDRI without changing what the camera sees. The world's Surface becomes
    a Mix Shader on Light Path "Is Camera Ray": the camera still sees the existing sky; every other
    ray (diffuse, glossy, shadow, the probe that lights the scene) sees the sky plus the HDRI at
    `strength`. With `end_strength` and `n_frames` the strength is keyed from frame 1 to n_frames.
    No-op (False) without the file or a node world."""
    import bpy
    path = hdri_path(hdri_id)
    if path is None:
        _warn(("hdri", hdri_id), f"HDRI '{hdri_id}' not found under {ASSET_ROOT}; world lighting unchanged")
        return False
    world = bpy.context.scene.world
    if world is None or not world.use_nodes or world.get("assets_hdri"):
        return False
    nt = world.node_tree
    out = next((n for n in nt.nodes if n.type == "OUTPUT_WORLD" and n.is_active_output), None) \
        or next((n for n in nt.nodes if n.type == "OUTPUT_WORLD"), None)
    if out is None or not out.inputs["Surface"].links:
        return False
    sky = out.inputs["Surface"].links[0].from_socket
    nodes, links = nt.nodes, nt.links
    coord = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Rotation"].default_value = (0.0, 0.0, rotation_z)
    links.new(coord.outputs["Generated"], mapping.inputs["Vector"])
    env = nodes.new("ShaderNodeTexEnvironment")
    env.image = _load_image(path, True)
    links.new(mapping.outputs["Vector"], env.inputs["Vector"])
    bg = nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = strength
    links.new(env.outputs["Color"], bg.inputs["Color"])
    add = nodes.new("ShaderNodeAddShader")
    links.new(sky, add.inputs[0])
    links.new(bg.outputs["Background"], add.inputs[1])
    cam = nodes.new("ShaderNodeLightPath")
    mix = nodes.new("ShaderNodeMixShader")                # Fac 0 -> first shader, 1 -> second
    links.new(cam.outputs["Is Camera Ray"], mix.inputs["Fac"])
    links.new(add.outputs["Shader"], mix.inputs[1])
    links.new(sky, mix.inputs[2])
    links.new(mix.outputs["Shader"], out.inputs["Surface"])
    if end_strength is not None and n_frames and end_strength != strength:
        for fr, v in ((1, strength), (n_frames, end_strength)):
            bg.inputs["Strength"].default_value = v
            bg.inputs["Strength"].keyframe_insert("default_value", frame=fr)
    world["assets_hdri"] = hdri_id
    return True


def scene_hdri(kind, time, n_frames):
    """hdri_light for a place ("street" | "ward" | "asylum") at a time, from HDRI_PLAN."""
    plan = hdri_plan(kind, time)
    if plan is None:
        return False
    hid, a, b = plan
    return hdri_light(hid, a, b, n_frames)


# --- props -------------------------------------------------------------------------------------------

_TEMPLATES = {}


def _template(model_id):
    """The glTF imported once per session, kept out of every scene (a collection nobody links)."""
    import bpy
    from mathutils import Vector
    tpl = _TEMPLATES.get(model_id)
    if tpl is not None:
        if tpl is False:
            return None
        try:
            if all(bpy.data.objects.get(o.name) is o for o in tpl["objs"]):
                return tpl
        except ReferenceError:
            pass
    path = model_path(model_id)
    if path is None:
        _warn(("model", model_id), f"model '{model_id}' not found under {ASSET_ROOT}; prop skipped")
        _TEMPLATES[model_id] = False
        return None
    before = {o.name for o in bpy.data.objects}
    try:
        bpy.ops.import_scene.gltf(filepath=str(path))
    except Exception as exc:                              # importer add-on off, corrupt file ...
        _warn(("model", model_id), f"model '{model_id}' failed to import ({exc}); prop skipped")
        _TEMPLATES[model_id] = False
        return None
    new = [o for o in bpy.data.objects if o.name not in before]
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in new if o.type == "MESH" for c in o.bound_box]
    if not pts:
        for o in new:
            bpy.data.objects.remove(o, do_unlink=True)
        _warn(("model", model_id), f"model '{model_id}' has no meshes; prop skipped")
        _TEMPLATES[model_id] = False
        return None
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    holder = bpy.data.collections.new(f"asset-template-{model_id}")
    holder.use_fake_user = True
    for o in new:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        holder.objects.link(o)
    tpl = _TEMPLATES[model_id] = {"objs": new, "lo": lo, "hi": hi}
    return tpl


def prop(model_id, location, rotation_z=0.0, height=None, name=None):
    """A linked duplicate of a glTF model standing on `location` (bottom centre of its bounding box),
    turned `rotation_z` about Z, scaled uniformly so its bounding-box height is `height` (natural size
    when None). Meshes are shared between duplicates. The glTF's front is assumed to face -Y at
    rotation_z = 0. Returns the root empty, or None when the model is missing."""
    import bpy
    from mathutils import Matrix, Vector
    tpl = _template(model_id)
    if tpl is None:
        return None
    lo, hi = tpl["lo"], tpl["hi"]
    h0 = hi.z - lo.z
    k = height / h0 if height and h0 > 1e-6 else 1.0
    centre = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    coll = bpy.context.scene.collection
    root = bpy.data.objects.new(name or model_id, None)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 0.05
    root.location = location
    root.rotation_euler = (0.0, 0.0, rotation_z)
    root.scale = (k, k, k)
    coll.objects.link(root)
    copies = {o: o.copy() for o in tpl["objs"]}           # Object.copy() shares mesh data
    for o, c in copies.items():
        c.hide_render = False
        c.hide_viewport = False
        if o.parent in copies:
            c.parent = copies[o.parent]
            c.matrix_parent_inverse = o.matrix_parent_inverse.copy()
        else:
            c.parent = root
            c.matrix_parent_inverse = Matrix.Translation(-centre)
        coll.objects.link(c)
    return root
