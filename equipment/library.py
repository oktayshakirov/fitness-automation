"""Procedural equipment in metres. No downloaded geometry or textures.
Rigid implements: origin at grip/ring, local X across the hands; -Z hangs down.
Fixed equipment: ground origin, except pullup_bar (bar-centre origin).
"""
import math, json
import bpy
from mathutils import Vector
from .basic import empty, cyl_x, mat, _add


def cube(name, loc, size, material='frame', parent=None, bevel=.008):
    o=_add('primitive_cube_add',name,material,parent,size=1,location=loc,scale=size)
    if bevel:
        m=o.modifiers.new('rounded edges','BEVEL'); m.width=bevel; m.segments=3
        m=o.modifiers.new('weighted normals','WEIGHTED_NORMAL')
    for p in o.data.polygons: p.use_smooth=False
    return o


def tube(name, points, radius=.018, material='steel', parent=None):
    d=bpy.data.curves.new(name,'CURVE'); d.dimensions='3D'; d.resolution_u=2
    d.bevel_depth=radius; d.bevel_resolution=3
    s=d.splines.new('POLY'); s.points.add(len(points)-1)
    for p,v in zip(s.points,points): p.co=(*v,1)
    o=bpy.data.objects.new(name,d); bpy.context.scene.collection.objects.link(o)
    d.materials.append(mat(material)); o.parent=parent
    return o


def beam(name,a,b,width=.06,parent=None,material='frame'):
    a,b=Vector(a),Vector(b); o=cube(name,(a+b)/2,(width,width,(b-a).length),material,parent)
    o.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler(); return o


def ring(name,loc=(0,0,0),parent=None,r=.018):
    return _add('primitive_torus_add',name,'steel',parent,major_radius=r,minor_radius=.004,
                location=loc,rotation=(math.pi/2,0,0))


def metadata(root, contacts):
    root['contacts_json']=json.dumps(contacts)
    return root


PLATES={25:(.225,.065),20:(.225,.055),15:(.225,.043),10:(.225,.035),5:(.115,.025),2.5:(.095,.020),1.25:(.075,.015)}

def barbell(name='barbell',plates=None,kind='olympic'):
    if kind!='olympic': raise ValueError('kind must be olympic')
    plates=[20] if plates is None else list(plates)
    if any(k not in PLATES for k in plates): raise ValueError('supported plate kg: '+str(list(PLATES)))
    if sum(PLATES[k][1]+.003 for k in plates)>.36: raise ValueError('plates exceed sleeve capacity')
    root=empty(name)
    cyl_x(name+'_shaft','steel',.014,1.31,parent=root)
    for x in (-.38,.38): cyl_x(name+'_knurl','dark',.0143,.30,x,root)
    for sign in (-1,1):
        cyl_x(name+'_sleeve','steel',.025,.445,sign*.8775,root)
        cyl_x(name+'_inner_collar','steel',.045,.025,sign*.6675,root)
        x=.685
        for kg in plates:
            r,w=PLATES[kg]; c=sign*(x+w/2)
            cyl_x(name+f'_{kg}kg','rubber',r,w,c,root,verts=64)
            cyl_x(name+'_hub','steel',.044,w+.002,c,root)
            for face in (-1,1):
                q=_add('primitive_torus_add',name+'_plate_rim','plate',root,major_radius=r-.012,minor_radius=.003,
                       location=(c+face*(w/2+.001),0,0),rotation=(0,math.pi/2,0))
            x+=w+.003
        cyl_x(name+'_lock','accent',.038,.025,sign*(x+.0125),root)
    root['plate_r']=max([PLATES[k][0] for k in plates],default=.045)
    root['kg']=20+2*sum(plates)
    return metadata(root,{'grip_axis':[1,0,0],'shaft_range':[-.655,.655],'plate_r':root['plate_r']})


def ez_bar(name='ez_bar'):
    r=empty(name)
    pts=[(-.6,0,0),(-.4,0,0),(-.30,0,.045),(-.15,0,-.025),(0,0,.025),(.15,0,-.025),(.30,0,.045),(.4,0,0),(.6,0,0)]
    tube(name+'_bent_shaft',pts,.014,parent=r)
    for s in (-1,1):
        cyl_x(name+'_sleeve','steel',.025,.2,s*.5,r)
        cyl_x(name+'_collar','dark',.04,.02,s*.4,r)
    return metadata(r,{'grips':[[-.225,0,.01],[.225,0,.01]],'grip_axis':[1,0,0]})


