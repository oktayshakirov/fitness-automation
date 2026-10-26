"""Original procedural eye surfaces and wrist watches; no external assets."""
import bpy, math
from mathutils import Matrix


def material(name, colour, rough=.4, metal=0):
    m=bpy.data.materials.new(name);m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(*colour,1)
    p.inputs['Roughness'].default_value=rough
    p.inputs['Metallic'].default_value=metal
    return m


def anchor(rig,bone,name):
    root=bpy.data.objects.new(name,None);bpy.context.collection.objects.link(root)
    root.matrix_world=rig.matrix_world@rig.data.bones[bone].matrix_local
    c=root.constraints.new('COPY_TRANSFORMS');c.target=rig;c.subtarget=bone
    root['accessory_anchor']=True
    return root


def add_eyes(rig):
    m=material('Warm brown eyes',(.65,.68,.64),.22)
    nt=m.node_tree;n=nt.nodes;l=nt.links;p=n.get('Principled BSDF')
    tex=n.new('ShaderNodeTexCoord');sep=n.new('ShaderNodeSeparateXYZ');l.new(tex.outputs['Generated'],sep.inputs[0])
    def mathnode(op,a,b):
        q=n.new('ShaderNodeMath');q.operation=op
        for i,v in enumerate((a,b)):
            if isinstance(v,(int,float)):q.inputs[i].default_value=v
            else:l.new(v,q.inputs[i])
        return q.outputs[0]
    x=mathnode('SUBTRACT',sep.outputs['X'],.5);z=mathnode('SUBTRACT',sep.outputs['Z'],.5)
    radius=mathnode('SQRT',mathnode('ADD',mathnode('MULTIPLY',x,x),mathnode('MULTIPLY',z,z)),0)
    ramp=n.new('ShaderNodeValToRGB');r=ramp.color_ramp;r.interpolation='EASE'
    r.elements.remove(r.elements[1])
    for i,(pos,col) in enumerate(((0,(.002,.003,.004,1)),(.095,(.003,.004,.005,1)),(.115,(.12,.055,.018,1)),(.20,(.20,.11,.035,1)),(.23,(.025,.018,.010,1)),(.25,(.65,.68,.64,1)))):
        e=r.elements[0] if i==0 else r.elements.new(pos);e.position=pos;e.color=col
    l.new(radius,ramp.inputs[0]);l.new(ramp.outputs[0],p.inputs['Base Color'])
    for side in ('L','R'):
        bone=rig.data.bones['eye.'+side]
        bpy.ops.mesh.primitive_uv_sphere_add(segments=40,ring_count=24,radius=.012,location=bone.head_local)
        eye=bpy.context.object;eye.name='Coloured eye '+side;eye['coloured_eye']=True
        eye.data.materials.append(m)
        for f in eye.data.polygons:f.use_smooth=True
        root=anchor(rig,'eye.'+side,'Eye anchor '+side)
        world=eye.matrix_world.copy();eye.parent=root;eye.matrix_world=world


def add_watch(rig):
    root=anchor(rig,'lowerarm02.L','Watch follows wrist')
    band=material('Black silicone strap',(.012,.015,.020),.75)
    case=material('Watch graphite case',(.045,.055,.065),.28,.65)
    glass=material('Watch glass',(.008,.022,.030),.16,.15)
    centre=rig.data.bones['lowerarm02.L'].length-.022
    verts=[];faces=[]
    for y,scale in ((centre-.011,1),(centre+.011,1),(centre-.011,1.10),(centre+.011,1.10)):
        for i in range(64):
            a=2*math.pi*i/64;verts.append((.027*scale*math.cos(a),y,.021*scale*math.sin(a)))
    for j,k in ((0,1),(2,3),(0,2),(1,3)):
        for i in range(64):faces.append((j*64+i,j*64+(i+1)%64,k*64+(i+1)%64,k*64+i))
    mesh=bpy.data.meshes.new('Watch strap');mesh.from_pydata(verts,[],faces);mesh.update()
    o=bpy.data.objects.new('Smartwatch strap',mesh);bpy.context.collection.objects.link(o);o.parent=root;o.data.materials.append(band);o['smartwatch']=True
    for f in mesh.polygons:f.use_smooth=True
    def box(name,loc,size,mat,bevel):
        bpy.ops.mesh.primitive_cube_add(size=1)
        o=bpy.context.object;o.name=name;o.parent=root;o.location=loc;o.scale=size
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        o.data.materials.append(mat);o['smartwatch']=True
        b=o.modifiers.new('Rounded corners','BEVEL');b.width=bevel;b.segments=4
        o.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
    box('Smartwatch case',(0,centre,.024),(.036,.042,.009),case,.005)
    box('Smartwatch screen',(0,centre,.029),(.029,.034,.002),glass,.004)
    accent=material('Watch display',(.05,.45,.30),.35)
    box('Watch activity indicator',(0,centre,.0302),(.018,.002,.0005),accent,.0005)
