"""Studio: lights, floor, world colour, orthographic cameras."""
import bpy, math
from mathutils import Vector
from .look import flat_material

# app light background (world colour); the floor is a touch darker
BG = (0.95, 0.955, 0.965)


def studio(scene, floor=True):
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            scene.render.engine = eng
            break
        except TypeError:
            pass
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    w = bpy.data.worlds.new("W"); scene.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (*BG, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
    key = bpy.data.objects.new("key", bpy.data.lights.new("key", "SUN"))
    key.data.energy = 1.5; key.data.angle = math.radians(12)
    key.rotation_euler = (math.radians(50), 0, math.radians(-30))
    fill = bpy.data.objects.new("fill", bpy.data.lights.new("fill", "SUN"))
    fill.data.energy = 0.7; fill.rotation_euler = (math.radians(65), 0, math.radians(140))
    for o in (key, fill):
        scene.collection.objects.link(o)
    if floor:
        bpy.ops.mesh.primitive_plane_add(size=12)
        bpy.context.active_object.data.materials.append(flat_material("floor", (0.93, 0.935, 0.945), 0.9))
    scene.render.fps = 30
    scene.eevee.taa_render_samples = 32


def camera(scene, name, target, yaw_deg, dist=6.0, ortho=2.2, height=None):
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    scene.collection.objects.link(cam)
    cam.data.type = "ORTHO"; cam.data.ortho_scale = ortho
    yaw = math.radians(yaw_deg)
    d = Vector((math.sin(yaw), -math.cos(yaw), 0))  # yaw 0 = in front of a -Y-facing body
    tgt = Vector(target)
    cam.location = tgt + d * dist
    if height is not None:
        cam.location.z = height
    cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
    return cam
