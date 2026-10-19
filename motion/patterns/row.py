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
from ..contact import reach, bar_palm, knuckles, grip_point
from .floor import Pattern as Floor, palm_point
from ..stance import arm_lengths
from core.solver import rot_x, rot_z

X = Vector((1, 0, 0))


class BentOver(Hinge):
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
                reach(P, side, g, pole, knuckle_dir=knuckles(sgn, grip),
                      palm=lambda fd, grip=grip: bar_palm(X, fd, grip))
        if p["load"] == "hang_bar":
            out["bar"] = (c, X.copy())
        return out

    def hang_point(self):
        """Bar centre with the arms hanging straight from the shoulders."""
        sh = self.shoulders()
        return Vector((0, sh.y, sh.z - self.arm_len * 0.98))


class OneArmBench(Floor):
    """One-arm dumbbell row with the same-side knee and hand on a flat bench (head
    toward -Y). The bench runs along Y under the support side; the working side's foot
    is planted on the floor, knee soft. Torso nearly parallel to the floor, square to
    it (no twist), flat back, neck in line. The dumbbell hangs under the shoulder, then
    the elbow drives back past the torso until the bell reaches the hip; the shoulder
    blade reaches at the bottom and squeezes back at the top."""

    def __init__(self, P, params):
        self.base_z = params.get("bench_z", 0.43)
        p = {"mode": "row_bench", "work": "R", "bench_x": 0.13, **params}
        super().__init__(P, p)
        self.p = p
        P = self.P
        ua, fa = arm_lengths(P)
        self.ua, self.fa = ua, fa
        self.la = (P.rest_head("lowerleg01.L") - P.rest_head("upperleg01.L")).length
        self.lb = (P.rest_head("foot.L") - P.rest_head("lowerleg01.L")).length
        sup = "L" if p["work"] == "R" else "R"
        self.sup, self.wk = sup, p["work"]
        sg = 1 if sup == "L" else -1
        self.sgn_sup = sg
        bz = self.base_z
        # support knee on the pad under the hip, shin back along the bench
        self.hip_z = bz + 0.055 + self.la * 0.99
        self.hip_y = 0.0
        self.knee_pad = Vector((sg * p["bench_x"], self.hip_y, bz + 0.055))
        self.hand_pad = Vector((sg * (p["bench_x"] + 0.04), -0.62, bz + 0.004))
        self.foot = Vector((-sg * 0.30, self.hip_y - 0.05, P.rest_head("foot.L").z))
        # torso pitch: the support arm is straight down to the pad
        # Flat hands extend along the pad, not another 7 cm down the arm.
        wrist_contact = self.hand_pad + Vector((0, .04, .024))
        f = lambda t: (self.place(t), (self.P.head(f"upperarm01.{sup}") - wrist_contact).length)[1]
        self.tilt = self.bisect(f, 50.0, 100.0, 0.985 * (ua + fa))

    def solve_supine(self):
        pass

    def place(self, tilt):
        P = self.P
        P.reset()
        hip = Vector((0, self.hip_y, self.hip_z))
        from ..stance import place_pelvis
        place_pelvis(P, tilt, hip)
        P.local("neck02", (1, 0, 0), -0.2 * tilt)           # neck in line, eyes down
        P.local("head", (1, 0, 0), -0.05 * tilt)

    def pose(self, s):
        P, p = self.P, self.p
        self.place(self.tilt)
        sup, wk, sg = self.sup, self.wk, self.sgn_sup
        # support leg: knee on the pad, shin along the bench, foot off the end
        ank = self.knee_pad + Vector((0, self.lb * 0.98, 0.015))
        P.limb(f"upperleg01.{sup}", f"lowerleg01.{sup}", f"foot.{sup}", ank, Vector((0, 0, -1)))
        P.set_world(f"foot.{sup}", rot_x(150) @ P.rest3(f"foot.{sup}"))   # top of the foot down
        # working-side leg: foot flat on the floor, knee soft
        P.limb(f"upperleg01.{wk}", f"lowerleg01.{wk}", f"foot.{wk}", self.foot, Vector((-sg * 0.3, -1, 0)))
        P.set_world(f"foot.{wk}", rot_z(-sg * 10) @ P.rest3(f"foot.{wk}"))
        # support arm straight to the pad, hand flat
        P.scap_rhythm(sup, (self.hand_pad - P.head(f"upperarm01.{sup}")).normalized())
        self.hand_flat(sup, sg, self.hand_pad, Vector((sg, 1, 0)))
        # working arm: hang -> bell at the hip
        sh = P.head(f"upperarm01.{wk}")
        hang = Vector((sh.x - sg * 0.02, sh.y, sh.z - (0.995 * (self.ua + self.fa) + 0.115)))
        hipj = P.head(f"upperleg01.{wk}")
        top = Vector((hipj.x - sg * 0.17, hipj.y - 0.16, hipj.z - 0.1))
        g = hang.lerp(top, smooth(s))
        g.x -= sg * 0.035 * math.sin(math.pi * smooth(s))    # bell arcs around the thigh
        arm = (g - sh).normalized()
        rh = max(0.0, P.humeral_elevation(arm) - 30.0) / 3.0
        P.scap_rhythm(wk, arm, protraction=lerp(10, -18, smooth(s)), elevation=-0.3 * rh)
        # The reaching shoulder moves down; derive the extended hand target after
        # girdle placement so the starting elbow does not stay flexed by 60 degrees.
        g.z -= (1 - smooth(s)) * 0.028
        wsg = -sg
        # neutral grip: palm faces the body, thumb toward the head
        reach(P, wk, g, Vector((wsg * 0.15, 0.3, 1.0)), knuckle_dir=Vector((0, 1, 0)),
              palm=lambda fd: Vector((-wsg, 0, 0)), mode="wrapped")
        return {}


def Pattern(P, params):
    if params.get("style") == "one_arm_bench":
        return OneArmBench(P, params)
    return BentOver(P, params)
