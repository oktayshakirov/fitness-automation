"""Dump pose-bone and object world matrices of an animated .blend to JSON, so a
refactor can be checked numerically against a golden build.
Usage: blender -b <file.blend> --python qa/pose_dump.py -- <out.json> [frames]"""
import bpy, json, sys

args = sys.argv[sys.argv.index("--") + 1:]
out = args[0]
frames = [int(x) for x in args[1].split(",")] if len(args) > 1 else None
scene = bpy.context.scene
rig = next(o for o in scene.objects if o.type == "ARMATURE")
if frames is None:
    frames = list(range(1, 73))
data = {}
for f in frames:
    scene.frame_set(f)
    d = {"bones": {pb.name: [list(r) for r in pb.matrix] for pb in rig.pose.bones},
         "objects": {o.name: [list(r) for r in o.matrix_world] for o in scene.objects
                     if o.animation_data and o.type != "ARMATURE"}}
    data[f] = d
json.dump(data, open(out, "w"))
print("DUMPED", out, len(frames))
