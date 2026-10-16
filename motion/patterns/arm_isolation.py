"""Standing single-joint arm work.

joint = "elbow" (curls, pushdowns): feet planted, elbows pinned at the sides (upper arm
fixed), only the forearm travels in the sagittal plane, wrists neutral. The planned
elbow is passed as the IK pole so it can't drift at deep flexion.
  params: tilt (forward lean, deg), hip_back (m), knee_reach (leg extension 0..1),
  ua_dir (upper-arm direction, x mirrored per side), grip_x (fixed wrist half-width, or
  [start, end] for hands that spread apart like rope ends, or null), phi ([start, end] elbow angle from the upper arm, deg),
  grip ("over" | "under" | "neutral"), carry (carrying angle at full extension, deg).

joint = "shoulder" (lateral / front raises): the elbow angle stays fixed and soft, the
whole arm rotates up in one plane to about shoulder height; the shoulder girdle follows
the scapulohumeral rhythm (no shrug beyond it).
  params: plane (deg: 0 = straight out to the side, 90 = straight forward; ~25 =
  scapular plane), elev ([start, end] humerus angle from hanging, deg), elbow (fixed
  bend, deg), palm ("in" = palms facing the thighs at the bottom -> down at the top,
  "back" = palms facing back -> down)."""
import math
from mathutils import Vector, Matrix
from core.solver import rot_x
from ..stance import Stance, place_pelvis, arm_lengths


class Pattern:
    def __init__(self, P, params):
        self.P = P
        self.p = p = {"joint": "elbow", "tilt": 1.0, "hip_back": 0.0, "knee_reach": 0.985,
                      "ua_dir": [0.06, -0.06, -1], "grip_x": None, "phi": [6, 138], "grip": "under",
                      "stance": 0.13, "toe_out": 8.0, "fingers": "fist",
                      "plane": 25.0, "elev": [12, 88], "elbow": 18.0, "palm": "in", "carry": 0.0, **params}
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
        for side, sgn in (("L", 1), ("R", -1)):
            if p["joint"] == "shoulder":
                self.raise_arm(side, sgn, s)
            else:
                self.elbow_arm(side, sgn, s)
            if p["fingers"] == "fist":
                P.curl_fingers(side)

    def elbow_arm(self, side, sgn, s):
        P, p = self.P, self.p
        phi0, phi1 = p["phi"]
        phi = phi0 + (phi1 - phi0) * s
        sh = P.head(f"upperarm01.{side}")
        ua, fa = arm_lengths(P, side)
        x, y, z = p["ua_dir"]
        d_ua = Vector((sgn * x, y, z)).normalized()
        elbow = sh + d_ua * ua
        f_dir = rot_x(-phi) @ d_ua          # forearm swings forward/up in the sagittal plane
        if p["carry"]:
            # carrying angle: the extended forearm angles out, fading as the elbow bends
            c = p["carry"] * max(0.0, math.cos(math.radians(phi)))
            f_dir = Matrix.Rotation(math.radians(-sgn * c), 3, "Y") @ f_dir
        wrist = elbow + f_dir * fa
        if p["grip_x"] is not None:
            gx = p["grip_x"]
            if isinstance(gx, (list, tuple)):          # hands travel apart (rope ends)
                gx = gx[0] + (gx[1] - gx[0]) * s
            wrist.x = sgn * gx
            wrist = elbow + (wrist - elbow).normalized() * fa
        fd = (wrist - elbow).normalized()
        if p["grip"] == "neutral":
            palm = Vector((-sgn, 0, 0))     # palms face each other (hammer grip)
            palm = (palm - palm.project(fd)).normalized()
        else:
            palm = (rot_x(90) if p["grip"] == "over" else rot_x(-90)) @ fd
        pole = (elbow - sh) - (elbow - sh).project(wrist - sh)
        P.limb(f"upperarm01.{side}", f"lowerarm01.{side}", f"wrist.{side}", wrist,
               pole, palm=palm, side=side)

    def raise_arm(self, side, sgn, s):
        P, p = self.P, self.p
        e0, e1 = p["elev"]
        elev = e0 + (e1 - e0) * s
        body = P.delta("spine01")
        down, fwd = body @ Vector((0, 0, -1)), body @ Vector((0, -1, 0))
        lat = body @ Vector((sgn, 0, 0))
        pl = math.radians(p["plane"])
        out = (lat * math.cos(pl) + fwd * math.sin(pl)).normalized()
        axis = down.cross(out).normalized()                 # rotation taking down -> out
        R = Matrix.Rotation(math.radians(elev), 3, axis)
        hum = R @ down
        P.scap_rhythm(side, hum)
        sh = P.head(f"upperarm01.{side}")
        ua, fa = arm_lengths(P, side)
        elbow = sh + hum * ua
        # soft elbow: forearm tipped toward the front of the arm (the biceps side)
        front = R @ fwd
        front = (front - front.project(hum)).normalized()
        fdir = (hum * math.cos(math.radians(p["elbow"])) + front * math.sin(math.radians(p["elbow"]))).normalized()
        wrist = elbow + fdir * fa
        palm0 = body @ (Vector((-sgn, 0, 0)) if p["palm"] == "in" else Vector((0, 1, 0)))
        palm = R @ palm0
        palm = (palm - palm.project(fdir)).normalized()
        pole = (elbow - sh) - (elbow - sh).project(wrist - sh)
        P.limb(f"upperarm01.{side}", f"lowerarm01.{side}", f"wrist.{side}", wrist,
               pole, palm=palm, side=side)
