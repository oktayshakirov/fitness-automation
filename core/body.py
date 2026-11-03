"""The MPFB2 body. Run Blender with BLENDER_USER_RESOURCES=<repo>/.blender-profile
so MPFB2 is importable (bl_ext.user_default.mpfb)."""
import bpy
import math
from mathutils import Vector


def update():
    bpy.context.view_layer.update()


def make_human(gender=1.0, muscle=0.95, weight=0.40, shoulder_smooth=False, press_proportions=False, preserve_volume=True):
    """MPFB body + default 163-bone rig at the origin, facing -Y, feet on z=0.
    Rig object at identity, so armature space = world space."""
    from bl_ext.user_default.mpfb.services.humanservice import HumanService
    from bl_ext.user_default.mpfb.services.targetservice import TargetService
    macro = TargetService.get_default_macro_info_dict()
    macro["gender"] = gender
    macro["muscle"] = muscle
    macro["weight"] = weight
    if gender == 0.0:
        # Fuller volume with a relaxed, supported lower contour for the adult athlete.
        # Keep these female-only: MPFB cup/firmness details are not male morphs.
        macro["cupsize"] = .89
        macro["firmness"] = .55
    body = HumanService.create_human(macro_detail_dict=macro)
    # The stock high-muscle male macro has a bulbous lower pectoral contour.
    # Use the authored MPFB correction before fitting the rig/clothing; leave
    # female breast anatomy independent of this male-only detail target.
    if gender == 1.0:
        from pathlib import Path
        from bl_ext.user_default.mpfb.services.locationservice import LocationService
        target = Path(LocationService.get_mpfb_data("targets")) / "torso/torso-muscle-pectoral-decr.target.gz"
        TargetService.load_target(body, str(target), weight=1.0)
    if gender == 0.0:
        from pathlib import Path
        from bl_ext.user_default.mpfb.services.locationservice import LocationService
        targets = Path(LocationService.get_mpfb_data("targets")) / "breast"
        # Round the profile rather than increasing only its pointed projection.
        for detail, strength in (("breast-dist-decr", .45), ("breast-trans-up", .12), ("breast-point-decr", .85), ("nipple-point-decr", 1.0), ("breast-volume-vert-down", .10)):
            TargetService.load_target(body, str(targets / (detail + ".target.gz")), weight=strength)
    from pathlib import Path
    from bl_ext.user_default.mpfb.services.locationservice import LocationService
    targets = Path(LocationService.get_mpfb_data("targets"))
    face = (("head/head-square", .32), ("chin/chin-width-incr", .25),
            ("chin/chin-prominent-incr", .18), ("nose/nose-width1-incr", .08)) if gender == 1.0 else (
            ("head/head-oval", .30), ("chin/chin-width-decr", .25),
            ("chin/chin-prominent-decr", .08), ("nose/nose-width1-decr", .12),
            ("mouth/mouth-upperlip-volume-incr", .18), ("mouth/mouth-lowerlip-volume-incr", .10))
    for detail, strength in face:
        TargetService.load_target(body, str(targets / (detail + ".target.gz")), weight=strength)
    rig = HumanService.add_builtin_rig(body, "default")
    # Dual-quaternion skinning preserves volume during axial twist. The overhead
    # press opts out: blended shoulder rotations otherwise produce large armpit bulges.
    for modifier in body.modifiers:
        if modifier.type == "ARMATURE":
            modifier.use_deform_preserve_volume = preserve_volume
    if shoulder_smooth:
        # Confine a silhouette correction to the shoulder/upper arm. The default
        # MPFB weights form sharp folds at overhead elevation; hands stay untouched.
        group = body.vertex_groups.new(name="shoulder_corrective")
        indices = {body.vertex_groups[n + "." + side].index
                   for side in ("L", "R")
                   for n in ("shoulder01", "upperarm01", "upperarm02")}
        for v in body.data.vertices:
            weight = min(1.0, sum(g.weight for g in v.groups if g.group in indices))
            if weight:
                group.add([v.index], weight, "REPLACE")
        # Shoulder/arm weights on the central ribcage otherwise pull the back
        # upward with the humerus. Blend them into the torso while preserving
        # the lateral deltoid and upper trapezius attachments and total weight.
        def ramp(value, lo, hi):
            t = max(0.0, min(1.0, (value-lo)/(hi-lo)))
            return t*t*(3-2*t)
        shoulder_groups = {body.vertex_groups[n+"."+side].index:
                           body.vertex_groups[n+"."+side]
                           for side in ("L", "R")
                           for n in ("shoulder01", "upperarm01", "upperarm02", "clavicle")}
        spine = body.vertex_groups["spine01"]
        for v in body.data.vertices:
            blend = (1-ramp(abs(v.co.x), .13, .22)) * (1-ramp(v.co.z, 1.30, 1.43))
            if v.co.z < 1.08 or blend < .001:
                continue
            old = next((g.weight for g in v.groups if g.group == spine.index), 0.0)
            transfer = 0.0
            for g in list(v.groups):
                if g.group in shoulder_groups:
                    transfer += g.weight*blend
                    shoulder_groups[g.group].add([v.index], g.weight*(1-blend), "REPLACE")
            if transfer:
                spine.add([v.index], old+transfer, "REPLACE")
        correction = body.modifiers.new("Shoulder silhouette", "CORRECTIVE_SMOOTH")
        correction.use_only_smooth = True
        correction.factor = .5
        correction.iterations = 5
        correction.smooth_type = "LENGTH_WEIGHTED"
        correction.vertex_group = group.name
    # Lowered arms also fold the stock chest/axilla weights. Smooth only the
    # chest and shoulder regions after deformation, before clothing follows skin.
    chest_group = body.vertex_groups.new(name="chest_pose_surface")
    chest_indices = {g.index for g in body.vertex_groups
                     if g.name.startswith(("breast.", "upperarm", "shoulder"))}
    for vertex in body.data.vertices:
        strength = min(1., sum(g.weight for g in vertex.groups if g.group in chest_indices))
        if strength:
            chest_group.add([vertex.index], strength, "REPLACE")
    surface = body.modifiers.new("Chest and axilla pose surface", "CORRECTIVE_SMOOTH")
    surface.use_only_smooth = True
    surface.factor = .5
    surface.iterations = 10
    surface.vertex_group = chest_group.name
    _flatten_crotch(body, rig)
    if press_proportions:
        _shape_press_proportions(body, rig)
    for pb in rig.pose.bones:
        pb.rotation_mode = "QUATERNION"
    update()
    from core.accessories import add_eyes
    add_eyes(rig, gender)
    from core.face_details import add_face_details
    add_face_details(body, rig, gender)
    return body, rig


