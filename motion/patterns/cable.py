"""Standing cable work at a dual-pulley station (body facing -Y).

mode = "crossover": staggered stance, slight forward lean with a flat back, handles from
  high pulleys out to the sides. Elbows softly bent and fixed; the arms sweep down and in
  until the hands meet in front of the hips, then open back to a stretch with the hands
  level with the shoulders - a hug, not a press.
mode = "face_pull": rope from a pulley at upper-chest height, overhand (thumbs back).
  From straight arms, pull toward the face with the elbows high and wide (level with
  the shoulders), ending with the hands beside the ears (shoulders rotated out) and the
  shoulder blades squeezed; torso upright, no leaning back.

params: lean (deg), elbow (crossover fixed bend, deg), stagger (front-foot offset, m),
pulleys (crossover: x/y/z of the right-hand pulley, mirrored), pulley (face pull)."""
import math
from mathutils import Vector, Matrix
from core.solver import rot_x
from ..stance import Stance, place_pelvis, arm_lengths
from ..contact import reach

X = Vector((1, 0, 0))
Y = Vector((0, 1, 0))
Z = Vector((0, 0, 1))


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


class Pattern:
    def __init__(self, P, params):
        self.P = P
        mode = params.get("mode", "crossover")
        self.p = p = {"mode": mode, "lean": 12.0 if mode == "crossover" else 0.0, "elbow": 20.0,
                      "stagger": 0.32 if mode == "crossover" else 0.0, "stance": 0.13, "toe_out": 6.0,
                      **params}
        split = {"L": -p["stagger"] / 2, "R": p["stagger"] / 2}
        self.st = Stance(P, p["stance"], p["toe_out"], split=split)
        a = (self.st.ankles["L"] + self.st.ankles["R"]) / 2
        L = self.st.la + self.st.lb
        self.hip = Vector((0, a.y + 0.03, a.z + 0.95 * math.sqrt(L * L - (p["stagger"] / 2) ** 2)))
        self.ua, self.fa = arm_lengths(P)

    def pose(self, s):
        P, p = self.P, self.p
        place_pelvis(P, p["lean"], self.hip)
        P.local("neck02", (1, 0, 0), -0.6 * p["lean"])
        self.st.legs()
        return getattr(self, "pose_" + p["mode"])(s)

    def pose_crossover(self, s):
        P, p = self.P, self.p
        body = P.delta("spine01")
        out = {}
        for side, sgn in (("L", 1), ("R", -1)):
            sh = P.head(f"upperarm01.{side}")
            # humerus: out to the side at shoulder height (stretch) -> down and in front
            # of the hips; elbow bend fixed
            open_dir = body @ Vector((sgn, 0.15, 0.05))
            closed = body @ Vector((sgn * 0.12, -0.55, -1))
            hum = open_dir.normalized().slerp(closed.normalized(), smooth(s)).normalized()
            P.scap_rhythm(side, hum, protraction=lerp(-10, 10, smooth(s)))
            sh = P.head(f"upperarm01.{side}")
            elbow = sh + hum * self.ua
            fwd = body @ Vector((0, -1, 0))
            inward = (fwd + body @ Vector((-sgn * 0.6, 0, 0))).normalized()
            inward = (inward - inward.project(hum)).normalized()
            b = math.radians(p["elbow"])
            fdir = (hum * math.cos(b) + inward * math.sin(b)).normalized()
            g = elbow + fdir * (self.fa + 0.045)
            pole = (elbow - sh) - (elbow - sh).project(g - sh)
            reach(P, side, g, pole, knuckle_dir=body @ Vector((0, 0, -1)),
                  palm=lambda fd, sgn=sgn: (body @ Vector((-sgn*smooth(s), -(1-smooth(s)), 0))).normalized())
            out[f"handle.{side}"] = g
        return out

    def pose_face_pull(self, s):
        P, p = self.P, self.p
        body = P.delta("spine01")
        sh_mid = (P.head("upperarm01.L") + P.head("upperarm01.R")) / 2
        start = sh_mid + Vector((0, -0.95 * (self.ua + self.fa) - 0.04, 0.02))
        out = {}
        for side, sgn in (("L", 1), ("R", -1)):
            sh = P.head(f"upperarm01.{side}")
            # end: elbows out at shoulder height and a little behind, hands by the ears
            elbow_end = sh + body @ Vector((sgn * 0.85, 0.3, -0.1)).normalized() * self.ua
            hand_end = elbow_end + body @ Vector((-sgn * 0.2, -0.7, 0.75)).normalized() * (self.fa + 0.07)
            hand_start = start + X * sgn * 0.05
            g = hand_start.lerp(hand_end, smooth(s))
            arm = (g - sh).normalized()
            rh = max(0.0, P.humeral_elevation(arm) - 30.0) / 3.0
            P.scap_rhythm(side, arm, protraction=lerp(10, -18, smooth(s)), elevation=-0.3 * rh)
            pole = body @ Vector((sgn, 0.2, -0.2 + 0.4 * s))
            reach(P, side, g, pole, knuckle_dir=body @ Vector((0, 0, -1)),
                  palm=lambda fd, sgn=sgn: (body @ Vector((-sgn, 0, 0))).normalized())
            out[f"handle.{side}"] = g
        return out
