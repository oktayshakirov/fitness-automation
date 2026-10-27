"""Model identity and fitted-hair attachment checks, within Blender."""
import math
from core.hair import STYLES


def validate_model(scene, body):
    from bl_ext.user_default.mpfb.services.targetservice import TargetService
    model = scene['fitness_model']
    macro = TargetService.get_macro_info_dict_from_basemesh(body)
    assert macro['gender'] == (1. if model == 'male' else 0.), 'Wrong body macro'
    expected_cup, expected_firmness = (.89, .55) if model == 'female' else (.5, .5)
    assert abs(macro['cupsize']-expected_cup) < 1e-6, 'Wrong bust volume macro'
    assert abs(macro['firmness']-expected_firmness) < 1e-6, 'Wrong bust firmness macro'
    assert abs(macro['muscle']-.95)<1e-6 and abs(macro['weight']-.40)<1e-6, 'Wrong athletic build'
    correction = TargetService.get_target_value(body, 'torso-muscle-pectoral-decr')
    assert correction == (1. if model == 'male' else 0.), 'Wrong pectoral correction'
    for detail, expected in (('breast-dist-decr', .45), ('breast-trans-up', .12), ('breast-point-decr', .85), ('nipple-point-decr', 1.0), ('breast-volume-vert-down', .10)):
        actual = TargetService.get_target_value(body, detail)
        assert abs(actual-(expected if model == 'female' else 0.)) < 1e-6, 'Wrong female contour detail'
    assert body.modifiers.get('Chest and axilla pose surface'), 'Missing pose surface correction'
    face_detail = 'head-square' if model == 'male' else 'head-oval'
    assert abs(TargetService.get_target_value(body, face_detail)-(.32 if model=='male' else .30)) < 1e-6, 'Wrong face profile'
    assert len([o for o in scene.objects if o.get('coloured_eye')]) == 2, 'Missing coloured eyes'
    assert len([o for o in scene.objects if o.get('smartwatch')]) == 4, 'Missing watch parts'
    assert len([o for o in scene.objects if o.get('shoe')]) == 12, 'Missing shoes'
    assert scene.objects['Smartwatch screen'].location.z < 0, 'Watch display on palm side'
    assert scene.objects['Watch follows wrist'].constraints[0].subtarget == 'wrist.L', 'Watch must follow hand orientation'
    assert body.data.attributes.get('beard_shade'), 'Missing facial shading'
    assert len([o for o in scene.objects if o.name.startswith('Eyebrow ')]) == 2, 'Missing eyebrows'
    assert len([o for o in scene.objects if o.name.startswith('Upper lashes ')]) == 2, 'Missing lashes'
    if model == 'female':assert scene.objects.get('Ponytail elastic band'), 'Missing ponytail band'
    hair = [o for o in scene.objects if o.type == 'MESH' and o.get('hair')]
    assert len(hair) == 1 and hair[0]['hair_style'] == STYLES[model], 'Wrong fitted hair'
    assert hair[0].data.uv_layers.active, 'Missing hair texture UVs'
    assert all(math.isfinite(c) for v in hair[0].data.vertices for c in v.co)
    return {'model': model, 'gender_macro': macro['gender'], 'cupsize_macro': macro['cupsize'], 'firmness_macro': macro['firmness'], 'hair_style': STYLES[model],
            'max_hair_attachment_mm': 0., 'max_hair_attachment_degrees': 0.}


def check_hair_frame(scene, report):
    for a in [o for o in scene.objects if o.get('accessory_anchor')]:
        c=a.constraints[0]
        expected=c.target.matrix_world @ c.target.pose.bones[c.subtarget].matrix
        delta=expected.inverted() @ a.matrix_world
        assert delta.translation.length < .00001 and delta.to_quaternion().angle < .0002, 'Accessory detached'
    for sole in [o for o in scene.objects if o.name.startswith('Trainer sole')]:
        evaluated=sole.evaluated_get(__import__('bpy').context.evaluated_depsgraph_get())
        lowest=min((evaluated.matrix_world @ v.co).z for v in evaluated.data.vertices)
        assert lowest >= -.004, f'Shoe crosses floor: {lowest:.4f} m'
    root = next(o for o in scene.objects if o.get('hair') and o.type == 'EMPTY')
    constraint = next(c for c in root.constraints if c.type == 'COPY_TRANSFORMS')
    expected = constraint.target.matrix_world @ constraint.target.pose.bones[constraint.subtarget].matrix
    delta = expected.inverted() @ root.matrix_world
    mm = delta.translation.length*1000
    degrees = delta.to_quaternion().angle*180/math.pi
    assert mm < .01 and degrees < .01, 'Hair detached from head'
    report['max_hair_attachment_mm'] = max(report['max_hair_attachment_mm'], round(mm, 6))
    report['max_hair_attachment_degrees'] = max(report['max_hair_attachment_degrees'], round(degrees, 6))