def kettlebell(name='kettlebell',kg=16):
    if kg<=0: raise ValueError('kg must be positive')
    r=empty(name); radius=.105*(kg/16)**(1/3)
    bell=_add('primitive_uv_sphere_add',name+'_bell','dark',r,radius=radius,segments=40,ring_count=24,location=(0,0,-.085-radius))
    # Flatten bottom, retain a broad stable base.
    for v in bell.data.vertices: v.co.z=max(v.co.z,-radius*.86)
    tube(name+'_handle',[(-.085,0,-.16),(-.095,0,-.035),(-.075,0,0),(.075,0,0),(.095,0,-.035),(.085,0,-.16)],.014,'dark',r)
    cyl_x(name+'_grip_mark','accent',.0145,.025,0,r)
    r['kg']=kg
    return metadata(r,{'grip_axis':[1,0,0],'grip_range':[-.075,.075]})


def bench(name='bench',incline=0,seat_z=.43,y0=-.78,y1=.42):
    if not -20<=incline<=85: raise ValueError('incline must be -20..85 degrees')
    r=empty(name); a=math.radians(incline); hinge=-.30
    for y in (y0+.13,y1-.12):
        cube(name+'_foot',(0,y,.025),(.48,.10,.05),parent=r)
        beam(name+'_leg',(0,y,.05),(0,y,seat_z-.08),parent=r)
    beam(name+'_spine',(0,y0,seat_z-.12),(0,y1,seat_z-.12),parent=r)
    cube(name+'_seat',(0,(y0+hinge)/2,seat_z-.04),(.30,hinge-y0-.012,.08),'rubber',r)
    pivot=empty(name+'_back_pivot',(0,hinge,seat_z)); pivot.parent=r; pivot.rotation_euler.x=a
    cube(name+'_back',(0,(y1-hinge)/2,-.04),(.30,y1-hinge-.012,.08),'rubber',pivot)
    if incline:
        beam(name+'_support',(0,.25,.10),(0,hinge+(y1-hinge)*.65*math.cos(a),seat_z+(y1-hinge)*.65*math.sin(a)-.08),parent=r)
    r['seat_z']=seat_z; r['pad_y_range']=[y0,y1]
    return metadata(r,{'seat_z':seat_z,'pad_plane':{'point':[0,hinge,seat_z],'normal':[0,-math.sin(a),math.cos(a)]},'pad_y_range':[y0,y1],'width':.30,'incline':incline})


def power_rack(name='power_rack',hook_z=1.4,safety_z=.65):
    r=empty(name)
    for x in (-.58,.58):
        for y in (-.50,.50):
            beam(name+'_upright',(x,y,.04),(x,y,2.22),parent=r)
            cube(name+'_foot',(x,y,.025),(.22,.30,.05),parent=r)
        beam(name+'_top',(x,-.50,2.2),(x,.50,2.2),parent=r)
        beam(name+'_safety',(x,-.50,safety_z),(x,.50,safety_z),parent=r)
        cube(name+'_j_hook',(x,.40,hook_z-.03),(.065,.16,.06),'steel',r)
        cube(name+'_j_lip',(x,.33,hook_z+.015),(.065,.025,.06),'rubber',r)
    beam(name+'_rear',( -.58,.5,2.2),(.58,.5,2.2),parent=r)
    tube(name+'_pullup',[(-.58,-.5,2.15),(.58,-.5,2.15)],.016,parent=r)
    return metadata(r,{'bar_rest':[0,.40,hook_z],'safety_z':safety_z,'inner_width':1.1})


def pullup_bar(name='pullup_bar',z=2.2):
    # Caller sets root at contact centre; z is descriptive, not a second offset.
    r=empty(name)
    tube(name+'_bar',[(-.68,0,0),(.68,0,0)],.016,parent=r)
    for x in (-.58,.58):
        beam(name+'_bracket',(x,0,0),(x,-.50,0),.045,r)
        cube(name+'_wall_mount',(x,-.52,-.08),(.10,.04,.30),parent=r)
    return metadata(r,{'grip_axis':[1,0,0],'grip_z':z,'root_at_bar':True})


def dip_station(name='dip_station',height=1.2,width=.52):
    r=empty(name)
    for x in (-width/2,width/2):
        tube(name+'_rail',[(x,-.4,height),(x,.4,height)],.02,parent=r)
        for y in (-.3,.3): beam(name+'_post',(x,y,.04),(x,y,height),.055,r)
        cube(name+'_base',(x,0,.03),(.25,1.0,.06),parent=r)
    return metadata(r,{'hands':[[-width/2,0,height],[width/2,0,height]],'grip_axis':[0,1,0]})


