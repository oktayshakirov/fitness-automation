"""Lying on a flat bench (head toward +Y): bench press (barbell / dumbbells), dumbbell
fly, skull crusher.

Set-up shared by all: head, upper back and glutes on the pad, a small natural arch in
the lower back, shoulder blades pulled back and down for the whole set, feet flat on
the floor a little wider than the bench, knees bent about 90 deg.

mode = "press": bar (or dumbbells) from straight arms over the shoulders down to the
  chest, forearms vertical, elbows ~50-70 deg from the torso; pressed back up in
  a slight arc toward the shoulders.
mode = "fly": dumbbells start over the chest, palms facing; arms open in a wide arc
  with the elbows softly bent and fixed until the upper arms are level with the
  bench, then hug back up.
mode = "skull_crusher": upper arms fixed, angled slightly back toward the head; only
  the elbows bend, lowering the bar to just above the forehead.

params: load ("bar" | "db"), grip_w, bench_z (pad top, m), arch (deg of lower-back
extension), elbow (fly: fixed elbow bend, deg), feet_w (ankle half-width)."""
import math
from mathutils import Vector
from core.solver import rot_x, rot_z
from .floor import Pattern as Floor, smooth, lerp
from ..stance import arm_lengths
from ..contact import reach, bar_palm, knuckles

X = Vector((1, 0, 0))
Y = Vector((0, 1, 0))
Z = Vector((0, 0, 1))


class Pattern(Floor):
    def __init__(self, P, params):
        self.base_z = params.get("bench_z", 0.43)
        self.back_y = 0.0
        params = {"mode": "press", "load": "bar", "grip_w": 0.28, "arch": 6.0, "elbow": 22.0,
                  "feet_w": 0.27, "feet": 0.42, **params}
        mode = params["mode"]
        params["mode"] = "supine_bench"
        super().__init__(P, params)
        self.p["mode"] = mode
        ua, fa = arm_lengths(P)
        self.ua, self.fa = ua, fa
        self.ankles = {s: Vector((sg * self.p["feet_w"], a.y, a.z)) for (s, a), sg in
                       zip(self.ankles.items(), (1, -1))}

    def solve_prone(self):
        pass

    def body(self):
        """Lie on the bench with a small arch; legs to the floor."""
        P, p = self.P, self.p
        self.supine(self.phi_floor)
        P.local("spine03", (1, 0, 0), -p["arch"] * 0.5)          # lower back arch
        P.local("spine04", (1, 0, 0), -p["arch"] * 0.5)
        P.local("neck02", (1, 0, 0), 4)
        for side, sgn in (("L", 1), ("R", -1)):
            P.limb(f"upperleg01.{side}", f"lowerleg01.{side}", f"foot.{side}", self.ankles[side],
                   Vector((sgn * 0.6, 0, 1)))
            P.set_world(f"foot.{side}", rot_z(sgn * 15) @ P.rest3(f"foot.{side}"))

    def shoulders(self):
        P = self.P
        return (P.head("upperarm01.L") + P.head("upperarm01.R")) / 2

    def pose(self, s):
        self.body()
        return getattr(self, "pose_" + self.p["mode"])(s)

    def girdle(self, side, target):
        P = self.P
        arm = (target - P.head(f"upperarm01.{side}")).normalized()
        rh = max(0.0, P.humeral_elevation(arm) - 30.0) / 3.0
        P.scap_rhythm(side, arm, protraction=-12, elevation=-0.3 * rh - 3)   # back and down

    def pose_press(self, s):
        P, p = self.P, self.p
        sh = self.shoulders()
        height=.94*(self.ua+self.fa)+.03
        if P.rest_head('upperarm01.L').x<.17 and p['load']=='bar':
            height=math.sqrt((.92*(self.ua+self.fa))**2-(p['grip_w']-P.head('upperarm01.L').x)**2)+.03
        top = Vector((0, sh.y - 0.01, sh.z+height))
        chest = self.lm["chest"]
        # +Y is toward the head. Keep the bottom position on the chest rather
        # than subtracting a fixed offset toward the abdomen for every press.
        bot = Vector((0, chest.y + p.get("chest_offset_y", -0.07),
                      chest.z + p.get("chest_clearance", 0.03)))
        # slight J-curve: the bar drifts toward the feet as it comes down
        c = Vector((0, lerp(top.y, bot.y, smooth(s) ** 0.7), lerp(top.z, bot.z, smooth(s))))
        out = {}
        for side, sgn in (("L", 1), ("R", -1)):
            w = p["grip_w"] if p["load"] == "bar" else lerp(0.17, 0.31, smooth(s))
            g = c + X * sgn * w
            if p["load"] == "db":
                g = g + Vector((0, 0, -0.01))
            self.girdle(side, g)
            pole = Vector((sgn * 0.75, -0.45, -1.0))               # elbows down, ~60 deg out
            reach(P, side, g, pole, knuckle_dir=knuckles(sgn, "over"),
                  palm=lambda fd: bar_palm(X, fd, "over"), mode="press" if p["load"] == "bar" else "hook")
        if p["load"] == "bar":
            out["bar"] = (c, X.copy())
        return out

    def pose_fly(self, s):
        P, p = self.P, self.p
        sh0 = self.shoulders()
        for side, sgn in (("L", 1), ("R", -1)):
            sh = P.head(f"upperarm01.{side}")
            # humerus swings from vertical to level, out to the side (a bit toward the feet)
            a = math.radians(lerp(8, 88, smooth(s)))
            out = Vector((sgn, -0.18, 0)).normalized()
            hum = (Z * math.cos(a) + out * math.sin(a)).normalized()
            self.girdle(side, sh + hum)
            sh = P.head(f"upperarm01.{side}")
            elbow = sh + hum * self.ua
            # soft elbow: forearm tips in, toward the midline, by the fixed bend
            b = math.radians(p["elbow"])
            inward = (Vector((-sgn, 0, 0)) - Vector((-sgn, 0, 0)).project(hum)).normalized()
            fdir = (hum * math.cos(b) + inward * math.sin(b)).normalized()
            wrist = elbow + fdir * self.fa
            palm = inward
            pole = (elbow - sh) - (elbow - sh).project(wrist - sh)
            P.limb(f"upperarm01.{side}", f"lowerarm01.{side}", f"wrist.{side}", wrist, pole, palm=palm, side=side)
            P.curl_fingers(side)
        return {}

    def pose_skull_crusher(self, s):
        P, p = self.P, self.p
        out = {}
        sh = self.shoulders()
        # upper arms fixed, tipped ~12 deg toward the head; forearms fold back to the forehead
        tip = math.radians(12)
        hum_dir = Vector((0, math.sin(tip), math.cos(tip)))
        flex = lerp(8, 118, smooth(s))
        cs = []
        for side, sgn in (("L", 1), ("R", -1)):
            shs = P.head(f"upperarm01.{side}")
            hd = (hum_dir + Vector((-sgn * 0.12, 0, 0))).normalized()
            self.girdle(side, shs + hd)
            shs = P.head(f"upperarm01.{side}")
            elbow = shs + hd * self.ua
            fdir = rot_x(flex) @ hd
            cs.append(elbow + fdir * (self.fa + 0.06))
        c = (cs[0] + cs[1]) / 2
        for side, sgn in (("L", 1), ("R", -1)):
            g = c + X * sgn * p["grip_w"]
            reach(P, side, g, Vector((sgn * 0.15, -0.3, 1.0)), knuckle_dir=knuckles(sgn, "over"),
                  palm=lambda fd: bar_palm(X, fd, "over"))
        out["bar"] = (c, X.copy())
        return out
