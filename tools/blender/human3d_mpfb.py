"""Build the dressed 3D people of an episode with MPFB2 (MakeHuman for Blender), run with Blender in background.

    blender -b --factory-startup -P tools/blender/human3d_mpfb.py -- \
        --assets <makehuman asset dir> --out work/semmelweis-10min/human3d [--who midwife ...] [--variants 3]
        [--sheet renders/people.png]

<makehuman asset dir> is the folder tools/human3d_assets.py fills: the MakeHuman system assets (CC0) and the
community packs the wardrobe below names (CC0 and CC-BY, credited in docs/human3d-credits.md), merged in the
MakeHuman layout (clothes/, hair/, eyebrows/, eyelashes/, eyes/, skins/, teeth/). The MPFB2 extension must be
installed in this Blender (tools/human3d_assets.py --install-mpfb does it); nothing of MPFB or the assets is
stored in git.

Each role is built `--variants` times with a different seed: face and body shape, skin, hair, beard and the
colours of the clothes change; role and period stay. The files are <out>/<who>.blend, <who>.2.blend, ...
and models/human3d.py hands the variants out in turn, so three mothers in one shot are three different women.

What a built file holds (the contract of models/human3d.py and storyboard_beats.place_human3d):
  - a generated Rigify rig (data["rig_id"]) with the FK controls the pose library uses
  - the body "mb_<who>", with the face shape keys human3d.MOUTH and FACE use (Exp_mouthOpen_max, ...)
    built from MakeHuman's expression unit targets; the eyebrows, eyelashes and beard carry the same keys
  - clothes, shoes, hair, eyebrows, eyelashes, eyes and teeth, all deformed by the rig; the skin under the
    clothes is masked away by the clothes' delete groups, so no body shows through
  - rig["human3d_poses"]: JSON {pose: {FK control: [w, x, y, z]}, "torso@loc": [x, y, z]} for stand, talk,
    point, look-hands, hold, sit, kneel
  - the action "walk": one cycle of a procedural walk (FK legs and arms), cyclic
The rig stands at the origin with the feet on z=0, facing -Y, at the height the role's phenotype gives.
"""
import argparse
import json
import math
import os
import random
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector

MPFB = "bl_ext.user_default.mpfb"

# 1846 Vienna, the General Hospital's First Clinic. Every list is a choice the seed makes per variant.
# clothes: (asset, tint) with tint an RGB multiplier on the garment's texture, or None for its own colours
DARK_WOOLS = [(0.10, 0.10, 0.12), (0.13, 0.10, 0.08), (0.08, 0.10, 0.09), (0.12, 0.12, 0.12)]
DRESS_COLOURS = [(0.42, 0.30, 0.22), (0.30, 0.33, 0.40), (0.38, 0.36, 0.30), (0.45, 0.25, 0.22), (0.28, 0.30, 0.26)]
LINEN = [(0.95, 0.93, 0.86), (0.90, 0.88, 0.82), (0.97, 0.96, 0.92)]
HAIR_COLOURS = {"dark": (0.12, 0.08, 0.05), "brown": (0.28, 0.17, 0.09), "fair": (0.55, 0.42, 0.25),
                "grey": (0.55, 0.53, 0.50), "black": (0.05, 0.04, 0.04), "auburn": (0.40, 0.17, 0.08)}

