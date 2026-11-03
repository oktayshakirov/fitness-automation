"""Seated machine work (facing -Y): lat pulldown, seated cable row, leg extension, seated
leg curl, 45-degree leg press.

The machine is described by a contact dict in params["machine"] (seat height, back pad
angle, pulley / rail), so the equipment machines can hand over their real numbers; the
defaults match the proxy machine in motion/props.py.

mode = "pulldown": thighs under the knee pads, feet flat; torso leaning back a little and
  a little more as the bar comes down; wide overhand grip; the bar comes from straight
  arms overhead down to the upper chest, elbows driving down and back, shoulder blades
  down and together.
mode = "cable_row": sitting tall on the bench, feet on the angled plates, knees soft; neutral V-handle
  from straight arms (shoulder blades reaching) to the lower ribs under the chest,
  elbows close to the body and behind it, blades squeezed; the torso leans back slightly
  into the pull.
mode = "leg_extension": back on the pad, hands on the side grips, knee joint lined up
  with the machine pivot; the shin pad swings the lower legs from ~90 deg bent to
  straight, thighs stay down.
mode = "leg_curl": seated, thighs under the pad, legs straight on the roller; knees
  bend to ~90 deg and back; thighs stay put.
mode = "leg_press": back and hips on the reclined seat, feet hip-width on the sled,
  toes out a little; knees from ~95 deg to almost straight (never locked), knees track
  the toes, lower back stays on the pad."""
import math
from mathutils import Vector, Matrix
from core.solver import rot_x, rot_z
from ..stance import place_pelvis, arm_lengths
from ..contact import reach, bar_palm, knuckles
from ..settle import skin, depth
from ..landmarks import Landmarks

X = Vector((1, 0, 0))
Y = Vector((0, 1, 0))
Z = Vector((0, 0, 1))
FWD = Vector((0, -1, 0))

MACHINES = {
    "pulldown": {"seat_z": 0.48, "lean": -12.0, "bar_z_top": 2.05, "grip_w": 0.40, "pulley": (0, -0.05, 2.45)},
    "cable_row": {"seat_z": 0.42, "lean": 0.0, "hip_y": -0.05, "ankle_z": 0.47, "plate_deg": 35.0, "knee_deg": 147.0, "handle_z": 0.75,
                  "pulley": (0, -1.11, 0.66), "seat_y": -0.02, "seat_depth": 0.50,
                  "sink": 0.030},   # seen edge-on from behind: the cheeks squash flat on the seat
    "leg_extension": {"seat_z": 0.50, "lean": -10.0, "knee_y": -0.47},
    "leg_curl": {"seat_z": 0.50, "lean": -10.0, "knee_y": -0.47},
    "leg_press": {"seat_z": 0.45, "lean": -48.0, "rail_deg": 45.0},
}


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


