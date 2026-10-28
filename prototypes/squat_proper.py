"""Bodyweight squat with enforced form on the MPFB body.

Feet stay planted (slightly wider than hips, toes out 15 deg), the hips follow a
back-and-down path to thighs-parallel, and a two-bone solver bends each knee
toward its own toes, so knees can't cave in or cross. Torso hinges to ~40 deg
with a neutral spine, chest up; arms rise forward as counterbalance.
Loop: 72 frames at 30 fps."""
import bpy, sys, math
import os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root
from mathutils import Vector
from common import (OUT, new_scene, make_human, Poser, rot_x, rot_z, muscle_material, studio,
                    camera, render_views, stitch_video, contact_sheet, update)

STANCE_X = 0.17       # ankle half-width (hip joints sit at ~0.108)
TOE_OUT = 15.0        # degrees
SHIN_LEAN = 32.0      # shin angle from vertical at the bottom (knees forward over toes)
TORSO = 40.0          # forward hinge at the bottom
N = 72

scene = new_scene()
body, rig = make_human()
P = Poser(rig)
up = Vector((0, 0, 1))

ankle_z = P.rest_head("foot.L").z
ankle_y = P.rest_head("foot.L").y
ankles = {"L": Vector((STANCE_X, ankle_y, ankle_z)), "R": Vector((-STANCE_X, ankle_y, ankle_z))}
toe = {"L": Vector((math.sin(math.radians(TOE_OUT)), -math.cos(math.radians(TOE_OUT)), 0)),
       "R": Vector((-math.sin(math.radians(TOE_OUT)), -math.cos(math.radians(TOE_OUT)), 0))}
la = (P.rest_head("lowerleg01.L") - P.rest_head("upperleg01.L")).length
lb = (P.rest_head("foot.L") - P.rest_head("lowerleg01.L")).length
hip_x = P.rest_head("upperleg01.L").x

# bottom: shin leaned along the toes, thigh parallel to the floor
knee_b = ankles["L"] + lb * (math.sin(math.radians(SHIN_LEAN)) * toe["L"] + math.cos(math.radians(SHIN_LEAN)) * up)
dx = hip_x - knee_b.x
hip_bot = Vector((0, knee_b.y + math.sqrt(la * la - dx * dx), knee_b.z + 0.03))
# top: legs almost straight, hips over mid-foot
reach = 0.985 * (la + lb)
dx_t = hip_x - STANCE_X
hip_top = Vector((0, ankle_y + 0.01, ankle_z + math.sqrt(reach ** 2 - dx_t ** 2 - 0.01 ** 2)))
print("HIP top", tuple(round(v, 3) for v in hip_top), "bottom", tuple(round(v, 3) for v in hip_bot))


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def depth(f):
    """0 = standing, 1 = bottom. 1-6 hold, 7-37 down, 38-44 pause, 45-68 up, 69-72 hold."""
    if f <= 6:
        return 0.0
    if f <= 37:
        return smooth((f - 6) / 31)
    if f <= 44:
        return 1.0
    if f <= 68:
        return 1.0 - smooth((f - 44) / 24)
    return 0.0


def pose(s):
    P.reset()
    # pelvis hinge, then place the hips on the path
    tilt = 3 + (TORSO - 3) * s
    root_rest = P.rest_head("root")
    P.set_world("root", rot_x(tilt) @ P.rest3("root"), root_rest)
    mid = (P.head("upperleg01.L") + P.head("upperleg01.R")) / 2
    back = 1 - (1 - s) ** 1.6          # hips travel back early, like a hip hinge
    target = Vector((0, hip_top.y + (hip_bot.y - hip_top.y) * back, hip_top.z + (hip_bot.z - hip_top.z) * s))
    P.set_world("root", rot_x(tilt) @ P.rest3("root"), root_rest + (target - mid))
    # neutral spine, chest up, eyes forward
    P.local("spine02", (1, 0, 0), -4 * s)
    P.local("spine01", (1, 0, 0), -5 * s)
    P.local("neck02", (1, 0, 0), -12 * s)
    P.local("head", (1, 0, 0), -14 * s)
    for side, sgn in (("L", 1), ("R", -1)):
        P.limb(f"upperleg01.{side}", f"lowerleg01.{side}", f"foot.{side}", ankles[side], toe[side])
        P.set_world(f"foot.{side}", rot_z(sgn * TOE_OUT) @ P.rest3(f"foot.{side}"))
        # arms: from hanging to shoulder height, palms down, straight
        e = math.radians(12 + 76 * s)
        sh = P.head(f"upperarm01.{side}")
        d = Vector((sgn * 0.12, -math.sin(e), -math.cos(e))).normalized()
        ua = (P.rest_head(f"lowerarm01.{side}") - P.rest_head(f"upperarm01.{side}")).length
        fa = (P.rest_head(f"wrist.{side}") - P.rest_head(f"lowerarm01.{side}")).length
        P.limb(f"upperarm01.{side}", f"lowerarm01.{side}", f"wrist.{side}", sh + d * 0.985 * (ua + fa),
               Vector((sgn, 0.3, -0.4)), palm=Vector((0, 0.15, -1)), side=side)


def key_all(f):
    for pb in rig.pose.bones:
        pb.keyframe_insert("rotation_quaternion", frame=f)
        pb.keyframe_insert("location", frame=f)


for f in range(1, N + 1):
    pose(depth(f))
    key_all(f)
print("KEYED", N)

# look: squat targets (free-exercise-db + standard coaching)
body.data.materials.clear()
body.data.materials.append(muscle_material(primary=("quadriceps", "glutes"),
                                           secondary=("adductors", "hamstrings", "calves", "lower back")))
studio(scene)
tgt = (0, 0.05, 0.85)
cams = [camera(scene, "front", tgt, 0, ortho=2.15), camera(scene, "side", tgt, 90, ortho=2.15),
        camera(scene, "threeq", tgt, 35, ortho=2.15), camera(scene, "back", tgt, 180, ortho=2.15)]
import os
dirs = render_views(scene, cams[:3], "squat", 1, N)
if not os.environ.get("QUICK"):
    stitch_video(dirs, OUT + "squat_proper.mp4")
contact_sheet(dirs, [1, 20, 30, 40, 56], OUT + "squat_proper_sheet.png")
scene.frame_set(40); scene.camera = cams[3]
scene.render.filepath = OUT + "squat_back_bottom.png"
bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT + "squat_proper.blend")