ROLES = {
    # Ignaz Semmelweis at 28: stocky, early receding hair, side whiskers, dark frock coat over a waistcoat
    "semmelweis": {
        "gender": 1.0, "age": (0.52, 0.55), "weight": (0.62, 0.68), "muscle": (0.5, 0.55), "height": (0.5, 0.56),
        "skin": ["middleage_caucasian_male", "young_caucasian_male"], "eyes": ["brown", "brownlight"],
        "hair": [("short02", "brown"), ("short04", "dark")], "eyebrows": ["eyebrow001", "eyebrow007"],
        "beard": [None],
        "clothes": [("toigo_suit_with_jacket_and_bowtie", None), ("punkduck_winter_coat", "wool"),
                    ("toigo_ankle_boots_male", "leather")],
    },
    # the professor (Klein): older, grey, full beard, long dark coat
    "doctor": {
        "gender": 1.0, "age": (0.78, 0.88), "weight": (0.55, 0.7), "muscle": (0.4, 0.5), "height": (0.45, 0.6),
        "skin": ["old_caucasian_male", "middleage_caucasian_male"], "eyes": ["grey", "blue", "brown"],
        "hair": [("short02", "grey"), ("short04", "grey")], "eyebrows": ["eyebrow001", "eyebrow003"],
        "beard": [("grinsegold_full_beard", "grey"), ("grinsegold_beard_sigmund_wip", "grey")],
        "clothes": [("elvs_male_shirt_tie_tucked1", "linen"), ("toigo_wool_pants", "wool"),
                    ("punkduck_winter_coat", "wool"),
                    ("toigo_ankle_boots_male", "leather")],
    },
    # medical students: young men in dark jackets, shirt and tie (a cravat at this distance)
    "student": {
        "gender": 1.0, "age": (0.38, 0.46), "weight": (0.4, 0.6), "muscle": (0.45, 0.6), "height": (0.45, 0.7),
        "skin": ["young_caucasian_male", "young_caucasian_male2", "middleage_caucasian_male"],
        "eyes": ["brown", "blue", "bluegreen", "grey"],
        "hair": [("short02", "brown"), ("short03", "dark"), ("short04", "fair"), ("short01", "black"),
                 ("short02", "auburn")],
        "eyebrows": ["eyebrow001", "eyebrow002", "eyebrow007", "eyebrow010"],
        "beard": [None, None, ("wdg_scruffy_beard", "hair")],
        "clothes": [("toigo_male_suit_tie_and_jacket", "wool"), ("toigo_ankle_boots_male", "leather")],
    },
    # the midwives of the Second Clinic: long working dress, white apron and bonnet, hair up
    "midwife": {
        "gender": 0.0, "age": (0.5, 0.75), "weight": (0.5, 0.7), "muscle": (0.4, 0.5), "height": (0.4, 0.55),
        "skin": ["middleage_caucasian_female", "young_caucasian_female", "old_caucasian_female"],
        "eyes": ["brown", "blue", "grey"],
        "hair": [("rehmanpolanski_hair_bun_brown", "brown"), ("elvs_reverse_french_braid_bun", "dark")],
        "eyebrows": ["eyebrow009", "eyebrow011"],
        "clothes": [("punkduck_medieval_dress", "dress"), ("elvs_ladies_apron", "linen"),
                    ("elvs_dirty_lil_maid_bonnet", "linen"), ("toigo_ankle_boots_female", "leather")],
    },
    # the mothers: poor women of Vienna in long skirts, blouses, aprons, hair covered or tied back
    "mother": {
        "gender": 0.0, "age": (0.45, 0.56), "weight": (0.42, 0.62), "muscle": (0.35, 0.5), "height": (0.3, 0.5),
        "skin": ["young_caucasian_female", "young_caucasian_female2", "middleage_caucasian_female"],
        "eyes": ["brown", "blue", "bluegreen", "grey", "green"],
        "hair": [("rehmanpolanski_hair_bun_brown", "brown"), ("elvs_reverse_french_braid_bun", "fair"),
                 ("braid01", "dark"), ("ponytail01", "auburn"), ("rehmanpolanski_hair_bun_brown", "black")],
        "eyebrows": ["eyebrow009", "eyebrow011", "eyebrow012"],
        "outfits": [
            [("toigo_long_full_skirt", "dress"), ("elvs_ruffle_sleeve_peasant_blouse_1", "linen"),
             ("elvs_ladies_apron", "linen"), ("toigo_ankle_boots_female", "leather")],
            [("punkduck_medieval_dress", "dress"), ("elvs_ladies_apron", "linen"), ("toigo_ankle_boots_female", "leather")],
            [("toigo_long_full_skirt", "dress"), ("elvs_ruffle_sleeve_peasant_blouse_1", "linen"),
             ("elvs_dirty_lil_maid_bonnet", "linen"), ("toigo_ankle_boots_female", "leather")],
        ],
    },
    # the explorer who guides the film: a traveller of the period in a long coat, seen mostly as a bust
    "explorer": {
        "gender": 1.0, "age": (0.45, 0.5), "weight": (0.45, 0.5), "muscle": (0.55, 0.6), "height": (0.55, 0.6),
        "skin": ["young_caucasian_male"], "eyes": ["bluegreen"], "hair": [("short04", "brown")],
        "eyebrows": ["eyebrow002"], "beard": [None],
        "clothes": [("elvs_male_shirt_tie_tucked1", "linen"), ("toigo_wool_pants", "wool"),
                    ("punkduck_winter_coat", "coat_brown"), ("toigo_ankle_boots_male", "leather")],
    },
}
TINTS = {"leather": [(0.09, 0.06, 0.04), (0.05, 0.04, 0.035)], "wool": DARK_WOOLS, "dress": DRESS_COLOURS, "linen": LINEN, "coat_brown": [(0.30, 0.20, 0.12)]}
ASSET_KIND = {"eyebrows": "Eyebrows", "eyelashes": "Eyelashes", "eyes": "Eyes", "teeth": "Teeth", "hair": "Hair"}

