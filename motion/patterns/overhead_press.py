"""Standing overhead press: barbell (strict press) or two dumbbells.

Feet planted hip-width, legs straight, glutes and abs braced. The load travels in a
vertical line over mid-foot. Barbell: starts in the front rack on the front delts,
forearms vertical, elbows a little in front of the bar; the torso leans back a few
degrees so the bar stays over mid-foot, the head moves back as the bar passes the face,
then "head through" at lockout with the bar over the shoulders and mid-foot, arms
locked, shoulder blades rotated up (a slight shrug at the top). Dumbbells: start beside
the head at shoulder height, palms forward, elbows under the wrists in the scapular
plane, press up and slightly in until the arms are straight over the shoulders.

params: load ("bar" | "db"), grip_w (bar half-width / dumbbell start half-width, m),
stance, toe_out, lean (deg back at the start), rack_z (bar height in the rack, m)."""
import math
from mathutils import Vector
from ..stance import Stance, place_pelvis, arm_lengths
from ..contact import reach, bar_palm, grip_point

X = Vector((1, 0, 0))


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


class Pattern:
    def __init__(self, P, params):
        self.P = P
        self.p = p = {"load": "bar", "grip_w": 0.26, "stance": 0.12, "toe_out": 8.0, "lean": 5.0,
                      "rack_z": 1.47, "top_reach": 0.945, "db_top_w": 0.16, **params}
        self.st = Stance(P, p["stance"], p["toe_out"])
        a = self.st.ankles["L"]
        self.midfoot_y = a.y - 0.06
        self.hip_z = self.st.hip_height(0.99, 0.0)
        ua, fa = arm_lengths(P)
        self.reach = ua + fa

    def shoulders(self):
        P = self.P
        return (P.head("upperarm01.L") + P.head("upperarm01.R")) / 2

    def place_body(self, tilt, sh_y):
        """Lean back by tilt and shift the hips so the shoulder midpoint sits at sh_y."""
        P = self.P
        hip = Vector((0, self.st.ankles["L"].y + 0.01, self.hip_z))
        place_pelvis(P, -tilt, hip)
        dy = sh_y - self.shoulders().y
        place_pelvis(P, -tilt, hip + Vector((0, dy, 0)))

    def pose(self, s):
        P, p = self.P, self.p
        tilt = p["lean"] * (1 - smooth(s * 1.2))
        bar_y = self.midfoot_y
        # shoulders behind the bar in the rack, under it at lockout
        self.place_body(tilt, bar_y + lerp(0.13 if p["load"] == "bar" else 0.0, 0.0, smooth(s)))
        sh = self.shoulders()
        # head back while the bar passes the face, through at lockout
        z_top = sh.z + 0.14 + p["top_reach"] * self.reach      # + girdle lift + hand
        z = lerp(p["rack_z"], z_top, s)
        face = smooth((z - 1.40) / 0.12) * (1 - smooth((z - 1.62) / 0.12))
        P.local("neck02", (1, 0, 0), -9 * face + 5 * smooth((s - 0.8) / 0.2))
        P.local("head", (1, 0, 0), -6 * face)
        self.st.legs()
        if p["load"] == "bar":
            return self.arms_bar(Vector((0, bar_y, z)), s)
        return self.arms_db(s, z)

    def girdle(self, side, g, s):
        P = self.P
        arm = (g - P.head(f"upperarm01.{side}")).normalized()
        # upward rotation follows the arm; a small active shrug at lockout
        if self.p["load"] == "db":
            upward = max(0.0, P.humeral_elevation(arm) - 30.0) / 3.0
            P.girdle(side, elevation=.3 * upward + 4 * smooth((s - .75) / .25),
                     protraction=2, upward=upward)
        else:
            P.scap_rhythm(side, arm, protraction=2, elevation=4 * smooth((s - 0.75) / 0.25))

    def arms_bar(self, c, s):
        P, p = self.P, self.p
        body = P.delta("spine01")
        for side, sgn in (("L", 1), ("R", -1)):
            g = c + X * sgn * p["grip_w"]
            self.girdle(side, g, s)
            # elbows down and a little forward in the rack, out to the side at lockout
            pole = body @ Vector((sgn * lerp(0.3, 0.6, s), -0.4, -1.0))
            reach(P, side, g, pole, knuckle_dir=X * sgn,
                  palm=lambda fd: bar_palm(X, fd, "over"), mode="press")
        return {"bar": (c, X.copy())}

    def arms_db(self, s, z):
        P, p = self.P, self.p
        body = P.delta("spine01")
        for side, sgn in (("L", 1), ("R", -1)):
            # start: bells at ear level, forearms vertical over elbows just below
            # shoulder height (scapular plane); top: arms straight over the shoulders
            x = lerp(p["grip_w"], p["db_top_w"], smooth(s))
            g = Vector((sgn * x, self.midfoot_y - lerp(0.03, 0.0, s), z))
            self.girdle(side, g, s)
            # The scapula raises the shoulder joint. Derive the terminal reach
            # from that posed joint instead of the pre-girdle shoulder height.
            terminal_z = P.head(f"upperarm01.{side}").z + .985 * self.reach + .115
            g.z = lerp(g.z, terminal_z, smooth(s))
            pole = body @ Vector((sgn, -0.8, -0.6))
            reach(P, side, g, pole, knuckle_dir=X * sgn,
                  palm=lambda fd: bar_palm(X, fd, "over"))
        return {}
