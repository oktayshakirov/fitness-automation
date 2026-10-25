"""Procedural hair: CC0 MPFB scalp derivative plus original tied-hair curves.
No reference screenshot pixels or external hair assets are incorporated.
"""
import math
import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from .look import flat_material


def add_hair(body, rig, model):
    states = [(m, m.show_viewport) for m in body.modifiers]
    for m, _ in states:
        if m.type != 'MASK': m.show_viewport = False
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(body.evaluated_get(dg), depsgraph=dg)
    for m, state in states: m.show_viewport = state
    top = max(v.co.z for v in mesh.vertices)
    head_matrix = rig.matrix_world @ rig.data.bones['head'].matrix_local
    inverse = head_matrix.inverted()
    root = bpy.data.objects.new('Hair follows head', None)
    bpy.context.collection.objects.link(root)
    root.matrix_world = head_matrix
    follow = root.constraints.new('COPY_TRANSFORMS')
    follow.target = rig; follow.subtarget = 'head'
    material = flat_material('Dark hair', (.016, .012, .009), rough=.54)
    bsdf = material.node_tree.nodes['Principled BSDF']
    if 'Anisotropic IOR Level' in bsdf.inputs:
        bsdf.inputs['Anisotropic IOR Level'].default_value = .55
    noise = material.node_tree.nodes.new('ShaderNodeTexWave')
    noise.bands_direction = 'X'
    noise.inputs['Scale'].default_value = 18
    noise.inputs['Distortion'].default_value = 6
    bump = material.node_tree.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = .18; bump.inputs['Distance'].default_value = .0005
    material.node_tree.links.new(noise.outputs['Color'], bump.inputs['Height'])
    material.node_tree.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    bm = bmesh.new(); bm.from_mesh(mesh)
    def hairline(y, x):
        t = min(1., max(0., (y+.065)/.14))
        return top-.065-.110*t*t*(3-2*t) + .007*math.sin(x*45)*(1-t)
    for v in bm.verts: v.co.z -= hairline(v.co.y, v.co.x)
    bmesh.ops.bisect_plane(bm, geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
                          plane_co=(0, 0, 0), plane_no=(0, 0, 1), dist=.000001, clear_inner=True)
    for v in bm.verts: v.co.z += hairline(v.co.y, v.co.x)
    bm.normal_update()
    for v in bm.verts:
        v.co += v.normal*.004
        if model == 'male':
            v.co.z += .003*math.sin(v.co.x*90+v.co.y*45)*max(0., 1-(top-v.co.z)/.08)
        v.co = inverse @ v.co
    bm.to_mesh(mesh); bm.free(); mesh.update()
    cap = bpy.data.objects.new('Short crop' if model=='male' else 'Tied scalp hair', mesh)
    bpy.context.collection.objects.link(cap); cap.parent = root
    cap.data.materials.clear(); cap.data.materials.append(material)
    for p in mesh.polygons: p.use_smooth = True
    sub = cap.modifiers.new('Smooth scalp hair', 'SUBSURF'); sub.levels = 1; sub.render_levels = 1
    shell = cap.modifiers.new('Hair thickness', 'SOLIDIFY'); shell.thickness = .002
    objects = [cap]
    def strand(name, points, radius, mat):
        data = bpy.data.curves.new(name, 'CURVE'); data.dimensions = '3D'
        data.bevel_depth = radius; data.bevel_resolution = 3; data.resolution_u = 12
        spline = data.splines.new('BEZIER'); spline.bezier_points.add(len(points)-1)
        for i, (point, co) in enumerate(zip(spline.bezier_points, points)):
            point.co = inverse @ Vector(co)
            point.handle_left_type = 'AUTO'; point.handle_right_type = 'AUTO'
            point.radius = (1., 1., .75, .12)[i]
        obj = bpy.data.objects.new(name, data); bpy.context.collection.objects.link(obj)
        obj.parent = root; data.materials.append(mat); objects.append(obj)
    # Fine combed locks follow the scalp surface rather than a smooth helmet.
    tree = BVHTree.FromPolygons([head_matrix @ v.co for v in mesh.vertices],
                                [list(p.vertices) for p in mesh.polygons])
    lock_material = flat_material('Hair strand sheen', (.024, .018, .013), rough=.55)
    for i in range(17):
        x0 = -.062 + .124*i/16
        points = []
        for t in (0., 1/3, 2/3, 1.):
            x = x0*(1-.65*t)
            y = -.062 + (.130 if model=='female' else .105)*t
            hit, normal, _, _ = tree.ray_cast(Vector((x,y,top+.10)),Vector((0,0,-1)))
            if hit is not None: points.append(tuple(hit+normal*.0012))
        if len(points)==4: strand('Combed scalp lock '+str(i), points, .0009, lock_material)
    if model == 'female':
        path = [(0,.050,top-.060), (0,.110,top-.055), (0,.175,top-.115), (0,.205,top-.235)]
        strand('Compact ponytail', path, .028, material)
        for i in range(8):
            a = i*math.tau/8
            points = [(x+.015*math.cos(a), y, z+.014*math.sin(a)) for x,y,z in path]
            strand('Ponytail lock '+str(i), points, .006, material)
        tie = flat_material('Hair tie', (.04,.045,.05), rough=.85)
        strand('Hair tie band', [(0,.083,top-.057),(0,.087,top-.056),(0,.091,top-.055),(0,.095,top-.055)], .030, tie)
    for obj in [root, *objects]:
        obj['hair'] = True; obj['licence'] = 'MPFB scalp CC0; original procedural hair curves'
    return objects
