"""Shared Blender helpers for the fitness tests: MPFB body, pose solver,
muscle-mask material, studio and render. Run Blender with
BLENDER_USER_RESOURCES=<repo>/.blender-profile so MPFB2 is importable."""
import bpy, math, os, subprocess
from mathutils import Vector, Matrix, Quaternion

ROOT = "/Users/oktayshakirov/Coding/fitness-automation/"
MAPS = ROOT + "assets/maps/"
OUT = ROOT + "review/"

# free-exercise-db's 17 muscle groups, packed 3 per RGB mask image
GROUPS = ["quadriceps", "hamstrings", "glutes", "adductors", "abductors", "calves",
          "abdominals", "lower back", "middle back", "lats", "traps", "shoulders",
          "chest", "biceps", "triceps", "forearms", "neck"]


def mask_slot(group):
    i = GROUPS.index(group)
    return i // 3, i % 3  # (image index, channel)


def new_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


def use_gpu(scene):
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = True
    scene.cycles.device = "GPU"


def make_human():
    from bl_ext.user_default.mpfb.services.humanservice import HumanService
    from bl_ext.user_default.mpfb.services.targetservice import TargetService
    macro = TargetService.get_default_macro_info_dict()
    macro["gender"] = 1.0
    macro["muscle"] = 0.8
    macro["weight"] = 0.45
    body = HumanService.create_human(macro_detail_dict=macro)
    rig = HumanService.add_builtin_rig(body, "default")
    for pb in rig.pose.bones:
        pb.rotation_mode = "QUATERNION"
    bpy.context.view_layer.update()
    return body, rig


def update():
    bpy.context.view_layer.update()


# --- math ----------------------------------------------------------------
def frame(v, f):
    """Orthonormal basis whose Y is v and whose Z is f made perpendicular to v."""
    y = v.normalized()
    z = (f - f.project(y)).normalized()
    x = y.cross(z)
    return Matrix((x, y, z)).transposed()


def frame_align(v0, f0, v1, f1):
    """Rotation taking direction v0 to v1, with reference f0 turned toward f1."""
    return frame(v1, f1) @ frame(v0, f0).transposed()


def two_bone(h, a_pt, la, lb, pole):
    """Knee/elbow position for a two-segment limb from h to a_pt, bending toward pole."""
    d_vec = a_pt - h
    d = min(d_vec.length, (la + lb) * 0.9995)
    u = d_vec.normalized()
    along = (la * la - lb * lb + d * d) / (2 * d)
    hgt = math.sqrt(max(0.0, la * la - along * along))
    p = (pole - pole.project(u)).normalized()
    return h + u * along + p * hgt


def rot_x(deg):
    return Matrix.Rotation(math.radians(deg), 3, "X")


def rot_z(deg):
    return Matrix.Rotation(math.radians(deg), 3, "Z")