# face shape keys the renderer keys (models/human3d.py MOUTH and FACE), each a mix of MakeHuman expression units
FACE_KEYS = {
    "Exp_mouthClosed_max": {"mouth-compression": 0.8},
    "Exp_mouthOpenHalf_max": {"mouth-open": 0.45},
    "Exp_mouthOpen_max": {"mouth-open": 0.8},
    "Exp_mouthOpenLarge_max": {"mouth-open": 1.0, "mouth-depression": 0.3},
    "Exp_mouthOpenO_max": {"mouth-open": 0.55, "mouth-pursing": 0.6},
    "Exp_mouthSmile_max": {"mouth-corner-puller": 0.9},
    "Exp_mouthSmile_min": {"mouth-depression": 0.8},
    "Exp_browSqueezeL_max": {"eyebrows-left-down": 0.8},
    "Exp_browSqueezeR_max": {"eyebrows-right-down": 0.8},
    "Exp_browsMidVert_max": {"eyebrows-left-inner-up": 0.8, "eyebrows-right-inner-up": 0.8},
    "Exp_browOutVertL_max": {"eyebrows-left-up": 0.8, "eyebrows-left-extern-up": 0.4},
    "Exp_browOutVertR_max": {"eyebrows-right-up": 0.8, "eyebrows-right-extern-up": 0.4},
    "Exp_eyesClosed_max": {"eye-left-closure": 1.0, "eye-right-closure": 1.0},
}
# face detail targets the seed moves a little, so two variants of a role do not share a face
FACE_DETAIL = ["nose/nose-scale-horiz-incr|decr", "nose/nose-scale-vert-incr|decr", "chin/chin-width-incr|decr",
               "chin/chin-prominent-incr|decr", "cheek/l-cheek-bones-incr|decr", "cheek/r-cheek-bones-incr|decr",
               "mouth/mouth-scale-horiz-incr|decr", "head/head-oval", "head/head-round", "head/head-square",
               "eyebrows/eyebrows-trans-up|down", "eyes/r-eye-height2-up|down", "eyes/l-eye-height2-up|down",
               "nose/nose-hump-incr|decr", "ears/r-ear-scale-incr|decr", "ears/l-ear-scale-incr|decr"]


def parse(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--who", action="append", choices=sorted(ROLES))
    ap.add_argument("--variants", type=int, default=3)
    ap.add_argument("--sheet", type=Path, help="also render a lineup of every built variant (Cycles)")
    ap.add_argument("--samples", type=int, default=48)
    return ap.parse_args(argv)


# ---------------------------------------------------------------------------------------------- setup

def start_blender():
    import addon_utils
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("rigify", default_set=True)
    try:
        bpy.ops.preferences.addon_enable(module=MPFB)
        __import__(MPFB)
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"MPFB2 is not installed in this Blender ({exc}): run tools/human3d_assets.py --install-mpfb")


def services():
    mod = __import__(MPFB + ".services", fromlist=["humanservice"])
    from importlib import import_module
    hs = import_module(MPFB + ".services.humanservice").HumanService
    rs = import_module(MPFB + ".services.rigservice").RigService
    ts = import_module(MPFB + ".services.targetservice").TargetService
    cs = import_module(MPFB + ".services.clothesservice").ClothesService
    ls = import_module(MPFB + ".services.locationservice").LocationService
    mhclo = import_module(MPFB + ".entities.clothes.mhclo").Mhclo
    del mod
    return hs, rs, ts, cs, ls, mhclo


def zdepth(mhclo_path):
    """The layer order MakeHuman gives a garment (higher is worn over lower)."""
    for line in Path(mhclo_path).read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("z_depth"):
            return int(line.split()[1])
    return 50


def find_asset(root, kind, name):
    """<root>/<kind>/<name>/<something>.mhclo (or .mhmat for skins and eye materials)."""
    ext = ".mhmat" if kind in ("skins", "eyes/materials") else ".mhclo"
    d = root / kind / name
    if kind == "eyes/materials":
        p = root / "eyes" / "materials" / f"{name}.mhmat"
        if p.exists():
            return p
    if d.is_dir():
        files = sorted(d.glob(f"*{ext}"))
        exact = [f for f in files if f.stem == name]
        if exact or files:
            return (exact or files)[0]
    for alt in ("clothes", "hair"):
        d = root / alt / name
        if d.is_dir():
            files = sorted(d.glob(f"*{ext}"))
            if files:
                return files[0]
    raise FileNotFoundError(f"asset {kind}/{name} not found under {root} (run tools/human3d_assets.py)")


# ---------------------------------------------------------------------------------------------- body

def target_file(name):
    from importlib import import_module
    loc = import_module(MPFB + ".services.locationservice").LocationService
    base = Path(loc.get_mpfb_data("targets"))
    for p in (base / f"{name}.target.gz", base / f"{name}.target"):
        if p.exists():
            return p
    return None


def build_body(spec, rng, hs, ts):
    macro = ts.get_default_macro_info_dict()
    macro["gender"] = spec["gender"]
    for k in ("age", "weight", "muscle", "height"):
        lo, hi = spec[k]
        macro[k] = rng.uniform(lo, hi)
    macro["proportions"] = rng.uniform(0.5, 0.8)
    if spec["gender"] < 0.5:
        macro["cupsize"] = rng.uniform(0.45, 0.6)
    macro["race"] = {"caucasian": 0.9, "african": 0.03, "asian": 0.07}
    body = hs.create_human(macro_detail_dict=macro)
    # a little of a dozen face details, so variants differ in the face as well as the build
    for item in FACE_DETAIL:
        if "|" in item:
            stem, alts = item.rsplit("-", 1)
            pick = rng.choice(alts.split("|"))
            name = f"{stem}-{pick}"
        else:
            name = item
        p = target_file(name)
        if p is None:
            continue
        ts.load_target(body, str(p), weight=rng.uniform(0.0, 0.45), name=name.replace("/", "_"))
    ts.bake_targets(body)
    return body, macro


