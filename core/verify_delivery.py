"""Audit both-model H.264 production exports without granting approval."""
import json,sys
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.delivery import read,digest,current_asset,probe
from core.approvals import is_approved

def verify(ids=None):
    ids=set(ids or (p.stem for p in (ROOT/'catalog').glob('*.json')))
    entries=[e for e in read(ROOT/'dist/manifest.json') if e['id'] in ids and e.get('model') in ('male','female')]
    expected={(eid,model) for eid in ids for model in ('male','female')}
    assert len(entries)==len(expected) and {(e['id'],e['model']) for e in entries}==expected,'Missing exercise/model deliveries'
    videos=posters=total=largest_video=largest_poster=0
    for e in entries:
        eid=e['id'];model=e['model'];current_asset(eid,e)
        assert e['approved']==is_approved(eid,e,ROOT)
        motion=read(ROOT/'motion/specs'/(eid+'.json'))
        views=[v['name'] if isinstance(v,dict) else v for v in motion['views']]
        assert e['views']==views and set(e['files'])==set(views)
        count=sum(motion['tempo'].values());assert abs(e['duration']-count/30)<1e-6
        for view in views:
            assert set(e['files'][view])=={'h264','poster'},'App exports must be H.264 only'
            for kind,relative in e['files'][view].items():
                path=ROOT/'dist'/relative;info=e['media'][path.name];size=path.stat().st_size
                assert digest(path)==info['sha256'] and size==info['bytes']
                total+=size
                if kind=='poster':
                    assert size<=40_000 and Image.open(path).size==(720,900)
                    posters+=1;largest_poster=max(largest_poster,size)
                else:
                    data=probe(path);assert len(data['streams'])==1
                    v=data['streams'][0]
                    assert v['codec_name']=='h264' and v['pix_fmt']=='yuv420p'
                    assert (v['width'],v['height'])==(720,900)
                    assert v['r_frame_rate']=='30/1' and int(v['nb_frames'])==count
                    assert abs(float(data['format']['duration'])-e['duration'])<.04 and size<=400_000
                    videos+=1;largest_video=max(largest_video,size)
            assert not list((ROOT/'review'/f'{eid}_{model}_{view}').glob('*.png')),'Frames not cleaned'
        assert Image.open(ROOT/'dist'/e['thumb']).size==(320,320)
    assert (ROOT/'dist/ATTRIBUTION.md').is_file()
    return dict(exercises=len(ids),model_deliveries=len(entries),videos=videos,posters=posters,thumbnails=len(entries),largest_video_bytes=largest_video,largest_poster_bytes=largest_poster,video_and_poster_bytes=total,approved=sum(e['approved'] for e in entries))
if __name__=='__main__':
    result=verify(sys.argv[1:] or None)
    (ROOT/'review/delivery_audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
