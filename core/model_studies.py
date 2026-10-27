"""Unpublished neutral model review, run inside Blender before exercise QA."""
import bpy, sys, json, os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bl_ext.user_default.mpfb.services.targetservice import TargetService
from core.body import make_human
from core.hair import add_hair
from core.clothes import add_clothing
from core.look import muscle_material
from core.studio import studio,camera
OUT=ROOT/'review/look_v18';OUT.mkdir(exist_ok=True)
checks=[]
models=os.environ.get('STUDY_MODELS','male,female').split(',')
assert set(models) <= {'male','female'}
for model in models:
 bpy.ops.wm.read_factory_settings(use_empty=True)
 scene=bpy.context.scene
 body,rig=make_human(gender=1.0 if model=='male' else 0.0)
 body['fitness_body']=True
 body.data.materials.append(muscle_material())
 garments=add_clothing(body,rig,model)
 hair=add_hair(body,rig,model)
 studio(scene,transparent=True)
 scene.render.resolution_x=600;scene.render.resolution_y=750;scene.render.resolution_percentage=100
 scene.render.image_settings.file_format='PNG'
 shoulder=rig.data.bones['upperarm01.L'].head_local.z
 top=max((body.matrix_world@v.co).z for v in body.data.vertices)
 # Head camera uses fitted hair bounds, not the undeformed base mesh head.
 bpy.context.view_layer.update()
 dg=bpy.context.evaluated_depsgraph_get()
 ev=hair[0].evaluated_get(dg)
 points=[ev.matrix_world@v.co for v in ev.data.vertices]
 hair_top=max(p.z for p in points)
 for part,target,scale in [('head',(0,.01,shoulder+.15),.60),('torso',(0,0,shoulder-.13),.85),('body',(0,0,shoulder*.53),1.95),('shoes',(0,-.06,.12),.95),('watch',tuple(rig.data.bones['lowerarm02.L'].tail_local),.23)]:
  if os.environ.get('STUDY_PARTS') and part not in os.environ['STUDY_PARTS'].split(','):continue
  for view,yaw in [('front',0),('threeq',35),('side',90),('back',180)]:
   scene.camera=camera(scene,part+view,target,yaw,ortho=scale)
   scene.render.filepath=str(OUT/f'{model}_{part}_{view}.png')
   bpy.ops.render.render(write_still=True)
 macro=[k.name for k in body.data.shape_keys.key_blocks if k.value>.01]
 checks.append({'model':model,'active_targets':macro,'hair_style':hair[0]['hair_style'],'hair_top':hair_top, 'macro': TargetService.get_macro_info_dict_from_basemesh(body)})
if (OUT/'model_checks.json').exists():
 old=json.loads((OUT/'model_checks.json').read_text())
 checks=[q for q in old if q['model'] not in models]+checks
(OUT/'model_checks.json').write_text(json.dumps(checks,indent=2)+'\n')
