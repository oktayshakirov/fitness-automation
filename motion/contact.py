import math
import os
"""Hand contact: where an implement sits in the closed hand."""


def grip_point(P, side, mode="hook"):
    """Handle centre in the closed hand, and the knuckle-line direction (index -> little
    finger). mode "hook" (pulling, carrying): across the palm at the knuckle line.
    mode "press" (pressing): further back in the palm, toward the heel of the hand, so
    the bar sits over the forearm bones while the fingers still wrap it."""
    k2, k5 = P.head(f"finger2-1.{side}"), P.head(f"finger5-1.{side}")
    w = P.head(f"wrist.{side}")
    k3 = P.head(f"finger3-1.{side}")
    n = P.palm_now(side)
    f = (k3 - w).normalized()
    if mode == "wrapped":
        # Centre inside the curled fingers, rather than below the knuckles.
        return (k2 + k5) / 2 + n * 0.020 - f * 0.006, (k5 - k2).normalized()
    if mode == "press":
        return (k2 + k5) / 2 + n * 0.026 - f * 0.030, (k5 - k2).normalized()
    # In the palm crease just behind the knuckles, so all three phalanges close round it.
    return (k2 + k5) / 2 + n * 0.026 - f * 0.012, (k5 - k2).normalized()


HANDLE_R = 0.015                       # handles, shafts and bars are 13-16 mm radius
FINGER_T = (0.010, 0.009, 0.008)       # bone centre to palm-side skin, per phalanx
THUMB_T = (0.011, 0.010, 0.009)
FINGER_MAX = (85, 95, 70)             # flexion limits (deg) per joint
THUMB_MAX = (45, 60, 50)


def hold(P, side, mode="hook"):
    """Mark a hand as closed on an implement at its grip point this frame; the
    fingers are wrapped round the handle after the props are placed (wrap_holds)."""
    if not hasattr(P, "holds"):
        P.holds = {}
    P.holds[side] = mode


def _line_dist(a, b, c, u, n=6):
    """Closest distance from segment a-b to the line through c along unit u."""
    best = 1e9
    for i in range(n + 1):
        p = a + (b - a) * (i / n) - c
        best = min(best, (p - p.project(u)).length)
    return best


def wrap_fingers(P, side, mode="hook", radius=HANDLE_R):
    """Close each finger joint, knuckle to tip, until its phalanx touches a handle of
    the given radius through the grip point, so the implement sits inside the fist
    instead of beside the curled fingers."""
    import bpy
    from mathutils import Matrix, Quaternion
    g, w = grip_point(P, side, mode)
    u = w.normalized()
    rest_w = (P.rest_head(f"finger5-1.{side}") - P.rest_head(f"finger2-1.{side}")).length
    scale = rest_w / 0.075                    # smaller hands have thinner fingers
    micro = getattr(P, "micro", {})
    chains = [(f"finger{i}", FINGER_T, FINGER_MAX) for i in range(2, 6)]
    chains.append(("finger1", THUMB_T, THUMB_MAX))
    pose = P.rig.pose.bones
    for name, _, _ in chains:
        for j in (1, 2, 3):
            n = f"{name}-{j}.{side}"
            pose[n].rotation_quaternion = micro.get(n, Quaternion())
    bpy.context.view_layer.update()
    for name, thick, limit in chains:
        for j in (1, 2, 3):
            n = f"{name}-{j}.{side}"
            h, v, ax = P.head(n), P.tail(n) - P.head(n), P.axis(n, 0)
            reach_d = radius + thick[j - 1] * scale

            def gap(deg):
                return _line_dist(h, h + Matrix.Rotation(math.radians(deg), 3, ax) @ v, g, u) - reach_d
            angle, prev = limit[j - 1], 0.0
            if gap(0.0) < -0.002 and j == 1:
                # already through the handle: open the knuckle until the phalanx rests on it
                lo, hi = 0.0, -30.0
                if gap(hi) < 0:
                    angle = hi
                else:
                    for _ in range(7):
                        mid = (lo + hi) / 2
                        lo, hi = (mid, hi) if gap(mid) < 0 else (lo, mid)
                    angle = hi
            elif gap(0.0) <= 0:
                angle = 0.0
            else:
                deg = 3.0
                while deg <= limit[j - 1]:
                    if gap(deg) <= 0:
                        lo, hi = prev, deg
                        for _ in range(6):
                            mid = (lo + hi) / 2
                            lo, hi = (lo, mid) if gap(mid) <= 0 else (mid, hi)
                        angle = hi
                        break
                    prev, deg = deg, deg + 3.0
            P.local(n, (1, 0, 0), angle)


