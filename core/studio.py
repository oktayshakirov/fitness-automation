"""Studio: lights, floor, world colour, orthographic cameras."""
import bpy, math
from mathutils import Vector
from .look import flat_material

# White background for the H.264 fallback (2026-10-26). Shader colours are linear.
BG_HEX = "#FFFFFF"
BG_SRGB = (1., 1., 1.)
BG = tuple(c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4
           for c in BG_SRGB)


def studio(scene, floor=True, transparent=False):
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
    scene.render.dither_intensity = 0
    scene.render.film_transparent = transparent
    scene.render.image_settings.color_mode = 'RGBA' if transparent else 'RGB'
    w = bpy.data.worlds.new("W"); scene.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (*BG, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
    # White is the camera backdrop, not an added white environment light.
    # Preserve the established studio illumination/reflections on the models.
    nodes = w.node_tree.nodes
    ambient = nodes.new('ShaderNodeBackground')
    ambient.inputs[0].default_value = (.00303527, .00303527, .00367651, 1)
    ambient.inputs[1].default_value = 1.
    rays = nodes.new('ShaderNodeLightPath')
    backdrop = nodes.new('ShaderNodeMixShader')
    w.node_tree.links.new(rays.outputs['Is Camera Ray'], backdrop.inputs[0])
    w.node_tree.links.new(ambient.outputs[0], backdrop.inputs[1])
    w.node_tree.links.new(nodes['Background'].outputs[0], backdrop.inputs[2])
    w.node_tree.links.new(backdrop.outputs[0], nodes['World Output'].inputs['Surface'])
    key = bpy.data.objects.new("key", bpy.data.lights.new("key", "SUN"))
    key.data.energy = 1.5; key.data.angle = math.radians(12)
    key.rotation_euler = (math.radians(50), 0, math.radians(-30))
    fill = bpy.data.objects.new("fill", bpy.data.lights.new("fill", "SUN"))
    fill.data.energy = 0.7; fill.rotation_euler = (math.radians(65), 0, math.radians(140))
    for o in (key, fill):
        scene.collection.objects.link(o)
    if floor and not transparent:
        bpy.ops.mesh.primitive_plane_add(size=12)
        bpy.context.active_object.name = 'Studio floor'
        bpy.context.active_object['studio_floor'] = True
        # An unlit floor joins the world seamlessly at the exact display colour.
        # Lighting a diffuse floor changes its pixels with camera/light direction.
        m = bpy.data.materials.new("background floor"); m.use_nodes = True
        nt = m.node_tree; nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        emission = nt.nodes.new("ShaderNodeEmission")
        emission.inputs["Color"].default_value = (*BG, 1)
        nt.links.new(emission.outputs[0], out.inputs["Surface"])
        bpy.context.active_object.data.materials.append(m)
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