def box(name='box',h=.4):
    r=empty(name); cube(name+'_body',(0,0,h/2),(.55,.55,h),'rubber',r)
    r['seat_z']=h; return metadata(r,{'top_plane':{'point':[0,0,h],'normal':[0,0,1]}})


def mat_floor(name='mat',length=1.9,width=.7):
    r=empty(name); cube(name+'_pad',(0,0,.006),(width,length,.012),'rubber',r,bevel=.005)
    return r


def rope(name='rope'):
    r=empty(name); ring(name+'_ring',parent=r)
    for s in (-1,1):
        tube(name+'_strand',[(0,0,-.015),(s*.09,0,-.11),(s*.17,0,-.24)],.011,'cable',r)
        _add('primitive_uv_sphere_add',name+'_stop','rubber',r,radius=.025,segments=20,ring_count=12,location=(s*.17,0,-.25))
    return metadata(r,{'ring':[0,0,0],'ends':[[-.17,0,-.24],[.17,0,-.24]]})


def update_rope(root,left,right,frame):
    """World-space hand endpoints; root is ring position (may be animated by caller)."""
    bpy.context.view_layer.update(); inv=root.matrix_world.inverted()
    strands=[o for o in root.children if o.type=='CURVE']
    stops=[o for o in root.children if o.type=='MESH' and '_stop' in o.name]
    for o,stop,end in zip(strands,stops,(left,right)):
        end=inv@Vector(end); start=Vector((0,0,-.015))
        for p,v in zip(o.data.splines[0].points,(start,start.lerp(end,.5),end)):
            p.co=(*v,1); p.keyframe_insert('co',frame=frame)
        stop.location=end; stop.keyframe_insert('location',frame=frame)


def d_handle(name='d_handle'):
    r=empty(name); ring(name+'_ring',parent=r)
    tube(name+'_frame',[(0,0,-.02),(-.09,0,-.13),(.09,0,-.13),(0,0,-.02)],.009,parent=r)
    o=cyl_x(name+'_grip','rubber',.016,.14,parent=r); o.location.z=-.13
    return metadata(r,{'ring':[0,0,0],'grip':[0,0,-.13],'grip_axis':[1,0,0]})


def v_bar(name='v_bar'):
    r=empty(name); ring(name+'_ring',parent=r)
    tube(name+'_bridge',[(-.07,0,-.09),(0,0,-.025),(.07,0,-.09)],.012,parent=r)
    for x in (-.045,.045): tube(name+'_grip',[(x,0,-.06),(x,0,-.20)],.016,'rubber',r)
    return metadata(r,{'ring':[0,0,0],'grips':[[-.045,0,-.13],[.045,0,-.13]],'grip_axis':[0,0,1]})


def lat_bar(name='lat_bar'):
    r=empty(name); ring(name+'_ring',parent=r)
    tube(name+'_bar',[(-.60,0,-.17),(-.42,0,-.04),(.42,0,-.04),(.60,0,-.17)],.014,parent=r)
    for s in (-1,1): tube(name+'_grip',[(s*.33,0,-.04),(s*.47,0,-.076)],.017,'rubber',r)
    return metadata(r,{'ring':[0,0,0],'grips':[[-.40,0,-.04],[.40,0,-.04]]})


def ankle_strap(name='ankle_strap'):
    r=empty(name); ring(name+'_ring',parent=r)
    o=_add('primitive_torus_add',name+'_cuff','rubber',r,major_radius=.047,minor_radius=.014,location=(0,0,-.065)); o.scale.z=2
    return metadata(r,{'ring':[0,0,0],'ankle':[0,0,-.065]})


class ResistanceBand:
    def __init__(self,name='band',a=(0,0,.1),b=(0,0,1),rest_length=None):
        self.a,self.b=Vector(a),Vector(b); self.rest_length=rest_length or (self.b-self.a).length
        if self.rest_length<=0: raise ValueError('positive rest length required')
        self.obj=tube(name,[self.a,self.b],.008,'accent'); self.update(a,b,1)
    def update(self,a,b,frame):
        a,b=Vector(a),Vector(b); stretch=max(1,(b-a).length/self.rest_length)
        for p,v in zip(self.obj.data.splines[0].points,(a,b)):
            p.co=(*v,1); p.keyframe_insert('co',frame=frame)
        self.obj.data.bevel_depth=.008/math.sqrt(stretch)
        self.obj.data.keyframe_insert('bevel_depth',frame=frame)
        self.obj['stretch']=stretch
        return stretch


def resistance_band(name='band',a=(0,0,.1),b=(0,0,1),rest_length=None):
    return ResistanceBand(name,a,b,rest_length)
