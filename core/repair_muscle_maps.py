"""Project fitted anatomy onto skin by nearest surface, avoiding bone ray occlusion.
Run Blender -b review/muscle_fit.blend --python core/repair_muscle_maps.py.
Original ray bakes are preserved; repaired masks retain the source CC BY-SA licence.
"""
import bpy, sys, json
from pathlib import Path
from collections import Counter
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.look import GROUPS
scene=bpy.context.scene
body=next(o for o in scene.objects if o.type=='MESH' and o.find_armature())
rig=body.find_armature()
for pb in rig.pose.bones:pb.matrix_basis.identity()
bpy.context.view_layer.update()
trees=[]
for g in GROUPS:
 o=bpy.data.objects['ZA_'+g]
 trees.append(BVHTree.FromPolygons([o.matrix_world@v.co for v in o.data.vertices],[list(p.vertices) for p in o.data.polygons]))
# Evaluate shape keys with unchanged vertex order. Helpers are excluded by the body mask.
mask=next(m for m in body.modifiers if m.type=='MASK');mask.show_viewport=False
vg=body.vertex_groups[mask.vertex_group].index
skin={v.index for v in body.data.vertices if any(g.group==vg and g.weight>.5 for g in v.groups)}
dg=bpy.context.evaluated_depsgraph_get();ev=body.evaluated_get(dg);me=ev.to_mesh()
points=[body.matrix_world@v.co for v in me.vertices];ev.to_mesh_clear();mask.show_viewport=True
labels={};distances={}
for i in skin:
 p=points[i]
 # Leave face, fingers and feet neutral; these are not muscle selection surfaces.
 if p.z>1.52 or p.z<.13:continue
 side='L' if p.x>0 else 'R'
 wrist=rig.data.bones['wrist.'+side].head_local
 elbow=rig.data.bones['lowerarm01.'+side].head_local
 if abs(p.x)>.37 and (p-wrist).dot(wrist-elbow)>0:continue
 candidates=[]
 for k,tree in enumerate(trees):
  g=GROUPS[k]
  if g=='lower back' and p.z>1.20:continue
  if g=='forearms' and (p-elbow).dot(wrist-elbow)<0:continue
  loc,normal,face,d=tree.find_nearest(p)
  if d is not None:candidates.append((d,k))
 d,k=min(candidates)
 if GROUPS[k]=='calves':
  knee=rig.data.bones['lowerleg01.'+side].head_local
  ankle=rig.data.bones['foot.'+side].head_local
  t=max(0.,min(1.,(p.z-ankle.z)/(knee.z-ankle.z)))
  if p.y<ankle.y+(knee.y-ankle.y)*t:continue
 if d<.075:labels[i]=k;distances[i]=d
# Remove isolated assignments on the connected skin, without spreading across UV seams.
adj={i:set() for i in skin}
for e in body.data.edges:
 a,b=e.vertices
 if a in skin and b in skin:adj[a].add(b);adj[b].add(a)
for _ in range(2):
 out=dict(labels)
 for i,k in labels.items():
  counts=Counter(labels[n] for n in adj[i] if n in labels)
  if counts:
   win,num=counts.most_common(1)[0]
   if num>=3 and num>counts[k]+1:out[i]=win
 labels=out
# Smooth labels on the surface graph, not across unrelated UV islands.
weights={i:[float(labels.get(i)==k) for k in range(len(GROUPS))] for i in skin}
for _ in range(5):
 weights={i:[.5*w[k]+.5*sum(weights[n][k] for n in adj[i])/max(1,len(adj[i])) for k in range(len(GROUPS))] for i,w in weights.items()}
for o in scene.objects:
 if o!=body:o.hide_render=True;o.select_set(False)
body.hide_render=False;body.hide_set(False);body.select_set(True);bpy.context.view_layer.objects.active=body
m=bpy.data.materials.new('repaired_anatomy');m.use_nodes=True;nt=m.node_tree;nt.nodes.clear()
attr=body.data.color_attributes.new(name='anatomy_projection',type='FLOAT_COLOR',domain='CORNER')
a=nt.nodes.new('ShaderNodeVertexColor');a.layer_name=attr.name
e=nt.nodes.new('ShaderNodeEmission');nt.links.new(a.outputs['Color'],e.inputs[0]);o=nt.nodes.new('ShaderNodeOutputMaterial');nt.links.new(e.outputs[0],o.inputs[0])
t=nt.nodes.new('ShaderNodeTexImage');nt.nodes.active=t;t.select=True
body.data.materials.clear();body.data.materials.append(m)
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=1;scene.render.use_freestyle=False;scene.use_nodes=False
scene.render.bake.use_selected_to_active=False;scene.render.bake.margin=12
out=ROOT/'assets/maps/repaired';out.mkdir(exist_ok=True)
for pack in range(6):
 for loop in body.data.loops:
  w=weights.get(loop.vertex_index,[0.]*len(GROUPS));rgb=[w[k] if k<len(GROUPS) else 0. for k in range(pack*3,pack*3+3)]+[1.]
  attr.data[loop.index].color=rgb
 img=bpy.data.images.new('repaired_'+str(pack),2048,2048,alpha=False);img.colorspace_settings.name='Non-Color';t.image=img
 bpy.ops.object.bake(type='EMIT');img.filepath_raw=str(out/f'mask_{pack}.png');img.file_format='PNG';img.save()
 print('REPAIRED',pack,flush=True)
(out/'coverage.json').write_text(json.dumps({g:sum(k==j for k in labels.values()) for j,g in enumerate(GROUPS)},indent=2)+'\n')
