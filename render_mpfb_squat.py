"""Review stills: an MPFB2 (CC0) body driven by the CMU squat mocap (13_29),
with a crude rig-weight highlight on the thighs. Stills only, no video.
Run with BLENDER_USER_RESOURCES=<repo>/.blender-profile so MPFB is found."""
import bpy, math, sys, mathutils
from mathutils import Vector, Matrix

ROOT = "/Users/oktayshakirov/Coding/fitness-automation/"
BVH = ROOT + "assets/mocap/13_29.bvh"
OUT = ROOT + "review/"
SQUAT_RANGE = (3780, 4100)  # first clean rep (31.5 s .. 34 s at 120 fps)

from bl_ext.user_default.mpfb.services.humanservice import HumanService
from bl_ext.user_default.mpfb.services.targetservice import TargetService

# start from an empty scene
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

macro = TargetService.get_default_macro_info_dict()
macro["gender"] = 1.0
macro["muscle"] = 0.8
macro["weight"] = 0.45
body = HumanService.create_human(macro_detail_dict=macro)
rig = HumanService.add_builtin_rig(body, "cmu_mb")
bpy.context.view_layer.update()

# --- mocap -------------------------------------------------------------
bpy.ops.import_anim.bvh(filepath=BVH, global_scale=1.0, axis_forward='-Z', axis_up='Y',
                        update_scene_fps=False, update_scene_duration=True)
src = bpy.context.active_object
act = src.animation_data.action


def hips_fcurve(i):
    for fc in getattr(act, "fcurves", []):
        if fc.data_path == 'pose.bones["Hips"].location' and fc.array_index == i:
            return fc
    # Blender 5 layered actions
    for layer in act.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for fc in bag.fcurves:
                    if fc.data_path == 'pose.bones["Hips"].location' and fc.array_index == i:
                        return fc


def src_hips_world(frame):
    scene.frame_set(frame)
    return src.matrix_world @ src.pose.bones["Hips"].head


# scale the mocap skeleton so standing hip height matches the MPFB body
mpfb_hips = (rig.matrix_world @ rig.data.bones["Hips"].head_local).z
stand = src_hips_world(SQUAT_RANGE[0]).z
s = mpfb_hips / stand
src.scale = (s, s, s)
bpy.context.view_layer.update()

# turn the mocap to face the same way as the body: compare the hip axes
def hip_axis_src():
    scene.frame_set(SQUAT_RANGE[0])
    mw = src.matrix_world
    return (mw @ src.pose.bones["LeftUpLeg"].head - mw @ src.pose.bones["RightUpLeg"].head).xy


va = hip_axis_src()
vb = (rig.matrix_world @ rig.data.bones["LeftUpLeg"].head_local
      - rig.matrix_world @ rig.data.bones["RightUpLeg"].head_local).xy
turn = math.atan2(vb.y, vb.x) - math.atan2(va.y, va.x)
src.rotation_euler.z += turn
bpy.context.view_layer.update()
print("TURN deg", round(math.degrees(turn), 1))

# park the mocap root over the MPFB hips (x/y only) so the camera framing holds
off = src_hips_world(SQUAT_RANGE[0]) - (rig.matrix_world @ rig.data.bones["Hips"].head_local)
src.location.x -= off.x
src.location.y -= off.y
bpy.context.view_layer.update()

zs = {f: src_hips_world(f).z for f in range(SQUAT_RANGE[0], SQUAT_RANGE[1], 4)}
bottom = min(zs, key=zs.get)
top = max((f for f in zs if f < bottom), key=zs.get)
mid = min((f for f in zs if top < f < bottom), key=lambda f: abs(zs[f] - (zs[top] + zs[bottom]) / 2))
print("FRAMES top/mid/bottom", top, mid, bottom, [round(zs[f], 2) for f in (top, mid, bottom)])

# --- retarget -----------------------------------------------------------
# Most bones copy their world rotation change from rest (CMU's spine, neck and
# hip-joint bones have zero-length offsets, so they can't be aimed). The arms
# rest differently (MPFB A-pose vs CMU T-pose), so they aim along their twin
# with Damped Track instead; that drops twist, which a squat barely uses.
AIMED = {"LeftArm", "LeftForeArm", "LeftHand", "RightArm", "RightForeArm", "RightHand"}
for pb in rig.pose.bones:
    if pb.name in AIMED:
        c = pb.constraints.new('DAMPED_TRACK')
        c.target, c.subtarget, c.head_tail = src, pb.name, 1.0
