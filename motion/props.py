"""Attach equipment (built by equipment/) to the posed body every frame.
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
        self.grip_mode = spec.get("grip_mode", "hook")
        self.bells = {}
        if self.hands == ["both"]:          # one dumbbell placed by the pattern (goblet)
            self.one = eq.dumbbell("db")
            self.one.rotation_mode = "QUATERNION"
            self.hands = []
        for side in self.hands:
            b = eq.dumbbell(f"db_{side}")
            b.rotation_mode = "QUATERNION"
            b["grip_mode"] = self.grip_mode
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
            g, w = grip_point(P, side, self.grip_mode)
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
        self.handle = spec.get("handle", "bar")
        self.ring = {}
        if self.handle == "rope":
            self.rope = self._rope()
            return
        self.bar = eq.straight_bar()
        self.bar.rotation_mode = "QUATERNION"

    def _rope(self):
        return eq.rope("pushdown_rope")

    def attach_rope(self, f):
        gL, _ = grip_point(self.P, "L")
        gR, _ = grip_point(self.P, "R")
        mid = (gL + gR) / 2
        up = (self.tower.front_c - mid).normalized()
        ring = mid + up * 0.16
        self.rope.location = ring
        self.rope.keyframe_insert("location", frame=f)
        eq.update_rope(self.rope, gL, gR, f)
        self.ring[f] = ring
        return {"L": gL, "R": gR}

    def attach(self, f, contacts=None):
        if self.handle == "rope":
            return self.attach_rope(f)
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
    """Stand-in until equipment.barbell exists: Olympic dimensions."""
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
        mid = (hL + hR) / 2
        root = eq.dip_station("dip_station", height=mid.z, width=abs(hL.x-hR.x))
        return [(root, Vector((mid.x, mid.y, 0)), Vector((1,0,0)))]

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
            self.root = maker("bench", incline=spec.get("incline",0), seat_z=z, y0=y0, y1=y1)
            self.root.location.x = spec.get("x", 0.0)
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
    """Real equipment/ machine driven by the motion pattern's contacts."""
    def __init__(self, P, spec):
        kw = {k:spec[k] for k in ("seat_z","lean") if k in spec}
        self.impl = eq.Machine(spec.get("type", "leg_extension"), **kw)
        self.root = self.impl.root
    def attach(self, f, contacts=None):
        self.impl.update(contacts or {},f)
        return {}
    def finish(self,n):
        pass


class CableHandle:
    """Handle (lat bar or V-handle) on a straight cable to a fixed pulley (stand-in
    until the cable tower has low/high pulley variants)."""

    def __init__(self, P, spec):
        import bpy
        self.pulley = Vector(spec.get("pulley", (0, -0.05, 2.45)))
        self.kind = spec.get("handle", "lat_bar")
        self.obj = eq.lat_bar("lat_bar") if self.kind == "lat_bar" else eq.v_bar("v_handle")
        if self.kind == "lat_bar":
            self.obj.scale.x = spec.get("grip_w", .40) / .40
        self.grip_local = Vector((0,0,-.04 if self.kind == "lat_bar" else -.13))
        self.obj.rotation_mode = "QUATERNION"
        self.spline = None
        if spec.get('standalone_cable', True):
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
        self.obj.rotation_quaternion = Matrix((x, z.cross(x), z)).transposed().to_quaternion()
        self.obj.location = c - self.obj.rotation_quaternion @ self.grip_local
        self.obj.keyframe_insert("location", frame=f)
        self.obj.keyframe_insert("rotation_quaternion", frame=f)
        if self.spline is not None:
            for p_, v in zip(self.spline.points, (self.obj.location, self.pulley)):
                p_.co = (v.x, v.y, v.z, 1)
                p_.keyframe_insert("co", frame=f)
        return {}

    def finish(self, n):
        pass


