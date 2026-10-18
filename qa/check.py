#!/usr/bin/env python3
"""QA gate for a built exercise (review/<id>.blend + motion/specs/<id>.json).

    ./qa/check.py <id> [<id> ...]      # writes review/<id>_qa.json, exit 1 if any fail

Checks, every frame:
  loop      frame 1 == last frame (bones within 1 mm / 0.5 deg)
  slide     a foot vertex that stays on the floor between two frames moves < 5 mm
  floor     no body vertex below the floor (-1 cm)
  grip      hand grip point on its implement: dumbbell handle centre < 2 cm,
            bar axis < 1.5 cm (cable bar, barbell); goblet hands < 5 cm of the handle
  props     implement vertices inside the body (> 5 mm deep), away from the hands
  joints    knee/elbow flexion <= 155 deg, no knee/elbow hyperextension (> 5 deg),
            knees track the toes (bend plane within 30 deg of the foot), wrist
            flexion/extension <= 75 deg, head vs chest <= 50 deg
  balance   centre of mass (segment masses + load) inside the feet's support polygon
            (1 cm margin), standing patterns, frames with both feet down (stepping is
            dynamic; single-support frames and the 4 frames after a foot lands are
            counted, not judged)

Spec overrides: "qa": {"skip": ["balance"], "load_kg": 40, ...}."""
import json, math, os, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"
try:
    import bpy
except ImportError:
    bpy = None

if bpy is None:
    import subprocess
    env = dict(os.environ, BLENDER_USER_RESOURCES=os.path.join(HERE, ".blender-profile"))
    rc = 0
    for eid in sys.argv[1:]:
        cmd = [BLENDER, "-b", os.path.join(HERE, "review", eid + ".blend"), "--python-exit-code", "1", "--python",
               os.path.abspath(__file__), "--", eid]
        r = subprocess.run(cmd, env=env, capture_output=True, text=True)
        out = [l for l in r.stdout.splitlines() if l.startswith(("QA", "  "))]
        print("\n".join(out) if out else r.stdout[-2000:] + r.stderr[-2000:])
        rc = rc or (r.returncode if out else 2)
    sys.exit(rc)

sys.path.insert(0, HERE)
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from core.solver import Poser
from motion.contact import grip_point

eid = sys.argv[sys.argv.index("--") + 1]
spec = json.load(open(os.path.join(HERE, "motion/specs", eid + ".json")))
qa_cfg = spec.get("qa", {})
skip = set(qa_cfg.get("skip", []))
if spec["pattern"] not in ("stand_hinge", "arm_isolation", "split_stance", "overhead_press", "row", "cable"):
    skip.add("balance")

scene = bpy.context.scene
rig = next(o for o in scene.objects if o.type == "ARMATURE")
body = next(o for o in scene.objects if o.type == "MESH" and o.find_armature() == rig)
mask_vg, mask_inv = None, False
for m in body.modifiers:
    if m.type == "MASK":            # MPFB keeps the "body" group and hides the helpers
        mask_vg, mask_inv = m.vertex_group, m.invert_vertex_group
        m.show_viewport = False
P = Poser(rig)
N = scene.frame_end
frames = range(1, N + 1)

# skin vertices (what the Mask modifier shows: no MPFB helper geometry)
vg_index = body.vertex_groups[mask_vg].index if mask_vg and mask_vg in body.vertex_groups else None


def visible(v):
    if vg_index is None:
        return True
    inside = any(g.group == vg_index and g.weight > 0.5 for g in v.groups)
    return inside != mask_inv


skin = [v.index for v in body.data.vertices if visible(v)]
skin_set = set(skin)
skin_polys = [list(p.vertices) for p in body.data.polygons if all(i in skin_set for i in p.vertices)]
rest_z = {v.index: v.co.z for v in body.data.vertices}
# sole = skin vertices near the floor in the rest pose
sole = [i for i in skin if rest_z[i] < 0.02]

fails, warns, stats = [], [], {}


def fail(check, msg):
    fails.append(f"{check}: {msg}")


def body_verts():
    dg = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(dg)
    me = ev.to_mesh()
    co = [body.matrix_world @ me.vertices[i].co for i in range(len(me.vertices))]
    ev.to_mesh_clear()
    return co


