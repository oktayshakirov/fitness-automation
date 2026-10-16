"""Rule-based pose solver: world-space bone placement, analytic two-bone IK with a
pole, palm-direction forearm twist, finger curl."""
import math
from mathutils import Vector, Matrix, Quaternion
from .body import update


def frame(v, f):
    """Orthonormal basis whose Y is v and whose Z is f made perpendicular to v."""
    y = v.normalized()
    z = (f - f.project(y)).normalized()
    x = y.cross(z)
    return Matrix((x, y, z)).transposed()


def frame_align(v0, f0, v1, f1):
    """Rotation taking direction v0 to v1, with reference f0 turned toward f1."""
    return frame(v1, f1) @ frame(v0, f0).transposed()


def two_bone(h, a_pt, la, lb, pole):
    """Knee/elbow position for a two-segment limb from h to a_pt, bending toward pole."""
    d_vec = a_pt - h
    d = min(d_vec.length, (la + lb) * 0.9995)
    u = d_vec.normalized()
    along = (la * la - lb * lb + d * d) / (2 * d)
    hgt = math.sqrt(max(0.0, la * la - along * along))
    p = (pole - pole.project(u)).normalized()
    return h + u * along + p * hgt


def rot_x(deg):
    return Matrix.Rotation(math.radians(deg), 3, "X")


def rot_z(deg):
    return Matrix.Rotation(math.radians(deg), 3, "Z")


