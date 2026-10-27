"""Render a saved, fully QA-validated model scene without repeating its pose build."""
import os,sys,subprocess,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
try:import bpy
except ImportError:
    env=dict(os.environ,BLENDER_USER_RESOURCES=str(ROOT/'.blender-profile'))
    env['PATH']=str(Path(sys.executable).parent)+os.pathsep+env.get('PATH','')
    cmd=['/Applications/Blender.app/Contents/MacOS/Blender','-b','--python-exit-code','1','--python',__file__,'--',*sys.argv[1:]]
    sys.exit(subprocess.run(cmd,env=env).returncode)
from core.delivery import current_qa,read
from core.render import render_views,contact_sheet,export_delivery
args=sys.argv[sys.argv.index('--')+1:];eid,model=args
q=current_qa(eid,model=model);prefix=f'{eid}_{model}'
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'review'/(prefix+'.blend')))
assert bpy.context.scene['fitness_model']==model
spec=read(ROOT/'motion/specs'/(eid+'.json'));views=spec['views']
names=[v['name'] if isinstance(v,dict) else v for v in views]
cams=[bpy.context.scene.objects[name] for name in names]
count=sum(spec['tempo'].values());scene=bpy.context.scene
assert scene.frame_end==count and not scene.render.film_transparent
if os.environ.get('QUICK'):raise ValueError('Cannot export a partial frame set')
dirs=render_views(scene,cams,prefix,1,count,res=(720,900))
frames=spec.get('sheet') or [1,1+count//4,1+count//2,1+3*count//4,count]
contact_sheet(dirs,frames,str(ROOT/'review'/(prefix+'_sheet.png')))
export_delivery(eid,dirs,views,model=model)
for folder in dirs:shutil.rmtree(folder)
print('EXPORTED',prefix)
