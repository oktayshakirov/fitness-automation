"""Procedural compression garments derived from the CC0 MPFB skin.

Skin UVs and deform weights are copied before cutting; bisect interpolates both.
No downloaded clothing. Anatomy colours retain assets/maps/LICENSE.md attribution.
"""
import bpy
import bmesh
from .look import muscle_material


def _shell(body, name, material, bounds, top=False):
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
    if top:
        # Cut the armholes with interpolated edges, not whole-face deletion.
        for x, normal in ((-.18, (1, 0, 0)), (.18, (-1, 0, 0))):
            bmesh.ops.bisect_plane(bm, geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
                                  dist=.000001, plane_co=(x, 0, 0), plane_no=normal,
                                  clear_inner=True)
        # Flatten a scoop-shaped boundary, bisect it, then restore the curvature.
        # This produces a continuous neckline while interpolating UVs/weights.
        def neck(x):
            t = min(1., max(0., (abs(x)-.055)/.07))
            return high-.195 + .195*t*t*(3-2*t)
        for v in bm.verts: v.co.z -= neck(v.co.x)
        bmesh.ops.bisect_plane(bm, geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
                              dist=.000001, plane_co=(0, 0, 0), plane_no=(0, 0, -1),
                              clear_inner=True)
        for v in bm.verts: v.co.z += neck(v.co.x)
    bm.normal_update()
    # Offset away from skin; a smooth fabric surface, not anatomy bump geometry.
    for v in bm.verts:
        v.co += v.normal * (.006 if top else .0015)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    interior = [v.index for v in bm.verts if not v.is_boundary]
    bm.to_mesh(mesh); bm.free(); mesh.update()
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
    follow.offset = .006 if top else .0015
    smooth = garment.modifiers.new('Fabric smoothing', 'SMOOTH')
    smooth.factor = .5; smooth.iterations = 5
    smooth.vertex_group = smooth_group.name
    solid = garment.modifiers.new('Fabric edge', 'SOLIDIFY')
    solid.thickness = .002 if top else .001; solid.offset = 0
    garment['garment'] = True
    garment['uv_source'] = body.name
    garment['licence'] = 'CC0 geometry; anatomy highlights CC BY-SA 4.0'
    return garment


def add_clothing(body, rig, model, primary=(), secondary=()):
    """Minimal shorts for both bodies and a sports top for the female body."""
    fabric = muscle_material(primary, secondary, name='Training fabric',
                             use_normal=False, base=(.025, .033, .045))
    fabric.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = .85
    # Anatomical dimensions adapt to MPFB gender proportions.
    hip = rig.data.bones['upperleg01.L'].head_local.z
    knee = rig.data.bones['lowerleg01.L'].head_local.z
    shoulder = rig.data.bones['upperarm01.L'].head_local.z
    garments = [_shell(body, 'Training shorts', fabric,
                       (hip - (hip-knee)*.40, hip+.11))]
    if model == 'female':
        garments.append(_shell(body, 'Sports top', fabric,
                               (shoulder-.27, shoulder+.10), top=True))
    _hide_covered_skin(body, hip, knee, shoulder, model)
    return garments


def _hide_covered_skin(body, hip, knee, shoulder, model):
    """Standard clothing occlusion: hide only skin skin inside a garment.

    Shader visibility keeps the complete skin geometry available to motion QA and
    the cloth projection. Exposed seam faces retain an 2 mm overlap for coverage.
    """
    states = [(m, m.show_viewport) for m in body.modifiers]
    for m, _ in states: m.show_viewport = False
    bpy.context.view_layer.update()
    evaluated = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh(); points = [v.co.copy() for v in mesh.vertices]
    evaluated.to_mesh_clear()
    for m, state in states: m.show_viewport = state
    low, high = hip-(hip-knee)*.40, hip+.11
    def coverage_distance(point):
        x, _, z = point
        distance = min(.298-abs(x), z-low-.002, high-.002-z)
        if model == 'female':
            t = min(1., max(0., (abs(x)-.055)/.07))
            neckline = shoulder-.095 + .195*t*t*(3-2*t)
            top_distance = min(.178-abs(x), z-(shoulder-.268),
                               shoulder+.098-z, neckline-.002-z)
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
