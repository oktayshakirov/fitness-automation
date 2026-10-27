"""Skin landmarks: points on the body surface that touch the floor, a bench or a pad
(upper back, chest, glutes, back of the head, heels). Measured once on the rest mesh,
stored in a bone's local frame, so they follow the pose without evaluating the mesh."""
from mathutils import Vector

# name: (bone, selector) - the selector picks rest-pose skin vertices and a score to maximise
SPECS = {
    "upper_back": ("spine01", lambda v: abs(v.x) < 0.05 and 1.27 < v.z < 1.33, lambda v: v.y),
    "upper_back_hi": ("spine01", lambda v: abs(v.x) < 0.05 and 1.36 < v.z < 1.42, lambda v: v.y),
    "scap.L": ("spine01", lambda v: 0.06 < v.x < 0.13 and 1.28 < v.z < 1.40, lambda v: v.y),
    "scap.R": ("spine01", lambda v: -0.13 < v.x < -0.06 and 1.28 < v.z < 1.40, lambda v: v.y),
    "mid_back": ("spine02", lambda v: abs(v.x) < 0.05 and 1.12 < v.z < 1.18, lambda v: v.y),
    "chest": ("spine01", lambda v: abs(v.x) < 0.04 and 1.22 < v.z < 1.28, lambda v: -v.y),
    "glutes": ("root", lambda v: abs(v.x) < 0.12 and 0.84 < v.z < 0.90, lambda v: v.y),
    "head_back": ("head", lambda v: abs(v.x) < 0.03 and 1.60 < v.z < 1.66, lambda v: v.y),
    "heel.L": ("foot.L", lambda v: v.x > 0.12 and v.z < 0.04, lambda v: v.y),
    "heel.R": ("foot.R", lambda v: v.x < -0.12 and v.z < 0.04, lambda v: v.y),
    "knee.L": ("lowerleg01.L", lambda v: v.x > 0.1 and 0.48 < v.z < 0.53, lambda v: -v.y),
    "knee.R": ("lowerleg01.R", lambda v: v.x < -0.1 and 0.48 < v.z < 0.53, lambda v: -v.y),
}


class Landmarks:
    def __init__(self, P):
        self.P = P
        import bpy
        rig = P.rig
        body = next(o for o in rig.children if o.type == "MESH")
        P.reset()
        # evaluated rest mesh: shape keys applied, the Mask modifier leaves only the skin
        dg = bpy.context.evaluated_depsgraph_get()
        ev = body.evaluated_get(dg)
        me = ev.to_mesh()
        verts = [body.matrix_world @ v.co for v in me.vertices]
        ev.to_mesh_clear()
        self.local = {}
        for name, (bone, sel, score) in SPECS.items():
            if name == 'head_back':
                # Locate the occiput relative to this model's head, rather than
                # the male model's absolute world height.
                head=P.rest_head('head')
                cand=[v for v in verts if abs(v.x-head.x)<.03 and head.z+.025<v.z<head.z+.085]
            else:
                cand = [v for v in verts if sel(v)]
            if not cand:
                continue
            w = max(cand, key=score)
            self.local[name] = (bone, P.rest[bone].inverted() @ w)

    def __getitem__(self, name):
        bone, loc = self.local[name]
        return self.P.rig.pose.bones[bone].matrix @ loc
