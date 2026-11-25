"""Build one rigged CharMorph character for the 3D episode test (run with Blender in background).

    blender -b --factory-startup --enable-autoexec -P tools/blender/human3d_build.py -- \
        --db <charmorph-db> --base mb_male --out <file.blend>

The Rigify rig UI text inside the finalized file only runs when Blender auto-execute is on, which is why
--enable-autoexec is part of the command. The result keeps the CharMorph rig (`<base>_rig`), its expression
shape keys and the skin/eye/teeth materials; garments and hair are added by the caller.
"""
import argparse
import importlib
import sys

import bpy


def parse(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--age", type=float, default=0.5)
    ap.add_argument("--mass", type=float, default=0.5)
    ap.add_argument("--tone", type=float, default=0.5)
    ap.add_argument("--hair-style", default="")
    ap.add_argument("--garment", choices=["coat", "dress", "none"], default="coat")
    ap.add_argument("--garment-colour", default="0.08,0.08,0.10")
    return ap.parse_args(argv)


def _hair_cap_from_body(body):
    """A hair cap made from the top of the head of the body mesh, shrinkwrapped back onto it.

    The scalp object from CharMorph does not follow the finalized rig, and particles read too thin at 720p.
    Shrinkwrap follows the deformed body every frame, so the cap moves with the head and the pose.
    """
    import bmesh
    zs = [v.co.z for v in body.data.vertices]
    zmax = max(zs)
    h = zmax - min(zs)
    bm = bmesh.new()
    bm.from_mesh(body.data)
    top = [v.co for v in bm.verts if v.co.z > zmax - 0.07 * h]
    yc = sum(c.y for c in top) / len(top)  # the face is on the -Y side; keep the back and top of the skull
    drop = [v for v in bm.verts if v.co.z < zmax - 0.07 * h or v.co.y < yc]
    bmesh.ops.delete(bm, geom=drop, context="VERTS")
    me = bpy.data.meshes.new("hair_cap_body")
    bm.to_mesh(me)
    bm.free()
    cap = bpy.data.objects.new("hair_cap_body", me)
    bpy.context.scene.collection.objects.link(cap)
    sw = cap.modifiers.new("wrap", "SHRINKWRAP")
    sw.target = body
    sw.wrap_method = "NEAREST_SURFACEPOINT"
    sw.offset = 0.006
    sol = cap.modifiers.new("cap", "SOLIDIFY")
    sol.thickness = 0.012
    mat = bpy.data.materials.new("hair_cap_brown")
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.16, 0.09, 0.05, 1)
    b.inputs["Roughness"].default_value = 0.45
    cap.data.materials.append(mat)
    for o in list(bpy.data.objects):
        if o.type == "MESH" and "_hair_" in o.name:
            bpy.data.objects.remove(o, do_unlink=True)
    print("HUMAN3D_HAIR_CAP", cap.name, len(me.vertices))


