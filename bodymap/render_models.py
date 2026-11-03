"""Per-model body views for the app's home screen (MVP item 4), in the approved look.

  BLENDER_USER_RESOURCES="$PWD/.blender-profile" Blender -b --python bodymap/render_models.py -- male|female

Writes bodymap/<model>/ with one camera per view (front, back):
  body_<view>.webp          transparent, 3D-shaded body as delivered (hair, shorts, top)
  mask_<view>_<muscle>.png  white + alpha, the baked UV mask as seen through that camera
  hits_<view>.svg           tap regions: strongest mask above 0.3 wins, traced (trace.py)
  bodymap.json              framing, sizes and per-view pixel coverage
Muscle names are the app's ids (abs, lower_back, ...). Garments carry the body UVs, so a
covered muscle's mask shows on the fabric. Outputs are CC BY-SA 4.0 derivatives (LICENSE.md).
"""
import bpy,sys,json,html,shutil
import numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'bodymap'))
from core.render import new_scene
from core.body import make_human
from core.clothes import add_clothing
from core.hair import add_hair
from core.look import muscle_material,load_masks,GROUPS
from core.studio import studio,camera
from importlib import util
spec=util.spec_from_file_location('bodymap_trace',ROOT/'bodymap/trace.py');trace=util.module_from_spec(spec);spec.loader.exec_module(trace)

model=sys.argv[sys.argv.index('--')+1]
assert model in ('male','female')
W,H=800,1000;TARGET=(0,0,.86);ORTHO=1.95   # the v0.1.0 selector framing at ~1000 px
APP={'abdominals':'abs'}
app_id=lambda g:APP.get(g,g.replace(' ','_'))
out=ROOT/'bodymap'/model;work=ROOT/'review/bodymap'/model
for d in (out,work):shutil.rmtree(d,ignore_errors=True);d.mkdir(parents=True)

scene=new_scene()
body,rig=make_human(gender=1.0 if model=='male' else 0.0)
body['fitness_body']=True;scene['fitness_model']=model
body.data.materials.clear();body.data.materials.append(muscle_material())
garments=add_clothing(body,rig,model)
add_hair(body,rig,model)
studio(scene,floor=False,transparent=True)
r=scene.render;r.resolution_x=W;r.resolution_y=H;r.resolution_percentage=100

def emission(name,image=None):
    m=bpy.data.materials.new(name);m.use_nodes=True;nt=m.node_tree;nt.nodes.clear()
    e=nt.nodes.new('ShaderNodeEmission');o=nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(e.outputs[0],o.inputs['Surface'])
    if image is None:e.inputs['Color'].default_value=(0,0,0,1)
    else:
        t=nt.nodes.new('ShaderNodeTexImage');t.image=image;nt.links.new(t.outputs['Color'],e.inputs['Color'])
    return m

meshes=[o for o in scene.objects if o.type=='MESH']
carriers={body.name,*(g.name for g in garments)}
looks={o.name:[s.material for s in o.material_slots] for o in meshes}
def dress(pick):
    for o in meshes:
        for i,s in enumerate(o.material_slots):s.material=pick(o,i)
def pixels(path):
    img=bpy.data.images.load(str(path));img.colorspace_settings.name='Non-Color'
    img.alpha_mode='CHANNEL_PACKED'   # read colour and alpha as stored, not premultiplied
    a=np.array(img.pixels[:],dtype=np.float32).reshape(H,W,4)[::-1];bpy.data.images.remove(img);return a
def save_mask(path,alpha):
    img=bpy.data.images.new(path.stem,W,H,alpha=True,float_buffer=False)
    px=np.ones((H,W,4),np.float32);px[...,3]=alpha;img.pixels[:]=px[::-1].ravel()
    img.alpha_mode='STRAIGHT';img.filepath_raw=str(path);img.file_format='PNG';img.save();bpy.data.images.remove(img)

black=emission('mask_off');masks=[emission(f'mask_{i}',img) for i,img in enumerate(load_masks())]
meta={'model':model,'width':W,'height':H,'camera':{'target':TARGET,'ortho_scale':ORTHO,'projection':'orthographic'},
      'threshold':.3,'views':{}}
for view,yaw in (('front',0),('back',180)):
    scene.camera=camera(scene,view,TARGET,yaw,ortho=ORTHO)
    dress(lambda o,i:looks[o.name][i])
    scene.view_settings.view_transform='Standard'
    r.image_settings.file_format='WEBP';r.image_settings.color_mode='RGBA';r.image_settings.quality=90
    r.filepath=str(out/f'body_{view}.webp');bpy.ops.render.render(write_still=True)
    # Raw: mask values reach the file linear, without a display transform.
    scene.view_settings.view_transform='Raw'
    r.image_settings.file_format='PNG';r.image_settings.color_depth='16'
    stack=[]
    for i,m in enumerate(masks):
        dress(lambda o,j:m if o.name in carriers else black)
        r.filepath=str(work/f'{view}_ids_{i}.png');bpy.ops.render.render(write_still=True)
        px=pixels(work/f'{view}_ids_{i}.png');stack+=[px[...,c]*px[...,3] for c in range(3)]
    stack=np.clip(np.array(stack[:len(GROUPS)]),0,1)
    best=stack.argmax(0);valid=stack.max(0)>meta['threshold']
    paths=[];coverage={}
    for k,g in enumerate(GROUPS):
        name=app_id(g);region=(best==k)&valid;coverage[name]=int(region.sum())
        if stack[k].max()>0:save_mask(out/f'mask_{view}_{name}.png',stack[k])
        rings=trace.loops(region)
        if not rings:continue
        d=' '.join('M'+' L'.join(f'{x},{y}' for x,y in ring)+' Z' for ring in rings)
        paths.append(f'<path id="{name}" data-muscle="{name}" role="button" tabindex="0" aria-label="{html.escape(g)}" d="{d}"/>')
    (out/f'hits_{view}.svg').write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">\n'
        f'<title>{model} {view} muscle selector</title>\n'
        '<metadata>Traced from MPFB skin UV masks derived from Z-Anatomy / BodyParts3D. CC BY-SA 4.0. See LICENSE.md.</metadata>\n'
        '<g fill="#df463c" fill-opacity="0.10" stroke="#df463c" stroke-opacity="0.25" stroke-width="0.65" fill-rule="evenodd">\n'
        +'\n'.join(paths)+'\n</g>\n</svg>\n')
    meta['views'][view]={'yaw_deg':yaw,'coverage_px':coverage}
missing=[n for n in map(app_id,GROUPS) if sum(v['coverage_px'][n] for v in meta['views'].values())<12]
if missing:raise ValueError('No tappable surface for '+str(missing))
shutil.copy2(ROOT/'bodymap/LICENSE.md',out/'LICENSE.md')
(out/'bodymap.json').write_text(json.dumps(meta,indent=1)+'\n')
shutil.rmtree(work)
print('BODYMAP',model,'ok',out)
