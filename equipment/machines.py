"""Machine shells with a driven pivot/slider and root-local contact contract.
Facing -Y; metres, degrees. Update accepts the motion layer's pad/plate/handle contacts.
"""
import math,json
import bpy
from mathutils import Vector,Matrix
from .basic import empty,cyl_x
from .library import cube,beam,tube,metadata,barbell

DEFAULTS={
 'lat_pulldown':dict(seat_z=.48,lean=-12,pulley=[0,-.05,2.45]),
 'seated_row':dict(seat_z=.42,lean=0,pulley=[0,-.95,.30]),
 'leg_press':dict(seat_z=.45,lean=-48,rail_deg=45),
 'leg_extension':dict(seat_z=.50,lean=-10,knee_y=-.47),
 'leg_curl':dict(seat_z=.50,lean=-10,knee_y=-.47),
 'chest_press':dict(seat_z=.48,lean=-10),
 'pec_deck':dict(seat_z=.48,lean=-10),
 'smith_machine':dict(seat_z=0,lean=0),
 'hack_squat':dict(seat_z=.7,lean=-45,rail_deg=45),
}
ALIASES={'pulldown':'lat_pulldown','cable_row':'seated_row','smith':'smith_machine'}


class Machine:
    def __init__(self,kind,name=None,seat_z=None,lean=None,**kw):
        kind=ALIASES.get(kind,kind)
        if kind not in DEFAULTS: raise ValueError('unknown machine '+kind)
        self.kind=kind; name=name or kind; self.root=empty(name)
        c=dict(DEFAULTS[kind],**kw)
        if seat_z is not None: c['seat_z']=seat_z
        if lean is not None: c['lean']=lean
        z=c['seat_z']; a=math.radians(c['lean']); self.moving=None; self.arms=[]; self.press_guides=[]
        up=Vector((0,-math.sin(a),math.cos(a))); back=Vector((0,math.cos(a),math.sin(a)))
        hip=Vector((0,0,z+.085)); bp=hip+up*.36+back*.10
        self.contacts={**c,'units':'metres','space':'root-local','facing':[0,-1,0],
          'seat_plane':{'point':[0,-.1,z],'normal':[0,0,1]},
          'back_pad_plane':{'point':list(bp-back*.04),'normal':list(-back)},
          'side_grips':[[-.27,-.08,z+.03],[.27,-.08,z+.03]],
          'handle_path':None,'foot_plate':None}
        r=self.root
        if kind=='smith_machine':
            for x in (-.78,.78):
                beam(name+'_post',(x,0,.03),(x,0,2.3),.08,r)
                beam(name+'_guide',(x,-.12,.15),(x,-.12,2.2),.022,r,'steel')
                cube(name+'_foot',(x,0,.04),(.4,1.3,.08),parent=r)
                for zz in (.5,.8,1.1,1.4,1.7,2): cube(name+'_stop',(x,-.16,zz),(.09,.12,.035),parent=r)
            beam(name+'_top',(-.78,0,2.3),(.78,0,2.3),.08,r)
            self.moving=barbell(name+'_bar',plates=[]); self.moving.parent=r; self.moving.location=(0,-.12,1.3)
            self.contacts['handle_path']={'type':'slider','origin':[0,-.12,.3],'axis':[0,0,1],'range':[0,1.8]}
        else:
            base_y=-.35 if kind in ('lat_pulldown','seated_row','leg_press','hack_squat') else -.1
            for x in (-.33,.33): cube(name+'_base',(x,base_y,.04),(.10,1.85 if kind in ('lat_pulldown','seated_row') else 1.65,.08),parent=r)
            for yy in (-.55,.45): beam(name+'_cross',(-.33,yy,.08),(.33,yy,.08),.065,r)
            if kind!='hack_squat':
                depth=.9 if kind=='seated_row' else .44
                cube(name+'_seat',(0,-.12,z-.04),(.42,depth,.08),'rubber',r)
                beam(name+'_seat_post',(0,-.08,.08),(0,-.08,z-.08),.10,r)
                if kind not in ('lat_pulldown','seated_row'):
                    o=cube(name+'_back',bp,(.40,.08,.68),'rubber',r); o.rotation_euler.x=a
                    beam(name+'_back_support',(0,.25,.08),bp,.065,r)
                for x in (-.27,.27): tube(name+'_side_grip',[(x,.18,z+.03),(x,-.22,z+.03)],.016,'rubber',r)
            if kind in ('leg_extension','leg_curl'):
                # Pivots align with the declared knee plane; one common cross shaft.
                self.pivot=empty(name+'_pivot',(0,c['knee_y'],z+.03)); self.pivot.parent=r
                self.moving=empty(name+'_lever'); self.moving.parent=self.pivot
                for x in (-.32,.32):
                    beam(name+'_pivot_support',(x,-.47,.08),(x,-.47,z+.03),.055,r)
                    beam(name+'_arm',(x,0,0),(x,0,-.38),.04,self.moving)
                roller=cyl_x(name+'_shin_roller','rubber',.055,.52,parent=self.moving); roller.location.z=-.38
                self.roller=roller
                axle=cyl_x(name+'_axle','steel',.025,.70,parent=self.pivot)
                if kind=='leg_curl':
                    pad=cyl_x(name+'_thigh_pad','rubber',.055,.48,parent=r); pad.location=(0,-.30,z+.15)
                    self.contacts['thigh_pad']=[0,-.30,z+.15]
                    for x in (-.29,.29):
                        tube(name+'_pad_support',[(x,.15,z+.03),(x,-.30,z+.03),(x,-.30,z+.15)],.018,'frame',r)
                self.contacts.update(knee_pivot=[0,c['knee_y'],z+.03],pad_radius=.055,handle_path={'type':'pivot','axis':[1,0,0],'origin':[0,c['knee_y'],z+.03],'radius':.38,'degrees':[0,90]})
            elif kind in ('leg_press','hack_squat'):
                self.axis=Vector((0,-math.cos(math.radians(c['rail_deg'])),math.sin(math.radians(c['rail_deg']))))
                origin=hip+self.axis*.12 if kind=='leg_press' else Vector((0,-.35,.25))
                for x in (-.5,.5):
                    p=origin+Vector((x,0,0)); end=p+self.axis*(1.15 if kind=='leg_press' else 1.65)
                    rail=beam(name+'_rail',p,end,.045,r,'steel')
                    if kind=='leg_press':self.press_guides.append((rail,end.copy(),(end-p).length,rail.scale.z))
                    beam(name+'_rear_post',(end.x,end.y,.05),end,.07,r)
                self.moving=empty(name+'_sled'); self.moving.parent=r
                if kind=='leg_press':
                    cube(name+'_foot_plate',(0,0,0),(.75,.04,.55),'frame',self.moving)
                    beam(name+'_sled_cross',(-.5,0,0),(.5,0,0),.05,self.moving)
                    for x in (-.5,.5): cube(name+'_slider',(x,0,0),(.09,.16,.09),'frame',self.moving)
                    for zz in (-.2,-.1,0,.1,.2): cube(name+'_tread',(0,.024,zz),(.68,.008,.014),'rubber',self.moving,bevel=.003)
                    self.moving.location=hip+self.axis*.8; self.moving.rotation_euler.x=-math.pi/4
                    self.contacts['foot_plate']={'point':list(self.moving.location),'normal':list(-self.axis),'size':[.75,.55]}
                else:
                    cube(name+'_back_pad',(0,0,.4),(.45,.09,.85),'rubber',self.moving)
                    for x in (-.2,.2): cube(name+'_shoulder_pad',(x,-.12,.80),(.16,.30,.10),'rubber',self.moving)
                    self.moving.location=(0,-.5,.65); self.moving.rotation_euler.x=-math.pi/4
                    plate=cube(name+'_foot_plate',(0,-1.0,.14),(.85,.65,.08),'frame',r)
                    self.contacts['foot_plate']={'point':[0,-1,.18],'normal':[0,0,1],'size':[.85,.65]}
                self.contacts['handle_path']={'type':'slider','origin':list(origin),'axis':list(self.axis),'range':[0,1.15] if kind=='leg_press' else [.1,1.45]}
            elif kind in ('lat_pulldown','seated_row'):
                if kind=='lat_pulldown':
                    pad=cyl_x(name+'_knee_pad','rubber',.06,.49,parent=r); pad.location=(0,-.38,z+.15)
                    self.contacts['thigh_pad']=[0,-.38,z+.15]
                    for x in (-.29,.29):
                        tube(name+'_pad_support',[(x,.15,z+.03),(x,-.38,z+.03),(x,-.38,z+.15)],.018,'frame',r)
                    tower_y=-1.10; p=Vector(c['pulley'])
                    for x in (-.34,.34): beam(name+'_upright',(x,tower_y,.05),(x,tower_y,2.50),.06,r)
                    beam(name+'_boom',(0,tower_y,2.50),p,.07,r)
                    beam(name+'_tower_base',(-.34,tower_y,.08),(.34,tower_y,.08),.065,r)
                    beam(name+'_pad_stem',(0,tower_y,z+.15),(0,-.38,z+.15),.045,r)
                else:
                    tower_y=-1.25; p=Vector(c['pulley'])
                    for x in (-.34,.34): beam(name+'_upright',(x,tower_y,.05),(x,tower_y,1.35),.06,r)
                    o=cube(name+'_footplate',(0,-.80,.30),(.55,.05,.35),'frame',r); o.rotation_euler.x=math.radians(20)
                    beam(name+'_footplate_post',(0,-.80,.08),(0,-.80,.30),.07,r)
                    self.contacts['foot_plate']={'point':[0,-.78,.3],'normal':[0,1,.34],'size':[.55,.35]}
                top_z=2.50 if kind=='lat_pulldown' else 1.35
                beam(name+'_top_cross',(-.34,tower_y,top_z),(.34,tower_y,top_z),.06,r)
                for x in (-.12,.12): beam(name+'_stack_guide',(x,tower_y,.08),(x,tower_y,top_z-.08),.012,r,'steel')
                self.rear_pulley=Vector((0,tower_y,top_z-.05))
                rear=cyl_x(name+'_rear_pulley','dark',.05,.03,parent=r);rear.location=self.rear_pulley
                for i in range(8): cube(name+'_weight',(0,tower_y,.13+i*.033),(.36,.18,.03),'plate',r,bevel=.003)
                self.moving=empty(name+'_stack_cap',(0,tower_y,.54)); self.moving.parent=r
                cube(name+'_selected',(0,0,0),(.36,.18,.10),'plate',self.moving)
                for i in range(4): cube(name+'_lifted_weight',(0,0,-.146+i*.033),(.36,.18,.03),'plate',self.moving,bevel=.003)
                cube(name+'_selector',(0,-.098,0),(.10,.016,.02),'accent',self.moving)
                self.cable=tube(name+'_cable',[Vector((0,tower_y,.59)),self.rear_pulley,p,p+Vector((0,0,-.5))],.0035,'cable',r)
                pulley=cyl_x(name+'_pulley','dark',.05,.03,parent=r); pulley.location=p
                self.handle0=None
                self.contacts['handle_path']={'type':'cable','pulley':list(p)}
            elif kind in ('chest_press','pec_deck'):
                for s in (-1,1):
                    pivot=empty(name+'_pivot',(s*.38,.18,z+.82)); pivot.parent=r
                    arm=empty(name+'_arm'); arm.parent=pivot; self.arms.append(arm)
                    beam(name+'_upright',(s*.38,.18,.08),pivot.location,.07,r)
                    tube(name+'_lever',[(0,0,0),(0,-.18,-.30),(0,-.42,-.30)],.026,'frame',arm)
                    tube(name+'_handle',[(0,-.42,-.37),(0,-.42,-.20)],.016,'rubber',arm)
                    if kind=='pec_deck': cube(name+'_elbow_pad',(0,-.15,-.32),(.14,.10,.25),'rubber',arm)
                self.moving=self.arms[0]
                self.contacts['handle_path']={'type':'paired_pivot','axes':[[1,0,0],[1,0,0]] if kind=='chest_press' else [[0,0,1],[0,0,1]],'origins':[[-.38,.18,z+.82],[.38,.18,z+.82]],'degrees':[0,70]}
        r['seat_z']=z; metadata(r,self.contacts)

    def update(self,contacts,frame):
        """`pad`/`plate`: (world point, direction), `handle`: (point, axis, kind).
        Other machines accept normalized `travel` in [0,1]. Does not pose the body.
        """
        if not self.moving:return
        bpy.context.view_layer.update(); inv=self.root.matrix_world.inverted()
        if 'pad' in contacts and self.kind in ('leg_extension','leg_curl'):
            c=inv@Vector(contacts['pad'][0]); d=c-self.pivot.location
            self.moving.rotation_euler.x=math.atan2(d.y,-d.z)
            # The motion's shin contact may vary slightly; roller + arms follow its length.
            length=max(.15,d.length)
            self.moving.scale.z=length/.38
        elif 'plate' in contacts and self.kind=='leg_press':
            c,d=contacts['plate']; c=inv@Vector(c); d=(inv.to_3x3()@Vector(d)).normalized()
            x=Vector((1,0,0)); y=-d
            self.moving.location=c+d*.07
            self.moving.rotation_euler=Matrix((x,y,x.cross(y))).transposed().to_euler()
            # Telescoping guides terminate inside the sled collars. Exposed steel
            # belongs on the far side of the footplate, never in the leg space.
            for rail,end,rest_length,rest_scale in self.press_guides:
                start=self.moving.location.copy(); start.x=end.x
                rail.location=(start+end)/2
                rail.rotation_euler=(end-start).to_track_quat('Z','Y').to_euler()
                rail.scale.z=rest_scale*(end-start).length/rest_length
                for path in ('location','rotation_euler','scale'):
                    rail.keyframe_insert(path,frame=frame)
        elif 'handle' in contacts and self.kind in ('lat_pulldown','seated_row'):
            h=inv@Vector(contacts['handle'][0]); p=Vector(self.contacts['pulley'])
            length=(h-p).length
            if self.handle0 is None: self.handle0=length
            self.moving.location.z=.54+max(0,length-self.handle0)
            ring=h+(p-h).normalized()*(.04 if contacts['handle'][2]=='lat_bar' else .13)
            cable_points=(self.moving.location+Vector((0,0,.05)),self.rear_pulley,p,ring)
            for pt,v in zip(self.cable.data.splines[0].points,cable_points):
                pt.co=(*v,1); pt.keyframe_insert('co',frame=frame)
        elif 'travel' in contacts:
            t=max(0,min(1,float(contacts['travel'])))
            if self.kind=='smith_machine': self.moving.location.z=.3+1.8*t
            elif self.kind=='hack_squat': self.moving.location=Vector((0,-.5,.65))+self.axis*.65*t
            elif self.kind in ('chest_press','pec_deck'):
                for i,arm in enumerate(self.arms):
                    arm.rotation_euler[0 if self.kind=='chest_press' else 2]=math.radians(55)*t*(1 if self.kind=='chest_press' or i==0 else -1)
                    arm.keyframe_insert('rotation_euler',frame=frame)
        for path in ('location','rotation_euler','scale'): self.moving.keyframe_insert(path,frame=frame)


def machine(kind,**kwargs): return Machine(kind,**kwargs)