def add_face_keys(body, ts, race="caucasian"):
    """The renderer's face keys, each baked from MakeHuman expression units at the weights in FACE_KEYS."""
    from importlib import import_module
    loc = import_module(MPFB + ".services.locationservice").LocationService
    units = Path(loc.get_mpfb_data("targets")) / "expression" / "units" / race
    if body.data.shape_keys is None:
        body.shape_key_add(name="Basis", from_mix=False)
    loaded = {}
    for mix in FACE_KEYS.values():
        for unit in mix:
            if unit not in loaded:
                loaded[unit] = ts.load_target(body, str(units / f"{unit}.target.gz"), weight=0.0, name=f"unit_{unit}")
    for key, mix in FACE_KEYS.items():
        for kb in loaded.values():
            kb.value = 0.0
        for unit, w in mix.items():
            loaded[unit].value = w
        kb = body.shape_key_add(name=key, from_mix=True)
        kb.value = 0.0
    for kb in loaded.values():
        body.shape_key_remove(kb)
    print("HUMAN3D_FACE_KEYS", len(FACE_KEYS))


def face_keys_on_proxies(body, proxies, cs, Mhclo):
    """Eyebrows, eyelashes and beards are separate meshes fitted to the face. For every face key they are
    refitted to the body with that key on, and the fitted shape is stored as the same key on the proxy, so
    human3d.set_face moves the brows with the forehead and the beard with the jaw."""
    keys = [k for k in FACE_KEYS if k in body.data.shape_keys.key_blocks]
    shapes = {}
    for proxy, mhclo_path in proxies:
        m = Mhclo()
        m.load(str(mhclo_path))
        m.clothes = proxy
        shapes[proxy.name] = (m, {})
    for key in keys + [None]:
        for kb in body.data.shape_keys.key_blocks[1:]:
            kb.value = 0.0
        if key:
            body.data.shape_keys.key_blocks[key].value = 1.0
        for proxy, _ in proxies:
            m, got = shapes[proxy.name]
            cs.fit_clothes_to_human(proxy, body, m, set_parent=False)
            got[key] = [v.co.copy() for v in proxy.data.vertices]
    for kb in body.data.shape_keys.key_blocks[1:]:
        kb.value = 0.0
    for proxy, _ in proxies:
        _, got = shapes[proxy.name]
        for v, co in zip(proxy.data.vertices, got[None]):
            v.co = co
        proxy.shape_key_add(name="Basis", from_mix=False)
        for key in keys:
            kb = proxy.shape_key_add(name=key, from_mix=False)
            for d, co in zip(kb.data, got[key]):
                d.co = co
            kb.value = 0.0


# ---------------------------------------------------------------------------------------------- materials

def tint_material(obj, rgb, texture=0.35):
    """Dye every material on `obj` to `rgb`: the garment's texture is turned to grey and only `texture` of its
    light and shade is kept (seams, folds, weave), so a red print dress becomes a plain dyed wool dress and a
    floral apron plain linen. Each object gets its own copy of the material."""
    for slot in obj.material_slots:
        mat = slot.material
        if mat is None or not mat.use_nodes:
            continue
        mat = mat.copy()
        slot.material = mat
        nt = mat.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None:
            continue
        sock = bsdf.inputs["Base Color"]
        shade = nt.nodes.new("ShaderNodeMix")          # white -> the texture's grey, `texture` of the way
        shade.data_type = "RGBA"
        shade.inputs["Factor"].default_value = texture
        shade.inputs["A"].default_value = (0.8, 0.8, 0.8, 1.0)
        if sock.is_linked:
            bw = nt.nodes.new("ShaderNodeRGBToBW")
            nt.links.new(sock.links[0].from_socket, bw.inputs["Color"])
            nt.links.new(bw.outputs["Val"], shade.inputs["B"])
        else:
            shade.inputs["B"].default_value = (0.8, 0.8, 0.8, 1.0)
        dye = nt.nodes.new("ShaderNodeMix")
        dye.data_type = "RGBA"
        dye.blend_type = "MULTIPLY"
        dye.inputs["Factor"].default_value = 1.0
        dye.inputs["B"].default_value = (*[min(1.0, c * 1.25) for c in rgb], 1.0)
        nt.links.new(shade.outputs["Result"], dye.inputs["A"])
        nt.links.new(dye.outputs["Result"], sock)
        if "Roughness" in bsdf.inputs and not bsdf.inputs["Roughness"].is_linked:
            bsdf.inputs["Roughness"].default_value = max(0.75, bsdf.inputs["Roughness"].default_value)
        if "Specular IOR Level" in bsdf.inputs and not bsdf.inputs["Specular IOR Level"].is_linked:
            bsdf.inputs["Specular IOR Level"].default_value = 0.15


EYE_COLOURS = {"brown": (0.18, 0.08, 0.03), "brownlight": (0.32, 0.18, 0.07), "blue": (0.12, 0.25, 0.45),
               "bluegreen": (0.12, 0.3, 0.3), "grey": (0.3, 0.33, 0.36), "green": (0.15, 0.3, 0.12)}


