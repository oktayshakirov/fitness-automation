"""Shared Blender pipeline. Ownership (plan.md): body.py + solver.py = Agent A;
look.py, studio.py, render.py = Agent B. Interfaces only change by adding."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/"
MAPS = ROOT + "assets/maps/"
OUT = ROOT + "review/"
