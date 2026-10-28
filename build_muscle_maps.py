"""Bake Z-Anatomy's real muscle outlines onto the MPFB body's UVs.

1. Append Z-Anatomy's muscles + bones next to an MPFB body in rest pose.
2. Fit each Z-Anatomy body segment (thigh, shin, upper arm, ...) onto the MPFB
   joints with a per-segment rotate + stretch, so the two bodies overlap.
3. Cycles "selected to active" bakes: each muscle group's emission -> one
   channel of mask_<n>.png (3 groups per image), plus a tangent normal map.

Output: assets/maps/mask_0..5.png, muscle_normal.png, fit_check renders."""
import bpy, sys, os, math
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # repo root
from mathutils import Vector, Matrix
from common import (ROOT, MAPS, OUT, GROUPS, mask_slot, new_scene, use_gpu, make_human,
                    frame_align, update)

ZA = ROOT + "assets/za/Z-Anatomy/Startup.blend"
RES = 2048
os.makedirs(MAPS, exist_ok=True)

scene = new_scene()
body, rig = make_human()
mw = rig.matrix_world

# --- append Z-Anatomy ---------------------------------------------------
with bpy.data.libraries.load(ZA, link=False) as (src, dst):
    dst.collections = [c for c in src.collections if c in ("4: Muscular system", "1: Skeletal system")]
for c in dst.collections:
    scene.collection.children.link(c)
update()  # appended objects get their world matrices only after an update
musc_col = bpy.data.collections["4: Muscular system"]
bone_col = bpy.data.collections["1: Skeletal system"]

SKIP = ("fascia", "septum", "bursa", "sheath", "retinacul", "tract")


def wanted(o):
    n = o.name.lower()
    return (o.type == "MESH" and ("." not in n or n.rsplit(".", 1)[-1] in ("l", "r"))
            and not any(k in n.replace("fasciae latae", "") for k in SKIP))


muscles = [o for o in musc_col.all_objects if wanted(o)]
bones = [o for o in bone_col.all_objects if wanted(o)]
print("ZA objects", len(muscles), "muscles", len(bones), "bones")


def verts(o):
    m = o.matrix_world
    return [m @ v.co for v in o.data.vertices]


def centroid(pts):
    s = Vector((0, 0, 0))
    for p in pts:
        s += p
    return s / len(pts)


def ob(name):
    return bpy.data.objects[name]