# --- per-frame sampling -----------------------------------------------------
props = {o.name: o for o in scene.objects if o.parent is None and o.type == "EMPTY" and o.animation_data}
prop_meshes = {n: [c for c in o.children_recursive if c.type == "MESH"] for n, o in props.items()}
bone_mats = {}
sole_prev = None
slide_max, floor_min = 0.0, 1.0
grip_max = {}
pen_max = 0.0
self_pen_max = 0.0
prop_loop_start = {}
prop_loop_mm = 0.0
prop_loop_deg = 0.0
joint_viol = {}
knee_range = {side: [180.0, 0.0] for side in ("L", "R")}
elbow_range = {side: [180.0, 0.0] for side in ("L", "R")}
joint_at = {}
com_out = 0.0
load_kg = qa_cfg.get("load_kg")
last_air = {}

SEG = [  # (from, to, mass fraction) after Dempster/Winter
    ("head", "head", 0.081), ("spine05", "neck01", 0.497),
    ("upperarm01.L", "lowerarm01.L", 0.028), ("upperarm01.R", "lowerarm01.R", 0.028),
    ("lowerarm01.L", "wrist.L", 0.016), ("lowerarm01.R", "wrist.R", 0.016),
    ("wrist.L", "finger3-1.L", 0.006), ("wrist.R", "finger3-1.R", 0.006),
    ("upperleg01.L", "lowerleg01.L", 0.100), ("upperleg01.R", "lowerleg01.R", 0.100),
    ("lowerleg01.L", "foot.L", 0.0465), ("lowerleg01.R", "foot.R", 0.0465),
    ("foot.L", "toe3-1.L", 0.0145), ("foot.R", "toe3-1.R", 0.0145),
]
BODY_KG = 75.0


def hits(tree, o, d):
    n = 0
    for _ in range(40):
        loc, nrm, idx, dist = tree.ray_cast(o, d)
        if loc is None:
            return n
        n += 1
        o = loc + d * 1e-4
    return n


def inside(tree, w):
    """Ray parity in two directions (robust in concave spots like between the thighs)."""
    return hits(tree, w, Vector((0.0, 0.0, 1.0))) % 2 == 1 and hits(tree, w, Vector((0.0, -1.0, 0.0))) % 2 == 1


def angle(a, b):
    return math.degrees(a.angle(b, 0.0))


def hull(pts):
    pts = sorted(set((round(p.x, 4), round(p.y, 4)) for p in pts))
    if len(pts) < 3:
        return pts
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def outside_dist(poly, q):
    """Signed distance of q outside a convex CCW polygon (negative = inside)."""
    if len(poly) < 3:
        return 1.0
    worst = -1e9
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        ex, ey = b[0] - a[0], b[1] - a[1]
        L = math.hypot(ex, ey) or 1e-9
        d = ((q[0] - a[0]) * ey - (q[1] - a[1]) * ex) / L     # > 0 = right of edge = outside
        worst = max(worst, d)
    return worst


