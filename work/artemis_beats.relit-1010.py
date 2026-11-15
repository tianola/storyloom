"""Build 9 Artemis II 3D render beats.

Each beat is a 5-second animation (150 frames at 30 fps) rendered with
EEVEE Next at 1280x720 with AgX colour management.

Scenes:
  1. sls-launch        — SLS rocket lifting off
  2. orion-space       — Orion capsule in Earth orbit
  3. orion-deep-space  — Orion coasting to the Moon
  4. lunar-flyby       — Orion passing over the Moon
  5. earth-rise        — Earth rising over lunar horizon
  6. lunar-approach    — Moon growing larger approaching
  7. far-side          — Moon's far side cratered highlands
  8. splashdown        — Orion descending with parachutes
  9. earth-from-moon   — Full Earth disk from lunar distance

Usage:
    blender --background --factory-startup --python-exit-code 1 \
        --python tools/blender/artemis_beats.py -- \
        --output work/episode-artemis-ii/renders/3d
"""
import argparse
import bmesh
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import bpy
import mathutils

TAU = 2 * math.pi

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / "techniques"))

from common import (
    wipe as wipe_scene, setup_scene, setup_world,
    material_principled, material_emissive, material_xray_shell, set_transparent,
    solar_cell_material, vmath, math_node, smooth_mask,
    add_sphere, add_box, add_cylinder,
    add_area_light, add_sun_light, add_camera,
    render_still, save_blend, aim,
    harden_edges, TEXTURED_MATERIALS,
)
from surfaces import apply_surface
from lighting import key_location, LUNAR_KEY_ELEVATION
from detail import surface_relief, stiffener_rings, bolt_circle, add_glare


def wipe():
    """Clear the scene, and with it every material the surface cache still points at.

    material_textured() caches a tile by parameter set so 19 beats share five materials.
    wipe() deletes those datablocks, and the cache would hand the next beat a removed
    Material — Blender answers that with ReferenceError, not with a rebuilt surface. All
    19 beats run in one process, so the cache has to die together with the scene.
    """
    wipe_scene()
    TEXTURED_MATERIALS.clear()

SPACE_BG = (0.012, 0.016, 0.04, 1.0)
EARTH_BLUE = (0.15, 0.35, 0.75, 1.0)
EARTH_GREEN = (0.18, 0.45, 0.22, 1.0)
EARTH_WHITE = (0.85, 0.88, 0.92, 1.0)
MOON_GREY = (0.45, 0.44, 0.42, 1.0)
MOON_DARK = (0.25, 0.24, 0.22, 1.0)
ROCKET_WHITE = (0.88, 0.88, 0.9, 1.0)
FLAME_ORANGE = (1.0, 0.55, 0.1, 1.0)
FLAME_YELLOW = (1.0, 0.9, 0.4, 1.0)
HEAT_GLOW = (1.0, 0.3, 0.05, 1.0)
METAL_GREY = (0.55, 0.56, 0.58, 1.0)
PARACHUTE_ORANGE = (1.0, 0.5, 0.15, 1.0)
OCEAN_BLUE = (0.05, 0.15, 0.4, 1.0)
SUN_WHITE = (1.0, 0.98, 0.95)
STAR_FIELD = (0.005, 0.005, 0.02, 1.0)

# Set by --still. Look-dev needs one frame, not a 150-frame animation plus its encode;
# without it every material tweak costs five minutes instead of ten seconds.
STILL_ONLY = False

# A beat is one continuous camera move, and the move has to be as long as the narration
# sitting on top of it. assemble_episode.py sums the utterance seconds per visual into
# shot_lengths.json; hardcoding 150 frames made every beat a 5 s clip under a 15 s
# sentence, which the assembler then looped, so the camera restarted mid-word and no move
# ever completed — the single biggest reason the episode read as motion graphics.
SHOT_LENGTHS_FILE = PROJECT_ROOT / "work" / "episode-artemis-ii" / "shot_lengths.json"
SHOT_FPS = 30
# beat_mars renders as mars-approach, so the function name is not always the shot key.
SHOT_KEYS = {"beat_mars": "mars-approach"}

SHOT_FRAMES = 150


def add_key(cam, frame, *, name="sun", energy=5.0, color=None, angle=None,
            side=1.0, elevation=LUNAR_KEY_ELEVATION, yaw=0.0, distance=14.0):
    """Place a beat's sun from where that beat's camera actually points, mid-move.

    lighting.key_location carries the geometry and the reason for it. Two things here are
    not obvious, and both bit during look-dev:

    The call belongs *after* the animation, not beside the other lights. Every camera in
    this episode travels — `cam.location` at build time is frame 1, and sls-launch walks 17
    units along its own view axis before it ends. A key aimed at the starting framing is
    already wrong by the half-way point, which is exactly the frame the QC stills are drawn
    from, so the helper evaluates the real matrix at the mid frame and uses that.

    `yaw` is a physics concession rather than a taste one. When the subject is a sphere the
    camera is looking at — the Earth from lunar distance, the Moon ahead of Orion — a
    perpendicular key drags the terminator across the middle of it and the planet reads as
    a crescent, which is true of nothing the narration says. Leaning the key back toward the
    camera to yaw=-15 keeps three quarters of the disc lit while the horizontal separation
    still measures 0.26, enough for the ground beneath it to keep its shadows.
    """
    scene = bpy.context.scene
    keep = scene.frame_current
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    origin = cam.matrix_world.translation.copy()
    forward = cam.matrix_world.to_quaternion() @ mathutils.Vector((0.0, 0.0, -1.0))
    scene.frame_set(keep)
    return add_sun_light(
        name,
        location=key_location(origin, origin + forward, elevation=elevation, side=side,
                              yaw=yaw, distance=distance),
        energy=energy, color=SUN_WHITE if color is None else color, angle=angle)


