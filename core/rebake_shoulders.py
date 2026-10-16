"""Rebake deltoids with a cage that encloses the fitted outer shoulder.
Run Blender -b review/muscle_fit.blend --python core/rebake_shoulders.py.
Only the shoulder channel is replaced; other anatomy masks remain unchanged.
"""
import bpy,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=1
scene.use_nodes=False;scene.render.use_freestyle=False
body=next(o for o in scene.objects if o.type=='MESH' and o.find_armature())
sources=[o for o in scene.objects if o.name.startswith('ZA_') and o.type=='MESH']
assert any(o.name=='ZA_shoulders' for o in sources),'Generate review/muscle_fit.blend first'
# The source deltoids end only ~12 cm along this 25 cm upper arm. Extend the
# fitted distal portion to ~16 cm to meet the muscular MPFB deltoid insertion.
# The medial supraspinatus portion (t <= 0) is left unchanged.
from mathutils import Vector
rig=body.find_armature();shoulder_mesh=bpy.data.objects['ZA_shoulders']
for v in shoulder_mesh.data.vertices:
 w=shoulder_mesh.matrix_world@v.co; side='L' if w.x>0 else 'R'
 origin=rig.matrix_world@rig.data.bones['upperarm01.'+side].head_local
 elbow=rig.matrix_world@rig.data.bones['lowerarm01.'+side].head_local
 axis=(elbow-origin).normalized();delta=w-origin;t=delta.dot(axis)
 if t>0:
  w=origin+axis*t*1.35+(delta-axis*t)*1.10
  v.co=shoulder_mesh.matrix_world.inverted()@w
bpy.context.view_layer.update()
for o in sources:
 m=bpy.data.materials.new(o.name+'_id');m.use_nodes=True;nt=m.node_tree;nt.nodes.clear()
 e=nt.nodes.new('ShaderNodeEmission');e.inputs[0].default_value=(1,1,1,1) if o.name=='ZA_shoulders' else (0,0,0,1)
 out=nt.nodes.new('ShaderNodeOutputMaterial');nt.links.new(e.outputs[0],out.inputs[0]);o.data.materials.clear();o.data.materials.append(m)
 o.hide_render=False;o.hide_set(False)
m=bpy.data.materials.new('target');m.use_nodes=True;body.data.materials.clear();body.data.materials.append(m)
img=bpy.data.images.new('shoulder_projection',2048,2048,alpha=False);img.colorspace_settings.name='Non-Color'
t=m.node_tree.nodes.new('ShaderNodeTexImage');t.image=img;m.node_tree.nodes.active=t;t.select=True
bpy.ops.object.select_all(action='DESELECT')
for o in sources:o.select_set(True)
body.hide_set(False);body.select_set(True);bpy.context.view_layer.objects.active=body
bk=scene.render.bake;bk.use_selected_to_active=True;bk.cage_extrusion=.12;bk.max_ray_distance=.25;bk.margin=12
bpy.ops.object.bake(type='EMIT');img.filepath_raw=str(ROOT/'review/shoulder_projection.png');img.file_format='PNG';img.save()
