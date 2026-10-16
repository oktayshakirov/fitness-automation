"""Standing single-joint arm work: curls and pushdowns now; raises and overhead
extensions next.

Form rules: feet planted, elbows pinned at the sides (upper arm fixed), only the forearm
travels in the sagittal plane, wrists neutral. The planned elbow is passed as the IK pole
so it can't drift at deep flexion.

params: tilt (forward lean, deg), hip_back (m), knee_reach (leg extension 0..1),
ua_dir (upper-arm direction, x mirrored per side), grip_x (fixed wrist half-width or
null), phi ([start, end] elbow angle from the upper arm, deg), grip ("over" | "under")."""
import math
from mathutils import Vector
from core.solver import rot_x
from ..stance import Stance, place_pelvis, arm_lengths


class Pattern:
    def __init__(self, P, params):
        self.P = P
        self.p = p = {"tilt": 1.0, "hip_back": 0.0, "knee_reach": 0.985, "ua_dir": [0.06, -0.06, -1],
                      "grip_x": None, "phi": [6, 138], "grip": "under", "stance": 0.13, "toe_out": 8.0,
                      "fingers": "fist", **params}
        self.st = Stance(P, p["stance"], p["toe_out"])
        ankle = self.st.ankles["L"]
        self.hip_mid = Vector((0, ankle.y + p["hip_back"], self.st.hip_height(p["knee_reach"], p["hip_back"])))

    def pose(self, s):
        P, p = self.P, self.p
        tilt = p["tilt"]
        place_pelvis(P, tilt, self.hip_mid)
        P.local("neck02", (1, 0, 0), -tilt * 0.5)
        P.local("head", (1, 0, 0), -tilt * 0.4)
        self.st.legs()
        phi0, phi1 = p["phi"]
        phi = phi0 + (phi1 - phi0) * s
        for side, sgn in (("L", 1), ("R", -1)):
            sh = P.head(f"upperarm01.{side}")
            ua, fa = arm_lengths(P, side)
            x, y, z = p["ua_dir"]
            d_ua = Vector((sgn * x, y, z)).normalized()
            elbow = sh + d_ua * ua
            f_dir = rot_x(-phi) @ d_ua          # forearm swings forward/up in the sagittal plane
            wrist = elbow + f_dir * fa
            if p["grip_x"] is not None:
                wrist.x = sgn * p["grip_x"]
                wrist = elbow + (wrist - elbow).normalized() * fa
            palm = (rot_x(90) if p["grip"] == "over" else rot_x(-90)) @ (wrist - elbow).normalized()
            pole = (elbow - sh) - (elbow - sh).project(wrist - sh)
            P.limb(f"upperarm01.{side}", f"lowerarm01.{side}", f"wrist.{side}", wrist,
                   pole, palm=palm, side=side)
            if p["fingers"] == "fist":
                P.curl_fingers(side)