for f in frames:
    scene.frame_set(f)
    bone_mats[f] = {pb.name: pb.matrix.copy() for pb in rig.pose.bones}
    co = body_verts()
    # floor + slide
    izmin = min(skin, key=lambda i: co[i].z)
    zmin = co[izmin].z
    if zmin < floor_min:
        floor_min = zmin
        g = max(body.data.vertices[izmin].groups, key=lambda g: g.weight if body.vertex_groups[g.group].name in rig.pose.bones else -1)
        stats["floor_at"] = (f, body.vertex_groups[g.group].name)
    cur = {i: co[i] for i in sole}
    if sole_prev is not None:
        for i in sole:
            a, b = sole_prev[i], cur[i]
            # a vertex rolling up off the floor (heel rise, toe-off) changes height;
            # a sliding one keeps it
            if a.z < 0.012 and b.z < 0.012 and abs(a.z - b.z) < 0.002:
                d = math.hypot(a.x - b.x, a.y - b.y)
                if d > slide_max:
                    slide_max = d
                    stats["slide_at"] = f
    sole_prev = cur
    # grips
    for name, o in props.items():
        mw = o.matrix_world
        c, ax = mw.translation, (mw.to_3x3() @ Vector((1, 0, 0))).normalized()
        if name.startswith("db_"):
            side = name[-1]
            g, _ = grip_point(P, side, o.get("grip_mode", "hook"))
            d = (g - c).length
            grip_max[name] = max(grip_max.get(name, 0.0), d)
        elif name in ("bar", "barbell", "pullup_bar") or name.startswith("dip_bar_"):
            for side in (("L", "R") if not name.startswith("dip_bar_") else (name[-1],)):
                d = 9.0
                for mode in ("hook", "press"):        # pulling or pressing grip
                    g, _ = grip_point(P, side, mode)
                    v = g - c
                    d = min(d, (v - v.project(ax)).length)
                grip_max[f"{name}.{side}"] = max(grip_max.get(f"{name}.{side}", 0.0), d)
        elif name == "db":
            for side in ("L", "R"):
                g, _ = grip_point(P, side)
                v = g - c
                d = (v - v.project(ax)).length
                grip_max[f"db.{side}"] = max(grip_max.get(f"db.{side}", 0.0), d)
    # Grip centres on the actual procedural attachments (root-local metadata).
    for o in scene.objects:
        if not o.get("contacts_json"): continue
        meta=json.loads(o["contacts_json"]);name=o.name
        targets=None
        if name.startswith("d_handle_"):
            targets={name[-1]:Vector(meta["grip"])}
        elif name in ("lat_bar","v_handle"):
            targets={"R":Vector(meta["grips"][0]),"L":Vector(meta["grips"][1])}
        elif name=="dip_station":
            targets={"R":Vector(meta["hands"][0]),"L":Vector(meta["hands"][1])}
        elif name=="kettlebell":
            targets={side:Vector((sgn*.065,0,0)) for side,sgn in (("L",1),("R",-1))}
        if targets:
            for side,local in targets.items():
                g,_=grip_point(P,side,"press" if name=="dip_station" else "hook")
                if name=="kettlebell":
                    local=o.matrix_world.inverted()@g;local.x=max(-.075,min(.075,local.x));local.y=0;local.z=0
                d=(g-o.matrix_world@local).length
                key=name+'.'+side;grip_max[key]=max(grip_max.get(key,0),d)
        if name in ("pushdown_rope","face_rope"):
            ends=[c for c in o.children if c.type=='CURVE']
            # Constructor creates R(-X) then L(+X); updater receives L then R.
            for side,curve in zip(("L","R"),ends):
                local=Vector(curve.data.splines[0].points[-1].co[:3]);g,_=grip_point(P,side)
                d=(g-curve.matrix_world@local).length
                key=name+'.'+side;grip_max[key]=max(grip_max.get(key,0),d)
    # Verify moving equipment transforms close at the loop seam, too.
    moving=[o for o in scene.objects if o.animation_data and o.type!='ARMATURE']
    if f==1: prop_loop_start={o.name:o.matrix_world.copy() for o in moving}
    if f==N:
        for o in moving:
            if o.name in prop_loop_start:
                m=prop_loop_start[o.name]
                prop_loop_mm=max(prop_loop_mm,(m.translation-o.matrix_world.translation).length*1000)
                prop_loop_deg=max(prop_loop_deg,math.degrees(m.to_quaternion().rotation_difference(o.matrix_world.to_quaternion()).angle))
    # Conservative hand/thigh spot check: a 45 mm inner thigh capsule catches
    # deep crossings without treating normal skin contact as collision.
    for side in ("L","R"):
        g,_=grip_point(P,side)
        for leg in ("L","R"):
            a=P.head("upperleg01."+leg);b=P.head("lowerleg01."+leg);ab=b-a
            t=max(.12,min(.9,(g-a).dot(ab)/ab.length_squared))
            penetration=.045-(g-(a+ab*t)).length
            self_pen_max=max(self_pen_max,penetration)
    # props inside the body (away from the hands)
    if "props" not in skip and props:
        tree = BVHTree.FromPolygons(co, skin_polys)
        hands = [P.head("wrist.L"), P.head("wrist.R"), grip_point(P, "L")[0], grip_point(P, "R")[0]]
        for name, meshes in prop_meshes.items():
            for m in meshes:
                for v in m.data.vertices:
                    w = m.matrix_world @ v.co
                    # fingers wrap the handle (and cup a two-hand dumbbell's plate)
                    if min((w - h).length for h in hands) < (0.15 if name == "db" else 0.11):
                        continue
                    loc, nrm, idx, dist = tree.find_nearest(w)
                    if loc is None or dist > 0.05 or dist <= pen_max:
                        continue
                    if inside(tree, w) and dist > pen_max:
                        pen_max = dist
                        stats["prop_pen_at"] = (f, m.name, [round(x, 3) for x in w], [round(x, 3) for x in loc])
    # joints
    def jv(key, val):
        if val > joint_viol.get(key, 0.0):
            joint_viol[key] = val
            joint_at[key] = f
    for side in ("L", "R"):
        hip, knee, ank = P.head(f"upperleg01.{side}"), P.head(f"lowerleg01.{side}"), P.head(f"foot.{side}")
        flex = angle(knee - hip, ank - knee)
        knee_range[side][0] = min(knee_range[side][0], flex)
        knee_range[side][1] = max(knee_range[side][1], flex)
        jv(f"knee_flex.{side}", flex - 155)
        toe = P.head(f"toe3-1.{side}") - ank
        bend = (knee - hip) - (knee - hip).project(ank - hip)
        # knees track the toes: the foot lies in the hip-knee-ankle plane, whatever the
        # body's orientation (standing, lunging, lying)
        n = (knee - hip).cross(ank - knee)
        if flex > 25 and n.length > 1e-6 and toe.length > 1e-6:
            dev = math.degrees(math.asin(min(1.0, abs(n.normalized().dot(toe.normalized())))))
            jv(f"knee_track.{side}", dev - 30)
        # hyperextension: the knee bends toward the back of the thigh's rest bend
        front = P.delta(f"upperleg01.{side}") @ P.rest_bend(f"upperleg01.{side}", f"lowerleg01.{side}", f"foot.{side}")
        if bend.length > 1e-4 and flex > 5 and bend.dot(front) < 0:
            jv(f"knee_hyper.{side}", flex - 5)
        sh, el, wr = P.head(f"upperarm01.{side}"), P.head(f"lowerarm01.{side}"), P.head(f"wrist.{side}")
        eflex = angle(el - sh, wr - el)
        elbow_range[side][0] = min(elbow_range[side][0], eflex)
        elbow_range[side][1] = max(elbow_range[side][1], eflex)
        jv(f"elbow_flex.{side}", eflex - 155)
        if "wrist_rotation_max" in qa_cfg:
            q = rig.pose.bones[f"wrist.{side}"].rotation_quaternion
            rotation = math.degrees(2 * math.acos(min(1.0, abs(q.w))))
            jv(f"wrist_rotation.{side}", rotation - qa_cfg["wrist_rotation_max"])
        hand = P.head(f"finger3-1.{side}") - wr
        jv(f"wrist.{side}", angle(wr - el, hand) - qa_cfg.get("wrist_max", 75))
    chest = P.axis("spine01", 1)
    jv("head", angle(chest, P.axis("head", 1)) - 50)
    # balance
    if "balance" not in skip:
        tot, acc = 0.0, Vector()
        for a, b, m in SEG:
            pa = P.head(a)
            pb_ = P.head(b) if b != a else P.tail(a)
            acc += (pa + pb_) / 2 * m
            tot += m
        com = acc / tot
        if load_kg is None:
            load_kg = {"bar": 0.0, "db": 12.0}
        load_sum=0.0;weighted=com*BODY_KG
        for name,o in props.items():
            if not (name=="barbell" or name=="kettlebell" or name=="db" or name.startswith("db_")):continue
            kg=load_kg.get(name,load_kg.get(name[:2],o.get("kg",8.0))) if isinstance(load_kg,dict) else load_kg/max(1,len(props))
            weighted+=o.matrix_world.translation*kg;load_sum+=kg
        com=weighted/(BODY_KG+load_sum)
        touching = [co[i] for i in sole if co[i].z < 0.015]
        feet = {s_: [p_ for p_ in touching if (p_.x > 0) == (s_ == "L")] for s_ in ("L", "R")}
        # a foot supports only with a real contact patch, not a toe tip on its way down
        pts = [p_ for s_ in feet for p_ in feet[s_] if len(feet[s_]) >= 10]
        for s_ in feet:
            if len(feet[s_]) < 10:
                last_air[s_] = f
        landing = any(f - last_air.get(s_, -99) <= 4 for s_ in feet)
        if not all(len(feet[s_]) >= 10 for s_ in feet) or landing:
            # single support while stepping is dynamic (the body falls into the step)
            stats["single_support_frames"] = stats.get("single_support_frames", 0) + 1
            continue
        poly = hull(pts)
        d = outside_dist(poly, (com.x, com.y)) + qa_cfg.get("balance_margin", 0.01)
        if os.environ.get("QA_DEBUG") and d > 0:
            print("  dbg frame", f, "com", round(com.x, 3), round(com.y, 3), "hull", poly)
        if d > com_out:
            com_out = d
            stats["balance_at"] = f

