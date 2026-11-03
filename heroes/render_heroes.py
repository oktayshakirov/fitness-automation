"""Onboarding hero stills (MVP item 5): each model standing relaxed, in the approved look.

  BLENDER_USER_RESOURCES="$PWD/.blender-profile" Blender -b --python heroes/render_heroes.py -- male|female

Writes heroes/<model>/:
  hero.webp    transparent, 800x1200 (2:3, the onboarding card), body fitted with a margin
  hero.json    pose, camera and framing
  LICENSE.md   the body material carries the anatomy relief (CC BY-SA 4.0, as bodymap/)
Pose: the standing base of motion/patterns/arm_isolation.py, arms hanging soft at the
sides, palms in, hands relaxed; the body turned a little to the camera. Light: the exercise
studio's key and fill plus two rim lights from behind, so the silhouette separates from a
dark card.
"""
import bpy,sys,json,shutil,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.render import new_scene
from core.body import make_human,key_pose
from core.clothes import add_clothing
from core.hair import add_hair
from core.look import muscle_material
from core.studio import studio,camera
from core.solver import Poser
from motion.patterns.arm_isolation import Pattern

model=sys.argv[sys.argv.index('--')+1]
assert model in ('male','female')
W,H=800,1200;YAW=22;CAM_Z=.80;MARGIN=1.06
POSE={'joint':'shoulder','plane':10,'elev':[9,9],'elbow':16,'palm':'in','fingers':'relaxed'}
out=ROOT/'heroes'/model
shutil.rmtree(out,ignore_errors=True);out.mkdir(parents=True)

scene=new_scene()
body,rig=make_human(gender=1.0 if model=='male' else 0.0)
body['fitness_body']=True;scene['fitness_model']=model
body.data.materials.clear();body.data.materials.append(muscle_material())
garments=add_clothing(body,rig,model)
add_hair(body,rig,model)
P=Poser(rig);P.reset();Pattern(P,POSE).pose(0.0)
for side in ('L','R'):P.curl_fingers(side,deg=(12,20,14),thumb=(6,10,6))
key_pose(rig,1);scene.frame_set(1)

studio(scene,floor=False,transparent=True)
for name,z in (('rim_L',38),('rim_R',-38)):
    rim=bpy.data.objects.new(name,bpy.data.lights.new(name,'SUN'))
    rim.data.energy=1.6;rim.data.angle=math.radians(8);rim.rotation_euler=(math.radians(-62),0,math.radians(z))
    scene.collection.objects.link(rim)
r=scene.render;r.resolution_x=W;r.resolution_y=H;r.resolution_percentage=100
r.image_settings.file_format='WEBP';r.image_settings.color_mode='RGBA';r.image_settings.quality=92

# fit the evaluated body, clothes and hair into the frame (curves are evaluated as meshes)
cam=camera(scene,'hero',(0,0,.9),YAW,ortho=2.2,height=CAM_Z);scene.camera=cam
bpy.context.view_layer.update();inv=cam.matrix_world.inverted();dg=bpy.context.evaluated_depsgraph_get();pts=[]
for o in scene.objects:
    if o.type not in ('MESH','CURVE') or o.hide_render:continue
    e=o.evaluated_get(dg);m=e.to_mesh();pts+=[inv@(e.matrix_world@v.co) for v in m.vertices];e.to_mesh_clear()
xs=[p.x for p in pts];ys=[p.y for p in pts]
cam.location+=cam.matrix_world.to_3x3()@Vector(((min(xs)+max(xs))/2,(min(ys)+max(ys))/2,0))
cam.data.ortho_scale=max(max(ys)-min(ys),(max(xs)-min(xs))*H/W)*MARGIN
r.filepath=str(out/'hero.webp');bpy.ops.render.render(write_still=True)

shutil.copy2(ROOT/'bodymap/LICENSE.md',out/'LICENSE.md')
(out/'hero.json').write_text(json.dumps({'model':model,'width':W,'height':H,'pose':POSE,
    'camera':{'yaw_deg':YAW,'height':CAM_Z,'ortho_scale':round(cam.data.ortho_scale,4),'projection':'orthographic'},
    'background':'transparent'},indent=1)+'\n')
print('HERO',model,'ok',out)
