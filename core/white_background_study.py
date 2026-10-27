"""Render one unpublished H.264 loop from the current, QA-passing female squat."""
import bpy,json,sys,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.delivery import pipeline_digest,spec_digest,digest,encode_frames
from core.render import render_views
name='bodyweight_squat_female';eid='bodyweight_squat'
blend=ROOT/'review'/(name+'.blend')
for suffix in ('qa','clothes_qa'):
 q=json.loads((ROOT/'review'/(name+'_'+suffix+'.json')).read_text())
 assert q['pass'] and q['pipeline_sha256']==pipeline_digest()
 assert q['blend_sha256']==digest(blend) and q['spec_sha256']==spec_digest(eid)
 if suffix=='clothes_qa':assert q['complete']
bpy.ops.wm.open_mainfile(filepath=str(blend))
s=bpy.context.scene
folders=render_views(s,[bpy.data.objects['side']],'look_v21/white_video',1,s.frame_end,res=(720,900))
try:
 path=ROOT/'review/look_v21/female_squat_white.mp4'
 metadata=encode_frames(Path(folders[0]),path,'libx264',s.frame_end)
 (path.with_suffix('.json')).write_text(json.dumps(metadata,indent=2)+'\n')
finally:
 for folder in folders:shutil.rmtree(folder)
