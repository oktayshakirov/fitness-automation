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
        p = MAPS + f"soft/mask_{i}.png"
        if not os.path.exists(p): p = MAPS + f"mask_{i}.png"
        img = bpy.data.images.load(p, check_existing=True)
        img.colorspace_settings.name = "Non-Color"
        imgs.append(img)
    return imgs


def muscle_material(primary=(), secondary=(), name="body", use_normal=True,
                    base=(0.32, 0.36, 0.42), hot=(0.72, 0.025, 0.018), warm=(0.95, 0.26, 0.025)):
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

    def math_node(operation, a, b=None):
        node = nt.nodes.new("ShaderNodeMath")
        node.operation = operation
        for index, value in enumerate((a, b)):
            if value is None:
                continue
            if isinstance(value, (int, float)):
                node.inputs[index].default_value = value
            else:
                nt.links.new(value, node.inputs[index])
        return node.outputs[0]

    # Treat the smoothed masks as a partition of the skin. Independently mixing
    # each mask with grey left gaps where neighbouring masks were each ~0.5.
    # A modest power tightens the anatomical boundary without UV dilation.
    weights = {g: math_node("POWER", channel(g), 3.0) for g in GROUPS}
    def combined(names):
        total = 0.0
        for g in dict.fromkeys(names):
            total = math_node("ADD", total, weights[g])
        return total

    denominator = math_node("MAXIMUM", combined(GROUPS), .0001)
    primary = tuple(dict.fromkeys(primary))
    secondary = tuple(g for g in dict.fromkeys(secondary) if g not in primary)
    p_weight = combined(primary)
    s_weight = combined(secondary)
    active = math_node("ADD", p_weight, s_weight)
    coverage = math_node("DIVIDE", active, denominator)
    ramp = nt.nodes.new("ShaderNodeMapRange")
    ramp.interpolation_type = "SMOOTHSTEP"
    ramp.inputs["From Min"].default_value = .12
    ramp.inputs["From Max"].default_value = .78
    nt.links.new(coverage, ramp.inputs["Value"])
    active_colour = nt.nodes.new("ShaderNodeMixRGB")
    active_colour.inputs[1].default_value = (*warm, 1)
    active_colour.inputs[2].default_value = (*hot, 1)
    ratio = math_node("DIVIDE", p_weight, math_node("MAXIMUM", active, .0001))
    nt.links.new(ratio, active_colour.inputs[0])
    colour = nt.nodes.new("ShaderNodeMixRGB")
    colour.inputs[1].default_value = (*base, 1)
    nt.links.new(ramp.outputs["Result"], colour.inputs[0])
    nt.links.new(active_colour.outputs[0], colour.inputs[2])
    nt.links.new(colour.outputs[0], bsdf.inputs["Base Color"])

    # Skin-space scalar relief follows deformation and is continuous at UV seams.
    # Never reuse the old raised-mask plateaus or the mirrored tangent normal map.
    height_path = MAPS + "surface_detail_height.png"
    if use_normal and os.path.exists(height_path):
        texture = nt.nodes.new("ShaderNodeTexImage")
        texture.image = bpy.data.images.load(height_path, check_existing=True)
        texture.image.colorspace_settings.name = "Non-Color"
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = .5
        bump.inputs["Distance"].default_value = .004
        nt.links.new(texture.outputs["Color"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
        # Low-contrast muscle belly shading stays readable at phone resolution.
        # It changes colour only: no alpha holes, floating layer or displaced mesh.
        anatomy = math_node("MINIMUM", math_node("MULTIPLY", combined(g for g in GROUPS if g != "neck"), 10.), 1.)
        modulation = math_node("MULTIPLY", math_node("SUBTRACT", texture.outputs["Color"], .5), .12)
        shade = math_node("ADD", 1., math_node("MULTIPLY", anatomy, modulation))
        tint = nt.nodes.new("ShaderNodeMixRGB")
        tint.blend_type = "MULTIPLY"
        tint.inputs[0].default_value = 1.0
        nt.links.new(colour.outputs[0], tint.inputs[1])
        nt.links.new(shade, tint.inputs[2])
        nt.links.new(tint.outputs[0], bsdf.inputs["Base Color"])
    return m


def flat_material(name, rgb, rough=0.45, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m