# --- Z-Anatomy joint landmarks (from the bone meshes) --------------------
def za_landmarks(side):
    sx = 1 if side == "l" else -1
    fem = verts(ob(f"Femur.{side}"))
    zmax = max(p.z for p in fem)
    top = [p for p in fem if p.z > zmax - 0.05]
    xmed = sorted(abs(p.x) for p in top)[len(top) // 3]
    hip = centroid([p for p in top if abs(p.x) <= xmed])  # femoral head is the medial part
    zmin = min(p.z for p in fem)
    knee = centroid([p for p in fem if p.z < zmin + 0.03])
    ankle = centroid(verts(ob(f"Talus.{side}")))
    hum = verts(ob(f"Humerus.{side}"))
    hz = max(p.z for p in hum)
    htop = [p for p in hum if p.z > hz - 0.045]
    hmed = sorted(abs(p.x) for p in htop)[len(htop) // 2]
    shoulder = centroid([p for p in htop if abs(p.x) <= hmed])
    hzmin = min(p.z for p in hum)
    elbow = centroid([p for p in hum if p.z < hzmin + 0.03])
    wrist = centroid(verts(ob(f"Lunate bone.{side}")))
    radius = centroid(verts(ob(f"Radius.{side}")))
    ulna = centroid(verts(ob(f"Ulna.{side}")))
    clav = verts(ob(f"Clavicle.{side}"))
    cmin = min(abs(p.x) for p in clav)
    notch = centroid([p for p in clav if abs(p.x) < cmin + 0.02])
    return dict(hip=hip, knee=knee, ankle=ankle, shoulder=shoulder, elbow=elbow, wrist=wrist,
                thumbside=radius - ulna, notch=notch)


def mp_landmarks(side):
    s = "L" if side == "l" else "R"
    h = lambda n: mw @ rig.data.bones[n].head_local
    return dict(hip=h(f"upperleg01.{s}"), knee=h(f"lowerleg01.{s}"), ankle=h(f"foot.{s}"),
                shoulder=h(f"upperarm01.{s}"), elbow=h(f"lowerarm01.{s}"), wrist=h(f"wrist.{s}"),
                thumbside=h(f"finger1-1.{s}") - h(f"metacarpal4.{s}"), notch=h(f"clavicle.{s}"))


za = {s: za_landmarks(s) for s in "lr"}
mp = {s: mp_landmarks(s) for s in "lr"}
za_top = max(p.z for o in muscles for p in verts(o)) if False else max(
    (o.matrix_world @ Vector(c)).z for o in muscles for c in o.bound_box)
mp_top = max((body.matrix_world @ v.co).z for v in body.data.vertices)
for k in ("hip", "knee", "ankle", "shoulder", "elbow", "wrist"):
    print(f"LANDMARK {k:9s} ZA {tuple(round(x, 3) for x in za['l'][k])}  MPFB {tuple(round(x, 3) for x in mp['l'][k])}")


def seg_matrix(p0, p1, q0, q1, ref_p, ref_q, perp=1.0):
    """Affine map: ZA segment p0->p1 onto MPFB q0->q1 (rotate + stretch along axis)."""
    u = (p1 - p0).normalized()
    k = (q1 - q0).length / (p1 - p0).length
    r = frame_align(p1 - p0, ref_p, q1 - q0, ref_q).to_4x4()
    uu = Matrix(((u.x * u.x, u.x * u.y, u.x * u.z), (u.y * u.x, u.y * u.y, u.y * u.z),
                 (u.z * u.x, u.z * u.y, u.z * u.z)))
    s = Matrix.Identity(3) * perp + uu * (k - perp)
    return Matrix.Translation(q0) @ r @ s.to_4x4() @ Matrix.Translation(-p0)


fwd = Vector((0, -1, 0))
segs = {}
for s in "lr":
    Z, M = za[s], mp[s]
    segs["thigh." + s] = (Z["hip"], Z["knee"], seg_matrix(Z["hip"], Z["knee"], M["hip"], M["knee"], fwd, fwd))
    segs["shin." + s] = (Z["knee"], Z["ankle"], seg_matrix(Z["knee"], Z["ankle"], M["knee"], M["ankle"], fwd, fwd))
    segs["uarm." + s] = (Z["shoulder"], Z["elbow"], seg_matrix(Z["shoulder"], Z["elbow"], M["shoulder"], M["elbow"],
                                                              Z["thumbside"], M["thumbside"]))
    segs["farm." + s] = (Z["elbow"], Z["wrist"], seg_matrix(Z["elbow"], Z["wrist"], M["elbow"], M["wrist"],
                                                           Z["thumbside"], M["thumbside"]))
    # foot: carry rigidly with the ankle
    segs["foot." + s] = (Z["ankle"], Z["ankle"] + Vector((0, -0.1, -0.04)),
                         Matrix.Translation(M["ankle"] - Z["ankle"]))
zh = (za["l"]["hip"] + za["r"]["hip"]) / 2
mh = (mp["l"]["hip"] + mp["r"]["hip"]) / 2
zn = (za["l"]["notch"] + za["r"]["notch"]) / 2
mn = (mp["l"]["notch"] + mp["r"]["notch"]) / 2
width = (mp["l"]["shoulder"] - mp["r"]["shoulder"]).length / (za["l"]["shoulder"] - za["r"]["shoulder"]).length
segs["torso"] = (zh, zn, seg_matrix(zh, zn, mh, mn, fwd, fwd, perp=width))
ztop = Vector((0, zn.y, za_top)); mtop = Vector((0, mn.y, mp_top))
segs["head"] = (zn, ztop, seg_matrix(zn, ztop, mn, mtop, fwd, fwd))
print("torso width scale", round(width, 3))


def dist_to_seg(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
    return (p - (a + ab * t)).length


TRUNK = ("trapezius", "latissimus", "rhomboid", "serratus", "pectoralis", "rectus abdominis",
         "abdominal oblique", "iliocostalis", "longissimus", "spinalis", "multifidus", "teres major",
         "infraspinatus", "teres minor", "levator scapulae", "quadratus lumborum")
assign = {}
for o in muscles + bones:
    c = centroid([o.matrix_world @ Vector(v) for v in o.bound_box])
    best = min(segs, key=lambda k: dist_to_seg(c, segs[k][0], segs[k][1]))
    # broad trunk muscles have off-centre centroids that sit nearer the arm line;
    # they belong to the torso, or the arm fit flings them out with the A-pose
    if any(k in o.name.lower() for k in TRUNK):
        best = "torso"
    # hands follow the forearm, feet the foot
    if best.startswith("farm") and c.z < segs[best][1].z - 0.02:
        best = best
    assign[o] = (best, c)
world = {o: o.matrix_world.copy() for o in assign}
for o, (seg, c) in assign.items():
    o.parent = None  # drop the atlas' label parents; world transform restored below
    o.matrix_world = segs[seg][2] @ world[o]
update()

# Z-Anatomy's torso is deeper front-to-back than MPFB's: its back muscles sat
# 4-7 cm behind the skin, out of the bake's reach. Refit torso depth (Y) so
# the muscle surface lands just inside the measured skin, front and back.
dg = bpy.context.evaluated_depsgraph_get()
bm_eval = body.evaluated_get(dg).to_mesh()
skin = [body.matrix_world @ v.co for v in bm_eval.vertices]
torso_objs = [o for o, (seg, c) in assign.items() if seg == "torso" and o in muscles]
fits = []
for z0 in (1.05, 1.15, 1.25, 1.35):
    slab = lambda pts: [p.y for p in pts if abs(p.z - z0) < 0.02 and abs(p.x) < 0.09]
    sk = slab(skin)
    zv = slab([p for o in torso_objs for p in verts(o)])
    if sk and zv:
        fits.append((min(zv), max(zv), min(sk) + 0.006, max(sk) - 0.006))
zf, zb, mf, mb = [sum(f[i] for f in fits) / len(fits) for i in range(4)]
a = (mb - mf) / (zb - zf)
ymap = Matrix(((1, 0, 0, 0), (0, a, 0, mf - a * zf), (0, 0, 1, 0), (0, 0, 0, 1)))
print("TORSO DEPTH ZA", round(zf, 3), round(zb, 3), "-> skin", round(mf, 3), round(mb, 3), "scale", round(a, 3))
for o, (seg, c) in assign.items():
    if seg in ("torso", "head"):
        o.matrix_world = ymap @ o.matrix_world
update()


# --- groups --------------------------------------------------------------
def group_of(o, c):
    n = o.name.lower()
    if o in bones:
        return None
    rules = [
        ("quadriceps", ("rectus femoris", "vastus")),
        ("hamstrings", ("biceps femoris", "semitendinosus", "semimembranosus")),
        ("glutes", ("gluteus maximus", "gluteus medius", "gluteus minimus")),
        ("adductors", ("adductor longus", "adductor brevis", "adductor magnus", "gracilis", "pectineus")),
        ("abductors", ("tensor fasciae latae",)),
        ("calves", ("gastrocnemius", "soleus", "plantaris")),
        ("abdominals", ("rectus abdominis", "abdominal oblique", "transversus abdominis", "pyramidalis")),
        ("lower back", ("iliocostalis", "longissimus", "spinalis", "multifidus", "quadratus lumborum",
                        "erector spinae")),
        ("middle back", ("rhomboid", "teres major", "teres minor", "infraspinatus")),
        ("lats", ("latissimus dorsi",)),
        ("traps", ("trapezius",)),
        ("shoulders", ("deltoid", "supraspinatus")),
        ("chest", ("pectoralis major", "pectoralis minor", "serratus anterior")),
        ("biceps", ("biceps brachii", "brachialis")),
        ("triceps", ("triceps brachii", "anconeus")),
        ("neck", ("sternocleidomastoid", "scalene", "splenius")),
    ]
    for g, keys in rules:
        if any(k in n for k in keys):
            if g == "biceps" and "femoris" in n:
                continue
            return g
    if any(k in n for k in ("flexor", "extensor", "pronator", "supinator", "palmaris", "brachioradialis")):
        if assign[o][0].startswith("farm") or assign[o][0].startswith("uarm"):
            return "forearms"
    return None


groups = {o: group_of(o, assign[o][1]) for o in muscles + bones}
from collections import Counter
print("GROUP COUNTS", Counter(g for g in groups.values()))

# --- bake ----------------------------------------------------------------
scene.render.engine = "CYCLES"
use_gpu(scene)
scene.cycles.samples = 1
bk = scene.render.bake
bk.use_selected_to_active = True
bk.cage_extrusion = 0.06
bk.max_ray_distance = 0.14
bk.margin = 12

emit = {}


def emission(rgb):
    key = tuple(rgb)
    if key not in emit:
        m = bpy.data.materials.new(f"emit_{key}")
        m.use_nodes = True
        nt = m.node_tree
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        e = nt.nodes.new("ShaderNodeEmission"); e.inputs["Color"].default_value = (*rgb, 1)
        e.inputs["Strength"].default_value = 1.0
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(e.outputs[0], out.inputs[0])
        emit[key] = m
    return emit[key]


def paint(o, m):
    o.data.materials.clear()
    o.data.materials.append(m)


# Cycles' selected-to-active bake casts every pixel against each source object
# separately, so ~770 objects took 10 min per map. Join them: one mesh per group
# plus one for everything else (unassigned muscles + bones, which block rays).
bpy.ops.object.select_all(action="DESELECT")
by_group = {}
for o in muscles + bones:
    by_group.setdefault(groups[o] or "_other", []).append(o)
joined = {}
for g, objs in by_group.items():
    for o in objs:
        o.hide_set(False); o.hide_viewport = False
        if o.data.users > 1:
            o.data = o.data.copy()
        o.data.materials.clear()
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    joined[g] = bpy.context.view_layer.objects.active
    joined[g].name = "ZA_" + g
print("JOINED", {g: len(o.data.vertices) for g, o in joined.items()})

bake_mat = bpy.data.materials.new("bake_target"); bake_mat.use_nodes = True
img_node = bake_mat.node_tree.nodes.new("ShaderNodeTexImage")
body.data.materials.clear(); body.data.materials.append(bake_mat)

bpy.ops.object.select_all(action="DESELECT")
src_objs = list(joined.values())
for o in src_objs:
    o.select_set(True)
body.hide_set(False)
body.select_set(True)
bpy.context.view_layer.objects.active = body


def bake_to(name, btype, colorspace="sRGB"):
    img = bpy.data.images.new(name, RES, RES, alpha=False, float_buffer=False)
    img.colorspace_settings.name = colorspace
    img_node.image = img
    bake_mat.node_tree.nodes.active = img_node
    img_node.select = True
    if btype == "NORMAL":
        bk.normal_space = "TANGENT"
    bpy.ops.object.bake(type=btype)
    img.filepath_raw = MAPS + name + ".png"
    img.file_format = "PNG"
    img.save()
    print("BAKED", name)


n_imgs = math.ceil(len(GROUPS) / 3)
for i in range(n_imgs):
    for g, o in joined.items():
        g = None if g == "_other" else g
        rgb = [0.0, 0.0, 0.0]
        if g is not None:
            gi, ch = mask_slot(g)
            if gi == i:
                rgb[ch] = 1.0
        paint(o, emission(rgb))
    bake_to(f"mask_{i}", "EMIT", "Non-Color")

bake_to("muscle_normal", "NORMAL", "Non-Color")
bpy.ops.wm.save_as_mainfile(filepath=ROOT + "review/muscle_fit.blend")
print("DONE")