def _garment_from_body(body, name, groups, colour, thickness=0.012, min_weight=0.5):
    """A garment made from the body itself: a copy that keeps the body's rig and topology.

    Faces are kept when every vertex has at least `min_weight` total weight in the bones listed in `groups`
    (name prefixes such as "DEF-spine", "DEF-upper_arm"). The copy keeps the armature modifier, so it follows
    the pose exactly, and a solidify gives the cloth thickness. Test grade: no tailoring, no folds.
    """
    import bmesh
    rig = next((m.object for m in body.modifiers if m.type == "ARMATURE"), None)
    me = body.data.copy()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.shape_key_clear()
    ob.matrix_world = body.matrix_world.copy()
    # a group matches by exact name, or by prefix when written with a trailing "*"
    idx = [g.index for g in body.vertex_groups
           if any((g.name == pre) or (pre.endswith("*") and g.name.startswith(pre[:-1])) for pre in groups)]
    bm = bmesh.new()
    bm.from_mesh(me)
    dl = bm.verts.layers.deform.verify()
    keep = set(idx)
    drop = []
    for f in bm.faces:
        ok = True
        for v in f.verts:
            w = sum(v[dl].get(i, 0.0) for i in keep)
            if w < min_weight:
                ok = False
                break
        if not ok:
            drop.append(f)
    bmesh.ops.delete(bm, geom=drop, context="FACES")
    bm.to_mesh(me)
    bm.free()
    for m in list(ob.modifiers):
        ob.modifiers.remove(m)
    if rig is not None:
        arm = ob.modifiers.new("armature", "ARMATURE")
        arm.object = rig
    # inflate the cloth outward from the skin, so it reads as a garment rather than a coat of paint
    sw = ob.modifiers.new("inflate", "SHRINKWRAP")
    sw.target = body
    sw.wrap_method = "NEAREST_SURFACEPOINT"
    sw.offset = 0.022
    sm = ob.modifiers.new("drape", "SMOOTH")  # fabric does not show the muscles underneath
    sm.factor = 1.0
    sm.iterations = 25
    sol = ob.modifiers.new("cloth", "SOLIDIFY")
    sol.thickness = thickness
    sol.offset = 1.0
    mat = bpy.data.materials.new(name + "_cloth")
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = colour
    b.inputs["Roughness"].default_value = 0.85
    me.materials.clear()  # the copy starts with the body's skin material; the cloth must not use it
    me.materials.append(mat)
    return ob


def _garments(body, kind, colour):
    rgb = tuple(float(x) for x in colour.split(",")) + (1.0,)
    torso = ("DEF-spine", "DEF-spine.001", "DEF-spine.002", "DEF-spine.003", "DEF-shoulder*", "DEF-breast*")
    arms = ("DEF-upper_arm*", "DEF-forearm*")
    legs = ("DEF-pelvis*", "DEF-thigh*", "DEF-shin*")
    if kind == "coat":
        _garment_from_body(body, "coat", torso + arms, rgb)
        _garment_from_body(body, "trousers", legs, (0.20, 0.19, 0.18, 1.0))
    elif kind == "dress":
        _garment_from_body(body, "dress", torso + arms + ("DEF-pelvis*", "DEF-thigh*"), rgb)
    print("HUMAN3D_GARMENTS", kind)


def main():
    args = parse(sys.argv[sys.argv.index("--") + 1:])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.preferences.addon_enable(module="rigify")
    bpy.ops.preferences.addon_enable(module="CharMorph")
    bpy.context.preferences.addons["CharMorph"].preferences.data_path = args.db
    bpy.ops.charmorph.reload_library()
    ui = bpy.context.window_manager.charmorph_ui
    ui.base_model = args.base
    ui.fin_rig = True
    ui.fin_expressions = "CH"
    ui.fin_vg_cleanup = True
    if bpy.ops.charmorph.import_char() != {"FINISHED"}:
        raise SystemExit(f"import failed for {args.base}")
    ob = next(o for o in bpy.data.objects if o.type == "MESH")
    common = importlib.import_module("CharMorph.common")
    morpher = common.manager.morpher
    for name, value in (("age", args.age), ("mass", args.mass), ("tone", args.tone)):
        morpher.prop_set(name, value)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    if bpy.ops.charmorph.finalize() != {"FINISHED"}:
        raise SystemExit(f"finalize failed for {args.base}")
    if args.hair_style:
        ui.hair_style = args.hair_style
        ui.hair_scalp = True  # emit hair from a scalp mesh, not from the whole body
        bpy.context.view_layer.objects.active = ob
        print("HUMAN3D_HAIR", bpy.ops.charmorph.hair_create())
        _hair_cap_from_body(ob)
    if args.garment != "none":
        _garments(ob, args.garment, args.garment_colour)
    rigs = [o for o in bpy.data.objects if o.type == "ARMATURE" and o.data.get("rig_id")]
    print("HUMAN3D_RIG", [r.name for r in rigs], "shape_keys", len(ob.data.shape_keys.key_blocks) if ob.data.shape_keys else 0)
    bpy.ops.wm.save_as_mainfile(filepath=args.out, check_existing=False)
    print("HUMAN3D_SAVED", args.out)


if __name__ == "__main__":
    main()
