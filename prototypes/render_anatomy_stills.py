"""Review stills of the Z-Anatomy muscle atlas: full muscle look plus a
'squat targets' highlight (quads + glutes). Stills only, no video."""
import bpy, math, sys, mathutils

import os; OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "review", "")
HIGHLIGHT = ["rectus femoris", "vastus lateralis", "vastus medialis", "vastus intermedius",
             "gluteus maximus muscle.", "gluteus medius muscle."]

scene = bpy.context.scene
muscles = bpy.data.collections['4: Muscular system']
bones = bpy.data.collections['1: Skeletal system']


# connective-tissue sheets sit on top of the muscles and hide any highlight
SKIP = ("fascia", "septum", "bursa", "sheath", "retinacul", "tract")


def wanted(o, coll):
    n = o.name.lower()
    return (o.type == 'MESH' and ('.' not in n or n.rsplit('.', 1)[-1] in ('l', 'r'))
            and not any(k in n for k in SKIP))


musc = [o for o in muscles.all_objects if wanted(o, muscles)]
skel = [o for o in bones.all_objects if wanted(o, bones)]
keep = set(musc) | set(skel)

# show only muscles + skeleton, at the view layer and collection level
def unhide_layer(lc):
    lc.exclude = False
    lc.hide_viewport = False
    lc.collection.hide_render = False
    for c in lc.children:
        unhide_layer(c)
unhide_layer(bpy.context.view_layer.layer_collection)
for o in scene.objects:
    show = o in keep
    o.hide_render = not show
    o.hide_viewport = not show
    try:
        o.hide_set(not show)
    except RuntimeError:
        pass


def mat(name, color, emit=0.0, rough=0.55):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = (*color, 1)
        b.inputs["Emission Strength"].default_value = emit
    return m


M_MUSCLE_RED = mat("muscle_red", (0.42, 0.06, 0.05))
M_MUSCLE_GREY = mat("muscle_grey", (0.55, 0.57, 0.6))
M_HOT = mat("muscle_hot", (0.9, 0.04, 0.02), emit=0.35, rough=0.4)
M_BONE = mat("bone", (0.85, 0.82, 0.74))


M_TENDON = mat("tendon", (0.8, 0.76, 0.68), rough=0.35)


ORIG = {}


def assign(o, m):
    # muscles carry [muscle, tendon] slots; keep the tendon slot pale
    slots = o.material_slots
    if not slots:
        o.data.materials.append(m)
        return
    orig = ORIG.setdefault(o.name, [sl.material.name if sl.material else "" for sl in slots])
    for sl, name in zip(slots, orig):
        sl.link = 'OBJECT'
        is_tendon = "tendon" in name.lower() or "ligament" in name.lower()
        sl.material = M_TENDON if (is_tendon and m is not M_BONE) else m


for o in skel:
    assign(o, M_BONE)

# framing from the actual visible geometry
mn = mathutils.Vector((1e9,) * 3); mx = mathutils.Vector((-1e9,) * 3)
for o in musc:
    for c in o.bound_box:
        w = o.matrix_world @ mathutils.Vector(c)
        mn = mathutils.Vector(map(min, mn, w)); mx = mathutils.Vector(map(max, mx, w))
center = (mn + mx) / 2
height = mx.z - mn.z
print("FRAME", tuple(round(v, 2) for v in mn), tuple(round(v, 2) for v in mx))

for l in [o for o in scene.objects if o.type == 'LIGHT']:
    l.hide_render = True
cam_data = bpy.data.cameras.new("ReviewCam")
cam_data.type = 'ORTHO'
cam_data.ortho_scale = height * 1.08
cam = bpy.data.objects.new("ReviewCam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam


def light(name, rot, energy, size=3):
    d = bpy.data.lights.new(name, 'AREA'); d.energy = energy; d.size = size
    o = bpy.data.objects.new(name, d); scene.collection.objects.link(o)
    return o, rot


key = bpy.data.lights.new("key", 'SUN'); key.energy = 3.2; key.angle = math.radians(8)
key_o = bpy.data.objects.new("key", key); scene.collection.objects.link(key_o)
rim = bpy.data.lights.new("rim", 'SUN'); rim.energy = 2.0
rim_o = bpy.data.objects.new("rim", rim); scene.collection.objects.link(rim_o)

world = scene.world or bpy.data.worlds.new("W"); scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs[0].default_value = (0.035, 0.04, 0.05, 1)
bg.inputs[1].default_value = 0.6

for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try:
        scene.render.engine = eng; break
    except TypeError:
        pass
scene.render.resolution_x, scene.render.resolution_y = 1080, 1920
scene.render.film_transparent = False
# the atlas renders as line art through Freestyle + a compositor; turn both off
scene.render.use_freestyle = False
for attr in ("use_compositing",):
    if hasattr(scene.render, attr):
        setattr(scene.render, attr, False)
try:
    scene.use_nodes = False
except Exception:
    pass
scene.render.resolution_percentage = int(sys.argv[-1]) if sys.argv[-1].isdigit() else 100
scene.view_settings.view_transform = 'AgX'
try:
    scene.view_settings.look = 'AgX - Medium High Contrast'
except TypeError:
    pass


def shoot(fname, front, hot):
    for o in musc:
        n = o.name.lower()
        if hot is None:
            assign(o, M_MUSCLE_RED)
        else:
            assign(o, M_HOT if any(h in n for h in hot) else M_MUSCLE_GREY)
    # Z-Anatomy faces -Y; the body's front is toward -Y
    sgn = -1 if front else 1
    cam.location = (center.x, center.y + sgn * 4, center.z)
    cam.rotation_euler = (math.radians(90), 0, 0 if front else math.radians(180))
    key_o.rotation_euler = (math.radians(60), 0, math.radians(-35 if front else 145))
    rim_o.rotation_euler = (math.radians(70), 0, math.radians(150 if front else -30))
    scene.render.filepath = OUT + fname
    bpy.ops.render.render(write_still=True)
    print("WROTE", fname)


if "--dbg" in sys.argv:
    o = bpy.data.objects["Rectus femoris muscle.l"]
    dg = bpy.context.evaluated_depsgraph_get()
    for x in (0.06, 0.08, 0.10, 0.12, 0.14):
        for z in (0.55, 0.65, 0.75):
            hit = scene.ray_cast(dg, mathutils.Vector((x, -3, z)), mathutils.Vector((0, 1, 0)))
            print("DBG ray", x, z, hit[0] and hit[4].name)
    print("DBG", o in keep, o.hide_render, o.visible_get(), o.visible_camera, o.parent and (o.parent.name, o.parent.hide_render, o.parent.type),
          tuple(round(v, 2) for v in o.matrix_world.translation), o.display_type, [c.type for c in o.constraints])
    sys.exit()
shoot("za_muscles_front.png", True, None)
shoot("za_squat_front.png", True, HIGHLIGHT)
shoot("za_squat_back.png", False, HIGHLIGHT)
