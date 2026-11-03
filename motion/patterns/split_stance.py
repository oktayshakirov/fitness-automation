"""Split-stance legs: split squat (static), forward lunge, reverse lunge.

Feet hip-width apart, one in front of the other ("on train tracks", not on a tightrope).
The front foot stays flat with the knee tracking the toes; the rear foot balances on
the ball of the foot (heel up, toes flat). The hips travel straight down until the front
thigh is parallel to the floor and the rear knee hovers a few cm above it. Torso
upright with a slight forward lean, neck neutral.

step = "none" (split squat), "forward" (front foot steps out and back),
"reverse" (rear foot steps back and returns). The stepping foot leaves the floor on a
low arc during the first `step_phase` of the descent.

params: front ("L" | "R"), stride (front ankle to rear ankle along Y, m), width (ankle
half-width), toe_out, shin_lean (front shin at the bottom, deg), torso (lean at the
bottom, deg), rear_pitch ([standing, bottom] heel-up angle of the rear foot, deg),
arms ("relaxed" | "hips" | "db")."""
import math
from mathutils import Vector, Matrix
from core.solver import rot_x, rot_z
from ..stance import place_pelvis, UP
from .. import arms

FWD = Vector((0, -1, 0))


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def soft_min(a, b, k=0.04):
    """min(a, b) with the corner rounded over k (no kink when one starts to bind)."""
    h = max(k - abs(a - b), 0.0) / k
    return min(a, b) - h * h * k / 4


