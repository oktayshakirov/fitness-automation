"""Micro-motion: the small life a real person shows during a set, layered under the
pattern so form never changes. Everything is periodic over the loop (integer cycles),
so frame 1 still equals the last frame.

- breathing: two breaths per loop, a fraction of a degree of upper-spine extension
- head settle: a slow sub-degree drift of the neck and head
- weight shift: a few millimetres of pelvis sway in standing patterns (feet stay planted:
  the leg IK absorbs it)

The offsets are handed to the Poser (P.micro, P.micro_shift); P.reset() applies them and
P.local() composes with them, and place_pelvis() adds the shift, so contacts are solved
after them."""
import math
from mathutils import Quaternion, Vector

TAU = 2 * math.pi


def set_frame(P, f, n, amp=1.0):
    if amp <= 0:
        P.micro, P.micro_shift = {}, Vector()
        return
    u = (f - 1) / max(1, n - 1)
    breath = math.sin(TAU * 2 * u)
    q = lambda axis, deg: Quaternion(axis, math.radians(deg * amp))
    X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)
    P.micro = {
        "spine02": q(X, -0.45 * breath),
        "spine01": q(X, -0.55 * breath),
        "neck02": q(X, 0.5 * math.sin(TAU * u + 1.3) + 0.25 * math.sin(TAU * 2 * u + 0.4)),
        "head": q(Y, 0.6 * math.sin(TAU * u + 2.1)),
    }
    P.micro_shift = Vector((0.006 * math.sin(TAU * u + 0.7), 0.003 * math.sin(TAU * 2 * u), 0)) * amp