class Pattern:
    def __init__(self, P, params):
        self.P = P
        mode = params.get("mode", "pulldown")
        m = dict(MACHINES[mode], **params.get("machine", {}))
        self.p = p = {"mode": mode, "width": 0.13, "toe_out": 8.0, **params}
        if mode == "pulldown":
            m["grip_w"] *= min(1.,P.rest_head("upperarm01.L").x/.186)
        self.m = m
        ua, fa = arm_lengths(P)
        self.ua, self.fa = ua, fa
        self.lm = Landmarks(P) if mode in ("pulldown", "cable_row") else None
        self.la = (P.rest_head("lowerleg01.L") - P.rest_head("upperleg01.L")).length
        self.lb = (P.rest_head("foot.L") - P.rest_head("lowerleg01.L")).length
        self.hip_x = P.rest_head("upperleg01.L").x
        self.az = P.rest_head("foot.L").z
        # hip joints sit ~8.5 cm above the seat surface, then settle into the cushions
        self.hip = Vector((0, 0.0, m["seat_z"] + 0.085))
        if mode == "cable_row":
            # same place on the bench for everyone; the footplates slide until the knees
            # are soft (~147 deg)
            self.hip.y = m["hip_y"]
            k = math.radians(m["knee_deg"])
            d2 = self.la ** 2 + self.lb ** 2 - 2 * self.la * self.lb * math.cos(k)
            z = m["ankle_z"]
            m["ankle_y"] = self.hip.y - math.sqrt(d2 - (0.12 - self.hip_x) ** 2 - (z - self.hip.z) ** 2)
        self.settle(sink=m.get("sink", 0.015))

    def pads(self):
        """The machine's seat and back-pad faces (as equipment.machines builds them)."""
        m = self.m
        z = m["seat_z"]
        seat = (Vector((0, m.get("seat_y", -0.12), z)), X, Y, Z, 0.21, m.get("seat_depth", 0.44) / 2)
        if self.p["mode"] in ("pulldown", "cable_row"):
            return seat, None
        a = math.radians(m["lean"])
        up = Vector((0, -math.sin(a), math.cos(a)))
        back = Vector((0, math.cos(a), math.sin(a)))
        bp = Vector((0, 0, z + 0.085)) + up * 0.36 + back * 0.10
        return seat, (bp - back * 0.04, X, up, -back, 0.20, 0.34)

    def settle(self, sink=0.015, back_sink=0.010):
        """Lower the pelvis until the posed skin sinks `sink` into the seat at its
        highest point over the rep, and lean the trunk so the back sinks `back_sink`
        into the back pad: soft contact everywhere, flattened by the pad-contact
        modifier at render time."""
        P = self.P
        seat, back = self.pads()
        lean0 = self.m["lean"]
        for _ in range(3):
            lows, backs, floor = [], [], []
            for s in (0.0, 0.25, 0.5, 0.75, 1.0):
                P.reset()
                self.pose(s)
                pts = skin(P)
                hip = (P.head("upperleg01.L") + P.head("upperleg01.R")) / 2
                # buttocks and thighs only: calves may hang under the seat's front edge
                lows.append(depth(pts, seat, keep=lambda p: hip.y - 0.25 < p.y < hip.y + 0.15
                                  and p.z > max(seat[0].z - 0.10, hip.z - 0.16)))
                if back:
                    backs.append(depth(pts, back, keep=lambda p: (p - hip).dot(back[2]) > 0.15))
                floor.append(min(p.z for p in pts))
            dz = max(lows) + sink
            if self.p["mode"] != "pulldown":          # its feet stand on the floor by design
                dz = min(dz, min(floor) - 0.016)      # never so low the feet brush the floor
            self.hip.z -= dz
            if back and min(backs) < 0.5:
                self.m["lean"] -= math.degrees((sum(backs) / len(backs) + back_sink) / 0.35)
        P.reset()
        self.settled = {"hip_z": round(self.hip.z, 4), "lean": round(self.m["lean"], 2), "lean0": lean0}

    def torso_front(self, lean, down, out):
        """A point `out` m in front of the chest skin, `down` m below the chest point,
        along a trunk leaned `lean` deg (negative = back)."""
        a = math.radians(lean)
        up = Vector((0, -math.sin(a), math.cos(a)))
        fwd = Vector((0, -math.cos(a), -math.sin(a)))
        return self.lm["chest"] - up * down + fwd * out

    def shoulders(self):
        P = self.P
        return (P.head("upperarm01.L") + P.head("upperarm01.R")) / 2

    def sit(self, lean):
        """Pelvis on the seat, torso leaned lean deg (negative = back)."""
        P = self.P
        place_pelvis(P, lean, self.hip)
        P.local("neck02", (1, 0, 0), -0.3 * lean)      # keep the gaze level

    def leg(self, side, knee, ankle, foot_rot=None):
        P = self.P
        hip = P.head(f"upperleg01.{side}")
        pole = (knee - hip) - (knee - hip).project(ankle - hip)
        P.limb(f"upperleg01.{side}", f"lowerleg01.{side}", f"foot.{side}", ankle, pole)
        if foot_rot is not None:
            P.set_world(f"foot.{side}", foot_rot @ P.rest3(f"foot.{side}"))

    def legs_seated(self, shin_deg, knee_y=None, feet_flat=True):
        """Thighs along the seat, shins at shin_deg forward of hanging straight down."""
        P = self.P
        for side, sgn in (("L", 1), ("R", -1)):
            h = P.head(f"upperleg01.{side}")
            th = Vector((sgn * 0.06, -1, -0.12)).normalized()
            knee = h + th * self.la
            a = math.radians(shin_deg)
            ank = knee + (Vector((0, 0, -1)) * math.cos(a) + FWD * math.sin(a)) * self.lb
            rot = rot_z(sgn * self.p["toe_out"]) if feet_flat else rot_x(-shin_deg)
            self.leg(side, knee, ank, rot)

    def pose(self, s):
        return getattr(self, "pose_" + self.p["mode"])(s)

    # --- upper body ----------------------------------------------------------------
    def pose_pulldown(self, s):
        P, m = self.P, self.m
        lean = lerp(m["lean"] + 8, m["lean"] - 3, smooth(s))     # leans back a little into the pull
        self.sit(lean)
        # feet flat on the floor, knees ~90 deg under the pads
        for side, sgn in (("L", 1), ("R", -1)):
            h = P.head(f"upperleg01.{side}")
            knee = h + Vector((sgn * 0.04, -self.la * 0.99, -0.03))
            ank = Vector((knee.x, knee.y + 0.05, self.az))
            self.leg(side, knee, ank, rot_z(sgn * 8))
        sh = self.shoulders()
        top = Vector((0, sh.y - 0.06, sh.z + 0.96 * (self.ua + self.fa) * 0.93 + 0.15*min(1.,P.rest_head("upperarm01.L").x/.186)**3))
        # Wider hands use more lateral reach; lower the top target accordingly
        # instead of stretching the arms off the handle.
        radius = .96 * (self.ua + self.fa)
        lateral = max(0.0, m["grip_w"] - .20)
        top.z += math.sqrt(max(.01, radius**2 - lateral**2)) - math.sqrt(radius**2 - .20**2)
        top.z -= 0.025                                    # the bar sits in the palm crease, not the fingers
        chest = self.torso_front(lean, -0.06, 0.030)      # bar on the upper chest, just under the collarbones
        c = top.lerp(chest, smooth(s))
        for side, sgn in (("L", 1), ("R", -1)):
            g = c + X * sgn * m["grip_w"]
            arm = (g - P.head(f"upperarm01.{side}")).normalized()
            rh = max(0.0, P.humeral_elevation(arm) - 30.0) / 3.0
            # top: arms long, blades up; bottom: blades down and together
            P.scap_rhythm(side, arm, protraction=lerp(2, -14, smooth(s)),
                          elevation=lerp(3, -0.3 * rh - 6, smooth(s)))
            pole = Vector((sgn, 0.45, -0.6))              # elbows down and slightly back
            reach(P, side, g, pole, knuckle_dir=knuckles(sgn, "over"),
                  palm=lambda fd: bar_palm(X, fd, "over"))
        return {"handle": (c, X.copy(), "lat_bar")}

    def pose_cable_row(self, s):
        P, m = self.P, self.m
        lean = m["lean"] + lerp(5, -9, smooth(s))         # a touch forward at the reach, leaning back into the pull
        self.sit(lean)
        # feet on the angled plates at about seat height, knees soft
        for side, sgn in (("L", 1), ("R", -1)):
            ank = Vector((sgn * 0.12, m["ankle_y"], m["ankle_z"]))
            h = P.head(f"upperleg01.{side}")
            mid = (h + ank) / 2 + Vector((0, 0, 0.12))
            self.leg(side, mid, ank, rot_x(m["plate_deg"] - 90) @ rot_z(sgn * 4))
        sh = self.shoulders()
        reach_pt = Vector((0, sh.y - 0.95 * (self.ua + self.fa) - 0.05, m["handle_z"] + 0.0))
        belly = self.torso_front(lean, 0.10, 0.065)       # handle to the lower ribs, under the chest
        c = reach_pt.lerp(belly, smooth(s))
        for side, sgn in (("L", 1), ("R", -1)):
            g = c + X * sgn * 0.045 + Z * 0.0
            arm = (g - P.head(f"upperarm01.{side}")).normalized()
            rh = max(0.0, P.humeral_elevation(arm) - 30.0) / 3.0
            P.scap_rhythm(side, arm, protraction=lerp(12, -18, smooth(s)), elevation=-0.3 * rh)
            pole = Vector((sgn * 0.6, 0.3, -1))               # elbows down, close to the body
            reach(P, side, g, pole, knuckle_dir=Vector((0, 0, -1)),
                  palm=lambda fd, sgn=sgn: Vector((-sgn, 0, 0)))
        return {"handle": (c, Z.copy(), "v_handle"), "feet": Vector((0, m["ankle_y"], m["ankle_z"]))}

    # --- legs -----------------------------------------------------------------------
    def side_grips(self):
        P, m = self.P, self.m
        for side, sgn in (("L", 1), ("R", -1)):
            g = Vector((sgn * 0.27, self.hip.y - 0.08, m["seat_z"] - 0.01))
            arm = (g - P.head(f"upperarm01.{side}")).normalized()
            P.scap_rhythm(side, arm)
            # neutral grip on a handle running fore-aft: index in front, palm in
            reach(P, side, g, Vector((sgn, 0.6, 0)), knuckle_dir=Y.copy(),
                  palm=lambda fd, sgn=sgn: Vector((-sgn, 0, 0)))

    def pose_leg_extension(self, s):
        P, m = self.P, self.m
        self.sit(m["lean"])
        self.legs_seated(lerp(8, 76, smooth(s)), feet_flat=False)
        self.side_grips()
        return {"pad": self.pad_contact()}

    def pose_leg_curl(self, s):
        P, m = self.P, self.m
        self.sit(m["lean"])
        self.legs_seated(lerp(76, -5, smooth(s)), feet_flat=False)
        self.side_grips()
        return {"pad": self.pad_contact(back=True)}

    def pad_contact(self, back=False):
        """Shin roller just above the ankles (front of the shin, or behind the calves)."""
        P = self.P
        pts = []
        for side in ("L", "R"):
            k, a = P.head(f"lowerleg01.{side}"), P.head(f"foot.{side}")
            shin = (a - k).normalized()
            front = (FWD - FWD.project(shin)).normalized()
            pts.append(k + (a - k) * 0.85 + front * (0.07 if not back else -0.085))
        return ((pts[0] + pts[1]) / 2, X.copy())

    def pose_leg_press(self, s):
        P, m = self.P, self.m
        self.sit(m["lean"])
        P.local("neck02", (1, 0, 0), 20)                    # head resting on the pad
        r = math.radians(m["rail_deg"])
        d = Vector((0, -math.cos(r), math.sin(r)))          # rail: forward and up
        sole = rot_x(-(180 - m["rail_deg"]))                 # soles flat on the sled plate
        hipc = (P.head("upperleg01.L") + P.head("upperleg01.R")) / 2
        L = self.la + self.lb
        t = lerp(0.985, 0.72, smooth(s)) * L                # ~160 deg -> ~92 deg included knee angle
        plate = hipc + d * t                              # keep ankle travel on the rail line
        for side, sgn in (("L", 1), ("R", -1)):
            ank = plate + X * sgn * self.p["width"]
            h = P.head(f"upperleg01.{side}")
            # knee bends up and a little out, over the toes
            mid = (h + ank) / 2
            perp = (Z - Z.project(ank - h)).normalized()
            knee_hint = mid + perp * 0.2 + X * sgn * 0.03
            self.leg(side, knee_hint, ank, sole @ rot_z(sgn * self.p["toe_out"]))
        for side, sgn in (("L", 1), ("R", -1)):
            g = Vector((sgn * 0.27, hipc.y + 0.05, m["seat_z"] - 0.01))
            arm = (g - P.head(f"upperarm01.{side}")).normalized()
            P.scap_rhythm(side, arm)
            reach(P, side, g, Vector((sgn, 0.3, -0.3)), knuckle_dir=Y.copy(),
                  palm=lambda fd, sgn=sgn: Vector((-sgn, 0, 0)))
        return {"plate": (plate, d)}
