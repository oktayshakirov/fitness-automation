"""Fitted, textured MakeHuman system hair (CC0); rigidly follows the head."""
from pathlib import Path
import bpy
from mathutils.bvhtree import BVHTree

ASSETS = Path(__file__).resolve().parents[1] / 'assets/hair/hair'
STYLES = {'male': 'short01', 'female': 'ponytail01'}


def add_hair(body, rig, model):
    from bl_ext.user_default.mpfb.services.humanservice import HumanService
    scalp = None
    if model == 'male':
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        evaluated = body.evaluated_get(dg)
        mesh = evaluated.to_mesh()
        points = [body.matrix_world @ v.co for v in mesh.vertices]
        scalp_top = max(p.z for p in points)
        scalp = BVHTree.FromPolygons(points, [list(p.vertices) for p in mesh.polygons])
        evaluated.to_mesh_clear()
    style = STYLES[model]
    source = ASSETS / style
    hair = HumanService.add_mhclo_asset(
        str(source / (style + '.mhclo')), body, asset_type='Hair',
        subdiv_levels=0, material_type='NONE', set_up_rigging=False)
    hair.name = model + ' ' + style
    _soft_edges(hair)
    if model == 'male':
        # The taper exposes scalp, so do not apply the source full-hair scalp mask.
        for modifier in body.modifiers:
            if modifier.type == 'MASK' and modifier.vertex_group == 'Delete.' + style:
                modifier.show_viewport = False
                modifier.show_render = False
        _fade(hair, scalp, scalp_top)

    # Keep the authored alpha-card silhouette, fitted through the basemesh's
    # macro targets. A rigid head attachment avoids stretching hair into the neck.
    matrix = rig.matrix_world @ rig.data.bones['head'].matrix_local
    root = bpy.data.objects.new('Hair follows head', None)
    bpy.context.collection.objects.link(root)
    root.matrix_world = matrix
    follow = root.constraints.new('COPY_TRANSFORMS')
    follow.target = rig
    follow.subtarget = 'head'
    hair.parent = root
    hair.matrix_parent_inverse = matrix.inverted()
    material = bpy.data.materials.new(style + ' textured hair')
    material.use_nodes = True
    material.surface_render_method = 'DITHERED'
    bsdf = material.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Roughness'].default_value = .66
    tex = material.node_tree.nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(str(source / (style + '_diffuse.png')), check_existing=True)
    color = tex.outputs['Color']
    alpha = tex.outputs['Alpha']
    if model == 'female':
        # Recolour in the shader: retain the authored strand detail and alpha.
        luminance = material.node_tree.nodes.new('ShaderNodeRGBToBW')
        material.node_tree.links.new(color, luminance.inputs[0])
        black = material.node_tree.nodes.new('ShaderNodeValToRGB')
        ramp = black.color_ramp
        ramp.elements[0].color = (.002, .002, .003, 1)
        ramp.elements[1].position = .4
        ramp.elements[1].color = (.035, .038, .042, 1)
        mid = ramp.elements.new(.12)
        mid.color = (.010, .011, .013, 1)
        material.node_tree.links.new(luminance.outputs[0], black.inputs[0])
        color = black.outputs['Color']
    else:
        density = material.node_tree.nodes.new('ShaderNodeAttribute')
        density.attribute_name = 'fade_density'
        product = material.node_tree.nodes.new('ShaderNodeMath')
        product.operation = 'MULTIPLY'
        material.node_tree.links.new(alpha, product.inputs[0])
        material.node_tree.links.new(density.outputs['Fac'], product.inputs[1])
        alpha = product.outputs[0]
    edge = material.node_tree.nodes.new('ShaderNodeAttribute')
    edge.attribute_name = 'hair_edge_softness'
    softened = material.node_tree.nodes.new('ShaderNodeMath'); softened.operation = 'MULTIPLY'
    material.node_tree.links.new(alpha, softened.inputs[0])
    material.node_tree.links.new(edge.outputs['Fac'], softened.inputs[1])
    alpha = softened.outputs[0]
    for name in ('Anisotropic IOR Level', 'Anisotropic'):
        if name in bsdf.inputs:
            bsdf.inputs[name].default_value = .20
            break
    material.node_tree.links.new(color, bsdf.inputs['Base Color'])
    material.node_tree.links.new(alpha, bsdf.inputs['Alpha'])
    hair.data.materials.clear()
    hair.data.materials.append(material)
    for polygon in hair.data.polygons:
        polygon.use_smooth = True
    for obj in (root, hair):
        obj['hair'] = True
        obj['licence'] = 'MakeHuman system assets CC0; see assets/hair/LICENSE.md'
        obj['hair_style'] = style
    return [hair]


def _fade(hair, scalp, top):
    """Shorten the sides/nape toward the fitted scalp and grade hair density."""
    def smooth(value):
        t = min(1., max(0., value))
        return t*t*(3-2*t)
    density = hair.data.attributes.new('fade_density', 'FLOAT', 'POINT')
    inverse = hair.matrix_world.inverted()
    for vertex, value in zip(hair.data.vertices, density.data):
        point = hair.matrix_world @ vertex.co
        sides = max(smooth((abs(point.x)-.035)/.04), smooth((point.y-.005)/.045))
        rise = smooth((point.z-(top-.145))/.09)
        blend = sides*(1-rise)
        nearest, normal, _, _ = scalp.find_nearest(point)
        if nearest is not None:
            clipped = nearest + normal*.0012
            vertex.co = inverse @ point.lerp(clipped, .96*blend)
        value.value = 1-.88*blend
    hair.data.update()


def _soft_edges(hair):
    """Feather authored card boundaries so hairlines and loose ends stay soft."""
    import bmesh
    from mathutils.kdtree import KDTree
    bm = bmesh.new(); bm.from_mesh(hair.data)
    boundary = [v.co.copy() for v in bm.verts if v.is_boundary]
    bm.free()
    attr = hair.data.attributes.new('hair_edge_softness', 'FLOAT', 'POINT')
    if not boundary:
        for item in attr.data: item.value = 1.
        return
    tree = KDTree(len(boundary))
    for index, point in enumerate(boundary): tree.insert(point, index)
    tree.balance()
    top = max(v.co.z for v in hair.data.vertices)
    for vertex, item in zip(hair.data.vertices, attr.data):
        t = min(1., tree.find(vertex.co)[2]/.006)
        low = min(1., max(0., (top-.055-vertex.co.z)/.035))
        item.value = 1-.20*low*(1-t*t*(3-2*t))
