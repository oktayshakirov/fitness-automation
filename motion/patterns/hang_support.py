"""Hanging and support on bars: pull-up / chin-up, hanging knee raise, parallel-bar dip.

The hands are fixed on the bar(s); the body is placed from them.

mode = "pullup": dead hang (arms straight, shoulder blades up) -> pull until the chin
  clears the bar, shoulder blades down and back, chest toward the bar, a slight lean
  back; legs hang long with soft knees, no swing. grip "over" (pull-up) or "under"
  (chin-up).
mode = "knee_raise": dead hang held; knees drawn up to hip height (hips ~100 deg,
  knees ~90 deg) with the pelvis curling under; no swing.
mode = "dip": support on parallel bars, arms straight, shoulders down; lower until the
  upper arms are parallel to the floor, elbows travelling back, torso leaning forward a
  little; knees bent, feet behind.

params: bar_z (bar height, m), grip_w (hand half-width), lean (deg forward at the
bottom of a dip / back at the top of a pull-up), grip, top_y / top_z (shoulder midpoint
behind / below the bar at the top of a pull-up, m)."""
import math
from mathutils import Vector, Matrix
from core.solver import rot_x
from ..stance import place_pelvis, arm_lengths
from ..contact import reach, bar_palm, grip_point, knuckles

X = Vector((1, 0, 0))
Y = Vector((0, 1, 0))


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


