"""Equipment test: triceps pushdown on the cable tower, or dumbbell curl.
Usage: blender -b --python prototypes/arm_exercises.py -- pushdown|curl

Form rules baked into the solver: feet planted, elbows pinned at the sides
(upper arm fixed), only the forearm travels, wrists neutral. Pushdown uses an
overhand grip and a slight forward lean; curl uses an underhand grip, torso
upright. Equipment is placed from the posed hands on every frame."""
import bpy, sys, math
import os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root
from mathutils import Vector, Matrix, Quaternion
from common import (OUT, new_scene, make_human, Poser, rot_x, rot_z, muscle_material, studio,
                    camera, render_views, stitch_video, contact_sheet, update)
import equipment as eq

MODE = sys.argv[-1] if sys.argv[-1] in ("pushdown", "curl") else "pushdown"
N = 72
CFG = {
    "pushdown": dict(tilt=12, hip_back=0.035, knee_reach=0.965, ua_dir=(0.03, -0.16, -1), grip_x=0.115,
                     phi=(98, 4), grip="over", primary=("triceps",), secondary=()),
    "curl": dict(tilt=1, hip_back=0.0, knee_reach=0.985, ua_dir=(0.06, -0.06, -1), grip_x=None,
                 phi=(6, 138), grip="under", primary=("biceps",), secondary=("forearms",)),
}[MODE]

scene = new_scene()
body, rig = make_human()
P = Poser(rig)
up = Vector((0, 0, 1))
ankle_z, ankle_y = P.rest_head("foot.L").z, P.rest_head("foot.L").y
ankles = {"L": Vector((0.13, ankle_y, ankle_z)), "R": Vector((-0.13, ankle_y, ankle_z))}
toe = {"L": Vector((math.sin(math.radians(8)), -math.cos(math.radians(8)), 0)),
       "R": Vector((-math.sin(math.radians(8)), -math.cos(math.radians(8)), 0))}
la = (P.rest_head("lowerleg01.L") - P.rest_head("upperleg01.L")).length
lb = (P.rest_head("foot.L") - P.rest_head("lowerleg01.L")).length
hip_x = P.rest_head("upperleg01.L").x
reach = CFG["knee_reach"] * (la + lb)
dx = hip_x - 0.13
hip_mid = Vector((0, ankle_y + CFG["hip_back"],
                  ankle_z + math.sqrt(reach ** 2 - dx ** 2 - CFG["hip_back"] ** 2)))


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def phase(f):
    """0 = start position, 1 = end of the concentric. 1-6 hold, 7-30 work,
    31-36 squeeze, 37-66 slower return, 67-72 hold."""
    if f <= 6:
        return 0.0
    if f <= 30:
        return smooth((f - 6) / 24)
    if f <= 36:
        return 1.0
    if f <= 66:
        return 1.0 - smooth((f - 36) / 30)
    return 0.0


def grip_point(side):
    """Where a handle sits in the closed hand: across the palm at the knuckle line."""
    k2, k5 = P.head(f"finger2-1.{side}"), P.head(f"finger5-1.{side}")
    w = P.head(f"wrist.{side}")
    k3 = P.head(f"finger3-1.{side}")
    n = P.palm_now(side)
    f = (k3 - w).normalized()
    return (k2 + k5) / 2 + n * 0.024 + f * 0.012, (k5 - k2).normalized()