hips_loc = rig.pose.bones["Hips"].constraints.new('COPY_LOCATION')
hips_loc.target, hips_loc.subtarget = src, "Hips"

src_rest = {b.name: (src.matrix_world @ b.matrix_local).to_quaternion() for b in src.data.bones}
dst_rest = {b.name: (rig.matrix_world @ b.matrix_local).to_quaternion() for b in rig.data.bones}
rig_rot_inv = rig.matrix_world.to_quaternion().inverted()
DELTA = [pb for pb in rig.pose.bones if pb.name in src.pose.bones and pb.name not in AIMED]


def pose_frame(frame):
    scene.frame_set(frame)
    for pb in DELTA:  # pose.bones is parent-first, so parents settle before children
        cur = (src.matrix_world @ src.pose.bones[pb.name].matrix).to_quaternion()
        world = cur @ src_rest[pb.name].inverted() @ dst_rest[pb.name]
        m = (rig_rot_inv @ world).to_matrix().to_4x4()
        m.translation = pb.matrix.translation
        pb.matrix = m
        bpy.context.view_layer.update()


# --- look -------------------------------------------------------------
def mat(name, color, emit=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1); b.inputs["Roughness"].default_value = 0.5
    return m, b


# thigh highlight from the rig's own skin weights: a stand-in for real muscle masks
mesh = body.data
attr = mesh.color_attributes.new("hot", 'FLOAT_COLOR', 'POINT')
gi = {g.name: g.index for g in body.vertex_groups}
want = {gi[n] for n in ("LeftUpLeg", "RightUpLeg") if n in gi}
for v in mesh.vertices:
    w = sum(g.weight for g in v.groups if g.group in want)
    w = min(1.0, w) ** 0.7
    attr.data[v.index].color = (w, w, w, 1)

m, bsdf = mat("body", (0.6, 0.62, 0.66))
nt = m.node_tree
ca = nt.nodes.new("ShaderNodeVertexColor"); ca.layer_name = "hot"
mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = 'RGBA'
mix.inputs["A"].default_value = (0.6, 0.62, 0.66, 1)
mix.inputs["B"].default_value = (0.85, 0.05, 0.02, 1)
nt.links.new(ca.outputs["Color"], mix.inputs["Factor"])
nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
body.data.materials.clear(); body.data.materials.append(m)
for o in body.children:
    if o.type == 'MESH':
        o.hide_render = True  # proxies / helpers

src.hide_render = True

for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try:
        scene.render.engine = eng; break
    except TypeError:
        pass
scene.render.resolution_x, scene.render.resolution_y = 1080, 1920
scene.render.resolution_percentage = 50
scene.view_settings.view_transform = 'AgX'
world = bpy.data.worlds.new("W"); scene.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.035, 0.04, 0.05, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.7
sun = bpy.data.objects.new("key", bpy.data.lights.new("key", 'SUN')); sun.data.energy = 3.5
scene.collection.objects.link(sun)
rim = bpy.data.objects.new("rim", bpy.data.lights.new("rim", 'SUN')); rim.data.energy = 2.0
scene.collection.objects.link(rim)
floor_m, _ = mat("floor", (0.08, 0.09, 0.1))
bpy.ops.mesh.primitive_plane_add(size=6); bpy.context.active_object.data.materials.append(floor_m)

cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); scene.collection.objects.link(cam)
cam.data.type = 'ORTHO'; cam.data.ortho_scale = 2.3
scene.camera = cam
hx, hy = (rig.matrix_world @ rig.data.bones["Hips"].head_local).xy


def shoot(fname, frame, yaw_deg):
    pose_frame(frame)
    yaw = math.radians(yaw_deg)
    # MPFB faces -Y; yaw 0 = front, 90 = the body's left side
    d = Vector((math.sin(yaw), -math.cos(yaw), 0))
    cam.location = Vector((hx, hy, 0.95)) + d * 5
    cam.rotation_euler = (math.radians(90), 0, yaw)
    sun.rotation_euler = (math.radians(55), 0, yaw - math.radians(35))
    rim.rotation_euler = (math.radians(70), 0, yaw + math.radians(160))
    scene.render.filepath = OUT + fname
    bpy.ops.render.render(write_still=True)
    print("WROTE", fname)


shoot("mpfb_squat_1_top_side.png", top, 70)
shoot("mpfb_squat_2_mid_side.png", mid, 70)
shoot("mpfb_squat_3_bottom_side.png", bottom, 70)
shoot("mpfb_squat_4_bottom_front.png", bottom, 15)
bpy.ops.wm.save_as_mainfile(filepath=ROOT + "review/mpfb_squat.blend")
