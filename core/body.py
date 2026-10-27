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

