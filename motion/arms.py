"""Arm poses shared by patterns where the arms aren't the point of the exercise."""
import math
from mathutils import Vector
from .stance import arm_lengths


def relaxed(P, side, out=0.08, fwd=0.04, bend=8.0, fist=False, reach=0.975):
    """Arm hanging at the side, elbow soft, palm facing the thigh. out/fwd tip the hand
    away from the body (body frame, metres per metre of drop). With fist=True the hand
    is closed (dumbbell carried at the side)."""
    sgn = 1 if side == "L" else -1
    body = P.delta("spine01")
    sh = P.head(f"upperarm01.{side}")
    ua, fa = arm_lengths(P, side)
    d = (body @ Vector((sgn * out, -fwd, -1))).normalized()
    # shorten the reach by the elbow bend so the forearm can tip forward
    L = math.sqrt(ua * ua + fa * fa + 2 * ua * fa * math.cos(math.radians(bend))) * min(reach, 0.999)
    wrist = sh + d * L
    palm = body @ Vector((-sgn, 0, 0))
    palm = (palm - palm.project(d)).normalized()
    P.scap_rhythm(side, d)
    P.limb(f"upperarm01.{side}", f"lowerarm01.{side}", f"wrist.{side}", wrist,
           body @ Vector((0, 1, 0)), palm=palm, side=side)
    if fist:
        P.curl_fingers(side)
    else:
        P.curl_fingers(side, deg=(12, 18, 10), thumb=(5, 10, 8))


def hands_on_hips(P, side):
    """Hands resting on the iliac crest, elbows out to the side."""
    sgn = 1 if side == "L" else -1
    body = P.delta("spine01")
    hip = P.head(f"upperleg01.{side}")
    root = P.rig.pose.bones["root"].matrix.to_3x3()
    target = hip + root @ Vector((sgn * 0.075, -0.01, 0.0)) + body @ Vector((0, 0, 0.12))
    sh = P.head(f"upperarm01.{side}")
    P.scap_rhythm(side, (target - sh).normalized())
    P.limb(f"upperarm01.{side}", f"lowerarm01.{side}", f"wrist.{side}", target,
           body @ Vector((sgn, 0.4, 0)), palm=body @ Vector((-sgn, 0.3, 0)).normalized(), side=side)
    P.curl_fingers(side, deg=(10, 15, 10), thumb=(5, 5, 5))
