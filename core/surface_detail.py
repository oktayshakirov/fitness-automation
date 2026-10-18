"""Continuous skin-space relief from connected components of fitted muscle meshes.
No extra mesh, tangent normals or world-space texture coordinates are used.
"""
import heapq
import json
import math
from collections import Counter
from pathlib import Path


def bake_surface_detail(body, points, skin, labels, adjacency, trees, groups, out_dir):
    import bpy

    face_components = []
    for name in groups:
        mesh = bpy.data.objects['ZA_' + name].data
        parent = list(range(len(mesh.vertices)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        for edge in mesh.edges:
            a, b = map(find, edge.vertices)
            parent[b] = a
        face_components.append([find(p.vertices[0]) for p in mesh.polygons])

    # Work on the actual connected skin, so UV seams cannot become relief grooves.
    parts = {}
    for i, group in labels.items():
        if groups[group] == 'neck':
            continue
        _, _, face, _ = trees[group].find_nearest(points[i])
        parts[i] = (group, face_components[group][face])
    # Small source fragments should not become dots or blisters on the skin.
    counts = Counter(parts.values())
    for _ in range(3):
        cleaned = dict(parts)
        for i, part in parts.items():
            near = Counter(parts[n] for n in adjacency[i]
                           if n in parts and parts[n][0] == part[0])
            if near:
                winner, count = near.most_common(1)[0]
                if counts[part] < 6 or count >= 3:
                    cleaned[i] = winner
        parts = cleaned
        counts = Counter(parts.values())

    distance = {i: math.inf for i in parts}
    queue = []
    for i, part in parts.items():
        if any(parts.get(n) != part for n in adjacency[i]):
            distance[i] = 0.
            heapq.heappush(queue, (0., i))
    while queue:
        d, i = heapq.heappop(queue)
        if d != distance[i]:
            continue
        for n in adjacency[i]:
            if parts.get(n) != parts[i]:
                continue
            candidate = d + (points[i] - points[n]).length
            if candidate < distance[n]:
                distance[n] = candidate
                heapq.heappush(queue, (candidate, n))
    height = {i: 0. for i in skin}
    for i, d in distance.items():
        # Rounded muscle bellies; bounded in physical metres, not atlas pixels.
        t = min(1., d / .035) if math.isfinite(d) else 0.
        height[i] = t * t * (3 - 2 * t)
    for _ in range(4):
        height = {i: .5 * h + .5 * sum(height[n] for n in adjacency[i]) /
                  max(1, len(adjacency[i])) for i, h in height.items()}
    # No detail on head, hands, feet or excluded shin surfaces, including blur bleed.
    for i in height:
        if i not in parts:
            height[i] = 0.

    attr = body.data.color_attributes.new(name='muscle_surface_relief', type='FLOAT_COLOR', domain='CORNER')
    for loop in body.data.loops:
        h = height.get(loop.vertex_index, 0.)
        attr.data[loop.index].color = (h, h, h, 1.)
    material = body.data.materials[0]
    nodes = material.node_tree.nodes
    next(n for n in nodes if n.type == 'VERTEX_COLOR').layer_name = attr.name
    target = next(n for n in nodes if n.type == 'TEX_IMAGE')
    image = bpy.data.images.new('muscle_surface_height', 2048, 2048, alpha=False, float_buffer=True)
    image.colorspace_settings.name = 'Non-Color'
    target.image = image
    nodes.active = target
    bpy.ops.object.bake(type='EMIT')
    image.filepath_raw = str(Path(out_dir) / 'surface_detail_height.png')
    image.file_format = 'PNG'
    bpy.context.scene.render.image_settings.color_depth = '16'
    image.save()
    report = {'source': 'connected Z-Anatomy muscle surfaces',
              'parts_on_skin': len(set(parts.values())), 'skin_vertices': len(skin),
              'relief_vertices': sum(h > .01 for h in height.values()),
              'height_min': min(height.values()), 'height_max': max(height.values()),
              'ramp_width_m': .035, 'excluded': ['face', 'neck', 'hands', 'feet', 'anterior shin']}
    (Path(out_dir) / 'surface_detail_report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('SURFACE DETAIL', report, flush=True)
