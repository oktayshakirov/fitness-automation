"""Render one still for every procedural asset, plus machine contact metadata.
BLENDER_USER_RESOURCES=$PWD/.blender-profile Blender -b --python equipment/preview.py
"""
import sys,os,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import bpy
from mathutils import Vector
import equipment as eq
from core.render import new_scene
from core.studio import studio,camera
from equipment.machines import DEFAULTS
out=ROOT/'review/equipment';out.mkdir(parents=True,exist_ok=True)
items=[('barbell',lambda:eq.barbell()),('ez_bar',lambda:eq.ez_bar()),('kettlebell',lambda:eq.kettlebell()),
 ('bench',lambda:eq.bench()),('incline_bench',lambda:eq.bench(incline=45)),('decline_bench',lambda:eq.bench(incline=-15)),
 ('rack',lambda:eq.power_rack()),('pullup',lambda:eq.pullup_bar()),('dip',lambda:eq.dip_station()),('mat',lambda:eq.exercise_mat()),
 ('box',lambda:eq.box()),('rope',lambda:eq.rope()),('d_handle',lambda:eq.d_handle()),('v_bar',lambda:eq.v_bar()),('lat_bar',lambda:eq.lat_bar()),('ankle_strap',lambda:eq.ankle_strap()),
 ('band',lambda:eq.ResistanceBand(a=(-.3,0,.1),b=(.3,0,1.1)))]
for mode in ('high','mid','low'):
 def tower(mode=mode):
  o=eq.CableTower(pulley=mode); h=Vector((0,.1,.8));o.calibrate(h);o.update(h,1);return o
 items.append(('cable_'+mode,tower))
def dual():
 o=eq.DualCable();o.calibrate((-.5,0,1),(.5,0,1));o.update((-.5,0,1),(.5,0,1),1);return o
items.append(('dual_cable',dual))
for kind in DEFAULTS: items.append((kind,lambda kind=kind:eq.Machine(kind)))
contacts={}
for name,maker in items:
 scene=new_scene();obj=maker();bpy.context.view_layer.update()
 if hasattr(obj,'contacts'):contacts[name]=obj.contacts
 if hasattr(obj,'get') and obj.get('contacts_json'):contacts[name]=json.loads(obj['contacts_json'])
 # Bounds before studio floor/lights, using evaluated geometry including curves.
 dg=bpy.context.evaluated_depsgraph_get();pts=[]
 for o in scene.objects:
  if o.type not in ('MESH','CURVE'): continue
  e=o.evaluated_get(dg)
  mesh=e.to_mesh()
  pts.extend(e.matrix_world@v.co for v in mesh.vertices)
  e.to_mesh_clear()
 lo=Vector(tuple(min(p[i] for p in pts) for i in range(3)));hi=Vector(tuple(max(p[i] for p in pts) for i in range(3)))
 studio(scene,floor=False);scene.camera=camera(scene,'threeq',(lo+hi)/2,35,ortho=max((hi-lo).length*1.16,.5),height=(lo.z+hi.z)/2+.5)
 scene.render.resolution_x=480;scene.render.resolution_y=480;scene.render.resolution_percentage=100
 scene.render.image_settings.file_format='PNG';scene.render.filepath=str(out/(name+'.png'))
 bpy.ops.render.render(write_still=True)
 print('PREVIEW',name,flush=True)
(ROOT/'equipment/contacts.json').write_text(json.dumps(contacts,indent=2)+'\n')
