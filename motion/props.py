"""Attach equipment (built by equipment/, Agent B) to the posed body every frame.
Spec entries: {"kind": "dumbbell", "hands": ["L", "R"]}, {"kind": "cable_bar", "tower": {...}},
{"kind": "barbell", "plates": [20]}. A pattern's pose() may return contacts, e.g.
{"bar": (centre, axis)}: rigid implements are placed from those, hands are solved onto them."""
import math
from mathutils import Vector, Matrix, Quaternion
import equipment as eq
from .contact import grip_point


class Dumbbells:
    def __init__(self, P, spec):
        self.P = P
        self.hands = spec.get("hands", ["L", "R"])
        self.bells = {}
        if self.hands == ["both"]:          # one dumbbell placed by the pattern (goblet)
            self.one = eq.dumbbell("db")
            self.one.rotation_mode = "QUATERNION"
            self.hands = []
        for side in self.hands:
            b = eq.dumbbell(f"db_{side}")
            b.rotation_mode = "QUATERNION"
            self.bells[side] = b

    def attach(self, f, contacts=None):
        P = self.P
        out = {}
        if contacts and "db" in contacts and hasattr(self, "one"):
            c, x = contacts["db"]
            ref = Vector((0, 1, 0))
            z = (ref - ref.project(x)).normalized()
            self.one.location = c
            self.one.rotation_quaternion = Matrix((x, z.cross(x), z)).transposed().to_quaternion()
            self.one.keyframe_insert("location", frame=f)
            self.one.keyframe_insert("rotation_quaternion", frame=f)
        for side in self.hands:
            g, w = grip_point(P, side)
            b = self.bells[side]
            # handle (local X) runs across the palm; the dumbbell is round about X
            x = w
            z = (P.palm_now(side) - P.palm_now(side).project(x)).normalized()
            b.location = g
            b.rotation_quaternion = Matrix((x, z.cross(x), z)).transposed().to_quaternion()
            b.keyframe_insert("location", frame=f)
            b.keyframe_insert("rotation_quaternion", frame=f)
            out[side] = g
        return out

    def finish(self, n):
        pass


class CableBar:
    """Straight bar held in both hands, hanging from a high-pulley cable tower."""

    def __init__(self, P, spec):
        self.P = P
        self.tower = eq.CableTower(**spec.get("tower", {}))
        self.bar = eq.straight_bar()
        self.bar.rotation_mode = "QUATERNION"
        self.ring = {}

    def attach(self, f, contacts=None):
        gL, _ = grip_point(self.P, "L")
        gR, _ = grip_point(self.P, "R")
        c = (gL + gR) / 2
        to_pulley = self.tower.front_c - c
        a = math.atan2(-to_pulley.y, to_pulley.z)
        self.bar.location = c
        self.bar.rotation_quaternion = Quaternion((1, 0, 0), a)
        self.bar.keyframe_insert("location", frame=f)
        self.bar.keyframe_insert("rotation_quaternion", frame=f)
        self.ring[f] = c + self.bar.rotation_quaternion @ Vector((0, 0, 0.068))
        return {"L": gL, "R": gR}

    def finish(self, n):
        shortest = min(self.ring.values(), key=lambda p: (p - self.tower.front_c).length)
        self.tower.calibrate(shortest)
        lifts = [self.tower.update(self.ring[f], f) for f in range(1, n + 1)]
        print("STACK LIFT max", round(max(lifts), 3), "m")


def _proxy_barbell(name, plates):
    """Stand-in until equipment.barbell exists (Agent B): Olympic dimensions."""
    root = eq.empty(name)
    eq.cyl_x(name + "_shaft", "steel", 0.014, 1.31, parent=root)
    for sgn in (1, -1):
        eq.cyl_x(name + "_sleeve", "steel", 0.025, 0.445, sgn * (0.655 + 0.2225), root)
        eq.cyl_x(name + "_collar", "steel", 0.04, 0.03, sgn * 0.67, root)
        x = 0.69
        for kg in plates:
            r, w = {25: (0.225, 0.06), 20: (0.225, 0.05), 15: (0.225, 0.04), 10: (0.225, 0.035),
                    5: (0.115, 0.03), 2.5: (0.095, 0.02)}.get(kg, (0.225, 0.05))
            eq.cyl_x(name + "_plate", "plate", r, w, sgn * (x + w / 2), root, verts=48)
            x += w + 0.003
    root["plate_r"] = 0.225 if plates else 0.025
    return root