def set_iris(eyes, rgb):
    """MPFB's procedural eyes: one node group whose iris colours are inputs."""
    for slot in eyes.material_slots:
        if slot.material is None or not slot.material.use_nodes:
            continue
        for node in slot.material.node_tree.nodes:
            if node.type != "GROUP":
                continue
            for sock in node.inputs:
                if sock.name == "IrisMinorColor":
                    sock.default_value = (*rgb, 1.0)
                elif sock.name == "IrisMajorColor":
                    sock.default_value = (*[c * 0.55 for c in rgb], 1.0)


def pick_tint(name, rng, hair_rgb):
    if name is None:
        return None
    if name == "hair":
        return hair_rgb
    if name in HAIR_COLOURS:
        return HAIR_COLOURS[name]
    return rng.choice(TINTS[name])


def hair_material(obj, rgb):
    """MakeHuman hair and beard textures are dark and coloured; they are dyed like cloth, keeping half of the
    strands' light and shade, so one cap can be grey, fair or black. The alpha (the strand cut-outs) stays."""
    tint_material(obj, rgb, texture=0.55)
    for slot in obj.material_slots:
        bsdf = next((n for n in slot.material.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is not None and not bsdf.inputs["Roughness"].is_linked:
            bsdf.inputs["Roughness"].default_value = 0.6


def opaque(obj):
    """Garment textures carry alpha (some, like the winter coat, have see-through patches in it): cloth is
    made fully opaque. Hair, brows, lashes and beards keep their alpha, which is what cuts the strands."""
    for slot in obj.material_slots:
        mat = slot.material
        if mat is None or not mat.use_nodes:
            continue
        bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None:
            continue
        a = bsdf.inputs["Alpha"]
        for link in list(a.links):
            mat.node_tree.links.remove(link)
        a.default_value = 1.0
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "DITHERED"
        if hasattr(mat, "blend_method"):
            mat.blend_method = "OPAQUE"


def hide_covered(inner, outer, reach=0.06):
    """Delete the faces of `inner` that `outer` covers: a ray from each vertex outward along its normal that
    meets `outer` within `reach` metres, or inward within 3 cm (the vertex already pokes through `outer`). Layered MakeHuman garments are fitted to the body independently, so
    a jacket pokes through a coat and a shirt through a jacket; what cannot be seen is simply not there."""
    import bmesh
    from mathutils.bvhtree import BVHTree
    deps = bpy.context.evaluated_depsgraph_get()
    tree = BVHTree.FromObject(outer, deps)
    to_outer = outer.matrix_world.inverted() @ inner.matrix_world
    rot = to_outer.to_3x3()
    covered = set()
    for v in inner.data.vertices:
        co = to_outer @ v.co
        n = (rot @ v.normal).normalized()
        # covered: the outer layer lies just outside this vertex, or this vertex already pokes out through it
        if tree.ray_cast(co - n * 0.002, n, reach)[0] is not None or tree.ray_cast(co, -n, 0.03)[0] is not None:
            covered.add(v.index)
    bm = bmesh.new()
    bm.from_mesh(inner.data)
    gone = [f for f in bm.faces if all(v.index in covered for v in f.verts)]
    bmesh.ops.delete(bm, geom=gone, context="FACES")
    bm.to_mesh(inner.data)
    bm.free()
    print("HUMAN3D_COVERED", inner.name, "under", outer.name, len(gone), "faces")


# ---------------------------------------------------------------------------------------------- rig and poses

def dedupe_armature_modifiers(obj, rig):
    seen = False
    for m in list(obj.modifiers):
        if m.type == "ARMATURE":
            if seen:
                obj.modifiers.remove(m)
            else:
                m.object = rig
                seen = True


def _world_dir(rig, name):
    pb = rig.pose.bones[name]
    m = rig.matrix_world @ pb.matrix
    return (m.to_3x3() @ Vector((0, 1, 0))).normalized()


def aim(rig, name, direction, twist_ref=None):
    """Turn FK control `name` so its bone points along world `direction` (its parent already posed)."""
    pb = rig.pose.bones[name]
    bpy.context.view_layer.update()
    cur = _world_dir(rig, name)
    want = Vector(direction).normalized()
    rot = cur.rotation_difference(want)
    m = pb.matrix.copy()
    loc = m.to_translation()
    r = (rot.to_matrix() @ m.to_3x3()).normalized()
    pb.matrix = Matrix.Translation(loc) @ r.to_4x4()
    bpy.context.view_layer.update()


def bend(rig, name, axis_angle_deg, axis="X"):
    """Extra local rotation of a control around its own axis (elbows and knees bend around X)."""
    pb = rig.pose.bones[name]
    q = Quaternion(Vector((1, 0, 0)) if axis == "X" else Vector((0, 0, 1)) if axis == "Z" else Vector((0, 1, 0)),
                   math.radians(axis_angle_deg))
    pb.rotation_quaternion = pb.rotation_quaternion @ q
    bpy.context.view_layer.update()


FK = ["torso", "hips", "chest", "spine_fk", "spine_fk.001", "spine_fk.002", "spine_fk.003", "neck", "head",
      "shoulder.L", "shoulder.R", "upper_arm_fk.L", "upper_arm_fk.R", "forearm_fk.L", "forearm_fk.R",
      "hand_fk.L", "hand_fk.R", "thigh_fk.L", "thigh_fk.R", "shin_fk.L", "shin_fk.R", "foot_fk.L", "foot_fk.R"]
SWITCHES = ["upper_arm_parent.L", "upper_arm_parent.R", "thigh_parent.L", "thigh_parent.R"]


def reset_pose(rig):
    for pb in rig.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    for s in SWITCHES:
        if s in rig.pose.bones:
            rig.pose.bones[s]["IK_FK"] = 1.0
    bpy.context.view_layer.update()


def read_pose(rig):
    out = {}
    for name in FK:
        pb = rig.pose.bones.get(name)
        if pb is None:
            continue
        q = pb.rotation_quaternion
        out[name] = [round(q.w, 5), round(q.x, 5), round(q.y, 5), round(q.z, 5)]
    out["torso@loc"] = [round(c, 5) for c in rig.pose.bones["torso"].location]
    return out


def drop_torso(rig, dz, dy=0.0):
    """Move the torso control down by dz metres (world), e.g. to kneel; stored in the control's local space."""
    pb = rig.pose.bones["torso"]
    rest = (rig.matrix_world @ pb.bone.matrix_local).to_3x3().normalized()
    pb.location = rest.inverted() @ Vector((0.0, dy, -dz))
    bpy.context.view_layer.update()


def arms_down(rig, out=0.18, fwd=-0.08, elbow=12):
    for side, sx in (("L", 1), ("R", -1)):
        aim(rig, f"upper_arm_fk.{side}", (sx * out, fwd, -1))
        aim(rig, f"forearm_fk.{side}", (sx * out * 0.6, fwd - 0.25 * math.sin(math.radians(elbow)), -1))
        aim(rig, f"hand_fk.{side}", (sx * out * 0.4, fwd - 0.1, -1))


def build_poses(rig):
    """The pose library, posed by aiming FK controls at world directions on this very body (rig faces -Y)."""
    poses = {}
    reset_pose(rig)
    arms_down(rig)
    poses["stand"] = read_pose(rig)

    # talk: one forearm raised in front, the open hand turned up
    reset_pose(rig)
    arms_down(rig)
    aim(rig, "upper_arm_fk.R", (-0.25, -0.35, -1))
    aim(rig, "forearm_fk.R", (-0.15, -1.0, 0.25))
    aim(rig, "hand_fk.R", (-0.2, -1.0, 0.15))
    poses["talk"] = read_pose(rig)

    # point: the right arm out toward the camera's left
    reset_pose(rig)
    arms_down(rig)
    aim(rig, "upper_arm_fk.R", (-1.0, -0.6, 0.15))
    aim(rig, "forearm_fk.R", (-1.0, -0.7, 0.2))
    aim(rig, "hand_fk.R", (-1.0, -0.7, 0.2))
    poses["point"] = read_pose(rig)

    # look-hands: both hands held up before the chest, the head bowed to them
    reset_pose(rig)
    arms_down(rig)
    for side, sx in (("L", 1), ("R", -1)):
        aim(rig, f"upper_arm_fk.{side}", (sx * 0.15, -0.3, -1))
        aim(rig, f"forearm_fk.{side}", (-sx * 0.25, -1.0, 0.45))
        aim(rig, f"hand_fk.{side}", (-sx * 0.1, -1.0, 0.6))
    bend(rig, "neck", 14)
    bend(rig, "head", 14)
    poses["look-hands"] = read_pose(rig)

    # hold: both forearms forward as if carrying a bundle or a book
    reset_pose(rig)
    arms_down(rig)
    for side, sx in (("L", 1), ("R", -1)):
        aim(rig, f"upper_arm_fk.{side}", (sx * 0.1, -0.15, -1))
        aim(rig, f"forearm_fk.{side}", (-sx * 0.35, -1.0, 0.0))
        aim(rig, f"hand_fk.{side}", (-sx * 0.5, -1.0, 0.0))
    poses["hold"] = read_pose(rig)

    # leg lengths of this body, to bring the hips to the floor
    bones = rig.data.bones
    thigh = bones["ORG-thigh.L"].length if "ORG-thigh.L" in bones else bones["DEF-thigh.L"].length
    shin = bones["ORG-shin.L"].length if "ORG-shin.L" in bones else bones["DEF-shin.L"].length

    # kneel: thighs straight down, shins flat behind, upper body a little forward, hands on the thighs
    reset_pose(rig)
    drop_torso(rig, shin * 0.95)
    for side, sx in (("L", 1), ("R", -1)):
        aim(rig, f"thigh_fk.{side}", (sx * 0.08, -0.12, -1))
        aim(rig, f"shin_fk.{side}", (sx * 0.02, 1.0, -0.08))
        aim(rig, f"foot_fk.{side}", (0.0, 1.0, 0.25))
    bend(rig, "spine_fk.001", 8)
    arms_down(rig, out=0.12, fwd=-0.25, elbow=25)
    poses["kneel"] = read_pose(rig)

    # sit: on a bench at knee height, thighs forward, shins down, hands on the knees
    reset_pose(rig)
    drop_torso(rig, thigh * 0.95, dy=0.0)
    for side, sx in (("L", 1), ("R", -1)):
        aim(rig, f"thigh_fk.{side}", (sx * 0.12, -1.0, -0.08))
        aim(rig, f"shin_fk.{side}", (sx * 0.02, -0.12, -1))
        aim(rig, f"foot_fk.{side}", (0.0, -1.0, -0.35))
        aim(rig, f"upper_arm_fk.{side}", (sx * 0.12, -0.5, -1))
        aim(rig, f"forearm_fk.{side}", (sx * 0.05, -1.0, -0.35))
    poses["sit"] = read_pose(rig)
    reset_pose(rig)
    print("HUMAN3D_POSES", sorted(poses))
    return poses


def build_walk(rig, poses, fps=30, cycle=1.1):
    """One walk cycle as an action named "walk": thighs swing, knees bend on the passing leg, arms swing
    against the legs. Cyclic F-modifiers make it repeat for as long as an NLA strip asks."""
    frames = int(round(cycle * fps))
    reset_pose(rig)
    rig.animation_data_create()
    act = bpy.data.actions.new("walk")
    rig.animation_data.action = act
    for f in range(0, frames + 1, 3):
        ph = 2 * math.pi * f / frames
        reset_pose(rig)
        arms_down(rig)
        for side, sx, off in (("L", 1, 0.0), ("R", -1, math.pi)):
            s = math.sin(ph + off)
            knee = max(0.0, math.sin(ph + off + 1.4))
            aim(rig, f"thigh_fk.{side}", (sx * 0.04, -0.42 * s, -1))
            aim(rig, f"shin_fk.{side}", (sx * 0.02, -0.42 * s + 0.75 * knee, -1))
            aim(rig, f"foot_fk.{side}", (0.0, -1.0, -0.25 + 0.6 * knee))
            aim(rig, f"upper_arm_fk.{side}", (sx * 0.16, 0.3 * s, -1))
            aim(rig, f"forearm_fk.{side}", (sx * 0.1, 0.3 * s - 0.25, -1))
        for name in FK:
            pb = rig.pose.bones.get(name)
            if pb is not None and name != "torso":
                pb.keyframe_insert("rotation_quaternion", frame=f + 1)
    for fc in act.fcurves:
        fc.modifiers.new("CYCLES")
    act.use_fake_user = True
    rig.animation_data.action = None
    reset_pose(rig)
    print("HUMAN3D_WALK", frames, "frames")
    return act


# ---------------------------------------------------------------------------------------------- one character

def build(who, variant, assets, out_dir):
    spec = ROLES[who]
    rng = random.Random(f"{who}-{variant}")
    start_blender()
    hs, rs, ts, cs, ls, Mhclo = services()
    body, macro = build_body(spec, rng, hs, ts)
    body.name = f"mb_{who}"

    meta = hs.add_builtin_rig(body, "rigify.human")
    rig = rs.generate_rigify_rig(meta, meta_rig_action="delete")
    rig.name = f"{who}_rig"
    dedupe_armature_modifiers(body, rig)

    skin = rng.choice(spec["skin"])
    hs.set_character_skin(str(find_asset(assets, "skins", skin)), body, skin_type="ENHANCED_SSS")

    hair_name, hair_col = rng.choice(spec["hair"])
    hair_rgb = HAIR_COLOURS[hair_col]
    proxies = []

    def add(kind, name, tint=None):
        path = find_asset(assets, kind if kind != "clothes" else "clothes", name)
        atype = ASSET_KIND.get(kind, "Clothes")
        ob = hs.add_mhclo_asset(str(path), body, asset_type=atype, subdiv_levels=0, material_type="MAKESKIN")
        dedupe_armature_modifiers(ob, rig)
        if tint is not None:
            tint_material(ob, tint)
        return ob, path

    eyes = hs.add_mhclo_asset(str(find_asset(assets, "eyes", "high-poly")), body, asset_type="Eyes",
                              subdiv_levels=0, material_type="PROCEDURAL_EYES")
    dedupe_armature_modifiers(eyes, rig)
    set_iris(eyes, EYE_COLOURS[rng.choice(spec["eyes"])])
    add("teeth", "teeth_base")
    proxies.append(add("eyebrows", rng.choice(spec["eyebrows"]), tint=tuple(c * 0.8 for c in hair_rgb)))
    proxies.append(add("eyelashes", rng.choice(["eyelashes01", "eyelashes02", "eyelashes04"])))
    hair, _ = add("hair", hair_name)
    hair_material(hair, hair_rgb)
    beard = rng.choice(spec.get("beard") or [None])
    if beard:
        bname, bcol = beard
        ob, path = add("clothes", bname)
        hair_material(ob, hair_rgb if bcol == "hair" else HAIR_COLOURS[bcol])
        proxies.append((ob, path))
    outfit = rng.choice(spec["outfits"]) if "outfits" in spec else spec["clothes"]
    worn = []
    for name, tint in outfit:
        ob, path = add("clothes", name, pick_tint(tint, rng, hair_rgb))
        opaque(ob)
        worn.append((zdepth(path), ob))
    # inner layers lose what the outer ones cover (shoes and hats are left alone: they cover nothing)
    worn.sort(key=lambda t: t[0])
    for i, (_, inner) in enumerate(worn):
        if any(k in inner.name for k in ("boots", "bonnet", "hat")):
            continue
        for _, outer in worn[i + 1:]:
            if not any(k in outer.name for k in ("boots", "bonnet", "hat")):
                hide_covered(inner, outer)

    add_face_keys(body, ts)
    face_keys_on_proxies(body, proxies, cs, Mhclo)

    poses = build_poses(rig)
    rig["human3d_poses"] = json.dumps(poses)
    rig["human3d_variant"] = variant
    rig["human3d_phenotype"] = json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in macro.items()})
    build_walk(rig, poses)

    # tidy: no widgets in view, every part follows the rig, nothing selectable but the rig
    for ob in bpy.data.objects:
        if ob.type == "MESH" and ob.name.startswith("WGT-"):
            ob.hide_render = True
    for ob in bpy.data.objects:
        if ob.type == "MESH" and not ob.name.startswith("WGT-") and ob.parent is None:
            ob.parent = rig
    bpy.context.preferences.filepaths.use_relative_paths = False
    for im in bpy.data.images:
        if im.filepath and not im.packed_file:
            im.filepath = bpy.path.abspath(im.filepath)
    out = out_dir / (f"{who}.blend" if variant == 1 else f"{who}.{variant}.blend")
    out.parent.mkdir(parents=True, exist_ok=True)
    # absolute texture paths: the file is appended into scenes saved elsewhere (or never saved)
    bpy.ops.wm.save_as_mainfile(filepath=str(out), check_existing=False, compress=True, relative_remap=False)
    height = max((rig.matrix_world @ v.co).z for v in body.data.vertices)
    print(f"HUMAN3D_SAVED {out} rig={rig.name} rig_id={rig.data.get('rig_id')} "
          f"keys={len(body.data.shape_keys.key_blocks)} height={height:.2f} outfit={[n for n, _ in outfit]}")
    return out


