"""Blender-only, unpublished RGBA and garment-material review studies.
Run after the four look previews pass; never saves or approves an exercise scene.
"""
import bpy
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.look import muscle_material
from core.clothes import fabric_material, _hide_covered_skin
from core.studio import camera
OUT=ROOT/'review/look_v2';OUT.mkdir(exist_ok=True)
checks=[]
for model in ('male','female'):
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'review'/f'bodyweight_squat_{model}.blend'))
    scene=bpy.context.scene
    hair=[o for o in scene.objects if o.get('hair')]
    assert hair, 'Missing procedural hair'
    scene.frame_set(1);start={o.name:o.matrix_world.copy() for o in hair}
    scene.frame_set(scene.frame_end)
    drift=max((o.matrix_world.translation-start[o.name].translation).length for o in hair)
    rotation=max(o.matrix_world.to_quaternion().rotation_difference(start[o.name].to_quaternion()).angle for o in hair)
    assert drift<.001 and rotation<.008727, 'Hair does not close at the loop seam'
    scene.frame_set(1)
    for obj in scene.objects:
        if obj.get('studio_floor'):obj.hide_render=True
    scene.render.film_transparent=True
    scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA'
    scene.camera=bpy.data.objects['threeq']
    scene.render.filepath=str(OUT/f'transparent_{model}.png')
    bpy.ops.render.render(write_still=True)
    checks.append({'model':model,'hair_loop_mm':round(drift*1000,6),'hair_loop_degrees':round(rotation*57.29578,6)})
    if model=='female':
        rig=next(o for o in scene.objects if o.type=='ARMATURE')
        body=next(o for o in scene.objects if o.get('fitness_body'))
        garments=[o for o in scene.objects if o.get('garment')]
        for garment in garments:
            alpha=garment.data.materials[0].node_tree.nodes['Principled BSDF'].inputs['Alpha']
            assert alpha.default_value==1 and not alpha.is_linked, 'Fabric must remain opaque'
        scene.camera=camera(scene,'Bra material study',(0,-.015,rig.pose.bones['upperarm01.L'].head.z-.10),35,ortho=.76)
        scene.render.filepath=str(OUT/'bra_inactive.png');bpy.ops.render.render(write_still=True)
        body.data.materials.clear();body.data.materials.append(muscle_material(primary=('chest',)))
        old=body.data.attributes.get('clothing_covered')
        if old:body.data.attributes.remove(old)
        _hide_covered_skin(body,rig.data.bones['upperleg01.L'].head_local.z,
                           rig.data.bones['lowerleg01.L'].head_local.z,
                           rig.data.bones['upperarm01.L'].head_local.z,model)
        material=fabric_material(primary=('chest',))
        for garment in garments:
            garment.data.materials.clear();garment.data.materials.append(material)
        scene.render.filepath=str(OUT/'bra_active.png');bpy.ops.render.render(write_still=True)
(OUT/'study_checks.json').write_text(json.dumps(checks,indent=2)+'\n')
