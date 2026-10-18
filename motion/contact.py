import math
import os
"""Hand contact: where an implement sits in the closed hand."""


def grip_point(P, side, mode="hook"):
    """Handle centre in the closed hand, and the knuckle-line direction (index -> little
    finger). mode "hook" (pulling, carrying): across the palm at the knuckle line.
    mode "press" (pressing): low in the palm over the heel of the hand, so the bar sits
    over the forearm bones."""
    k2, k5 = P.head(f"finger2-1.{side}"), P.head(f"finger5-1.{side}")
    w = P.head(f"wrist.{side}")
    k3 = P.head(f"finger3-1.{side}")
    n = P.palm_now(side)
    f = (k3 - w).normalized()
    if mode == "wrapped":
        # Centre inside the curled fingers, rather than below the knuckles.
        return (k2 + k5) / 2 + n * 0.020 - f * 0.006, (k5 - k2).normalized()
    if mode == "press":
        return w + ((k2 + k5) / 2 - w) * 0.45 + n * 0.03, (k5 - k2).normalized()
    return (k2 + k5) / 2 + n * 0.024 + f * 0.012, (k5 - k2).normalized()


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
