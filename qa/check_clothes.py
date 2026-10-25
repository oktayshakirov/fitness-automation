"""Run in Blender against a saved look preview; sample garment clearance each frame.
blender -b review/<id>_<model>.blend --python qa/check_clothes.py
This supplements motion QA and human visual review; it does not approve anything.
"""
import bpy
import json
import os
import sys
from pathlib import Path
from mathutils.bvhtree import BVHTree
from mathutils import Vector
from mathutils.geometry import barycentric_transform

def hits(tree, origin, direction):
    count = 0
    for _ in range(40):
        point, _, _, _ = tree.ray_cast(origin, direction)
        if point is None: return count
        count += 1
        origin = point + direction*.0001
    return count


def inside(tree, point):
    # Closest-face normals alone misclassify concave crotch/armpit regions.
    return all(hits(tree, point, direction) % 2 for direction in
               (Vector((0, 0, 1)), Vector((0, -1, 0))))


scene = bpy.context.scene
body = next(o for o in scene.objects if o.get('fitness_body'))
garments = [o for o in scene.objects if o.get('garment')]
assert len(garments) == (2 if scene['fitness_model'] == 'female' else 1)
for garment in garments:
    assert garment.data.uv_layers.active is not None, 'Missing transferred UVs'
    assert garment.vertex_groups.keys()[:len(body.vertex_groups)] == body.vertex_groups.keys(), 'Missing rig weights'
    assert garment['uv_source'] == body.name
frames = [int(v) for v in os.environ.get('CLOTHES_FRAMES', '').split(',') if v] or list(range(1, scene.frame_end+1))
report = {'complete': frames == list(range(1, scene.frame_end+1)), 'model': scene['fitness_model'], 'frames': len(frames),
          'pass': True, 'covered_skin_hidden': True, 'garments': {}}
for garment in garments:
    report['garments'][garment.name] = {'max_visible_skin_penetration_mm': 0., 'max_added_penetration_mm': 0., 'max_existing_body_contact_mm': 0., 'frame': 1}
for frame in frames:
    print(f'CLOTHES_FRAME {frame}', flush=True)
    scene.frame_set(frame)
    dg = bpy.context.evaluated_depsgraph_get()
    evaluated = body.evaluated_get(dg); mesh = evaluated.to_mesh()
    vertices = [evaluated.matrix_world @ v.co for v in mesh.vertices]
    mesh.calc_loop_triangles()
    triangles = [list(t.vertices) for t in mesh.loop_triangles]
    tree = BVHTree.FromPolygons(vertices, triangles, all_triangles=True)
    covered = mesh.attributes.get('clothing_covered')
    assert covered and covered.domain == 'POINT', 'Missing covered-skin visibility mask'
    values = [Vector((item.value, 0, 0)) for item in covered.data]
    def hidden(point, index):
        a, b, c = triangles[index]
        return barycentric_transform(point, vertices[a], vertices[b], vertices[c],
                                     values[a], values[b], values[c]).x > 0
    # The original deep squat already folds abdomen against upper thigh.
    # Compare fabric with that measured body contact, rather than classifying
    # every natural body fold as a new clothing collision.
    covered_tree = BVHTree.FromPolygons(vertices, [t for t in triangles if all(values[v].x>0 for v in t)], all_triangles=True)
    exposed_tree = BVHTree.FromPolygons(vertices, [t for t in triangles if all(values[v].x<=0 for v in t)], all_triangles=True)
    evaluated.to_mesh_clear()
    for garment in garments:
        evaluated = garment.evaluated_get(dg); mesh = evaluated.to_mesh()
        points = [v.co for v in mesh.vertices] + [p.center for p in mesh.polygons]
        for local in points:
            world = evaluated.matrix_world @ local
            loc, normal, index, distance = tree.find_nearest(world)
            item = report['garments'][garment.name]
            if loc is None or distance*1000 <= item['max_added_penetration_mm']:
                continue
            if (world-loc).dot(normal) >= 0 or hidden(loc, index) or not inside(tree, world):
                continue
            baseline = 0.
            source, _, _, source_distance = covered_tree.find_nearest(world)
            if source is not None and source_distance < .025:
                contact, contact_normal, _, contact_distance = exposed_tree.find_nearest(source)
                if contact is not None and (source-contact).dot(contact_normal) < 0:
                    baseline = contact_distance
            added = max(0., distance-baseline)*1000
            item['max_visible_skin_penetration_mm'] = max(item['max_visible_skin_penetration_mm'], round(distance*1000, 3))
            item['max_existing_body_contact_mm'] = max(item['max_existing_body_contact_mm'], round(baseline*1000, 3))
            if added > item['max_added_penetration_mm']:
                item.update(max_added_penetration_mm=round(added, 3), frame=frame, point=list(world))
        evaluated.to_mesh_clear()
for item in report['garments'].values():
    if item['max_added_penetration_mm'] > 2.: report['pass'] = False
path = Path(bpy.data.filepath).with_name(Path(bpy.data.filepath).stem+'_clothes_qa.json')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.delivery import digest, pipeline_digest, spec_digest
report['id'] = Path(bpy.data.filepath).stem.removesuffix('_'+scene['fitness_model'])
report['blend_sha256'] = digest(bpy.data.filepath)
report['pipeline_sha256'] = pipeline_digest()
report['spec_sha256'] = spec_digest(report['id'])
path.write_text(json.dumps(report, indent=2)+'\n')
print('CLOTHES_QA', json.dumps(report))
if not report['pass']: raise RuntimeError('Garment adds more than 2 mm penetration beyond measured body contact')