def wrap_open(P, side, mode="hook"):
    """How many of fingers 2-5 fail to enclose the handle: seen along the handle, its
    centre must lie inside the loop wrist -> knuckle -> finger joints -> fingertip."""
    g, w = grip_point(P, side, mode)
    u = w.normalized()
    f = (P.head(f"finger3-1.{side}") - P.head(f"wrist.{side}")).normalized()
    f = (f - f.project(u)).normalized()
    n = u.cross(f)

    def flat(p):
        d = p - g
        return d.dot(f), d.dot(n)
    wr = P.head(f"wrist.{side}")
    open_ = 0
    for i in range(2, 6):
        pts = [wr, P.head(f"finger{i}-1.{side}"), P.head(f"finger{i}-2.{side}"),
               P.head(f"finger{i}-3.{side}"), P.tail(f"finger{i}-3.{side}")]
        poly = [flat(p) for p in pts]
        inside = False                      # ray cast from the handle centre (origin)
        for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
            if (y1 > 0) != (y2 > 0) and x1 + (0 - y1) * (x2 - x1) / (y2 - y1) > 0:
                inside = not inside
        open_ += not inside
    return open_


def wrap_holds(P):
    for side, mode in getattr(P, "holds", {}).items():
        wrap_fingers(P, side, mode)


GRIPS = ("over", "under", "neutral", "mixed")


def knuckles(sgn, grip, axis=None):
    """Index -> little-finger direction for a hand on a bar along axis (default world X).
    Overhand: the little finger is on the outside; underhand (supinated) flips it."""
    from mathutils import Vector as V
    a = axis if axis is not None else V((1, 0, 0))
    return a * sgn if grip == "over" else a * -sgn


def bar_palm(bar_axis, forearm, grip):
    """Palm normal for a hand closed around a bar: overhand (pronated) = back of the
    hand toward the bar's far side; underhand (supinated) flips it."""
    n = bar_axis.cross(forearm)
    n = n.normalized() if n.length > 1e-6 else forearm.orthogonal().normalized()
    return n if grip == "over" else -n


def reach(P, side, grip_target, pole, knuckle_dir=None, palm=None, elbow=None, iters=12, fist=True,
          mode="hook"):
    """Put the hand's grip point (see grip_point) on grip_target.

    pole: elbow bend hint (world vector); knuckle_dir: direction the handle runs through
    the fist (index -> little finger); palm: palm normal, or a callable
    palm(forearm_dir) -> vector, recomputed each pass. The wrist target is corrected
    until the grip point lands on the handle (usually 2-6 passes, < 0.5 mm)."""
    upper, lower, end = f"upperarm01.{side}", f"lowerarm01.{side}", f"wrist.{side}"
    if fist:
        P.curl_fingers(side)
        hold(P, side, mode)
    wrist = grip_target.copy()
    err = None
    max_reach = ((P.rest_head(lower) - P.rest_head(upper)).length +
                 (P.rest_head(end) - P.rest_head(lower)).length)
    for it in range(iters):
        sh = P.head(upper)
        k_guess = elbow if elbow is not None else None
        fdir = (wrist - (k_guess if k_guess is not None else P.head(lower))).normalized()
        pv = palm(fdir) if callable(palm) else palm
        P.limb(upper, lower, end, wrist, pole, palm=pv, side=side)
        if knuckle_dir is not None:
            fdir = (P.head(end) - P.head(lower)).normalized()
            pv = palm(fdir) if callable(palm) else (pv if pv is not None else P.palm_now(side))
            P.hand_orient(side, knuckle_dir, pv)
        g, _ = grip_point(P, side, mode)
        err = grip_target - g
        if err.length < 0.0005:
            break
        wrist = wrist + err * (1.0 if it == 0 else 0.6)     # damped: folded arms oscillate
        # never ask for more than the arm can reach: a clamped arm doesn't move
        sh = P.head(upper)
        if (wrist - sh).length > 0.998 * max_reach:
            wrist = sh + (wrist - sh).normalized() * 0.998 * max_reach
    if os.environ.get("FIT_DEBUG"):
        d = (grip_target - P.head(upper)).length
        print(f"REACH {side} err {err.length * 1000:.1f} mm, shoulder->target {d:.3f}")
    return err.length
