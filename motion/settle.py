"""Settle the body into soft pads, measured on the posed skin rather than on rigid
landmarks: buttocks and thighs flatten on a seat, so the bones sit lower than the
round rest-pose skin suggests. The render's pad-contact modifier (core.body) presses
whatever sinks in back onto the pad face; these helpers set how far it sinks."""
import bpy
from mathutils import Vector


def skin(P):
    """World positions of the posed skin (shape keys, armature, corrective smooths)."""
    bpy.context.view_layer.update()
    body = max((o for o in P.rig.children if o.type == "MESH"), key=lambda o: len(o.data.vertices))
    ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    pts = [ev.matrix_world @ v.co for v in me.vertices]
    ev.to_mesh_clear()
    return pts


def depth(pts, plane, keep=None):
    """Deepest point (m, negative = below the face) of the skin over a pad face:
    plane = (origin, along, across, normal, half_along, half_across)."""
    o, a, c, n, ha, hc = plane
    best = 1.0
    for p in pts:
        r = p - o
        z = r.dot(n)
        if z < best and abs(r.dot(a)) < ha and abs(r.dot(c)) < hc and (keep is None or keep(p)):
            best = z
    return best


class SkinGap:
    """Signed clearance (m, negative = inside) from one set of skin regions to the
    surface of another, on the posed mesh: e.g. crossed forearms resting on the chest.
    Regions are vertex-group name prefixes, counted where their weight passes 0.5."""

    def __init__(self, P, near, onto):
        body = max((o for o in P.rig.children if o.type == "MESH"), key=lambda o: len(o.data.vertices))
        self.body = body
        names = {g.index: g.name for g in body.vertex_groups}
        helper = {i for i, n in names.items() if n in ("HelperGeometry", "JointCubes")}

        def weight(v, prefixes):
            return sum(g.weight for g in v.groups if names[g.group].startswith(prefixes))
        # the evaluated mesh keeps the skin (the helper geometry is masked away) in order
        kept = [v for v in body.data.vertices if not any(g.group in helper for g in v.groups)]
        self.near = [i for i, v in enumerate(kept) if weight(v, near) > 0.5]
        self.onto = {i for i, v in enumerate(kept) if weight(v, onto) > 0.5}

    def __call__(self):
        from mathutils.bvhtree import BVHTree
        bpy.context.view_layer.update()
        ev = self.body.evaluated_get(bpy.context.evaluated_depsgraph_get())
        me = ev.to_mesh()
        me.calc_loop_triangles()
        co = [ev.matrix_world @ v.co for v in me.vertices]
        tris = [tuple(t.vertices) for t in me.loop_triangles if all(i in self.onto for i in t.vertices)]
        ev.to_mesh_clear()
        tree = BVHTree.FromPolygons(co, tris, all_triangles=True)
        best = 1.0
        for i in self.near:
            loc, n, _, d = tree.find_nearest(co[i], 0.2)
            if loc is not None:
                best = min(best, d if (co[i] - loc).dot(n) > 0 else -d)
        return best
