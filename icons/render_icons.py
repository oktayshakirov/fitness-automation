"""Equipment icons for the Exercises chips (MVP item 6), rendered from our procedural
equipment in one style.

  BLENDER_USER_RESOURCES="$PWD/.blender-profile" Blender -b --python icons/render_icons.py

Writes icons/set/<category>.webp (256x256, transparent) and icons/set/icons.json: the eight
categories and which catalog equipment ids each one stands for (the chip filter). One matte
light-grey material, the same three-quarter camera, the same light and margin for every
icon, so they read as a set on dark chips. All geometry is procedural (equipment/).
"""
import bpy,sys,json,math,shutil
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import equipment as eq
from equipment.basic import cyl_x,empty
from equipment.library import cube,tube
from core.render import new_scene

SIZE=256;YAW=35;ELEV=24;MARGIN=1.14;STROKE=.012   # thin tubes are thickened to this radius
GREY=(0.62,0.63,0.66)          # linear; ~#CFD0D4 on screen
CATEGORIES={   # catalog equipment id -> chip category
 'barbell':['barbell','power_rack'],
 'dumbbell':['dumbbell'],
 'kettlebell':['kettlebell'],
 'cable':['cable_tower','dual_cable','rope','d_handle','v_bar','lat_bar','straight_bar'],
 'machine':['seated_row','lat_pulldown','leg_curl','leg_extension','leg_press'],
 'bench':['bench'],
 'bodyweight':['mat','pullup_bar','dip_station'],
 'band':['band'],
}

def cable():
    r=empty('cable');eq.d_handle().parent=r
    pulley=empty('pulley',(0,.09,.30));pulley.parent=r;pulley.rotation_euler.z=math.radians(-55)   # wheel faces the camera
    cyl_x('pulley_wheel','dark',.09,.04,parent=pulley)
    tube('bracket',[(-.035,0,0),(-.035,0,.13),(.035,0,.13),(.035,0,0)],.008,'frame',pulley)
    tube('cable',[(0,0,.30),(0,0,0)],.004,'cable',r)
    return r

def bodyweight():
    r=empty('mat');cube('mat_flat',(0,-.20,.006),(.60,.70,.012),'rubber',r,bevel=.005)
    roll=cyl_x('mat_roll','rubber',.075,.60,parent=r);roll.location=(0,.22,.075)
    return r

def band():
    r=empty('band')
    pts=[(-.20,0,.62),(-.21,0,.40),(-.14,0,.16),(0,0,.04),(.14,0,.16),(.21,0,.40),(.20,0,.62)]
    tube('band_tube',pts,.020,'rubber',r)
    for s in (-1,1):
        tube('band_strap',[(s*.20,0,.62),(s*.20-.05,0,.68),(s*.20+.05,0,.68),(s*.20,0,.62)],.010,'rubber',r)
        h=cyl_x('band_handle','rubber',.024,.14,parent=r);h.location=(s*.20,0,.69)
    return r

def barbell():
    r=eq.barbell(plates=[25,25]);r.rotation_euler.z=math.radians(-25)   # bar toward the camera, plates read large
    return r

ITEMS={
 'barbell':barbell,
 'dumbbell':lambda:eq.dumbbell(),
 'kettlebell':lambda:eq.kettlebell(),
 'cable':cable,
 'machine':lambda:eq.Machine('leg_extension').root,
 'bench':lambda:eq.bench(),
 'bodyweight':bodyweight,
 'band':band,
}

out=ROOT/'icons/set';shutil.rmtree(out,ignore_errors=True);out.mkdir(parents=True)
for name,make in ITEMS.items():
    scene=new_scene();make();bpy.context.view_layer.update()
    m=bpy.data.materials.new('icon');m.use_nodes=True;b=m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value=(*GREY,1);b.inputs['Roughness'].default_value=.55;b.inputs['Metallic'].default_value=0
    for o in scene.objects:
        if o.type in ('MESH','CURVE'):
            o.data.materials.clear();o.data.materials.append(m)
        if o.type=='CURVE':o.data.bevel_depth=max(o.data.bevel_depth,STROKE)
    scene.render.engine='BLENDER_EEVEE';scene.render.film_transparent=True
    scene.view_settings.view_transform='Standard';scene.eevee.taa_render_samples=32
    w=bpy.data.worlds.new('W');scene.world=w;w.use_nodes=True
    w.node_tree.nodes['Background'].inputs[0].default_value=(.20,.20,.22,1)   # soft ambient, never seen (transparent)
    for lname,energy,rot in (('key',3.0,(40,0,-35)),('fill',1.0,(70,0,150)),('rim',1.5,(-60,0,25))):
        L=bpy.data.objects.new(lname,bpy.data.lights.new(lname,'SUN'));L.data.energy=energy
        L.rotation_euler=tuple(math.radians(a) for a in rot);scene.collection.objects.link(L)
    r=scene.render;r.resolution_x=r.resolution_y=SIZE;r.resolution_percentage=100
    r.image_settings.file_format='WEBP';r.image_settings.color_mode='RGBA';r.image_settings.quality=95
    cam=bpy.data.objects.new('cam',bpy.data.cameras.new('cam'));scene.collection.objects.link(cam);scene.camera=cam
    cam.data.type='ORTHO';y,e=math.radians(YAW),math.radians(ELEV)
    cam.location=Vector((math.sin(y)*math.cos(e),-math.cos(y)*math.cos(e),math.sin(e)))*6
    cam.rotation_euler=(-cam.location).to_track_quat('-Z','Y').to_euler()
    bpy.context.view_layer.update();inv=cam.matrix_world.inverted();dg=bpy.context.evaluated_depsgraph_get();pts=[]
    for o in scene.objects:
        if o.type not in ('MESH','CURVE'):continue
        ev=o.evaluated_get(dg);me=ev.to_mesh();pts+=[inv@(ev.matrix_world@v.co) for v in me.vertices];ev.to_mesh_clear()
    xs=[p.x for p in pts];ys=[p.y for p in pts]
    cam.location+=cam.matrix_world.to_3x3()@Vector(((min(xs)+max(xs))/2,(min(ys)+max(ys))/2,0))
    cam.data.ortho_scale=max(max(xs)-min(xs),max(ys)-min(ys))*MARGIN
    r.filepath=str(out/f'{name}.webp');bpy.ops.render.render(write_still=True)
(out/'icons.json').write_text(json.dumps({'size':SIZE,'background':'transparent',
    'camera':{'yaw_deg':YAW,'elevation_deg':ELEV,'projection':'orthographic'},'categories':CATEGORIES},indent=1)+'\n')
print('ICONS ok',len(ITEMS))
