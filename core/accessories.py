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
    from mathutils import Vector
    wrist=rig.data.bones['wrist.L']
    # The wrist frame follows the back of the hand; forearm roll differs.
    fitted=wrist.matrix_local.copy()
    fitted.translation=wrist.head_local-fitted.to_3x3().col[1]*.020
    attachment=anchor(rig,'wrist.L','Watch follows wrist')
    root=bpy.data.objects.new('Watch aligned to hand plane',None)
    bpy.context.collection.objects.link(root);root.parent=attachment
    root.matrix_world=rig.matrix_world@fitted
    band=material('Black silicone strap',(.012,.015,.020),.75)
    case=material('Watch graphite case',(.045,.055,.065),.28,.65)
    glass=material('Watch glass',(.008,.022,.030),.16,.15)
    centre=0.
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
    box('Smartwatch case',(0,centre,-.024),(.036,.042,.009),case,.005)
    box('Smartwatch screen',(0,centre,-.029),(.029,.034,.002),glass,.004)
    accent=material('Watch display',(.05,.45,.30),.35)
    box('Watch activity indicator',(0,centre,-.0302),(.018,.002,.0005),accent,.0005)


def add_shoes(rig):
    """Low-profile trainers fitted to foot/toe landmarks, rigid to each foot."""
    from mathutils import Vector
    upper=material('Trainer charcoal mesh',(.022,.028,.035),.85)
    sole=material('Trainer grey rubber',(.16,.18,.20),.8)
    lace=material('Trainer laces',(.32,.35,.38),.8)
    for side in ('L','R'):
        foot=rig.data.bones['foot.'+side]
        toes=[b for b in rig.data.bones if b.name.startswith('toe') and b.name.endswith('.'+side)]
        points=[p for b in toes for p in (b.head_local,b.tail_local)]
        x=(min(p.x for p in points)+max(p.x for p in points))/2
        front=min(p.y for p in points)-.017;rear=foot.head_local.y+.060
        width=(max(p.x for p in points)-min(p.x for p in points))/2+.018
        root=anchor(rig,'foot.'+side,'Trainer follows foot '+side)
        def meshpart(name,verts,faces,mat):
            me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update()
            o=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(o)
            o.parent=root;o.matrix_parent_inverse=root.matrix_world.inverted()
            o.data.materials.append(mat);o['shoe']=True
            for f in me.polygons:f.use_smooth=True
            return o
        # Rounded plan outline, wider at the ball and narrower through the heel.
        stations=[(0,.08,.020),(.05,.65,.030),(.16,1.,.035),(.38,1.,.045),(.58,.85,.060),(.78,.72,.068),(.93,.65,.052),(1,.08,.025)]
        verts=[];faces=[];n=25
        for t,w,h in stations:
            y=front+(rear-front)*t
            for i in range(n):
                a=math.pi*i/(n-1);verts.append((x+width*w*math.cos(a),y,.011+h*math.sin(a)**.65))
        for j in range(len(stations)-1):
            for i in range(n-1):
                ids=(j*n+i,j*n+i+1,(j+1)*n+i+1,(j+1)*n+i)
                centre=sum((Vector(verts[k]) for k in ids),Vector())/4
                # Open collar around the ankle rather than sealing over the leg.
                if ((centre.x-foot.head_local.x)/.028)**2+((centre.y-foot.head_local.y)/.040)**2<1 and centre.z>.055:continue
                faces.append(ids)
        faces.append(tuple(range(n-1,-1,-1)))
        faces.append(tuple((len(stations)-1)*n+i for i in range(n)))
        o=meshpart('Trainer upper '+side,verts,faces,upper)
        m=o.modifiers.new('Soft textile surface','SUBSURF');m.levels=2
        m=o.modifiers.new('Upper thickness','SOLIDIFY');m.thickness=.002
        # Continuous rubber outsole, kept above the existing bare-foot floor datum.
        outline=[(x+width*w,front+(rear-front)*t) for t,w,h in stations]
        outline += [(x-width*w,front+(rear-front)*t) for t,w,h in reversed(stations)]
        count=len(outline);v=[(a,b,z) for z in (.001,.012) for a,b in outline]
        f=[tuple(range(count-1,-1,-1)),tuple(range(count,count*2))]
        f += [(i,(i+1)%count,(i+1)%count+count,i+count) for i in range(count)]
        o=meshpart('Trainer sole '+side,v,f,sole)
        m=o.modifiers.new('Rounded rubber edge','BEVEL');m.width=.004;m.segments=3
        o.modifiers.new('Sole normals','WEIGHTED_NORMAL')
        for j,t in enumerate((.40,.46,.52,.58)):
            y=front+(rear-front)*t;h=.045+(t-.38)/.20*.015
            curve=bpy.data.curves.new('Lace','CURVE');curve.dimensions='3D';curve.bevel_depth=.0016;curve.bevel_resolution=2
            s=curve.splines.new('POLY');s.points.add(2)
            for p,co in zip(s.points,((x-.020,y,.011+h*.90+.003),(x,y-.004,.011+h+.004),(x+.020,y,.011+h*.90+.003))):p.co=(*co,1)
            o=bpy.data.objects.new('Trainer lace '+side+str(j),curve);bpy.context.collection.objects.link(o);o.parent=root;o.matrix_parent_inverse=root.matrix_world.inverted();o.data.materials.append(lace);o['shoe']=True