class Pattern:
    def __init__(self, P, params):
        self.P = P
        mode = params.get("mode", "pullup")
        self.p = p = {"mode": mode, "bar_z": 2.25 if mode != "dip" else 1.25,
                      "grip_w": 0.32 if mode != "dip" else 0.25, "grip": "over",
                      "lean": 10.0 if mode != "dip" else 18.0, "top_y": 0.07, "top_z": 0.12, **params}
        ua, fa = arm_lengths(P)
        self.ua, self.fa = ua, fa
        self.root_rest = P.rest_head("root")
        self.hands = {s: Vector((sg * p["grip_w"], 0.0, p["bar_z"])) for s, sg in (("L", 1), ("R", -1))}
        # straight-arm reach from the shoulder joint to the grip point
        self.arm = 0.985 * (ua + fa) + (0.075 if mode != "dip" else 0.05)

    def shoulders(self):
        P = self.P
        return (P.head("upperarm01.L") + P.head("upperarm01.R")) / 2

    def place(self, tilt, sh_target, girdle):
        """Torso pitched by tilt (deg, + = forward), girdle(side, arm_dir) applied, then
        the body moved so the shoulder midpoint lands on sh_target."""
        P = self.P
        R = rot_x(tilt) @ P.rest3("root")
        base = self.root_rest.copy()
        for _ in range(4):
            P.set_world("root", R, base)
            for side in ("L", "R"):
                girdle(side, (self.hands[side] - P.head(f"upperarm01.{side}")).normalized())
            d = sh_target - self.shoulders()
            base = base + d
            if d.length < 1e-4:
                break
        P.set_world("root", R, base)

    def legs_hanging(self, hip_flex=8.0, knee=12.0):
        """Legs hang under the hips, thighs hip_flex deg forward, knees bent knee deg."""
        P = self.P
        body = P.delta("root")
        for side, sgn in (("L", 1), ("R", -1)):
            h = P.head(f"upperleg01.{side}")
            la = (P.rest_head(f"lowerleg01.{side}") - P.rest_head(f"upperleg01.{side}")).length
            lb = (P.rest_head(f"foot.{side}") - P.rest_head(f"lowerleg01.{side}")).length
            down = body @ Vector((sgn * 0.03, 0, -1)).normalized()
            fwd = body @ Vector((0, -1, 0))
            th = (down * math.cos(math.radians(hip_flex)) + fwd * math.sin(math.radians(hip_flex))).normalized()
            k = h + th * la
            a = math.radians(hip_flex - knee)          # shin angle forward of vertical
            sh_dir = (down * math.cos(a) + fwd * math.sin(a)).normalized()
            ank = k + sh_dir * lb
            P.limb(f"upperleg01.{side}", f"lowerleg01.{side}", f"foot.{side}", ank, fwd)
            # relaxed feet, toes pointing down a little
            P.set_world(f"foot.{side}", P.delta(f"lowerleg01.{side}") @ rot_x(25) @ P.rest3(f"foot.{side}"))

    def grip(self, side, sgn, pole, mode="hook", grip=None, knuckle=None):
        P, p = self.P, self.p
        g = grip or p["grip"]
        if p["mode"] == "dip":
            reach(P, side, self.hands[side], pole, knuckle_dir=knuckle,
                  palm=lambda fd: Vector((-sgn, 0, 0)), mode="press")
        else:
            reach(P, side, self.hands[side], pole, knuckle_dir=knuckles(sgn, g),
                  palm=lambda fd, g=g: bar_palm(X, fd, g), mode=mode)

    def pose(self, s):
        return getattr(self, "pose_" + self.p["mode"])(s)

    def hang_shoulders(self):
        """Shoulder midpoint in a dead hang: arms straight, hands on the bar."""
        p = self.p
        dx = p["grip_w"] - 0.2
        return Vector((0, 0.03, p["bar_z"] - math.sqrt(self.arm ** 2 - dx * dx)))

    def pose_pullup(self, s):
        P, p = self.P, self.p
        bot = self.hang_shoulders()
        top = Vector((0, p["top_y"], p["bar_z"] - p["top_z"]))   # chin to the bar, chest toward it
        sh = bot.lerp(top, smooth(s))
        tilt = -p["lean"] * smooth(s)                        # lean back toward the top

        def girdle(side, arm):
            # dead hang: blades up and rotated with the arms; top: down and back
            P.scap_rhythm(side, arm, protraction=lerp(4, -16, s), elevation=lerp(6, -8, smooth(s)))
        self.place(tilt, sh, girdle)
        P.local("neck02", (1, 0, 0), lerp(0, -6, smooth(s)))       # eyes to the bar
        self.legs_hanging(hip_flex=lerp(6, 14, s), knee=lerp(10, 25, s))
        for side, sgn in (("L", 1), ("R", -1)):
            pole = Vector((sgn, -0.35, -0.4))
            self.grip(side, sgn, pole)
        return {"bar": ((self.hands["L"] + self.hands["R"]) / 2, X.copy())}

    def pose_knee_raise(self, s):
        P, p = self.P, self.p
        sh = self.hang_shoulders()

        def girdle(side, arm):
            P.scap_rhythm(side, arm, protraction=0, elevation=-2)   # active hang
        self.place(0.0, sh, girdle)
        # pelvis curls under as the knees come up (posterior tilt), torso stays put
        curl = 18 * smooth(s)
        P.local("spine05", (1, 0, 0), 0.0)
        root = P.rig.pose.bones["root"].matrix.copy()
        P.set_world("root", rot_x(-curl) @ root.to_3x3(), root.translation)
        P.local("spine05", (1, 0, 0), curl * 0.6)
        P.local("spine04", (1, 0, 0), curl * 0.4)
        self.legs_hanging(hip_flex=lerp(4, 95, smooth(s)), knee=lerp(8, 95, smooth(s)))
        for side, sgn in (("L", 1), ("R", -1)):
            self.grip(side, sgn, Vector((sgn, -0.2, -0.3)))
        return {"bar": ((self.hands["L"] + self.hands["R"]) / 2, X.copy())}

    def pose_dip(self, s):
        P, p = self.P, self.p
        dx = p["grip_w"] - 0.19
        top = Vector((0, 0.02, p["bar_z"] + math.sqrt(self.arm ** 2 - dx * dx)))
        # bottom: upper arm parallel to the floor, elbow over the hand, a little behind
        bot = Vector((0, -0.10, p["bar_z"] + self.fa + 0.05))
        sh = top.lerp(bot, smooth(s))
        tilt = lerp(5, p["lean"], smooth(s))

        def girdle(side, arm):
            # shoulders pressed down (depressed) at the top; a little forward at the bottom
            P.scap_rhythm(side, arm, protraction=lerp(-4, 8, s), elevation=lerp(-10, -4, s))
        self.place(tilt, sh, girdle)
        P.local("neck02", (1, 0, 0), 4)
        self.legs_hanging(hip_flex=-5, knee=80)
        for side, sgn in (("L", 1), ("R", -1)):
            pole = Vector((sgn * 0.35, 1.0, 0.0))                 # elbows back
            self.grip(side, sgn, pole, knuckle=Y.copy())
        return {"dip": (self.hands["L"], self.hands["R"])}
