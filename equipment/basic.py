"""Procedural gym equipment: dumbbell, straight bar, and a single-stack cable
tower whose cable and weight stack follow the handle every frame."""
import bpy, math
from mathutils import Vector, Matrix
from core.look import flat_material

_mats = {}


def mat(name):
    try:
        valid = bool(_mats) and all(m.name in bpy.data.materials for m in _mats.values())
    except ReferenceError:
        valid = False
    if not valid:
        _mats.clear()
        _mats["steel"] = flat_material("steel", (0.75, 0.76, 0.78), 0.28, 1.0)
        _mats["dark"] = flat_material("dark_steel", (0.09, 0.095, 0.1), 0.45, 0.6)
        _mats["rubber"] = flat_material("rubber", (0.05, 0.05, 0.055), 0.75)
        _mats["frame"] = flat_material("frame", (0.16, 0.17, 0.19), 0.4, 0.5)
        _mats["plate"] = flat_material("plate", (0.12, 0.12, 0.13), 0.35, 0.7)
        _mats["accent"] = flat_material("accent", (0.85, 0.1, 0.05), 0.4)
        _mats["cable"] = flat_material("cable", (0.08, 0.08, 0.09), 0.3, 0.4)
    return _mats[name]


def _add(prim, name, material, parent=None, **kw):
    getattr(bpy.ops.mesh, prim)(**kw)
    o = bpy.context.active_object
    o.name = name
    o.data.materials.append(mat(material))
    bpy.ops.object.shade_smooth()
    if parent:
        o.parent = parent
    return o


def empty(name, loc=(0, 0, 0)):
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    e.location = loc
    return e


def cyl_x(name, material, r, length, x=0.0, parent=None, verts=32):
    """Cylinder along the local X axis, centred at x."""
    return _add("primitive_cylinder_add", name, material, parent, radius=r, depth=length,
                vertices=verts, location=(x, 0, 0), rotation=(0, math.radians(90), 0))


def dumbbell(name="dumbbell", head_r=0.062, head_w=0.055, handle=0.13):
    """Rubber hex-style dumbbell; local X = handle axis, origin = grip centre."""
    root = empty(name)
    cyl_x(name + "_handle", "steel", 0.016, handle + 2 * head_w, parent=root)
    for sgn in (1, -1):
        cyl_x(name + "_head", "rubber", head_r, head_w, sgn * (handle / 2 + head_w / 2), root, verts=6)
        cyl_x(name + "_collar", "steel", 0.024, 0.012, sgn * (handle / 2 + 0.004), root)
    return root


def straight_bar(name="bar", length=0.52):
    """Cable straight bar; local X = bar axis, origin = bar centre, cable ring on +Z."""
    root = empty(name)
    cyl_x(name + "_shaft", "steel", 0.013, length, parent=root)
    for sgn in (1, -1):
        cyl_x(name + "_grip", "rubber", 0.0165, 0.13, sgn * 0.12, root)
        cyl_x(name + "_end", "dark", 0.017, 0.012, sgn * (length / 2), root)
    hub = _add("primitive_cylinder_add", name + "_swivel", "dark", root, radius=0.018, depth=0.05,
               location=(0, 0, 0.03))
    ring = _add("primitive_torus_add", name + "_ring", "steel", root, major_radius=0.016,
                minor_radius=0.004, location=(0, 0, 0.068), rotation=(math.radians(90), 0, 0))
    return root


