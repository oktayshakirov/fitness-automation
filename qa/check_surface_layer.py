"""Render a synthetic muscle boundary: active neighbours must not expose grey skin.
Run with Blender --background --python-exit-code 1 --python qa/check_surface_layer.py.
"""
import bpy, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core import look
from core.render import new_scene
from core.studio import camera
new_scene();scene=bpy.context.scene
scene.render.engine='CYCLES';scene.cycles.samples=1;scene.cycles.device='CPU'
scene.render.resolution_x=96;scene.render.resolution_y=32;scene.render.resolution_percentage=100
scene.view_settings.view_transform='Standard';scene.render.image_settings.file_format='OPEN_EXR'
images=[]
for pack in range(6):
 im=bpy.data.images.new('mask_fixture_'+str(pack),64,4,alpha=False,float_buffer=True)
 im.colorspace_settings.name='Non-Color';pixels=[]
 for y in range(4):
  for x in range(64):
   t=x/63;pixels.extend((t,1-t,0,1) if pack==0 else (0,0,0,1))
 im.pixels[:]=pixels;images.append(im)
look.load_masks=lambda:images
bpy.ops.mesh.primitive_plane_add(size=2,rotation=(1.57079632679,0,0))
plane=bpy.context.object;plane.scale.x=3
scene.camera=camera(scene,'check',(0,0,0),0,ortho=6)
for mode,primary,secondary in [('same',['quadriceps','hamstrings'],[]),('mixed',['quadriceps'],['hamstrings'])]:
 mat=look.muscle_material(primary,secondary,use_normal=False)
 nt=mat.node_tree;bsdf=nt.nodes['Principled BSDF'];source=bsdf.inputs['Base Color'].links[0].from_socket
 emission=nt.nodes.new('ShaderNodeEmission');nt.links.new(source,emission.inputs[0]);nt.links.new(emission.outputs[0],nt.nodes['Material Output'].inputs['Surface'])
 plane.data.materials.clear();plane.data.materials.append(mat)
 path='/tmp/muscle_boundary_'+mode+'.exr';scene.render.filepath=path;bpy.ops.render.render(write_still=True)
 result=bpy.data.images.load(path);pixels=list(result.pixels)
 sample=[pixels[4*(16*96+x):4*(16*96+x)+3] for x in range(12,84)]
 hot=(.72,.025,.018);warm=(.95,.26,.025)
 if mode=='same':
  assert max(abs(c[k]-hot[k]) for c in sample for k in range(3))<.005,'Grey gap at a shared active boundary'
 else:
  assert all(min(hot[k],warm[k])-.005<=c[k]<=max(hot[k],warm[k])+.005 for c in sample for k in range(3)),'Mixed boundary contains base-grey contamination'
 print('PASS rendered muscle boundary:',mode)

# The two copies of a UV seam must sample the same scalar surface height.
import numpy as np
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'review/muscle_fit.blend'))
body=next(o for o in bpy.context.scene.objects if o.type=='MESH' and o.find_armature())
mask=next(m for m in body.modifiers if m.type=='MASK');group=body.vertex_groups[mask.vertex_group].index
skin={v.index for v in body.data.vertices if any(g.group==group and g.weight>.5 for g in v.groups)}
height=bpy.data.images.load(str(ROOT/'assets/maps/surface_detail_height.png'),check_existing=False)
height.colorspace_settings.name='Non-Color'
w,h=height.size;pixels=np.empty(w*h*4,np.float32);height.pixels.foreach_get(pixels);pixels=pixels.reshape(h,w,4)[:,:,0]
assert np.isfinite(pixels).all() and pixels.min()>=0 and pixels.max()<=1
samples={}
for loop in body.data.loops:
 if loop.vertex_index not in skin:continue
 uv=body.data.uv_layers.active.data[loop.index].uv
 x=min(w-1,max(0,float(uv.x)*w-.5));y=min(h-1,max(0,float(uv.y)*h-.5))
 xi,yi=int(x),int(y);xf,yf=x-xi,y-yi
 value=(pixels[yi,xi]*(1-xf)+pixels[yi,min(w-1,xi+1)]*xf)*(1-yf)+(pixels[min(h-1,yi+1),xi]*(1-xf)+pixels[min(h-1,yi+1),min(w-1,xi+1)]*xf)*yf
 samples.setdefault(loop.vertex_index,{})[(round(float(uv.x),5),round(float(uv.y),5))]=float(value)
seams=[max(v.values())-min(v.values()) for v in samples.values() if len(v)>1]
assert seams and max(seams)<.08, f'Visible height discontinuity at a UV seam: {max(seams)}'
print('PASS scalar UV seams:',len(seams),'max height delta',round(max(seams),6))
