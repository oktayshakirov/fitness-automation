"""Standing base shared by the standing patterns: planted feet, knees tracking the toes,
pelvis placed so the hip-joint midpoint lands on a planned point."""
import math
from mathutils import Vector
from core.solver import rot_x, rot_z

UP = Vector((0, 0, 1))


class Stance:
    def __init__(self, P, width=0.13, toe_out=8.0, foot_y=0.0, split=None):
        """width = ankle half-width (hip joints sit at ~0.108). foot_y shifts both feet
        along Y (-Y = forward). split = {"L": dy, "R": dy} for staggered feet."""
        self.P = P
        self.toe_out = toe_out
        az, ay = P.rest_head("foot.L").z, P.rest_head("foot.L").y + foot_y
        split = split or {"L": 0.0, "R": 0.0}
        self.ankles = {"L": Vector((width, ay + split["L"], az)), "R": Vector((-width, ay + split["R"], az))}
        a = math.radians(toe_out)
        self.toe = {"L": Vector((math.sin(a), -math.cos(a), 0)), "R": Vector((-math.sin(a), -math.cos(a), 0))}
        self.la = (P.rest_head("lowerleg01.L") - P.rest_head("upperleg01.L")).length
        self.lb = (P.rest_head("foot.L") - P.rest_head("lowerleg01.L")).length
        self.hip_x = P.rest_head("upperleg01.L").x
        self.width = width

    def hip_height(self, reach, back=0.0, side="L"):
        """Hip-joint z for legs extended to reach*(la+lb), hips `back` (+Y) of the ankle."""
        r = reach * (self.la + self.lb)
        dx = self.hip_x - abs(self.ankles[side].x)
        return self.ankles[side].z + math.sqrt(r * r - dx * dx - back * back)

    def legs(self, sides=("L", "R")):
        P = self.P
        for side, sgn in (("L", 1), ("R", -1)):
            if side not in sides:
                continue
            P.limb(f"upperleg01.{side}", f"lowerleg01.{side}", f"foot.{side}", self.ankles[side], self.toe[side])
            P.set_world(f"foot.{side}", rot_z(sgn * self.toe_out) @ P.rest3(f"foot.{side}"))


def place_pelvis(P, tilt, hip_mid):
    """Hinge the pelvis forward by tilt degrees and move it so the hip-joint midpoint
    sits at hip_mid."""
    root_rest = P.rest_head("root")
    P.set_world("root", rot_x(tilt) @ P.rest3("root"), root_rest)
    mid = (P.head("upperleg01.L") + P.head("upperleg01.R")) / 2
    P.set_world("root", rot_x(tilt) @ P.rest3("root"), root_rest + (hip_mid - mid))


def arm_lengths(P, side="L"):
    ua = (P.rest_head(f"lowerarm01.{side}") - P.rest_head(f"upperarm01.{side}")).length
    fa = (P.rest_head(f"wrist.{side}") - P.rest_head(f"lowerarm01.{side}")).length
    return ua, fa
