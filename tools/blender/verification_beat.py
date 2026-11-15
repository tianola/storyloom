import argparse
import random
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:])


def material(name, color, metallic=0.0, roughness=0.4):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1.0)
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Roughness"].default_value = roughness
    return mat


def assign(obj, mat):
    obj.data.materials.append(mat)
    return obj


def smooth(obj):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.shade_smooth()
    obj.select_set(False)
    return obj


def aim(obj, point):
    obj.rotation_euler = (Vector(point) - obj.location).to_track_quat("-Z", "Y").to_euler()


def area_light(name, location, energy, color, size):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.color = color
    data.shape = "DISK"
    data.size = size
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    aim(obj, (0.0, 0.0, 2.0))
    return obj


def build_scene(output):
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.materials, bpy.data.worlds):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)

    scene = bpy.context.scene
    version = bpy.app.version
    scene.render.engine = "BLENDER_EEVEE" if version < (4, 2, 0) else "BLENDER_EEVEE_NEXT"
    scene.eevee.taa_render_samples = 32
    if hasattr(scene.eevee, "volumetric_samples"):
        scene.eevee.volumetric_samples = 64
    if hasattr(scene.eevee, "volumetric_tile_size"):
        scene.eevee.volumetric_tile_size = "4"
    if hasattr(scene.eevee, "use_volumetric_shadows"):
        scene.eevee.use_volumetric_shadows = True
    if hasattr(scene.eevee, "use_ssr"):
        scene.eevee.use_ssr = True
    if hasattr(scene.eevee, "use_ssr_refraction"):
        scene.eevee.use_ssr_refraction = True

    scene.render.resolution_x = 640
    scene.render.resolution_y = 360
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    scene.render.fps = 30
    scene.frame_start = 1
    scene.frame_end = 150
    scene.frame_set(48)
    random.seed(48)
    if hasattr(scene.render, "seed"):
        scene.render.seed = 48

    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0

    world = bpy.data.worlds.new("Studio World")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.035, 0.05, 0.08, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.25
    scene.world = world

    glass = bpy.data.materials.new("Glass Outer Shell")
    glass.use_nodes = True
    nodes = glass.node_tree.nodes
    nodes.clear()
    output_node = nodes.new("ShaderNodeOutputMaterial")
    glass_node = nodes.new("ShaderNodeBsdfGlass")
    glass_node.inputs["Color"].default_value = (0.55, 0.8, 1.0, 1.0)
    glass_node.inputs["Roughness"].default_value = 0.12
    glass_node.inputs["IOR"].default_value = 1.45
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    mix = nodes.new("ShaderNodeMixShader")
    mix.inputs[0].default_value = 0.68
    glass.node_tree.links.new(glass_node.outputs[0], mix.inputs[1])
    glass.node_tree.links.new(transparent.outputs[0], mix.inputs[2])
    glass.node_tree.links.new(mix.outputs[0], output_node.inputs["Surface"])
    if hasattr(glass, "blend_method"):
        glass.blend_method = "HASHED"
    if hasattr(glass, "use_screen_refraction"):
        glass.use_screen_refraction = True
    if hasattr(glass, "surface_render_method"):
        glass.surface_render_method = "DITHERED"

    metal = material("Machined Titanium", (0.19, 0.28, 0.38), metallic=0.9, roughness=0.22)
    accent = material("Copper Winding", (0.65, 0.19, 0.055), metallic=0.82, roughness=0.25)
    ground_mat = material("Shadow Catching Ground", (0.085, 0.105, 0.14), metallic=0.05, roughness=0.48)

    core_mat = bpy.data.materials.new("Emissive Core")
    core_mat.use_nodes = True
    core_shader = core_mat.node_tree.nodes.get("Principled BSDF")
    core_shader.inputs["Base Color"].default_value = (0.02, 0.25, 0.5, 1.0)
    core_shader.inputs["Emission Color"].default_value = (0.02, 0.55, 1.0, 1.0)
    core_shader.inputs["Emission Strength"].default_value = 5.0
    core_shader.inputs["Roughness"].default_value = 0.2

    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=2.15, location=(0, 0, 2.55))
    shell = smooth(assign(bpy.context.object, glass))
    shell.name = "Glass Outer Shell"

    bpy.ops.mesh.primitive_torus_add(major_segments=64, minor_segments=16, location=(0, 0, 2.55), major_radius=1.25, minor_radius=0.18, rotation=(1.57079632679, 0, 0))
    ring = smooth(assign(bpy.context.object, metal))
    ring.name = "Metallic Inner Mechanism - Main Ring"

    bpy.ops.mesh.primitive_torus_add(major_segments=64, minor_segments=12, location=(0, 0, 2.55), major_radius=0.82, minor_radius=0.11, rotation=(1.57079632679, 0.78539816339, 0))
    winding = smooth(assign(bpy.context.object, accent))
    winding.name = "Metallic Inner Mechanism - Copper Ring"

    for index in range(8):
        angle = index * 0.78539816339
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(1.22 * __import__("math").cos(angle), 0.0, 2.55 + 1.22 * __import__("math").sin(angle)))
        tooth = assign(bpy.context.object, metal)
        tooth.name = f"Mechanism Tooth {index + 1:02d}"
        tooth.scale = (0.24, 0.34, 0.24)
        tooth.rotation_euler[1] = -angle
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=0.58, location=(0, 0, 2.55))
    core = smooth(assign(bpy.context.object, core_mat))
    core.name = "Emissive Core"

    bpy.ops.mesh.primitive_plane_add(size=200.0, location=(0, 0, 0))
    ground = assign(bpy.context.object, ground_mat)
    ground.name = "Shadow-catching Ground"

    volume_mat = bpy.data.materials.new("Visible Atmosphere")
    volume_mat.use_nodes = True
    volume_nodes = volume_mat.node_tree.nodes
    volume_nodes.clear()
    volume_output = volume_nodes.new("ShaderNodeOutputMaterial")
    scatter = volume_nodes.new("ShaderNodeVolumeScatter")
    scatter.inputs["Color"].default_value = (0.32, 0.48, 0.7, 1.0)
    scatter.inputs["Density"].default_value = 0.025
    scatter.inputs["Anisotropy"].default_value = 0.2
    volume_mat.node_tree.links.new(scatter.outputs[0], volume_output.inputs["Volume"])
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 4.0))
    volume = assign(bpy.context.object, volume_mat)
    volume.name = "Volumetric Cube"
    volume.scale = (12.0, 12.0, 9.0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    volume.display_type = "WIRE"

    area_light("Key Area", (4.5, -4.5, 8.0), 1150.0, (0.72, 0.86, 1.0), 5.0)
    area_light("Rim Area", (-4.0, 2.0, 6.5), 1350.0, (0.25, 0.5, 1.0), 4.0)
    area_light("Warm Area", (2.0, 4.5, 5.0), 1000.0, (1.0, 0.48, 0.2), 3.0)

    camera_data = bpy.data.cameras.new("Verification Camera")
    camera = bpy.data.objects.new("Verification Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = (7.5, -10.5, 6.5)
    camera_data.lens = 52.0
    aim(camera, (0.0, 0.0, 2.2))
    scene.camera = camera

    output.parent.mkdir(parents=True, exist_ok=True)
    blend_path = output.with_suffix(".blend")
    scene.render.filepath = str(output)
    print(f"BLENDER_VERSION: {bpy.app.version_string}", flush=True)
    print(f"BLENDER_ENGINE: {scene.render.engine}", flush=True)
    print(f"BLEND_OUTPUT: {blend_path}", flush=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    bpy.ops.render.render(write_still=True)
    print(f"RENDER_OUTPUT: {output}", flush=True)


if __name__ == "__main__":
    build_scene(arguments().output.resolve())
