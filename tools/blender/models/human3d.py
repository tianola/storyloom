"""Rigged 3D people for the storyboard renderer.

Each person is a dressed MPFB2 (MakeHuman) character built by tools/blender/human3d_mpfb.py, in several
variants per role (work/<episode>/human3d/<who>.blend, <who>.2.blend, ...); the older CharMorph builds of
human3d_build.py and human3d_poses.py follow the same contract. A cast entry with "render": "3d" uses this module instead of the 2D
sprites in characters.py:

  load_template(who, built_dir)  append the character once per Blender run (hidden)
  instance(who, built_dir, name) copy it (rig, body, garments, hair), so every cast member has its own pose
  set_pose(inst, pose, frame)     FK pose from the library (stand, sit, kneel), keyed at a frame
  play_walk(inst, start_frame)    the baked walk clip, as an NLA strip from a frame
  set_face(inst, face, frame)     expression shape keys
  talk(inst, visemes, fps)        mouth shapes from mouth_timing.json, keyed in beat time
  show(inst, f0, f1, total)       visible only while the cast member is in its shot

Nothing here knows the camera: storyboard_beats.place_human3d decides the foot point and the height.
"""
import json
from pathlib import Path

import bpy

# mouth_timing.json shapes -> expression shape keys (CharMorph's 83 expression keys, male and female alike)
MOUTH = {
    "rest": (None, 0.0),
    "closed": ("Exp_mouthClosed_max", 1.0),
    "half": ("Exp_mouthOpenHalf_max", 1.0),
    "open": ("Exp_mouthOpen_max", 1.0),
    "wide": ("Exp_mouthOpenLarge_max", 0.8),
}
FACE = {
    "neutral": {},
    "worried": {"Exp_browSqueezeL_max": 0.5, "Exp_browSqueezeR_max": 0.5, "Exp_browsMidVert_max": 0.3},
    "sad": {"Exp_browsMidVert_max": 0.6, "Exp_mouthSmile_min": 0.4},
    "shocked": {"Exp_browOutVertL_max": 0.7, "Exp_browOutVertR_max": 0.7, "Exp_mouthOpenO_max": 0.6},
    "angry": {"Exp_browSqueezeL_max": 0.9, "Exp_browSqueezeR_max": 0.9},
    "smile": {"Exp_mouthSmile_max": 0.8},
}
ALL_FACE_KEYS = sorted({k for face in FACE.values() for k in face} | {v[0] for v in MOUTH.values() if v[0]})
IK_SWITCHES = ["upper_arm_parent.L", "upper_arm_parent.R", "thigh_parent.L", "thigh_parent.R"]

TEMPLATES = {}
USED = {}   # role -> how many cast members of that role this beat has placed, to hand out the variants in turn


def reset():
    """A new beat: forget the templates (they belonged to the last scene) and start the variants again."""
    TEMPLATES.clear()
    USED.clear()


def variants(who, built_dir):
    """The built files of a role: <who>.blend, then <who>.2.blend, <who>.3.blend ... (human3d_mpfb.py)."""
    d = Path(built_dir)
    out = [who] if (d / f"{who}.blend").exists() else []
    k = 2
    while (d / f"{who}.{k}.blend").exists():
        out.append(f"{who}.{k}")
        k += 1
    return out or [who]


def pick_variant(who, built_dir, variant=None):
    """`variant` (1-based) when the storyboard names one, otherwise the next one in turn for this beat; the
    first cast member of a role is always variant 1, so a named person looks the same in every beat."""
    names = variants(who, built_dir)
    if variant:
        return names[(int(variant) - 1) % len(names)]
    n = USED.get(who, 0)
    USED[who] = n + 1
    return names[n % len(names)]


def _rig_of(objects):
    return next(o for o in objects if o.type == "ARMATURE" and o.data.get("rig_id"))


def _body_of(objects):
    return next(o for o in objects if o.type == "MESH" and o.name.startswith("mb_") and o.data.shape_keys)


def load_template(who, built_dir):
    """Append the built character once per Blender run. The template stays hidden; copies are placed."""
    if who in TEMPLATES:
        return TEMPLATES[who]
    path = Path(built_dir) / f"{who}.blend"
    if not path.exists():
        raise FileNotFoundError(f"3D character not built: {path} (run tools/blender/human3d_build.py)")
    with bpy.data.libraries.load(str(path), link=False) as (src, dst):
        dst.objects = [n for n in src.objects if not n.startswith("WGT-") and n not in ("Camera", "Light", "Cube")]
        dst.actions = [n for n in src.actions if n == "walk"]
    objects = [o for o in dst.objects if o is not None]
    coll = bpy.data.collections.get("human3d_templates") or bpy.data.collections.new("human3d_templates")
    if coll.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(coll)
    for o in objects:
        if o.name not in coll.objects:
            coll.objects.link(o)
        o.hide_render = True
        o.hide_viewport = True
    rig = _rig_of(objects)
    body = _body_of(objects)
    skin_look(objects)
    walk = next((a for a in dst.actions if a is not None), None)
    poses = json.loads(rig["human3d_poses"]) if "human3d_poses" in rig.keys() else {}
    TEMPLATES[who] = {"rig": rig, "body": body, "parts": [o for o in objects if o.type == "MESH"],
                      "poses": poses, "walk": walk}
    return TEMPLATES[who]


# MPFB's skin group as built reads as wax at film distance: strong subsurface, a clear coat and an even
# roughness. Skin that reads as skin is drier and less translucent, with the pores (its roughness and bump
# noise) stronger; lips and ears a touch redder; the eyes' outer layer a wet, sharp coat that catches light.
SKIN = {"SSS strength": 0.12, "SSS radius scale": 0.25, "Clearcoat": 0.0, "Roughness": 0.5, "Pore strength": 0.22,
        "Pore scale": 2600.0, "Contrast": 0.05}
SKIN_PART = {"lips": {"colorMixInStrength": 0.2, "Roughness": 0.38},
             "ears": {"colorMixInStrength": 0.12}}
EYES = {"Clearcoat": 1.0, "Clearcoat Roughness": 0.02, "OuterLayerRoughness": 0.0}


