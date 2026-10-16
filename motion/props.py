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
        for side in self.hands:
            b = eq.dumbbell(f"db_{side}")
            b.rotation_mode = "QUATERNION"
            self.bells[side] = b

    def attach(self, f, contacts=None):
        P = self.P
        out = {}
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


KINDS = {"dumbbell": Dumbbells, "cable_bar": CableBar, "barbell": Barbell}


def build(P, specs):
    return [KINDS[s["kind"]](P, s) for s in specs]