# --- verdicts ---------------------------------------------------------------
loop_t = max((bone_mats[1][n].translation - bone_mats[N][n].translation).length for n in bone_mats[1])
loop_r = max(math.degrees(bone_mats[1][n].to_quaternion().rotation_difference(bone_mats[N][n].to_quaternion()).angle)
             for n in bone_mats[1])
stats.update(prop_loop_mm=round(prop_loop_mm,3),prop_loop_deg=round(prop_loop_deg,3),hand_thigh_pen_mm=round(self_pen_max*1000,1),loop_mm=round(loop_t * 1000, 2), loop_deg=round(loop_r, 2), slide_mm=round(slide_max * 1000, 1),
             floor_mm=round(floor_min * 1000, 1), prop_pen_mm=round(pen_max * 1000, 1),
             grip_mm={k: round(v * 1000, 1) for k, v in grip_max.items()},
             joints={k: round(v, 1) for k, v in joint_viol.items() if v > 0},
             balance_out_mm=round(com_out * 1000, 1) if "balance" not in skip else None)
if "loop" not in skip and (loop_t > 0.001 or loop_r > 0.5):
    fail("loop", f"frame 1 vs {N}: {loop_t * 1000:.1f} mm / {loop_r:.2f} deg")
if "loop" not in skip and (prop_loop_mm>1 or prop_loop_deg>.5):
    fail("loop",f"equipment seam {prop_loop_mm:.1f} mm / {prop_loop_deg:.2f} deg")
