#!/usr/bin/env python3
"""Directional regression check for the two seated knee machines.

python3 qa/check_seated_feet.py [--render]
Checks both feet at every saved frame. Unlike a knee-plane check, the signed
anterior direction rejects toes pointing behind the shins. Optional close-ups
hide the equipment, so the base/rollers cannot obscure the ankle and toes.
"""
import json, math, os, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
try:
    import bpy
except ImportError:
    env = dict(os.environ, BLENDER_USER_RESOURCES=str(ROOT / '.blender-profile'))
    raise SystemExit(subprocess.run([
        '/Applications/Blender.app/Contents/MacOS/Blender', '-b',
        '--python-exit-code', '1', '--python', str(Path(__file__).resolve()),
        '--', *sys.argv[1:]], env=env).returncode)

sys.path.insert(0, str(ROOT))
from mathutils import Vector
from core.solver import Poser
from core.studio import camera
from core.delivery import current_qa

out = ROOT / 'review/feet_revision'
out.mkdir(exist_ok=True)
reports = []
for eid in ('leg_extension', 'leg_curl'):
    current_qa(eid)  # The saved scene must match the current source and motion.
    bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'review' / f'{eid}.blend'))
    scene = bpy.context.scene
    P = Poser(next(o for o in scene.objects if o.type == 'ARMATURE'))
    deviations, changes, previous = [], [], {}
    for f in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(f)
        for side in ('L', 'R'):
            ankle = P.head(f'foot.{side}')
            shin = (ankle - P.head(f'lowerleg01.{side}')).normalized()
            toe = (P.head(f'toe3-1.{side}') - ankle).normalized()
            front = Vector((0, -1, 0))
            front = (front - front.project(shin)).normalized()
            angle = math.degrees(toe.angle(front))
            assert angle < 30, (eid, f, side, 'toes face away from shin front', angle)
            deviations.append(angle)
            # Measure ankle continuity relative to the moving shin, not world
            # speed: the leg intentionally accelerates during each repetition.
            relative = Vector((toe.dot(front), toe.dot(shin),
                               toe.dot(shin.cross(front))))
            if side in previous:
                change = math.degrees(relative.angle(previous[side]))
                assert change < 5, (eid, f, side, 'ankle orientation jumps', change)
                changes.append(change)
            previous[side] = relative
    reports.append(dict(id=eid, frames=scene.frame_end, feet_checked=2,
                        max_direction_deviation_deg=max(deviations),
                        max_ankle_frame_change_deg=max(changes), passed=True))
    if '--render' in sys.argv:
        for obj in scene.objects:
            if obj.type == 'MESH' and not obj.find_armature():obj.hide_render=True
        scene.render.resolution_x = scene.render.resolution_y = 600
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = 'PNG'
        for f in (1, 32):
            scene.frame_set(f)
            target = (P.head('foot.L') + P.head('toe3-1.L')) / 2
            scene.camera = camera(scene, 'feet_closeup', target, 75,
                                  ortho=.60, height=target.z + .3)
            scene.render.filepath = str(out / f'{eid}_{f}.png')
            bpy.ops.render.render(write_still=True)
(out / 'direction_check.json').write_text(json.dumps(reports, indent=2) + '\n')
print('FEET CHECK:', json.dumps(reports), flush=True)