def key_pose(rig, f):
    """Keyframe every pose bone, so the saved .blend replays (and can export to GLB)."""
    for pb in rig.pose.bones:
        pb.keyframe_insert("rotation_quaternion", frame=f)
        pb.keyframe_insert("location", frame=f)
        pb.keyframe_insert("scale", frame=f)


def _crotch_weight(p, hip_z):
    """1 at the centre of the groin, fading out over the inner thighs, belly and seat."""
    def ramp(v, lo, hi):
        t = max(0., min(1., (v-lo)/(hi-lo))); return t*t*(3-2*t)
    return ((1-ramp(abs(p.x), .035, .080)) * (1-ramp(p.z, hip_z-.035, hip_z+.005)) *
            ramp(p.z, hip_z-.125, hip_z-.105) * (1-ramp(p.y, .020, .060)))


def _flatten_crotch(body, rig):
    """Flat groin under the shorts on both bodies: smooth the stock genital shape out
    of the rest pose (shape key), then smooth again after posing so deep hip flexion
    (squats, lunges) can't fold the skin into a hanging lump between the legs."""
    states = [(m, m.show_viewport) for m in body.modifiers]
    for m, _ in states: m.show_viewport = False
    bpy.context.view_layer.update()
    ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get()); mesh = ev.to_mesh()
    points = [v.co.copy() for v in mesh.vertices]
    edges = [tuple(e.vertices) for e in mesh.edges]
    ev.to_mesh_clear()
    for m, state in states: m.show_viewport = state
    helper = {g.index for g in body.vertex_groups if g.name in ("HelperGeometry", "JointCubes")}
    skin = [not any(g.group in helper for g in v.groups) for v in body.data.vertices]
    hips = (rig.data.bones["upperleg01.L"].head_local + rig.data.bones["upperleg01.R"].head_local) / 2
    weight = [_crotch_weight(p, hips.z) if s else 0. for p, s in zip(points, skin)]
    near = [[] for _ in points]
    for a, b in edges:
        if skin[a] and skin[b]:
            near[a].append(b); near[b].append(a)
    region = [i for i, w in enumerate(weight) if w > 0 and near[i]]
    flat = [p.copy() for p in points]
    for _ in range(60):
        nxt = {i: flat[i] + (sum((flat[j] for j in near[i]), Vector()) / len(near[i]) - flat[i]) * .5 * weight[i]
               for i in region}
        for i, p in nxt.items(): flat[i] = p
    key = body.shape_key_add(name="Flat groin", from_mix=False)
    for i in region:
        key.data[i].co += flat[i] - points[i]
    key.value = 1
    group = body.vertex_groups.new(name="groin_pose_surface")
    for i in region:
        group.add([i], weight[i], "REPLACE")
    surface = body.modifiers.new("Groin pose surface", "CORRECTIVE_SMOOTH")
    surface.use_only_smooth = True
    surface.factor = .5
    surface.iterations = 12
    surface.vertex_group = group.name
    bpy.context.view_layer.update()


