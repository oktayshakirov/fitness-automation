"""Standing lower-body pattern: squats, hip hinges (Romanian deadlift, good morning) and
pulls from the floor (deadlift).

Shared rules: feet planted (stance width, toes out), the two-bone solver bends each knee
toward its own toes (knees can't cave in or cross), flat back (pelvis and spine hinge as
one unit), neck in line with the spine. A load (bar on the back, bar or dumbbells in the
hands) always stays over mid-foot: that is the balance rule every loaded variant solves
for.

mode = "squat": hips travel back and down to the bottom (thighs parallel with
  shin_lean). Bodyweight: torso hinges to `torso`. With load "back_bar" the torso angle is
  solved every frame so the bar stays over mid-foot.
mode = "hinge" (RDL, good morning): knees unlock to `knee` deg and stay there, the hips
  push back while the torso tilts to `hinge` deg from vertical.
mode = "pull" (deadlift): s = 0 bar on the floor (plate radius), s = 1 lockout. Torso
  angle `torso` at the floor, held until the bar passes the knees, then the hips drive
  through. Arms straight and vertical, shoulders just in front of the bar at the floor.

load: "none" (arms per `arms`), "back_bar" (high-bar position, hands on the bar),
  "hang_bar" (barbell in straight arms), "hang_db" (a dumbbell in each hand).
params: stance, toe_out, shin_lean, torso, hinge, knee, grip_w (half-width of the grip,
m), grip ("over" | "under" | "mixed"), arms ("counterbalance")."""
import math
from mathutils import Vector, Matrix
from core.solver import rot_x
from ..stance import Stance, place_pelvis, arm_lengths, UP
from ..contact import reach, bar_palm, grip_point

X = Vector((1, 0, 0))


def lerp(a, b, t):
    return a + (b - a) * t


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