class Kettlebell:
    """Kettlebell held by its handle (stand-in until equipment.kettlebell exists): handle
    along local X, the bell hangs along the arms' direction."""

    def __init__(self, P, spec):
        import bpy
        maker = getattr(eq, "kettlebell", None)
        if maker:
            self.kb = maker("kettlebell", spec.get("kg", 16))
        else:
            self.kb = eq.empty("kettlebell")
            r = 0.105
            bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=(0, 0, -0.035 - r), segments=32, ring_count=16)
            bell = bpy.context.active_object
            bell.name = "kettlebell_bell"
            bell.data.materials.append(eq.mat("dark"))
            bpy.ops.object.shade_smooth()
            bell.parent = self.kb
            bpy.ops.mesh.primitive_torus_add(major_radius=0.07, minor_radius=0.011, location=(0, 0, -0.035),
                                             rotation=(math.radians(90), 0, 0))
            h = bpy.context.active_object
            h.name = "kettlebell_handle"
            h.scale = (1.0, 0.75, 1.0)
            h.data.materials.append(eq.mat("dark"))
            h.parent = self.kb
        self.kb.rotation_mode = "QUATERNION"

    def attach(self, f, contacts=None):
        if not contacts or "kb" not in contacts:
            return {}
        c, x, d = contacts["kb"]
        z = (-d - (-d).project(x)).normalized()           # local -Z (bell) along the arms
        self.kb.location = c
        self.kb.rotation_quaternion = Matrix((x, z.cross(x), z)).transposed().to_quaternion()
        self.kb.keyframe_insert("location", frame=f)
        self.kb.keyframe_insert("rotation_quaternion", frame=f)
        return {}

    def finish(self, n):
        pass


class CableLines:
    """Cables from fixed pulleys to the hands (stand-in for the dual cable station):
    {"kind": "cable_lines", "pulleys": {"L": [x, y, z], "R": [...]}} gives each hand a
    D-handle on its own cable; {"kind": "cable_lines", "pulley": [x, y, z], "rope": true}
    gives a rope whose two ends are in the hands."""

    def __init__(self, P, spec):
        import bpy
        self.rope = spec.get("rope", False)
        self.pulleys = {k: Vector(v) for k, v in spec.get("pulleys", {}).items()}
        if self.rope:
            self.pulleys = {"C": Vector(spec["pulley"])}
        self.lines, self.handles, self.towers, self.rings = {}, {}, {}, {}
        for k,pul in self.pulleys.items():
            mode = "mid" if self.rope else "high"
            top = 2.12 if self.rope else pul.z + .07
            tower = eq.CableTower(x=pul.x,y_stack=pul.y-.32,y_front=pul.y,top=top,pulley=mode,name="cable_"+k)
            # Mid-pulley default is 1.35 m; translate the complete fixed station to
            # preserve the declared cable outlet height (face pull uses 1.42 m).
            dz = pul.z-tower.front_c.z
            for ob in tower.objects:
                if ob.name.find("pulley_front")>=0: ob.location.z += dz
            tower.front_c.z = pul.z
            self.towers[k]=tower; self.rings[k]={}
        if self.rope:
            self.rope_obj=eq.rope("face_rope")
        else:
            for side in ("L", "R"):
                h=eq.d_handle("d_handle_"+side); h.rotation_mode="QUATERNION"
                self.handles[side]=h

    def _set(self, sp, a, b, f):
        for p_, v in zip(sp.points, (a, b)):
            p_.co = (v.x, v.y, v.z, 1)
            p_.keyframe_insert("co", frame=f)

    def attach(self, f, contacts=None):
        if not contacts:
            return {}
        if self.rope:
            gL, gR = contacts["handle.L"], contacts["handle.R"]
            mid = (gL + gR) / 2
            ring = mid + (self.pulleys["C"] - mid).normalized() * 0.14
            self.rope_obj.location=ring
            self.rope_obj.keyframe_insert("location",frame=f)
            eq.update_rope(self.rope_obj,gL,gR,f)
            self.rings["C"][f]=ring
            return {}
        for side in ("L", "R"):
            g = contacts[f"handle.{side}"]
            pul = self.pulleys[side]
            d = (pul - g).normalized()
            h = self.handles[side]
            # handle across the fist; the cable leaves the handle toward the pulley
            x = Vector((0, 0, 1))
            x = (x - x.project(d)).normalized()
            h.rotation_quaternion = Matrix((x, d.cross(x), d)).transposed().to_quaternion()
            h.location = g - h.rotation_quaternion @ Vector((0,0,-.13))
            h.keyframe_insert("location", frame=f)
            h.keyframe_insert("rotation_quaternion", frame=f)
            self.rings[side][f]=h.location.copy()
        return {}

    def finish(self, n):
        for key,tower in self.towers.items():
            rings=self.rings[key]
            shortest=min(rings.values(),key=lambda p:tower.length(tower.path(p,0)))
            tower.calibrate(shortest)
            for f,p in rings.items(): tower.update(p,f)


KINDS = {"dumbbell": Dumbbells, "cable_bar": CableBar, "barbell": Barbell,
         "pullup_bar": FixedBars, "dip_bars": FixedBars, "bench": Bench,
         "machine": Machine, "cable_handle": CableHandle,
         "kettlebell": Kettlebell, "cable_lines": CableLines}


def build(P, specs):
    return [KINDS[s["kind"]](P, s) for s in specs]