class Barbell:
    def __init__(self, P, spec):
        self.P = P
        plates = spec.get("plates", [20])
        maker = getattr(eq, "barbell", None)
        self.bar = maker("barbell", plates=plates) if maker else _proxy_barbell("barbell", plates)
        self.bar.rotation_mode = "QUATERNION"

    def attach(self, f, contacts=None):
        if contacts and "bar" in contacts:
            c, axis = contacts["bar"]
        else:
            gL, _ = grip_point(self.P, "L")
            gR, _ = grip_point(self.P, "R")
            c, axis = (gL + gR) / 2, (gL - gR).normalized()
        up = Vector((0, 0, 1))
        z = (up - up.project(axis)).normalized()
        self.bar.location = c
        self.bar.rotation_quaternion = Matrix((axis, z.cross(axis), z)).transposed().to_quaternion()
        self.bar.keyframe_insert("location", frame=f)
        self.bar.keyframe_insert("rotation_quaternion", frame=f)
        return {"bar": c}

    def finish(self, n):
        pass


class FixedBars:
    """Pull-up bar or parallel dip bars (stand-ins until equipment/ has them): built
    where the pattern says the hands are, keyed in place every frame."""

    def __init__(self, P, spec):
        self.P = P
        self.kind = spec["kind"]
        self.objs = None

    def _build(self, contacts):
        if self.kind == "pullup_bar":
            c, axis = contacts["bar"]
            maker = getattr(eq, "pullup_bar", None)
            if maker:
                return [(maker("pullup_bar", c.z), c, Vector((1, 0, 0)))]
            # wall-mounted: brackets run back to the wall, so side views stay clear
            root = eq.empty("pullup_bar")
            eq.cyl_x("pullup_bar_tube", "steel", 0.016, 1.3, parent=root)
            for sgn in (1, -1):
                arm = eq.cyl_x("pullup_bracket", "frame", 0.022, 0.6, parent=root)
                arm.rotation_euler = (math.radians(90), 0, 0)
                arm.location = (sgn * 0.6, 0.3, 0)
            wall = eq.cyl_x("pullup_wall_rail", "frame", 0.03, 1.3, parent=root)
            wall.location = (0, 0.6, 0)
            return [(root, c, Vector((1, 0, 0)))]
        hL, hR = contacts["dip"]
        out = []
        for side, h in (("L", hL), ("R", hR)):
            root = eq.empty(f"dip_bar_{side}")
            eq.cyl_x(f"dip_bar_{side}_tube", "steel", 0.02, 0.7, parent=root)
            for dy in (0.3, -0.3):
                post = eq.cyl_x(f"dip_post", "frame", 0.03, h.z, parent=root)
                post.rotation_euler = (0, 0, 0)
                post.location = (dy, 0, -h.z / 2)
            out.append((root, h, Vector((0, 1, 0))))
        return out

    def attach(self, f, contacts=None):
        if not contacts:
            return {}
        if self.objs is None:
            self.objs = self._build(contacts)
        for o, c, axis in self.objs:
            o.rotation_mode = "QUATERNION"
            z = Vector((0, 0, 1))
            o.location = c
            o.rotation_quaternion = Matrix((axis, z.cross(axis), z)).transposed().to_quaternion()
            o.keyframe_insert("location", frame=f)
            o.keyframe_insert("rotation_quaternion", frame=f)
        return {}

    def finish(self, n):
        pass


