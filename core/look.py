"""Body look: muscle-mask material (primary red, secondary orange) and flat materials."""
import bpy, math, os
from . import MAPS

# free-exercise-db's 17 muscle groups, packed 3 per RGB mask image
GROUPS = ["quadriceps", "hamstrings", "glutes", "adductors", "abductors", "calves",
          "abdominals", "lower back", "middle back", "lats", "traps", "shoulders",
          "chest", "biceps", "triceps", "forearms", "neck"]


def mask_slot(group):
    i = GROUPS.index(group)
    return i // 3, i % 3  # (image index, channel)


def load_masks():
    imgs = []
    for i in range(math.ceil(len(GROUPS) / 3)):
        p = MAPS + f"mask_{i}.png"
        img = bpy.data.images.load(p, check_existing=True)
        img.colorspace_settings.name = "Non-Color"
        imgs.append(img)
    return imgs


def muscle_material(primary=(), secondary=(), name="body", use_normal=False,
                    base=(0.5, 0.52, 0.56), hot=(0.86, 0.06, 0.03), warm=(0.98, 0.42, 0.06)):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.48
    imgs = load_masks()
    tex_nodes, sep_nodes = {}, {}

    def channel(group):
        i, c = mask_slot(group)
        if i not in tex_nodes:
            t = nt.nodes.new("ShaderNodeTexImage"); t.image = imgs[i]
            s = nt.nodes.new("ShaderNodeSeparateColor")
            nt.links.new(t.outputs["Color"], s.inputs["Color"])
            tex_nodes[i], sep_nodes[i] = t, s
        return sep_nodes[i].outputs[c]

    def combined(groups):
        out = None
        for g in groups:
            ch = channel(g)
            if out is None:
                out = ch
            else:
                mx = nt.nodes.new("ShaderNodeMath"); mx.operation = "MAXIMUM"
                nt.links.new(out, mx.inputs[0]); nt.links.new(ch, mx.inputs[1])
                out = mx.outputs[0]
        return out

    color = None
    col_base = nt.nodes.new("ShaderNodeRGB"); col_base.outputs[0].default_value = (*base, 1)
    color = col_base.outputs[0]
    for groups, rgb in ((secondary, warm), (primary, hot)):
        if not groups:
            continue
        mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"
        mix.inputs["B"].default_value = (*rgb, 1)
        nt.links.new(color, mix.inputs["A"])
        # sharpen the baked mask edge a little
        ramp = nt.nodes.new("ShaderNodeMapRange")
        ramp.inputs["From Min"].default_value = 0.25
        ramp.inputs["From Max"].default_value = 0.6
        nt.links.new(combined(groups), ramp.inputs["Value"])
        nt.links.new(ramp.outputs["Result"], mix.inputs["Factor"])
        color = mix.outputs["Result"]
    nt.links.new(color, bsdf.inputs["Base Color"])
    nmap_path = MAPS + "muscle_normal.png"
    if use_normal and os.path.exists(nmap_path):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(nmap_path, check_existing=True)
        t.image.colorspace_settings.name = "Non-Color"
        nm = nt.nodes.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = 0.8
        nt.links.new(t.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def flat_material(name, rgb, rough=0.45, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m