# ---------------------------------------------------------------------------------------------- lineup render

def render_sheet(files, path, samples):
    """Every built file side by side, standing, under soft daylight; Cycles on the CPU."""
    sys.path.insert(0, str(Path(__file__).resolve().parent / "models"))
    import human3d
    bpy.ops.wm.read_factory_settings(use_empty=True)
    import addon_utils
    addon_utils.enable("rigify", default_set=True)
    scene = bpy.context.scene
    coll = scene.collection
    gap = 0.75
    x0 = -gap * (len(files) - 1) / 2
    for i, f in enumerate(files):
        who = f.stem
        inst = human3d.instance(who, f.parent, f"sheet-{i}", coll)
        rig = inst["rig"]
        rig.location = (x0 + i * gap, 0, 0)
        pose = ["stand", "talk", "look-hands", "hold", "point"][i % 5] if len(files) > 6 else "stand"
        human3d.set_pose(inst, pose, 1)
        human3d.set_face(inst, ["neutral", "smile", "worried"][i % 3], 1)
    scene.frame_set(1)
    floor = bpy.data.objects.new("floor", bpy.data.meshes.new("floor"))
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=30)
    bm.to_mesh(floor.data)
    coll.objects.link(floor)
    fm = bpy.data.materials.new("floor")
    fm.use_nodes = True
    fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.35, 0.32, 0.28, 1)
    floor.data.materials.append(fm)
    world = bpy.data.worlds.new("w")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.55, 0.58, 0.62, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6
    scene.world = world
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 3.0
    sun.data.angle = math.radians(12)
    sun.rotation_euler = (math.radians(50), math.radians(-10), math.radians(-30))
    coll.objects.link(sun)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    width = gap * len(files) + 0.6
    cam.data.lens = 50
    dist = max(4.0, width * 1.25)
    cam.location = (0, -dist, 1.05)
    cam.rotation_euler = (math.radians(88), 0, 0)
    coll.objects.link(cam)
    scene.camera = cam
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x = max(1280, int(260 * len(files)))
    scene.render.resolution_y = 900
    scene.view_settings.view_transform = "AgX"
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    print("HUMAN3D_SHEET", path)


def main():
    args = parse(sys.argv[sys.argv.index("--") + 1:])
    assets = args.assets.resolve()
    out_dir = args.out.resolve()
    built = []
    for who in args.who or list(ROLES):
        for v in range(1, args.variants + 1):
            built.append(build(who, v, assets, out_dir))
    if args.sheet:
        render_sheet(built, args.sheet.resolve(), args.samples)


if __name__ == "__main__":
    main()
