"""Procedural compression garments derived from the CC0 MPFB skin.

Skin UVs and deform weights are copied before cutting; bisect interpolates both.
No downloaded clothing. Anatomy colours retain assets/maps/LICENSE.md attribution.
"""
import bpy
import bmesh
from .look import muscle_material


def _smooth(t):
    t = min(1., max(0., t))
    return t*t*(3-2*t)


def shorts_hem(x, hip, model):
    # Higher side openings expose the upper thigh; the centre keeps groin coverage.
    depth, rise = (.115, .060) if model == 'female' else (.130, .055)
    return hip-depth + rise*_smooth(abs(x)/.14)


def bra_neck(x, shoulder):
    return shoulder-.065 + .165*_smooth((abs(x)-.065)/.045)


def bra_width(z, shoulder):
    return .18 - .060*_smooth((z-(shoulder-.12))/.10)


def _shell(body, name, material, bounds, top=False, hem=None, shoulder=None):
    # Evaluate macro shape keys and the body-only mask, but not pose/correction.
    states = [(m, m.show_viewport) for m in body.modifiers]
    for m, _ in states:
        if m.type != 'MASK':
            m.show_viewport = False
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(body.evaluated_get(dg),
                                          preserve_all_data_layers=True, depsgraph=dg)
    for m, state in states:
        m.show_viewport = state
    garment = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(garment)
    garment.matrix_world = body.matrix_world.copy()
    for group in body.vertex_groups:
        # Blender 5.2 can retain group names in new_from_object already.
        if group.name not in garment.vertex_groups:
            garment.vertex_groups.new(name=group.name)
    bm = bmesh.new(); bm.from_mesh(mesh)
    low, high = bounds
    # Exact horizontal waist/hem cuts, preserving UV interpolation and skin weights.
    for z, normal in ((low, (0, 0, 1)), (high, (0, 0, -1))):
        bmesh.ops.bisect_plane(bm, geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
                              dist=.000001, plane_co=(0, 0, z), plane_no=normal,
                              clear_inner=True)
    if not top:
        # The rest-pose hands overlap the shorts' height range; exclude them.
        for x, normal in ((-.30, (1, 0, 0)), (.30, (-1, 0, 0))):
            bmesh.ops.bisect_plane(bm, geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
                                  dist=.000001, plane_co=(x, 0, 0), plane_no=normal,
                                  clear_inner=True)
    if hem:
        for v in bm.verts: v.co.z -= hem(v.co.x)
        bmesh.ops.bisect_plane(bm, geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
                              dist=.000001, plane_co=(0, 0, 0), plane_no=(0, 0, 1),
                              clear_inner=True)
        for v in bm.verts: v.co.z += hem(v.co.x)
    if top:
        # Narrow straps above the cups, with wider coverage across the bust band.
        for v in bm.verts: v.co.x /= bra_width(v.co.z, shoulder)
        for x, normal in ((-1., (1, 0, 0)), (1., (-1, 0, 0))):
            bmesh.ops.bisect_plane(bm, geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
                                  dist=.000001, plane_co=(x, 0, 0), plane_no=normal,
                                  clear_inner=True)
        for v in bm.verts: v.co.x *= bra_width(v.co.z, shoulder)
        for v in bm.verts: v.co.z -= bra_neck(v.co.x, shoulder)
        bmesh.ops.bisect_plane(bm, geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
                              dist=.000001, plane_co=(0, 0, 0), plane_no=(0, 0, -1),
                              clear_inner=True)
        for v in bm.verts: v.co.z += bra_neck(v.co.x, shoulder)
    bm.normal_update()
    # Offset away from skin; a smooth fabric surface, not anatomy bump geometry.
    for v in bm.verts:
        v.co += v.normal * (.003 if top else .0015)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    interior = [v.index for v in bm.verts if not v.is_boundary]
    bm.to_mesh(mesh); bm.free(); mesh.update()
    fabric_edge_attribute(mesh)
    smooth_group = garment.vertex_groups.new(name='fabric_interior')
    smooth_group.add(interior, 1., 'REPLACE')
    garment.data.materials.clear(); garment.data.materials.append(material)
    for poly in mesh.polygons:
        poly.use_smooth = True
    for source in body.modifiers:
        if source.type == 'ARMATURE':
            modifier = garment.modifiers.new('Same body rig', 'ARMATURE')
            modifier.object = source.object
            modifier.use_deform_preserve_volume = source.use_deform_preserve_volume
    refine = garment.modifiers.new('Smooth fabric panels', 'SUBSURF')
    refine.subdivision_type = 'SIMPLE'
    refine.levels = 1; refine.render_levels = 1
    # Follow the final corrected skin too (e.g. the overhead shoulder smoothing).
    follow = garment.modifiers.new('Follow corrected skin', 'SHRINKWRAP')
    follow.target = body
    follow.wrap_method = 'NEAREST_SURFACEPOINT'
    follow.wrap_mode = 'OUTSIDE_SURFACE'
    follow.offset = .003 if top else .0015
    smooth = garment.modifiers.new('Fabric smoothing', 'SMOOTH')
    smooth.factor = .6 if top else .5; smooth.iterations = 12 if top else 5
    smooth.vertex_group = smooth_group.name
    solid = garment.modifiers.new('Fabric edge', 'SOLIDIFY')
    solid.thickness = .0015 if top else .001; solid.offset = 0
    garment['garment'] = True
    garment['uv_source'] = body.name
    garment['licence'] = 'CC0 geometry; anatomy highlights CC BY-SA 4.0'
    return garment