class Pattern:
    def __init__(self, P, params):
        self.P = P
        self.p = p = {"front": "L", "stride": 0.82, "width": 0.11, "toe_out": 6.0, "shin_lean": 12.0,
                      "torso": 8.0, "rear_pitch": [32, 58], "step": "none", "step_phase": 0.4,
                      "lift": 0.07, "arms": "relaxed", "knee_clear": 0.11, **params}
        self.fr = p["front"]
        self.rr = "R" if self.fr == "L" else "L"
        self.la = (P.rest_head("lowerleg01.L") - P.rest_head("upperleg01.L")).length
        self.lb = (P.rest_head("foot.L") - P.rest_head("lowerleg01.L")).length
        self.hip_x = P.rest_head("upperleg01.L").x
        a0 = P.rest_head("foot.L")
        self.ankle_z, self.ankle_y = a0.z, a0.y
        ball = (P.rest_head("toe1-1.L") + P.rest_head("toe5-1.L")) / 2
        self.ball_off = a0 - Vector((a0.x, ball.y, ball.z))      # ankle relative to the ball (x = 0)
        self.ball_z = ball.z
        sgn = {"L": 1, "R": -1}
        w = p["width"]
        y0 = self.ankle_y
        # flat-foot ankle positions: standing and split
        self.stand = {s: Vector((sgn[s] * w, y0, self.ankle_z)) for s in ("L", "R")}
        if p["step"] == "forward":
            yf, yr = y0 - p["stride"], y0
        elif p["step"] == "reverse":
            yf, yr = y0, y0 + p["stride"]
        else:
            yf, yr = y0 - p["stride"] / 2, y0 + p["stride"] / 2
        self.split = {self.fr: Vector((sgn[self.fr] * w, yf, self.ankle_z)),
                      self.rr: Vector((sgn[self.rr] * w, yr, self.ankle_z))}
        self.sgn = sgn
        # bottom: front shin leaned along the toes, front thigh parallel to the floor
        sl = math.radians(p["shin_lean"])
        fa = self.split[self.fr]
        knee_f = fa + self.lb * (math.sin(sl) * FWD + math.cos(sl) * UP)
        dx = self.hip_x - w
        self.hip_bot = Vector((0, knee_f.y + math.sqrt(self.la ** 2 - dx * dx), knee_f.z + 0.02))
        self.hip_split_top = Vector((0, self.hip_bot.y, 2.0))     # capped by leg reach in pose()
        if p["step"] != "none":
            self.hip_path()

    def hip_y(self, s):
        return lerp(self.ankle_y + 0.01, self.hip_bot.y, smooth(s / 0.6))

    def hip_path(self, n=60, w=4):
        """Hip height over a stepping rep: down from standing to the bottom without ever
        rising, never above what the legs reach (the reach dips while the stepping foot
        is in the air), with the corners blurred, so the body sinks in one smooth
        motion instead of dropping, catching and dropping again."""
        # 0.96 of full reach: a knee near straight swings fast for tiny hip moves
        cap = [self.max_hip_z(Vector((0, self.hip_y(i / n), 0)), self.foot_targets(i / n), reach=0.96)
               for i in range(n + 1)]
        want = [lerp(cap[0], self.hip_bot.z, smooth((i / n - 0.1) / 0.9)) for i in range(n + 1)]
        low, raw = 9.0, []
        for c, d in zip(cap, want):
            low = min(low, c, d)
            raw.append(low)

        def win(i, k):
            k = min(k, i, n - i)
            return slice(i - k, i + k + 1)
        eroded = [min(raw[win(i, w)]) for i in range(n + 1)]
        self._hz = [sum(eroded[win(i, w)]) / len(eroded[win(i, w)]) for i in range(n + 1)]

    def hip_z(self, s):
        x = max(0.0, min(1.0, s)) * (len(self._hz) - 1)
        i = min(int(x), len(self._hz) - 2)
        return lerp(self._hz[i], self._hz[i + 1], x - i)

    # --- feet ---------------------------------------------------------------
    def rear_ankle(self, flat_ankle, pitch):
        """Ankle position with the foot pivoting about the ball of the foot."""
        ball = Vector((flat_ankle.x, flat_ankle.y - self.ball_off.y, self.ball_z + flat_ankle.z - self.ankle_z))
        return ball + rot_x(pitch) @ Vector((0, self.ball_off.y, self.ball_off.z))

    def foot_targets(self, s):
        """Ankle target, heel pitch and lift for each foot at phase s."""
        p = self.p
        st = p["step_phase"]
        r0, r1 = p["rear_pitch"]
        u = smooth(s / st) if p["step"] != "none" else 1.0     # step progress
        out = {}
        if p["step"] == "none":
            out[self.fr] = (self.split[self.fr], 0.0, 0.0)
            out[self.rr] = (self.split[self.rr], lerp(r0, r1, s), 0.0)
        elif p["step"] == "forward":
            a = self.stand[self.fr].lerp(self.split[self.fr], smooth(u))     # lifts, then travels
            lift = p["lift"] * math.sin(math.pi * u)
            out[self.fr] = (a + Vector((0, 0, lift)), 0.0, lift)
            # stance foot stays put; its heel rises as the body moves forward
            out[self.rr] = (self.stand[self.rr], lerp(0.0, r1, smooth(s / 0.85)), 0.0)
        else:
            a = self.stand[self.rr].lerp(self.split[self.rr], smooth(u))
            lift = p["lift"] * math.sin(math.pi * u)
            pitch = lerp(0.0, r0, u) if s < st else lerp(r0, r1, (s - st) / (1 - st))
            out[self.rr] = (a + Vector((0, 0, lift)), pitch, lift)
            out[self.fr] = (self.stand[self.fr], 0.0, 0.0)
        return out

    def max_hip_z(self, hip, feet, reach=0.985):
        z = 9.0
        for side, (a, pitch, _) in feet.items():
            ank = self.rear_ankle(a, pitch) if pitch > 0 else a
            hx = self.sgn[side] * self.hip_x
            d2 = (reach * (self.la + self.lb)) ** 2 - (hx - ank.x) ** 2 - (hip.y - ank.y) ** 2
            z = min(z, ank.z + math.sqrt(max(0.0, d2)))
        return z

    # --- pose ---------------------------------------------------------------
    def pose(self, s):
        P, p = self.P, self.p
        feet = self.foot_targets(s)
        # hips: from standing over the feet to the split, then straight down
        if p["step"] == "none":
            hy = self.hip_bot.y
            top = self.max_hip_z(Vector((0, hy, 0)), feet)
            hz = lerp(top, self.hip_bot.z, s)
        else:
            # the body moves into the step: hips travel with the stepping foot and sink
            # along one smooth path under the legs' reach
            hy = self.hip_y(s)
            hz = self.hip_z(s)
        hip = Vector((0, hy, soft_min(hz, self.max_hip_z(Vector((0, hy, 0)), feet))))
        depth = smooth((self.max_hip_z(Vector((0, hy, 0)), feet) - hip.z) / 0.3)
        tilt = 2 + (p["torso"] - 2) * depth
        place_pelvis(P, tilt, hip)
        P.local("neck02", (1, 0, 0), -0.3 * tilt)
        P.local("head", (1, 0, 0), -0.2 * tilt)
        for side in ("L", "R"):
            a, pitch, lift = feet[side]
            yaw = self.sgn[side] * p["toe_out"]
            ank = self.rear_ankle(a, pitch) if pitch > 0 else a
            toe = rot_z(yaw) @ FWD
            if side == self.rr:
                # rear knee: forward while the foot is flat, turning down as the heel rises
                down = (toe * 0.3 + Vector((0, 0, -1))).normalized()
                fwd = (toe * 0.6 + Vector((0, 0, -0.4))).normalized()
                pole = fwd.lerp(down, smooth((pitch - 5.0) / 20.0))
            else:
                pole = toe
            P.limb(f"upperleg01.{side}", f"lowerleg01.{side}", f"foot.{side}", ank, pole)
            P.set_world(f"foot.{side}", rot_x(pitch) @ rot_z(yaw) @ P.rest3(f"foot.{side}"))
            if pitch > 0:          # toes stay flat on the floor
                for t in range(1, 6):
                    n = f"toe{t}-1.{side}"
                    if n in P.rig.pose.bones:
                        P.set_world(n, rot_z(yaw) @ P.rest3(n))
        for side in ("L", "R"):
            if p["arms"] == "hips":
                arms.hands_on_hips(P, side)
            else:
                arms.relaxed(P, side, out=0.14 if p["arms"] == "db" else 0.08,
                             fist=p["arms"] == "db")
        return {}
