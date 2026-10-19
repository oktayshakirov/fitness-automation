"""Floor exercises (bodyweight), head toward -Y when prone, toward +Y when supine.

mode = "pushup": rigid plank from head to heels pivoting on the tucked toes; hands flat
  under the shoulders (a little wider), fingers forward; chest lowers to `depth` m off
  the floor with the elbows ~45 deg from the torso, then presses back to straight arms.
mode = "plank": forearm plank, elbows under the shoulders, forearms parallel, body in a
  straight line; a static hold (the loop only breathes).
mode = "bridge": glute bridge. Lying on the back, knees bent, feet flat hip-width,
  arms on the floor palms down. The hips lift until shoulders, hips and knees line up;
  the upper back stays on the floor, the head stays down.
mode = "crunch": lying on the back, knees bent, feet flat, hands across the chest. The
  upper spine curls until the shoulder blades leave the floor; the lower back stays down.

params: hands (half-width of the hands / elbows, m), depth (push-up chest height at the
bottom, m), lift (bridge hip angle at the top, deg), curl (crunch trunk flexion, deg),
feet (bridge/crunch heel distance from the glutes, m)."""
import math
from mathutils import Vector, Matrix
from core.solver import rot_x, rot_z, two_bone, update
from ..landmarks import Landmarks
from ..stance import arm_lengths
from ..contact import grip_point

DOWN = Vector((0, 0, -1))


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def palm_point(P, side):
    """Centre of the palm's skin, for a hand flat on the floor."""
    w = P.head(f"wrist.{side}")
    k = (P.head(f"finger2-1.{side}") + P.head(f"finger5-1.{side}")) / 2
    return w + (k - w) * 0.55 + P.palm_now(side) * 0.024