def _shape_press_proportions(body, rig):
    """Add smooth rest-space arm/shoulder volume and waist breadth; preserve topology,
    bone lengths, joints and hand contacts. Opt-in per exercise."""

    # Evaluate macro shape keys without topology-changing or pose modifiers.
    states=[(m,m.show_viewport) for m in body.modifiers]
    for m,_ in states:m.show_viewport=False
    bpy.context.view_layer.update()
    ev=body.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
    points=[v.co.copy() for v in mesh.vertices];ev.to_mesh_clear()
    for m,state in states:m.show_viewport=state
    assert len(points)==len(body.data.vertices)
    key=body.shape_key_add(name='Press athletic proportions',from_mix=False)
    groups={g.name:g.index for g in body.vertex_groups}
    def ramp(v,lo,hi):
        t=max(0.,min(1.,(v-lo)/(hi-lo)));return t*t*(3-2*t)
    for v,p in zip(body.data.vertices,points):
        weights={g.group:g.weight for g in v.groups};delta=Vector()
        for side in ('L','R'):
            a=rig.data.bones['upperarm01.'+side].head_local
            b=rig.data.bones['lowerarm01.'+side].head_local
            c=rig.data.bones['wrist.'+side].head_local
            upper=sum(weights.get(groups[n+'.'+side],0) for n in ('upperarm01','upperarm02','shoulder01'))
            upper*=ramp(abs(p.x),.13,.22)
            axis=(b-a).normalized();t=max(0,min(1,(p-a).dot(axis)/(b-a).length))
            radial=(p-a)-axis*(p-a).dot(axis)
            delta+=radial*upper*(.30+.20*math.sin(math.pi*t))
            fore=sum(weights.get(groups[n+'.'+side],0) for n in ('lowerarm01','lowerarm02'))
            axis=(c-b).normalized();t=max(0,min(1,(p-b).dot(axis)/(c-b).length))
            radial=(p-b)-axis*(p-b).dot(axis)
            delta+=radial*fore*.14*math.sin(math.pi*t)
        trunk=sum(weights.get(groups[n],0) for n in ('root','spine01','spine02','spine03','spine04','spine05') if n in groups)
        waist=.16*math.exp(-((p.z-1.04)/.16)**4)*min(1,trunk)
        delta.x+=p.x*waist
        delta.y+=p.y*waist*.3
        key.data[v.index].co+=delta
    key.value=1
    bpy.context.view_layer.update()