class Poser:
    """Sets bone orientations in world space. The rig object sits at identity,
    so armature space is world space."""

    def __init__(self, rig):
        self.rig = rig
        self.rest = {b.name: b.matrix_local.copy() for b in rig.data.bones}

    def rest3(self, n):
        return self.rest[n].to_3x3()

    def rest_head(self, n):
        return self.rest[n].translation.copy()

    def head(self, n):
        return self.rig.pose.bones[n].matrix.translation.copy()

    def tail(self, n):
        pb = self.rig.pose.bones[n]
        return pb.matrix @ Vector((0, pb.length, 0))

    def axis(self, n, i):
        return self.rig.pose.bones[n].matrix.to_3x3().col[i].normalized()

    def reset(self):
        for pb in self.rig.pose.bones:
            pb.matrix_basis = Matrix.Identity(4)
        update()

    def set_world(self, n, r3, loc=None):
        pb = self.rig.pose.bones[n]
        m = r3.to_4x4()
        m.translation = loc if loc is not None else pb.matrix.translation
        pb.matrix = m
        update()

    def turn(self, n, q3):
        """World-space rotation q3 applied to the bone's rest orientation."""
        self.set_world(n, q3 @ self.rest3(n))

    def local(self, n, axis, deg):
        """Rotation relative to the parent (bone-local axis)."""
        pb = self.rig.pose.bones[n]
        pb.rotation_quaternion = Quaternion(axis, math.radians(deg))
        update()

    def rest_bend(self, upper, lower, end):
        """Direction the middle joint (knee/elbow) points in the rest pose."""
        h0, k0, a0 = self.rest_head(upper), self.rest_head(lower), self.rest_head(end)
        u = (a0 - h0).normalized()
        off = (k0 - h0) - (k0 - h0).project(u)
        return off.normalized()

    def palm_rest(self, side):
        """Rest palm normal of a hand, from the knuckle line and finger direction."""
        w = self.rest_head(f"finger5-1.{side}") - self.rest_head(f"finger2-1.{side}")
        f = self.rest_head(f"finger3-1.{side}") - self.rest_head(f"wrist.{side}")
        n = w.cross(f) if side == "L" else f.cross(w)
        return n.normalized()

    def palm_now(self, side):
        w = self.head(f"finger5-1.{side}") - self.head(f"finger2-1.{side}")
        f = self.head(f"finger3-1.{side}") - self.head(f"wrist.{side}")
        n = w.cross(f) if side == "L" else f.cross(w)
        return n.normalized()

    def limb(self, upper, lower, end, target, pole, palm=None, side=None):
        """Two-segment limb (each segment may be a chain of child bones at rest
        relative to each other): upper starts the first segment, lower starts the
        second, end is the bone whose head is the end joint. The middle joint
        points toward pole. For arms, palm (world vector) sets forearm rotation."""
        h0, k0, a0 = self.rest_head(upper), self.rest_head(lower), self.rest_head(end)
        la, lb = (k0 - h0).length, (a0 - k0).length
        bend0 = self.rest_bend(upper, lower, end)
        h = self.head(upper)
        k = two_bone(h, target, la, lb, pole)
        bend1 = (k - h) - (k - h).project(target - h)
        if bend1.length < 1e-4:
            bend1 = pole
        self.turn(upper, frame_align(k0 - h0, bend0, k - h, bend1))
        if palm is not None:
            self.turn(lower, frame_align(a0 - k0, self.palm_rest(side), target - k, palm))
        else:
            self.turn(lower, frame_align(a0 - k0, bend0, target - k, bend1))
        return k

    def curl_fingers(self, side, deg=(55, 75, 50), thumb=(20, 35, 30), sign=1):
        for i in range(2, 6):
            for j, a in enumerate(deg, 1):
                self.local(f"finger{i}-{j}.{side}", (1, 0, 0), sign * a)
        for j, a in enumerate(thumb, 1):
            self.local(f"finger1-{j}.{side}", (1, 0, 0), sign * a)


# --- look ----------------------------------------------------------------
def load_masks():
    imgs = []
    for i in range(math.ceil(len(GROUPS) / 3)):
        p = MAPS + f"mask_{i}.png"
        img = bpy.data.images.load(p, check_existing=True)
        img.colorspace_settings.name = "Non-Color"
        imgs.append(img)
    return imgs