def fabric_edge_attribute(mesh):
    """Rest-space distance to cut edges, carried through cloth deformation."""
    from mathutils.kdtree import KDTree
    bm = bmesh.new(); bm.from_mesh(mesh)
    boundary = [v.co.copy() for v in bm.verts if v.is_boundary]
    bm.free()
    tree = KDTree(len(boundary))
    for index, point in enumerate(boundary):
        tree.insert(point, index)
    tree.balance()
    attr = mesh.attributes.get('fabric_edge_distance') or mesh.attributes.new('fabric_edge_distance', 'FLOAT', 'POINT')
    for vertex, item in zip(mesh.vertices, attr.data):
        item.value = tree.find(vertex.co)[2] if boundary else 1.


def fabric_material(primary=(), secondary=(), model="male"):
    """Opaque textile veil over a muted muscle signal, with solid edge binding."""
    colour = (.025, .033, .045)
    fabric = muscle_material(primary, secondary, name='Training fabric',
                             use_normal=False, base=colour,
                             hot=(.32, .065, .060), warm=(.40, .17, .075))
    nt = fabric.node_tree
    bsdf = nt.nodes['Principled BSDF']
    signal = bsdf.inputs['Base Color'].links[0].from_socket
    veil = nt.nodes.new('ShaderNodeMixRGB'); veil.label = 'Outer fabric over muscle tint'
    veil.inputs[0].default_value = .96
    veil.inputs[2].default_value = (*colour, 1)
    nt.links.new(signal, veil.inputs[1])
    edge = nt.nodes.new('ShaderNodeAttribute'); edge.attribute_name = 'fabric_edge_distance'
    band = nt.nodes.new('ShaderNodeMapRange'); band.interpolation_type = 'SMOOTHSTEP'
    band.inputs['From Min'].default_value = .002
    band.inputs['From Max'].default_value = .010
    nt.links.new(edge.outputs['Fac'], band.inputs['Value'])
    binding = nt.nodes.new('ShaderNodeMixRGB'); binding.label = 'Solid waistband and hem binding'
    binding.inputs[1].default_value = (*(c*.65 for c in colour), 1)
    nt.links.new(band.outputs['Result'], binding.inputs[0])
    nt.links.new(veil.outputs[0], binding.inputs[2])
    nt.links.new(binding.outputs[0], bsdf.inputs['Base Color'])
    uv = nt.nodes.new('ShaderNodeTexCoord')
    grain = nt.nodes.new('ShaderNodeTexNoise'); grain.inputs['Scale'].default_value = 550
    grain.inputs['Detail'].default_value = 2
    nt.links.new(uv.outputs['UV'], grain.inputs['Vector'])
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = .16
    bump.inputs['Distance'].default_value = .00018
    nt.links.new(grain.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    bsdf.inputs['Roughness'].default_value = .88
    bsdf.inputs['Sheen Weight'].default_value = .25
    return fabric


def add_clothing(body, rig, model, primary=(), secondary=()):
    """Minimal shorts for both bodies and a sports top for the female body."""
    fabric = fabric_material(primary, secondary, model)
    # Anatomical dimensions adapt to MPFB gender proportions.
    hip = rig.data.bones['upperleg01.L'].head_local.z
    knee = rig.data.bones['lowerleg01.L'].head_local.z
    shoulder = rig.data.bones['upperarm01.L'].head_local.z
    garments = [_shell(body, 'Training shorts', fabric,
                       (shorts_hem(0, hip, model), hip+.070),
                       hem=lambda x: shorts_hem(x, hip, model))]
    if model == 'female':
        garments.append(_shell(body, 'Sports top', fabric,
                               (shoulder-.225, shoulder+.10), top=True, shoulder=shoulder))
    _hide_covered_skin(body, hip, knee, shoulder, model)
    from core.accessories import add_watch, add_shoes
    add_watch(rig)
    add_shoes(rig)
    return garments


def _hide_covered_skin(body, hip, knee, shoulder, model):
    """Standard clothing occlusion: hide only skin inside a garment.

    Shader visibility keeps the complete skin geometry available to motion QA and
    the cloth projection. Exposed seam faces retain a 2 mm overlap for coverage.
    """
    states = [(m, m.show_viewport) for m in body.modifiers]
    for m, _ in states: m.show_viewport = False
    bpy.context.view_layer.update()
    evaluated = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh(); points = [v.co.copy() for v in mesh.vertices]
    evaluated.to_mesh_clear()
    for m, state in states: m.show_viewport = state
    high = hip+.070
    def coverage_distance(point):
        x, _, z = point
        distance = min(.298-abs(x), z-shorts_hem(x, hip, model)-.002, high-.002-z)
        if model == 'female':
            # Keep a generous opaque skin overlap at the curved armhole.
            # Interpolated rest-space cuts move differently from smoothed cloth;
            # the old 2 mm inset could reveal transparency in side views.
            top_distance = min(bra_width(z, shoulder)-.015-abs(x), z-(shoulder-.223),
                               shoulder+.098-z, bra_neck(x, shoulder)-.002-z)
            distance = max(distance, top_distance)
        return distance
    attribute = body.data.attributes.new('clothing_covered', 'FLOAT', 'POINT')
    for index, point in enumerate(points):
        attribute.data[index].value = coverage_distance(point)
    material = body.data.materials[0]; material.surface_render_method = 'DITHERED'
    nt = material.node_tree
    output = nt.nodes.get('Material Output')
    shader = output.inputs['Surface'].links[0].from_socket
    attr = nt.nodes.new('ShaderNodeAttribute'); attr.attribute_name = 'clothing_covered'
    transparent = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    threshold = nt.nodes.new('ShaderNodeMath'); threshold.operation = 'GREATER_THAN'
    threshold.inputs[1].default_value = 0
    nt.links.new(attr.outputs['Fac'], threshold.inputs[0])
    nt.links.new(threshold.outputs[0], mix.inputs[0])
    nt.links.new(shader, mix.inputs[1]); nt.links.new(transparent.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], output.inputs['Surface'])
