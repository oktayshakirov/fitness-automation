"""Bent-over row (barbell or two dumbbells).

Hip hinge held still for the whole set: soft knees, flat back at `hinge` deg from
vertical, neck in line. The load hangs at arm's length over mid-foot, then is pulled to
the lower ribs: elbows travel back past the torso, ~25 deg out from its sides, shoulder blades
squeeze together at the top and reach (slight protraction) at the bottom. No torso
swing.

params: hinge (deg from vertical), knee (deg), grip_w (half-width), grip ("over" |
"under" | "neutral" for dumbbells), load ("bar" | "db"), elbow_out (deg the elbow path opens from the torso's side),
touch (where the bar meets the body, metres up the torso from the hip line)."""
import math
from mathutils import Vector
from .stand_hinge import Pattern as Hinge, lerp, smooth
from ..contact import reach, bar_palm

X = Vector((1, 0, 0))


class Pattern(Hinge):
    def __init__(self, P, params):
        params = {"mode": "hinge", "load": "hang_bar", "hinge": 55.0, "knee": 22.0, "grip_w": 0.25,
                  "grip": "over", "elbow_out": 25.0, "touch": 0.32, **params}
        if params.get("load") == "db":
            params["load"] = "hang_db"
        super().__init__(P, params)

    def pose(self, s):
        P, p = self.P, self.p
        # hold the hinge: the parent's hinge pose at its bottom (s = 1) every frame
        self.pose_hinge(1.0, arms=False)
        body = P.delta("spine01")
        # bar contact on the lower ribs, in the hip-spine frame
        root = P.rig.pose.bones["root"].matrix
        hip = self.hip_mid()
        up = (self.shoulders() - hip).normalized()
        fwd_body = body @ Vector((0, -1, 0))
        touch = hip + up * p["touch"] + fwd_body * 0.17
        hang = self.hang_point()
        c = hang.lerp(touch, smooth(s * 1.05))
        out = {}
        for side, sgn in (("L", 1), ("R", -1)):
            g = c + X * sgn * p["grip_w"]
            arm = (g - P.head(f"upperarm01.{side}")).normalized()
            # reach at the bottom, squeeze at the top; shoulder blades stay down (no shrug)
            rh = max(0.0, P.humeral_elevation(arm) - 30.0) / 3.0
            P.scap_rhythm(side, arm, protraction=lerp(8, -18, smooth(s)), elevation=-0.3 * rh - 2 * s)
            # elbows toward the ceiling and out at elbow_out from the torso
            a = math.radians(p["elbow_out"])
            pole = body @ Vector((sgn * math.sin(a), math.cos(a), 0))
            grip = p["grip"]
            if p["load"] == "hang_db" and grip == "neutral":
                reach(P, side, g, pole, knuckle_dir=body @ Vector((0, -1, 0)),
                      palm=lambda fd, sgn=sgn: (body @ Vector((-sgn, 0, 0))))
            else:
                reach(P, side, g, pole, knuckle_dir=X * sgn,
                      palm=lambda fd, grip=grip: bar_palm(X, fd, grip))
        if p["load"] == "hang_bar":
            out["bar"] = (c, X.copy())
        return out

    def hang_point(self):
        """Bar centre with the arms hanging straight from the shoulders."""
        sh = self.shoulders()
        return Vector((0, sh.y, sh.z - self.arm_len * 0.98))
