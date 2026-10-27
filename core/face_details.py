"""Original simple facial grooming, projected onto the fitted CC0 body."""
import bpy, math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from core.accessories import anchor,material


def strand(name,points,radius,mat,root,taper=True):
    c=bpy.data.curves.new(name,'CURVE');c.dimensions='3D';c.bevel_depth=radius;c.bevel_resolution=2
    s=c.splines.new('POLY');s.points.add(len(points)-1)
    for i,(p,co) in enumerate(zip(s.points,points)):
        p.co=(*co,1);p.radius=(.25+.75*math.sin(math.pi*i/(len(points)-1))**.4) if taper else 1
    o=bpy.data.objects.new(name,c);bpy.context.collection.objects.link(o);o.parent=root;o.matrix_parent_inverse=root.matrix_world.inverted();o.data.materials.append(mat);o['face_detail']=True
    return o


def add_face_details(body,rig,gender):
    bpy.context.view_layer.update();ev=body.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
    tree=BVHTree.FromPolygons([body.matrix_world@v.co for v in mesh.vertices],[list(p.vertices) for p in mesh.polygons]);ev.to_mesh_clear()
    root=anchor(rig,'head','Facial grooming follows head')
    dark=material('Soft black brows and lashes',(.009,.008,.008),.85)
    for side in ('L','R'):
        eye=rig.data.bones['eye.'+side].head_local
        sign=1 if side=='L' else -1
        # Flat tapered brow follows the forehead, rather than a round tube.
        verts=[];faces=[]
        for i in range(33):
            t=i/32;x=eye.x+sign*(t-.5)*.041
            z=eye.z+.018+.004*math.sin(math.pi*t)
            half=(.0032 if gender else .0026)*(.20+.80*math.sin(math.pi*t)**.5)
            for dz in (-half,half):
                hit,normal,_,_=tree.ray_cast(Vector((x,-.4,z+dz)),Vector((0,1,0)),.6)
                assert hit is not None, 'Brow projection missed forehead'
                verts.append(hit+normal*.0006)
            if i:faces.append((2*i-2,2*i-1,2*i+1,2*i))
        me=bpy.data.meshes.new('Tapered brow');me.from_pydata(verts,[],faces);me.update()
        brow=bpy.data.objects.new('Eyebrow '+side,me);bpy.context.collection.objects.link(brow)
        brow.parent=root;brow.matrix_parent_inverse=root.matrix_world.inverted();brow.data.materials.append(dark);brow['face_detail']=True
        for f in me.polygons:f.use_smooth=True
        # Fine upper-lid lash line; tips are deliberately short and understated.
        line=[]
        for i in range(17):
            t=i/16;x=eye.x+(t-.5)*.023;z=eye.z+.003+.003*math.sin(math.pi*t)
            y=eye.y-math.sqrt(max(.00001,.012**2-(x-eye.x)**2-(z-eye.z)**2))-.0004
            line.append(Vector((x,y,z)))
        strand('Upper lashes '+side,line,.00045,dark,root)
        for i in range(2,16,2):
            a=line[i];strand('Lash '+side+str(i),[a,a+Vector((sign*.0004,-.0014,.0005)),a+Vector((sign*.0008,-.0025,.001))],.00018,dark,root)
    # Skin-space beard tint stays on the deforming mesh, with feathered borders.
    states=[(m,m.show_viewport) for m in body.modifiers]
    for m,_ in states:m.show_viewport=False
    bpy.context.view_layer.update();ev=body.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();points=[v.co.copy() for v in me.vertices];ev.to_mesh_clear()
    for m,state in states:m.show_viewport=state
    attr=body.data.attributes.new('beard_shade','FLOAT','POINT')
    eyez=rig.data.bones['eye.L'].head_local.z
    def smooth(a,b,v):
        t=max(0,min(1,(v-a)/(b-a)));return t*t*(3-2*t)
    for item,p in zip(attr.data,points):
        x,y,z=p;d=eyez-z
        jaw=smooth(.035,.055,d)*(1-smooth(.115,.140,d))
        cheek=smooth(.027,.046,abs(x))*smooth(.020,.045,d)*(1-smooth(.11,.14,d))
        lip=1-math.exp(-((x/.030)**2+((d-.061)/.009)**2)*2)
        front=1-smooth(-.075,-.035,y)
        item.value=(max(jaw,cheek)*lip*front*.65) if gender else 0


def ponytail_band(hair,rig):
    root=anchor(rig,'head','Ponytail band follows head')
    bpy.context.view_layer.update();ev=hair.evaluated_get(bpy.context.evaluated_depsgraph_get())
    points=[ev.matrix_world@v.co for v in ev.data.vertices]
    top=max(p.z for p in points)
    # Simple elastic around the high ponytail root.
    centre=Vector((0,.059,top-.065))
    mat=material('Ponytail elastic',(.13,.14,.15),.9)
    pts=[centre+Vector((.017*math.cos(i*2*math.pi/48),.012*math.sin(i*2*math.pi/48),.003*math.sin(i*2*math.pi/48))) for i in range(49)]
    strand('Ponytail elastic band',pts,.0025,mat,root,False)