class Pattern:
    def __init__(self, P, params):
        self.P = P
        self.p = p = {"mode": "pushup", "hands": 0.25, "depth": 0.07, "lift": 26.0, "curl": 34.0,
                      "feet": 0.45, "width": 0.11, **params}
        self.lm = Landmarks(P)
        self.root_rest = P.rest_head("root")
        if p["mode"] in ("pushup", "plank"):
            self.toe_y = 0.6
            self.solve_prone()
        else:
            self.solve_supine()

    # --- whole-body placement --------------------------------------------------
    def orient(self, deg, anchor, target):
        """Rotate the body about X by deg (from standing) and translate it so the point
        anchor() lands on target."""
        P = self.P
        R = rot_x(deg)
        P.set_world("root", R @ P.rest3("root"), self.root_rest)
        a = anchor()
        P.set_world("root", R @ P.rest3("root"), self.root_rest + (target - a))

    def mtp(self):
        P = self.P
        pts = [P.head(f"toe{t}-1.{s}") for s in ("L", "R") for t in (1, 5)]
        return sum(pts, Vector()) / len(pts)

    def shoulders(self):
        P = self.P
        return (P.head("upperarm01.L") + P.head("upperarm01.R")) / 2

    def bisect(self, f, lo, hi, want, n=30):
        """Angle in [lo, hi] where f(angle) == want (f monotonic)."""
        flo = f(lo)
        for _ in range(n):
            mid = (lo + hi) / 2
            if (f(mid) - want) * (flo - want) > 0:
                lo, flo = mid, f(mid)
            else:
                hi = mid
        return (lo + hi) / 2

    # --- prone ------------------------------------------------------------------
    def prone(self, theta):
        """Plank at theta deg above the floor, pivoting on the toes."""
        self.P.reset()
        self.orient(90 - theta, self.mtp, Vector((0, self.toe_y, 0.034)))
        self.legs_straight()

    def solve_prone(self):
        P, p = self.P, self.p
        ua, fa = arm_lengths(P)
        if p["mode"] == "plank":
            want = ua * 0.97 + 0.058            # elbow on the floor under the shoulder
        else:
            want = 0.98 * (ua + fa) + 0.024     # flat palm adds thickness, not hand length
        sh_z = lambda th: (self.prone(th), self.shoulders().z)[1]
        self.theta_top = self.bisect(sh_z, 2.0, 45.0, want)
        self.prone(self.theta_top)
        sh = self.shoulders()
        self.hand_y = sh.y + (0.03 if p["mode"] == "pushup" else 0.0)
        if p["mode"] == "pushup":
            chest_z = lambda th: (self.prone(th), self.lm["chest"].z)[1]
            self.theta_bot = self.bisect(chest_z, 0.0, self.theta_top, p["depth"])
        P.reset()

    # --- supine -----------------------------------------------------------------
    def supine(self, phi):
        """On the back, upper back on the floor, hips lifted phi deg."""
        P = self.P
        P.reset()
        z0 = getattr(self, "base_z", 0.0) + (0.017 if self.p["mode"] == "bridge" else 0.004)          # floor, or a bench pad
        self.orient(-(90 + phi), lambda: self.lm["upper_back"], Vector((0, getattr(self, "back_y", 0.0), z0)))
        # the contact moves up the back as the hips rise: rest on the lowest point
        low = min(self.lm[n].z for n in ("upper_back", "upper_back_hi", "scap.L", "scap.R"))
        if low < z0:
            m = P.rig.pose.bones["root"].matrix.copy()
            P.set_world("root", m.to_3x3(), m.translation + Vector((0, 0, z0 - low)))

    def solve_supine(self):
        P, p = self.P, self.p
        gl = lambda ph: (self.supine(ph), self.lm["glutes"].z)[1]
        self.phi_floor = self.bisect(gl, -20.0, 30.0, getattr(self, "base_z", 0.0) + 0.004)
        self.supine(self.phi_floor)
        hip = (P.head("upperleg01.L") + P.head("upperleg01.R")) / 2
        az = P.rest_head("foot.L").z
        self.ankles = {s: Vector((sg * p["width"], hip.y - p["feet"], az)) for s, sg in (("L", 1), ("R", -1))}
        P.reset()

    # --- pose ------------------------------------------------------------------------
    def pose(self, s):
        return getattr(self, "pose_" + self.p["mode"])(s)

    def tuck_toes(self):
        P = self.P
        for side in ("L", "R"):
            for t in range(1, 6):
                n = f"toe{t}-1.{side}"
                # toe pads flat on the floor, pointing toward the head
                P.set_world(n, P.rest3(n))

    def flatten_fingers(self, side, floor=0.0):
        """Settle finger pads onto the support plane with a slight natural slope."""
        P = self.P
        for f in range(1, 6):
            for j in (1, 2, 3):
                n = f"finger{f}-{j}.{side}"
                if n not in P.rig.pose.bones:
                    continue
                d = P.tail(n) - P.head(n)
                remaining = sum(P.rig.pose.bones[f"finger{f}-{k}.{side}"].length
                                for k in range(j, 4)) * .9
                # Bone centres stay above the surface; skin pads meet it at the tips.
                dz = (floor + .006 - P.head(n).z) * d.length / max(remaining, 1e-6)
                flat = Vector((d.x, d.y, dz))
                if flat.length < 1e-6:
                    continue
                r = d.rotation_difference(flat).to_matrix()
                P.set_world(n, r @ P.rig.pose.bones[n].matrix.to_3x3())

    def legs_straight(self):
        """Legs long but not locked: a soft knee instead of MPFB's slightly
        hyperextended rest pose; knees point along the body's front."""
        P = self.P
        front = P.delta("root") @ Vector((0, -1, 0))
        for side in ("L", "R"):
            h, a = P.head(f"upperleg01.{side}"), P.head(f"foot.{side}")
            tgt = h + (a - h) * 0.995
            foot = P.rig.pose.bones[f"foot.{side}"].matrix.to_3x3()
            P.limb(f"upperleg01.{side}", f"lowerleg01.{side}", f"foot.{side}", tgt, front)
            P.set_world(f"foot.{side}", foot)

    def hand_flat(self, side, sgn, target, pole):
        P = self.P
        X = Vector((1, 0, 0))
        wrist = target.copy()
        ua, fa = arm_lengths(P)
        for it in range(10):
            sh = P.head(f"upperarm01.{side}")
            if (wrist - sh).length > .998 * (ua + fa):
                wrist = sh + (wrist - sh).normalized() * .998 * (ua + fa)
            elbow = two_bone(sh, wrist, ua, fa, pole)
            P.limb(f"upperarm01.{side}", f"lowerarm01.{side}", f"wrist.{side}", wrist, pole,
                   palm=X.cross(wrist - elbow), side=side)
            P.hand_orient(side, X * sgn, DOWN)
            # Compact the hand as a unit, including finger joints; arm lengths stay fixed.
            P.rig.pose.bones[f"wrist.{side}"].scale = (0.9, 0.9, 0.9)
            update()
            err = target - palm_point(P, side)
            if err.length < 0.0008:
                break
            wrist = wrist + err * (1.0 if it == 0 else 0.6)
        P.curl_fingers(side, deg=(4, 6, 4), thumb=(0, 5, 5))
        self.flatten_fingers(side, floor=target.z - .004)

    def pose_pushup(self, s):
        P, p = self.P, self.p
        th = lerp(self.theta_top, self.theta_bot, s)
        self.prone(th)
        P.local("neck02", (1, 0, 0), -6)                 # neutral neck, eyes just ahead
        self.tuck_toes()
        for side, sgn in (("L", 1), ("R", -1)):
            P.scap_rhythm(side, DOWN, protraction=lerp(6, -8, s))
            tgt = Vector((sgn * p["hands"], self.hand_y, 0.004))
            pole = Vector((sgn * 0.7, 0.7, 0.25))         # elbows back and out ~45 deg
            self.hand_flat(side, sgn, tgt, pole)
        return {}

    def pose_plank(self, s):
        P, p = self.P, self.p
        th = self.theta_top + 0.6 * math.sin(math.pi * s)   # breathing
        self.prone(th)
        P.local("neck02", (1, 0, 0), -4)
        self.tuck_toes()
        ua, fa = arm_lengths(P)
        for side, sgn in (("L", 1), ("R", -1)):
            P.scap_rhythm(side, DOWN, protraction=6)
            sh = P.head(f"upperarm01.{side}")
            elbow = Vector((sgn * (abs(sh.x) - 0.01), sh.y, 0.058))
            wrist = elbow + Vector((-sgn * 0.04, -fa * 0.995, -0.008))
            P.limb(f"upperarm01.{side}", f"lowerarm01.{side}", f"wrist.{side}", wrist,
                   Vector((0, 0.2, -1)), palm=Vector((-sgn, 0, 0)), side=side)
            # Neutral wrists and relaxed fists, supported on the little-finger side.
            P.hand_orient(side, Vector((0, 0, -1)), Vector((-sgn, 0, 0)))
            P.rig.pose.bones[f"wrist.{side}"].scale = (0.9, 0.9, 0.9)
            update()
            P.curl_fingers(side, deg=(55, 65, 40), thumb=(15, 30, 25))
        return {}

    def legs_bent(self):
        P = self.P
        for side, sgn in (("L", 1), ("R", -1)):
            P.limb(f"upperleg01.{side}", f"lowerleg01.{side}", f"foot.{side}", self.ankles[side],
                   Vector((sgn * 0.15, 0, 1)))
            P.set_world(f"foot.{side}", rot_z(sgn * 5) @ P.rest3(f"foot.{side}"))

    def arms_floor(self):
        P = self.P
        for side, sgn in (("L", 1), ("R", -1)):
            P.scap_rhythm(side, Vector((0, -1, 0)))
            tgt = Vector((sgn * 0.27, -0.48, 0.004))
            ua, fa = arm_lengths(P)
            sh = P.head(f"upperarm01.{side}")
            d = tgt - sh
            if d.length > 0.98 * (ua + fa) + 0.07:
                tgt = sh + d.normalized() * (0.98 * (ua + fa) + 0.07)
            self.hand_flat(side, sgn, tgt, Vector((sgn, 0, 0.6)))

    def pose_bridge(self, s):
        P, p = self.P, self.p
        phi = lerp(self.phi_floor, self.phi_floor + p["lift"], s)
        self.supine(phi)
        # head stays on the floor: solve the neck angle (flexion as the torso tips)
        def head_z(a):
            P.local("neck01", (1, 0, 0), 0.6 * a)
            P.local("neck02", (1, 0, 0), 0.4 * a)
            return self.lm["head_back"].z
        a = self.bisect(head_z, -35.0, 50.0, 0.006, n=20)
        head_z(a)
        self.legs_bent()
        self.arms_floor()
        return {}

    def pose_crunch(self, s):
        P, p = self.P, self.p
        self.supine(self.phi_floor)
        c = p["curl"] * s
        for n, k in (("spine03", 0.25), ("spine02", 0.4), ("spine01", 0.35)):
            P.local(n, (1, 0, 0), k * c)
        P.local("neck02", (1, 0, 0), 8 + 0.15 * c)            # chin slightly tucked
        self.legs_bent()
        body = P.delta("spine01")
        chest = self.lm["chest"]
        for side, sgn in (("L", 1), ("R", -1)):
            P.scap_rhythm(side, body @ Vector((-sgn * 0.6, -1, 0.3)).normalized(), protraction=10)
            # hand on the opposite shoulder, forearms crossed over the chest
            tgt = chest + body @ Vector((-sgn * 0.11, -0.06, 0.06))
            P.limb(f"upperarm01.{side}", f"lowerarm01.{side}", f"wrist.{side}", tgt,
                   body @ Vector((sgn, 0, -0.5)), palm=body @ Vector((0, 1, 0)), side=side)
            P.curl_fingers(side, deg=(15, 20, 10), thumb=(5, 10, 10))
        return {}
