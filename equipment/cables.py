"""High/mid/low cable towers and two independent crossover stacks."""
import math
import bpy
from mathutils import Vector
from .basic import CableTower as LegacyTower
from .library import beam


class CableTower(LegacyTower):
    def __init__(self,y_stack=-.74,y_front=-.25,top=2.12,plates=12,selected=5,
                 pulley='high',x=0,name='tower'):
        if pulley not in ('low','mid','high'): raise ValueError('pulley must be low, mid or high')
        if not 1<=selected<=plates: raise ValueError('selected plates must be 1..plates')
        before=set(bpy.context.scene.objects)
        super().__init__(y_stack,y_front,top,plates,selected)
        self.pulley=pulley; self.x=x; self.name=name
        old_z=self.front_c.z
        self.front_c.z={'high':top-.07,'mid':1.35,'low':.22}[pulley]
        self.objects=list(set(bpy.context.scene.objects)-before)
        for o in self.objects:
            if o.name.startswith('pulley_front'): o.location.z+=self.front_c.z-old_z
        if pulley!='high':
            self.objects.append(beam(name+'_front_rail',(0,y_front,.10),(0,y_front,top),.055))
        # All vertices of cable are world space; fixed objects/stack use X translation.
        for o in self.objects:
            if not o.parent and o!=self.cable: o.location.x+=x
            o.name=name+'_'+o.name
        self.rear_c.x=x; self.front_c.x=x
        self.contacts={'pulley':list(self.front_c),'stack_base':self.stack_base,'max_lift':top-self.stack_top0-.18}

    def path(self,handle,lift):
        handle=Vector(handle); rear=self.rear_c; front=self.front_c; r=self.r
        top=self.stack_top0+.055+lift
        if self.pulley=='high':
            d=Vector((0,handle.y-front.y,handle.z-front.z))
            base=math.atan2(d.z,d.y); a=base+math.acos(min(1,r/max(d.length,r)))
            return [Vector((self.x,self.y_stack,top)),Vector((self.x,self.y_stack,rear.z))]+self._arc(rear,math.pi,math.pi/2,6)[1:]+self._arc(front,math.pi/2,a,8)+[handle]
        # Run over top pulley and down the outside of the front adjustable pulley.
        d=Vector((0,handle.y-front.y,handle.z-front.z))
        base=math.atan2(d.z,d.y)
        exit_angle=base-math.acos(min(1,r/max(d.length,r)))
        return [Vector((self.x,self.y_stack,top)),Vector((self.x,self.y_stack,rear.z))]+self._arc(rear,math.pi,math.pi/2,6)[1:]+[Vector((self.x,front.y-r,rear.z+r))]+self._arc(front,math.pi,exit_angle,10)+[handle]

    def update(self,handle,frame):
        lift=super().update(Vector(handle),frame)
        if lift>self.contacts['max_lift']:
            raise ValueError(f'{self.name}: stack travel {lift:.3f} exceeds guide clearance')
        return lift


class DualCable:
    def __init__(self,width=2.8,pulley='high',y_stack=-.8,y_front=-.45,top=2.3):
        self.left=CableTower(x=-width/2,pulley=pulley,y_stack=y_stack,y_front=y_front,top=top,name='left_tower')
        self.right=CableTower(x=width/2,pulley=pulley,y_stack=y_stack,y_front=y_front,top=top,name='right_tower')
        self.crossbar=beam('crossover_top',(-width/2,y_stack,top+.13),(width/2,y_stack,top+.13),.08)
    def calibrate(self,left,right):
        self.left.calibrate(Vector(left)); self.right.calibrate(Vector(right))
    def update(self,left,right,frame):
        return self.left.update(Vector(left),frame),self.right.update(Vector(right),frame)
