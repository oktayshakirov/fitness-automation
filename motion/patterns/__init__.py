"""Movement patterns. Each module defines `Pattern(P, params)` with `pose(s)` (s = 0..1
phase, called after P.reset()) and optional `camera_target`."""
import importlib

NAMES = ("stand_hinge", "arm_isolation")


def get(name):
    return importlib.import_module(f"motion.patterns.{name}").Pattern