def pose(s):
    P.reset()
    tilt = CFG["tilt"]
    root_rest = P.rest_head("root")
    P.set_world("root", rot_x(tilt) @ P.rest3("root"), root_rest)
    mid = (P.head("upperleg01.L") + P.head("upperleg01.R")) / 2
    P.set_world("root", rot_x(tilt) @ P.rest3("root"), root_rest + (hip_mid - mid))
    P.local("neck02", (1, 0, 0), -tilt * 0.5)
    P.local("head", (1, 0, 0), -tilt * 0.4)
    phi0, phi1 = CFG["phi"]
    phi = phi0 + (phi1 - phi0) * s
    for side, sgn in (("L", 1), ("R", -1)):
        P.limb(f"upperleg01.{side}", f"lowerleg01.{side}", f"foot.{side}", ankles[side], toe[side])
        P.set_world(f"foot.{side}", rot_z(sgn * 8) @ P.rest3(f"foot.{side}"))
        sh = P.head(f"upperarm01.{side}")
        ua = (P.rest_head(f"lowerarm01.{side}") - P.rest_head(f"upperarm01.{side}")).length
        fa = (P.rest_head(f"wrist.{side}") - P.rest_head(f"lowerarm01.{side}")).length
        x, y, z = CFG["ua_dir"]
        d_ua = Vector((sgn * x, y, z)).normalized()
        elbow = sh + d_ua * ua
        f_dir = rot_x(-phi) @ d_ua          # forearm swings forward/up in the sagittal plane
        wrist = elbow + f_dir * fa
        if CFG["grip_x"] is not None:
            wrist.x = sgn * CFG["grip_x"]
            wrist = elbow + (wrist - elbow).normalized() * fa
        palm = (rot_x(90) if CFG["grip"] == "over" else rot_x(-90)) @ (wrist - elbow).normalized()
        # bend hint = the planned elbow itself, so the solver can't let it drift
        pole = (elbow - sh) - (elbow - sh).project(wrist - sh)
        P.limb(f"upperarm01.{side}", f"lowerarm01.{side}", f"wrist.{side}", wrist,
               pole, palm=palm, side=side)
        P.curl_fingers(side)


# --- equipment ------------------------------------------------------------
if MODE == "pushdown":
    tower = eq.CableTower()
    bar = eq.straight_bar()
    bar.rotation_mode = "QUATERNION"
else:
    bells = {"L": eq.dumbbell("db_L"), "R": eq.dumbbell("db_R")}
    for b in bells.values():
        b.rotation_mode = "QUATERNION"


def key_all(f):
    for pb in rig.pose.bones:
        pb.keyframe_insert("rotation_quaternion", frame=f)
        pb.keyframe_insert("location", frame=f)


attach = {}
for f in range(1, N + 1):
    pose(phase(f))
    key_all(f)
    gL, wL = grip_point("L")
    gR, wR = grip_point("R")
    if MODE == "pushdown":
        c = (gL + gR) / 2
        to_pulley = (tower.front_c - c)
        a = math.atan2(-to_pulley.y, to_pulley.z)
        bar.location = c
        bar.rotation_quaternion = Quaternion((1, 0, 0), a)
        bar.keyframe_insert("location", frame=f)
        bar.keyframe_insert("rotation_quaternion", frame=f)
        attach[f] = c + bar.rotation_quaternion @ Vector((0, 0, 0.068))
    else:
        for side, g, w in (("L", gL, wL), ("R", gR, wR)):
            b = bells[side]
            # handle (local X) runs across the palm; the dumbbell is round about X
            x = w
            z = (P.palm_now(side) - P.palm_now(side).project(x)).normalized()
            b.location = g
            b.rotation_quaternion = Matrix((x, z.cross(x), z)).transposed().to_quaternion()
            b.keyframe_insert("location", frame=f)
            b.keyframe_insert("rotation_quaternion", frame=f)
print("POSED", N)

if MODE == "pushdown":
    shortest = min(attach.values(), key=lambda p: (p - tower.front_c).length)
    tower.calibrate(shortest)
    lifts = [tower.update(attach[f], f) for f in range(1, N + 1)]
    print("STACK LIFT max", round(max(lifts), 3), "m")

body.data.materials.clear()
body.data.materials.append(muscle_material(primary=CFG["primary"], secondary=CFG["secondary"]))
studio(scene)
if MODE == "pushdown":
    tgt = (0, -0.3, 1.1)
    cams = [camera(scene, "side", tgt, 90, ortho=2.6), camera(scene, "rear", tgt, 150, ortho=2.6),
            camera(scene, "front", tgt, 35, ortho=2.6)]
else:
    tgt = (0, 0, 1.0)
    cams = [camera(scene, "front", tgt, 25, ortho=2.1), camera(scene, "side", tgt, 90, ortho=2.1)]
import os
dirs = render_views(scene, cams, MODE, 1, N)
if not os.environ.get("QUICK"):
    stitch_video(dirs, OUT + f"{MODE}.mp4")
contact_sheet(dirs, [1, 15, 33, 50, 66], OUT + f"{MODE}_sheet.png")
bpy.ops.wm.save_as_mainfile(filepath=OUT + f"{MODE}.blend")