def pad_planes(pads):
    """Contact face of each tagged pad cube (obj['contact_face'] '+Z' or '-Y'), in world
    space: (origin, along, across, normal, half_along, half_across)."""
    planes = []
    for o in pads:
        m = o.matrix_world
        lo = Vector([min(c[i] for c in o.bound_box) for i in range(3)])
        hi = Vector([max(c[i] for c in o.bound_box) for i in range(3)])
        mid = (lo + hi) / 2
        ax = [m.to_3x3() @ Vector(c) for c in ((1, 0, 0), (0, 1, 0), (0, 0, 1))]
        half = [(hi[i] - lo[i]) / 2 * ax[i].length for i in range(3)]
        ax = [a.normalized() for a in ax]
        if o["contact_face"] == "+Z":
            planes.append((m @ Vector((mid.x, mid.y, hi.z)), ax[0], ax[1], ax[2], half[0], half[1]))
        else:
            planes.append((m @ Vector((mid.x, lo.y, mid.z)), ax[0], ax[2], -ax[1], half[0], half[2]))
    return planes


def add_pad_contact(obj, planes, lift=0.0, depth=0.08, fade=0.02):
    """Soft-pad contact as the last modifier: skin (or cloth, hair) that sinks into a pad
    face is pushed back onto it, so a body settled a little into the seat or bench lies
    flat on it instead of touching at one point. Off the pad's footprint the floor
    drops away at 45 deg, so the pad's edges never cut into a thigh draped over them;
    points deeper than `depth` below the face are left alone."""
    ng = bpy.data.node_groups.new("Pad contact " + obj.name, "GeometryNodeTree")
    ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, L = ng.nodes, ng.links
    geo = N.new("NodeGroupInput").outputs[0]

    def vec(op, a, b=None, scale=None):
        n = N.new("ShaderNodeVectorMath"); n.operation = op
        for i, v in ((0, a), (1, b)):
            if v is None: continue
            if isinstance(v, Vector): n.inputs[i].default_value = v
            else: L.new(v, n.inputs[i])
        if scale is not None:
            if isinstance(scale, float): n.inputs[3].default_value = scale
            else: L.new(scale, n.inputs[3])
        return n.outputs[1] if op == "DOT_PRODUCT" else n.outputs[0]

    def num(op, a, b=None):
        n = N.new("ShaderNodeMath"); n.operation = op
        for i, v in ((0, a), (1, b)):
            if v is None: continue
            if isinstance(v, float): n.inputs[i].default_value = v
            else: L.new(v, n.inputs[i])
        return n.outputs[0]

    for origin, along, across, normal, ha, hc in planes:
        pos = N.new("GeometryNodeInputPosition").outputs[0]
        rel = vec("SUBTRACT", pos, Vector(origin + normal * lift))
        la, lc, lz = (vec("DOT_PRODUCT", rel, Vector(a)) for a in (along, across, normal))
        da = num("MAXIMUM", num("SUBTRACT", num("ABSOLUTE", la), ha), 0.0)
        dc = num("MAXIMUM", num("SUBTRACT", num("ABSOLUTE", lc), hc), 0.0)
        floor = num("MULTIPLY", num("SQRT", num("ADD", num("MULTIPLY", da, da), num("MULTIPLY", dc, dc))), -1.0)
        push = num("MAXIMUM", num("SUBTRACT", floor, lz), 0.0)
        ramp = N.new("ShaderNodeMapRange"); ramp.clamp = True
        L.new(lz, ramp.inputs[0])
        ramp.inputs[1].default_value, ramp.inputs[2].default_value = -depth, -depth + fade
        push = num("MULTIPLY", push, ramp.outputs[0])
        setp = N.new("GeometryNodeSetPosition")
        L.new(geo, setp.inputs["Geometry"])
        L.new(vec("SCALE", Vector(normal), scale=push), setp.inputs["Offset"])
        geo = setp.outputs[0]
    L.new(geo, N.new("NodeGroupOutput").inputs[0])
    mod = obj.modifiers.new("Pad contact", "NODES")
    mod.node_group = ng
    return mod