if self_pen_max>.005:
    fail("self_intersection",f"hand crosses thigh inner capsule by {self_pen_max*1000:.1f} mm")
if "slide" not in skip and slide_max > 0.005:
    fail("slide", f"planted foot moved {slide_max * 1000:.1f} mm (frame {stats.get('slide_at')})")
if "floor" not in skip and floor_min < -0.01:
    fail("floor", f"body {floor_min * 1000:.0f} mm below the floor")
for k, v in grip_max.items():
    tol = 0.05 if k.startswith("db.") else 0.02 if k.startswith("db_") else 0.015
    if "grip" not in skip and v > tol:
        fail("grip", f"{k} hand {v * 1000:.0f} mm off the implement")
if "props" not in skip and pen_max > 0.005:
    fail("props", f"implement {pen_max * 1000:.0f} mm inside the body at {stats.get('prop_pen_at')}")
for k, v in joint_viol.items():
    if "joints" not in skip and v > 0.5 and k not in qa_cfg.get("allow", []):
        fail("joints", f"{k} over its limit by {v:.0f} deg (frame {joint_at.get(k)})")
if "balance" not in skip and com_out > 0:
    fail("balance", f"centre of mass {com_out * 1000:.0f} mm outside the feet (frame {stats.get('balance_at')})")

for joint, ranges in [('knee', knee_range), ('elbow', elbow_range)]:
    key = joint + '_flexion_range'
    stats[key] = {side: [round(v, 1) for v in values] for side, values in ranges.items()}
    if key in qa_cfg:
        for side, values in ranges.items():
            for index, name in enumerate(('min', 'max')):
                bounds = qa_cfg[key].get(side, qa_cfg[key])
                if name not in bounds: continue
                lo, hi = bounds[name]
                if not lo <= values[index] <= hi:
                    fail('range_of_motion', f'{joint} {side} {name} flexion {values[index]:.1f} deg outside {lo}..{hi}')

from core.delivery import spec_digest, pipeline_digest, digest
result = {"id": eid, "pass": not fails, "fails": fails, "stats": stats,
          "skipped": sorted(skip), "allowances": qa_cfg, "spec_sha256": spec_digest(eid) if os.path.exists(os.path.join(HERE,"catalog",eid+".json")) else None,
          "pipeline_sha256": pipeline_digest(), "blend_sha256": digest(os.path.join(HERE,"review",eid+".blend"))}
with open(os.path.join(HERE, "review", eid + "_qa.json"), "w") as fh:
    json.dump(result, fh, indent=1)
print(f"QA {eid}: {'PASS' if not fails else 'FAIL'}")
for x in fails:
    print("  -", x)
print("  stats:", json.dumps(stats))

if fails:
    sys.exit(1)
