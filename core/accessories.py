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


def add_eyes(rig, gender=1.0):
    m=material('Blue eyes' if gender else 'Green eyes',(.65,.68,.64),.22)
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
    iris=(.035,.17,.32,1) if gender else (.055,.22,.095,1)
    inner=(.02,.07,.13,1) if gender else (.045,.11,.035,1)
    for i,(pos,col) in enumerate(((0,(.002,.003,.004,1)),(.095,(.003,.004,.005,1)),(.115,inner),(.20,iris),(.23,(.025,.018,.010,1)),(.25,(.65,.68,.64,1)))):
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


def add_watch(rig, body, model):
    from mathutils import Vector
    wrist=rig.data.bones['wrist.L']
    index=rig.data.bones['finger2-1.L'].head_local
    pinky=rig.data.bones['finger5-1.L'].head_local
    y=((index+pinky)/2-wrist.head_local).normalized()
    dorsal=(index-pinky).cross(y).normalized()
    from mathutils.bvhtree import BVHTree
    bpy.context.view_layer.update()
    ev=body.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh()
    handtree=BVHTree.FromPolygons([body.matrix_world@v.co for v in me.vertices],[list(p.vertices) for p in me.polygons]);ev.to_mesh_clear()
    centre_hand=wrist.head_local+y*.035
    hit,normal,_,_=handtree.ray_cast(centre_hand,Vector((0,-1,0)),.10)
    assert hit is not None, 'Missing dorsal hand surface'
    dorsal=normal.normalized()
    if dorsal.y>0:dorsal.negate()
    z=-dorsal;y=(y-z*y.dot(z)).normalized();x=y.cross(z).normalized();y=z.cross(x).normalized()
    fitted=Matrix((x,y,z)).transposed().to_4x4()
    target=fitted.to_3x3().inverted() @ (-wrist.matrix_local.to_3x3().col[2])
    turn=(6 if model=='male' else 4)*max(-math.radians(10),min(math.radians(10),math.atan2(-target.x,-target.z)))
    fitted=fitted @ Matrix.Rotation(turn,4,'Y')
    fitted.translation=wrist.head_local-y*.018
    attachment=anchor(rig,'wrist.L','Watch follows wrist')
    root=bpy.data.objects.new('Watch aligned to hand plane',None)
    bpy.context.collection.objects.link(root);root.parent=attachment
    root.matrix_world=rig.matrix_world@fitted
    band=material('Black silicone strap',(.012,.015,.020),.75)
    case=material('Watch graphite case',(.045,.055,.065),.28,.65)
    glass=material('Watch glass',(.003,.003,.003),.20,.05)
    centre=0.
    from mathutils.bvhtree import BVHTree
    bpy.context.view_layer.update()
    evaluated=body.evaluated_get(bpy.context.evaluated_depsgraph_get());skin=evaluated.to_mesh()
    tree=BVHTree.FromPolygons([fitted.inverted() @ (body.matrix_world @ v.co) for v in skin.vertices], [list(p.vertices) for p in skin.polygons])
    evaluated.to_mesh_clear()
    def radius(y,a):
        hit,normal,face,distance=tree.ray_cast(Vector((0,y,0)),Vector((math.cos(a),0,math.sin(a))),.08)
        assert hit is not None, 'Cannot fit wrist strap'
        return distance
    verts=[];faces=[]
    for y,offset in ((-.009,.0007),(.009,.0007),(-.009,.0019),(.009,.0019)):
        for i in range(64):
            a=2*math.pi*i/64;r=radius(y,a)+offset
            verts.append((r*math.cos(a),y,r*math.sin(a)))
    for j,k in ((0,1),(2,3),(0,2),(1,3)):
        for i in range(64):faces.append((j*64+i,j*64+(i+1)%64,k*64+(i+1)%64,k*64+i))
    face_z=-radius(0,-math.pi/2)-.002
    mesh=bpy.data.meshes.new('Watch strap');mesh.from_pydata(verts,[],faces);mesh.update()
    o=bpy.data.objects.new('Smartwatch strap',mesh);bpy.context.collection.objects.link(o);o.parent=root;o.data.materials.append(band);o['smartwatch']=True
    import bmesh
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
    for f in mesh.polygons:f.use_smooth=True
    def rounded_case(name,loc,size,mat,radius):
        # Explicit rounded XY outline: corner radius is independent of thickness.
        w,h,d=size;outline=[]
        for cx,cy,start in ((w/2-radius,h/2-radius,0),(-w/2+radius,h/2-radius,90),(-w/2+radius,-h/2+radius,180),(w/2-radius,-h/2+radius,270)):
            for i in range(9):
                a=math.radians(start+i*90/8)
                outline.append((cx+radius*math.cos(a),cy+radius*math.sin(a)))
        n=len(outline);verts=[(x,y,z) for z in (-d/2,d/2) for x,y in outline]
        faces=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]
        faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
        me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update()
        o=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(o);o.parent=root;o.location=loc
        o.data.materials.append(mat);o['smartwatch']=True
        b=o.modifiers.new('Soft rim','BEVEL');b.width=.00025;b.segments=3
        o.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
    rounded_case('Smartwatch case',(0,centre,face_z-.002),(.032,.037,.004),case,.007)
    rounded_case('Smartwatch screen',(0,centre,face_z-.0043),(.027,.032,.0008),glass,.006)


