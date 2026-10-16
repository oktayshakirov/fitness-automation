"""Attach equipment (built by equipment/, Agent B) to the posed body every frame.
Spec entries: {"kind": "dumbbell", "hands": ["L", "R"]} or {"kind": "cable_bar", "tower": {...}}."""
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

    def attach(self, f):
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

    def attach(self, f):
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


KINDS = {"dumbbell": Dumbbells, "cable_bar": CableBar}


def build(P, specs):
    return [KINDS[s["kind"]](P, s) for s in specs]