class Bench:
    """Flat bench (stand-in until equipment.bench exists): pad top at z, running along Y
    under a lying body whose upper back is at y = 0."""

    def __init__(self, P, spec):
        import bpy
        z, y0, y1 = spec.get("z", 0.43), spec.get("y0", -0.78), spec.get("y1", 0.42)
        maker = getattr(eq, "bench", None)
        if maker:
            self.root = maker("bench")
            return
        self.root = eq.empty("bench")
        self.root.location.x = spec.get("x", 0.0)
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, (y0 + y1) / 2, z - 0.04),
                                        scale=(0.29, y1 - y0, 0.08))
        pad = bpy.context.active_object
        pad.name = "bench_pad"
        pad.data.materials.append(eq.mat("rubber"))
        pad.parent = self.root
        for y in (y0 + 0.12, y1 - 0.12):
            bpy.ops.mesh.primitive_cube_add(size=1, location=(0, y, (z - 0.08) / 2), scale=(0.06, 0.06, z - 0.08))
            leg = bpy.context.active_object
            leg.data.materials.append(eq.mat("frame"))
            leg.parent = self.root
            bpy.ops.mesh.primitive_cube_add(size=1, location=(0, y, 0.02), scale=(0.42, 0.07, 0.04))
            foot = bpy.context.active_object
            foot.data.materials.append(eq.mat("frame"))
            foot.parent = self.root

    def attach(self, f, contacts=None):
        return {}

    def finish(self, n):
        pass


def _box(name, loc, scale, material, parent, rot=None):
    import bpy
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, scale=scale)
    o = bpy.context.active_object
    o.name = name
    o.data.materials.append(eq.mat(material))
    if rot is not None:
        o.rotation_euler = rot
    o.parent = parent
    return o


class Machine:
    """Stand-in machine frame (until equipment/ has the real ones): seat, back pad, and
    the part the pattern moves - a shin roller ("pad") or a sled plate ("plate").
    spec: {"kind": "machine", "type": "leg_extension" | "leg_curl" | "leg_press" |
    "pulldown" | "cable_row", "seat_z": .., "lean": ..}"""

    def __init__(self, P, spec):
        self.P = P
        t = spec.get("type", "leg_extension")
        self.t = t
        z = spec.get("seat_z", 0.48)
        lean = math.radians(spec.get("lean", -10.0))
        self.root = eq.empty("machine")
        # back pad along the torso: hip joint ~8.5 cm over the seat, back surface
        # ~12 cm behind the hip-shoulder line
        hip = Vector((0, 0, z + 0.085))
        up = Vector((0, -math.sin(lean), math.cos(lean)))
        back = Vector((0, math.cos(lean), math.sin(lean)))
        if t == "leg_press":
            _box("seat", (0, 0.06, z - 0.04), (0.42, 0.36, 0.08), "rubber", self.root)
            c = hip + up * 0.40 + back * 0.16
            _box("back_pad", tuple(c), (0.42, 0.08, 0.80), "rubber", self.root, rot=(lean, 0, 0))
            _box("base", (0, -0.3, 0.05), (0.8, 2.0, 0.1), "frame", self.root)
        elif t == "cable_row":
            _box("seat", (0, 0.05, z - 0.04), (0.32, 0.9, 0.08), "rubber", self.root)
            _box("rail", (0, -0.35, z / 2), (0.12, 1.5, z - 0.08), "frame", self.root)
            _box("footplate", (0, -0.80, 0.30), (0.5, 0.05, 0.30), "frame", self.root, rot=(math.radians(20), 0, 0))
        else:
            _box("seat", (0, -0.12, z - 0.04), (0.42, 0.44, 0.08), "rubber", self.root)
            _box("seat_post", (0, -0.05, (z - 0.08) / 2), (0.1, 0.1, z - 0.08), "frame", self.root)
            if t != "pulldown":
                c = hip + up * 0.36 + back * 0.17
                _box("back_pad", tuple(c), (0.40, 0.08, 0.62), "rubber", self.root, rot=(lean, 0, 0))
            else:
                _box("knee_pad", (0, -0.40, z + 0.20), (0.45, 0.10, 0.10), "rubber", self.root)
        self.moving = None
        if t in ("leg_extension", "leg_curl"):
            self.moving = eq.cyl_x("shin_roller", "rubber", 0.05, 0.42)
        elif t == "leg_press":
            self.moving = eq.empty("sled")
            _box("sled_plate", (0, 0, 0), (0.75, 0.04, 0.55), "frame", self.moving)

    def attach(self, f, contacts=None):
        if not self.moving or not contacts:
            return {}
        if "pad" in contacts:
            c, _ = contacts["pad"]
            self.moving.location = c
            self.moving.keyframe_insert("location", frame=f)
        if "plate" in contacts:
            c, d = contacts["plate"]
            self.moving.rotation_mode = "QUATERNION"
            # plate face perpendicular to the rail, centred just past the soles
            y = -d
            x = Vector((1, 0, 0))
            self.moving.rotation_quaternion = Matrix((x, y, x.cross(y))).transposed().to_quaternion()
            self.moving.location = c + d * 0.07
            self.moving.keyframe_insert("location", frame=f)
            self.moving.keyframe_insert("rotation_quaternion", frame=f)
        return {}

    def finish(self, n):
        pass


