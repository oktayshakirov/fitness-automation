"""Render front/back underlays plus 17-colour ID pass from baked UV muscle masks."""
import bpy,sys,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.render import new_scene
from core.body import make_human
from core.look import muscle_material,load_masks,GROUPS
from core.studio import studio,camera
scene=new_scene();body,rig=make_human();studio(scene,floor=False)
scene.render.resolution_x=720;scene.render.resolution_y=900;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA'
scene.render.film_transparent=True
scene.view_settings.view_transform='Standard';scene.view_settings.look='None'
base=muscle_material(name='neutral_bodymap')
palette=[(220,45,55),(245,125,35),(238,190,35),(155,195,40),(35,170,70),(40,195,150),(35,150,215),(70,90,230),(125,65,200),(190,65,180),(230,90,130),(70,200,210),(125,95,50),(110,160,105),(190,130,220),(70,120,145),(180,75,70)]
def linear(v):
 v=v/255;return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4
m=bpy.data.materials.new('muscle_ID');m.use_nodes=True;nt=m.node_tree;nt.nodes.clear()
imgs=load_masks();channels=[]
for img in imgs:
 t=nt.nodes.new('ShaderNodeTexImage');t.image=img
 sp=nt.nodes.new('ShaderNodeSeparateColor');nt.links.new(t.outputs['Color'],sp.inputs['Color']);channels.extend(sp.outputs[:3])
rgb=nt.nodes.new('ShaderNodeRGB');rgb.outputs[0].default_value=(.21,.21,.21,1);color=rgb.outputs[0]
maximum=None
for i,g in enumerate(GROUPS):
 ch=channels[i];gate=nt.nodes.new('ShaderNodeMath');gate.operation='GREATER_THAN';nt.links.new(ch,gate.inputs[0]);gate.inputs[1].default_value=.3
 if maximum is not None:
  win=nt.nodes.new('ShaderNodeMath');win.operation='GREATER_THAN';nt.links.new(ch,win.inputs[0]);nt.links.new(maximum,win.inputs[1])
  both=nt.nodes.new('ShaderNodeMath');both.operation='MULTIPLY';nt.links.new(win.outputs[0],both.inputs[0]);nt.links.new(gate.outputs[0],both.inputs[1]);factor=both.outputs[0]
  mx=nt.nodes.new('ShaderNodeMath');mx.operation='MAXIMUM';nt.links.new(ch,mx.inputs[0]);nt.links.new(maximum,mx.inputs[1]);maximum=mx.outputs[0]
 else:factor=gate.outputs[0];maximum=ch
 mix=nt.nodes.new('ShaderNodeMixRGB');mix.blend_type='MIX';nt.links.new(factor,mix.inputs[0]);nt.links.new(color,mix.inputs[1]);mix.inputs[2].default_value=(*map(linear,palette[i]),1);color=mix.outputs[0]
e=nt.nodes.new('ShaderNodeEmission');nt.links.new(color,e.inputs[0]);o=nt.nodes.new('ShaderNodeOutputMaterial');nt.links.new(e.outputs[0],o.inputs[0])
for view,yaw in [('front',0),('back',180)]:
 scene.camera=camera(scene,view,(0,0,.86),yaw,ortho=1.95)
 for label,material in [('',base),('_ids',m)]:
  body.data.materials.clear();body.data.materials.append(material)
  scene.render.filepath=str(ROOT/'bodymap'/(view+label+'.png'));bpy.ops.render.render(write_still=True)
(ROOT/'bodymap/palette.json').write_text(json.dumps(dict(zip(GROUPS,palette)),indent=2)+'\n')