def _shot_frames_for(beat_name):
    try:
        table = json.loads(SHOT_LENGTHS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return SHOT_FRAMES
    seconds = table.get(SHOT_KEYS.get(beat_name,
                                      beat_name.removeprefix("beat_").replace("_", "-")))
    return int(round(seconds * SHOT_FPS)) if seconds else SHOT_FRAMES


def render_animation(output_dir, name):
    scene = bpy.context.scene
    frame_end = SHOT_FRAMES
    scene.frame_end = frame_end
    out_dir = output_dir / name
    out_dir.mkdir(parents=True, exist_ok=True)
    if STILL_ONLY:
        # Look-dev needs to see the ends of a move, not only its middle: a plume that is
        # right at t=0.5 can still be buried on the pad at frame 1.
        scene.frame_set(int(os.environ.get("ARTEMIS_STILL_FRAME") or frame_end // 2))
        still_path = output_dir / f"{name}-mid.png"
        scene.render.filepath = str(still_path)
        bpy.ops.render.render(write_still=True)
        print(f"  Still: {still_path}", flush=True)
        return
    scene.render.filepath = str(out_dir / "frame-####.png")
    bpy.ops.render.render(animation=True)
    print(f"  Rendered {frame_end} frames to {out_dir}", flush=True)

    mp4_path = output_dir / f"{name}.mp4"
    subprocess.run([
        "ffmpeg", "-y",
        "-framerate", "30",
        "-i", str(out_dir / "frame-%04d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-preset", "medium", "-crf", "18",
        "-movflags", "+faststart",
        str(mp4_path),
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if mp4_path.exists():
        size_mb = mp4_path.stat().st_size / 1024 / 1024
        print(f"  MP4: {mp4_path} ({size_mb:.1f} MB)", flush=True)

    scene.frame_set(frame_end // 2)
    still_path = output_dir / f"{name}-mid.png"
    scene.render.filepath = str(still_path)
    bpy.ops.render.render(write_still=True)
    print(f"  Still: {still_path}", flush=True)


def add_starfield(radius=400.0):
    """Enclosing shell with speckled emission = visible stars.

    Must never cast shadows: as a closed surface around the camera and the sun it
    would put every object in shadow and render the frame black.
    """
    mat = bpy.data.materials.new("starfield")
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.0, 0.0, 0.005, 1.0)
    bsdf.inputs["Roughness"].default_value = 1.0
    bsdf.inputs["Emission Color"].default_value = (0.9, 0.93, 1.0, 1.0)
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 4.0 * radius
    noise.inputs["Detail"].default_value = 2.0
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.72
    ramp.color_ramp.elements[1].position = 0.80
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Emission Strength"])

    bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=48, radius=radius)
    shell = bpy.context.active_object
    shell.name = "Starfield"
    bpy.ops.object.shade_smooth()
    shell.data.materials.append(mat)
    shell.visible_shadow = False
    return shell


def aim_key(cam, target, frame):
    """Aim the camera and key the rotation, so the aim tracks the moving subject."""
    aim(cam, target)
    cam.keyframe_insert(data_path="rotation_euler", frame=frame)


# ---------------------------------------------------------------------------
# Look-development helpers
# ---------------------------------------------------------------------------

def add_planet(name, radius, location, mat, segments=96, rings=48):
    """Smooth-shaded sphere. Ico spheres render visibly faceted at 640x360."""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings,
                                         radius=radius, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    return obj


def material_surface(name, stops, scale=3.0, detail=8.0, bump_strength=0.2,
                     roughness=0.85, warp=0.0, patch=None):
    """Noise-driven base colour plus bump, so bodies are not flat single-colour balls.

    `warp` offsets the sample point with a second low-frequency noise. Without it every
    feature is the same size and evenly spread, which reads as camouflage rather than
    geography.

    `patch` is ``(colour, edge, frac)``: a second, much lower frequency mask that
    subtracts dark plains out of the height field -- maria on the Moon, the large dark
    albedo features on Mars. `frac` is the mare wavelength relative to the surface
    noise, and `edge` where the mask opens. One noise at one frequency cannot produce
    them: its brightest spots are the same size as its darkest, so the body has no
    dominant landform and the eye finds nothing to lock onto at orbital distance.
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = roughness
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    def vm(op, *srcs):
        return vmath(nodes, links, op, *srcs)

    def mn(op, *srcs, clamp=False):
        return math_node(nodes, links, op, *srcs, clamp=clamp)

    tex = nodes.new("ShaderNodeTexCoord")
    vector = tex.outputs["Object"]
    if warp > 0.0:
        drift = nodes.new("ShaderNodeTexNoise")
        drift.inputs["Scale"].default_value = max(scale * 0.5, 0.05)
        drift.inputs["Detail"].default_value = 2.0
        links.new(tex.outputs["Object"], drift.inputs["Vector"])
        amp = nodes.new("ShaderNodeVectorMath")
        amp.operation = "SCALE"
        amp.inputs["Scale"].default_value = warp
        links.new(drift.outputs["Color"], amp.inputs[0])
        shift = nodes.new("ShaderNodeVectorMath")
        shift.operation = "ADD"
        links.new(tex.outputs["Object"], shift.inputs[0])
        links.new(amp.outputs["Vector"], shift.inputs[1])
        vector = shift.outputs["Vector"]

    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = scale
    noise.inputs["Detail"].default_value = detail
    links.new(vector, noise.inputs["Vector"])

    ramp = nodes.new("ShaderNodeValToRGB")
    elements = ramp.color_ramp.elements
    elements[0].position = stops[0][0]
    elements[0].color = stops[0][1]
    while len(elements) > 1:
        elements.remove(elements[-1])
    for pos, col in stops[1:]:
        elements.new(pos).color = col
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    colour = ramp.outputs["Color"]
    height = noise.outputs["Fac"]

    if patch:
        patch_colour, edge, frac = patch
        maria = nodes.new("ShaderNodeTexNoise")
        maria.inputs["Scale"].default_value = max(scale * frac, 0.02)
        maria.inputs["Detail"].default_value = 3.0
        maria.inputs["Roughness"].default_value = 0.55
        links.new(vector, maria.inputs["Vector"])
        # Smoothstepped rather than a hard step: a sharp mare boundary is the one edge
        # that shimmers at 30 fps as the body rotates under a fixed camera.
        mask = smooth_mask(nodes, links, maria.outputs["Fac"], edge, 0.11)
        colour = vm("ADD", colour, vm("SCALE", vm("SUBTRACT", patch_colour, colour), mask))
        # Basalt plains are smoother than highland regolith, so they catch the sun as a
        # broad sheen rather than the same matte scatter.
        links.new(mn("MULTIPLY_ADD", mask, -0.22, roughness, clamp=True),
                  bsdf.inputs["Roughness"])
        height = mn("SUBTRACT", height, mn("MULTIPLY", mask, 0.35))

    links.new(colour, bsdf.inputs["Base Color"])

    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = bump_strength
    links.new(height, bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def surface_scale(radius, frac=0.26):
    """Noise scale for a body so its dominant features span `frac` of its radius.

    Noise scale works in object units, so one fixed value gives every body the same
    absolute feature size: speckle on a nearby Moon, mud on a distant Earth.
    """
    return 1.0 / (frac * max(radius, 0.01))


SKY_DOME_RADIUS = 900.0


def setup_sky(zenith=(0.010, 0.085, 0.400), mid=(0.045, 0.220, 0.550),
              horizon=(0.420, 0.550, 0.620), strength=0.85):
    """A gradient sky built as geometry, with a matching flat world behind it.

    EEVEE Next does not evaluate the Geometry normal inside a world shader, so a
    ColorRamp wired to the background renders one flat colour however it is arranged.
    An emission dome with an object-space ramp is the only gradient that shows, and it
    doubles as the daylight fill; past the ground plane's edge it supplies the haze that
    would otherwise expose the pad as a disc floating in space.
    """
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    nodes, links = world.node_tree.nodes, world.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputWorld")
    bg = nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = (*horizon[:3], 1.0)
    bg.inputs["Strength"].default_value = strength * 0.35
    links.new(bg.outputs["Background"], out.inputs["Surface"])

    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16,
                                         radius=SKY_DOME_RADIUS)
    dome = bpy.context.active_object
    dome.name = "SkyDome"
    mat = bpy.data.materials.new("sky-dome")
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    emis = nodes.new("ShaderNodeEmission")
    emis.inputs["Strength"].default_value = strength
    ramp = nodes.new("ShaderNodeValToRGB")
    elems = ramp.color_ramp.elements
    elems[0].position = 0.0
    elems[1].position = 0.55
    elems.new(0.09)
    # Insertion re-sorts the elements, so assign colours by index afterwards
    elems[0].color = (*horizon[:3], 1.0)
    elems[1].color = (*mid[:3], 1.0)
    elems[2].color = (*zenith[:3], 1.0)
    geo = nodes.new("ShaderNodeTexCoord")
    rng = nodes.new("ShaderNodeMapRange")
    rng.inputs["From Min"].default_value = 0.0
    rng.inputs["From Max"].default_value = SKY_DOME_RADIUS
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(geo.outputs["Object"], sep.inputs["Vector"])
    links.new(sep.outputs["Z"], rng.inputs["Value"])
    links.new(rng.outputs["Result"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], emis.inputs["Color"])
    links.new(emis.outputs["Emission"], out.inputs["Surface"])
    dome.data.materials.append(mat)
    dome.visible_shadow = False
    return dome


def earth_material(scale=None):
    """Ocean-dominant, muted land.

    Noise `Fac` clusters around 0.5, so a land threshold below it paints most of the
    sphere green and the planet reads as a beach ball rather than a photograph.
    """
    return material_surface(
        "earth-surf",
        [(0.0, (0.004, 0.016, 0.075, 1.0)), (0.44, (0.010, 0.045, 0.160, 1.0)),
         (0.56, (0.030, 0.100, 0.260, 1.0)), (0.61, (0.085, 0.135, 0.075, 1.0)),
         (0.73, (0.200, 0.200, 0.110, 1.0)), (0.85, (0.340, 0.280, 0.170, 1.0)),
         (0.95, (0.560, 0.540, 0.470, 1.0))],
        scale=scale or 0.45, detail=6.0, bump_strength=0.08, roughness=0.42,
        warp=2.2)


def moon_material(scale=None):
    """Highlands plus maria.

    The warp is deliberately weak here: at 1.2 the base mottle reads as ink swirls, and a
    swirl competes with the plains for the same large-scale contrast, so the maria
    vanished into it. Mare basalt is about 0.07 albedo against 0.18 for the highlands,
    which is a factor of ~0.4 -- the first pass used 0.042 against 0.29 and the plains
    looked punched into the surface rather than filling it.
    """
    return material_surface(
        "moon-surf",
        [(0.0, (0.105, 0.105, 0.118, 1.0)), (0.42, (0.145, 0.145, 0.158, 1.0)),
         (0.55, (0.290, 0.290, 0.305, 1.0)), (0.78, (0.400, 0.400, 0.415, 1.0))],
        scale=scale or 0.55, detail=8.0, bump_strength=0.30, warp=0.45,
        patch=((0.075, 0.076, 0.086, 1.0), 0.52, 0.30))


def regolith_material(scale=None):
    return material_surface(
        "regolith",
        [(0.0, (0.16, 0.16, 0.17, 1.0)), (0.45, (0.29, 0.29, 0.30, 1.0)),
         (0.72, (0.41, 0.41, 0.42, 1.0))],
        scale=scale or 0.9, detail=10.0, bump_strength=0.55, warp=1.0)


def mars_material(scale=None):
    return material_surface(
        "mars-surf",
        [(0.0, (0.21, 0.065, 0.032, 1.0)), (0.45, (0.40, 0.16, 0.075, 1.0)),
         (0.70, (0.60, 0.32, 0.18, 1.0)), (0.88, (0.76, 0.56, 0.38, 1.0))],
        scale=scale or 0.70, detail=8.0, bump_strength=0.30, warp=1.4)


def cloud_material(radius=4.0, name="clouds"):
    """Noise-gated alpha shell: banded cloud cover instead of floating blobs."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    bsdf.inputs["Roughness"].default_value = 1.0
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    tex = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    # Compressing the polar axis stretches the swirls into latitudinal bands, which is
    # how a real cloud deck reads; isotropic noise looks like a ceiling of cotton wool.
    mapping.inputs["Scale"].default_value = (1.0, 1.0, 0.48)
    links.new(tex.outputs["Object"], mapping.inputs["Vector"])
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = surface_scale(radius, 0.32)
    noise.inputs["Detail"].default_value = 8.0
    noise.inputs["Roughness"].default_value = 0.62
    links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.49
    ramp.color_ramp.elements[1].position = 0.74
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Alpha"])
    return blend_shell(mat)


def blend_shell(mat):
    """Alpha-blend a shell without dithering. Shadow pass is an object-level flag."""
    return set_transparent(mat)


def atmosphere_material(name, color=(0.22, 0.50, 0.95), strength=1.5):
    """Limb glow: bright where the shell turns away edge-on, clear where it faces us.

    Without this rim a planet renders as a painted ball; the lit limb is the cue that
    reads as "photographed from orbit". Kept thin and dim: a fat, bright shell sits
    outside the planet's own edge and renders as a neon outline with a gap in it.
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    emis = nodes.new("ShaderNodeEmission")
    emis.inputs["Color"].default_value = (*color[:3], 1.0)
    emis.inputs["Strength"].default_value = strength
    transp = nodes.new("ShaderNodeBsdfTransparent")
    mix = nodes.new("ShaderNodeMixShader")
    weight = nodes.new("ShaderNodeLayerWeight")
    weight.inputs["Blend"].default_value = 0.30
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.58
    ramp.color_ramp.elements[1].position = 1.0
    links.new(weight.outputs["Fresnel"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], mix.inputs["Fac"])
    links.new(transp.outputs[0], mix.inputs[1])
    links.new(emis.outputs["Emission"], mix.inputs[2])
    links.new(mix.outputs[0], out.inputs["Surface"])
    return blend_shell(mat)


def plasma_material(name, color=(1.0, 0.42, 0.12), strength=6.0, bow=0.55, tip=0.05,
                    gate=True):
    """Emissive sheath that glows at its silhouette and fades aft along local Z.

    Generated space puts 0 at the wide end of a cone and 1 at the tip, so one ramp
    serves both the bow shell and the streaking tail. The Fresnel gate is the part that
    sells it: a shell seen face-on is nearly clear and only accumulates brightness where
    it turns edge-on, so the volume reads as gas. Without the gate the same shell is a
    hard-edged solid, because there is nothing behind it in space to blend against.

    gate=False drops that term and lets the ramp alone decide brightness. Use it for a
    plume, which is a column of glowing gas seen against nothing — with the gate on it
    is a hollow outline, and the eye reads that as a wireframe, not a burn.
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    emis = nodes.new("ShaderNodeEmission")
    emis.inputs["Color"].default_value = (*color[:3], 1.0)
    emis.inputs["Strength"].default_value = strength
    transp = nodes.new("ShaderNodeBsdfTransparent")
    mix = nodes.new("ShaderNodeMixShader")
    geo = nodes.new("ShaderNodeTexCoord")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (bow, bow, bow, 1.0)
    ramp.color_ramp.elements[1].position = 1.0
    ramp.color_ramp.elements[1].color = (tip, tip, tip, 1.0)
    links.new(geo.outputs["Generated"], sep.inputs["Vector"])
    links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    if gate:
        weight = nodes.new("ShaderNodeLayerWeight")
        weight.inputs["Blend"].default_value = 0.55
        gate_node = nodes.new("ShaderNodeMath")
        gate_node.operation = "MULTIPLY"
        links.new(ramp.outputs["Color"], gate_node.inputs[0])
        links.new(weight.outputs["Fresnel"], gate_node.inputs[1])
        links.new(gate_node.outputs["Value"], mix.inputs["Fac"])
    else:
        links.new(ramp.outputs["Color"], mix.inputs["Fac"])
    links.new(transp.outputs[0], mix.inputs[1])
    links.new(emis.outputs["Emission"], mix.inputs[2])
    links.new(mix.outputs[0], out.inputs["Surface"])
    return blend_shell(mat)


def steam_material(name="steam", scale=2.6):
    """Soft-edged ground steam. It is the hard sphere silhouette, not the count, that
    makes a puff read as a ball — gating alpha on noise dissolves the rim so overlapping
    puffs merge into one rolling mass."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.88, 0.89, 0.90, 1.0)
    bsdf.inputs["Roughness"].default_value = 1.0
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    tex = nodes.new("ShaderNodeTexCoord")
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = scale
    noise.inputs["Detail"].default_value = 6.0
    links.new(tex.outputs["Object"], noise.inputs["Vector"])
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.30
    ramp.color_ramp.elements[1].position = 0.60
    # Twenty-six overlapping shells each fading to a full 1.0 composite to an opaque white
    # floor, and a floor is exactly what the pad steam is not: the reason it reads as cloud
    # in footage is that light gets *into* it, so the far side stays bright and the near
    # filaments stay translucent. Capping the ramp leaves that gradient standing.
    ramp.color_ramp.elements[1].color = (0.72, 0.74, 0.78, 1.0)
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Alpha"])
    return blend_shell(mat)


def plasma_volume_material(name, color=(1.0, 0.55, 0.22), density=2.2, strength=3.0,
                           anisotropy=0.35, mode="axial", turb=0.0, turb_scale=1.0):
    """A glowing gas body: volume shader only, no surface, so it has no silhouette.

    Every surface treatment of the reentry wake failed the same way from two opposite
    ends. bow=0.10 put the MixShader Fac at 0.1, so the filaments were 90% Transparent
    BSDF, and a transparent shell only traces as deep as refraction_depth (4 m) while the
    starfield is far beyond it — it painted the world's dark red across the stars and read
    as a bundle of black rods. Raise it to 95% emission and the same cones become ivory
    sticks, because a cone mesh always shows its own edge. Gas has no edge. Removing the
    Surface socket entirely leaves only depth, and the shape the eye sees is how much
    material each ray happens to travel through.

    mode="axial" fades along Generated Z (0 at the wide root of a cone, 1 at the tip),
    which is a streak. mode="nozzle" is the same axis reversed — hot at Generated Z 1 —
    for a cone whose wide mouth points aft, i.e. an engine plume. mode="jet" is axial
    times cross-axis, for a streak that must not show the wall of its own cone;
    mode="nozzle-jet" applies that same wall removal to the nozzle ramp, for a beam or
    plume whose hot end is the narrow one.
    mode="radial" fades from the centre of the primitive outward, which is a hot spot.
    mode="uniform" carries no falloff at all, for a body whose bounding box has no
    relation to its shape.

    turb is how hard a noise field modulates that falloff. A smooth falloff alone is the
    remaining giveaway: it turns a sheath into a gradient disc and a bundle of streaks into
    one ridged slab. The noise is sampled in world space, so overlapping bodies read the
    same flow field rather than repeating one pattern per object — which is what makes the
    streaks merge into a plume instead of stacking into ribs.
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    vol = nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = (*color[:3], 1.0)
    vol.inputs["Emission Color"].default_value = (*color[:3], 1.0)
    vol.inputs["Anisotropy"].default_value = anisotropy

    geo = nodes.new("ShaderNodeTexCoord")
    falloff = None
    if mode == "uniform":
        pass
    elif mode == "radial":
        off = nodes.new("ShaderNodeVectorMath")
        off.operation = "SUBTRACT"
        off.inputs[1].default_value = (0.5, 0.5, 0.5)
        length = nodes.new("ShaderNodeVectorMath")
        length.operation = "LENGTH"
        widen = nodes.new("ShaderNodeMath")
        widen.operation = "MULTIPLY"
        widen.inputs[1].default_value = 2.0
        invert = nodes.new("ShaderNodeMath")
        invert.operation = "SUBTRACT"
        invert.inputs[0].default_value = 1.0
        links.new(geo.outputs["Generated"], off.inputs[0])
        links.new(off.outputs[0], length.inputs[0])
        links.new(length.outputs["Value"], widen.inputs[0])
        links.new(widen.outputs["Value"], invert.inputs[1])
        falloff = invert.outputs["Value"]
    else:
        sep = nodes.new("ShaderNodeSeparateXYZ")
        links.new(geo.outputs["Generated"], sep.inputs["Vector"])
        if mode in ("nozzle", "nozzle-jet"):
            # An engine plume is the mirror case of a wake: the cone is built with its wide
            # mouth aft, so Generated Z is 1 at the bell and the hot end is the far one.
            falloff = sep.outputs["Z"]
        else:
            invert = nodes.new("ShaderNodeMath")
            invert.operation = "SUBTRACT"
            invert.inputs[0].default_value = 1.0
            links.new(sep.outputs["Z"], invert.inputs[1])
            falloff = invert.outputs["Value"]
        if mode in ("jet", "nozzle-jet"):
            # The axial ramp alone still leaves the cone's own wall: a streak fades at its
            # end but stops dead at its side, and eight of them union into a slab with a
            # hard outline. Multiplying in a cross-axis falloff removes that wall, so the
            # body's edge is where its depth runs out rather than where its mesh does.
            xy = nodes.new("ShaderNodeCombineXYZ")
            links.new(sep.outputs["X"], xy.inputs[0])
            links.new(sep.outputs["Y"], xy.inputs[1])
            off = nodes.new("ShaderNodeVectorMath")
            off.operation = "SUBTRACT"
            off.inputs[1].default_value = (0.5, 0.5, 0.0)
            arm = nodes.new("ShaderNodeVectorMath")
            arm.operation = "LENGTH"
            widen = nodes.new("ShaderNodeMath")
            widen.operation = "MULTIPLY"
            widen.inputs[1].default_value = 2.0
            edge = nodes.new("ShaderNodeMath")
            edge.operation = "SUBTRACT"
            edge.inputs[0].default_value = 1.0
            soft = nodes.new("ShaderNodeMath")
            soft.operation = "MULTIPLY"
            both = nodes.new("ShaderNodeMath")
            both.operation = "MULTIPLY"
            links.new(xy.outputs[0], off.inputs[0])
            links.new(off.outputs[0], arm.inputs[0])
            links.new(arm.outputs["Value"], widen.inputs[0])
            links.new(widen.outputs["Value"], edge.inputs[1])
            links.new(edge.outputs["Value"], soft.inputs[0])
            links.new(edge.outputs["Value"], soft.inputs[1])
            links.new(soft.outputs["Value"], both.inputs[0])
            links.new(falloff, both.inputs[1])
            falloff = both.outputs["Value"]

    if falloff is None:
        # A trail drawn along a curve has no honest per-primitive axis: Generated
        # coordinates normalise the whole bounding box, so any falloff would brighten one
        # end of the path for reasons the shape does not have. Constant depth, broken up by
        # the turbulence field, is the only reading that does not invent geometry.
        flat = nodes.new("ShaderNodeValue")
        flat.outputs[0].default_value = 1.0
        shape = flat.outputs[0]
    else:
        ramp = nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.0
        ramp.color_ramp.elements[1].position = 1.0
        links.new(falloff, ramp.inputs["Fac"])
        shape = ramp.outputs["Color"]
    if turb > 0.0:
        world_pos = nodes.new("ShaderNodeNewGeometry")
        noise = nodes.new("ShaderNodeTexNoise")
        noise.noise_dimensions = "3D"
        noise.inputs["Scale"].default_value = turb_scale
        noise.inputs["Detail"].default_value = 4.0
        noise.inputs["Roughness"].default_value = 0.6
        links.new(world_pos.outputs["Position"], noise.inputs["Vector"])
        # Remap 0..1 into [1-turb, 1] so the field only ever thins the gas, never adds
        # where the falloff already said there is none.
        band = nodes.new("ShaderNodeMath")
        band.operation = "MULTIPLY_ADD"
        band.inputs[1].default_value = turb
        band.inputs[2].default_value = 1.0 - turb
        links.new(noise.outputs["Fac"], band.inputs[0])
        rippled = nodes.new("ShaderNodeMath")
        rippled.operation = "MULTIPLY"
        links.new(shape, rippled.inputs[0])
        links.new(band.outputs["Value"], rippled.inputs[1])
        shape = rippled.outputs["Value"]

    for src, dst, base in (("Density", vol.inputs["Density"], density),
                           ("Emission", vol.inputs["Emission Strength"], strength)):
        mul = nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        mul.inputs[1].default_value = base
        links.new(shape, mul.inputs[0])
        links.new(mul.outputs["Value"], dst)

    links.new(vol.outputs["Volume"], out.inputs["Volume"])
    return mat


def add_curved_disc(name, center, body_radius, normal, size, lift, mat):
    """A disc bent onto the body's own curvature.

    A tangent flat disc on a sphere floats past the silhouette at the limb and renders
    as a bright sliver outside the body; a curved one hugs the surface everywhere.
    """
    c = mathutils.Vector(center)
    up = mathutils.Vector(normal).normalized()
    ref = mathutils.Vector((0, 0, 1.0)) if abs(up.z) < 0.9 else mathutils.Vector((1.0, 0, 0))
    u_axis = up.cross(ref).normalized()
    v_axis = up.cross(u_axis).normalized()
    rl = body_radius + lift
    tangent = c + up * rl

    bm = bmesh.new()
    rings, segs = 3, 18
    # Everything else is stored relative to the tangent point, which becomes the
    # object origin so a scale keyframe grows the crater in place.
    hub = bm.verts.new((0.0, 0.0, 0.0))
    grid = []
    for j in range(1, rings + 1):
        alpha = (size * j / rings) / rl
        row = []
        for k in range(segs):
            phi = TAU * k / segs
            sideways = u_axis * math.cos(phi) + v_axis * math.sin(phi)
            d = up * math.cos(alpha) + sideways * math.sin(alpha)
            row.append(bm.verts.new(c + d * rl - tangent))
        grid.append(row)
    for k in range(segs):
        bm.faces.new((hub, grid[0][k], grid[0][(k + 1) % segs]))
    for j in range(1, rings):
        for k in range(segs):
            bm.faces.new((grid[j - 1][k], grid[j - 1][(k + 1) % segs],
                          grid[j][(k + 1) % segs], grid[j][k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    total = mathutils.Vector((0.0, 0.0, 0.0))
    for face in bm.faces:
        total += face.normal
    if total.dot(up) < 0.0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)

    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = tuple(tangent)
    obj.data.materials.append(mat)
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj


def add_earth(name, radius, location, segments=96, rings=48, clouds=True, atmosphere=True):
    """Surface + cloud deck + limb glow as one unit; the returned object carries the spin."""
    earth = add_planet(name, radius, location, earth_material(scale=surface_scale(radius)),
                       segments=segments, rings=rings)
    shells = []
    if clouds:
        shells.append((f"{name}-clouds", radius * 1.022,
                       cloud_material(radius * 1.022, f"{name}-cloud-mat")))
    if atmosphere:
        shells.append((f"{name}-atmos", radius * 1.016,
                       atmosphere_material(f"{name}-atmos-mat")))
    for shell_name, shell_radius, mat in shells:
        shell = add_planet(shell_name, shell_radius, location, mat,
                           segments=segments, rings=rings)
        shell.parent = earth
        shell.matrix_parent_inverse = earth.matrix_world.inverted()
        shell.visible_shadow = False
    return earth


def fit_distance(radius, lens=50.0, margin=1.3, aspect=0.5625, sensor=36.0):
    """Camera distance at which a sphere of `radius` fills the tighter (vertical) frame."""
    vfov = 2.0 * math.atan(sensor * aspect / 2.0 / lens)
    return radius * margin / math.tan(vfov / 2.0)


def place_camera(cam, center, direction, radius, margin=1.3):
    """Back the camera off along `direction` until the subject fits, then aim it."""
    d = math.sqrt(sum(c * c for c in direction)) or 1.0
    dist = fit_distance(radius, cam.data.lens, margin)
    cam.location = tuple(center[i] + direction[i] / d * dist for i in range(3))
    aim(cam, center)


# Figure space: hips at the origin, the whole body facing local +X. That is not a style
# choice. The crew seat rigs are rotated by `atan2(-y, -x)`, which points their local +X at
# the cabin centre, so a figure built facing +Y or -Y sits sideways in its own seat — and a
# backrest built at local -Y lands beside the occupant instead of behind them. Both of those
# were true of the old crew quarters, at three different conventions in one beat. The seat
# parts in `beat_crew_quarters` and the EVA calls below follow this one.
_ASTRONAUT_POSES = {
    # Joint chain in figure space. `sit` assumes a deck 0.70 below the hips and hands
    # resting on the thighs; `stand` puts the sole 1.065 below the hips, so a standing
    # figure has its rig at z=1.05 to be feet-on-ground.
    "stand": dict(elbow=(0.02, 0.30, 0.10), wrist=(0.05, 0.26, -0.18),
                  glove=(0.07, 0.25, -0.25), hip=(0.01, 0.135, -0.16),
                  knee=(0.02, 0.14, -0.58), ankle=(0.01, 0.14, -0.94),
                  boot=(0.06, 0.14, -0.995)),
    "sit": dict(elbow=(0.10, 0.30, 0.14), wrist=(0.30, 0.23, 0.02),
                glove=(0.38, 0.21, -0.02), hip=(0.02, 0.14, -0.06),
                knee=(0.34, 0.15, -0.10), ankle=(0.32, 0.15, -0.62),
                boot=(0.37, 0.15, -0.665)),
}


def add_astronaut(prefix, location, mat_suit, mat_vis, pose="stand"):
    """A suited figure: hard upper torso, PLSS pack, bubble visor, articulated limbs.

    The previous version was one cylinder, one sphere and four sausages, and it read as a
    clipart dummy at every camera distance. What makes a pressure garment read as one is
    the hardgoods silhouette — HUT, neck ring, chest module, backpack — plus the accordion
    folds around every joint, because those are the lines the eye uses to find the elbows
    and knees. Parts are parented to a rig empty at `location`, so the caller places and
    turns the whole figure with one transform.
    """
    rig = bpy.data.objects.new(f"{prefix}Rig", None)
    bpy.context.scene.collection.objects.link(rig)
    rig.location = location
    joints = _ASTRONAUT_POSES[pose]
    mat_hard = material_principled(f"{prefix}-hard", (0.52, 0.53, 0.55, 1.0),
                                   metallic=0.35, roughness=0.45)
    mat_pack = material_principled(f"{prefix}-pack", (0.44, 0.44, 0.46, 1.0), roughness=0.72)
    mat_dark = material_principled(f"{prefix}-glove", (0.14, 0.14, 0.16, 1.0), roughness=0.9)
    # The joint bellows get their own material, and it is not the hardgoods one. Metal at
    # 0.52 grey rendered every fold as a bright plastic ring sitting on top of the limb,
    # which is the read that made the figure look like an articulated mannequin. Real
    # bellows are rubber-coated fabric: darker than the garment they join, matte, and
    # thin enough that the eye reads a crease rather than an added part.
    mat_bellows = material_principled(f"{prefix}-bellows", (0.26, 0.25, 0.26, 1.0),
                                      metallic=0.0, roughness=0.92)
    # The helmet shell is a separate material from the garment on purpose. When it took the
    # suit tile the head rendered in the same colour as the body and the figure read as a
    # bald person sitting down — the helmet silhouette is the single fastest "astronaut"
    # cue the shot has, so it has to break the suit's colour.
    mat_shell = material_principled(f"{prefix}-shell", (0.86, 0.86, 0.88, 1.0),
                                    metallic=0.05, roughness=0.42)
    soft = []

    def add(creator, name, local, material, smooth=True, **kwargs):
        creator(location=(0, 0, 0), **kwargs)
        obj = bpy.context.active_object
        obj.name = f"{prefix}-{name}"
        obj.location = local
        obj.data.materials.append(material)
        if smooth:
            bpy.ops.object.shade_smooth()
        obj.parent = rig
        return obj

    def box(name, centre, scale, material):
        obj = add(bpy.ops.mesh.primitive_cube_add, name, centre, material, size=1.0)
        obj.scale = scale
        # Local space again: the size lives in the object scale, so 0.06 rounds the
        # PLSS by ~4 cm and a glove by ~5 mm — both of which is roughly what they are.
        harden_edges(obj, width=0.06, segments=2)
        return obj

    def limb(name, a, b, radius, folds=2):
        """One limb segment as a cylinder stretched between two joints, with its folds."""
        va, vb = mathutils.Vector(a), mathutils.Vector(b)
        axis = vb - va
        quat = axis.to_track_quat("Z", "Y")
        seg = add(bpy.ops.mesh.primitive_cylinder_add, name, tuple((va + vb) / 2.0),
                  mat_suit, radius=radius, depth=axis.length, vertices=20)
        seg.rotation_mode = "QUATERNION"
        seg.rotation_quaternion = quat
        soft.append(seg)
        for at in (0.34, 0.66)[:folds]:
            ring = add(bpy.ops.mesh.primitive_torus_add, f"{name}-fold",
                       tuple(va.lerp(vb, at)), mat_bellows,
                       major_radius=radius * 1.03, minor_radius=radius * 0.16,
                       major_segments=20, minor_segments=6)
            ring.rotation_mode = "QUATERNION"
            ring.rotation_quaternion = quat
        return seg

    torso = add(bpy.ops.mesh.primitive_cylinder_add, "hut", (0, 0, 0.24), mat_suit,
                radius=0.20, depth=0.36, vertices=24)
    torso.scale = (1.0, 0.86, 1.0)
    waist = add(bpy.ops.mesh.primitive_cylinder_add, "waist", (0, 0, -0.06), mat_suit,
                radius=0.17, depth=0.22, vertices=24)
    helmet = add(bpy.ops.mesh.primitive_uv_sphere_add, "helmet", (0, 0, 0.66), mat_shell,
                 segments=32, ring_count=16, radius=0.20)
    # The visor has to clear the shell. At centre 0.045 / x-scale 0.72 its front reached
    # 0.171 against a helmet surface at 0.200, so the gold bubble sat *inside* the white
    # sphere and the face read as a grey ring with nothing in it.
    visor = add(bpy.ops.mesh.primitive_uv_sphere_add, "visor", (0.06, 0, 0.66), mat_vis,
                segments=32, ring_count=16, radius=0.175)
    visor.scale = (0.95, 0.90, 0.86)
    # The rim is what sells the bubble: without it the gold sphere reads as a face painted
    # into the helmet, which is exactly how the old figures looked in the frame. At x 0.15
    # with a 0.135 ring radius it lies on the shell's own surface (sqrt(0.15^2+0.135^2)=0.202).
    rim = add(bpy.ops.mesh.primitive_torus_add, "visor-rim", (0.15, 0, 0.66), mat_hard,
              major_radius=0.135, minor_radius=0.020, major_segments=24, minor_segments=8)
    rim.rotation_euler = (0, math.radians(90), 0)
    add(bpy.ops.mesh.primitive_torus_add, "neck-ring", (0, 0, 0.46), mat_hard,
        major_radius=0.125, minor_radius=0.022, major_segments=24, minor_segments=8)

    # Life-support pack behind the HUT, with the two tanks proud of its sides so the
    # silhouette from a cabin camera is a backpack and not a box.
    box("plss", (-0.32, 0, 0.26), (0.28, 0.46, 0.62), mat_pack)
    for side in (-1, 1):
        add(bpy.ops.mesh.primitive_cylinder_add, f"tank{side}", (-0.32, 0.30 * side, 0.26),
            mat_pack, radius=0.06, depth=0.55, vertices=16)
    # Chest module, flat against the front of the HUT, with two knobs on it: the detail
    # that tells the eye this is equipment worn on the suit, not a decoration.
    box("rcu", (0.155, 0, 0.30), (0.09, 0.26, 0.20), mat_pack)
    for side in (-1, 1):
        knob = add(bpy.ops.mesh.primitive_cylinder_add, f"valve{side}",
                   (0.215, 0.07 * side, 0.30), mat_hard, radius=0.028, depth=0.05,
                   vertices=12)
        knob.rotation_euler = (0, math.radians(90), 0)
        cap = add(bpy.ops.mesh.primitive_cylinder_add, f"comm{side}",
                  (0, 0.185 * side, 0.66), mat_hard, radius=0.045, depth=0.06, vertices=16)
        cap.rotation_euler = (math.radians(90), 0, 0)

    arms, legs = [], []
    for side in (-1, 1):
        shoulder = add(bpy.ops.mesh.primitive_uv_sphere_add, f"shoulder{side}",
                       (0.0, 0.235 * side, 0.38), mat_suit,
                       segments=20, ring_count=12, radius=0.115)
        soft.append(shoulder)
        elbow = (joints["elbow"][0], joints["elbow"][1] * side, joints["elbow"][2])
        wrist = (joints["wrist"][0], joints["wrist"][1] * side, joints["wrist"][2])
        arms.append(limb(f"upper-arm{side}", (0.0, 0.25 * side, 0.37), elbow, 0.085))
        arms.append(limb(f"forearm{side}", elbow, wrist, 0.075))
        cuff = add(bpy.ops.mesh.primitive_torus_add, f"wrist{side}", wrist, mat_hard,
                   major_radius=0.078, minor_radius=0.020,
                   major_segments=20, minor_segments=6)
        cuff.rotation_mode = "QUATERNION"
        cuff.rotation_quaternion = (mathutils.Vector(wrist) -
                                    mathutils.Vector(elbow)).to_track_quat("Z", "Y")
        glove = box(f"glove{side}", (joints["glove"][0], joints["glove"][1] * side,
                                     joints["glove"][2]), (0.13, 0.09, 0.065), mat_dark)
        hip = (joints["hip"][0], joints["hip"][1] * side, joints["hip"][2])
        knee = (joints["knee"][0], joints["knee"][1] * side, joints["knee"][2])
        ankle = (joints["ankle"][0], joints["ankle"][1] * side, joints["ankle"][2])
        hipball = add(bpy.ops.mesh.primitive_uv_sphere_add, f"hip{side}", hip, mat_suit,
                      segments=20, ring_count=12, radius=0.105)
        soft.append(hipball)
        legs.append(limb(f"thigh{side}", hip, knee, 0.115))
        legs.append(limb(f"shin{side}", knee, ankle, 0.088))
        box(f"boot{side}", (joints["boot"][0], joints["boot"][1] * side,
                            joints["boot"][2]), (0.20, 0.10, 0.075), mat_dark)

    # Wrinkles are geometry, not shading: a perfectly smooth suit cylinder is the one
    # silhouette that no texture can rescue. Amplitude is a fraction of each part's own
    # diagonal, so the same call gives 1.4 cm on the torso and 0.9 cm on a forearm.
    for i, ob in enumerate([torso, waist] + arms + legs):
        surface_relief(ob, amplitude=0.02, wavelength=0.55, cuts=1, turbulence=0.55,
                       seed=(i * 1.7, i * 0.9, i * 2.3))
    # cube_size 0.25, not 1.0: the suit tile is 0.25 m per tile already, so the finer cube
    # is what puts the weave at a readable scale on a part this small. The helmet shell,
    # the visor and the hardgoods stay off the tile — a gold vacuum coating and a polycarbonate
    # bubble are not fabric — and the relief runs before the UVs, never after.
    apply_surface([torso, waist] + soft, "suit_fabric", cube_size=0.25)
    return rig


def add_cubesat(location, index):
    """Bus body + two solar wings + antenna: reads as a CubeSat, not a dice cube.

    Everything hangs off one empty, so animating the returned rig moves the wings.
    """
    mat_body = material_principled(f"cubesat-body-{index}", (0.75, 0.75, 0.78, 1.0),
                                   metallic=0.4, roughness=0.4)
    mat_panel = solar_cell_material(f"cubesat-panel-{index}", cells=(12, 6), axes="XY")
    mat_gold = material_principled(f"cubesat-foil-{index}", (0.85, 0.65, 0.2, 1.0),
                                   metallic=0.9, roughness=0.3)

    rig = bpy.data.objects.new(f"Cubesat{index}Rig", None)
    bpy.context.scene.collection.objects.link(rig)
    rig.location = location

    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
    body = bpy.context.active_object
    body.name = f"Cubesat-{index}"
    body.scale = (0.6, 0.42, 0.42)
    body.data.materials.append(mat_body)
    body.parent = rig

    for side in (-1, 1):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0.75 * side, 0))
        wing = bpy.context.active_object
        wing.name = f"Cubesat-{index}-wing{side}"
        wing.scale = (1.4, 0.7, 0.02)
        wing.data.materials.append(mat_panel)
        wing.parent = rig
        harden_edges(wing, width=0.008, segments=2)

    bpy.ops.mesh.primitive_cylinder_add(radius=0.03, depth=0.5, location=(0, 0, 0.45))
    ant = bpy.context.active_object
    ant.name = f"Cubesat-{index}-antenna"
    ant.data.materials.append(mat_gold)
    ant.parent = rig
    # cube_size 0.25 because the bus is 0.6 m across: at 1.0 the silver quilt would land
    # at roughly twice the size of the panel it is stretched over. Wings keep mat_panel —
    # solar cells are not in the palette, and a metallic tile on them is a wrong material.
    harden_edges(body, width=0.008, segments=2)
    # The quilt is buckled in geometry before the tile goes on. A flat box wearing a quilt
    # pattern is a texture; the same box with a centimetre of oil-can dimple between the
    # stitches is a blanket, and the difference is exactly what made these read as plastic
    # dice.
    surface_relief(body, amplitude=0.014, wavelength=0.5, cuts=5, turbulence=0.45,
                   seed=(1.7 * index, 0.4, 2.1))
    surface_relief(ant, amplitude=0.05, wavelength=0.5, cuts=2, smooth=False,
                   seed=(0.3, 2.2 * index, 1.1))
    apply_surface(body, "mli_silver", cube_size=0.25)
    apply_surface(ant, "mli_gold", cube_size=0.25)
    return rig


def make_dome(obj):
    """Delete the lower half of a sphere object; a full sphere reads as an egg.

    Used for parachute canopies, which are domes with an open skirt.
    """
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    for face in [f for f in bm.faces if f.calc_center_median().z < 0.0]:
        bm.faces.remove(face)
    bm.to_mesh(obj.data)
    bm.free()


def surface_point(center, radius, u, v):
    """Point on a sphere from two normalised coordinates, plus its outward normal.

    v is measured from +Z, not from the near side: v=1 is +Z and v=0 is -Z. A band meant
    to sit in the ground a camera can see has to be derived from the sub-camera point and
    the tangent circle, or the craters land on the far side of the body.
    """
    theta = u * TAU
    phi = math.acos(max(-1.0, min(1.0, 2.0 * v - 1.0)))
    sp = math.sin(phi)
    offset = (radius * sp * math.cos(theta), radius * sp * math.sin(theta), radius * math.cos(phi))
    p = tuple(center[i] + offset[i] for i in range(3))
    return p, mathutils.Vector(offset).normalized()


def add_crater_relief(obj, center, radius, specs, depth_ratio=0.42):
    """Push the body's own skin inward where the craters are.

    A disc painted on a sphere survives exactly one lighting angle. At every other angle
    the same flat grey circle reads as a decal, which is what made the far side look drawn
    rather than excavated. A displaced bowl has a shadowed far wall and a lit near wall, so
    it reads as a hole from any camera position — and it costs one pass over the mesh.

    Profile is a parabolic floor out to the rim, then a Gaussian ridge just outside it;
    real craters throw a lip up, and that lip is what gives the rim its own shading. The
    lip is a sixth of the depth: at 0.4 it was a mountain ring that caught the sun along
    its whole near edge, and a lit ring around a dark hole is the donut every one of these
    bowls used to render as.

    Each spec carries a third term, `wear` in 0..1. A surface hit for four billion years is
    a mixture of ages: the youngest bowl is deep with a sharp crest, the oldest is a
    shallow disc with its rim knocked down. One profile drawn N times is what made every
    crater on the far side look stamped from the same mould, so `wear` scales the depth and
    removes the ridge as it rises.
    """
    c = mathutils.Vector(center)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bowls = []
    for n, size, wear in specs:
        theta = size / radius
        cos_lim = math.cos(min(1.8 * theta, 1.4))
        depth = size * depth_ratio * (1.0 - 0.55 * wear)
        bowls.append((n, cos_lim, theta, depth, depth * 0.16 * (1.0 - wear)))
    for vert in bm.verts:
        v = vert.co
        dist = v.length
        if dist < 1e-6:
            continue
        d = v / dist
        off = 0.0
        for n, cos_lim, theta, depth, rim_h in bowls:
            dot = d.dot(n)
            if dot < cos_lim:
                continue
            x = math.acos(max(-1.0, min(1.0, dot))) / theta
            if x < 1.0:
                off -= depth * (1.0 - x * x)
            t = (x - 1.06) / 0.30
            off += rim_h * math.exp(-t * t)
        if off:
            vert.co = d * (dist + off)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def material_soft_patch(name, color, size, roughness=1.0):
    """A surface-coloured patch that fades out before its own rim.

    Every hard-edged disc on these bodies — crater floors, frost, mare — turns into a
    decal the moment it is lit, because the eye finds the edge rather than the shape.
    Alpha falling off across the outer half of the patch leaves the same albedo change
    with no silhouette to trace.
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*color[:3], 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    length = nodes.new("ShaderNodeVectorMath")
    length.operation = "LENGTH"
    links.new(nodes.new("ShaderNodeTexCoord").outputs["Object"], length.inputs[0])
    fade = nodes.new("ShaderNodeMapRange")
    fade.inputs["From Min"].default_value = 0.50 * size
    fade.inputs["From Max"].default_value = 0.97 * size
    fade.inputs["To Min"].default_value = 1.0
    fade.inputs["To Max"].default_value = 0.0
    links.new(length.outputs["Value"], fade.inputs["Value"])
    links.new(fade.outputs["Result"], bsdf.inputs["Alpha"])
    set_transparent(mat)
    return mat


def cap_v_window(radius, half):
    """The v value at arc distance `half` from +Z, for use as a crater field's uv_range."""
    return (1.0 + math.cos(min(half / radius, 1.4))) / 2.0


def add_terrain_cap(name, center, radius, mat=None, half=3.0, cols=512, lift=0.0):
    """A fine spherical patch standing in for the ground a camera is standing on.

    A UV sphere cannot do double duty as a foreground plane. Its rings are latitude
    circles, so the vertex spacing across the few units a ground camera can see is the same
    as it is across the whole body: 0.49 on a radius-40 Moon at 512x256. A bowl needs its
    floor and rim sampled, so nothing under 1.6 spacings can be excavated, and the only way
    to fill a 2.4-unit visible field at that size is to pack the craters until they merge
    into the pillow ridge earth-rise was rendering. This puts the vertices where the camera
    is: one grid, spacing 2*half/cols.

    `lift` raises the patch off the body it sits on, because that body's skin is still
    underneath and two coincident surfaces z-fight. It has to exceed the deepest crater the
    patch excavates, or the bowl punches through to the sphere behind it. Keep the patch
    wider than the visible field so its edge falls past the horizon.
    """
    bm = bmesh.new()
    rr = radius + lift
    grid = []
    for j in range(cols + 1):
        y = -half + 2.0 * half * j / cols
        row = []
        for i in range(cols + 1):
            x = -half + 2.0 * half * i / cols
            row.append(bm.verts.new((x, y, math.sqrt(max(rr * rr - x * x - y * y, 0.0)))))
        grid.append(row)
    for j in range(cols):
        for i in range(cols):
            bm.faces.new((grid[j][i], grid[j][i + 1],
                          grid[j + 1][i + 1], grid[j + 1][i]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    obj = bpy.data.objects.new(name, me)
    obj.location = center
    bpy.context.collection.objects.link(obj)
    if mat is not None:
        obj.data.materials.append(mat)
    return obj


def add_regolith_blocks(prefix, center, radius, count, seed, size=(0.05, 0.30),
                        arc=(4.6, 24.0), mat=None, sink=0.42):
    """Rocks lying where they fell, dropped onto a body and settled half in.

    A tiled ground plane with nothing standing on it reads as a surface photographed from a
    helicopter. There are no contact shadows, so the eye cannot tell how far away the ground
    is, and it certainly cannot tell what scale the hardware is. Blocks are the cheapest cure:
    a hand of rock under a low sun throws a hard shadow that says *this is dirt, and it is
    metres away*. Being real geometry, they also do not shimmer between frames the way a
    stippled tile does.

    `arc` restricts the drop to a band of horizontal distance from the +Z pole, because the
    pad under a habitat is graded site work and a boulder there is one that came through the
    ceiling. `size` is drawn with a power bias so most of the field is gravel and a handful are
    the blocks you can name.

    A private Random instance rather than the module's, because `add_crater_field` seeds the
    global generator — a helper sharing it would move every later draw in the file.
    """
    import random
    rng = random.Random(seed)
    made = []
    for k in range(count):
        d = rng.uniform(*arc)
        if d >= radius:
            continue
        th = rng.uniform(0.0, TAU)
        n = mathutils.Vector((d * math.cos(th), d * math.sin(th),
                              math.sqrt(radius * radius - d * d))).normalized()
        s = size[0] + (size[1] - size[0]) * rng.random() ** 2.4
        sx = s * rng.uniform(0.70, 1.25)
        sy = s * rng.uniform(0.70, 1.25)
        sz = s * rng.uniform(0.34, 0.60)
        # The ico sphere is unit radius, so its half-height along its own Z is sz, and its
        # centre has to sit sz*(0.5 - sink) *above* the ground for `sink` to be the fraction of
        # the block left under it. Sinking the centre by s*sink instead buries 0.9 of every
        # block — the first version of this helper put 520 rocks in the scene and not one of
        # them in the render.
        bpy.ops.mesh.primitive_ico_sphere_add(
            subdivisions=1, radius=1.0,
            location=mathutils.Vector(center) + n * (radius + sz * (0.5 - sink)))
        ob = bpy.context.active_object
        ob.name = f"{prefix}{k}"
        ob.rotation_euler = (n.to_track_quat("Z", "Y") @ mathutils.Quaternion(
            mathutils.Vector((0.0, 0.0, 1.0)), rng.uniform(0.0, math.pi))).to_euler()
        ob.scale = (sx, sy, sz)
        if mat is not None:
            ob.data.materials.append(mat)
        made.append(ob)
    return made


def add_crater_field(prefix, body, radius, count, seed=7, size_fracs=(0.008, 0.045),
                     uv_range=None, mat_floor=None, min_gap=1.05, relief=None, also=(),
                     floor_color=(0.095, 0.096, 0.105), floor_worn=(0.165, 0.165, 0.180),
                     size_bias=2.2, spacing=None):
    """Crater a body: displace its skin where the mesh can carry the bowl, paint where it
    cannot.

    Returns the floor patches. On a displaced body they sit just above the bottom of their
    own bowl, so the bowl wall hides their edges and only a dark pool remains; on a painted
    body they ride a hair above the surface and their own radial alpha fade hides the rim.
    Either way there is no bright ring — that ring was the single most obvious "drawn on"
    mark in every lunar shot.

    `size_fracs` are crater radii as a fraction of the body radius, not absolute units. In
    metres the same numbers mean a 300 km crater on a nearby Moon and a 3 km one on a
    distant one, so the sizes have to travel with the body. Real prominence at whole-disk
    scale is 3-9 % of the diameter, which is a fraction of 0.015-0.045 here: the old
    absolute ranges landed at 0.07-0.21, i.e. South Pole-Aitken basins repeated twenty
    times, and that is what read as cartoon bowls rather than terrain.

    `size_bias` draws the sizes. A uniform draw over the range produces twenty craters of
    comparable width spaced evenly apart, which is a polka-dot pattern; a surface that has
    been hit for four billion years is saturated, so most bowls are small and a handful are
    large. Raising the uniform draw to a power gives that distribution without changing the
    range.

    Each crater also draws an age. `floor_color` is the fresh impact-melt floor and
    `floor_worn` is what that floor looks like once regolith has been reworked across it,
    so the same field carries sharp dark bowls and pale shallow discs side by side instead
    of N copies of one profile.

    relief=None decides from the mesh: a bowl needs its floor and rim sampled, so the
    smallest crater has to be wider than about 1.6 vertex spacings.

    also takes (shell, shell_radius) pairs — a mare deck riding above the body has to be
    displaced by the same bowls or it bridges across them and reads as a shrink-wrap.
    """
    import random
    random.seed(seed)
    lo, hi = uv_range or (0.0, 1.0)
    f_lo, f_hi = size_fracs
    center = tuple(body.location)
    if spacing is None:
        spacing = radius * TAU / math.sqrt(2.0 * len(body.data.vertices))
    if relief is None:
        relief = f_lo * radius >= 1.6 * spacing

    picked = []
    for _ in range(count * 12):
        if len(picked) >= count:
            break
        u, v = random.random(), lo + random.random() * (hi - lo)
        p, n = surface_point(center, radius, u, v)
        p = mathutils.Vector(p)
        size = radius * (f_lo + (f_hi - f_lo) * random.random() ** size_bias)
        wear = random.random() ** 0.65
        # Overlapping rims merge into shapes the eye reads as faces, which is exactly what
        # happened on the far side. Keep every pair of centres further apart than the sum
        # of their radii plus a margin.
        if any((p - q).length < (size + s) * min_gap for q, _, s, _w in picked):
            continue
        picked.append((p, n, size, wear))

    specs = [(n, s, w) for _, n, s, w in picked]
    if relief:
        add_crater_relief(body, center, radius, specs)
        for shell, shell_radius in also:
            add_crater_relief(shell, center, shell_radius, specs)

    made = []
    for i, (_, n, size, wear) in enumerate(picked):
        # The fade stops are absolute distances in the patch's own units, so each crater
        # needs its own material; one shared patch would fade at the wrong radius.
        tint = tuple(floor_color[j] + (floor_worn[j] - floor_color[j]) * wear * 0.75
                     for j in range(3))
        mat = mat_floor or material_soft_patch(f"{prefix}-soft{i}", tint,
                                               size * 0.62, roughness=1.0)
        lift = -size * 0.26 if relief else size * 0.010
        floor = add_curved_disc(f"{prefix}-floor{i}", center, radius, n,
                                size * 0.62, lift, mat)
        floor.visible_shadow = False
        made.append(floor)
    return made


def add_orion(prefix, location, mat_hull, mat_metal, mat_panel):
    """Crew module + docking ring + service module + engine bell + two solar wings.

    Assembled nose-up along +Z and returned as an empty parent, so callers can
    rotate the whole stack with one animated transform.
    """
    rig = bpy.data.objects.new(f"{prefix}Rig", None)
    bpy.context.scene.collection.objects.link(rig)
    rig.location = location

    parts = []
    bpy.ops.mesh.primitive_cone_add(radius1=0.95, radius2=0.28, depth=1.05, location=(0, 0, 1.15))
    crew = bpy.context.active_object
    crew.name = f"{prefix}-crew"
    crew.data.materials.append(mat_hull)
    bpy.ops.object.shade_smooth()
    parts.append(crew)

    bpy.ops.mesh.primitive_cylinder_add(radius=0.42, depth=0.3, location=(0, 0, 1.9))
    dock = bpy.context.active_object
    dock.name = f"{prefix}-dock"
    dock.data.materials.append(mat_metal)
    parts.append(dock)

    bpy.ops.mesh.primitive_cylinder_add(radius=0.85, depth=1.6, location=(0, 0, -0.2))
    sm = bpy.context.active_object
    sm.name = f"{prefix}-sm"
    sm.data.materials.append(mat_metal)
    bpy.ops.object.shade_smooth()
    parts.append(sm)

    bpy.ops.mesh.primitive_cone_add(radius1=0.55, radius2=0.3, depth=0.6, location=(0, 0, -1.3))
    bell = bpy.context.active_object
    bell.name = f"{prefix}-bell"
    bell.data.materials.append(mat_metal)
    parts.append(bell)

    booms = []
    for side in (-1, 1):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.06, depth=1.0,
                                            location=(0.95 * side, 0, -0.2),
                                            rotation=(0, math.radians(90), 0))
        boom = bpy.context.active_object
        boom.name = f"{prefix}-boom{side}"
        boom.data.materials.append(mat_metal)
        parts.append(boom)
        booms.append(boom)
        bpy.ops.mesh.primitive_cube_add(size=1, location=(2.3 * side, 0, -0.2))
        wing = bpy.context.active_object
        wing.name = f"{prefix}-wing{side}"
        wing.scale = (1.6, 0.04, 1.1)
        wing.data.materials.append(mat_panel)
        parts.append(wing)

    for part in parts:
        part.parent = rig  # parts are modelled at the origin; the rig supplies the offset

    # Milling and blanketing, not paint: the cone and the small machined fittings are
    # panelled aluminium, and a real service module is MLI-wrapped rather than bare metal.
    # The wings keep mat_panel — solar cells are not in the palette and a tile on them is
    # the wrong material. No bevel on `crew` or `sm`: both are already shade_smooth, and a
    # bevel modifier on a smoothed body fights the smooth shading.
    #
    # The service module is buckled before it is blanketed: a wrapped cylinder is a
    # cylinder until the blanket creases, and the crease has to move the silhouette because
    # the highlight runs along it. Relief first, UVs after, so the quilt follows the wrinkle.
    surface_relief(sm, amplitude=0.012, wavelength=0.20, cuts=5, turbulence=0.5,
                   seed=(0.7, 1.3, 2.9))
    apply_surface([crew, dock, bell] + booms, "hull_panel")
    apply_surface(sm, "mli_silver")
    for machined in (dock, bell, *booms):
        harden_edges(machined)
    # Circumferential beads on the crew cone and a bolt circle on the docking ring: two
    # small parts that give the eye a size reference on a vehicle with none. The bead radius
    # is interpolated along the cone's own taper so a ring sits on the hull, not inside it.
    def cone_radius(z):
        return 0.95 - (0.95 - 0.28) * (z - 0.625) / 1.05

    for z in (0.86, 1.20, 1.52):
        for ring in stiffener_rings(f"{prefix}-crew", center=(0, 0, z),
                                    radius=cone_radius(z), count=1, spacing=0.0,
                                    width=0.016, material=mat_metal):
            ring.parent = rig
    for bolt in bolt_circle(f"{prefix}-dock", center=(0, 0, 2.05), radius=0.34, count=12,
                            bolt_radius=0.022, material=mat_metal):
        bolt.parent = rig
    return rig


def add_rocket(prefix, location, stages, radius=0.5, srbs=0, tower=False, mat_dark=None):
    """Vertical rocket from a stage list [(height, Material), ...], bottom-up.

    Black interstage bands, engine bells and an optional launch-escape tower are
    what make two rockets read as Saturn V versus SLS instead of two pipes.
    """
    parts = []
    hull_parts = []
    z = 0.0
    for i, (h, mat) in enumerate(stages):
        bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=h,
                                            location=(0, 0, z + h / 2.0))
        stage = bpy.context.active_object
        stage.name = f"{prefix}-stage{i}"
        stage.data.materials.append(mat)
        bpy.ops.object.shade_smooth()
        # A tank is built from rolled sheets stiffened underneath, so it is never flat: the
        # shallow oil-can between the stringers is what a moving highlight reads as
        # structure instead of as a rendered primitive. `wavelength` is a fraction of the
        # body's own diagonal, and `cuts` has to put at least two loops across it — on a
        # cylinder that means many loops, because a primitive cylinder has exactly one edge
        # running down its length. Anything finer than a couple of metres belongs to the
        # tile's bump map, not to the mesh.
        surface_relief(stage, amplitude=0.004, wavelength=0.20, cuts=8, turbulence=0.4,
                       seed=(i * 2.3, 0.9, 1.7))
        parts.append(stage)
        hull_parts.append(stage)

        bpy.ops.mesh.primitive_cylinder_add(radius=radius * 1.04, depth=h * 0.11,
                                            location=(0, 0, z + h * 0.94))
        band = bpy.context.active_object
        band.name = f"{prefix}-band{i}"
        band.data.materials.append(mat_dark)
        parts.append(band)

        for bell in (-1, 1):
            bpy.ops.mesh.primitive_cone_add(radius1=radius * 0.3, radius2=radius * 0.12,
                                            depth=h * 0.13,
                                            location=(bell * radius * 0.45, 0, z + h * 0.03),
                                            rotation=(math.radians(180), 0, 0))
            noz = bpy.context.active_object
            noz.name = f"{prefix}-nozzle{i}-{bell}"
            noz.data.materials.append(mat_dark)
            parts.append(noz)
        z += h

    if srbs:
        for k in range(srbs):
            a = k * TAU / srbs
            x, y = radius * 1.6 * math.cos(a), radius * 1.6 * math.sin(a)
            h = z * 0.42
            bpy.ops.mesh.primitive_cylinder_add(radius=radius * 0.38, depth=h,
                                                location=(x, y, h / 2.0))
            srb = bpy.context.active_object
            srb.name = f"{prefix}-srb{k}"
            srb.data.materials.append(material_principled(f"{prefix}-srb-m{k}",
                                                          (0.82, 0.82, 0.8, 1.0),
                                                          roughness=0.6))
            bpy.ops.object.shade_smooth()
            parts.append(srb)
            bpy.ops.mesh.primitive_cone_add(radius1=radius * 0.38, radius2=0.02,
                                            depth=h * 0.14, location=(x, y, h * 1.06))
            nose = bpy.context.active_object
            nose.name = f"{prefix}-srbnose{k}"
            nose.data.materials.append(mat_dark)
            parts.append(nose)

    bpy.ops.mesh.primitive_cone_add(radius1=radius, radius2=radius * 0.25, depth=radius * 2.4,
                                    location=(0, 0, z + radius * 1.2))
    fairing = bpy.context.active_object
    fairing.name = f"{prefix}-fairing"
    fairing.data.materials.append(stages[-1][1])
    bpy.ops.object.shade_smooth()
    parts.append(fairing)
    hull_parts.append(fairing)

    if tower:
        bpy.ops.mesh.primitive_cylinder_add(radius=radius * 0.12, depth=radius * 2.6,
                                            location=(0, 0, z + radius * 3.4))
        mast = bpy.context.active_object
        mast.name = f"{prefix}-tower"
        mast.data.materials.append(mat_dark)
        parts.append(mast)

    # The stage cylinders and the payload fairing over them carry the same white hull
    # material, so they get the same panel tile; texturing the stages and leaving the
    # fairing flat would show a seam mid-vehicle. No harden_edges: these bodies are
    # shade_smooth, and a bevel on a smoothed pipe fights the smoothing. Dark bands,
    # nozzles, nose caps and the tower keep their materials, and the SRB casings keep
    # theirs because their material is minted here, not the caller's hull material.
    apply_surface(hull_parts, "hull_panel")

    rig = bpy.data.objects.new(f"{prefix}Rig", None)
    bpy.context.scene.collection.objects.link(rig)
    rig.location = location
    for part in parts:
        part.parent = rig  # parts are modelled at the origin; the rig supplies the offset
    return rig, z + radius * 2.4


def animate_keyframe(obj, data_path, keyframes):
    """Set keyframes: [(frame, value), ...]"""
    for frame, value in keyframes:
        obj.driver_remove(data_path)
        if isinstance(value, (tuple, list)):
            for i, v in enumerate(value):
                obj.path_resolve(data_path)[i] = v
                obj.keyframe_insert(data_path=data_path, index=i, frame=frame)
        else:
            obj.path_resolve(data_path)
            setattr(obj, data_path.split(".")[-1], value)
            obj.keyframe_insert(data_path=data_path, frame=frame)


# ---------------------------------------------------------------------------
# Beat 1: SLS Launch
# ---------------------------------------------------------------------------
def add_space_fill(name="fill", location=(-6, -8, -4), energy=0.45,
                   color=(0.42, 0.55, 0.85)):
    """A dim second sun on the shadow side of a vehicle in deep space.

    SPACE_BG is nearly black, so with only the key sun a hull's unlit face renders as a
    silhouette and the whole craft reads as a cardboard cut-out. Real footage is never
    like that: earthshine off the planet below, the instrument shading and the camera's
    own exposure floor all lift the dark face a few percent. One low-energy cool sun does
    the same job and costs no render time.
    """
    return add_sun_light(name, location=location, energy=energy, color=color)


def beat_sls_launch(output_dir):
    print("\n=== Beat 1: SLS Launch ===", flush=True)
    wipe()
    setup_scene(fps=30, frame_end=SHOT_FRAMES, resolution_x=1280, resolution_y=720)
    # Daylight over the pad: the sky is the fill, so no starfield here. AgX desaturates
    # hard, so the stops have to be far more chromatic than the colour you want to see.
    setup_sky(zenith=(0.010, 0.085, 0.400), mid=(0.045, 0.220, 0.550),
              horizon=(0.420, 0.550, 0.620), strength=0.85)

    cam = add_camera("cam-sls", location=(30, -42, 10), target=(0, 0, 13), lens=35.0)

    mat_body = material_principled("rocket-body", ROCKET_WHITE, metallic=0.1, roughness=0.4)
    # The engine gas is a volume, not a shape with a colour on it. Every surface treatment
    # of this plume has failed the same way — a cone mesh always shows its own outline, and
    # an outline that does not move with the flow inside it is what made the last pass read
    # as a pale-yellow solid. A volume body has no outline; what the eye sees is depth, so
    # overlapping bodies accumulate into one gas instead of stacking into shells.
    #
    # Luminance is set against the frame, not against a dark background. At 1.15 W the SRB
    # column measured *below* the sunlit concrete, so the brightest object in a launch shot
    # rendered as a smudge and the shot read as a parked rocket; a real liftoff frame has the
    # jet as its clipping highlight. These are scene-linear watts — and the core is capped
    # well below the gas, because at 11 W the whole column averaged over 1.0 and AgX turned
    # a flame into a white pillar with no colour left in it.
    mat_srb_gas = plasma_volume_material("srb-gas", (1.0, 0.55, 0.20), density=0.60,
                                         strength=2.6, mode="nozzle-jet", turb=0.92,
                                         turb_scale=1.15)
    mat_srb_core = plasma_volume_material("srb-core", (1.0, 0.78, 0.48), density=0.85,
                                          strength=5.2, mode="nozzle-jet", turb=0.75,
                                          turb_scale=1.9)
    # The core stage burns hydrogen and oxygen, and the product is steam: the real RS-25
    # plume is almost invisible in daylight except for the shock collars at the bells. Two
    # of the three biggest tells in a fake launch shot are a yellow cone where the SSMEs are
    # and no condensation cloud, so this one goes bluish-white and thin.
    mat_h2_gas = plasma_volume_material("h2-gas", (0.80, 0.88, 1.0), density=0.16,
                                        strength=1.1, mode="nozzle-jet", turb=0.9,
                                        turb_scale=1.6)
    mat_h2_core = plasma_volume_material("h2-core", (0.88, 0.95, 1.0), density=0.50,
                                         strength=3.0, mode="nozzle-jet", turb=0.6,
                                         turb_scale=2.6)
    # Mach diamonds are the one part of a real plume that does have an edge: standing shock
    # discs reflect the flow to full luminance, so they are geometry, not density.
    mat_shock = material_emissive("shock-collar", (1.0, 0.74, 0.44, 1.0), strength=5.0)
    # Exhaust that reaches the blast bucket does not stop: it turns sideways along the trench
    # and lifts as a dust-and-steam wall off the pad edge. For the first third of the shot
    # this *is* the flame — the vehicle has not yet lifted its own exhaust clear of the
    # concrete, so anything that reads as fire in those frames has to live on the pad.
    #
    # Radial, on spheres, not cones: a cone's own wall is a straight line, and the first
    # version of this cloud rendered as eight glowing triangular sheets standing on the deck.
    # A centre-out falloff has no line in it, so overlapping puffs accumulate into one mass.
    mat_blast = plasma_volume_material("blast-flow", (1.0, 0.50, 0.20), density=0.55,
                                       strength=1.9, mode="radial", turb=0.95,
                                       turb_scale=0.9)
    mat_metal = material_principled("metal", METAL_GREY, metallic=0.7, roughness=0.3)
    mat_dark = material_principled("rocket-dark", (0.05, 0.05, 0.06, 1.0), roughness=0.8)
    mat_steam = steam_material()
    mat_engine = material_principled("engine-bell", (0.30, 0.29, 0.28, 1.0),
                                     metallic=0.85, roughness=0.35)
    # The core stage wears sprayed-on foam, not paint. A uniformly white stack is the
    # single biggest reason this shot read as a toy: the real vehicle is orange between
    # two white boosters. Mottled rather than flat because foam is never one colour.
    mat_foam = material_surface("core-foam",
                                [(0.0, (0.250, 0.072, 0.016, 1.0)),
                                 (0.45, (0.430, 0.138, 0.028, 1.0)),
                                 (1.0, (0.560, 0.230, 0.060, 1.0))],
                                scale=2.2, detail=6.0, bump_strength=0.30,
                                roughness=0.85, warp=0.45)

    # One empty carries the whole stack off the pad, so the animation is a single
    # keyframed transform instead of a name-matching loop over every part.
    rig = bpy.data.objects.new("SlsRig", None)
    bpy.context.scene.collection.objects.link(rig)

    def part(op, name, mat, parent=True, smooth=False, **kwargs):
        op(**kwargs)
        obj = bpy.context.active_object
        obj.name = name
        obj.data.materials.append(mat)
        if smooth:
            bpy.ops.object.shade_smooth()
        if parent:
            obj.parent = rig
        return obj

    # Core, interstage, Orion and the launch abort system
    core = part(bpy.ops.mesh.primitive_cylinder_add, "CoreStage", mat_foam,
                radius=1.0, depth=14, location=(0, 0, 11), smooth=True)
    # Sprayed-on foam is applied in passes by hand, so the core stage is the least round and
    # least straight thing on the vehicle. Long-wavelength waviness has to be vertices: a
    # bump map cannot move the silhouette of a 14 m tank, and the silhouette is where the
    # eye decides whether this is an object or a shape.
    surface_relief(core, amplitude=0.0045, wavelength=0.22, cuts=9, turbulence=0.55,
                   seed=(2.1, 0.7, 1.4))
    # Stringer runs and the tank's circumferential joints, as real geometry on the core.
    for ring in stiffener_rings("Core", center=(0, 0, 11), radius=1.005, count=5,
                                spacing=3.0, width=0.035, material=mat_dark):
        ring.parent = rig
    interstage = part(bpy.ops.mesh.primitive_cylinder_add, "Interstage", mat_dark,
                      radius=1.02, depth=1.4, location=(0, 0, 18.7))
    harden_edges(interstage, width=0.03, segments=2)
    part(bpy.ops.mesh.primitive_cylinder_add, "CrewModule", mat_metal,
         radius=0.85, depth=1.3, location=(0, 0, 20.1), smooth=True)
    part(bpy.ops.mesh.primitive_cone_add, "OrionCone", mat_body,
         radius1=0.85, radius2=0.3, depth=1.2, location=(0, 0, 21.3), smooth=True)
    part(bpy.ops.mesh.primitive_cylinder_add, "LasFairing", mat_body,
         radius=0.22, depth=3.4, location=(0, 0, 23.4), smooth=True)
    part(bpy.ops.mesh.primitive_cone_add, "LasTip", mat_dark,
         radius1=0.24, radius2=0.0, depth=1.0, location=(0, 0, 25.6), smooth=True)

    # Two solid boosters strapped against the core, each with a nose and a nozzle.
    # hull_panel at cube_size 0.6: the casings are 9.4 m across and 45 m tall, so the
    # tile repeats roughly 75 times down one booster — enough that the tube reads as
    # steel laid in courses rather than a single glossy cylinder.
    whiteware = []
    for side in (-1, 1):
        srb = part(bpy.ops.mesh.primitive_cylinder_add, f"SRB-{side}", mat_body,
                   radius=0.55, depth=12, location=(1.15 * side, 0, 10), smooth=True)
        surface_relief(srb, amplitude=0.0028, wavelength=0.20, cuts=8, turbulence=0.35,
                       seed=(side * 3.1, 1.9, 0.6))
        nose = part(bpy.ops.mesh.primitive_cone_add, f"SRBnose-{side}", mat_body,
                    radius1=0.55, radius2=0.12, depth=1.8, location=(1.15 * side, 0, 16.9),
                    smooth=True)
        nozzle = part(bpy.ops.mesh.primitive_cone_add, f"SRBnozzle-{side}", mat_dark,
                      radius1=0.2, radius2=0.45, depth=1.1, location=(1.15 * side, 0, 3.4),
                      smooth=True)
        harden_edges(nozzle, width=0.02, segments=2)
        whiteware += [srb, nose]
        # A booster is four motor segments bolted together; without the joint rings the
        # 45 m tube is one seamless extrusion and the eye has nothing to measure it by.
        for j, jz in enumerate((6.5, 9.5, 12.5, 15.5)):
            part(bpy.ops.mesh.primitive_cylinder_add, f"SRBjoint-{side}-{j}", mat_dark,
                 radius=0.565, depth=0.26, location=(1.15 * side, 0, jz))
    apply_surface(whiteware, "hull_panel", cube_size=0.6)

    # Four RS-25 bells in a square under the core stage. The plume hides their throats
    # but their outer rims catch the engine glow, which is what tells the viewer this
    # is a machine producing thrust rather than a cone painted onto the sky.
    for i, (ex, ey) in enumerate(((-0.40, -0.40), (0.40, -0.40),
                                  (-0.40, 0.40), (0.40, 0.40))):
        bell = part(bpy.ops.mesh.primitive_cone_add, f"RS25-{i}", mat_engine,
                    radius1=0.40, radius2=0.15, depth=1.6, location=(ex, ey, 3.3),
                    smooth=True)
        harden_edges(bell, width=0.02, segments=2)
    skirt = part(bpy.ops.mesh.primitive_cone_add, "CoreSkirt", mat_engine,
                 radius1=1.0, radius2=0.86, depth=0.9, location=(0, 0, 4.1), smooth=True)
    harden_edges(skirt, width=0.02, segments=2)

    # Exhaust: one empty carries every gas body, so the whole plume grows *downward out of
    # the bells* under a single animated Z scale — the throat stays pinned to the engine and
    # only the aft end travels, which is what thrust does. The bodies nest wide-dim outside
    # narrow-bright because a plume is stratified that way: entrained air at the edge,
    # unreacted jet in the core.
    plume = bpy.data.objects.new("PlumeRig", None)
    bpy.context.scene.collection.objects.link(plume)
    plume.parent = rig
    plume.location = (0, 0, 2.9)  # the SRB exit plane; the SSME bells hang 0.4 below it

    def gas(name, r_aft, r_bell, length, mat, x=0.0, y=0.0, drop=0.0):
        """One volume body, bell-width at `drop` below the throat plane, widening aft."""
        bpy.ops.mesh.primitive_cone_add(radius1=r_aft, radius2=r_bell, depth=length,
                                        location=(x, y, -drop - length / 2.0))
        obj = bpy.context.active_object
        obj.name = name
        obj.data.materials.append(mat)
        obj.parent = plume
        obj.visible_shadow = False
        return obj

    # Two solid boosters throw the two big orange columns; four SSMEs throw a short,
    # nearly-clear fan between them.
    #
    # Length is set against the vehicle, not against the bell. At 15 m the columns ended a
    # little below the boosters' own noses, so the frame showed two lit cylinders with a
    # wisp under them; a liftoff reads as a launch because the flame is roughly as long as
    # the stack is tall and it is wider than the boosters that throw it.
    for side in (-1, 1):
        gas(f"SRBgas{side}", 2.90, 0.52, 27.0, mat_srb_gas, x=1.15 * side)
        gas(f"SRBcore{side}", 1.05, 0.26, 15.0, mat_srb_core, x=1.15 * side)
        # Mach diamonds: standing shock discs, brightest nearest the bell. They are the one
        # part of a plume that genuinely has an edge, so they are geometry inside the gas
        # rather than another density ramp.
        for k, (dz, r) in enumerate(((1.5, 0.34), (2.9, 0.27), (4.4, 0.21))):
            bpy.ops.mesh.primitive_torus_add(major_radius=r, minor_radius=r * 0.30,
                                             location=(1.15 * side, 0, -dz),
                                             major_segments=24, minor_segments=6)
            disc = bpy.context.active_object
            disc.name = f"SRBshock{side}-{k}"
            disc.data.materials.append(mat_shock)
            disc.parent = plume
            disc.visible_shadow = False
    for i, (ex, ey) in enumerate(((-0.40, -0.40), (0.40, -0.40),
                                  (-0.40, 0.40), (0.40, 0.40))):
        gas(f"H2gas{i}", 0.80, 0.18, 9.0, mat_h2_gas, x=ex, y=ey, drop=0.4)
        gas(f"H2core{i}", 0.30, 0.10, 4.2, mat_h2_core, x=ex, y=ey, drop=0.4)
    gas("Coremantle", 5.2, 1.6, 14.0, mat_h2_gas, drop=0.4)

    # Ignition steam is a density current, not a pool. It leaves the water deluge at tens of
    # metres per second, stays flat against the concrete because it is cold and heavy, and
    # grows as it entrains air — so the leading front is the *largest* puff in the shot and
    # the tallest thing on the pad is well behind it. Small puffs scattered on a circle read
    # as dots on a plate however soft their edges are; what merges into a mass is overlap, so
    # the balls are large, few and heavily interpenetrating, and each one drifts in angle as
    # it travels, which is what makes the whole thing read as rolling rather than inflating.
    steam = []
    for i in range(26):
        a = i * TAU / 26 + 0.3 + 0.34 * math.sin(i * 2.4)
        reach = 0.35 + 0.65 * ((i * 5) % 7) / 6.0
        delay = 0.055 * (i % 7)
        drift = (0.05 + 0.09 * reach) * (1.0 if i % 2 else -1.0)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=2.6,
                                             location=(3.4 * math.cos(a),
                                                       3.4 * math.sin(a), 0.6))
        obj = bpy.context.active_object
        obj.name = f"Steam-{i}"
        obj.data.materials.append(mat_steam)
        obj.visible_shadow = False
        steam.append((obj, a, reach, delay, drift))

    # Exhaust that reaches the blast bucket does not stop at the concrete: it turns sideways,
    # runs down the trench and lifts as a dust-and-steam wall off the pad edge. Ten bodies
    # lying flat on the deck carry that, and they are fixed to the world rather than to the
    # rig because the flow leaves the pad, not the vehicle.
    blast = []
    for i in range(18):
        a = i * TAU / 18 + 0.22 + 0.30 * math.sin(i * 1.7)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12,
                                             radius=6.0 + 2.5 * ((i * 5) % 4) / 3.0,
                                             location=(11.0 * math.cos(a),
                                                       11.0 * math.sin(a), 2.4))
        obj = bpy.context.active_object
        obj.name = f"Blast-{i}"
        obj.data.materials.append(mat_blast)
        obj.visible_shadow = False
        obj.scale = (0.01, 0.01, 0.01)
        blast.append((obj, a, 0.015 * (i % 6)))

    # Pad, flame trench and service tower, all fixed to the ground
    # LC-39B's blast surface is a wide concrete apron, not a black disc: kept small and
    # dark it reads as a coaster under the rocket instead of part of the ground.
    mat_pad = material_principled("pad", (0.150, 0.152, 0.148, 1.0), roughness=0.95)
    # The deck has to be seen *through* a long shot, so the two rings around it are a
    # gradient, not three plates. At 0.24 m tall and 300 m across, the shoulder's own rim
    # drew a dark line straight across the frame at two thirds height — the eye read it as
    # the horizon and the pad as a coin standing on its edge.
    bpy.ops.mesh.primitive_plane_add(size=900, location=(0, 0, 0))
    ground = bpy.context.active_object
    ground.name = "Ground"
    ground.data.materials.append(
        material_surface("ground-surf",
                         [(0.0, (0.052, 0.056, 0.044, 1.0)), (0.55, (0.098, 0.102, 0.078, 1.0)),
                          (0.85, (0.155, 0.150, 0.118, 1.0))],
                         scale=0.08, detail=8.0, bump_strength=0.4, roughness=1.0, warp=0.8))
    bpy.ops.mesh.primitive_cylinder_add(radius=90, depth=0.06, location=(0, 0, 0.03))
    pad = bpy.context.active_object
    pad.name = "LaunchPad"
    pad.data.materials.append(mat_pad)
    # cube_size 0.5: the deck is 180 m across, and at 1.0 the panel field is coarse enough
    # that the apron reads as one slab under the rocket instead of laid concrete.
    apply_surface(pad, "hull_panel", cube_size=0.5)
    bpy.ops.mesh.primitive_cylinder_add(radius=300, depth=0.03, location=(0, 0, 0.015))
    shoulder = bpy.context.active_object
    shoulder.name = "PadShoulder"
    shoulder.data.materials.append(
        material_principled("shoulder", (0.088, 0.092, 0.074, 1.0), roughness=1.0))
    bpy.ops.mesh.primitive_cylinder_add(radius=5.5, depth=0.44, location=(0, 0, 0.42))
    scorch = bpy.context.active_object
    scorch.name = "BlastSurface"
    scorch.data.materials.append(material_principled("scorched", (0.055, 0.054, 0.055, 1.0),
                                                     roughness=1.0))
    bpy.ops.mesh.primitive_cylinder_add(radius=2.8, depth=0.7, location=(0, 0, 0.35))
    trench = bpy.context.active_object
    trench.name = "FlameTrench"
    trench.data.materials.append(mat_dark)

    mat_truss = material_principled("truss", (0.52, 0.28, 0.11, 1.0), metallic=0.6, roughness=0.5)
    # Four posts with nothing between them is a drawing of a tower. The real Fixed Service
    # Structure is a lattice, and the horizontal courses are what let the eye read its
    # height instead of guessing it from a pair of orange lines.
    for lx in (-5.8, -4.4):
        for ly in (-0.8, 0.8):
            leg = add_box(f"TowerLeg{lx}{ly}", (lx, ly, 12), (0.3, 0.3, 24), mat_truss)
            harden_edges(leg, width=0.04, segments=2)
    for bz in (2.0, 6.0, 10.0, 14.0, 18.0, 22.0):
        for ly in (-0.8, 0.8):
            add_box(f"TowerBraceX{bz}{ly}", (-5.1, ly, bz), (1.7, 0.11, 0.11), mat_truss)
        for lx in (-5.8, -4.4):
            add_box(f"TowerBraceY{bz}{lx}", (lx, 0.0, bz), (0.11, 1.9, 0.11), mat_truss)
    # Diagonals, not just courses. A frame of verticals and horizontals is a drawing of a
    # tower; the bracing is what makes it a structure that could stand, and it is the detail
    # that carries the lattice's texture at the 60 m this shot views it from.
    corners = [(-5.8, -0.8), (-4.4, -0.8), (-4.4, 0.8), (-5.8, 0.8)]
    for j in range(4):
        c0 = mathutils.Vector((*corners[j], 0.0))
        c1 = mathutils.Vector((*corners[(j + 1) % 4], 0.0))
        for k, bz in enumerate((2.0, 6.0, 10.0, 14.0, 18.0, 22.0)):
            # Alternate the direction per bay so the faces read as a zigzag lattice.
            a, b = (c0, c1) if (k + j) % 2 else (c1, c0)
            p0 = mathutils.Vector((a.x, a.y, bz))
            p1 = mathutils.Vector((b.x, b.y, bz + 4.0))
            span = p1 - p0
            bpy.ops.mesh.primitive_cylinder_add(radius=0.055, depth=span.length,
                                                location=(p0 + p1) * 0.5)
            diag = bpy.context.active_object
            diag.name = f"TowerDiag{j}-{k}"
            diag.rotation_euler = span.to_track_quat("Z", "Y").to_euler()
            diag.data.materials.append(mat_truss)
    for bz in (4.0, 12.0, 20.0):
        for ly in (-0.8, 0.8):
            add_box(f"TowerDeck{bz}{ly}", (-5.1, ly, bz), (1.7, 1.9, 0.09), mat_truss)
    arm = add_box("SwingArm", (-3.1, 0, 18), (2.6, 0.3, 0.3), mat_truss)
    harden_edges(arm, width=0.04, segments=2)

    # Engine glow warms the pad and the rocket's underside. It rides with the vehicle: a
    # light left on the pad while the stack climbs stops lighting anything at all.
    glow = add_area_light("engine-glow", location=(0, 0, 3), energy=150.0,
                          color=(1.0, 0.45, 0.12), size=6.0)

    # A second key that never leaves the deck. At T+0 the brightest thing on LC-39B is the
    # blast box, not the vehicle: the exhaust is still being turned sideways by the trench
    # and the whole pad is lit from below by it. The vehicle's own glow rides away with the
    # stack, so without a light anchored here the first third of the shot is lit as if the
    # engines were off.
    flare = add_area_light("pad-flare", location=(0, 0, 1.6), energy=900.0,
                           color=(1.0, 0.52, 0.22), size=26.0)

    # A colder second key from behind and to the side. Without it the white stack and the
    # pale horizon sit at the same luminance and the vehicle dissolves into the sky at the
    # exact moment it becomes the subject — a rim is the cheapest separation a shot can buy,
    # and the one thing that makes a 3D render look *lit* rather than shaded.
    add_sun_light("rim", location=(-16, 26, 21), energy=1.7, color=(0.76, 0.85, 1.0))
    # Bloom in the compositor: EEVEE Next has no in-engine glow, so a light source that is
    # brighter than the frame around it renders as a bright *shape* instead of a bright
    # *thing*. Threshold is scene-linear, so 1.6 catches the shock discs and the jet core and
    # leaves the sunlit concrete alone — a low threshold hazes the entire shot.
    add_glare(bpy.context.scene, glare_type="BLOOM", threshold=1.6, size=6)

    for frame in range(1, SHOT_FRAMES + 1):
        t = (frame - 1) / (SHOT_FRAMES - 1)
        rig.location = (0, 0, t * t * 25)  # accelerating rise
        rig.keyframe_insert(data_path="location", frame=frame)

        # The plume is one animated transform. Its throat is pinned to the bells by
        # construction — every body hangs below the empty's origin — so scaling Z stretches
        # it aft out of the engines instead of sliding a finished cone through the air, and
        # X/Y widens as the vehicle climbs because ambient pressure drops and an expanding
        # jet gets fatter with altitude. A plume that narrows on the way up is backwards.
        gz = (0.55 + 0.60 * t) * (1.0 + 0.07 * math.sin(frame * 0.55))
        w = (0.86 + 0.30 * t) * (1.0 + 0.05 * math.sin(frame * 0.9 + 1.1))
        plume.scale = (w, w, gz)
        plume.keyframe_insert(data_path="scale", frame=frame)

        glow.location = (0, 0, 3.0 + t * t * 25)
        glow.data.energy = 150.0 + 260.0 * t
        glow.keyframe_insert(data_path="location", frame=frame)
        glow.data.keyframe_insert(data_path="energy", frame=frame)

        flare.data.energy = 900.0 * (1.0 - min(1.0, max(0.0, (t - 0.30) / 0.40)))
        flare.data.keyframe_insert(data_path="energy", frame=frame)

        for obj, a, reach, delay, drift in steam:
            grow = max(0.0, min(1.0, 0.06 + (t - delay) * 3.2))
            radius = 3.0 + grow * 26.0 * reach
            angle = a + drift * grow
            size = 0.50 + grow * 1.95 * (0.55 + reach)
            obj.scale = (size, size, size * 0.32)
            obj.location = (math.cos(angle) * radius, math.sin(angle) * radius,
                            0.35 + grow * (0.8 + 3.5 * reach))
            obj.keyframe_insert(data_path="scale", frame=frame)
            obj.keyframe_insert(data_path="location", frame=frame)

        # The trench flow arrives about a third of a second after ignition and dies away as
        # the stack clears the deck — a blast cloud that is still rolling at T+17 s is a
        # second, wrong launch under the vehicle.
        for obj, a, delay in blast:
            up = max(0.0, min(1.0, (t - delay) / 0.20))
            down = max(0.0, min(1.0, (t - 0.62) / 0.30))
            g = (0.40 + up * 0.85) * (1.0 - 0.90 * down)
            obj.scale = (g, g, g * 0.80)
            obj.location = (math.cos(a) * (4.0 + up * 24.0),
                            math.sin(a) * (4.0 + up * 24.0),
                            1.1 + up * 2.4)
            obj.keyframe_insert(data_path="scale", frame=frame)
            obj.keyframe_insert(data_path="location", frame=frame)

    # Camera slow pull-back
    for frame in range(1, SHOT_FRAMES + 1):
        t = (frame - 1) / (SHOT_FRAMES - 1)
        cam.location = (30 + t * 12, -42 - t * 12, 10 + t * 9)
        cam.keyframe_insert(data_path="location", frame=frame)
        aim_key(cam, (0, 0, 13 + t * 20), frame)

    add_key(cam, SHOT_FRAMES // 2, energy=4.0, angle=math.radians(4.0), elevation=35.0)
    render_animation(output_dir, "sls-launch")


# ---------------------------------------------------------------------------
# Beat 2: Orion in Space
# ---------------------------------------------------------------------------
def beat_orion_space(output_dir):
    print("\n=== Beat 2: Orion in Space ===", flush=True)
    wipe()
    setup_scene(fps=30, frame_end=SHOT_FRAMES, resolution_x=1280, resolution_y=720)
    setup_world(SPACE_BG)
    add_starfield()

    cam = add_camera("cam-orion", location=(11, -15, 4), target=(0, 0, 0), lens=45.0)
    add_space_fill()  # lifts the shadow face off pure black

    mat_body = material_principled("orion-body", ROCKET_WHITE, metallic=0.2, roughness=0.3)
    mat_metal = material_principled("orion-metal", METAL_GREY, metallic=0.7, roughness=0.3)
    # The panel blue here was (0.10, 0.15, 0.40) and it was applied to the service module
    # as well as the wings, so the whole vehicle rendered as one saturated blue blob — the
    # single largest contributor to "όλο μπλε". Real wing cells read near-black from a
    # distance; the hull carries the light.
    mat_panel = solar_cell_material("orion-panel")

    # Crew module, dock ring, service module, engine bell and two wings. Built by hand
    # here as a cone, a cylinder and four boxes on a cross boom, which at 360p read as a
    # traffic cone welded to a pipe.
    rig = add_orion("Orion", (0, 0, 0), mat_body, mat_metal, mat_panel)

    # Earth in background: surface, cloud deck and a lit limb
    earth = add_earth("Earth", 4.0, (-15, 20, -5))
    clouds = bpy.data.objects["Earth-clouds"]

    # Slow controlled tumble: a fixed 24-degree pitch plus a yaw, so the nose swings
    # toward and away from the orbiting camera. Pure yaw on an axisymmetric stack shows
    # the same silhouette all the way through, which is the still-image look.
    for frame in range(1, SHOT_FRAMES + 1):
        t = (frame - 1) / (SHOT_FRAMES - 1)
        rig.rotation_euler = (math.radians(24), 0, t * 0.6)
        rig.keyframe_insert(data_path="rotation_euler", frame=frame)
        earth.rotation_euler.z = t * 0.1
        earth.keyframe_insert(data_path="rotation_euler", frame=frame)
        clouds.rotation_euler.z = t * 0.15
        clouds.keyframe_insert(data_path="rotation_euler", frame=frame)

    # Camera orbit
    for frame in range(1, SHOT_FRAMES + 1):
        t = (frame - 1) / (SHOT_FRAMES - 1)
        a = t * 0.5
        cam.location = (11 * math.cos(a), -11 * math.sin(a), 3.0 + math.sin(t * math.pi) * 1.6)
        cam.keyframe_insert(data_path="location", frame=frame)
        aim_key(cam, (0, 0, 0), frame)

    add_key(cam, SHOT_FRAMES // 2, energy=4.0, angle=math.radians(4.0), elevation=25.0)
    render_animation(output_dir, "orion-space")


# ---------------------------------------------------------------------------
# Beat 3: Orion Deep Space
# ---------------------------------------------------------------------------
def beat_orion_deep_space(output_dir):
    print("\n=== Beat 3: Orion Deep Space ===", flush=True)
    wipe()
    setup_scene(fps=30, frame_end=SHOT_FRAMES, resolution_x=1280, resolution_y=720)
    setup_world(SPACE_BG)
    add_starfield()

    cam = add_camera("cam-deep", location=(0, -15, 3.5), target=(0, 0, 0), lens=40.0)
    add_space_fill()  # lifts the shadow face off pure black

    mat_body = material_principled("orion-body", ROCKET_WHITE, metallic=0.2, roughness=0.3)
    mat_metal = material_principled("orion-metal", METAL_GREY, metallic=0.7, roughness=0.3)
    mat_panel = solar_cell_material("deep-panel", cell_color=(0.045, 0.058, 0.110))

    # The full rig on a long burn, not a cone and a cylinder that read as a blob.
    # Parts are built in the rig's own frame, so the rig transform orients them.
    rig = add_orion("Deep", (0, 0, 0), mat_body, mat_metal, mat_panel)
    # Nose across frame (+X). Standing the wings vertical put their edges in the camera
    # plane, so each wing rendered as a black bar with nothing on it; rolling the rig about
    # its own nose axis tilts a face back toward the camera, which is what makes them read
    # as panels rather than glyphs. The sign is not free: the wing normals are local ±Y, so
    # +38° aimed them at (0,-0.79,-0.62) — toward the camera but downward, away from a sun
    # that sits high, and N·L came out -0.19. Every panel pixel was unlit. -38° keeps the
    # same camera-facing tilt and adds the sun at N·L +0.85.
    rig.rotation_euler = (mathutils.Vector((1, 0, 0)).to_track_quat("Z", "X").to_matrix()
                          @ mathutils.Matrix.Rotation(math.radians(-38), 3, "Z")).to_euler()

    # Hypergolic exhaust is a gas, so it is drawn as one: volume only, no surface, no
    # silhouette. The old alpha-blended cone was a hard-edged white wedge — the single
    # most diagram-shaped object in the episode. mode="nozzle" puts the density at the
    # bell and lets it thin aft, which is the opposite of a reentry wake.
    # The noise is sampled in world space, and that is right here rather than merely
    # tolerated: gas released at the nozzle stays roughly where it was released, so a
    # field fixed in the inertial frame is the frame the plume actually lives in.
    # Colour follows the propellant. SLS and ICPS burn liquid hydrogen with liquid
    # oxygen, and that exhaust is a near-transparent steam cone with a hot white root —
    # not the cobalt blue the surface shader was pushing. Blue is what the whole episode
    # read as, so the plume goes warm-neutral.
    # Optically thick is the other way to draw a silhouette: once density x path saturates,
    # the volume boundary hardens back into the cone wall and the plume is a white wedge
    # again. These numbers are chosen so the deepest chord still transmits — thin sheath,
    # and a core hot enough to read as a root without clipping. The noise cells also have
    # to land inside the body: at scale 2.2 a cell is ~0.45 m against a 1.15 m half-width,
    # so it only roughened the middle and left the wall smooth.
    mat_plume = plasma_volume_material("engine-plume", (0.80, 0.80, 0.82), density=0.07,
                                       strength=0.85, mode="nozzle-jet", turb=0.95,
                                       turb_scale=2.0)
    mat_plume_core = plasma_volume_material("engine-plume-core", (1.0, 0.94, 0.86),
                                            density=0.22, strength=1.2, mode="nozzle-jet",
                                            turb=0.85, turb_scale=3.2)

    # Built along local -Z, which is aft once the rig is rotated, so the plume rides the
    # engine bell rather than pointing at the floor.
    trail = bpy.data.objects.new("EngineTrail", None)
    bpy.context.scene.collection.objects.link(trail)
    trail.parent = rig
    trail.location = (0, 0, -1.8)
    for name, r_aft, r_bell, long, mat in (("Plume-Sheath", 1.15, 0.50, 6.0, mat_plume),
                                           ("Plume-Core", 0.42, 0.34, 2.8, mat_plume_core)):
        bpy.ops.mesh.primitive_cone_add(radius1=r_aft, radius2=r_bell, depth=long,
                                        location=(0, 0, -long / 2.0))
        part = bpy.context.active_object
        part.name = name
        part.data.materials.append(mat)
        bpy.ops.object.shade_smooth()
        part.visible_shadow = False
        part.parent = trail

    # Small Moon in distance
    moon = add_planet("MoonDistant", 2.0, (15, 20, 5), moon_material(scale=surface_scale(2.0, 0.30)))

    for frame in range(1, SHOT_FRAMES + 1):
        t = (frame - 1) / (SHOT_FRAMES - 1)
        pos = (-6.5 + t * 13.0, math.sin(t * math.pi) * 1.2, math.cos(t * 0.9) * 0.7)
        rig.location = pos
        rig.keyframe_insert(data_path="location", frame=frame)
        pulse = 0.8 + 0.3 * math.sin(frame * 0.3)
        trail.scale = (pulse, pulse, 1.0)
        trail.keyframe_insert(data_path="scale", frame=frame)

    for frame in range(1, SHOT_FRAMES + 1):
        t = (frame - 1) / (SHOT_FRAMES - 1)
        pos = (-6.5 + t * 13.0, math.sin(t * math.pi) * 1.2, math.cos(t * 0.9) * 0.7)
        cam.location = (pos[0] * 0.4, -15.0 + t * 2.5, 3.5 - t * 1.2)
        cam.keyframe_insert(data_path="location", frame=frame)
        aim_key(cam, pos, frame)

    add_key(cam, SHOT_FRAMES // 2, energy=3.0, angle=math.radians(4.0), elevation=22.0)
    render_animation(output_dir, "orion-deep-space")


# ---------------------------------------------------------------------------
# Beat 4: Lunar Flyby
# ---------------------------------------------------------------------------
def beat_lunar_flyby(output_dir):
    print("\n=== Beat 4: Lunar Flyby ===", flush=True)
    wipe()
    setup_scene(fps=30, frame_end=SHOT_FRAMES, resolution_x=1280, resolution_y=720)
    setup_world(SPACE_BG)
    add_starfield()

    cam = add_camera("cam-flyby", location=(-5.1, -8.0, 4.6), target=(-6.4, 0, -0.2), lens=30.0)
    # The default fill sits below the ground plane, so it lifted the hull and left the
    # cast shadow a black hole. From ahead-left and above it reaches the floor, and
    # neutral rather than blue because this is the shot the user called "όλο μπλε".
    add_space_fill(location=(-12, 8, 6), energy=1.5, color=(0.55, 0.58, 0.62))

    mat_body = material_principled("orion-body", ROCKET_WHITE, metallic=0.2, roughness=0.3)
    mat_metal = material_principled("orion-metal", METAL_GREY, metallic=0.7, roughness=0.3)

    # A body this large reads as terrain with a horizon. At r20 the same camera
    # looked over the limb and rendered nothing but space.
    moon_center = (0, 0, -62)
    # 512x256, not 256x128: a crater bowl needs its floor and rim sampled, and at the
    # coarser mesh the vertex spacing was 1.47 against a 2.4 m smallest crater — right on
    # the relief threshold, so the bowls came out shallow and their floor patches read as
    # painted smudges on the foreground.
    moon = add_planet("MoonSurface", 60.0, moon_center,
                      moon_material(scale=surface_scale(60.0, 0.20)), segments=512, rings=256)
    # The one ground beat that never got its tile. moon_material's noise spans 0.20 of a
    # 60-unit radius, so at this camera it is twelve-metre blobs of albedo with no grain at
    # all — which is exactly what "the ground looks like bright snow" was. The other three
    # lunar beats already switch to the regolith tile; this one was missed.
    apply_surface(moon, "regolith", cube_size=1.0)
    # Measured, not derived: projecting a surface grid through this camera at the QC frame
    # leaves v 0.955-1.000 in frame. u is a full circle and only part of it is visible, so
    # the count carries the wasted azimuths.
    # This one keeps the sphere. The same census that put earth-rise at 99 % crater
    # coverage and earth-from-moon at 72 % puts the flyby at 42 %, because its visible field
    # reaches arc 25 on a radius-60 body — the widest of the four — so the bowls are small
    # relative to it and the rims stay apart. Its smallest crater, 1.2 units, sits one
    # tolerance above the 1.18 that this mesh can excavate; the two beats whose fields were
    # narrow enough to need a finer mesh got their own terrain caps.
    add_crater_field("flyby-crater", moon, 60.0, 50, seed=17,
                     size_fracs=(0.020, 0.060), uv_range=(0.955, 1.000))
    add_earth("EarthDistant", 5.0, (6, 90, -28), segments=128, rings=64)

    # The full Orion rig, nose along the flight direction and wings level,
    # instead of a cone and a cylinder that read as an unlit blob.
    mat_panel = solar_cell_material("flyby-panel", cell_color=(0.040, 0.050, 0.092))
    nose = mathutils.Vector((1, 0, 0)).to_track_quat("Z", "Y")
    orion = add_orion("Flyby", (-8, 0, 2), mat_body, mat_metal, mat_panel)
    # A crisp shadow under a flyby vehicle is a defect, not grounding. The key here sits high
    # and to the +X side, so the real shadow would be thrown far outside the visible terrain
    # band; on frame it landed as a black blob directly beneath the craft, which is the one
    # thing no fill energy can lift — a shadow is missing light, not missing ambient.
    for obj in (orion,) + tuple(orion.children):
        obj.visible_shadow = False

    for frame in range(1, SHOT_FRAMES + 1):
        t = (frame - 1) / (SHOT_FRAMES - 1)
        cx = -8 + t * 16
        cz = 2 + math.sin(t * math.pi) * 2
        orion.location = (cx, 0, cz)
        rot = nose.to_euler()
        rot[2] += math.sin(t * math.pi) * 0.08
        orion.rotation_euler = rot
        orion.keyframe_insert(data_path="location", frame=frame)
        orion.keyframe_insert(data_path="rotation_euler", frame=frame)

    for frame in range(1, SHOT_FRAMES + 1):
        t = (frame - 1) / (SHOT_FRAMES - 1)
        cx = -8 + t * 16
        cz = 2 + math.sin(t * math.pi) * 2
        cam.location = (cx * 0.45 - 1.5, -8.0, cz + 2.6)
        cam.keyframe_insert(data_path="location", frame=frame)
        # Aim under the spacecraft: the ground only enters the frame once the
        # camera pitches past the limb's dip angle, and then it fills the frame.
        aim_key(cam, (cx * 0.8, 0, cz - 2.2), frame)

    add_key(cam, SHOT_FRAMES // 2, energy=5.0, angle=math.radians(8.0), elevation=20.0)
    render_animation(output_dir, "lunar-flyby")


# ---------------------------------------------------------------------------
# Beat 5: Earth Rise
# ---------------------------------------------------------------------------
def beat_earth_rise(output_dir):
    print("\n=== Beat 5: Earth Rise ===", flush=True)
    wipe()
    setup_scene(fps=30, frame_end=SHOT_FRAMES, resolution_x=1280, resolution_y=720)
    setup_world(SPACE_BG)
    add_starfield()

    cam = add_camera("cam-rise", location=(0, -6, 0.6), target=(0, 12, 2), lens=40.0)
    # Earth is the subject and it hangs above a lunar dawn, so the key cannot sit fully
    # perpendicular: that drags the terminator through the middle of the planet and the shot
    # shows a crescent Earth, which is true of nothing the narration says. yaw=-15 keeps
    # three quarters of the disc lit and still separates key from view axis by 0.26, the
    # floor the craters sit on needs that much to hold their shadows. The lamp itself is
    # placed at the end of the beat, where the animated framing is known.

    # Curved lunar horizon in the foreground
    ground = add_planet("LunarGround", 40.0, (0, 0, -42), regolith_material(scale=surface_scale(40.0, 0.10)), segments=512, rings=256)
    # The procedural regolith is a noise ramp with no grain at this camera distance, which
    # is the whole reason the Moon read as bright snow. The tile owns the gravel.
    apply_surface(ground, "regolith", cube_size=1.0)

    # Earth rising over it: surface, cloud deck and limb glow ride as one unit
    earth = add_earth("Earth", 3.0, (0, 22, -6))

    # Measured: only the zone between arc 2.8 and 11.0 units from the sub-camera point is
    # inside the frame, over about a third of the azimuths — a 354-square-unit field. Cutting
    # that field on the body itself is what produced the pillow ridges. At 512x256 the
    # sphere's vertex spacing is 0.49 however close the camera gets, so nothing under 0.79
    # units of radius can be excavated, and 45 bowls of that floor in 354 units² is 99 %
    # coverage: every rim touches its neighbour and the surface reads as blisters. The cap
    # puts the vertices where the camera is — spacing 0.059 instead of 0.49 — and the mesh
    # can then carry a bowl about six vertices across its radius. Below that there is no
    # floor to shade, the parabola collapses into a dome, and the crater's own floor disc
    # ends up resting on top of the bump.
    #
    # half=15 reaches arc 15.3 at its mid-edges, past the 14.1 geometric horizon for a
    # camera 2.6 above a radius-40 body, so the 1.4-unit step where the cap ends is never in
    # frame at any pose. lift has to clear the deepest bowl (2.4 x 0.42 = 1.01) or the
    # craters punch through to the sphere behind them.
    rise_cap = add_terrain_cap("RiseCap", (0, 0, -42), 40.0, half=15.0, cols=512, lift=1.4)
    # Cube projection reads world x and y, and the cap sits on the same axis as the ground
    # below it, so the gravel lines up with the sphere's own tile instead of seaming across
    # it. The only disagreement between the two surfaces is in depth, which is the point.
    apply_surface(rise_cap, "regolith", cube_size=1.0)

    # Three tunings tried on the cap before this one. A dense field of small bowls
    # (120 at 0.12-2.3) renders as a carpet of domes: at four vertices across a radius the
    # parabola has no floor to shade, and the crater's own dark disc lands on top of the
    # bump. A sparse field of large ones (30 at 0.45-2.4) leaves the plain bare, because
    # front lighting hides every shadow a bowl of that depth can cast. A wide draw at
    # moderate density — most bowls small, a handful basins, none allowed to touch — is the
    # only one of the three that reads as a surface that has been hit for four billion
    # years rather than as texture, or as a pattern, or as nothing.
    add_crater_field("rise-crater", rise_cap, 41.4, 45, seed=13,
                     size_fracs=(0.003, 0.055), size_bias=2.2, min_gap=1.05,
                     uv_range=(cap_v_window(41.4, 12.5), 1.0),
                     spacing=30.0 / 512)

    for frame in range(1, SHOT_FRAMES + 1):
        t = (frame - 1) / (SHOT_FRAMES - 1)
        earth.location.z = -6 + t * 8
        earth.rotation_euler.z = t * 0.2
        earth.keyframe_insert(data_path="location", frame=frame)
        earth.keyframe_insert(data_path="rotation_euler", frame=frame)

    for frame in range(1, SHOT_FRAMES + 1):
        t = (frame - 1) / (SHOT_FRAMES - 1)
        cam.location = (math.sin(t * 0.4) * 1.5, -6, 0.6 + t * 0.6)
        cam.keyframe_insert(data_path="location", frame=frame)
        aim_key(cam, (0, 22, -6 + t * 8), frame)

    add_key(cam, SHOT_FRAMES // 2, energy=5.0, angle=math.radians(5.0), elevation=17.0, yaw=-15.0)
    render_animation(output_dir, "earth-rise")


# ---------------------------------------------------------------------------
# Beat 6: Lunar Approach
# ---------------------------------------------------------------------------
def beat_lunar_approach(output_dir):
    print("\n=== Beat 6: Lunar Approach ===", flush=True)
    wipe()
    setup_scene(fps=30, frame_end=SHOT_FRAMES, resolution_x=1280, resolution_y=720)
    setup_world(SPACE_BG)
    add_starfield()

    cam = add_camera("cam-approach", location=(0, -10, 0), target=(0, 20, 0), lens=45.0)
    # The Moon sits dead ahead down +Y, so a key from +Y lit only the hemisphere facing away
    # and rendered a black disc. The old fix was to front-light it, which bought a lit face
    # and gave back no crater shadow at all — the two defects traded places. yaw=-15 is the
    # compromise: terminator near the limb, three quarters of the disc lit, relief still
    # reading. Placement is at the end of the beat, where the camera has been animated.

    moon_center = (0, 34, 0)
    moon = add_planet("Moon", 6.0, moon_center, moon_material(scale=surface_scale(6.0)), segments=512, rings=256)
    # Two classes, split by what this mesh can excavate. The large class is displaced, so
    # it keeps its shading as the terminator crosses it; the small one is painted and only
    # has to survive as speckle. A single class reads as a pattern, and a pattern is what
    # gave the old bowls their drawn-on look however small they were made.
    craters = add_crater_field("approach-crater", moon, 6.0, 40, seed=11,
                               size_fracs=(0.028, 0.075), uv_range=(0.08, 0.92))
    craters += add_crater_field("approach-speckle", moon, 6.0, 90, seed=27,
                                size_fracs=(0.008, 0.022), uv_range=(0.06, 0.94))
    # Surface detail must ride with the body, or it slides under the rotating sphere.
    for obj in craters:
        obj.parent = moon
        obj.matrix_parent_inverse = moon.matrix_world.inverted()

    for frame in range(1, SHOT_FRAMES + 1):
        t = (frame - 1) / (SHOT_FRAMES - 1)
        # Real approach: the Moon travels toward the camera, it does not inflate.
        y = 34 - t * 16
        moon.location.y = y
        moon.keyframe_insert(data_path="location", frame=frame)
        moon.rotation_euler.z = t * 0.25
        moon.keyframe_insert(data_path="rotation_euler", frame=frame)
        cam.location = (math.sin(t * 0.5) * 1.2, -10, math.cos(t * 0.5) * 0.8)
        cam.keyframe_insert(data_path="location", frame=frame)
        aim_key(cam, (0, y, 0), frame)

    add_key(cam, SHOT_FRAMES // 2, energy=5.0, angle=math.radians(4.0), elevation=22.0, yaw=-15.0)
    render_animation(output_dir, "lunar-approach")


# ---------------------------------------------------------------------------
# Beat 7: Far Side
# ---------------------------------------------------------------------------
def beat_far_side(output_dir):
    print("\n=== Beat 7: Far Side ===", flush=True)
    wipe()
    setup_scene(fps=30, frame_end=SHOT_FRAMES, resolution_x=1280, resolution_y=720)
    setup_world(SPACE_BG)
    add_starfield()

    cam = add_camera("cam-far", location=(0, -48, 16), target=(0, 0, -16), lens=35.0)

    moon_center = (0, 0, -16)
    moon = add_planet("MoonSurface", 15.0, moon_center, moon_material(scale=surface_scale(15.0)),
                      segments=512, rings=256)
    # The far side is heavily cratered: two size classes, deliberately separated by what
    # this mesh can excavate. At 0.022-0.062 of the radius the large class is wider than
    # 1.6 vertex spacings, so it gets a real bowl; the small class sits under that limit
    # and stays a painted patch rather than a spike. The old absolute ranges put the large
    # class at 0.07-0.21 of the radius — South Pole-Aitken basins, twenty of them, evenly
    # spaced — which is the single loudest "drawn on" mark on this body.
    add_crater_field("far-crater", moon, 15.0, 55, seed=42,
                     size_fracs=(0.022, 0.062), uv_range=(0.08, 0.92))
    add_crater_field("far-crater-small", moon, 15.0, 130, seed=99,
                     size_fracs=(0.006, 0.018), uv_range=(0.05, 0.95))

    # Slow camera pan
    for frame in range(1, SHOT_FRAMES + 1):
        t = (frame - 1) / (SHOT_FRAMES - 1)
        cam.location = (math.sin(t * 0.8) * 9, -48 + t * 4, 16 + math.cos(t * 0.5) * 2)
        cam.keyframe_insert(data_path="location", frame=frame)
        aim_key(cam, moon_center, frame)

    add_key(cam, SHOT_FRAMES // 2, energy=6.0, angle=math.radians(4.0), elevation=30.0, yaw=-15.0)
    render_animation(output_dir, "far-side")


# ---------------------------------------------------------------------------
# Beat 8: Splashdown
# ---------------------------------------------------------------------------
GORE_COUNT = 24


def gore_ripple(obj, radius, amp=0.075, flatten=0.60):
    """Scallop a hemisphere's skirt and squash it into a canopy.

    A UV hemisphere scaled to (1,1,0.82) is a plastic bowl. A ringsail canopy is inflated
    tubes sewn side by side, so the mouth must scallop in and out once per gore while the
    crown stays smooth. The wave therefore dies out with height and the whole body is
    flattened to the slenderness an inflated canopy actually has.
    """
    for v in obj.data.vertices:
        r_xy = math.hypot(v.co.x, v.co.y)
        if r_xy < 1e-6:
            continue
        phi = math.atan2(v.co.y, v.co.x)
        height = max(0.0, min(1.0, v.co.z / max(radius, 1e-6)))
        k = 1.0 + amp * math.cos(GORE_COUNT * phi) * (1.0 - height) ** 2
        v.co.x *= k
        v.co.y *= k
        v.co.z *= flatten
    obj.data.update()


def gore_stripes(obj):
    """Alternate the two slot materials gore by gore.

    The orange-and-white banding is the pattern the eye files as "parachute"; a single
    flat colour only reads as a dome, however good the silhouette is.
    """
    band = TAU / GORE_COUNT
    for poly in obj.data.polygons:
        phi = (math.atan2(poly.center.y, poly.center.x) + TAU) % TAU
        poly.material_index = int(phi / band) % 2


def beat_splashdown(output_dir):
    print("\n=== Beat 8: Splashdown ===", flush=True)
    wipe()
    setup_scene(fps=30, frame_end=SHOT_FRAMES, resolution_x=1280, resolution_y=720)
    setup_world((0.35, 0.55, 0.75, 1.0), strength=1.0)  # late-afternoon sky over water

    cam = add_camera("cam-splash", location=(18, -18, 13), target=(0, 0, 18), lens=40.0)

    mat_capsule = material_principled("capsule", ROCKET_WHITE, metallic=0.2, roughness=0.4)
    # Roughness 0.7 on a saturated orange reads as blow-moulded plastic. Ripstop canopy
    # cloth is a diffuse, slightly dusty surface, and the second colour is the pale gore
    # the banding alternates with it.
    mat_chute = material_principled("chute", PARACHUTE_ORANGE, metallic=0.0, roughness=0.92)
    mat_chute_b = material_principled("chute-gore", (0.68, 0.66, 0.62, 1.0),
                                      metallic=0.0, roughness=0.92)
    mat_vent = material_principled("chute-vent", (0.030, 0.030, 0.034, 1.0),
                                   metallic=0.0, roughness=1.0)
    mat_line = material_principled("line", (0.15, 0.15, 0.16, 1.0), roughness=0.9)

    # Ocean: a wide rippled plane, not a coin
    bpy.ops.mesh.primitive_plane_add(size=240, location=(0, 0, -2))
    ocean = bpy.context.active_object
    ocean.name = "Ocean"
    ocean.data.materials.append(material_surface(
        "ocean-plane", [(0.0, (0.006, 0.028, 0.09, 1.0)), (0.58, (0.018, 0.09, 0.22, 1.0)),
                        (1.0, (0.09, 0.24, 0.34, 1.0))],
        scale=0.45, detail=6.0, bump_strength=0.45, roughness=0.18, warp=1.2))
    ocean.visible_shadow = False

    # Orion capsule descending
    bpy.ops.mesh.primitive_cone_add(radius1=1.1, radius2=0.35, depth=1.6, location=(0, 0, 15))
    capsule = bpy.context.active_object
    capsule.name = "Capsule"
    capsule.data.materials.append(mat_capsule)
    bpy.ops.object.shade_smooth()
    # The one solid hull in the shot; the canopies stay two-slot gore-striped cloth.
    # Buckled before blanketed, as every other hull here: a cone this straight reads as a
    # lathe drawing, and the capsules that came back were dented.
    surface_relief(capsule, amplitude=0.008, wavelength=0.22, cuts=4,
                   turbulence=0.45, seed=(2.1, 0.4, 1.7))
    apply_surface(capsule, "hull_panel")

    # Three canopies: hemispheres with a vent, each on its own riser
    chutes = []
    for i in range(3):
        angle = i * TAU / 3 + 0.4
        x, y = 3.4 * math.cos(angle), 3.4 * math.sin(angle)
        rig = bpy.data.objects.new(f"Chute{i}Rig", None)
        bpy.context.scene.collection.objects.link(rig)
        rig.location = (x, y, 20)

        bpy.ops.mesh.primitive_uv_sphere_add(segments=GORE_COUNT * 4, ring_count=20,
                                             radius=2.4, location=(0, 0, 0))
        canopy = bpy.context.active_object
        canopy.name = f"Chute-{i}-canopy"
        make_dome(canopy)
        canopy.data.materials.append(mat_chute)
        canopy.data.materials.append(mat_chute_b)
        gore_ripple(canopy, 2.4)
        gore_stripes(canopy)
        bpy.ops.object.shade_smooth()
        canopy.parent = rig

        # The skirt ring follows the same scallop, or a plain torus floats a circular
        # hoop outside an irregular mouth.
        bpy.ops.mesh.primitive_torus_add(major_radius=2.36, minor_radius=0.075,
                                         location=(0, 0, 0.0), major_segments=GORE_COUNT * 4,
                                         minor_segments=10)
        vent = bpy.context.active_object
        vent.name = f"Chute-{i}-skirt"
        vent.data.materials.append(mat_chute)
        gore_ripple(vent, 2.36)
        bpy.ops.object.shade_smooth()
        vent.parent = rig

        # Apex vent: the hole a ringsail spills air through, dark so the eye reads
        # through the canopy rather than onto it.
        bpy.ops.mesh.primitive_cylinder_add(radius=0.42, depth=0.06,
                                            location=(0, 0, 2.4 * 0.60 - 0.01),
                                            vertices=48)
        eye = bpy.context.active_object
        eye.name = f"Chute-{i}-vent"
        eye.data.materials.append(mat_vent)
        eye.parent = rig

        # Risers converge on the capsule: the capsule hangs 5 units below the
        # canopy and 3.4 units inward, so the line direction is fixed in rig space.
        attach = mathutils.Vector((-x, -y, -5.0))
        length = attach.length
        quat = attach.normalized().to_track_quat("Z", "Y")
        for j, perp in enumerate((-0.9, 0.9)):
            offset = mathutils.Vector((0, 0, 1)).cross(attach.normalized()) * perp
            mid = attach / 2.0 + offset
            bpy.ops.mesh.primitive_cylinder_add(radius=0.035, depth=length,
                                                location=mid, rotation=quat.to_euler())
            line = bpy.context.active_object
            line.name = f"Chute-{i}-line{j}"
            line.data.materials.append(mat_line)
            line.parent = rig

        chutes.append(rig)

    # Descending animation
    for frame in range(1, SHOT_FRAMES + 1):
        t = (frame - 1) / (SHOT_FRAMES - 1)
        descent = 15 - t * 17  # from 15 to -2
        capsule.location.z = descent
        capsule.keyframe_insert(data_path="location", frame=frame)
        capsule.rotation_euler.z = math.sin(t * 3.0) * 0.06
        capsule.keyframe_insert(data_path="rotation_euler", frame=frame)
        for i, rig in enumerate(chutes):
            sway = math.sin(frame * 0.07 + i * 2.1)
            rig.location = (3.4 * math.cos(i * TAU / 3 + 0.4) + sway * 0.5,
                            3.4 * math.sin(i * TAU / 3 + 0.4) + sway * 0.3,
                            descent + 5.5)
            rig.keyframe_insert(data_path="location", frame=frame)
            rig.rotation_euler = (sway * 0.09, math.cos(frame * 0.06 + i) * 0.09, 0)
            rig.keyframe_insert(data_path="rotation_euler", frame=frame)

    # Camera follows the whole descent: the aim point is the middle of the
    # capsule + riser + canopy stack, not the capsule, or the chutes leave frame.
    for frame in range(1, SHOT_FRAMES + 1):
        t = (frame - 1) / (SHOT_FRAMES - 1)
        cam.location = (18 - t * 3, -18 + t * 2, 13 - t * 4)
        cam.keyframe_insert(data_path="location", frame=frame)
        aim_key(cam, (0, 0, max(-1.0, 15 - t * 17) + 3.2), frame)

    add_key(cam, SHOT_FRAMES // 2, energy=5.0, angle=math.radians(4.0), elevation=30.0, yaw=-10.0)
    render_animation(output_dir, "splashdown")


# ---------------------------------------------------------------------------
# Beat 9: Earth from Moon
# ---------------------------------------------------------------------------
def beat_earth_from_moon(output_dir):
    print("\n=== Beat 9: Earth from Moon ===", flush=True)
    wipe()
    setup_scene(fps=30, frame_end=SHOT_FRAMES, resolution_x=1280, resolution_y=720)
    setup_world(SPACE_BG)
    add_starfield()

    cam = add_camera("cam-earth", location=(0, -12, 7), target=(0, 20, 3), lens=40.0)
    # The camera looks toward +Y, so a key placed beyond the Earth lit its far side and the
    # planet rendered as a black disc with a bright rim. Fully perpendicular would fix the
    # ground and break the planet, so this leans the key 15 deg back toward the camera: the
    # near face stays three quarters lit and the lunar floor still keeps enough separation
    # to throw its craters into relief. Placement is at the end of the beat.

    # Curved lunar horizon in the foreground, not a disc
    ground = add_planet("LunarGround", 60.0, (0, 0, -58), regolith_material(scale=surface_scale(60.0, 0.10)),
               segments=512, rings=256)
    apply_surface(ground, "regolith", cube_size=1.0)
    # Measured: the ground the camera can see is the zone from arc 4.2 to 17.5 out from the
    # sub-camera point, over about a third of the azimuths — 905 units². Fifty bowls drawn
    # from 1.2 to 3.3 units of radius cover 72 % of that, and the rims merge the same way
    # earth-rise's did. Same fix: a fine cap whose mid-edges reach arc 28, past the 25.5
    # geometric horizon for a camera 6.1 above this body, so the step where it ends is
    # never in frame, and a size floor set by the cap's own vertex spacing (0.105) rather
    # than by the latitude rings (0.74).
    view_cap = add_terrain_cap("EarthViewCap", (0, 0, -58), 60.0,
                               half=27.0, cols=512, lift=2.0)
    apply_surface(view_cap, "regolith", cube_size=1.0)
    add_crater_field("earthview-crater", view_cap, 62.0, 50, seed=23,
                     size_fracs=(0.010, 0.053), size_bias=2.2, min_gap=1.05,
                     uv_range=(cap_v_window(62.0, 23.0), 1.0),
                     spacing=54.0 / 512)

    earth_center = (0, 20, 3)
    earth = add_earth("Earth", 4.0, earth_center, segments=128, rings=64)

    # Slow Earth rotation with a day-side terminator kept lit
    for frame in range(1, SHOT_FRAMES + 1):
        t = (frame - 1) / (SHOT_FRAMES - 1)
        earth.rotation_euler.z = t * 0.35
        earth.keyframe_insert(data_path="rotation_euler", frame=frame)

    # Camera very slow drift
    for frame in range(1, SHOT_FRAMES + 1):
        t = (frame - 1) / (SHOT_FRAMES - 1)
        cam.location = (math.sin(t * 0.2) * 2, -12, 7 + math.cos(t * 0.2) * 0.6)
        cam.keyframe_insert(data_path="location", frame=frame)
        aim_key(cam, earth_center, frame)

    add_key(cam, SHOT_FRAMES // 2, energy=5.0, angle=math.radians(4.0), elevation=20.0, yaw=-15.0)
    render_animation(output_dir, "earth-from-moon")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
# Beat 10: Apollo Era (Saturn V / Apollo CSM comparison)
# ---------------------------------------------------------------------------

def beat_apollo_era(output_dir):
    print("\n=== Beat 10: Apollo Era ===", flush=True)
    wipe()
    setup_scene(fps=30, frame_end=SHOT_FRAMES, resolution_x=1280, resolution_y=720)
    setup_world(SPACE_BG)
    add_starfield()

    cam = add_camera("cam-apollo", location=(0, -26, 5), target=(0, 0, 5.8), lens=35.0)

    mat_white = material_principled("rocket-white", ROCKET_WHITE, metallic=0.15, roughness=0.45)
    mat_cream = material_principled("sls-white", (0.9, 0.9, 0.85, 1.0), metallic=0.2, roughness=0.5)
    mat_dark = material_principled("roll-black", (0.03, 0.03, 0.035, 1.0), roughness=0.8)

    # Saturn V 111 m vs SLS 98 m: the 1.13 height ratio is the point of the shot.
    _, h_saturn = add_rocket("saturnv", (-4.6, 0, 0),
                             [(3.0, mat_white), (1.7, mat_white), (3.6, mat_white), (2.0, mat_white)],
                             radius=0.55, tower=True, mat_dark=mat_dark)
    _, h_sls = add_rocket("sls", (4.6, 0, 0),
                          [(4.4, mat_cream), (3.9, mat_cream)],
                          radius=0.62, srbs=2, mat_dark=mat_dark)
    print(f"  Saturn V height {h_saturn:.1f}  SLS height {h_sls:.1f}", flush=True)

    # A ground plane, not a disc: a coin floating in starfield is a diagram, and the
    # user asked for renders. The masts and their pools of light do the grounding.
    bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, 0))
    ground = bpy.context.active_object
    ground.name = "ComplexGround"
    ground.data.materials.append(
        material_surface("apollo-ground",
                         [(0.0, (0.048, 0.050, 0.056, 1.0)), (0.55, (0.090, 0.094, 0.104, 1.0)),
                          (0.90, (0.150, 0.154, 0.166, 1.0))],
                         scale=0.09, detail=8.0, bump_strength=0.45, roughness=1.0, warp=1.0))
    # A bare emissive ball on a stick reads as a diagram glyph. What makes a night
    # launch complex is the beam: dust in the air gives the shaft its body, and the shaft
    # is what tells you where the light is coming from. As a surface the cone shows its own
    # wall and the shot becomes four translucent triangles, so the beam is a volume.
    # Generated Z runs 0 at the wide pool end and 1 at the lamp, so the nozzle ramp puts the
    # hot end on the source and fades it into the ground it illuminates, and the cross-axis
    # term of nozzle-jet removes the cone wall that made four translucent triangles.
    mat_shaft = plasma_volume_material("flood-shaft", (1.0, 0.82, 0.55), density=0.055,
                                       strength=0.75, mode="nozzle-jet", turb=0.90,
                                       turb_scale=2.2)
    for k in range(4):
        a = k * TAU / 4 + 0.4
        mx, my = 7.5 * math.cos(a), 7.5 * math.sin(a)
        bpy.ops.mesh.primitive_cylinder_add(radius=0.22, depth=7.5, location=(mx, my, 3.75))
        mast = bpy.context.active_object
        mast.name = f"LightMast-{k}"
        mast.data.materials.append(mat_dark)
        lamp_pt = mathutils.Vector((mx, my, 7.6))
        pool_pt = mathutils.Vector((mx * 0.25, my * 0.25, 0.0))
        axis = lamp_pt - pool_pt
        bpy.ops.mesh.primitive_cone_add(radius1=1.7, radius2=0.30, depth=axis.length,
                                       location=(pool_pt + lamp_pt) * 0.5)
        shaft = bpy.context.active_object
        shaft.name = f"FloodShaft-{k}"
        shaft.rotation_euler = axis.to_track_quat("Z", "Y").to_euler()
        shaft.data.materials.append(mat_shaft)
        bpy.ops.object.shade_smooth()
        shaft.visible_shadow = False
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=12, radius=0.24,
                                             location=lamp_pt)
        lamp = bpy.context.active_object
        lamp.name = f"Lamp-{k}"
        # Inside its own beam the fitting no longer has to sell the light; a bulb at 5.0
        # clipped to a white disc and was the only thing in frame that read as a glyph.
        lamp.data.materials.append(material_emissive(f"lamp-mat-{k}", (1.0, 0.86, 0.62),
                                                      strength=1.8))
        lamp.visible_shadow = False
        add_area_light(f"flood-{k}", location=(mx * 0.5, my * 0.5, 7.0), energy=260.0,
                       color=(1.0, 0.88, 0.70), size=6.0)

    earth = add_earth("Earth", 4.0, (16, 34, 13), segments=128, rings=64)
    clouds = bpy.data.objects["Earth-clouds"]

    for frame in range(1, SHOT_FRAMES + 1):
        t = (frame - 1) / (SHOT_FRAMES - 1)
        earth.rotation_euler.z = t * 0.3
        earth.keyframe_insert(data_path="rotation_euler", frame=frame)
        clouds.rotation_euler.z = t * 0.42
        clouds.keyframe_insert(data_path="rotation_euler", frame=frame)
        cam.location = (-9 + t * 18, -26, 5.5 + math.sin(t * math.pi) * 2.0)
        cam.keyframe_insert(data_path="location", frame=frame)
        aim_key(cam, (0, 0, 5.6), frame)

    add_key(cam, SHOT_FRAMES // 2, name="moonlight", energy=0.55,
            color=(0.72, 0.80, 1.0), angle=math.radians(4.0), elevation=30.0)
    render_animation(output_dir, "apollo-era")


# ---------------------------------------------------------------------------
# Beat 11: Crew Quarters (4 astronaut figures in Orion)
# ---------------------------------------------------------------------------

def beat_crew_quarters(output_dir):
    print("\n=== Beat 11: Crew Quarters ===", flush=True)
    wipe()
    setup_scene(fps=30, frame_end=SHOT_FRAMES, resolution_x=1280, resolution_y=720)
    setup_world((0.02, 0.02, 0.03, 1.0), strength=1.0)  # dark interior
    cam = add_camera("cam-crew", location=(0, -7.2, 1.9), target=(0, 0, 0.35), lens=40.0)

    # Wall radius of the cone at a given height, so every interior fitting can be seated
    # against the actual surface instead of a guessed constant. Without this the frame
    # rings and longerons landed outside the hull and floated in space around it.
    def wall_r(z):
        return 3.6 - 2.5 * (z + 1.5) / 3.8

    # An x-ray hull was the only way the camera read the interior of a closed cone, but a
    # Transparent BSDF mixed with an alpha-0.6 Principled is exactly the surface EEVEE
    # cannot sort: it put film grain over the whole shell that no sample count removed
    # (32 and 96 TAA samples were pixel-identical; hiding the hull removed it entirely),
    # and one blown white wedge where the interior lamps struck the sloped wall. A real
    # cutaway — opaque hull, near arc booleaned out, Solidify for wall thickness — is what
    # the reference documentaries actually show, and it renders clean.
    #
    # Deliberately dull: a bright smooth inner wall lit from above renders as a lamp
    # shade. An unbleached thermal blanket takes the light softly and stays a backdrop —
    # at 0.34 with a key on it the far wall clipped to white and became the subject.
    mat_hull = material_principled("capsule-int", (0.18, 0.19, 0.21, 1.0),
                                   metallic=0.0, roughness=0.95)
    bpy.ops.mesh.primitive_cone_add(radius1=3.6, radius2=1.1, depth=3.8, location=(0, 0, 0.4))
    capsule = bpy.context.active_object
    capsule.name = "Capsule"
    capsule.data.materials.append(mat_hull)
    bpy.ops.object.shade_smooth()

    wall = capsule.modifiers.new("Wall", "SOLIDIFY")
    wall.thickness = 0.11
    wall.offset = -1.0
    wall.use_even_offset = True

    # Removes the whole -Y arc down to the deck. Stopping the cut above the floor left the
    # lower feet of the near longerons outside the hull, crossing the shell's own
    # silhouette; taking the opening to the deck leaves the floor plate as the foreground
    # edge of the shot instead.
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -2.8, 1.0))
    cutter = bpy.context.active_object
    cutter.name = "CutawayCutter"
    cutter.scale = (8.0, 6.4, 5.2)
    cutter.display_type = "WIRE"
    cutter.hide_render = True
    cut = capsule.modifiers.new("Cutaway", "BOOLEAN")
    cut.operation = "DIFFERENCE"
    cut.solver = "EXACT"
    cut.object = cutter

    mat_frame = material_principled("frame", METAL_GREY, metallic=0.35, roughness=0.45)
    mat_seat = material_principled("seat", (0.24, 0.26, 0.31, 1.0), roughness=0.85)
    # The cushion is the only saturated thing in the seating group, and at 0.5 red it
    # rendered as the same pale salmon as the over-lit suits. A real fire-retardant seat
    # pad is a dark oxblood; keeping it dark is what lets the suit be the orange object.
    mat_pad = material_principled("pad", (0.30, 0.075, 0.05, 1.0), roughness=0.9)
    mat_suit = material_principled("suit", (0.9, 0.9, 0.92, 1.0), roughness=0.45)
    mat_vis = material_principled("visor", (0.75, 0.55, 0.15, 1.0), metallic=0.9, roughness=0.08)
    # 2.0 clipped these to flat white-blue rectangles that read as stickers pasted on the
    # lockers. A lit panel is bright *relative* to its surroundings, not saturated: the
    # colour goes deep enough that the emission still leaves the blue in it.
    mat_panel = material_emissive("panel", (0.06, 0.28, 0.62, 1.0), strength=1.0)

    # The hull stays world-fixed so the cutaway opening always faces the camera.
    cabin = bpy.data.objects.new("CabinRig", None)
    bpy.context.scene.collection.objects.link(cabin)

    # Floor plate and four seats on a ring, backs toward the hull
    bpy.ops.mesh.primitive_cylinder_add(radius=3.1, depth=0.16, location=(0, 0, -1.35))
    floor = bpy.context.active_object
    floor.name = "Floor"
    floor.data.materials.append(mat_frame)
    floor.parent = cabin

    # Seat space: local +X is the direction the occupant faces, which is the cabin centre,
    # because the rig rotation below is `atan2(-y, -x)`. Every scale here used to be written
    # for a +Y-facing seat, so the pan rendered as a vertical plate, the backrest stood to
    # the occupant's side, and the cushion floated above them all.
    positions = [(-1.45, -1.25, -1.25), (1.45, -1.25, -1.25),
                 (-1.45, 1.25, -1.25), (1.45, 1.25, -1.25)]
    seats = {"pan": ((0.62, 0.78, 0.06), (0, 0, 0.56), mat_frame),
             "pad": ((0.58, 0.74, 0.10), (0, 0, 0.64), mat_pad),
             "back": ((0.10, 0.58, 0.78), (-0.46, 0, 0.90), mat_seat),
             "arm-l": ((0.44, 0.07, 0.06), (0.02, 0.42, 0.81), mat_frame),
             "arm-r": ((0.44, 0.07, 0.06), (0.02, -0.42, 0.81), mat_frame)}
    for i, pos in enumerate(positions):
        # One empty per seat: parts are built in seat space and face the cabin centre.
        rig = bpy.data.objects.new(f"Seat{i}Rig", None)
        bpy.context.scene.collection.objects.link(rig)
        rig.location = pos
        rig.rotation_euler = (0, 0, math.atan2(-pos[1], -pos[0]))
        for name, (scale, off, mat) in seats.items():
            bpy.ops.mesh.primitive_cube_add(size=1, location=off)
            part = bpy.context.active_object
            part.name = f"Seat{i}-{name}"
            part.scale = scale
            # These parts carry their size as an object scale, and a bevel modifier
            # works in the mesh's own space, so the world round-over is 0.06 * scale:
            # ~4 cm across the pan and backrest faces and near nothing on the 6 cm
            # thin axis, which is the right behaviour for a flat part.
            harden_edges(part, width=0.06, segments=2)
            part.data.materials.append(mat)
            part.parent = rig
        crew = add_astronaut(f"Crew{i}", (0, 0, 0.68), mat_suit, mat_vis, pose="sit")
        crew.parent = rig
        rig.parent = cabin

    # Console and stowage lockers between the seats, so the volume is furnished. Seated
    # against the wall line at their own height; METAL_GREY at metallic 0.6 rendered these
    # as black monoliths because nothing in a closed cabin is bright enough to reflect.
    mat_locker = material_principled("locker", (0.34, 0.34, 0.36, 1.0),
                                     metallic=0.0, roughness=0.8)
    # The four ring positions put one locker dead centre in the cutaway opening, where it
    # occluded the near seats and read as the subject of the shot. Stowage lives on the
    # far arc: behind the crew, where a cutaway model would actually show it. The angles
    # are the gaps between the seats, not the seats themselves — now that a backrest sits
    # on each seat's radial line, a locker 0.16 rad away is inside it.
    lockers = []
    for a, ang in enumerate((0.25, math.pi / 2.0, 2.90)):
        r_lock = wall_r(0.1) - 0.36
        bpy.ops.mesh.primitive_cube_add(size=1, location=(r_lock * math.cos(ang), r_lock * math.sin(ang), -0.05))
        locker = bpy.context.active_object
        locker.name = f"Locker{a}"
        locker.scale = (0.38, 0.85, 0.95)
        locker.rotation_euler = (0, 0, ang)
        harden_edges(locker, width=0.05, segments=2)
        # A stowage locker is a formed sheet, and formed sheet oil-cans. Without relief
        # these three boxes were the flattest objects in the shot at exactly the height
        # the eye uses to judge the room.
        surface_relief(locker, amplitude=0.006, wavelength=0.6, cuts=2,
                       turbulence=0.4, seed=(a * 2.1, a * 0.7, a * 1.3))
        locker.data.materials.append(mat_locker)
        locker.parent = cabin
        lockers.append(locker)
        # A screen is a display set into a bezel, not a rectangle of light pasted on a
        # wall. The frame is what gives the panel a thickness and a shadow line, and it
        # is the difference between "instrument" and "sticker".
        bpy.ops.mesh.primitive_cube_add(size=1,
                                        location=((r_lock - 0.20) * math.cos(ang), (r_lock - 0.20) * math.sin(ang), 0.55))
        bezel = bpy.context.active_object
        bezel.name = f"ScreenBezel{a}"
        bezel.scale = (0.10, 0.52, 0.40)
        bezel.rotation_euler = (0, 0, ang)
        harden_edges(bezel, width=0.08, segments=2)
        bezel.data.materials.append(mat_locker)
        bezel.parent = cabin
        bpy.ops.mesh.primitive_cube_add(size=1,
                                        location=((r_lock - 0.26) * math.cos(ang), (r_lock - 0.26) * math.sin(ang), 0.55))
        screen = bpy.context.active_object
        screen.name = f"Screen{a}"
        screen.scale = (0.05, 0.42, 0.30)
        screen.rotation_euler = (0, 0, ang)
        screen.data.materials.append(mat_panel)
        screen.parent = cabin

    # Primary structure. A cutaway only reads as a cutaway if there is something behind
    # the wall: longerons and frames give the shell its skeleton, and without them the
    # seats float in an empty drum. Both follow the cone: the wall closes 2.5 m over
    # 3.8 m of height, so a longeron is tilted atan(2.5/3.8) = 33 degrees, not vertical.
    #
    # Two things this block got wrong before. It was parented to the turntable, so the
    # skeleton swung through the fixed opening the hull no longer had — hoops hanging in
    # empty air. And it was never cut: a full ring's near half sat in the void where the
    # wall had been removed. Joining to one mesh and running the same cutter through it
    # fixes both, because the frame now stops exactly where the hull stops.
    mat_truss = material_principled("cabin-truss", (0.42, 0.43, 0.46, 1.0),
                                    metallic=0.75, roughness=0.35)
    rib_lo, rib_hi = -1.30, 1.60
    rib_len = math.hypot(wall_r(rib_lo) - wall_r(rib_hi), rib_hi - rib_lo)
    rib_tilt = math.atan2(wall_r(rib_lo) - wall_r(rib_hi), rib_hi - rib_lo)
    rib_r = (wall_r(rib_lo) + wall_r(rib_hi)) / 2.0 - 0.16
    frame_parts = []
    for k in range(8):
        ang = k * TAU / 8
        bpy.ops.mesh.primitive_cylinder_add(radius=0.055, depth=rib_len,
                                            location=(rib_r * math.cos(ang), rib_r * math.sin(ang),
                                                      (rib_lo + rib_hi) / 2.0),
                                            rotation=(0, -rib_tilt, ang))
        rib = bpy.context.active_object
        rib.name = f"Longeron{k}"
        rib.data.materials.append(mat_truss)
        frame_parts.append(rib)
    for z in (-1.0, 0.2, 1.4):
        bpy.ops.mesh.primitive_torus_add(major_radius=wall_r(z) - 0.16, minor_radius=0.05,
                                         location=(0, 0, z), major_segments=48,
                                         minor_segments=10)
        ring = bpy.context.active_object
        ring.name = f"FrameRing{z}"
        ring.data.materials.append(mat_truss)
        bpy.ops.object.shade_smooth()
        frame_parts.append(ring)

    bpy.ops.object.select_all(action="DESELECT")
    for part in frame_parts:
        part.select_set(True)
    bpy.context.view_layer.objects.active = frame_parts[0]
    bpy.ops.object.join()
    cabin_frame = bpy.context.active_object
    cabin_frame.name = "CabinFrame"
    frame_cut = cabin_frame.modifiers.new("Cutaway", "BOOLEAN")
    frame_cut.operation = "DIFFERENCE"
    frame_cut.solver = "EXACT"
    frame_cut.object = cutter

    # Central equipment column: the volume the four seats look into. Kept low so it does
    # not wall off the far seats from the camera.
    bpy.ops.mesh.primitive_cylinder_add(radius=0.45, depth=1.4, location=(0, 0, -0.62),
                                        vertices=24)
    column = bpy.context.active_object
    column.name = "EqColumn"
    harden_edges(column, width=0.03, segments=2)
    column.data.materials.append(mat_locker)
    column.parent = cabin
    bpy.ops.mesh.primitive_cylinder_add(radius=0.50, depth=0.09, location=(0, 0, 0.10),
                                         vertices=24)
    shelf = bpy.context.active_object
    shelf.name = "ConsoleShelf"
    # 0.62 over a 0.45 column is a 17 cm overhang on every side, which is a table top:
    # the shot's most furniture-shaped object, in the middle of a spacecraft. Pulled to
    # a 5 cm lip, it reads as the rim of a console instead.
    harden_edges(shelf, width=0.02, segments=2)
    shelf.data.materials.append(mat_frame)
    shelf.parent = cabin
    for k, (ang, z) in enumerate(((0.0, -0.20), (TAU / 3, -0.20), (2 * TAU / 3, -0.20),
                                  (0.0, -0.85), (TAU / 3, -0.85), (2 * TAU / 3, -0.85))):
        # Backing plate first, then the lit face in front of it: the same rule the locker
        # screens follow. A bare emissive box on a bare cylinder is the last two
        # stickers left in the shot.
        sw = add_box(f"SwitchBezel{k}", (0.44 * math.cos(ang), 0.44 * math.sin(ang), z),
                     (0.08, 0.44, 0.30), mat_locker)
        sw.rotation_euler = (0, 0, ang)
        harden_edges(sw, width=0.015, segments=2)
        sw.parent = cabin
        bpy.ops.mesh.primitive_cube_add(size=1,
                                        location=(0.49 * math.cos(ang), 0.49 * math.sin(ang), z))
        sw = bpy.context.active_object
        sw.name = f"SwitchPanel{k}"
        sw.scale = (0.05, 0.40, 0.24)
        sw.rotation_euler = (0, 0, ang)
        sw.data.materials.append(mat_panel if k % 2 else mat_truss)
        sw.parent = cabin

    # Deck hardware, then the tile. Eight radial stringers and a centre ring are what
    # turn a 3.1 m flat disc from a card into a floor: they give the eye a set of
    # converging lines to read the room's size from, and each one throws a shadow that
    # changes as the camera moves, which a bare disc cannot do at any sample count.
    mat_deck = material_principled("deck-rib", (0.26, 0.26, 0.28, 1.0),
                                   metallic=0.2, roughness=0.7)
    for k in range(8):
        ang = k * TAU / 8 + TAU / 16
        # add_box bakes the size into the mesh, so the bevel width below is world
        # metres. On a primitive kept at a non-uniform object scale the same width
        # would be a fraction of the *unit* cube and stretch with each axis: 0.02 here
        # would have been 0.75 m along the rib's own length.
        rib = add_box(f"DeckStringer{k}", (1.55 * math.cos(ang), 1.55 * math.sin(ang), -1.24),
                      (3.0, 0.09, 0.10), mat_deck)
        rib.rotation_euler = (0, 0, ang)
        harden_edges(rib, width=0.02, segments=2)
        rib.parent = cabin
    bpy.ops.mesh.primitive_torus_add(major_radius=1.9, minor_radius=0.055,
                                     location=(0, 0, -1.24), major_segments=48,
                                     minor_segments=8)
    deck_ring = bpy.context.active_object
    deck_ring.name = "DeckRing"
    bpy.ops.object.shade_smooth()
    deck_ring.data.materials.append(mat_deck)
    deck_ring.parent = cabin

    # The upper wall was the largest empty area in the frame, and an empty cone reads as
    # a studio backdrop however good the tile on it is. Three attempts at it.
    #
    # One: three arcs at one radius and one angular span — rendered as a handrail.
    # Two: four runs with their own spans, heights and sags — rendered as a garden trellis,
    # and the reason is the cone itself. By z=0.98 the wall has already closed to 2.0 m
    # radius, so a harness up there runs within 16 cm of the z=1.4 frame ring, and two
    # nearly concentric circles crossing eight tilted longerons at shallow angles read as
    # a fence no matter what the individual runs do.
    #
    # Three: the runs are not decorative. One trunk, clamped to the wall five times along
    # its length, that drops into the top of each display bezel — which is also what makes
    # the three screens read as instruments instead of stickers on a wall.
    mat_conduit = material_principled("conduit", (0.16, 0.16, 0.18, 1.0),
                                      metallic=0.0, roughness=0.75)

    def on_wall(ang, z, standoff=0.10):
        r = wall_r(z) - standoff
        return (r * math.cos(ang), r * math.sin(ang), z)

    def loom(name, pts, radius=0.028):
        cu = bpy.data.curves.new(name, "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth = radius
        cu.bevel_resolution = 3
        sp = cu.splines.new("NURBS")
        sp.points.add(len(pts) - 1)
        for p, xyz in zip(sp.points, pts):
            p.co = (*xyz, 1.0)
        sp.use_endpoint_u = True
        sp.order_u = 4
        ob = bpy.data.objects.new(name, cu)
        bpy.context.scene.collection.objects.link(ob)
        ob.data.materials.append(mat_conduit)
        ob.parent = cabin
        return ob

    TRUNK_Z, TRUNK_A0, TRUNK_A1 = 0.98, 0.10, 2.95

    def trunk_z(ang):
        return TRUNK_Z - 0.09 * math.sin(math.pi * (ang - TRUNK_A0) / (TRUNK_A1 - TRUNK_A0))

    loom("CableTrunk", [on_wall(TRUNK_A0 + (TRUNK_A1 - TRUNK_A0) * i / 8.0,
                                trunk_z(TRUNK_A0 + (TRUNK_A1 - TRUNK_A0) * i / 8.0))
                        for i in range(9)])
    for i in range(5):
        ang = TRUNK_A0 + (TRUNK_A1 - TRUNK_A0) * (i + 0.5) / 5.0
        clamp = add_box(f"TrunkClamp{i}", on_wall(ang, trunk_z(ang), standoff=0.055),
                        (0.13, 0.085, 0.085), mat_conduit)
        clamp.rotation_euler = (0, 0, ang)
        harden_edges(clamp, width=0.012, segments=2)
        clamp.parent = cabin

    # A display is wired, and the wire is the cheapest thing that proves the panel belongs
    # to the ship. r_bezel repeats the ScreenBezel centre radius from the locker loop.
    r_bezel = wall_r(0.1) - 0.56
    for k, ang in enumerate((0.25, math.pi / 2.0, 2.90)):
        r0, z0 = wall_r(TRUNK_Z) - 0.10, trunk_z(ang)
        r1, z1 = r_bezel, 0.77
        loom(f"CableDrop{k}", [((r0 + (r1 - r0) * t / 3.0) * math.cos(ang),
                                (r0 + (r1 - r0) * t / 3.0) * math.sin(ang),
                                z0 + (z1 - z0) * t / 3.0) for t in range(4)],
             radius=0.021)

    # Something solid in the bays between the lockers, so the upper wall is not only
    # lines. The first version of this hung two 0.24 m boxes from the ceiling at z=1.15 —
    # which is exactly the camera's sightline to the left display, so one occluded a
    # screen and both read as the thing the shot is about. A cube in mid-air is the
    # original complaint. These are flush panels instead: set into the wall line at the
    # same height as the displays, so they are furniture in the wall, not objects in the
    # room.
    overhead = []
    # Standoff is measured from the cone surface, and the cone is Solidified with offset
    # -1, so the surface the cabin actually shows is 0.11 inside it. A panel back at
    # standoff 0.05 is buried in the wall material and only its louvers come through.
    for k, ang in enumerate((0.91, 2.24)):
        panel = add_box(f"EnvPanel{k}", on_wall(ang, 0.85, standoff=0.16),
                        (0.10, 0.55, 0.42), mat_locker)
        panel.rotation_euler = (0, 0, ang)
        harden_edges(panel, width=0.015, segments=2)
        panel.parent = cabin
        overhead.append(panel)
        # Proud of the face means toward the cabin centre, which is the smaller radius.
        # The radius is taken once, at the panel's own height: on_wall would re-read the
        # cone at each louver's z, and over the 0.22 m stack that leans the row 15 cm
        # inward, so the bottom slat ends up inside the panel and the top one in the room.
        r_face = wall_r(0.85) - 0.225
        for j in range(4):
            z = 0.85 - 0.11 + j * 0.075
            slat = add_box(f"EnvLouver{k}-{j}", (r_face * math.cos(ang),
                                                 r_face * math.sin(ang), z),
                           (0.03, 0.44, 0.022), mat_conduit)
            slat.rotation_euler = (0, 0, ang)
            slat.parent = cabin
        readout = add_box(f"EnvReadout{k}", (r_face * math.cos(ang),
                                             r_face * math.sin(ang), 1.005),
                          (0.02, 0.16, 0.08), mat_panel)
        readout.rotation_euler = (0, 0, ang)
        readout.parent = cabin

    # Relief before UVs, everywhere: the tile is projected on the base mesh, and a
    # subsurf added afterwards would stretch it.
    apply_surface([floor, column, shelf] + lockers + overhead, "cabin_deck", cube_size=0.7)

    # Spread over three sources so the interior gets a near/far gradient instead of one
    # bright blob, and low enough that the dull blanket wall stays a backdrop.
    #
    # These energies came out of a measurement, not a taste call. A locker with 0.50
    # linear albedo rendered at (214, 218, 224) — 0.70 in linear, i.e. the cabin was a
    # little over a stop hot — and at that level nothing in the frame can be dark, so the
    # seats, the suits and the wall all collapsed into the same pale grey band and the
    # shot lost every depth cue the cutaway was supposed to give it.
    add_area_light("interior", location=(0, 0, 2.2), energy=68.0,
                   color=(1.0, 0.95, 0.88), size=2.4)
    add_area_light("cabin-low", location=(0, -2.0, 0.1), energy=68.0,
                   color=(0.7, 0.82, 1.0), size=2.0)
    add_area_light("cabin-aft", location=(0, 2.2, 0.5), energy=56.0,
                   color=(0.95, 0.88, 0.78), size=1.8)

    # The cutaway is the reason this light exists. Everything on the near arc — the near
    # seats — faces out through the opening into a world at 0.02, so it rendered as a
    # black monolith standing in front of a lit cabin. A key from the camera side is what
    # an actual cutaway model gets under studio lights.
    add_area_light("cutaway-key", location=(1.5, -6.2, 2.8), energy=92.0,
                   color=(1.0, 0.97, 0.93), size=5.0)

    # No turntable. The shell and its skeleton are cut on a fixed plane, so spinning the
    # furnishings inside them swung lockers and longerons through the opening. The camera
    # move carries the shot instead.
    for frame in range(1, SHOT_FRAMES + 1):
        t = (frame - 1) / (SHOT_FRAMES - 1)
        cam.location = (math.sin(t * 1.2) * 1.8, -7.2 + math.cos(t * 0.6) * 0.6,
                        1.9 - t * 0.45)
        cam.keyframe_insert(data_path="location", frame=frame)
        aim_key(cam, (0, 0, 0.3), frame)

    render_animation(output_dir, "crew-quarters")


# ---------------------------------------------------------------------------
# Beat 12: Rendezvous (Orion docking with ICPS)
# ---------------------------------------------------------------------------

def beat_rendezvous(output_dir):
    print("\n=== Beat 12: Rendezvous ===", flush=True)
    wipe()
    setup_scene(fps=30, frame_end=SHOT_FRAMES, resolution_x=1280, resolution_y=720)
    setup_world(SPACE_BG)
    add_starfield()

    cam = add_camera("cam-rendezvous", location=(3, -15, 5), target=(3, 0, 0), lens=35.0)
    add_space_fill()  # lifts the shadow face off pure black
    add_area_light("earthshine", location=(-8, 6, -6), energy=180.0,
                   color=(0.35, 0.55, 0.9), size=10.0)

    mat_icps = material_principled("icps", METAL_GREY, metallic=0.7, roughness=0.3)
    mat_dark = material_principled("icps-dark", (0.08, 0.08, 0.09, 1.0), roughness=0.8)
    mat_orion = material_principled("orion", ROCKET_WHITE, metallic=0.2, roughness=0.3)
    mat_panel = solar_cell_material("solar-panel")

    # ICPS: tank, interstage, engine compartment, docking target
    bpy.ops.mesh.primitive_cylinder_add(radius=1.25, depth=4, location=(0, 0, 0))
    icps = bpy.context.active_object
    icps.name = "ICPS"
    icps.data.materials.append(mat_icps)
    bpy.ops.object.shade_smooth()
    for z, r, d in ((2.05, 1.27, 0.3), (-1.55, 1.35, 0.5)):
        bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=d, location=(0, 0, z))
        band = bpy.context.active_object
        band.name = f"ICPS-band{z}"
        band.data.materials.append(mat_dark)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.45, depth=0.45, location=(0, 0, 2.4))
    collar = bpy.context.active_object
    collar.name = "DockingCollar"
    collar.data.materials.append(mat_dark)
    bpy.ops.object.shade_smooth()
    target = material_emissive("target", (1.0, 0.35, 0.2, 1.0), strength=6.0)
    for k in range(4):
        a = k * TAU / 4
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.09,
                                             location=(0.55 * math.cos(a), 0.55 * math.sin(a), 2.6))
        lamp = bpy.context.active_object
        lamp.name = f"TargetLamp{k}"
        lamp.data.materials.append(target)

    orion = add_orion("rv", (8, 0, 0), mat_orion, mat_icps, mat_panel)
    orion.rotation_euler = (0, math.radians(-90), 0)
    orion.keyframe_insert(data_path="rotation_euler", frame=1)

    # The stack was built along +Z; lay it on +X so the collar faces the incoming Orion
    icps_rig = bpy.data.objects.new("IcpsRig", None)
    bpy.context.scene.collection.objects.link(icps_rig)
    for obj in bpy.data.objects:
        if obj.name.startswith(("ICPS", "DockingCollar", "TargetLamp")):
            obj.parent = icps_rig
    icps_rig.rotation_euler = (0, math.radians(90), 0)

    # Closing at a believable docking speed: the Orion nose stops on the collar
    for frame in range(1, SHOT_FRAMES + 1):
        t = (frame - 1) / (SHOT_FRAMES - 1)
        eased = t * t * (3 - 2 * t)
        x = 8 - eased * 4.45
        orion.location = (x, 0, 0.02 * math.sin(t * math.pi * 3))
        orion.keyframe_insert(data_path="location", frame=frame)
        orion.rotation_euler = (0, math.radians(-90) + math.sin(t * math.pi * 2) * 0.04, 0)
        orion.keyframe_insert(data_path="rotation_euler", frame=frame)

        span = x + 4.0
        dist = span * 1.22
        a = t * 0.9
        aim_x = (x + 1.15 - 2.5) / 2.0
        cam.location = (aim_x + math.sin(a) * dist * 0.35, -dist * 0.92, dist * 0.30)
        cam.keyframe_insert(data_path="location", frame=frame)
        aim_key(cam, (aim_x, 0, 0), frame)

    add_key(cam, SHOT_FRAMES // 2, energy=5.0, angle=math.radians(4.0), elevation=25.0)
    render_animation(output_dir, "rendezvous")


# ---------------------------------------------------------------------------
# Beat 13: CubeSats (4 small satellites deploying)
# ---------------------------------------------------------------------------

def beat_cubesats(output_dir):
    print("\n=== Beat 13: CubeSats ===", flush=True)
    wipe()
    setup_scene(fps=30, frame_end=SHOT_FRAMES, resolution_x=1280, resolution_y=720)
    setup_world(SPACE_BG)
    add_starfield()

    # At 8 units a 40mm lens fills the frame with the hull and AgX clips ROCKET_WHITE to
    # a featureless blob; pulled back and dimmed, the vehicle reads as one object in space.
    cam = add_camera("cam-cubesats", location=(0, -15, 5), target=(0, 0, 0), lens=35.0)
    add_space_fill()  # lifts the shadow face off pure black
    add_earth("EarthDistant", 4.5, (8.0, 50.0, -3.0))

    mat_orion = material_principled("orion", ROCKET_WHITE, metallic=0.2, roughness=0.3)
    mat_metal = material_principled("orion-metal", METAL_GREY, metallic=0.7, roughness=0.3)
    mat_panel = solar_cell_material("solar-panel")

    orion = add_orion("cs", (0, 0, 0), mat_orion, mat_metal, mat_panel)

    # 4 CubeSats riding the ejector rings, then flying out on their own vectors
    sats = []
    ring_r, ring_z = 1.35, -1.3
    vectors = [(5.2, 1.4, 0.6), (-5.2, 1.4, -0.4), (1.2, -5.0, 1.8), (-1.4, 4.6, -1.6)]
    for i, direction in enumerate(vectors):
        a = i * TAU / 4
        sat = add_cubesat((ring_r * math.cos(a), ring_r * math.sin(a), ring_z), i)
        sats.append((sat, direction))

    for frame in range(1, SHOT_FRAMES + 1):
        t = (frame - 1) / (SHOT_FRAMES - 1)
        for i, (sat, direction) in enumerate(sats):
            start = 0.12 + i * 0.15
            p = max(0.0, min(1.0, (t - start) / (1 - start)))
            eased = p * p * (3 - 2 * p)
            home = (ring_r * math.cos(i * TAU / 4), ring_r * math.sin(i * TAU / 4), ring_z)
            sat.location = tuple(home[k] + direction[k] * eased for k in range(3))
            sat.keyframe_insert(data_path="location", frame=frame)
            sat.rotation_euler = (eased * 1.6 + i, eased * 2.4, eased * 1.1)
            sat.keyframe_insert(data_path="rotation_euler", frame=frame)

        a = t * 0.7
        cam.location = (math.sin(a) * 15, -math.cos(a) * 15, 5 - t * 1.5)
        cam.keyframe_insert(data_path="location", frame=frame)
        aim_key(cam, (0, 0, 0), frame)

    add_key(cam, SHOT_FRAMES // 2, energy=4.2, angle=math.radians(4.0), elevation=25.0)
    render_animation(output_dir, "cubesats")


# ---------------------------------------------------------------------------
# Beat 14: Heat Shield (with reentry plasma glow)
# ---------------------------------------------------------------------------

def beat_heat_shield(output_dir):
    print("\n=== Beat 14: Heat Shield ===", flush=True)
    wipe()
    setup_scene(fps=30, frame_end=SHOT_FRAMES, resolution_x=1280, resolution_y=720)
    setup_world((0.05, 0.02, 0.01, 1.0))  # dark reddish
    add_starfield()

    cam = add_camera("cam-heatshield", location=(13.5, -11.0, -1.2), target=(0, 0, 0.8),
                     lens=40.0)

    # Avcoat does not stay black, but it does not turn into a lamp either: under AgX an
    # emission above ~1 on a surface this size clips to a white disc and the capsule's
    # own silhouette disappears, which is the opposite of the point.
    mat_shield = material_principled("shield", (0.16, 0.075, 0.045, 1.0),
                                     metallic=0.0, roughness=0.9,
                                     emission_color=(1.0, 0.22, 0.05, 1.0),
                                     emission_strength=0.10)
    bpy.ops.mesh.primitive_cone_add(radius1=2.0, radius2=1.55, depth=0.5, location=(0, 0, -0.05))
    shield = bpy.context.active_object
    shield.name = "HeatShield"
    shield.data.materials.append(mat_shield)
    bpy.ops.object.shade_smooth()

    bpy.ops.mesh.primitive_cone_add(radius1=1.55, radius2=0.45, depth=1.9, location=(0, 0, 1.2))
    module = bpy.context.active_object
    module.name = "CrewModule"
    module.data.materials.append(
        material_principled("module", ROCKET_WHITE, metallic=0.2, roughness=0.35))
    bpy.ops.object.shade_smooth()
    # Buckled before blanketed, as every other hull here. This cone is the whole subject of
    # the shot and it is the straightest solid in the episode: a 1.9 m flank with nothing on
    # it reflects the plasma glow as one unbroken sheet of white.
    surface_relief(module, amplitude=0.006, wavelength=0.26, cuts=4, turbulence=0.35,
                   seed=(0.9, 2.4, 1.1))
    # Only the module: the ablator below it is charred Avcoat with its own emission term,
    # and every plasma body here is a volume, not a surface a tile could sit on.
    apply_surface(module, "hull_panel")

    mat_collar = material_principled("collar", METAL_GREY, metallic=0.7, roughness=0.3)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.42, depth=0.35, location=(0, 0, 2.3))
    collar = bpy.context.active_object
    collar.name = "DockCollar"
    collar.data.materials.append(mat_collar)
    # Fasteners around the docking flange. The capsule is the only vehicle in this frame and
    # it is 2 m across, so without something small and repeated on it there is nothing for
    # the eye to measure against. Centred on the collar's own top plane so each bolt sits
    # half in the metal, and parented with the inverse: these are modelled where they are
    # meant to be seen, not at the origin, so a bare `.parent =` would add the collar's own
    # 2.3 m offset on top of their 2.475 m and park the ring two metres clear of the vehicle.
    bpy.context.view_layer.update()
    for bolt in bolt_circle("hs-dock", center=(0, 0, 2.475), radius=0.36, count=14,
                            bolt_radius=0.02, material=mat_collar):
        bolt.parent = collar
        bolt.matrix_parent_inverse = collar.matrix_world.inverted()

    # Volumetric quality. The default tile size is coarse enough to band a two-metre bow
    # sheath, and the end plane has to clear the wake or the plume is clipped mid-frame.
    eevee = bpy.context.scene.eevee
    for attr, value in (("volumetric_tile_size", "4"), ("volumetric_samples", 96),
                        ("volumetric_start", 0.05), ("volumetric_end", 80.0)):
        if hasattr(eevee, attr):
            setattr(eevee, attr, value)

    # Bow shock: the hot spot is the stagnation point at the centre of the shield, so the
    # sheath has to decay toward its rim. Two nested volumes — a small hot core inside a
    # wide dim cushion — read as compressed gas; one uniform emissive sheet reads as a lit
    # peach disc and erases the vehicle behind it.
    # Flattened along the flow axis: the shock layer is a thin cushion, not a ball. These
    # are the rest-pose thicknesses the pulse animation below has to preserve.
    # Both sit inside the shield's own 2.0 rim, so the dark edge of the vehicle frames the
    # glow instead of being swallowed by it — the silhouette is what sells the scale.
    bow_z, core_z = 0.22, 0.26
    mat_bow = plasma_volume_material("plasma-bow", (1.0, 0.34, 0.10), density=0.30,
                                     strength=0.95, mode="radial", turb=0.90,
                                     turb_scale=1.6)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=1.72,
                                         location=(0, 0, -0.30))
    plasma = bpy.context.active_object
    plasma.name = "Plasma"
    plasma.scale = (1.0, 1.0, bow_z)
    plasma.data.materials.append(mat_bow)
    bpy.ops.object.shade_smooth()
    plasma.visible_shadow = False

    mat_bow_core = plasma_volume_material("plasma-bow-core", (1.0, 0.60, 0.26),
                                          density=0.55, strength=1.9, mode="radial",
                                          turb=0.95, turb_scale=2.6)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=40, ring_count=20, radius=0.78,
                                         location=(0, 0, -0.34))
    halo = bpy.context.active_object
    halo.name = "PlasmaCore"
    halo.scale = (1.0, 1.0, core_z)
    halo.data.materials.append(mat_bow_core)
    bpy.ops.object.shade_smooth()
    halo.visible_shadow = False

    # The wake runs along local +Z: radius1 sits at the -Z end, so the root of each
    # filament lands on the vehicle and its tip fades aft with no offset to correct.
    #
    # Both surface treatments of this failed from opposite ends. bow=0.10 made the
    # filaments 90% Transparent BSDF, and a transparent shell only traces as deep as
    # refraction_depth (4 m) while the starfield is far beyond it, so it painted the
    # world's dark red across the stars — a bundle of black rods. Raise the same cones to
    # 95% emission and they become ivory sticks, because a cone mesh always shows its own
    # silhouette. Gas has no silhouette: with the Surface socket left unconnected the only
    # thing the eye gets is optical depth, so overlapping streaks accumulate into a plume
    # instead of tiling into a fan.
    # turb_scale has to be read in world units against the body's own width: at 0.9 a noise
    # cell is ~1.1 m across, wider than the filament, so each cone sampled a near-constant
    # value and the field did nothing. The scale below puts the cells inside the bodies,
    # which is what actually rips their edges into eddies.
    # Eight wide bodies stack their emission, so what reads as "cream" is accumulation,
    # not one bright surface: the per-body numbers have to be low enough that the sum, not
    # the individual cone, lands on orange.
    # The envelope has to be the widest body in the column. When the ring streaks sat at
    # 1.15-1.55 m from the axis with roots of 1.05-1.65 m, they poked outside the 1.40 m
    # spine sheath and each one became its own bright band with a dark gap beside it —
    # pass12 rendered as a venetian blind. The sheath is now wider than the ring is deep,
    # so the streaks only add texture inside a body that already reads as one column.
    mat_wake = plasma_volume_material("plasma-wake", (1.0, 0.30, 0.08), density=0.07,
                                      strength=0.28, mode="jet", turb=0.70,
                                      turb_scale=2.2)
    mat_wake_core = plasma_volume_material("plasma-wake-core", (1.0, 0.42, 0.14),
                                           density=0.18, strength=0.42, mode="jet",
                                           turb=0.65, turb_scale=3.2)
    # Fat, overlapping, near-axial bodies rather than a bundle of thin needles. Eight wide
    # cones union into one column and the noise field gives it its edges; thin needles do
    # the opposite — each stays visible as its own flame with a dark gap to its neighbour,
    # which is a fan of torches, not a wake. Same for the taper: a cone closing to 0.02 m
    # draws a visible point, so the aft radius stays wide enough to keep the column open.
    tails = []
    # Every body used to sit on a ring, which made the wake a hollow tube: the camera saw
    # its near and far walls as two bright bands over a dark channel, and that is exactly
    # the "two streams" read. One fat on-axis pair fills the middle, so the column is solid.
    for r_root, r_aft, long, mat in ((1.85, 1.05, 12.2, mat_wake),
                                     (0.95, 0.55, 11.4, mat_wake_core)):
        bpy.ops.mesh.primitive_cone_add(radius1=r_root, radius2=r_aft, depth=long,
                                        location=(0, 0, 0.15 + long / 2.0))
        spine = bpy.context.active_object
        spine.name = f"PlasmaTail-spine-{'sheath' if mat is mat_wake else 'core'}"
        spine.data.materials.append(mat)
        bpy.ops.object.shade_smooth()
        spine.visible_shadow = False
        tails.append(spine)
    for k in range(8):
        # Even azimuths with a small deterministic jitter. The old k*TAU/8 + 0.35*k spiral
        # wrapped unevenly and left a 65-degree gap in the envelope.
        az = k * TAU / 8 + 0.18 * math.sin(k * 2.3)
        long = 11.0 + 1.6 * ((k * 3) % 5) / 4.0
        ring = 0.55 + 0.30 * ((k % 3) / 2.0)
        # Rooted at the shoulder, not above the docking collar. The shock layer wraps the
        # vehicle and peels off its edge; a clear gap between the glowing shield and the
        # first streak reads as smoke from a pipe instead of flow around a body.
        root = mathutils.Vector((ring * math.cos(az), ring * math.sin(az), 0.15))
        for r_root, r_aft, tilt_deg, mat in ((0.95 + 0.25 * (k % 3), 0.60,
                                              2 + 4 * (k % 3) / 2.0, mat_wake),
                                             (0.55 + 0.20 * (k % 3), 0.42,
                                              1 + 3 * (k % 3) / 2.0, mat_wake_core)):
            tilt = math.radians(tilt_deg)
            axis = mathutils.Vector((math.sin(tilt) * math.cos(az),
                                     math.sin(tilt) * math.sin(az), math.cos(tilt)))
            bpy.ops.mesh.primitive_cone_add(radius1=r_root, radius2=r_aft, depth=long,
                                            location=root + axis * (long / 2.0))
            streak = bpy.context.active_object
            streak.name = f"PlasmaTail-{'core' if mat is mat_wake_core else 'sheath'}-{k}"
            streak.rotation_euler = axis.to_track_quat("Z", "Y").to_euler()
            streak.data.materials.append(mat)
            bpy.ops.object.shade_smooth()
            streak.visible_shadow = False
            tails.append(streak)

    # Reentry attitude: shield into the flow, tilted back from vertical. The camera sits
    # low and to the side, so a steep 48-degree pitch turns the glowing face almost
    # straight onto it and the whole shot becomes one bright disc hiding the vehicle.
    # 30 degrees keeps the shield readable at an angle with the module above it.
    stack = bpy.data.objects.new("ReentryRig", None)
    bpy.context.scene.collection.objects.link(stack)
    for obj in (shield, module, collar, plasma, halo) + tuple(tails):
        obj.parent = stack
    stack.rotation_euler = (math.radians(-30), 0, 0)

    add_area_light("plasma-glow", location=(0, 0, -2.6), energy=90.0,
                   color=(1.0, 0.42, 0.12), size=9.0)

    # Animate plasma intensity and a slow roll
    for frame in range(1, SHOT_FRAMES + 1):
        t = (frame - 1) / (SHOT_FRAMES - 1)
        pulse = 1.0 + 0.10 * math.sin(t * math.pi * 6)
        plasma.scale = (pulse, pulse, bow_z)
        plasma.keyframe_insert(data_path="scale", frame=frame)
        halo.scale = (pulse, pulse, core_z)
        halo.keyframe_insert(data_path="scale", frame=frame)
        stack.rotation_euler = (math.radians(-30), 0, t * 0.9)
        stack.keyframe_insert(data_path="rotation_euler", frame=frame)
        cam.location = (13.5 - t * 2.0, -11.0 + t * 1.5, -1.2 + t * 1.8)
        cam.keyframe_insert(data_path="location", frame=frame)
        aim_key(cam, (0, 0, 0.8), frame)

    add_key(cam, SHOT_FRAMES // 2, energy=3.0, angle=math.radians(4.0), elevation=25.0)
    render_animation(output_dir, "heat-shield")


# ---------------------------------------------------------------------------
# Beat 15: Gateway Station (lunar orbit)
# ---------------------------------------------------------------------------

def beat_gateway(output_dir):
    print("\n=== Beat 15: Gateway ===", flush=True)
    wipe()
    setup_scene(fps=30, frame_end=SHOT_FRAMES, resolution_x=1280, resolution_y=720)
    setup_world(SPACE_BG)
    add_starfield()

    cam = add_camera("cam-gateway", location=(8, -8, 4), target=(0, 0, 0), lens=40.0)
    add_space_fill()  # lifts the shadow face off pure black

    moon_center = (0, 26, -14)
    moon = add_planet("Moon", 12.0, moon_center, moon_material(scale=surface_scale(12.0)), segments=512, rings=256)
    craters = add_crater_field("gw-crater", moon, 12.0, 40, seed=5,
                               size_fracs=(0.028, 0.065), uv_range=(0.08, 0.92))
    craters += add_crater_field("gw-speckle", moon, 12.0, 90, seed=19,
                                size_fracs=(0.008, 0.020), uv_range=(0.06, 0.94))
    # Surface detail must ride with the body, or it slides under the rotating sphere
    for obj in craters:
        obj.parent = moon
        obj.matrix_parent_inverse = moon.matrix_world.inverted()

    mat_module = material_principled("module", (0.85, 0.85, 0.9, 1.0), metallic=0.5, roughness=0.3)
    mat_solar = solar_cell_material("solar", cells=(8, 16), axes="XY")
    mat_truss = material_principled("truss", METAL_GREY, metallic=0.7, roughness=0.35)
    mat_foil = material_principled("foil", (0.8, 0.62, 0.2, 1.0), metallic=0.9, roughness=0.3)

    # One rig carries the whole station, so the modules turn together
    station = bpy.data.objects.new("GatewayRig", None)
    bpy.context.scene.collection.objects.link(station)

    def module(name, loc, rot, radius=0.55, depth=2.6, mat=None):
        bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth, location=loc,
                                            rotation=rot)
        obj = bpy.context.active_object
        obj.name = name
        bpy.ops.object.shade_smooth()
        obj.data.materials.append(mat or mat_module)
        obj.parent = station
        return obj

    ppe = module("PPE", (0, 0, 0), (0, math.radians(90), 0), radius=0.7, depth=3.2,
                 mat=mat_foil)
    trunk_specs = [("HALO", (0, 0, 0), (math.radians(90), 0, 0), 0.55, 2.4),
                   ("GateWay-Logistics", (0, 2.4, 0), (math.radians(90), 0, 0), 0.5, 2.0),
                   ("GateWay-Crew", (2.4, 0, 0), (0, math.radians(90), 0), 0.45, 1.8)]
    trunks = [module(name, loc, rot, radius=r, depth=d)
              for name, loc, rot, r, d in trunk_specs]
    # Creased and ribbed before blanketed, as every other hull here. These are 2 m drums
    # hanging in front of the Moon, and a smooth cylinder at that distance is a shape rather
    # than an object; the rings are what let the eye order the modules by size. Rings go on
    # after the relief and are parented to their own module, so each one rides the crease
    # instead of being displaced into it and follows the station's rotation on the trunk's
    # own axis (local Z is the cylinder axis for all four).
    surface_relief(ppe, amplitude=0.010, wavelength=0.24, cuts=4, turbulence=0.45,
                   seed=(1.4, 0.6, 2.2))
    for i, trunk in enumerate(trunks):
        surface_relief(trunk, amplitude=0.005, wavelength=0.24, cuts=4, turbulence=0.45,
                       seed=(0.3 + 1.7 * i, 1.1 - 0.4 * i, 0.8 + 0.9 * i))
    # cube_size 1.5 on the pressurised trunks: hull_panel repeats every 0.7 m at the default
    # density, which on a 2-3 m module gives dozens of narrow strips and reads as instrument
    # panelling rather than as a station hull. 1.5 stretches that to roughly one panel per
    # metre, the scale a trunk is actually built at. The PPE carries the power-processing
    # trunk, so it is blanket-wrapped gold, and the arrays, ports and booms stay as they are
    # — cells and truss are not in the palette.
    apply_surface(trunks, "hull_panel", cube_size=1.5)
    apply_surface(ppe, "mli_gold")
    for trunk, (_, _, _, r, d) in zip(trunks, trunk_specs):
        for ring in stiffener_rings(f"{trunk.name}-bay", center=(0, 0, 0), radius=r + 0.012,
                                    count=3, spacing=d / 3.0, width=0.02,
                                    material=mat_truss):
            ring.parent = trunk
    for ring in stiffener_rings("PPE-bay", center=(0, 0, 0), radius=0.712,
                                count=2, spacing=1.4, width=0.025, material=mat_truss):
        ring.parent = ppe

    # Docking rings, and they have to sit on a hull. The previous pair was parked at
    # z = +/-1.35, which is 0.65 m clear of the power trunk's 0.7 m skin and 0.15 m clear of
    # anything else: two chrome washers floating in front of the Moon were the loudest fake
    # tell in this frame. Each ring now mounts on a module's own end cap, on that cap's
    # axis, and carries a bolt circle on its outer face.
    for loc, axis in (((0, -1.2, 0), "Y"), ((0, 3.4, 0), "Y"), ((-1.6, 0, 0), "X")):
        bpy.ops.mesh.primitive_torus_add(major_radius=0.3, minor_radius=0.08,
                                         location=loc,
                                         rotation=(math.radians(90), 0, 0) if axis == "Y"
                                         else (0, math.radians(90), 0))
        port = bpy.context.active_object
        port.name = f"Port{loc}"
        port.data.materials.append(mat_truss)
        port.parent = station
        bpy.ops.object.shade_smooth()
        k = 1 if axis == "X" else 2
        flange = list(loc)
        flange[k] += 0.08 * (1.0 if loc[k] > 0 else -1.0)
        for bolt in bolt_circle(f"port{loc}", center=tuple(flange), radius=0.3, count=10,
                                bolt_radius=0.018, material=mat_truss, normal=axis):
            bolt.parent = station

    # The arrays hang off the end of a truss that starts outside the pressurised modules.
    # They used to be centred on the boom's own axis and offset in Z, which put the blades
    # floating in front of the Moon with nothing joining them to anything — four blue
    # dashes is a diagram of solar arrays, not a station.
    # The truss has to start on the hull that carries it. Both wings reach the same tip, but
    # the +X side leaves the Crew trunk's end cap at x=3.3 while the -X side leaves the power
    # trunk at x=-1.6. Centring both booms at the same |x| left the whole left array floating
    # 1.8 m clear of the station with nothing joining it to anything.
    for side in (-1, 1):
        root = 1.6 if side < 0 else 3.3
        depth = 7.2 - root
        bpy.ops.mesh.primitive_cylinder_add(radius=0.09, depth=depth,
                                            location=((root + depth / 2.0) * side, 0, 0),
                                            rotation=(0, math.radians(90), 0))
        boom = bpy.context.active_object
        boom.name = f"ArrayBoom{side}"
        boom.data.materials.append(mat_truss)
        boom.parent = station
        for k in range(4):
            x = (3.7 + k * 1.05) * side
            for wy in (-1, 1):
                # A yoke reaches out from the truss and the wing turns on its end, so the
                # blade is visibly carried by the structure rather than parked near it.
                bpy.ops.mesh.primitive_cylinder_add(radius=0.045, depth=1.05,
                                                    location=(x, 0.55 * wy, 0),
                                                    rotation=(math.radians(90), 0, 0))
                yoke = bpy.context.active_object
                yoke.name = f"ArrayYoke{side}-{k}-{wy}"
                yoke.data.materials.append(mat_truss)
                yoke.parent = station
                bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 1.55 * wy, 0))
                panel = bpy.context.active_object
                panel.name = f"Array{side}-{k}-{wy}"
                panel.scale = (0.92, 1.9, 0.035)
                panel.rotation_euler = (0, 0, math.radians(18) * wy)
                panel.data.materials.append(mat_solar)
                panel.parent = station

    # Slow rotation
    for frame in range(1, SHOT_FRAMES + 1):
        t = (frame - 1) / (SHOT_FRAMES - 1)
        station.rotation_euler = (0, 0, t * TAU / 8)
        station.keyframe_insert(data_path="rotation_euler", frame=frame)
        moon.rotation_euler.z = t * 0.06
        moon.keyframe_insert(data_path="rotation_euler", frame=frame)

        dist = 24.0 - t * 5.0
        a = t * 0.8
        cam.location = (dist * math.sin(a), -dist * math.cos(a), 8.0 + math.sin(t * math.pi) * 2.0)
        cam.keyframe_insert(data_path="location", frame=frame)
        aim_key(cam, (0, 0, 0), frame)

    add_key(cam, SHOT_FRAMES // 2, energy=5.0, angle=math.radians(5.0), elevation=25.0, side=-1.0)
    render_animation(output_dir, "gateway")


# ---------------------------------------------------------------------------
# Beat 16: Mars Approach
# ---------------------------------------------------------------------------

def beat_mars(output_dir):
    print("\n=== Beat 16: Mars Approach ===", flush=True)
    wipe()
    setup_scene(fps=30, frame_end=SHOT_FRAMES, resolution_x=1280, resolution_y=720)
    setup_world(SPACE_BG)
    add_starfield()

    cam = add_camera("cam-mars", location=(0, -24, 6), target=(0, 0, 0), lens=35.0)
    add_space_fill()  # lifts the shadow face off pure black

    mars = add_planet("Mars", 3.0, (0, 0, 0), mars_material(scale=surface_scale(3.0, 0.30)), segments=128, rings=64)
    # Frost, not a lid: a scaled sphere at the pole is wider than the planet at that
    # height, so it pokes past the silhouette as a hard-edged white pill. A curved disc
    # hugs the surface, and a radial alpha fade keeps its rim from reading as an edge.
    mat_ice = bpy.data.materials.new("ice-cap")
    mat_ice.use_nodes = True
    inodes, ilinks = mat_ice.node_tree.nodes, mat_ice.node_tree.links
    inodes.clear()
    iout = inodes.new("ShaderNodeOutputMaterial")
    ibsdf = inodes.new("ShaderNodeBsdfPrincipled")
    ibsdf.inputs["Base Color"].default_value = (0.60, 0.58, 0.58, 1.0)
    ibsdf.inputs["Roughness"].default_value = 0.85
    ilinks.new(ibsdf.outputs["BSDF"], iout.inputs["Surface"])
    ilength = inodes.new("ShaderNodeVectorMath")
    ilength.operation = "LENGTH"
    ilinks.new(inodes.new("ShaderNodeTexCoord").outputs["Object"], ilength.inputs[0])
    ifade = inodes.new("ShaderNodeMapRange")
    ifade.inputs["From Min"].default_value = 0.42
    ifade.inputs["From Max"].default_value = 0.93
    ifade.inputs["To Min"].default_value = 1.0
    ifade.inputs["To Max"].default_value = 0.0
    ilinks.new(ilength.outputs["Value"], ifade.inputs["Value"])
    ilinks.new(ifade.outputs["Result"], ibsdf.inputs["Alpha"])
    set_transparent(mat_ice)
    for pole in (1, -1):
        cap = add_curved_disc(f"IceCap{'N' if pole > 0 else 'S'}", (0, 0, 0), 3.0,
                              (0, 0, pole), 0.95, 0.02, mat_ice)
        cap.parent = mars
        cap.visible_shadow = False
    for i, (u, v, size) in enumerate(((0.22, 0.44, 0.5), (0.75, 0.6, 0.35))):
        p, n = surface_point((0, 0, 0), 3.0, u, v)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=size,
                                              location=tuple(p[k] - n[k] * size * 0.4 for k in range(3)))
        valles = bpy.context.active_object
        valles.name = f"Valles{i}"
        valles.scale = (1.6, 1.0, 0.35)
        valles.rotation_euler = n.to_track_quat("Z", "Y").to_euler()
        valles.data.materials.append(material_principled(f"valles{i}", (0.32, 0.13, 0.07, 1.0),
                                                          roughness=1.0))
        valles.parent = mars
    bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=48, radius=3.06, location=(0, 0, 0))
    haze = bpy.context.active_object
    haze.name = "DustHaze"
    mat_haze = bpy.data.materials.new("dust-haze")
    mat_haze.use_nodes = True
    hnodes, hlinks = mat_haze.node_tree.nodes, mat_haze.node_tree.links
    hnodes.clear()
    hout = hnodes.new("ShaderNodeOutputMaterial")
    hbsdf = hnodes.new("ShaderNodeBsdfPrincipled")
    hbsdf.inputs["Base Color"].default_value = (0.85, 0.55, 0.35, 1.0)
    hbsdf.inputs["Roughness"].default_value = 1.0
    hlinks.new(hbsdf.outputs["BSDF"], hout.inputs["Surface"])
    htex = hnodes.new("ShaderNodeTexCoord")
    hnoise = hnodes.new("ShaderNodeTexNoise")
    hnoise.inputs["Scale"].default_value = 0.8
    hnoise.inputs["Detail"].default_value = 6.0
    hlinks.new(htex.outputs["Object"], hnoise.inputs["Vector"])
    hramp = hnodes.new("ShaderNodeValToRGB")
    hramp.color_ramp.elements[0].position = 0.58
    hramp.color_ramp.elements[1].position = 0.82
    hlinks.new(hnoise.outputs["Fac"], hramp.inputs["Fac"])
    hlinks.new(hramp.outputs["Color"], hbsdf.inputs["Alpha"])
    blend_shell(mat_haze)
    haze.data.materials.append(mat_haze)
    haze.parent = mars
    haze.visible_shadow = False

    # Transfer arc the craft actually flies, drawn from the same formula
    def arc(u):
        return (15.0 - 22.0 * u, -9.0 * math.sin(u * math.pi), 1.5 * math.cos(u * math.pi) + 0.5)

    # A hairline at strength 4 reads as a diagram drawn on top of the shot; a thicker,
    # dimmer ribbon reads as something the vehicle left behind.
    #
    # material_emissive cannot do that: it is an opaque Principled whose base colour is
    # its emission colour, so a saturated blue at strength 1.1 renders as a solid plastic
    # hose. Two nested alpha-blended strokes — a bright thin core inside a wide dim sheath
    # — give the same line a soft edge and no silhouette of its own.
    for sheath in (False, True):
        data = bpy.data.curves.new(f"Trajectory{'Sheath' if sheath else 'Core'}", "CURVE")
        data.dimensions = "3D"
        data.bevel_depth = 0.16 if sheath else 0.05
        data.bevel_resolution = 3 if sheath else 2
        data.use_fill_caps = True
        spline = data.splines.new("NURBS")
        samples = 24
        spline.points.add(samples - 1)
        for k in range(samples):
            x, y, z = arc(k / (samples - 1))
            spline.points[k].co = (x, y, z, 1.0)
        spline.order_u = 4
        spline.use_endpoint_u = True
        obj = bpy.data.objects.new(data.name, data)
        bpy.context.scene.collection.objects.link(obj)
        obj.visible_shadow = False
        data.materials.append(plasma_volume_material(
            f"arc-{'sheath' if sheath else 'core'}",
            (0.86, 0.88, 0.94) if sheath else (1.0, 0.96, 0.90),
            density=0.06 if sheath else 0.32,
            strength=0.24 if sheath else 1.9,
            mode="uniform", turb=0.85, turb_scale=1.1))

    mat_ship = material_principled("ship-hull", ROCKET_WHITE, metallic=0.2, roughness=0.35)
    mat_ship_metal = material_principled("ship-metal", METAL_GREY, metallic=0.7, roughness=0.3)
    mat_ship_panel = solar_cell_material("ship-panel")
    ship = add_orion("mars", arc(0.0), mat_ship, mat_ship_metal, mat_ship_panel)
    ship.scale = (0.55, 0.55, 0.55)

    earth = add_earth("EarthDistant", 0.7, (-13, -11, 5))

    for frame in range(1, SHOT_FRAMES + 1):
        t = (frame - 1) / (SHOT_FRAMES - 1)
        mars.rotation_euler.z = t * 0.25
        mars.keyframe_insert(data_path="rotation_euler", frame=frame)

        u = t * 0.92
        x, y, z = arc(u)
        nx, ny, nz = arc(min(1.0, u + 0.01))
        ship.location = (x, y, z)
        ship.keyframe_insert(data_path="location", frame=frame)
        vel = mathutils.Vector((nx - x, ny - y, nz - z))
        ship.rotation_euler = vel.to_track_quat("Z", "Y").to_euler()
        ship.keyframe_insert(data_path="rotation_euler", frame=frame)

        cam.location = (2 * math.sin(t * 0.6), -24 + t * 3, 6 - t * 2.5)
        cam.keyframe_insert(data_path="location", frame=frame)
        aim_key(cam, (x * 0.18, y * 0.1, z * 0.2), frame)

    add_key(cam, SHOT_FRAMES // 2, energy=5.0, angle=math.radians(5.0), elevation=25.0, yaw=-15.0)
    render_animation(output_dir, "mars-approach")


# ---------------------------------------------------------------------------
# Beat 17: Lunar Base
# ---------------------------------------------------------------------------

def beat_lunar_base(output_dir):
    print("\n=== Beat 17: Lunar Base ===", flush=True)
    wipe()
    setup_scene(fps=30, frame_end=SHOT_FRAMES, resolution_x=1280, resolution_y=720)
    setup_world(SPACE_BG)
    add_starfield()

    cam = add_camera("cam-base", location=(16, -17, 9.5), target=(0, 0, 2.2), lens=40.0)
    # The key has to come from the SIDE, and the reason it was not is worth keeping. The old
    # call passed rotation=(72 deg, 0, 30 deg) directly, which is a correct 18 deg elevation —
    # and the wrong azimuth. Measured against this camera the view axis is (-0.68, +0.73) and
    # the light travelled (-0.48, +0.82, -0.31), so the sun sat inside the camera's own
    # quadrant. Every shadow fell away from us, hidden behind the object that cast it, and a
    # scene with no visible shadow is a scene lit by a softbox. It is also why the terrain
    # relief bought nothing: raking light is the only thing that makes a 5 cm rock and a 30 cm
    # rock look different, and front light flattens both into the same grey. This beat was
    # hand-fixed to frame-right and the rest of the episode then moved onto the same rule.
    sun = add_sun_light("sun", location=key_location(cam.location, (0, 0, 2.2),
                                                     distance=12.5),
                        energy=5.0, color=SUN_WHITE, angle=math.radians(2.5))
    # No atmosphere on the Moon, but Earth hangs in this sky and the regolith bounces, so the
    # night side of a hull is not pure black. One cool sun at a tenth of the key lifts the
    # shadow faces without touching the contrast the key just bought — and it comes from
    # frame-left, which is exactly where the shadow faces point.
    add_space_fill("earthshine", location=(-8.7, -8.2, 2.2), energy=0.5)

    surface_center = (0, 0, -42)
    surface = add_planet("Surface", 42.0, surface_center, regolith_material(scale=surface_scale(42.0, 0.10)), segments=512, rings=256)
    # At one tile per metre the regolith image's pebbles land at 16 cm pitch and the whole
    # plain reads as stucco — a painted pattern, which is the one thing a ground plane must
    # never look like. Three metres per tile puts those features at half a metre: the same
    # picture now reads as a rock-strewn plain, which is what the Apollo sites actually look
    # like from a standing position.
    apply_surface(surface, "regolith", cube_size=2.6)
    # Measured: v 0.961-1.000 is in frame, but the near half of that is where the habitat
    # cluster sits, and a displaced bowl there drops the ground under the base rings. This
    # band is the mid-ground beyond the hardware, 13-17 units out from the pole.
    add_crater_field("base-crater", surface, 42.0, 40, seed=31,
                     size_fracs=(0.020, 0.060), uv_range=(0.961, 0.975))
    # The crater band is 12.5 to 13.3 units out from the pole — one narrow ring, and nothing
    # else between the camera and the habitat has any relief at all. That is why the ground
    # read as asphalt: a uniform speckle with no object on it, so the eye had no shadow and
    # no scale cue anywhere in the two thirds of the frame that is dirt.
    #
    # Two tunings before this one. A wide scatter from 4.6 out, mostly centimetre gravel, put
    # 420 blocks in frame and not one of them readable: at the distances the camera actually
    # sees, 18 units and more, a 13 cm rock is four pixels, and a rock that is four pixels is
    # dirt. The pad around the habitats stays clear because it is site work, and the field is
    # the ground between the pad and the horizon, where the blocks are big enough to cast.
    mat_basalt = material_principled("basalt", (0.118, 0.112, 0.106, 1.0),
                                     metallic=0.0, roughness=0.88)
    add_regolith_blocks("base-rock", surface_center, 42.0, 520, seed=17,
                        size=(0.09, 0.55), arc=(10.0, 26.0), mat=mat_basalt)

    mat_habitat = material_principled("habitat", (0.9, 0.9, 0.85, 1.0), metallic=0.3, roughness=0.4)
    mat_foil = material_principled("foil", (0.82, 0.63, 0.22, 1.0), metallic=0.9, roughness=0.3)
    mat_solar = solar_cell_material("solar-array", cells=(15, 11))
    mat_truss = material_principled("base-truss", METAL_GREY, metallic=0.7, roughness=0.35)
    mat_vis = material_principled("visor2", (0.75, 0.55, 0.15, 1.0), metallic=0.9, roughness=0.08)
    mat_suit = material_principled("suit2", (0.9, 0.9, 0.92, 1.0), roughness=0.45)

    # Inflatable domes on a hard-shell base ring, joined by covered tunnels
    dome_spots = [(0, 0), (-3.4, 2.2), (3.4, 2.2)]
    hull_shells, foil_shells = [], []
    for pos in dome_spots:
        bpy.ops.mesh.primitive_cylinder_add(radius=1.35, depth=0.4, vertices=96,
                                            location=(pos[0], pos[1], 0.2))
        ring = bpy.context.active_object
        ring.name = f"BaseRing{pos}"
        # A 32-vertex puck flat-shaded renders as a fluted skirt, and those vertical stripes
        # were the loudest thing on the base. They are an artefact of the tessellation, not of
        # the hardware. Smooth the wall only: the deck plate and the rim keep their hard edge.
        for poly in ring.data.polygons:
            poly.use_smooth = abs(poly.normal.z) < 0.5
        ring.data.materials.append(mat_truss)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=1.3,
                                             location=(pos[0], pos[1], 0.4))
        dome = bpy.context.active_object
        dome.name = f"Habitat{pos}"
        dome.scale = (1.0, 1.0, 0.8)
        dome.data.materials.append(mat_habitat)
        bpy.ops.object.shade_smooth()
        hull_shells.append(dome)

    for pos in dome_spots[1:]:
        # The way between two habitats has to be *seen* or the base reads as three separate
        # shells with a gold blob between them. At radius 0.42 on z=0.35 the tube sat inside
        # both dome footprints and inside the ring walls, so all that came through was two
        # ends. Wider, higher, and long enough to be buried in both hulls: what is left above
        # the deck line is a covered connection, which is the thing the shot is about.
        mid = (pos[0] / 2.0, pos[1] / 2.0, 0.50)
        bpy.ops.mesh.primitive_cylinder_add(radius=0.55, depth=math.hypot(*pos) - 1.0,
                                            location=mid,
                                            rotation=(0, math.radians(90), math.atan2(pos[1], pos[0])))
        tunnel = bpy.context.active_object
        tunnel.name = f"Tunnel{pos}"
        tunnel.data.materials.append(mat_foil)
        bpy.ops.object.shade_smooth()
        foil_shells.append(tunnel)

    # Airlock, mast and an array on a single-axis tracker
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -1.9, 0.5))
    airlock = bpy.context.active_object
    airlock.name = "Airlock"
    airlock.scale = (0.7, 0.7, 0.9)
    airlock.data.materials.append(mat_habitat)
    hull_shells.append(airlock)
    # The domes and the airlock are opaque pressure shells, so they take the panel tile;
    # the tunnels are wrapped in blanket. Rings, mast, dish and truss stay bare metal.
    #
    # Dented before tiled, with a per-body seed: four identical spheres at the same scale are
    # a plate of marbles, and a fabric blanket laid over a rigid tube is never flat where it
    # crosses the rings. The tunnels take the larger crease because foil quilting is a
    # feature of the wrap, not of the pressure vessel inside it.
    for shell in hull_shells:
        surface_relief(shell, amplitude=0.006, wavelength=0.30, cuts=4, turbulence=0.3,
                       seed=tuple(c * 0.37 for c in shell.location))
    for tunnel in foil_shells:
        surface_relief(tunnel, amplitude=0.015, wavelength=0.35, cuts=4, turbulence=0.6,
                       seed=tuple(c * 0.53 for c in tunnel.location))
    # No tile on the domes, and two tunings of the tile proved it. hull_panel is a
    # machined-aluminium photograph whose information is fine linear scratching; at four
    # repeats across a 2.6 m shell the triplanar blend band is a wide latitude collar, and
    # inside that collar the scratches stretch into a smudge. Dropping the pitch to 0.45 to
    # make the seams read made it *worse* — the smudge multiplied into a frosted soap bubble.
    # What the shells already carry is real geometry: surface_relief put genuine buckling in
    # the silhouette, and buckling is what an inflatable actually shows. A plain low-metallic
    # white over that relief reads as technical fabric; a tile over it reads as a rendering
    # artefact. The panels stay on the hard bodies, where the surface really is panelled.
    # The blanket outer layer on the ways is the silver TFE/Kapton build-up, not the gold
    # release film. At mli_gold these two tubes were the most saturated objects in frame and
    # the eye landed on a yellow banana crossing the habitat cluster instead of on the habitat
    # cluster — and the crew, who are the subject of the shot.
    apply_surface(foil_shells, "mli_silver")
    bpy.ops.mesh.primitive_cylinder_add(radius=0.08, depth=4.2, location=(-4.6, -1.6, 2.1))
    mast = bpy.context.active_object
    mast.name = "CommsMast"
    mast.data.materials.append(mat_truss)
    dish_rot = math.radians(70)
    dish_center = mathutils.Vector((-4.6, -1.6, 4.3))
    dish_axis = mathutils.Vector((0.0, -math.sin(dish_rot), math.cos(dish_rot)))
    dish_plane = mathutils.Vector((0.0, math.cos(dish_rot), math.sin(dish_rot)))
    bpy.ops.mesh.primitive_torus_add(major_radius=0.85, minor_radius=0.06,
                                     location=dish_center, rotation=(dish_rot, 0, 0))
    dish = bpy.context.active_object
    dish.name = "CommsDish"
    dish.data.materials.append(mat_truss)
    bpy.ops.object.shade_smooth()
    # A bare ring on a mast is a diagram of an antenna, not one. The reflector is a shallow
    # cone-scan dish whose rim sits on that ring, and the feed horn stands in front of it on
    # the torus's own axis, carried by three struts from the rim.
    bpy.ops.mesh.primitive_cone_add(radius1=0.10, radius2=0.85, depth=0.30,
                                    location=dish_center - 0.15 * dish_axis,
                                    rotation=(dish_rot, 0, 0))
    reflector = bpy.context.active_object
    reflector.name = "DishReflector"
    reflector.data.materials.append(mat_truss)
    bpy.ops.object.shade_smooth()
    horn_at = dish_center + 0.34 * dish_axis
    bpy.ops.mesh.primitive_cylinder_add(radius=0.05, depth=0.22, location=horn_at,
                                        rotation=(dish_rot, 0, 0))
    horn = bpy.context.active_object
    horn.name = "DishFeedhorn"
    horn.data.materials.append(mat_truss)
    for k in range(3):
        a = k * 2.094
        rim = dish_center + 0.85 * (math.cos(a) * mathutils.Vector((1, 0, 0))
                                    + math.sin(a) * dish_plane)
        feed = horn_at - 0.11 * dish_axis
        span = feed - rim
        bpy.ops.mesh.primitive_cylinder_add(radius=0.016, depth=span.length,
                                            location=(rim + feed) / 2.0,
                                            rotation=span.to_track_quat("Z", "Y").to_euler())
        strut = bpy.context.active_object
        strut.name = f"DishStrut{k}"
        strut.data.materials.append(mat_truss)
    bpy.context.view_layer.update()
    for part in (reflector, horn) + tuple(
            o for o in bpy.data.objects if o.name.startswith("DishStrut")):
        part.parent = dish
        part.matrix_parent_inverse = dish.matrix_world.inverted()

    for k in range(3):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(-1.6 + k * 1.6, -4.4, 1.4))
        panel = bpy.context.active_object
        panel.name = f"ArrayPanel{k}"
        panel.scale = (1.5, 0.04, 1.1)
        panel.rotation_euler = (math.radians(-28), 0, 0)
        panel.data.materials.append(mat_solar)
        bpy.ops.mesh.primitive_cylinder_add(radius=0.07, depth=1.3,
                                            location=(-1.6 + k * 1.6, -4.4, 0.65))
        post = bpy.context.active_object
        post.name = f"ArrayPost{k}"
        post.data.materials.append(mat_truss)

    # Landed Orion, rover tracks, and two crew working outside
    landed = add_orion("base", (5.6, -4.2, 1.7),
                       material_principled("base-orion", ROCKET_WHITE, metallic=0.2, roughness=0.35),
                       mat_truss, mat_solar)
    landed.rotation_euler = (0, 0, math.radians(140))
    # Two reads were wrong on this vehicle. It stood on its engine bell with nothing under it,
    # which is a rocket parked on a pad rather than hardware that came down; and its arrays are
    # thin boxes whose face normal is local ±Y, so yawed with the hull they went edge-on to both
    # the sun and the camera and rendered as a black card stabbed into the machine.
    #
    # Four struts splaying to round footpads is the cheapest thing that says "landed", and it
    # gives the eye a scale reference on a body that has none. Modelled in the rig's own space
    # and parented bare, exactly as add_orion models its parts, so they yaw with the vehicle.
    for k in range(4):
        a = math.radians(45 + 90 * k)
        top = mathutils.Vector((0.80 * math.cos(a), 0.80 * math.sin(a), -0.45))
        foot = mathutils.Vector((1.55 * math.cos(a), 1.55 * math.sin(a), -1.665))
        span = foot - top
        bpy.ops.mesh.primitive_cylinder_add(radius=0.055, depth=span.length,
                                            location=(top + foot) / 2.0,
                                            rotation=span.to_track_quat("Z", "Y").to_euler())
        leg = bpy.context.active_object
        leg.name = f"base-leg{k}"
        leg.data.materials.append(mat_truss)
        leg.parent = landed
        bpy.ops.mesh.primitive_cylinder_add(radius=0.24, depth=0.07, vertices=32,
                                            location=foot - mathutils.Vector((0, 0, 0.035)))
        pad = bpy.context.active_object
        pad.name = f"base-pad{k}"
        pad.data.materials.append(mat_truss)
        pad.parent = landed

    # Aimed, not tilted. The fixed 55 deg was right for the old key and wrong for this one,
    # and the reason is a geometry the shot itself creates: the sun is 90 deg away from the
    # camera in azimuth, so a panel pointed at the sun shows the lens its edge, and the edge
    # of a 0.04-unit box is a black card stabbed into the machine.
    #
    # The exact bisector is the other failure, and it is worse: the bisector is by definition
    # the mirror line, so the whole sun reflects into the lens and the array clips to a white
    # board with no grid on it. Weighting the sun at 0.55 moves the glint 31 deg off the view
    # axis, which at cell roughness 0.22 kills the clip, while the panel still sits only 28 deg
    # off the lens and takes 52 % of full sun. Cells legible, array lit, no hot spot — which is
    # where a real two-axis tracker actually settles when a camera is not on its mirror line.
    #
    # Solved in the rig's own space, because the wings are parented bare to a rig that yaws
    # with the hull: undoing the yaw is what turns a world direction into a local euler.
    to_cam = (mathutils.Vector(cam.location) - mathutils.Vector(landed.location)).normalized()
    to_sun = -(sun.rotation_euler.to_matrix() @ mathutils.Vector((0, 0, -1))).normalized()
    aim = (0.55 * to_sun + to_cam).normalized()
    aim_local = mathutils.Matrix.Rotation(math.radians(-140), 3, "Z") @ aim
    for side in (-1, 1):
        bpy.data.objects[f"base-wing{side}"].rotation_euler = aim_local.to_track_quat("Y", "Z").to_euler()
    # Rig z is hip height, and a standing figure's sole sits 1.065 below the hips, so 1.05
    # puts the boots on the regolith (the surface here crests at z=0). The old 0.1 planted
    # the crew knee-deep in the ground and cut 0.4 m off their height.
    add_astronaut("EVA1", (-1.4, -2.9, 1.05), mat_suit, mat_vis)
    add_astronaut("EVA2", (2.6, 3.4, 1.05), mat_suit, mat_vis).rotation_euler = (0, 0, 1.2)

    # Tracks are the cheapest thing that makes a surface read as a place people work. They
    # answer "how did they get here" without a word, and they tie the two halves of the frame
    # — the vehicle that came down and the habitat the crew live in — into one story instead
    # of two prop lists. A rover leaves a *pair* of ruts, and the pair is what makes it a track
    # rather than a scar; a foot leaves one line.
    mat_rut = material_principled("rut", (0.070, 0.068, 0.066, 1.0),
                                  metallic=0.0, roughness=0.98)

    def ground_z(x, y):
        return surface_center[2] + math.sqrt(max(42.0 * 42.0 - x * x - y * y, 0.0))

    def lay_marks(p0, p1, count, offsets, mark, prefix):
        v0, v1 = mathutils.Vector(p0), mathutils.Vector(p1)
        span = v1 - v0
        side = mathutils.Vector((-span.y, span.x)).normalized()
        yaw = math.atan2(span.y, span.x)
        made = []
        for i in range(count):
            t = (i + 0.5) / count
            for j, off in enumerate(offsets):
                c = v0.lerp(v1, t) + side * off
                bpy.ops.mesh.primitive_cube_add(
                    size=1.0, location=(c.x, c.y, ground_z(c.x, c.y) + 0.012))
                m = bpy.context.active_object
                m.name = f"{prefix}-{i}-{j}"
                m.rotation_euler = (0, 0, yaw)
                m.scale = mark
                m.data.materials.append(mat_rut)
                made.append(m)
        return made

    lay_marks((5.2, -3.9), (0.35, -2.15), 26, (-0.42, 0.42), (0.30, 0.13, 0.05), "base-rut")
    lay_marks((0.30, -2.30), (-1.30, -2.85), 14, (0.0,), (0.20, 0.09, 0.04), "base-boot")

    earth = add_earth("Earth", 2.2, (12, 26, 16))

    # Low sun rakes across the regolith, so the relief reads
    for frame in range(1, SHOT_FRAMES + 1):
        t = (frame - 1) / (SHOT_FRAMES - 1)
        earth.rotation_euler.z = t * 0.2
        earth.keyframe_insert(data_path="rotation_euler", frame=frame)
        cam.location = (16 - t * 4, -17 + t * 3, 9.5 - t * 2.5)
        cam.keyframe_insert(data_path="location", frame=frame)
        aim_key(cam, (0, 0, 2.2), frame)

    render_animation(output_dir, "lunar-base")


