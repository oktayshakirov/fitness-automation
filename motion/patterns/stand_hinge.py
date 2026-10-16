"""Standing lower-body pattern: squats now; hip-hinge variants (deadlift, RDL, good
morning) are added as params on the same path model.

Feet planted (stance width, toes out), the hips follow a back-and-down path to the
bottom position, and the two-bone solver bends each knee toward its own toes, so knees
can't cave in or cross. The torso hinges with a neutral spine, chest up, eyes forward.

params: stance (ankle half-width, m), toe_out (deg), shin_lean (deg from vertical at the
bottom), torso (forward hinge at the bottom, deg), arms ("counterbalance")."""
import math
from mathutils import Vector
from ..stance import Stance, place_pelvis, arm_lengths, UP


class Pattern:
    def __init__(self, P, params):
        self.P = P
        self.p = p = {"stance": 0.17, "toe_out": 15.0, "shin_lean": 32.0, "torso": 40.0,
                      "arms": "counterbalance", **params}
        st = self.st = Stance(P, p["stance"], p["toe_out"])
        la, lb = st.la, st.lb
        ankle = st.ankles["L"]
        # bottom: shin leaned along the toes, thigh parallel to the floor
        sl = math.radians(p["shin_lean"])
        knee_b = ankle + lb * (math.sin(sl) * st.toe["L"] + math.cos(sl) * UP)
        dx = st.hip_x - knee_b.x
        self.hip_bot = Vector((0, knee_b.y + math.sqrt(la * la - dx * dx), knee_b.z + 0.03))
        # top: legs almost straight, hips over mid-foot
        self.hip_top = Vector((0, ankle.y + 0.01, st.hip_height(0.985, 0.01)))
        print("HIP top", tuple(round(v, 3) for v in self.hip_top),
              "bottom", tuple(round(v, 3) for v in self.hip_bot))

    def pose(self, s):
        P, p = self.P, self.p
        tilt = 3 + (p["torso"] - 3) * s
        back = 1 - (1 - s) ** 1.6          # hips travel back early, like a hip hinge
        top, bot = self.hip_top, self.hip_bot
        place_pelvis(P, tilt, Vector((0, top.y + (bot.y - top.y) * back, top.z + (bot.z - top.z) * s)))
        # neutral spine, chest up, eyes forward
        P.local("spine02", (1, 0, 0), -4 * s)
        P.local("spine01", (1, 0, 0), -5 * s)
        P.local("neck02", (1, 0, 0), -12 * s)
        P.local("head", (1, 0, 0), -14 * s)
        self.st.legs()
        if p["arms"] == "counterbalance":
            self.arms_counterbalance(s)

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