class Pattern:
    def __init__(self, P, params):
        self.P = P
        self.p = p = {"mode": "squat", "stance": 0.17, "toe_out": 15.0, "shin_lean": 32.0, "torso": 40.0,
                      "hinge": 75.0, "knee": 20.0, "arms": "counterbalance", "load": "none",
                      "grip_w": 0.25, "grip": "over", "plate_r": 0.225, "bar_r": 0.014, **params}
        st = self.st = Stance(P, p["stance"], p["toe_out"])
        la, lb = st.la, st.lb
        ankle = st.ankles["L"]
        self.midfoot_y = ankle.y - 0.06          # foot runs y -0.207 (toe) .. +0.056 (heel)
        # bottom: shin leaned along the toes, thigh parallel to the floor
        sl = math.radians(p["shin_lean"])
        knee_b = ankle + lb * (math.sin(sl) * st.toe["L"] + math.cos(sl) * UP)
        dx = st.hip_x - knee_b.x
        self.hip_bot = Vector((0, knee_b.y + math.sqrt(la * la - dx * dx), knee_b.z + 0.03))
        # top: legs almost straight, hips over mid-foot
        self.hip_top = Vector((0, ankle.y + 0.01, st.hip_height(0.985, 0.01)))
        if p["mode"] == "squat":
            print("HIP top", tuple(round(v, 3) for v in self.hip_top),
                  "bottom", tuple(round(v, 3) for v in self.hip_bot))
        # high-bar position, fixed in spine01's frame: on the traps above the shoulder blades
        P.reset()
        sp = P.rig.pose.bones["spine01"].matrix
        self.bar_local = sp.inverted() @ Vector((0, 0.074, 1.43))
        # goblet dumbbell: vertical, lower head against the sternum
        self.goblet_local = sp.inverted() @ Vector((0, -0.19, 1.255))
        self.arm_len = self.hang_length()

    # --- helpers ------------------------------------------------------------
    def shoulders(self):
        P = self.P
        return (P.head("upperarm01.L") + P.head("upperarm01.R")) / 2

    def hip_mid(self):
        P = self.P
        return (P.head("upperleg01.L") + P.head("upperleg01.R")) / 2

    def hang_length(self):
        """Shoulder-joint to grip-point distance with the arm hanging straight (98.5%)."""
        P = self.P
        P.reset()
        sh = P.head("upperarm01.L")
        ua, fa = arm_lengths(P)
        P.limb("upperarm01.L", "lowerarm01.L", "wrist.L", sh + Vector((0.02, 0, -1)).normalized() * 0.985 * (ua + fa),
               Vector((0, 1, 0)), palm=Vector((0, 1, 0)), side="L")
        P.curl_fingers("L")
        P.hand_orient("L", X, Vector((0, 1, 0)))
        g, _ = grip_point(P, "L")
        L = (g - sh).length
        P.reset()
        return L

    def torso_offset(self, tilt, fn):
        """Vector from the hip-joint midpoint to fn() with the pelvis tilted."""
        place_pelvis(self.P, tilt, self.hip_top)
        return fn() - self.hip_mid()

    def back_set(self, tilt):
        """Flat back under load: chest up (upper spine extended against the rest-pose
        curve), neck in line with the spine, gaze a little ahead on the floor."""
        P = self.P
        P.local("spine02", (1, 0, 0), -0.10 * tilt)
        P.local("spine01", (1, 0, 0), -0.12 * tilt)
        P.local("neck02", (1, 0, 0), -0.22 * tilt)
        P.local("head", (1, 0, 0), -0.12 * tilt)
        if self.p["load"] in ("hang_bar", "hang_db") or self.p["mode"] == "pull":
            # lats on, shoulder blades set back; arms hang straight down
            for side in ("L", "R"):
                P.scap_rhythm(side, Vector((0, 0, -1)), protraction=-8)

    # --- pose -----------------------------------------------------------------
    def pose(self, s):
        mode = self.p["mode"]
        if mode == "squat":
            out = self.pose_squat(s)
        elif mode == "hinge":
            out = self.pose_hinge(s)
        else:
            out = self.pose_pull(s)
        return out

    def pose_squat(self, s):
        P, p = self.P, self.p
        back = 1 - (1 - s) ** 1.6          # hips travel back early, like a hip hinge
        top, bot = self.hip_top, self.hip_bot
        hip = Vector((0, top.y + (bot.y - top.y) * back, top.z + (bot.z - top.z) * s))
        if p["load"] == "back_bar":
            tilt = self.balance_tilt(hip, lambda: P.rig.pose.bones["spine01"].matrix @ self.bar_local)
        else:
            tilt = 3 + (p["torso"] - 3) * s
        if p["load"] == "back_bar":
            self.back_set(tilt)
        place_pelvis(P, tilt, hip)
        if p["load"] == "back_bar":
            self.st.legs()
            return self.arms_back_bar()
        if p["load"] == "goblet":
            P.local("spine01", (1, 0, 0), -0.12 * tilt)
            P.local("neck02", (1, 0, 0), -0.3 * tilt)
            P.local("head", (1, 0, 0), -0.2 * tilt)
            self.st.legs()
            return self.arms_goblet()
        # neutral spine, chest up, eyes forward
        P.local("spine02", (1, 0, 0), -4 * s)
        P.local("spine01", (1, 0, 0), -5 * s)
        k = p["torso"] / 40.0              # gaze stays level whatever the torso angle
        P.local("neck02", (1, 0, 0), -12 * s * k)
        P.local("head", (1, 0, 0), -14 * s * k)
        self.st.legs()
        if p["arms"] == "counterbalance":
            self.arms_counterbalance(s)
        return {}

    def balance_tilt(self, hip, fn, lo=0.0, hi=75.0):
        """Torso tilt (deg) that puts fn() (a point fixed on the torso) over mid-foot."""
        P = self.P
        for _ in range(24):
            mid = (lo + hi) / 2
            self.back_set(mid)
            place_pelvis(P, mid, hip)
            if fn().y > self.midfoot_y:      # load behind mid-foot: lean further forward
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    def pose_hinge(self, s):
        """RDL / good morning: fixed soft knee, hips back, torso to `hinge` deg."""
        P, p, st = self.P, self.p, self.st
        tilt = 3 + (p["hinge"] - 3) * s
        knee = lerp(8.0, p["knee"], smooth(s / 0.3))          # unlock the knees first
        k = math.radians(180 - knee)
        leg = math.sqrt(st.la ** 2 + st.lb ** 2 - 2 * st.la * st.lb * math.cos(k))
        ankle = st.ankles["L"]
        dx = st.hip_x - ankle.x
        self.back_set(tilt)
        if p["load"] == "back_bar":
            anchor = lambda: P.rig.pose.bones["spine01"].matrix @ self.bar_local
            want_y = self.midfoot_y - 0.02        # bar a touch ahead: hips sit far back
        else:
            anchor = self.shoulders
            # shoulders over the bar: behind it while the bar rests on the thighs, just in
            # front of it at the bottom
            u = (tilt - 3) / max(1.0, p["hinge"] - 3)
            self._u = u
            want_y = self.midfoot_y - 0.02 + lerp(0.07, -0.03, smooth(u * 1.4))
        off = self.torso_offset(tilt, anchor)
        hy = want_y - off.y
        dy = hy - ankle.y
        hz = ankle.z + math.sqrt(max(0.0, leg * leg - dx * dx - dy * dy))
        place_pelvis(P, tilt, Vector((0, hy, hz)))
        st.legs()
        if p["load"] == "back_bar":
            return self.arms_back_bar()
        return self.arms_hang()

    def bar_y(self):
        if self.p["load"] == "hang_db":
            # dumbbell heads are fat: in front of the thighs at the top, back over
            # mid-foot as the hips hinge and the thighs lean away
            u = getattr(self, "_u", 0.0)
            return self.midfoot_y - lerp(0.11, 0.03, smooth(u * 1.3))
        return self.midfoot_y - 0.02

    def pose_pull(self, s):
        """Deadlift from the floor: s = 0 bar on the floor, 1 = lockout."""
        P, p, st = self.P, self.p, self.st
        z0 = p["plate_r"]
        # lockout: standing tall, bar against the thighs, arms straight
        self.back_set(1.0)
        off0 = self.torso_offset(1.0, self.shoulders)
        sh_top = self.hip_top + off0
        dy_top = sh_top.y - self.bar_y()
        z1 = sh_top.z - math.sqrt(self.arm_len ** 2 - dy_top ** 2)
        zb = lerp(z0, z1, s)
        h = (zb - z0) / (z1 - z0)
        # torso angle: held (slight rise) until the bar passes the knees, then hips through
        knee_h = 0.42
        t0 = p["torso"]
        if h < knee_h:
            tilt = lerp(t0, t0 - 10, h / knee_h)
        else:
            tilt = lerp(t0 - 10, 1.0, smooth((h - knee_h) / (1 - knee_h)))
        dy = lerp(-0.03, dy_top, smooth(h))     # shoulders just in front of the bar at the floor
        sh_z = zb + math.sqrt(max(0.0, self.arm_len ** 2 - dy * dy))
        self.back_set(tilt)
        off = self.torso_offset(tilt, self.shoulders)
        hip = Vector((0, self.bar_y() + dy - off.y, sh_z - off.z))
        place_pelvis(P, tilt, hip)
        st.legs()
        return self.arms_hang(zb)

    # --- arms -----------------------------------------------------------------
    def arms_hang(self, zb=None):
        """Straight arms hanging from the shoulders to a bar (or two dumbbells) held at
        bar_y over mid-foot."""
        P, p = self.P, self.p
        sh = self.shoulders()
        if zb is None:
            dy = sh.y - self.bar_y()
            zb = sh.z - math.sqrt(max(0.0, self.arm_len ** 2 - dy * dy))
        c = Vector((0, self.bar_y(), zb))
        body = P.delta("spine01")
        for side, sgn in (("L", 1), ("R", -1)):
            g = c + X * sgn * p["grip_w"]
            grip = p["grip"] if p["grip"] != "mixed" else ("over" if side == "R" else "under")
            pole = body @ Vector((sgn * 0.4, 1, 0))           # elbows point back and out
            reach(P, side, g, pole, knuckle_dir=X * sgn,
                  palm=lambda fd, grip=grip: bar_palm(X, fd, grip))
        return {"bar": (c, X.copy())}

    def arms_back_bar(self):
        """High-bar back squat grip: hands just outside the shoulders, elbows down and
        back, shoulder blades squeezed."""
        P, p = self.P, self.p
        c = P.rig.pose.bones["spine01"].matrix @ self.bar_local
        body = P.delta("spine01")
        axis = (body @ X)
        axis = Vector((axis.x, axis.y, 0)).normalized()
        for side, sgn in (("L", 1), ("R", -1)):
            g = c + axis * sgn * p["grip_w"]
            arm = (g - P.head(f"upperarm01.{side}")).normalized()
            # retracted and slightly depressed: cancel the rhythm's shrug, then -3 deg
            rh = max(0.0, P.humeral_elevation(arm) - 30.0) / 3.0
            P.scap_rhythm(side, arm, protraction=-14, elevation=-0.2 * rh - 2)
            pole = body @ Vector((sgn * 0.3, 0.6, -1))
            reach(P, side, g, pole, knuckle_dir=axis * sgn,
                  palm=lambda fd: bar_palm(axis, fd, "over"))
        return {"bar": (c, axis)}

    def arms_goblet(self):
        """One dumbbell held vertically at the chest, both palms cupping the underside of
        the top head, elbows down and close (inside the knees at the bottom)."""
        P = self.P
        sp = P.rig.pose.bones["spine01"].matrix
        c = sp @ self.goblet_local
        body = P.delta("spine01")
        up = Vector((0, 0, 1))
        axis = (0.6 * (body @ up) + 0.4 * up).normalized()     # between torso-up and vertical
        to_chest = body @ Vector((0, 1, 0))
        for side, sgn in (("L", 1), ("R", -1)):
            lat = body @ Vector((sgn, 0, 0))
            g = c + axis * 0.05 + lat * 0.042 - to_chest * 0.01
            arm = (g - P.head(f"upperarm01.{side}")).normalized()
            P.scap_rhythm(side, arm, protraction=4)
            palm = (axis * 0.9 - lat * 0.4).normalized()
            P.curl_fingers(side, deg=(25, 35, 25), thumb=(10, 20, 15))
            reach(P, side, g, body @ Vector((sgn * 0.5, 0.3, -1)), knuckle_dir=to_chest, palm=palm, fist=False)
            P.curl_fingers(side, deg=(25, 35, 25), thumb=(10, 20, 15))
        return {"db": (c, axis)}

    def arms_counterbalance(self, s):
        """Arms from hanging to shoulder height, palms down, straight."""
        P = self.P
        for side, sgn in (("L", 1), ("R", -1)):
            e = math.radians(12 + 76 * s)
            sh = P.head(f"upperarm01.{side}")
            d = Vector((sgn * 0.12, -math.sin(e), -math.cos(e))).normalized()
            ua, fa = arm_lengths(P, side)
            P.limb(f"upperarm01.{side}", f"lowerarm01.{side}", f"wrist.{side}", sh + d * 0.985 * (ua + fa),
                   Vector((sgn, 0.3, -0.4)), palm=Vector((0, 0.15, -1)), side=side)