# ---------------------------------------------------------------------------
# Beat 18: Free-Return Corridor (the 2D diagram rebuilt as one 3D shot)
# ---------------------------------------------------------------------------

def catmull_rom(points, samples):
    """Points along an open Catmull-Rom spline through `points`.

    The end waypoints are duplicated as phantom guides, otherwise the curve would only
    run between the second and second-last points and the craft would start off the line.
    The same function feeds the drawn ribbon and the vehicle riding it, so the craft
    cannot drift off the path the viewer is reading.
    """
    ends = [mathutils.Vector(p) for p in points]
    pts = [ends[0]] + ends + [ends[-1]]
    segments = len(pts) - 3
    out = []
    for s in range(samples):
        u = s / (samples - 1) * segments
        i = min(int(u), segments - 1)
        f = u - i
        p0, p1, p2, p3 = pts[i], pts[i + 1], pts[i + 2], pts[i + 3]
        out.append(0.5 * ((2.0 * p1)
                          + (-p0 + p2) * f
                          + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * f * f
                          + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * f * f * f))
    return out


def beat_free_return(output_dir):
    print("\n=== Beat 18: Free-Return Corridor ===", flush=True)
    wipe()
    setup_scene(fps=30, frame_end=SHOT_FRAMES, resolution_x=1280, resolution_y=720)
    setup_world(SPACE_BG)
    add_starfield()

    # Tight enough that the two planets carry the frame. At y=-36.5 with a 29 mm lens they
    # rendered as marbles and the only large thing on screen was the trail — which is the
    # diagram this shot exists to avoid, no matter what shader the trail wears.
    cam = add_camera("cam-freereturn", location=(1.5, -30.0, 7.0), target=(1.5, 1.0, 0.0),
                     lens=33.0)
    add_space_fill()  # lifts the shadow face off pure black

    earth = add_earth("EarthBig", 4.4, (-17.5, 2.0, 0.0), segments=128, rings=64)
    moon = add_planet("MoonBig", 2.2, (15.2, 3.3, 0.3),
                      moon_material(scale=surface_scale(2.2, 0.30)), segments=96, rings=48)
    add_crater_field("fr", moon, 2.2, count=34, seed=11, size_fracs=(0.025, 0.075))

    # Out from Earth, behind the Moon, and home on gravity alone. The scene is compressed
    # to a ~40 unit span on purpose: at the first 80-unit span the two planets rendered as
    # dots and the corridor was the only thing on screen, which is the diagram look this
    # shot exists to replace. The turn waypoints sit ~2 units off the Moon so the path
    # visibly wraps it, and the last one grazes Earth's limb.
    waypoints = [(-12.4, 2.5, 0.9), (-5.5, -3.3, 0.7), (2.2, -5.8, 0.2),
                 (9.9, -3.3, -0.2), (16.6, 0.6, 0.2), (18.4, 3.3, 0.4),
                 (16.6, 6.0, 0.7), (8.8, 7.7, 0.4), (1.1, 5.5, -0.2),
                 (-6.6, 2.8, 0.2), (-13.0, 1.5, 0.6)]
    path = catmull_rom(waypoints, 160)

    # Two nested strokes, both volume-only. material_emissive is the wrong tool here: it
    # builds an opaque Principled BSDF whose base colour is the same saturated blue as its
    # emission, so the corridor rendered as a solid cyan pipe lit by the sun. The
    # surface-plasma version that replaced it kept the same problem in a different costume
    # — a cone or a tube mesh always shows its own edge, and a hard-edged glowing outline
    # of the whole trajectory is the definition of a diagram. With the Surface socket gone
    # the strokes only carry optical depth, and they are drawn progressively behind the
    # vehicle (bevel_factor_end) so no frame ever contains the completed loop.
    corridor_curves = []
    for sheath in (False, True):
        data = bpy.data.curves.new(f"Corridor{'Sheath' if sheath else 'Core'}", "CURVE")
        data.dimensions = "3D"
        data.bevel_depth = 0.11 if sheath else 0.045
        data.bevel_resolution = 3
        data.use_fill_caps = True
        spline = data.splines.new("NURBS")
        spline.points.add(len(path) - 1)
        for k, p in enumerate(path):
            spline.points[k].co = (p.x, p.y, p.z, 1.0)
        spline.order_u = 4
        spline.use_endpoint_u = True
        obj = bpy.data.objects.new(data.name, data)
        bpy.context.scene.collection.objects.link(obj)
        obj.visible_shadow = False
        data.materials.append(plasma_volume_material(
            f"corridor-{'sheath' if sheath else 'core'}",
            (0.86, 0.88, 0.94) if sheath else (1.0, 0.96, 0.90),
            density=0.05 if sheath else 0.30,
            strength=0.22 if sheath else 1.8,
            mode="uniform", turb=0.85, turb_scale=1.1))
        corridor_curves.append(data)

    mat_body = material_principled("fr-hull", ROCKET_WHITE, metallic=0.2, roughness=0.32)
    mat_metal = material_principled("fr-metal", METAL_GREY, metallic=0.7, roughness=0.3)
    mat_panel = solar_cell_material("fr-panel")
    ship = add_orion("FR", tuple(path[0]), mat_body, mat_metal, mat_panel)
    ship.scale = (1.4, 1.4, 1.4)

    for frame in range(1, SHOT_FRAMES + 1):
        t = (frame - 1) / (SHOT_FRAMES - 1)
        earth.rotation_euler.z = t * 0.22
        earth.keyframe_insert(data_path="rotation_euler", frame=frame)
        bpy.data.objects["EarthBig-clouds"].rotation_euler.z = t * 0.34
        moon.rotation_euler.z = t * 0.10

        u = t * (len(path) - 1)
        k = min(int(u), len(path) - 2)
        f = u - k
        p = path[k] + (path[k + 1] - path[k]) * f
        ship.location = (p.x, p.y, p.z)
        ship.keyframe_insert(data_path="location", frame=frame)
        vel = path[k + 1] - path[k]
        if vel.length > 1e-6:
            ship.rotation_euler = vel.to_track_quat("Z", "Y").to_euler()
            ship.keyframe_insert(data_path="rotation_euler", frame=frame)

        cam.location = (1.5 + math.sin(t * 0.5) * 2.0, -36.5 + t * 1.5, 10 - t * 1.0)
        cam.keyframe_insert(data_path="location", frame=frame)
        aim_key(cam, (1.5, 1.0, 0.0), frame)

    add_key(cam, SHOT_FRAMES // 2, energy=3.4, angle=math.radians(4.0), elevation=17.0, yaw=-10.0)
    render_animation(output_dir, "free-return")


# ---------------------------------------------------------------------------
# Beat 19: Trans-Lunar Injection Burn
# ---------------------------------------------------------------------------

def beat_tli_burn(output_dir):
    print("\n=== Beat 19: TLI Burn ===", flush=True)
    wipe()
    setup_scene(fps=30, frame_end=SHOT_FRAMES, resolution_x=1280, resolution_y=720)
    setup_world(SPACE_BG)
    add_starfield()

    cam = add_camera("cam-tli", location=(24, -36, 8), target=(0, 2.0, 3.0), lens=40.0)
    add_space_fill()  # lifts the shadow face off pure black

    # Earth filling the lower frame, so the burn reads as leaving somewhere
    earth = add_earth("EarthLimb", 26.0, (0, 6, -30.5), segments=192, rings=96)

    mat_stage = material_principled("icps", (0.62, 0.63, 0.66, 1.0), metallic=0.55,
                                    roughness=0.42)
    mat_body = material_principled("tli-hull", ROCKET_WHITE, metallic=0.2, roughness=0.32)
    mat_metal = material_principled("tli-metal", METAL_GREY, metallic=0.7, roughness=0.3)
    mat_panel = solar_cell_material("tli-panel")

    # The ICPS and the service module share a diameter; a narrower stage makes Orion look
    # like it is threaded through a pipe rather than stacked on one.
    bpy.ops.mesh.primitive_cylinder_add(radius=0.85, depth=3.4, location=(0, 0, -1.1))
    stage = bpy.context.active_object
    stage.name = "ICPS"
    stage.data.materials.append(mat_stage)
    bpy.ops.object.shade_smooth()

    bpy.ops.mesh.primitive_cylinder_add(radius=0.88, depth=0.16, location=(0, 0, -2.85))
    skirt = bpy.context.active_object
    skirt.name = "EngineSkirt"
    skirt.data.materials.append(material_principled("skirt", (0.16, 0.16, 0.18, 1.0),
                                                    metallic=0.6, roughness=0.5))
    bpy.ops.object.shade_smooth()

    # Orion's own bell sits ~1.6 below its rig, so the rig has to clear the stage top.
    ship = add_orion("TLI", (0, 0, 2.4), mat_body, mat_metal, mat_panel)

    # radius1 is the -Z end of a primitive cone, so a cone centred on -length/2 with no
    # rotation is wide aft and narrow at the bell, and Generated Z runs 0 at that wide end
    # to 1 at the bell — which is exactly the axis mode="nozzle" fades along. The plume is
    # kept short and the rig lifted because Earth's limb sits only ~5 units under the
    # engine: a longer cone disappears into the planet instead of burning above it.
    #
    # This was three surface-shader cones and it rendered as one solid blue wedge. A cone
    # mesh always shows its own silhouette no matter how the shader is gated, so the only
    # fix is to remove the surface: overlapping volume bodies accumulate into optical
    # depth, which is the thing that actually reads as gas. Same construction as the
    # reentry wake, mirrored so the hot end is the bell instead of the root.
    nozzle_z = -3.0
    # Two-tone by construction, not by colour: a short core driven hard enough that AgX
    # clips it white at the bell, inside a wide dim sheath that fades aft. One uniform
    # strength across the whole cone gives a glass tube — real exhaust is brightest where
    # it leaves the nozzle and almost nothing a few metres aft. Per-body numbers stay low
    # because eleven bodies overlap; the sum has to land on hot white, not each one.
    mat_sheath = plasma_volume_material("tli-sheath", (0.78, 0.80, 0.84), density=0.16,
                                        strength=0.40, mode="nozzle", turb=0.95,
                                        turb_scale=2.6)
    mat_mid = plasma_volume_material("tli-mid", (0.92, 0.90, 0.86), density=0.22,
                                     strength=0.70, mode="nozzle", turb=0.90,
                                     turb_scale=4.0)
    mat_core = plasma_volume_material("tli-core", (1.0, 0.95, 0.88), density=0.50,
                                      strength=2.6, mode="nozzle", turb=0.70,
                                      turb_scale=5.5)
    mat_fil = plasma_volume_material("tli-filament", (0.88, 0.90, 0.94), density=0.11,
                                     strength=0.32, mode="nozzle", turb=0.95,
                                     turb_scale=7.0)

    def plume_cone(name, r_aft, r_bell, length, mat, tilt=0.0, az=0.0):
        """One volume body hanging off the nozzle, bell-end up.

        `dir_aft` points the way the gas travels, and the cone is rotated so its local
        +Z points back toward the engine. That keeps Generated Z=1 at the bell for the
        tilted streaks as well as the axial ones — tracking the aft vector directly
        would flip the taper and put a wide, cold mouth on the nozzle.
        """
        dir_aft = mathutils.Vector((math.sin(math.radians(tilt)) * math.cos(az),
                                    math.sin(math.radians(tilt)) * math.sin(az),
                                    -math.cos(math.radians(tilt))))
        # Positions are relative to the Plume empty, which sits on the nozzle, so the
        # flicker scale in the animation grows the plume out of the bell instead of
        # sliding it off the engine.
        bpy.ops.mesh.primitive_cone_add(radius1=r_aft, radius2=r_bell, depth=length,
                                        location=dir_aft * (length / 2.0))
        obj = bpy.context.active_object
        obj.name = name
        if tilt:
            obj.rotation_euler = (-dir_aft).to_track_quat("Z", "Y").to_euler()
        obj.data.materials.append(mat)
        bpy.ops.object.shade_smooth()
        obj.visible_shadow = False
        return obj

    plume = bpy.data.objects.new("Plume", None)
    bpy.context.scene.collection.objects.link(plume)
    plume.location = (0, 0, nozzle_z)
    plume_parts = [plume_cone("PlumeSheath", 1.30, 0.52, 4.6, mat_sheath),
                   plume_cone("PlumeMid", 0.72, 0.30, 3.4, mat_mid),
                   plume_cone("PlumeCore", 0.34, 0.16, 2.2, mat_core)]
    # Eight fat, near-parallel streaks. Twenty-four thin needles each kept their own
    # silhouette and the burn looked like a bundle of torches; gas only reads as gas when
    # the individual filaments stop being countable, so they are wide and barely tilted.
    for k in range(8):
        plume_parts.append(plume_cone(
            f"PlumeFil-{k}", 0.42 + 0.10 * (k % 3), 0.20 + 0.05 * (k % 2),
            3.2 + 1.1 * ((k * 3) % 4) / 3.0, mat_fil,
            tilt=1.2 + 2.6 * ((k * 5) % 3) / 2.0, az=k * TAU / 8 + 0.37 * k))
    for part in plume_parts:
        part.parent = plume

    # The burn is the only thing under the vehicle, so it has to light it. Without this
    # the ICPS underside stays in the sun's shadow and the engine reads as a drawing.
    glow = add_area_light("tli-glow", location=(0, 0, nozzle_z + 0.4), energy=70.0,
                          color=(0.86, 0.84, 0.80), size=3.0)

    stack = bpy.data.objects.new("TLIStack", None)
    bpy.context.scene.collection.objects.link(stack)
    for obj in (stage, skirt, ship, plume, glow):
        obj.parent = stack
    stack.rotation_euler = (math.radians(18), 0, 0)
    # The stack hangs over a sunlit planet. If it casts, the shot ends with a black
    # aircraft shadow crawling across the ocean — the eye reads that as the subject.
    for obj in (stage, skirt, plume, glow, ship, *ship.children, *plume_parts):
        obj.visible_shadow = False

    for frame in range(1, SHOT_FRAMES + 1):
        t = (frame - 1) / (SHOT_FRAMES - 1)
        earth.rotation_euler.z = t * 0.12
        bpy.data.objects["EarthLimb-clouds"].rotation_euler.z = t * 0.18

        stack.location = (t * 5.0, -t * 3.0, 4.6 + t * 1.0)
        stack.keyframe_insert(data_path="location", frame=frame)
        stack.rotation_euler = (math.radians(18 - t * 6), 0, t * 0.25)
        stack.keyframe_insert(data_path="rotation_euler", frame=frame)

        flicker = 0.86 + 0.14 * math.sin(frame * 0.55) + 0.05 * math.sin(frame * 1.7)
        plume.scale = (flicker, flicker, 1.0 + 0.06 * math.sin(frame * 0.4))
        plume.keyframe_insert(data_path="scale", frame=frame)

        # The aim point stays a fixed distance under the vehicle. Chasing the rig pushed
        # the camera's pitch up until Earth left the frame, and a TLI burn with no planet
        # in shot is just a rocket in the dark.
        cam.location = (24 - t * 6.0, -36 + t * 4.0, 8 - t * 1.0)
        cam.keyframe_insert(data_path="location", frame=frame)
        aim_key(cam, (t * 3.0, 2.0, 3.0 + t * 0.8), frame)

    add_key(cam, SHOT_FRAMES // 2, energy=3.2, angle=math.radians(4.0), elevation=22.0, yaw=-10.0)
    render_animation(output_dir, "tli-burn")


# ---------------------------------------------------------------------------
def main():
    global STILL_ONLY, SHOT_FRAMES
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default="",
                        help="comma-separated beat suffixes to render, e.g. tli-burn,free-return")
    parser.add_argument("--still", action="store_true",
                        help="render only each beat's mid-frame still — look-dev, no animation or encode")
    # Blender leaves its own `--` separator in sys.argv, and argparse reads that as
    # "end of options" — without stripping it every flag becomes an unrecognised
    # positional, the default is used, and --only silently renders all 19 beats.
    args, _ = parser.parse_known_args([a for a in sys.argv[1:] if a != "--"])
    STILL_ONLY = args.still
    wanted = {w.strip().replace("-", "_") for w in args.only.split(",") if w.strip()}

    output_dir = (PROJECT_ROOT / "work" / "episode-artemis-ii" / "renders" / "3d").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    beats = [beat_sls_launch, beat_orion_space, beat_orion_deep_space,
             beat_lunar_flyby, beat_earth_rise, beat_lunar_approach,
             beat_far_side, beat_splashdown, beat_earth_from_moon,
             beat_free_return, beat_tli_burn, beat_apollo_era,
             beat_crew_quarters, beat_rendezvous, beat_cubesats,
             beat_heat_shield, beat_gateway, beat_mars, beat_lunar_base]
    if wanted:
        beats = [b for b in beats if b.__name__.removeprefix("beat_") in wanted]

    print(f"Rendering {len(beats)} Artemis II beats to {output_dir}", flush=True)
    for beat in beats:
        SHOT_FRAMES = _shot_frames_for(beat.__name__)
        print(f"  {beat.__name__}: {SHOT_FRAMES} frames = "
              f"{SHOT_FRAMES / SHOT_FPS:.1f}s", flush=True)
        beat(output_dir)

    print(f"\nAll {len(beats)} beats rendered to {output_dir}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