def add_shoes(rig, body):
    """Low-profile trainers fitted to foot/toe landmarks, rigid to each foot."""
    from mathutils import Vector
    upper=material('Trainer charcoal mesh',(.022,.028,.035),.85)
    nt=upper.node_tree;noise=nt.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=180
    bump=nt.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.22;bump.inputs['Distance'].default_value=.0007
    nt.links.new(noise.outputs['Fac'],bump.inputs['Height']);nt.links.new(bump.outputs[0],nt.nodes['Principled BSDF'].inputs['Normal'])
    sole=material('Trainer grey rubber',(.16,.18,.20),.8)
    panel=material('Trainer reinforced toe and heel',(.012,.017,.023),.6)
    lace=material('Trainer laces',(.32,.35,.38),.8)
    bpy.context.view_layer.update()
    ev=body.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh()
    skin=[body.matrix_world@v.co for v in me.vertices];ev.to_mesh_clear()
    for side in ('L','R'):
        foot=rig.data.bones['foot.'+side]
        toes=[b for b in rig.data.bones if b.name.startswith('toe') and b.name.endswith('.'+side)]
        points=[p for b in toes for p in (b.head_local,b.tail_local)]
        x=(min(p.x for p in points)+max(p.x for p in points))/2
        foot_skin=[p for p in skin if p.z<.075 and p.x*(1 if side=='L' else -1)>0]
        front=min(p.y for p in foot_skin)-.014;rear=max(p.y for p in foot_skin)+.008
        forefoot=[p for p in foot_skin if p.y<foot.head_local.y-.055]
        x=(min(p.x for p in forefoot)+max(p.x for p in forefoot))/2
        width=(max(p.x for p in forefoot)-min(p.x for p in forefoot))/2+.008
        root=anchor(rig,'foot.'+side,'Trainer follows foot '+side)
        def meshpart(name,verts,faces,mat):
            me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update()
            o=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(o)
            o.parent=root;o.matrix_parent_inverse=root.matrix_world.inverted()
            o.data.materials.append(mat);o['shoe']=True
            for f in me.polygons:f.use_smooth=True
            return o
        # Rounded plan outline, wider at the ball and narrower through the heel.
        stations=[(0,.40,.025),(.05,.88,.035),(.16,1.,.040),(.38,1.,.045),(.58,.85,.060),(.78,.72,.068),(.93,.65,.052),(1,.35,.040)]
        verts=[];faces=[];n=25
        for t,w,h in stations:
            y=front+(rear-front)*t
            for i in range(n):
                a=math.pi*i/(n-1);verts.append((x+width*w*math.copysign(abs(math.cos(a))**.65,math.cos(a)),y,.011+h*math.sin(a)**.65))
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
        o.data.materials.append(panel)
        for face in o.data.polygons:
            c=sum((o.data.vertices[i].co for i in face.vertices),Vector())/len(face.vertices)
            t=(c.y-front)/(rear-front)
            if t<.16 or t>.78:face.material_index=1
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
            for p,co in zip(s.points,((x-.020,y,.011+h*.90+.003),(x,y-.004,.011+h+.004),(x+.020,y+.008,.011+h*.90+.003))):p.co=(*co,1)
            o=bpy.data.objects.new('Trainer lace '+side+str(j),curve);bpy.context.collection.objects.link(o);o.parent=root;o.matrix_parent_inverse=root.matrix_world.inverted();o.data.materials.append(lace);o['shoe']=True


def add_nail_polish(body,rig):
    """Short nail plates projected onto distal fingers, attached to each digit."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    bpy.context.view_layer.update();ev=body.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh()
    tree=BVHTree.FromPolygons([body.matrix_world@v.co for v in me.vertices],[list(p.vertices) for p in me.polygons]);ev.to_mesh_clear()
    polish=material('Muted rose nail polish',(.32,.065,.10),.24)
    for side in ('L','R'):
        wrist=rig.data.bones['wrist.'+side]
        mid=rig.data.bones['finger3-1.'+side].head_local
        hit,normal,_,_=tree.ray_cast((wrist.head_local+mid)/2,Vector((0,-1,0)),.10)
        assert hit is not None
        hand_normal=normal.normalized()
        if hand_normal.y>0:hand_normal.negate()
        for finger in range(1,6):
            name=f'finger{finger}-3.{side}';bone=rig.data.bones[name]
            along=(bone.tail_local-bone.head_local).normalized()
            out=(hand_normal-along*hand_normal.dot(along)).normalized()
            across=along.cross(out).normalized()
            centre=bone.head_local.lerp(bone.tail_local,.60)
            length=min(.0045,bone.length*.25);width=.0026 if finger<5 else .0021
            verts=[];faces=[]
            for ring in range(5):
                for i in range(32):
                    a=2*math.pi*i/32;r=max(.001,ring/4)
                    offset=(across*(width*math.cos(a))+along*(length*math.sin(a)))*r
                    origin=centre+offset
                    hit,n,_,_=tree.ray_cast(origin+out*.025,-out,.05)
                    assert hit is not None, 'Nail projection missed finger'
                    verts.append(hit+n*.00065)
                    if ring:
                        faces.append(((ring-1)*32+i,(ring-1)*32+(i+1)%32,ring*32+(i+1)%32,ring*32+i))
            mesh=bpy.data.meshes.new('Nail plate');mesh.from_pydata(verts,[],faces);mesh.update()
            o=bpy.data.objects.new('Rose nail '+name,mesh);bpy.context.collection.objects.link(o)
            root=anchor(rig,name,'Nail follows '+name);o.parent=root;o.matrix_parent_inverse=root.matrix_world.inverted()
            o.data.materials.append(polish);o['nail_polish']=True
            for p in mesh.polygons:p.use_smooth=True