class CableTower:
    """Single-stack tower in front of a -Y-facing user. The cable runs from the
    stack up over a rear pulley, forward to a high front pulley, down to the handle."""

    def __init__(self, y_stack=-0.74, y_front=-0.42, top=2.12, plates=12, selected=5):
        self.y_stack, self.y_front = y_stack, y_front
        self.r = 0.048
        self.rear_c = Vector((0, y_stack + self.r, top + 0.03))
        self.front_c = Vector((0, y_front, top - 0.07))
        self.plate_h, self.gap = 0.03, 0.003
        self.stack_base = 0.09
        frame_x = 0.26
        # frame: base, uprights, top beam, boom to the front pulley, guide rods
        _add("primitive_cube_add", "tower_base", "frame", size=1, location=(0, y_stack - 0.02, 0.025),
             scale=(0.72, 0.5, 0.05))
        for sx in (1, -1):
            _add("primitive_cube_add", "tower_upright", "frame", size=1,
                 location=(sx * frame_x, y_stack, top / 2 + 0.05), scale=(0.07, 0.07, top + 0.1))
            _add("primitive_cylinder_add", "guide_rod", "steel", radius=0.011, depth=top - 0.2,
                 location=(sx * 0.11, y_stack, (top - 0.2) / 2 + 0.06))
        _add("primitive_cube_add", "tower_top", "frame", size=1, location=(0, y_stack, top + 0.13),
             scale=(2 * frame_x + 0.07, 0.09, 0.07))
        boom_len = abs(y_front - y_stack) + 0.08
        _add("primitive_cube_add", "tower_boom", "frame", size=1,
             location=(0, (y_front + y_stack) / 2, top + 0.13), scale=(0.07, boom_len, 0.06))
        _add("primitive_cube_add", "pulley_drop", "frame", size=1,
             location=(0, y_front, top + 0.04), scale=(0.05, 0.05, 0.12))
        for c, nm in ((self.rear_c, "rear"), (self.front_c, "front")):
            p = cyl_x(f"pulley_{nm}", "dark", self.r, 0.026, parent=None)
            p.location = c
            for sx in (1, -1):
                s = _add("primitive_cube_add", f"pulley_{nm}_cheek", "frame", size=1,
                         location=(sx * 0.022, c.y, c.z), scale=(0.008, 0.12, 0.12))
        # stack: the top `selected` plates ride on the cable
        self.moving = empty("stack_moving")
        n_fixed = plates - selected
        for i in range(plates):
            z = self.stack_base + i * (self.plate_h + self.gap) + self.plate_h / 2
            o = _add("primitive_cube_add", f"plate_{i:02d}", "plate", size=1, location=(0, y_stack, z),
                     scale=(0.3, 0.17, self.plate_h))
            if i >= n_fixed:
                o.parent = self.moving
        self.stack_top0 = self.stack_base + plates * (self.plate_h + self.gap)
        cap = _add("primitive_cube_add", "stack_cap", "accent", size=1,
                   location=(0, y_stack, self.stack_top0 + 0.02), scale=(0.3, 0.17, 0.035))
        cap.parent = self.moving
        pin_z = self.stack_base + n_fixed * (self.plate_h + self.gap) + self.plate_h / 2
        pin = _add("primitive_cylinder_add", "selector_pin", "accent", radius=0.007, depth=0.14,
                   location=(0, y_stack + 0.13, pin_z), rotation=(math.radians(90), 0, 0))
        pin.parent = self.moving
        rod = _add("primitive_cylinder_add", "selector_rod", "steel", radius=0.008, depth=0.5,
                   location=(0, y_stack, self.stack_top0 - 0.2))
        rod.parent = self.moving
        # cable: a poly curve rebuilt every frame
        cd = bpy.data.curves.new("cable", "CURVE")
        cd.dimensions = "3D"
        cd.bevel_depth = 0.0035
        cd.bevel_resolution = 3
        self.spline = cd.splines.new("POLY")
        self.n_pts = 22
        self.spline.points.add(self.n_pts - 1)
        self.cable = bpy.data.objects.new("cable", cd)
        bpy.context.scene.collection.objects.link(self.cable)
        cd.materials.append(mat("cable"))
        self.len0 = None

    def _arc(self, c, a0, a1, n):
        """Points on a pulley circle (YZ plane) from angle a0 to a1."""
        return [c + Vector((0, math.cos(a0 + (a1 - a0) * i / n) * self.r,
                            math.sin(a0 + (a1 - a0) * i / n) * self.r)) for i in range(n + 1)]

    def path(self, handle, lift):
        top = self.stack_top0 + 0.055 + lift
        rear, front, r = self.rear_c, self.front_c, self.r
        # leave the front pulley on the user's side, tangent toward the handle
        d = Vector((0, handle.y - front.y, handle.z - front.z))
        L = d.length
        base = math.atan2(d.z, d.y)
        a_exit = base + math.acos(min(1.0, r / L))
        # cable from rear pulley top runs forward to front pulley top (angle pi/2)
        pts = [Vector((0, self.y_stack, top)), Vector((0, self.y_stack, rear.z))]
        pts += self._arc(rear, math.pi, math.pi / 2, 6)[1:]
        pts += self._arc(front, math.pi / 2, a_exit, 8)
        pts.append(Vector((0, handle.y, handle.z)) + Vector((handle.x, 0, 0)))
        return pts

    def length(self, pts):
        return sum((pts[i + 1] - pts[i]).length for i in range(len(pts) - 1))

    def update(self, handle, frame):
        """Place cable + stack for a handle (cable attachment point) at this frame."""
        pts0 = self.path(handle, 0.0)
        L = self.length(pts0)
        if self.len0 is None:
            raise RuntimeError("call calibrate() with the shortest-cable handle position first")
        lift = max(0.0, L - self.len0)
        pts = self.path(handle, lift)
        # resample to a fixed point count
        tot = self.length(pts)
        out, acc, j = [], 0.0, 0
        seg = [(pts[i + 1] - pts[i]).length for i in range(len(pts) - 1)]
        for k in range(self.n_pts):
            t = tot * k / (self.n_pts - 1)
            while j < len(seg) - 1 and acc + seg[j] < t:
                acc += seg[j]; j += 1
            u = 0 if seg[j] == 0 else (t - acc) / seg[j]
            out.append(pts[j].lerp(pts[j + 1], min(1.0, u)))
        for p, v in zip(self.spline.points, out):
            p.co = (v.x, v.y, v.z, 1)
            p.keyframe_insert("co", frame=frame)
        self.moving.location.z = lift
        self.moving.keyframe_insert("location", frame=frame)
        return lift

    def calibrate(self, handle_highest):
        self.len0 = self.length(self.path(handle_highest, 0.0))