class Poser:
    """Sets bone orientations in world space. The rig object sits at identity,
    so armature space is world space."""

    def __init__(self, rig):
        self.rig = rig
        self.rest = {b.name: b.matrix_local.copy() for b in rig.data.bones}

    def rest3(self, n):
        return self.rest[n].to_3x3()

    def rest_head(self, n):
        return self.rest[n].translation.copy()

    def head(self, n):
        return self.rig.pose.bones[n].matrix.translation.copy()

    def tail(self, n):
        pb = self.rig.pose.bones[n]
        return pb.matrix @ Vector((0, pb.length, 0))

    def axis(self, n, i):
        return self.rig.pose.bones[n].matrix.to_3x3().col[i].normalized()

    def reset(self):
        for pb in self.rig.pose.bones:
            pb.matrix_basis = Matrix.Identity(4)
        update()

    def set_world(self, n, r3, loc=None):
        pb = self.rig.pose.bones[n]
        m = r3.to_4x4()
        m.translation = loc if loc is not None else pb.matrix.translation
        pb.matrix = m
        update()

    def turn(self, n, q3):
        """World-space rotation q3 applied to the bone's rest orientation."""
        self.set_world(n, q3 @ self.rest3(n))

    def local(self, n, axis, deg):
        """Rotation relative to the parent (bone-local axis)."""
        pb = self.rig.pose.bones[n]
        pb.rotation_quaternion = Quaternion(axis, math.radians(deg))
        update()

    def rest_bend(self, upper, lower, end):
        """Direction the middle joint (knee/elbow) points in the rest pose."""
        h0, k0, a0 = self.rest_head(upper), self.rest_head(lower), self.rest_head(end)
        u = (a0 - h0).normalized()
        off = (k0 - h0) - (k0 - h0).project(u)
        return off.normalized()

    def palm_rest(self, side):
        """Rest palm normal of a hand, from the knuckle line and finger direction."""
        w = self.rest_head(f"finger5-1.{side}") - self.rest_head(f"finger2-1.{side}")
        f = self.rest_head(f"finger3-1.{side}") - self.rest_head(f"wrist.{side}")
        n = w.cross(f) if side == "L" else f.cross(w)
        return n.normalized()

    def palm_now(self, side):
        w = self.head(f"finger5-1.{side}") - self.head(f"finger2-1.{side}")
        f = self.head(f"finger3-1.{side}") - self.head(f"wrist.{side}")
        n = w.cross(f) if side == "L" else f.cross(w)
        return n.normalized()

    def limb(self, upper, lower, end, target, pole, palm=None, side=None):
        """Two-segment limb (each segment may be a chain of child bones at rest
        relative to each other): upper starts the first segment, lower starts the
        second, end is the bone whose head is the end joint. The middle joint
        points toward pole. For arms, palm (world vector) sets forearm rotation."""
        h0, k0, a0 = self.rest_head(upper), self.rest_head(lower), self.rest_head(end)
        la, lb = (k0 - h0).length, (a0 - k0).length
        bend0 = self.rest_bend(upper, lower, end)
        h = self.head(upper)
        k = two_bone(h, target, la, lb, pole)
        bend1 = (k - h) - (k - h).project(target - h)
        if bend1.length < 1e-4:
            bend1 = pole
        self.turn(upper, frame_align(k0 - h0, bend0, k - h, bend1))
        if palm is not None:
            self.turn(lower, frame_align(a0 - k0, self.palm_rest(side), target - k, palm))
        else:
            self.turn(lower, frame_align(a0 - k0, bend0, target - k, bend1))
        return k

    def curl_fingers(self, side, deg=(55, 75, 50), thumb=(20, 35, 30), sign=1):
        for i in range(2, 6):
            for j, a in enumerate(deg, 1):
                self.local(f"finger{i}-{j}.{side}", (1, 0, 0), sign * a)
        for j, a in enumerate(thumb, 1):
            self.local(f"finger1-{j}.{side}", (1, 0, 0), sign * a)

    # --- shoulder girdle -------------------------------------------------
    def delta(self, n):
        """World rotation of bone n relative to its rest orientation."""
        return self.rig.pose.bones[n].matrix.to_3x3() @ self.rest3(n).transposed()

    def girdle(self, side, elevation=0.0, protraction=0.0, upward=0.0):
        """Clavicle + scapula (shoulder01) in the torso's frame, degrees.
        elevation lifts the clavicle's lateral end (shrug), protraction moves it forward
        (negative = retraction, shoulder blades squeezed), upward rotates the scapula so
        the shoulder joint rises further (arm overhead)."""
        sgn = 1 if side == "L" else -1
        d = self.delta("spine01")
        r = (Matrix.Rotation(math.radians(elevation), 3, Vector((0, -sgn, 0))) @
             Matrix.Rotation(math.radians(protraction), 3, Vector((0, 0, -sgn))))
        self.set_world(f"clavicle.{side}", d @ r @ self.rest3(f"clavicle.{side}"))
        u = Matrix.Rotation(math.radians(upward), 3, Vector((0, -sgn, 0)))
        self.set_world(f"shoulder01.{side}", d @ r @ u @ self.rest3(f"shoulder01.{side}"))

    def humeral_elevation(self, arm_dir):
        """Angle (deg) between an upper-arm direction and the torso's down axis."""
        down = self.delta("spine01") @ Vector((0, 0, -1))
        return math.degrees(arm_dir.angle(down, 0.0))

    def scap_rhythm(self, side, arm_dir, protraction=0.0, elevation=0.0):
        """Scapulohumeral rhythm: above 30 deg of humeral elevation the scapula
        rotates upward ~1 deg per 2 deg of the humerus; the clavicle elevates with it.
        Extra protraction/elevation (presses, rows, shrugs) are added on top."""
        g = max(0.0, self.humeral_elevation(arm_dir) - 30.0) / 3.0
        self.girdle(side, elevation=elevation + 0.3 * g, protraction=protraction, upward=0.2 * g)
        return g

    def hand_orient(self, side, knuckle_dir, palm):
        """Rotate the wrist so the knuckle line (index -> little finger) runs along
        knuckle_dir and the palm faces palm (radial/ulnar deviation + flexion)."""
        k = self.head(f"finger5-1.{side}") - self.head(f"finger2-1.{side}")
        r = frame_align(k, self.palm_now(side), knuckle_dir, palm)
        pb = self.rig.pose.bones[f"wrist.{side}"]
        self.set_world(f"wrist.{side}", r @ pb.matrix.to_3x3())