def _asset_roots():
    """MakeHuman asset folders this Blender session knows of: the repo's own, and wherever the built
    characters' textures were loaded from (the .blend files store absolute paths)."""
    roots = [Path(__file__).resolve().parents[3] / "assets" / "makehuman"]
    for img in bpy.data.images:
        p = Path(bpy.path.abspath(img.filepath)) if img.filepath else None
        if p is not None and "makehuman" in p.parts:
            roots.append(Path(*p.parts[:p.parts.index("makehuman") + 1]))
    return roots


def _eye_texture(iris):
    """The MakeHuman (CC0) eye texture nearest to an iris colour from the built procedural eye."""
    r, g, b = iris[:3]
    name = "blue" if b > r * 1.1 else "green" if g > r and g > b else "grey" if max(r, g, b) < 0.08 else \
        "brownlight" if r > 0.25 else "brown"
    for root in _asset_roots():
        f = root / "eyes" / "materials" / f"{name}_eye.png"
        if f.is_file():
            return f
    return None


def _real_eye(m, group):
    """Replace MPFB's procedural eye (its node group does not build cleanly in Blender 4.5: the iris comes
    out as a flat glowing disc) with the MakeHuman eye texture under a wet, sharp clear coat: a real iris
    pattern, a pupil, a sclera that is not pure white, and a catchlight from whatever lights the face."""
    iris = tuple(group.inputs["IrisMajorColor"].default_value) if "IrisMajorColor" in group.inputs else (0.2, 0.1, 0.05)
    tex = _eye_texture(iris)
    if tex is None:
        return False
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    img = nt.nodes.new("ShaderNodeTexImage")
    img.image = bpy.data.images.load(str(tex), check_existing=True)
    tint = nt.nodes.new("ShaderNodeMixRGB")          # the sclera a touch warm and shadowed, never paper white
    tint.blend_type = "MULTIPLY"
    tint.inputs["Fac"].default_value = 1.0
    tint.inputs["Color2"].default_value = (0.86, 0.80, 0.76, 1.0)
    nt.links.new(img.outputs["Color"], tint.inputs["Color1"])
    nt.links.new(tint.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(img.outputs["Alpha"], bsdf.inputs["Alpha"])
    bsdf.inputs["Roughness"].default_value = 0.35
    for key, value in (("Coat Weight", 1.0), ("Coat Roughness", 0.02), ("Coat IOR", 1.376)):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = value
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    m.surface_render_method = "DITHERED"
    return True


def _cloth_wrinkles(m):
    """Fabric that is not a smooth shell: a fine weave and soft, uneven creases as a bump on the cloth's
    normal (garments that bring their own normal map keep it)."""
    bsdf = next((n for n in m.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
    if bsdf is None or bsdf.inputs["Normal"].is_linked:
        return
    nt = m.node_tree
    coord = nt.nodes.new("ShaderNodeTexCoord")
    creases = nt.nodes.new("ShaderNodeTexWave")
    creases.wave_type = "BANDS"
    creases.inputs["Scale"].default_value = 3.0
    creases.inputs["Distortion"].default_value = 9.0
    creases.inputs["Detail"].default_value = 3.0
    weave = nt.nodes.new("ShaderNodeTexNoise")
    weave.inputs["Scale"].default_value = 900.0
    nt.links.new(coord.outputs["Object"], creases.inputs["Vector"])
    nt.links.new(coord.outputs["Object"], weave.inputs["Vector"])
    big = nt.nodes.new("ShaderNodeBump")
    big.inputs["Strength"].default_value = 0.35
    big.inputs["Distance"].default_value = 0.02
    fine = nt.nodes.new("ShaderNodeBump")
    fine.inputs["Strength"].default_value = 0.15
    fine.inputs["Distance"].default_value = 0.002
    nt.links.new(creases.outputs["Fac"], big.inputs["Height"])
    nt.links.new(weave.outputs["Fac"], fine.inputs["Height"])
    nt.links.new(big.outputs["Normal"], fine.inputs["Normal"])
    nt.links.new(fine.outputs["Normal"], bsdf.inputs["Normal"])
    # a real weave where one is on disk: a CC0 Poly Haven fabric normal map under the creases (wool for
    # coats, herringbone suiting for suits and trousers, linen for blouses, aprons, dresses and skirts)
    weave_tex = _fabric_normal(m.name)
    if weave_tex is not None:
        mapping = nt.nodes.new("ShaderNodeMapping")
        mapping.inputs["Scale"].default_value = (7.0, 7.0, 7.0)          # a tile every ~14 cm
        nt.links.new(coord.outputs["Object"], mapping.inputs["Vector"])
        img = nt.nodes.new("ShaderNodeTexImage")
        img.image = bpy.data.images.load(str(weave_tex), check_existing=True)
        img.image.colorspace_settings.name = "Non-Color"
        img.projection = "BOX"
        img.projection_blend = 0.3
        nt.links.new(mapping.outputs["Vector"], img.inputs["Vector"])
        nmap = nt.nodes.new("ShaderNodeNormalMap")
        nmap.inputs["Strength"].default_value = 0.6
        nt.links.new(img.outputs["Color"], nmap.inputs["Color"])
        nt.links.new(nmap.outputs["Normal"], big.inputs["Normal"])
        nt.nodes.remove(fine)
        nt.links.new(big.outputs["Normal"], bsdf.inputs["Normal"])


FABRICS = [(("coat",), "caban"), (("suit", "pants", "trousers", "jacket"), "poly_wool_herringbone"),
           (("blouse", "apron", "dress", "skirt", "shirt", "bonnet"), "rough_linen")]


def _fabric_normal(material_name):
    """The CC0 fabric normal map for a garment, by the words in its material name, or None."""
    name = material_name.lower()
    try:
        import assets
    except ImportError:
        return None
    for words, tex in FABRICS:
        if any(w in name for w in words):
            files = assets.texture_files(tex)
            return files["nor"] if files and files.get("nor") else None
    return None
    if not bsdf.inputs["Roughness"].is_linked:
        bsdf.inputs["Roughness"].default_value = max(0.75, bsdf.inputs["Roughness"].default_value)
    if "Sheen Weight" in bsdf.inputs:
        bsdf.inputs["Sheen Weight"].default_value = 0.35     # cotton and wool catch a soft sheen at grazing light


def _hair_look(m):
    """Hair cards that read less like a painted cap: a soft anisotropic sheen along the strands, a little
    light through the thin edges, a matte top."""
    bsdf = next((n for n in m.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
    if bsdf is None:
        return
    for key, value in (("Roughness", 0.42), ("Anisotropic", 0.7), ("Subsurface Weight", 0.15),
                       ("Specular IOR Level", 0.35), ("Sheen Weight", 0.2)):
        if key in bsdf.inputs and not bsdf.inputs[key].is_linked:
            bsdf.inputs[key].default_value = value


def skin_look(objects):
    """Tune the MPFB skin, eye, hair and cloth shaders of a loaded character (its materials, once per
    template)."""
    for ob in objects:
        if ob.type != "MESH":
            continue
        for slot in ob.material_slots:
            m = slot.material
            if m is None or not m.use_nodes or m.get("human3d_skin"):
                continue
            part = next((p for p in reversed(m.name.split(".")) if not p.isdigit()), "")
            groups = [n for n in m.node_tree.nodes if n.bl_idname == "ShaderNodeGroup" and n.node_tree is not None]
            for node in groups:
                if "SSS strength" in node.inputs:
                    for key, value in dict(SKIN, **SKIN_PART.get(part, {})).items():
                        if key in node.inputs and not node.inputs[key].is_linked:
                            node.inputs[key].default_value = value
                elif "OuterLayerRoughness" in node.inputs:
                    if not _real_eye(m, node):
                        for key, value in EYES.items():
                            if key in node.inputs:
                                node.inputs[key].default_value = value
                    break
            if not groups:
                kind = part.lower()
                if any(k in kind for k in ("short", "hair", "bun", "braid", "ponytail", "beard")):
                    _hair_look(m)
                elif not any(k in kind for k in ("eyebrow", "eyelash", "teeth", "tongue", "boots")):
                    _cloth_wrinkles(m)
            m["human3d_skin"] = True


def instance(who, built_dir, name, collection, variant=None):
    """A copy of the character for one cast member: rig, body, garments and hair, all linked and re-pointed.
    Roles built in several variants (human3d_mpfb.py) hand them out in turn, see pick_variant."""
    if "." not in who:
        who = pick_variant(who, built_dir, variant)
    t = load_template(who, built_dir)
    mapping = {}
    rig = t["rig"].copy()
    rig.name = f"{name}_rig"
    collection.objects.link(rig)
    mapping[t["rig"]] = rig
    for part in t["parts"]:
        p = part.copy()
        p.data = part.data.copy()
        p.name = f"{name}_{part.name}"
        collection.objects.link(p)
        mapping[part] = p
    for old, new in mapping.items():
        if old.type == "MESH":
            # garments and hair are not children of the rig in the built file; here every part follows the rig,
            # so the whole costume moves and scales with the person
            new.parent = mapping.get(old.parent, rig) if old.parent is not None else rig
            new.matrix_parent_inverse.identity()
            for m in new.modifiers:
                if m.type == "ARMATURE" and m.object in mapping:
                    m.object = mapping[m.object]
                if m.type == "SHRINKWRAP" and m.target in mapping:
                    m.target = mapping[m.target]
    for new in mapping.values():
        new.hide_render = False
        new.hide_viewport = False
    body = mapping[t["body"]]
    return {"rig": rig, "body": body, "parts": [mapping[p] for p in t["parts"]], "poses": t["poses"], "walk": t["walk"]}


def stature(inst):
    """Standing height of the character at rig scale 1: the top of its body mesh (feet are at z=0)."""
    body = inst["body"]
    top = max((body.matrix_parent_inverse @ __import__("mathutils").Vector(c)).z for c in body.bound_box)
    return top if top > 0.5 else 1.75


def size_jitter(n):
    """A small size change per cast member (about +-3 %), so two people of one role and variant still differ."""
    return 1.0 + ((n * 37 + 11) % 7 - 3) * 0.01


def _key_pose_bone(pb, frame):
    pb.keyframe_insert("rotation_quaternion", frame=frame)


# the CharMorph kneel clip (CMU 23_03) retargets badly onto the rig, so there a kneel is the seated pose;
# the MPFB characters have a kneel of their own
POSE_STAND_IN = {"kneel": "sit"}

# the MPFB "point" pose lifts the arm about 65 degrees out from the body; the coats and blouses are weighted
# for a hanging arm, so the sleeve stretches into a fin. A pointing arm held lower (the fraction of the
# library rotation kept) keeps the cloth on the arm and still reads as a gesture
SOFTEN = {"point": {"upper_arm_fk.R": 0.55, "upper_arm_fk.L": 0.6, "forearm_fk.R": 0.8}}


def _toward_rest(q, keep):
    """The rotation `q` (w, x, y, z) scaled to `keep` of its angle (a slerp toward the rest pose)."""
    import math
    w, x, y, z = q
    w = max(-1.0, min(1.0, w))
    angle = 2 * math.acos(abs(w))
    s = math.sqrt(max(1e-12, 1 - w * w))
    if angle < 1e-6:
        return q
    sign = 1.0 if w >= 0 else -1.0
    half = angle * keep / 2
    return [math.cos(half), sign * x / s * math.sin(half), sign * y / s * math.sin(half),
            sign * z / s * math.sin(half)]


def set_pose(inst, pose, frame):
    """Pose from the library; a pose without its own entry uses its stand-in, then the standing pose."""
    rig = inst["rig"]
    library = inst["poses"]
    if pose not in library:
        pose = POSE_STAND_IN.get(pose, pose)
    entry = library.get(pose) or library.get("stand") or {}
    if "torso@loc" not in entry and any(k.endswith("@loc") for e in library.values() for k in e):
        entry = dict(entry, **{"torso@loc": [0.0, 0.0, 0.0]})
    for name in IK_SWITCHES:
        pb = rig.pose.bones.get(name)
        if pb is not None:
            pb["IK_FK"] = 1.0
            pb.keyframe_insert('["IK_FK"]', frame=frame)
    soften = SOFTEN.get(pose, {})
    for ctrl, q in entry.items():
        if ctrl in soften:
            q = _toward_rest(q, soften[ctrl])
        if ctrl.endswith("@loc"):
            # a control's location (MPFB poses lower the torso to kneel and sit)
            pb = rig.pose.bones.get(ctrl[:-4])
            if pb is not None:
                pb.location = q
                pb.keyframe_insert("location", frame=frame)
            continue
        pb = rig.pose.bones.get(ctrl)
        if pb is None:
            continue
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = q
        _key_pose_bone(pb, frame)


def play_walk(inst, start_frame):
    """The baked walk clip as an NLA strip starting at `start_frame` (the standing pose is replaced meanwhile)."""
    rig = inst["rig"]
    if inst["walk"] is None:
        return
    # the clip's vertical hip bob lifts the figure off the floor in this rig (its torso control is not
    # vertical), so the test walk keeps the leg and arm cycle and drops the torso translation
    for fc in list(inst["walk"].fcurves):
        if fc.data_path == 'pose.bones["torso"].location':
            inst["walk"].fcurves.remove(fc)
    if rig.animation_data is None:
        rig.animation_data_create()
    # the active action (the poses keyed by set_pose) is evaluated over the NLA and would hold the legs still:
    # the bones the clip moves are left to the clip
    walked = {fc.data_path for fc in inst["walk"].fcurves}
    act = rig.animation_data.action
    if act is not None:
        for fc in list(act.fcurves):
            if fc.data_path in walked:
                act.fcurves.remove(fc)
    track = rig.animation_data.nla_tracks.new()
    strip = track.strips.new("walk", int(start_frame), inst["walk"])
    if any(m.type == "CYCLES" for fc in inst["walk"].fcurves for m in fc.modifiers):
        strip.repeat = 60   # a one-cycle clip (human3d_mpfb.py) repeats for the rest of the shot
    strip.extrapolation = "HOLD_FORWARD"


def _key_sets(inst):
    """The body's shape keys, then those of the parts that carry the same face keys (MPFB eyebrows,
    eyelashes and beards), so the brows move with the forehead."""
    out = [inst["body"].data.shape_keys.key_blocks]
    for p in inst["parts"]:
        if p is not inst["body"] and p.data.shape_keys is not None:
            out.append(p.data.shape_keys.key_blocks)
    return out


def set_face(inst, face, frame):
    """Expression shape keys for `face`, keyed at `frame`; everything else in the face set to zero. A
    face is never quite symmetric: one side's keys are scaled a little (per person, from its rig name)."""
    wanted = FACE.get(face or "neutral", {})
    lean = 0.8 + 0.15 * ((sum(map(ord, inst["rig"].name)) * 37) % 100) / 100.0
    side = "R" if sum(map(ord, inst["rig"].name)) % 2 else "L"
    for keys in _key_sets(inst):
        for name in ALL_FACE_KEYS:
            kb = keys.get(name)
            if kb is None:
                continue
            value = wanted.get(name, 0.0)
            if name.endswith(f"{side}_max"):
                value *= lean
            kb.value = value
            kb.keyframe_insert("value", frame=frame)


# the face is never still: the brows lift and settle a little, one more than the other, and the corners
# of the mouth move (noise on the expression keys over whatever face is keyed)
FACE_IDLE = [("Exp_browsMidVert_max", 0.16, 3.0), ("Exp_browOutVertL_max", 0.10, 4.5),
             ("Exp_browOutVertR_max", 0.07, 5.5), ("Exp_mouthSmile_max", 0.05, 6.0)]


def face_idle(inst, seed, fps):
    import random
    rnd = random.Random(seed * 271 + 9)
    phases = {name: rnd.uniform(0, 1000) for name, _, _ in FACE_IDLE}
    for p in [inst["body"]] + [q for q in inst["parts"] if q is not inst["body"]]:
        sk = p.data.shape_keys
        if sk is None or sk.animation_data is None or sk.animation_data.action is None:
            continue
        for name, strength, period in FACE_IDLE:
            fc = sk.animation_data.action.fcurves.find(f'key_blocks["{name}"].value')
            if fc is None:
                if sk.key_blocks.get(name) is None:
                    continue
                sk.key_blocks[name].keyframe_insert("value", frame=1)
                fc = sk.animation_data.action.fcurves.find(f'key_blocks["{name}"].value')
                if fc is None:
                    continue
            m = fc.modifiers.new("NOISE")
            m.blend_type = "REPLACE"
            m.scale = period * fps
            m.strength = strength
            m.phase = phases[name]       # the same phase on body, brows and lashes: they move as one face
            m.offset = 0.0


def gaze(inst, yaw, pitch, spans=None, fps=30, seed=0):
    """Turn the head (and a little of the neck) by `yaw` radians (positive = to the person's left) and tip it
    down by `pitch`, as a layer over the pose and the idle head motion. Without `spans` the look holds for
    the whole shot (someone reading, someone at a board). With `spans` ([(f0, f1)] frames, when the one
    looked at speaks) the person turns toward the speaker a moment after the speaker starts, the head
    leading and the neck following a few frames behind, holds, and turns back after the line, all eased.
    Returns the frames at which the head starts to turn (a blink goes there)."""
    import math
    import random
    rig = inst["rig"]
    act = rig.animation_data.action if rig.animation_data else None
    if act is None:
        return []
    rnd = random.Random(seed * 409 + 3)
    yaw = max(-1.05, min(1.05, yaw))
    pitch = max(-0.35, min(0.5, pitch))
    turns = []
    windows = [(None, None)] if not spans else []
    for f0, f1 in spans or []:
        delay = round(rnd.uniform(0.25, 0.7) * fps)            # listeners react, never on the same frame
        windows.append((f0 + delay, f1 + round(rnd.uniform(0.4, 1.0) * fps)))
        turns.append(f0 + delay)
    # the eyes go first (eye_aim), the head a few frames later, then the neck, and last the shoulders follow
    # a part of the turn, so a look travels down the body instead of the head swivelling alone
    for bone, share, lag in (("head", 0.6, 3), ("neck", 0.3, 6), ("chest", 0.18, 10)):
        for axis, angle in ((2, yaw * share), (1, pitch * share if bone != "chest" else 0.0)):
            fc = act.fcurves.find(f'pose.bones["{bone}"].rotation_quaternion', index=axis)
            if fc is None or abs(angle) < 1e-4:
                continue
            for a, b in windows:
                m = fc.modifiers.new("FNGENERATOR")
                m.function_type = "SIN"
                m.amplitude = 0.0
                m.value_offset = math.sin(angle / 2)
                m.use_additive = True
                if a is not None:
                    m.use_restricted_range = True
                    m.frame_start = a + lag
                    m.frame_end = max(a + lag + 12, b + lag)
                    m.blend_in = min(9 + lag, (m.frame_end - m.frame_start) / 2 - 1)
                    m.blend_out = min(12, (m.frame_end - m.frame_start) / 2 - 1)
    eye_aim(inst, yaw * 0.4, pitch * 0.3, windows)
    return turns


def eye_aim(inst, yaw, pitch, windows):
    """The eyes turn to the target before the head does (they take the part of the look the head does not):
    the eye controls (eye.L, eye.R targets in front of the face) move sideways and down, keyed to arrive a
    few frames ahead of the head and to come back with it."""
    import math
    rig = inst["rig"]
    targets = [rig.pose.bones.get(n) for n in ("eye.L", "eye.R")]
    targets = [t for t in targets if t is not None]
    if not targets:
        return
    k = _scale(inst)
    # the targets sit about 0.13 m before the eyes in the rest pose; a shift of tan(angle) * that distance
    # turns the eyeball by the angle. Their local x is the character's x, local z is up
    dx = math.tan(max(-0.5, min(0.5, yaw))) * 0.13 * k      # a positive yaw looks toward +x (her left)
    dz = -math.tan(max(-0.3, min(0.3, pitch))) * 0.13 * k
    for a, b in windows:
        for pb in targets:
            frames = [(1, (0, 0, 0))] if a is None else [(max(1, a - 2), (0, 0, 0)), (a + 3, (dx, 0, dz)),
                                                         (max(a + 6, b), (dx, 0, dz)), (max(a + 9, b + 6), (0, 0, 0))]
            if a is None:
                frames = [(1, (dx, 0, dz))]
            for f, loc in frames:
                pb.location = loc
                pb.keyframe_insert("location", frame=f)


def nod(inst, pose, frame, fps, depth=0.055):
    """A small nod at `frame`: the head dips and comes back over about half a second (eased keys on the
    head's x channel, relative to the pose the person holds)."""
    rig = inst["rig"]
    act = rig.animation_data.action if rig.animation_data else None
    if act is None:
        return
    entry = inst["poses"].get(pose) or inst["poses"].get("stand") or {}
    base = entry.get("head", [1.0, 0.0, 0.0, 0.0])[1]
    fc = act.fcurves.find('pose.bones["head"].rotation_quaternion', index=1)
    if fc is None:
        return
    for df, v in ((0, base), (round(0.2 * fps), base + depth), (round(0.32 * fps), base + depth * 0.7),
                  (round(0.6 * fps), base)):
        fc.keyframe_points.insert(frame + df, v)


def word_beats(words, t0, t1, fps):
    """Frames of the stressed words inside [t0, t1]: content words of five letters or more, where a speaker's
    hands would move (a gesture lands just before the word it underlines)."""
    out = []
    for w in words:
        t = w.get("start", 0.0)
        text = "".join(ch for ch in w.get("word", "") if ch.isalpha())
        if t0 <= t <= t1 and len(text) >= 5:
            out.append(t)
    return out


def gestures(inst, spans, fps, base_pose, seed, stresses=()):
    """While a person speaks ([start, end] seconds per line), the hands underline the words: a gesture opens
    just before a stressed word (`stresses`, seconds) and is held through the phrase, the open-handed "talk"
    for explaining, the hands brought together for a point being weighed; in the pauses the arms settle back.
    No stressed word, no gesture: the hands stay down. Keys are eased, with a short anticipation (the arms
    dip toward rest before they rise) so a gesture does not start like a machine."""
    import random
    rnd = random.Random(seed * 3571 + 5)
    library = inst["poses"]
    choices = [p for p in ("talk", "talk", "look-hands") if p in library]   # point swings the arm out sideways
    if not choices:
        return
    for t0, t1 in spans:
        marks = [t for t in stresses if t0 <= t <= t1] or [t0 + 0.3]
        last_end = -1.0
        for t in marks:
            if t < last_end + 0.4:
                continue                                   # still inside the last gesture
            start = max(t0, t - 0.35)
            end = min(t1, t + rnd.uniform(1.4, 2.4))
            pose = rnd.choice(choices)
            f_in = max(2, round(start * fps) + 1)
            set_pose(inst, base_pose, max(1, f_in - round(0.2 * fps)))        # anticipation: from rest
            set_pose(inst, pose, f_in + round(0.3 * fps))
            set_pose(inst, pose, max(f_in + round(0.35 * fps), round(end * fps)))
            set_pose(inst, base_pose, round(end * fps) + round(0.45 * fps))   # settle
            last_end = end + 0.45


# a hand at rest is never flat: the fingers curl a little, more toward the little finger, the thumb tucks in
FINGER_CURL = {"index": 10, "middle": 14, "ring": 18, "pinky": 22}
CURL_SIGN = 1.0


def relax_hands(inst, seed):
    import math
    import random
    rnd = random.Random(seed * 53 + 7)
    rig = inst["rig"]
    for side in ("L", "R"):
        for finger, deg in FINGER_CURL.items():
            for k, share in (("01", 0.6), ("02", 1.0), ("03", 0.8)):
                pb = rig.pose.bones.get(f"f_{finger}.{k}.{side}")
                if pb is None:
                    continue
                a = math.radians(deg * share * rnd.uniform(0.8, 1.25)) * CURL_SIGN
                pb.rotation_mode = "QUATERNION"
                pb.rotation_quaternion = (math.cos(a / 2), math.sin(a / 2), 0.0, 0.0)
                pb.keyframe_insert("rotation_quaternion", frame=1)
        for k, deg in (("02", 12), ("03", 10)):
            pb = rig.pose.bones.get(f"thumb.{k}.{side}")
            if pb is not None:
                a = math.radians(deg) * CURL_SIGN
                pb.rotation_mode = "QUATERNION"
                pb.rotation_quaternion = (math.cos(a / 2), math.sin(a / 2), 0.0, 0.0)
                pb.keyframe_insert("rotation_quaternion", frame=1)


# speakers' arms are never quite still between gestures either
ARM_IDLE = [("upper_arm_fk.L", 1), ("upper_arm_fk.R", 1), ("forearm_fk.L", 1), ("forearm_fk.R", 1),
            ("hand_fk.L", 3), ("hand_fk.R", 3)]


def arm_idle(inst, seed, fps, strength=0.05):
    import random
    rnd = random.Random(seed * 911 + 1)
    act = inst["rig"].animation_data.action if inst["rig"].animation_data else None
    if act is None:
        return
    for bone, axis in ARM_IDLE:
        fc = act.fcurves.find(f'pose.bones["{bone}"].rotation_quaternion', index=axis)
        if fc is None:
            continue
        m = fc.modifiers.new("NOISE")
        m.blend_type = "REPLACE"
        m.scale = rnd.uniform(1.5, 2.5) * fps
        m.strength = strength
        m.phase = rnd.uniform(0, 1000)


# mouth_timing.json marks whole phrases as one "half" or "open" stretch; a held open mouth reads as a gape,
# so inside each stretch the jaw opens and closes at syllable rate (about 4-6 a second), each syllable a
# little different, and the stretch's shape sets how far it opens
SYLLABLE = (0.13, 0.22)          # seconds per syllable, min and max
OPENING = {"half": ("Exp_mouthOpenHalf_max", 0.9), "open": ("Exp_mouthOpen_max", 0.75),
           "wide": ("Exp_mouthOpenLarge_max", 0.6)}
MOUTH_KEYS = sorted({name for name, _ in OPENING.values()})


def talk(inst, visemes, fps, seed=0):
    """Mouth motion from [shape, start, end] visemes in beat seconds: syllable flaps inside the spoken
    stretches, the mouth shut in the "rest" and "closed" ones. Each key set (body, brows, lashes) gets the
    same curve, so the face moves as one."""
    import random
    rnd = random.Random(seed * 7919 + len(visemes))
    keys_out = {}                 # shape key -> [(frame, value)]
    for shape, t0, t1 in visemes:
        f0 = max(1, round(t0 * fps) + 1)
        f1 = max(f0 + 1, round(t1 * fps) + 1)
        if shape not in OPENING:
            for name in MOUTH_KEYS:
                keys_out.setdefault(name, []).append((f0, 0.0))
            continue
        name, peak = OPENING[shape]
        t = t0
        while t < t1 - 0.06:
            step = rnd.uniform(*SYLLABLE)
            mid, end = t + step * 0.45, min(t1, t + step)
            keys_out.setdefault(name, []).append((round(mid * fps) + 1, peak * rnd.uniform(0.45, 1.0)))
            keys_out[name].append((round(end * fps) + 1, peak * rnd.uniform(0.0, 0.15)))
            for other in MOUTH_KEYS:
                if other != name:
                    keys_out.setdefault(other, []).append((round(mid * fps) + 1, 0.0))
            t = end
        keys_out.setdefault(name, []).append((f1, 0.0))
    for keys in _key_sets(inst):
        for name, points in keys_out.items():
            kb = keys.get(name)
            if kb is None:
                continue
            last = {}
            for frame, value in points:
                last[max(1, frame)] = value          # a later key on the same frame wins
            for frame in sorted(last):
                kb.value = last[frame]
                kb.keyframe_insert("value", frame=frame)


def blinks(inst, total, seed, fps, extra=()):
    """Blinks every 2.5-5.5 s (a quick double now and then), on the eyelid shape key of the body, brows
    and lashes; a seed per person so a group never blinks together."""
    import random
    rnd = random.Random(seed * 104729 + 17)
    t = rnd.uniform(0.3, 2.5)
    frames = []
    while t * fps < total:
        frames.append(round(t * fps) + 1)
        if rnd.random() < 0.15:
            frames.append(round((t + 0.35) * fps) + 1)
        t += rnd.uniform(2.5, 5.5)
    # a blink comes with a head turn (the eyes close as they move to the new target); none on top of another
    for f in extra:
        if 1 < f + 2 < total and all(abs(f + 2 - g) > 12 for g in frames):
            frames.append(f + 2)
    frames.sort()
    for keys in _key_sets(inst):
        kb = keys.get("Exp_eyesClosed_max")
        if kb is None:
            continue
        kb.value = 0.0
        kb.keyframe_insert("value", frame=1)
        for f in frames:
            for df, v in ((-1, 0.0), (1, 1.0), (2, 1.0), (5, 0.0)):
                kb.value = v
                kb.keyframe_insert("value", frame=max(1, f + df))


# subtle life on a person who is not walking, layered over whatever pose is keyed: F-curve modifiers on the
# quaternion x/y/z channels of the spine and head controls (Blender normalises pose quaternions, so a small
# offset there is a small extra rotation). (bone, axis, kind, amplitude, period in seconds):
#   breathing   the chest bends a little forward and back, about every 4 s
#   sway        the chest leans side to side and the hips roll the other way, slowly: a weight shift
#   head        a slow look left and right, a small nod and tilt
IDLE = [
    ("chest", 1, "sine", 0.010, 4.2),
    ("chest", 3, "noise", 0.030, 7.0),
    ("hips", 3, "noise", 0.016, 9.0),
    ("neck", 2, "noise", 0.040, 6.0),
    ("head", 2, "noise", 0.110, 5.0),
    ("head", 1, "noise", 0.050, 3.5),
    ("head", 3, "noise", 0.030, 6.5),
]


def idle(inst, seed, fps, walking=False):
    """Breathing, a weight shift and a wandering head, out of step with everyone else (seed per person).
    A walker keeps the clip's own body motion; only its head and breathing are added where the clip
    leaves those bones to the keyed pose."""
    import math
    import random
    rig = inst["rig"]
    act = rig.animation_data.action if rig.animation_data else None
    if act is None:
        return 0
    rnd = random.Random(seed * 6151 + 3)
    added = 0
    for bone, axis, kind, amp, period in IDLE:
        if walking and bone in ("hips", "chest") and kind == "noise":
            continue
        fc = act.fcurves.find(f'pose.bones["{bone}"].rotation_quaternion', index=axis)
        if fc is None:
            continue
        amp *= rnd.uniform(0.75, 1.25)
        if kind == "sine":
            m = fc.modifiers.new("FNGENERATOR")
            m.function_type = "SIN"
            m.amplitude = amp
            m.phase_multiplier = 2 * math.pi / (period * fps * rnd.uniform(0.85, 1.15))
            m.phase_offset = rnd.uniform(0, 2 * math.pi)
            m.use_additive = True
        else:
            m = fc.modifiers.new("NOISE")
            m.blend_type = "REPLACE"           # value + (noise - 0.5) * strength: centred on the pose
            m.scale = period * fps * rnd.uniform(0.8, 1.25)
            m.strength = 2 * amp
            m.phase = rnd.uniform(0, 1000)
            m.depth = 0
        added += 1
    return added


def show(inst, f0, f1, total):
    """Visible only from frame f0 to f1 (the cast member's shot)."""
    for ob in [inst["rig"]] + inst["parts"]:
        ob.hide_render = True
        ob.keyframe_insert("hide_render", frame=1)
        ob.hide_render = False
        ob.keyframe_insert("hide_render", frame=f0)
        if f1 < total:
            ob.hide_render = True
            ob.keyframe_insert("hide_render", frame=f1 + 1)
        ob.hide_render = False


# ---------------------------------------------------------------------------
# Hands that go somewhere: IK reaches for gestures with a meaning and for touching things
# ---------------------------------------------------------------------------
# Body landmarks in the armature's own space (the character faces -y), for a figure whose neck top (the head
# bone's root) is at 1.59 m; they are scaled to each character. The right hand is "R" (x < 0).
LANDMARKS = {
    "chest": (-0.05, -0.19, 1.30),        # the flat of the hand on the breastbone
    "mouth": (-0.02, -0.17, 1.51),        # the back of the fingers before the lips
    "clasp": (-0.02, -0.30, 1.12),        # hands held together before the body, pleading
    "explain": (-0.28, -0.34, 1.06),      # forearm forward, palm open to whoever listens
    "rest": (-0.24, -0.06, 0.86),         # beside the thigh
}
MIRROR = {"R": 1.0, "L": -1.0}


def _scale(inst):
    b = inst["rig"].data.bones.get("head")
    return (b.head_local.z / 1.59) if b is not None else 1.0


def landmark(inst, name, side="R"):
    """Armature-space point for a body landmark, mirrored for the left hand."""
    from mathutils import Vector
    x, y, z = LANDMARKS[name]
    k = _scale(inst)
    return Vector((x * MIRROR[side] * k, y * k, z * k))


def world_to_arm(inst, p):
    """A world point in the rig's armature space. The rig has no parent, so its matrix_basis (made from its
    location, rotation and scale as they are set now) is its world matrix even before the scene updates."""
    from mathutils import Vector
    return inst["rig"].matrix_basis.inverted() @ Vector(p)


def _key_ik(inst, side, value, frame):
    pb = inst["rig"].pose.bones.get(f"upper_arm_parent.{side}")
    if pb is not None:
        pb["IK_FK"] = value
        pb.keyframe_insert('["IK_FK"]', frame=frame)


def _key_hand(inst, side, arm_point, frame):
    """Put the IK hand control at an armature-space point (its rest orientation kept) and key it."""
    from mathutils import Matrix
    rig = inst["rig"]
    pb = rig.pose.bones.get(f"hand_ik.{side}")
    if pb is None:
        return
    import bpy as _bpy
    _bpy.context.scene.frame_set(frame)
    rest = pb.bone.matrix_local.copy()
    rest.translation = arm_point
    # Blender works out the local offset from the armature-space matrix, whatever the parent chain does
    pb.matrix = rest
    _bpy.context.view_layer.update()
    import os as _os
    if _os.environ.get("DEBUG_IK"):
        got = rig.matrix_world @ pb.matrix.translation
        print("IK_DEBUG", rig.name, side, frame, "want", tuple(round(v, 2) for v in (rig.matrix_world @ arm_point)),
              "got", tuple(round(v, 2) for v in got), "loc", tuple(round(v, 2) for v in pb.location),
              "parent", pb.parent.name if pb.parent else None, flush=True)
    pb.keyframe_insert("location", frame=frame)
    pb.keyframe_insert("rotation_quaternion", frame=frame)


def reach(inst, side, points, fps, lead=0.3, back=0.45):
    """Move one hand by IK through [(frame, armature point), ...] and give the arm back to its FK pose
    afterwards. The blend in starts `lead` seconds before the first point (the anticipation: the hand
    gathers before it goes), and the arm settles back over `back` seconds after the last one. Every key is
    eased, so the move has a start, a travel and a settle rather than a constant speed."""
    if not points:
        return
    f_first, f_last = points[0][0], points[-1][0]
    f_in = max(2, f_first - round(lead * fps))
    _key_ik(inst, side, 1.0, f_in)
    _key_hand(inst, side, points[0][1], f_in)
    for f, p in points:
        _key_ik(inst, side, 0.0, f)
        _key_hand(inst, side, p, f)
    _key_ik(inst, side, 1.0, f_last + round(back * fps))


def point_at(inst, side, world_target, f0, f1, fps):
    """The arm straightened toward a target (a door, a board, a person), index finger out, held, then down."""
    import math
    from mathutils import Vector
    shoulder = Vector((-0.19 * MIRROR[side], -0.02, 1.39)) * _scale(inst)
    d = world_to_arm(inst, world_target) - shoulder
    d.z = max(-0.4, min(0.5, d.z))
    if d.length < 1e-3:
        return
    hand = shoulder + d.normalized() * 0.56 * _scale(inst)
    reach(inst, side, [(f0, hand), (f1, hand)], fps)
    rig = inst["rig"]
    # the index straight, the other fingers curled in: a point, not an open hand
    for finger, deg in (("index", -12), ("middle", 70), ("ring", 80), ("pinky", 85)):
        for k in ("01", "02", "03"):
            pb = rig.pose.bones.get(f"f_{finger}.{k}.{side}")
            if pb is None:
                continue
            pb.rotation_mode = "QUATERNION"
            for fr, a in ((max(1, f0 - round(0.3 * fps)), math.radians(12)), (f0, math.radians(deg * (0.8 if k == "01" else 1.0))),
                          (f1, math.radians(deg * (0.8 if k == "01" else 1.0))), (f1 + round(0.4 * fps), math.radians(12))):
                pb.rotation_quaternion = (math.cos(a / 2), math.sin(a / 2), 0.0, 0.0)
                pb.keyframe_insert("rotation_quaternion", frame=fr)


def gesture(inst, kind, f0, f1, fps, seed=0, target=None):
    """One gesture with a meaning, from frame f0 to f1:
      point     the right arm toward `target` (a world point)
      explain   the right hand forward, palm open, moving a little with the words
      chest     the right hand to the breastbone (grief, worry)
      mouth     the right hand to the mouth (shock)
      clasp     both hands together before the body (pleading)
      shake     the head turned left and right (no)
      nod       the head dips (yes, I hear you)
    """
    import random
    from mathutils import Vector
    rnd = random.Random(seed * 131 + f0)
    if kind == "point" and target is not None:
        point_at(inst, "R", target, f0, f1, fps)
    elif kind == "explain":
        base = landmark(inst, "explain", "R")
        pts, f = [], f0
        while f < f1:
            pts.append((f, base + Vector((rnd.uniform(-0.05, 0.05), rnd.uniform(-0.04, 0.03), rnd.uniform(-0.04, 0.05)))))
            f += round(rnd.uniform(0.35, 0.6) * fps)
        pts.append((f1, base))
        reach(inst, "R", pts, fps)
    elif kind in ("chest", "mouth"):
        p = landmark(inst, kind, "R")
        reach(inst, "R", [(f0, p), (f1, p + Vector((0, -0.01, -0.01)))], fps, lead=0.25)
    elif kind == "clasp":
        for side in ("R", "L"):
            p = landmark(inst, "clasp", side)
            reach(inst, side, [(f0, p), (f1, p)], fps, lead=0.35)
    elif kind == "shake":
        head_turns(inst, f0, f1, fps, [0.16, -0.16, 0.12, -0.08, 0.0])
    elif kind == "nod":
        head_turns(inst, f0, f1, fps, [0.0], nod_only=True)


def head_turns(inst, f0, f1, fps, yaws, nod_only=False):
    """Keyed head moves relative to the held pose: a shake (yaw left and right, getting smaller) or a nod."""
    import math
    rig = inst["rig"]
    act = rig.animation_data.action if rig.animation_data else None
    if act is None:
        return
    if nod_only:
        for fc_axis, offsets in ((1, [0.0, 0.07, 0.05, 0.0]),):
            fc = act.fcurves.find('pose.bones["head"].rotation_quaternion', index=fc_axis)
            if fc is None:
                return
            base = fc.evaluate(f0)
            for k, o in enumerate(offsets):
                fc.keyframe_points.insert(f0 + round(k * 0.15 * fps), base + o)
        return
    fc = act.fcurves.find('pose.bones["head"].rotation_quaternion', index=2)
    if fc is None:
        return
    base = fc.evaluate(f0)
    fc.keyframe_points.insert(f0, base)
    step = max(4, (f1 - f0) // (len(yaws) + 1))
    for k, y in enumerate(yaws, 1):
        fc.keyframe_points.insert(f0 + k * step, base + math.sin(y))


def lean(inst, f0, f1, fps, amount=0.06):
    """A lean into a start or a stop: the torso tips forward as the walk begins and rocks back as it ends."""
    rig = inst["rig"]
    act = rig.animation_data.action if rig.animation_data else None
    fc = act.fcurves.find('pose.bones["chest"].rotation_quaternion', index=1) if act else None
    if fc is None:
        return
    base = fc.evaluate(f0)
    for df, o in ((0, 0.0), (round(0.3 * fps), amount), (round(0.8 * fps), 0.0)):
        fc.keyframe_points.insert(f0 + df, base + o)
    for df, o in ((-round(0.2 * fps), 0.0), (round(0.15 * fps), -amount * 0.7), (round(0.6 * fps), 0.0)):
        fc.keyframe_points.insert(max(1, f1 + df), base + o)


def stride_speed(inst, fps):
    """Metres per second a walker must travel for its feet to stay planted: the speed at which the stance
    foot slides back in the walk clip when the body does not move (measured once per character)."""
    if "stride" in inst:
        return inst["stride"]
    import bpy as _bpy
    rig, walk = inst["rig"], inst["walk"]
    speed = 1.2
    if walk is not None and rig.data.bones.get("DEF-foot.L") is not None:
        ad = rig.animation_data or rig.animation_data_create()
        old = ad.action
        ad.action = walk
        scene = _bpy.context.scene
        keep = scene.frame_current
        start, end = int(walk.frame_range[0]), int(walk.frame_range[1])
        ys = []
        for f in range(start, end + 1):
            scene.frame_set(f)
            m = rig.pose.bones["DEF-foot.L"].matrix
            ys.append((m.translation.y, m.translation.z))
        ad.action = old
        scene.frame_set(keep)
        low = min(z for _, z in ys)
        stance = [y for y, z in ys if z < low + 0.02]
        if len(stance) >= 2:
            # the planted foot moves backward (+y, the character faces -y) at the body's ground speed
            frames_down = sum(1 for _, z in ys if z < low + 0.02)
            speed = max(0.6, min(1.8, (max(stance) - min(stance)) / max(1, frames_down - 1) * fps))
    inst["stride"] = speed
    return speed


def bend(inst, amount, f0=None, f1=None, fps=30):
    """Bend forward over work (a desk, a table): the chest and neck pitch by `amount` radians, eased in and
    out at f0 / f1 (or held throughout). The head is left to the gaze."""
    import math
    rig = inst["rig"]
    act = rig.animation_data.action if rig.animation_data else None
    if act is None:
        return
    for bone, share in (("chest", 0.65), ("neck", 0.35)):
        fc = act.fcurves.find(f'pose.bones["{bone}"].rotation_quaternion', index=1)
        if fc is None:
            continue
        m = fc.modifiers.new("FNGENERATOR")
        m.function_type = "SIN"
        m.amplitude = 0.0
        m.value_offset = math.sin(amount * share / 2)
        m.use_additive = True
        if f0 is not None and f1 is not None:
            m.use_restricted_range = True
            m.frame_start, m.frame_end = f0, f1
            m.blend_in = m.blend_out = min(round(0.4 * fps), (f1 - f0) / 2 - 1)


def pen_in_hand(inst, side="R", name="pen"):
    """A quill held in the hand: a thin dark shaft with a pale feather, parented to the hand bone so it
    goes wherever the hand writes."""
    import bpy as _bpy
    rig = inst["rig"]
    bone = f"DEF-hand.{side}" if rig.data.bones.get(f"DEF-hand.{side}") else f"hand_fk.{side}"
    _bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.004, depth=0.2)
    pen = _bpy.context.active_object
    pen.name = f"{rig.name}-{name}"
    mat = _bpy.data.materials.new(f"{pen.name}-mat")
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.75, 0.70, 0.62, 1)
    pen.data.materials.append(mat)
    pen.parent = rig
    pen.parent_type = "BONE"
    pen.parent_bone = bone
    # bone parenting puts the child at the bone's tail; the quill lies between thumb and fingers, its nib
    # toward the page and the feather up past the knuckles
    import math
    pen.location = (0.0, -0.04, -0.03)
    pen.rotation_euler = (math.radians(65), 0.0, 0.0)
    return pen
