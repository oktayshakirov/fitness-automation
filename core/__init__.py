"""Shared Blender pipeline: body.py + solver.py pose the figure; look.py,
studio.py, render.py shade and render it. Interfaces only change by adding."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/"
MAPS = ROOT + "assets/maps/"
OUT = ROOT + "review/"
