"""Model identity and fitted-hair attachment checks, within Blender."""
import math
from core.hair import STYLES


def validate_model(scene, body):
    from bl_ext.user_default.mpfb.services.targetservice import TargetService
    model = scene['fitness_model']
    macro = TargetService.get_macro_info_dict_from_basemesh(body)
    assert macro['gender'] == (1. if model == 'male' else 0.), 'Wrong body macro'
    correction = TargetService.get_target_value(body, 'torso-muscle-pectoral-decr')
    assert correction == (1. if model == 'male' else 0.), 'Wrong pectoral correction'
    assert body.modifiers.get('Chest and axilla pose surface'), 'Missing pose surface correction'
    hair = [o for o in scene.objects if o.type == 'MESH' and o.get('hair')]
    assert len(hair) == 1 and hair[0]['hair_style'] == STYLES[model], 'Wrong fitted hair'
    assert hair[0].data.uv_layers.active, 'Missing hair texture UVs'
    assert all(math.isfinite(c) for v in hair[0].data.vertices for c in v.co)
    return {'model': model, 'gender_macro': macro['gender'], 'hair_style': STYLES[model],
            'max_hair_attachment_mm': 0., 'max_hair_attachment_degrees': 0.}


def check_hair_frame(scene, report):
    root = next(o for o in scene.objects if o.get('hair') and o.type == 'EMPTY')
    constraint = next(c for c in root.constraints if c.type == 'COPY_TRANSFORMS')
    expected = constraint.target.matrix_world @ constraint.target.pose.bones[constraint.subtarget].matrix
    delta = expected.inverted() @ root.matrix_world
    mm = delta.translation.length*1000
    degrees = delta.to_quaternion().angle*180/math.pi
    assert mm < .01 and degrees < .01, 'Hair detached from head'
    report['max_hair_attachment_mm'] = max(report['max_hair_attachment_mm'], round(mm, 6))
    report['max_hair_attachment_degrees'] = max(report['max_hair_attachment_degrees'], round(degrees, 6))
