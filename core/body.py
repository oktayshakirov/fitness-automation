"""The MPFB2 body. Run Blender with BLENDER_USER_RESOURCES=<repo>/.blender-profile
so MPFB2 is importable (bl_ext.user_default.mpfb)."""
import bpy


def update():
    bpy.context.view_layer.update()


def make_human(gender=1.0, muscle=0.8, weight=0.45):
    """MPFB body + default 163-bone rig at the origin, facing -Y, feet on z=0.
    Rig object at identity, so armature space = world space."""
    from bl_ext.user_default.mpfb.services.humanservice import HumanService
    from bl_ext.user_default.mpfb.services.targetservice import TargetService
    macro = TargetService.get_default_macro_info_dict()
    macro["gender"] = gender
    macro["muscle"] = muscle
    macro["weight"] = weight
    body = HumanService.create_human(macro_detail_dict=macro)
    rig = HumanService.add_builtin_rig(body, "default")
    for pb in rig.pose.bones:
        pb.rotation_mode = "QUATERNION"
    update()
    return body, rig


def key_pose(rig, f):
    """Keyframe every pose bone, so the saved .blend replays (and can export to GLB)."""
    for pb in rig.pose.bones:
        pb.keyframe_insert("rotation_quaternion", frame=f)
        pb.keyframe_insert("location", frame=f)