class CableHandle:
    """Handle (lat bar or V-handle) on a straight cable to a fixed pulley (stand-in
    until the cable tower has low/high pulley variants)."""

    def __init__(self, P, spec):
        import bpy
        self.pulley = Vector(spec.get("pulley", (0, -0.05, 2.45)))
        self.kind = spec.get("handle", "lat_bar")
        if self.kind == "lat_bar":
            self.obj = eq.empty("lat_bar")
            eq.cyl_x("lat_bar_tube", "steel", 0.014, 1.15, parent=self.obj)
            for sgn in (1, -1):
                bend = eq.cyl_x("lat_bar_grip", "rubber", 0.017, 0.16, sgn * 0.4, self.obj)
        else:
            self.obj = eq.empty("v_handle")
            for sgn in (1, -1):
                h = eq.cyl_x("v_handle_grip", "rubber", 0.016, 0.13, 0, self.obj)
                h.rotation_euler = (0, 0, 0)
                h.location = (sgn * 0.045, 0, 0)
            eq.cyl_x("v_handle_bridge", "steel", 0.012, 0.11, parent=self.obj)
        self.obj.rotation_mode = "QUATERNION"
        pulley = eq.cyl_x("pulley_wheel", "dark", 0.05, 0.03)
        pulley.location = self.pulley
        cd = bpy.data.curves.new("cable", "CURVE")
        cd.dimensions = "3D"
        cd.bevel_depth = 0.0035
        sp = cd.splines.new("POLY")
        sp.points.add(1)
        self.spline = sp
        cab = bpy.data.objects.new("cable", cd)
        bpy.context.scene.collection.objects.link(cab)
        cd.materials.append(eq.mat("cable"))

    def attach(self, f, contacts=None):
        if not contacts or "handle" not in contacts:
            return {}
        c, axis, _ = contacts["handle"]
        z = (self.pulley - c).normalized()
        if self.kind == "lat_bar":
            x = Vector((1, 0, 0))
            z = (z - z.project(x)).normalized()
        else:
            x = Vector((1, 0, 0))
            z = (z - z.project(x)).normalized()
        self.obj.location = c
        self.obj.rotation_quaternion = Matrix((x, z.cross(x), z)).transposed().to_quaternion()
        self.obj.keyframe_insert("location", frame=f)
        self.obj.keyframe_insert("rotation_quaternion", frame=f)
        for p_, v in zip(self.spline.points, (c, self.pulley)):
            p_.co = (v.x, v.y, v.z, 1)
            p_.keyframe_insert("co", frame=f)
        return {}

    def finish(self, n):
        pass


KINDS = {"dumbbell": Dumbbells, "cable_bar": CableBar, "barbell": Barbell,
         "pullup_bar": FixedBars, "dip_bars": FixedBars, "bench": Bench,
         "machine": Machine, "cable_handle": CableHandle}


def build(P, specs):
    return [KINDS[s["kind"]](P, s) for s in specs]
