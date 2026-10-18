"""Compare the saved delivery look with the current material on identical poses.
Blender -b --python core/preview_surface.py (writes review/surface_revision/).
"""
import bpy, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.look import muscle_material
out=ROOT/'review/surface_revision';out.mkdir(exist_ok=True)
cases=[('push_up',32,'threeq'),('dumbbell_shoulder_press',32,'threeq'),
       ('leg_extension',32,'threeq'),('one_arm_dumbbell_row',30,'back')]
for eid,frame,view in cases:
 bpy.ops.wm.open_mainfile(filepath=str(ROOT/'review'/(eid+'.blend')))
 scene=bpy.context.scene;scene.frame_set(frame);scene.camera=bpy.data.objects[view]
 scene.render.resolution_x=720;scene.render.resolution_y=900;scene.render.resolution_percentage=100
 scene.render.image_settings.file_format='PNG'
 body=next(o for o in scene.objects if o.type=='MESH' and o.find_armature())
 cat=json.loads((ROOT/'catalog'/(eid+'.json')).read_text())
 for variant in ['before','after']:
  if variant=='after':
   body.data.materials.clear();body.data.materials.append(muscle_material(cat['primary'],cat['secondary']))
  scene.render.filepath=str(out/(eid+'_'+variant+'.png'));bpy.ops.render.render(write_still=True)
 print('COMPARED',eid,flush=True)
# Neutral rest surface: material-only comparison makes relief easy to inspect.
from core.render import new_scene
from core.body import make_human
from core.studio import studio,camera
scene=new_scene();body,rig=make_human();studio(scene,floor=False)
scene.render.resolution_x=720;scene.render.resolution_y=900
for view,yaw in [('front',0),('back',180)]:
 scene.camera=camera(scene,view,(0,0,1.17),yaw,ortho=1.2)
 for detail in [False,True]:
  body.data.materials.clear();body.data.materials.append(muscle_material(use_normal=detail))
  scene.render.filepath=str(out/(view+('_relief' if detail else '_plain')+'.png'));bpy.ops.render.render(write_still=True)

html = ["<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>Muscle surface comparison</title><style>body{font:16px system-ui;background:#f5f7fa;color:#172435;margin:24px auto;max-width:1100px;padding:0 20px}section{margin:30px 0}div{display:grid;grid-template-columns:1fr 1fr;gap:16px}figure{margin:0}img{width:100%;background:white;border-radius:12px}figcaption{padding:8px}a{color:#145ba8}</style><h1>Muscle surface comparison</h1><p>Same pose, camera and lighting. Left: previous material. Right: repaired highlight blending and continuous muscle relief.</p><a href='../index.html'>Exercise review</a>"]
for eid,frame,view in cases:
 html.append(f"<section><h2>{eid.replace('_',' ').title()}</h2><div><figure><img src='{eid}_before.png'><figcaption>Before</figcaption></figure><figure><img src='{eid}_after.png'><figcaption>After</figcaption></figure></div></section>")
for view in ('front','back'):
 html.append(f"<section><h2>{view.title()} surface detail</h2><div><figure><img src='{view}_plain.png'><figcaption>Plain surface</figcaption></figure><figure><img src='{view}_relief.png'><figcaption>New relief</figcaption></figure></div></section>")
(out/'index.html').write_text(''.join(html)+'</html>')
