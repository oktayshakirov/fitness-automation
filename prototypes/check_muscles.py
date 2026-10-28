"""Coverage check: all 17 baked muscle groups in distinct colours on the MPFB
body, front + back + side, rest pose."""
import bpy, sys, colorsys
import os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root
from common import (OUT, GROUPS, mask_slot, new_scene, make_human, load_masks, studio, camera,
                    contact_sheet)

scene = new_scene()
body, rig = make_human()
m = bpy.data.materials.new("groups"); m.use_nodes = True
nt = m.node_tree
bsdf = nt.nodes["Principled BSDF"]
imgs = load_masks()
seps = []
for img in imgs:
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = img
    s = nt.nodes.new("ShaderNodeSeparateColor"); nt.links.new(t.outputs[0], s.inputs[0])
    seps.append(s)
col = nt.nodes.new("ShaderNodeRGB"); col.outputs[0].default_value = (0.7, 0.7, 0.72, 1)
out = col.outputs[0]
for k, g in enumerate(GROUPS):
    i, c = mask_slot(g)
    h = (k * 0.618) % 1.0
    rgb = colorsys.hsv_to_rgb(h, 0.85, 0.9)
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"
    mix.inputs["B"].default_value = (*rgb, 1)
    nt.links.new(out, mix.inputs["A"])
    nt.links.new(seps[i].outputs[c], mix.inputs["Factor"])
    out = mix.outputs["Result"]
    print("COLOR", g, tuple(round(x, 2) for x in rgb))
nt.links.new(out, bsdf.inputs["Base Color"])
body.data.materials.clear(); body.data.materials.append(m)
studio(scene, floor=False)
tgt = (0, 0, 0.9)
cams = [camera(scene, n, tgt, y, ortho=1.95) for n, y in (("front", 0), ("back", 180), ("side", 90))]
scene.render.resolution_x, scene.render.resolution_y = 600, 1000
paths = []
for c in cams:
    scene.camera = c
    scene.render.filepath = OUT + f"groups_{c.name}.png"
    bpy.ops.render.render(write_still=True)
    paths.append(scene.render.filepath)
import subprocess
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *sum([["-i", p] for p in paths], []),
                "-filter_complex", "hstack=inputs=3", OUT + "groups_sheet.png"], check=True)
print("SHEET", OUT + "groups_sheet.png")