def muscle_material(primary=(), secondary=(), name="body", use_normal=False,
                    base=(0.5, 0.52, 0.56), hot=(0.86, 0.06, 0.03), warm=(0.98, 0.42, 0.06)):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.48
    imgs = load_masks()
    tex_nodes, sep_nodes = {}, {}

    def channel(group):
        i, c = mask_slot(group)
        if i not in tex_nodes:
            t = nt.nodes.new("ShaderNodeTexImage"); t.image = imgs[i]
            s = nt.nodes.new("ShaderNodeSeparateColor")
            nt.links.new(t.outputs["Color"], s.inputs["Color"])
            tex_nodes[i], sep_nodes[i] = t, s
        return sep_nodes[i].outputs[c]

    def combined(groups):
        out = None
        for g in groups:
            ch = channel(g)
            if out is None:
                out = ch
            else:
                mx = nt.nodes.new("ShaderNodeMath"); mx.operation = "MAXIMUM"
                nt.links.new(out, mx.inputs[0]); nt.links.new(ch, mx.inputs[1])
                out = mx.outputs[0]
        return out

    color = None
    col_base = nt.nodes.new("ShaderNodeRGB"); col_base.outputs[0].default_value = (*base, 1)
    color = col_base.outputs[0]
    for groups, rgb in ((secondary, warm), (primary, hot)):
        if not groups:
            continue
        mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"
        mix.inputs["B"].default_value = (*rgb, 1)
        nt.links.new(color, mix.inputs["A"])
        # sharpen the baked mask edge a little
        ramp = nt.nodes.new("ShaderNodeMapRange")
        ramp.inputs["From Min"].default_value = 0.25
        ramp.inputs["From Max"].default_value = 0.6
        nt.links.new(combined(groups), ramp.inputs["Value"])
        nt.links.new(ramp.outputs["Result"], mix.inputs["Factor"])
        color = mix.outputs["Result"]
    nt.links.new(color, bsdf.inputs["Base Color"])
    nmap_path = MAPS + "muscle_normal.png"
    if use_normal and os.path.exists(nmap_path):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(nmap_path, check_existing=True)
        t.image.colorspace_settings.name = "Non-Color"
        nm = nt.nodes.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = 0.8
        nt.links.new(t.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def flat_material(name, rgb, rough=0.45, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


def studio(scene, floor=True):
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            scene.render.engine = eng
            break
        except TypeError:
            pass
    scene.view_settings.view_transform = "AgX"
    w = bpy.data.worlds.new("W"); scene.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.95, 0.955, 0.965, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.8
    key = bpy.data.objects.new("key", bpy.data.lights.new("key", "SUN"))
    key.data.energy = 3.2; key.data.angle = math.radians(12)
    key.rotation_euler = (math.radians(50), 0, math.radians(-30))
    fill = bpy.data.objects.new("fill", bpy.data.lights.new("fill", "SUN"))
    fill.data.energy = 1.2; fill.rotation_euler = (math.radians(65), 0, math.radians(140))
    for o in (key, fill):
        scene.collection.objects.link(o)
    if floor:
        bpy.ops.mesh.primitive_plane_add(size=12)
        bpy.context.active_object.data.materials.append(flat_material("floor", (0.93, 0.935, 0.945), 0.9))
    scene.render.fps = 30


def camera(scene, name, target, yaw_deg, dist=6.0, ortho=2.2, height=None):
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    scene.collection.objects.link(cam)
    cam.data.type = "ORTHO"; cam.data.ortho_scale = ortho
    yaw = math.radians(yaw_deg)
    d = Vector((math.sin(yaw), -math.cos(yaw), 0))  # yaw 0 = in front of a -Y-facing body
    tgt = Vector(target)
    cam.location = tgt + d * dist
    if height is not None:
        cam.location.z = height
    cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
    return cam


def render_views(scene, cams, prefix, f0, f1, res=(720, 1280)):
    """Render frames f0..f1 for each camera into OUT/<prefix>_<cam>/####.png."""
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    dirs = []
    for cam in cams:
        scene.camera = cam
        d = OUT + f"{prefix}_{cam.name}/"
        os.makedirs(d, exist_ok=True)
        if os.environ.get("QUICK"):
            for f in [int(x) for x in os.environ["QUICK"].split(",")]:
                scene.frame_set(f)
                scene.render.filepath = d + f"{f:04d}.png"
                bpy.ops.render.render(write_still=True)
        else:
            scene.frame_start, scene.frame_end = f0, f1
            scene.render.filepath = d
            bpy.ops.render.render(animation=True)
        dirs.append(d)
        print("RENDERED", d)
    return dirs


def stitch_video(dirs, out_mp4, fps=30, loops=3):
    """Side-by-side mp4 of the per-camera frame folders, looped a few times."""
    inputs = []
    for d in dirs:
        inputs += ["-stream_loop", str(loops - 1), "-framerate", str(fps), "-i", d + "%04d.png"]
    filt = "".join(f"[{i}:v]" for i in range(len(dirs))) + f"hstack=inputs={len(dirs)},format=yuv420p[v]" \
        if len(dirs) > 1 else "[0:v]format=yuv420p[v]"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *inputs, "-filter_complex", filt,
                    "-map", "[v]", "-c:v", "libx264", "-crf", "20", out_mp4], check=True)
    print("VIDEO", out_mp4)


def contact_sheet(dirs, frames, out_png):
    """Grid: one row per camera, one column per frame."""
    if os.environ.get("QUICK"):
        frames = [int(x) for x in os.environ["QUICK"].split(",")]
    rows = []
    for d in dirs:
        rows.append("".join(f"-i {d}{f:04d}.png " for f in frames))
    args = []
    for d in dirs:
        for f in frames:
            args += ["-i", f"{d}{f:04d}.png"]
    n, m = len(dirs), len(frames)
    filt = ""
    for r in range(n):
        filt += "".join(f"[{r * m + c}:v]" for c in range(m)) + f"hstack=inputs={m}[r{r}];"
    filt += "".join(f"[r{r}]" for r in range(n)) + (f"vstack=inputs={n}[v]" if n > 1 else "copy[v]")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *args, "-filter_complex", filt,
                    "-map", "[v]", "-frames:v", "1", out_png], check=True)
    print("SHEET", out_png)
