"""Fitted, textured MakeHuman system hair (CC0); rigidly follows the head."""
from pathlib import Path
import bpy

ASSETS = Path(__file__).resolve().parents[1] / 'assets/hair/hair'
STYLES = {'male': 'short01', 'female': 'ponytail01'}


def add_hair(body, rig, model):
    from bl_ext.user_default.mpfb.services.humanservice import HumanService
    style = STYLES[model]
    source = ASSETS / style
    hair = HumanService.add_mhclo_asset(
        str(source / (style + '.mhclo')), body, asset_type='Hair',
        subdiv_levels=0, material_type='NONE', set_up_rigging=False)
    hair.name = model + ' ' + style
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
    bsdf.inputs['Roughness'].default_value = .62
    tex = material.node_tree.nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(str(source / (style + '_diffuse.png')), check_existing=True)
    material.node_tree.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    material.node_tree.links.new(tex.outputs['Alpha'], bsdf.inputs['Alpha'])
    hair.data.materials.clear()
    hair.data.materials.append(material)
    for polygon in hair.data.polygons:
        polygon.use_smooth = True
    for obj in (root, hair):
        obj['hair'] = True
        obj['licence'] = 'MakeHuman system assets CC0; see assets/hair/LICENSE.md'
        obj['hair_style'] = style
    return [hair]
