"""Unapproved fabric-layer study from the current female squat preview."""
import bpy, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.clothes import fabric_material, _hide_covered_skin
from core.look import muscle_material
from core.studio import camera
OUT=ROOT/'review/look_v5';OUT.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'review/bodyweight_squat_female.blend'))
scene=bpy.context.scene;scene.frame_set(1)
body=next(o for o in scene.objects if o.get('fitness_body'))
rig=next(o for o in scene.objects if o.type=='ARMATURE')
scene.camera=camera(scene,'Fabric study',(0,-.03,rig.pose.bones['upperarm01.L'].head.z-.11),35,ortho=.65)
scene.render.resolution_x=600;scene.render.resolution_y=750
for active in (False,True):
 primary=('chest',) if active else ()
 body.data.materials.clear();body.data.materials.append(muscle_material(primary=primary))
 attr=body.data.attributes.get('clothing_covered')
 if attr:body.data.attributes.remove(attr)
 _hide_covered_skin(body,rig.data.bones['upperleg01.L'].head_local.z,
                    rig.data.bones['lowerleg01.L'].head_local.z,
                    rig.data.bones['upperarm01.L'].head_local.z,'female')
 material=fabric_material(primary=primary)
 for obj in scene.objects:
  if obj.get('garment'):
   obj.data.materials.clear();obj.data.materials.append(material)
 scene.render.filepath=str(OUT/('bra_active.png' if active else 'bra_inactive.png'))
 bpy.ops.render.render(write_still=True)
