"""App media export and manifest, usable without Blender. No failed QA in dist/."""
import json,hashlib,subprocess,os,re,tempfile,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
FFMPEG='/opt/homebrew/bin/ffmpeg'; FFPROBE='/opt/homebrew/bin/ffprobe'
VIDEO_BUDGET=400_000; POSTER_BUDGET=40_000

def read(path):return json.loads(Path(path).read_text())
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def spec_digest(eid):
    obj=[]
    for d,flag in [('catalog','reviewed'),('motion/specs','approved')]:
        data=read(ROOT/d/(eid+'.json'));data.pop(flag,None);obj.append(data)
    return hashlib.sha256(json.dumps(obj,sort_keys=True).encode()).hexdigest()
def pipeline_digest():
    files=[ROOT/'build.py', ROOT/'qa/check.py', ROOT/'qa/check_clothes.py', ROOT/'qa/model.py']
    files += [ROOT/'core'/n for n in ('face_details.py','accessories.py','body.py','clothes.py','hair.py','solver.py','look.py','studio.py','render.py','render_saved.py')]
    for folder in ('motion','equipment'):
        files += [p for p in sorted((ROOT/folder).rglob('*.py')) if p.name!='preview.py']
    files += sorted((ROOT/'assets/maps').rglob('*.png'))
    files += sorted(p for p in (ROOT/'assets/hair').rglob('*') if p.is_file() and p.name != 'sources.json')
    h=hashlib.sha256()
    for p in files:
        h.update(str(p.relative_to(ROOT)).encode());h.update(p.read_bytes())
    return h.hexdigest()
def asset_folder(eid,model=None):
    if model not in (None,'male','female'):raise ValueError('Invalid model')
    return ROOT/'dist'/eid/model if model else ROOT/'dist'/eid

def current_qa(eid,path=None,model=None):
    if model not in (None,'male','female'):raise ValueError('Invalid model')
    prefix=f'{eid}_{model}' if model else eid
    q=read(path or ROOT/'review'/(prefix+'_qa.json'))
    if model and q.get('model')!=model:raise ValueError(eid+': wrong QA model')
    if q.get('id')!=eid or q.get('pass') is not True:raise ValueError(eid+': QA missing or failed')
    if q.get('spec_sha256')!=spec_digest(eid):raise ValueError(eid+': QA spec is stale')
    if q.get('pipeline_sha256')!=pipeline_digest():raise ValueError(eid+': QA pipeline is stale')
    if q.get('blend_sha256')!=digest(ROOT/'review'/(prefix+'.blend')):raise ValueError(eid+': QA blend is stale')
    if q.get('clothes_required'):
        clothing=read(ROOT/'review'/(prefix+'_clothes_qa.json'))
        if clothing.get('pass') is not True or clothing.get('complete') is not True:
            raise ValueError(eid+': clothing QA missing, incomplete or failed')
        for key in ('blend_sha256','pipeline_sha256','spec_sha256','model'):
            if clothing.get(key)!=q.get(key):raise ValueError(eid+': clothing QA is stale')
    return q


def current_asset(eid, entry):
    """Require matching QA and complete, unmodified delivered media."""
    q = current_qa(eid, model=entry.get("model"))
    if entry.get('model') and q.get('model')!=entry['model']:raise ValueError(eid+': wrong delivery model')
    if entry.get('spec_sha256') != spec_digest(eid):
        raise ValueError(eid + ': delivery spec is stale')
    if entry.get('pipeline_sha256') != q.get('pipeline_sha256'):
        raise ValueError(eid + ': delivery pipeline is stale')
    if entry.get('qa', {}).get('blend_sha256') != q.get('blend_sha256'):
        raise ValueError(eid + ': delivery scene is stale')
    base = asset_folder(eid,entry.get('model'))
    paths = [p for view in entry['files'].values() for p in view.values()]
    paths.append(entry['thumb'])
    for relative in paths:
        path = (ROOT / 'dist' / relative).resolve()
        if not path.is_relative_to(base.resolve()) or not path.is_file():
            raise ValueError(eid + ': delivery file missing or invalid')
        metadata = entry.get('media', {}).get(path.name)
        if metadata and (path.stat().st_size != metadata['bytes'] or digest(path) != metadata['sha256']):
            raise ValueError(eid + ': delivery file changed')
    return entry

def run(args):subprocess.run(args,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
def probe(path):return read_probe(path)
def read_probe(path):
    return json.loads(subprocess.check_output([FFPROBE,'-v','error','-show_streams','-show_format','-of','json',str(path)]))
def encode_frames(folder,path,codec,count):
    for crf in (25,28,31,34):
        opts=['-c:v',codec,'-preset','medium','-crf',str(crf)]
        if codec=='libx265':opts+=['-tag:v','hvc1','-x265-params','log-level=error:pools=2']
        run([FFMPEG,'-hide_banner','-loglevel','error','-y','-framerate','30','-start_number','1','-i',str(folder/'%04d.png'),'-frames:v',str(count),'-an','-pix_fmt','yuv420p',*opts,'-movflags','+faststart',str(path)])
        if path.stat().st_size<=VIDEO_BUDGET:break
    if path.stat().st_size>VIDEO_BUDGET:raise ValueError(f'{path.name} exceeds 400 KB at quality floor')
    data=probe(path);v=[s for s in data['streams'] if s['codec_type']=='video']
    assert len(data['streams'])==1 and len(v)==1
    assert (v[0]['width'],v[0]['height'])==(720,900)
    assert v[0]['r_frame_rate']=='30/1' and int(v[0]['nb_frames'])==count
    return {'bytes':path.stat().st_size,'sha256':digest(path),'codec':v[0]['codec_name'],'crf':crf}

def export_delivery(eid,dirs,views,qa_path=None,model=None):
    from PIL import Image,ImageOps
    if not re.fullmatch(r'[a-z0-9_]+',eid):raise ValueError('bad id')
    q=current_qa(eid,qa_path,model); cat=read(ROOT/'catalog'/(eid+'.json'));motion=read(ROOT/'motion/specs'/(eid+'.json'))
    names=[v['name'] if isinstance(v,dict) else v for v in views]
    if len(names)!=len(dirs) or not names:raise ValueError('views and directories must correspond')
    all_names=[v['name'] if isinstance(v,dict) else v for v in motion['views']]
    if names!=all_names:raise ValueError('delivery requires every declared view in order')
    count=sum(motion['tempo'].values()); staged=Path(tempfile.mkdtemp(prefix=eid+'-',dir=ROOT/'review'))
    relative=f'{eid}/{model}' if model else eid
    files={};metadata={}
    try:
        for view,directory in zip(names,dirs):
            if not re.fullmatch(r'[A-Za-z0-9_]+',view):raise ValueError('bad view name')
            folder=Path(directory)
            expected=[folder/f'{f:04d}.png' for f in range(1,count+1)]
            if any(not p.is_file() for p in expected):raise ValueError(eid+': incomplete frame set')
            first=Image.open(expected[0]);last=Image.open(expected[-1])
            if first.size!=(720,900):raise ValueError('render at 720x900; do not crop/upscale portrait renders')
            # Loop closure in final pixels as well as pose-space QA.
            from PIL import ImageChops,ImageStat
            delta=ImageStat.Stat(ImageChops.difference(first.convert('RGB'),last.convert('RGB')))
            if max(delta.mean)>1:raise ValueError(eid+': rendered first/last frame mismatch')
            tag=f'{model}_' if model else ''
            paths={'h264':f'{tag}loop_{view}.mp4','poster':f'{tag}poster_{view}.webp'}
            for kind,codec in [('h264','libx264')]:metadata[paths[kind]]=encode_frames(folder,staged/paths[kind],codec,count)
            for quality in (86,78,68):
                first.convert('RGB').save(staged/paths['poster'],'WEBP',quality=quality,method=6)
                if (staged/paths['poster']).stat().st_size<=POSTER_BUDGET:break
            if (staged/paths['poster']).stat().st_size>POSTER_BUDGET:raise ValueError('poster over budget')
            metadata[paths['poster']]={'bytes':(staged/paths['poster']).stat().st_size,'sha256':digest(staged/paths['poster'])}
            files[view]={k:f'{relative}/{v}' for k,v in paths.items()}
        poster=Image.open(staged/((f'{model}_' if model else '')+f'poster_{names[0]}.webp'))
        ImageOps.pad(poster,(320,320),color='#FFFFFF').save(staged/'thumb.webp','WEBP',quality=82,method=6)
        entry={k:cat[k] for k in ('id','name','primary','secondary','equipment')}
        entry.update(views=names,files=files,thumb=f'{relative}/thumb.webp',duration=count/30,approved=bool(motion.get('approved') and cat.get('reviewed')),
                     qa=q,media=metadata,spec_sha256=spec_digest(eid),pipeline_sha256=pipeline_digest())
        if model:entry['model']=model
        from core.approvals import is_approved
        entry['approved']=is_approved(eid,entry,ROOT)
        (staged/'asset.json').write_text(json.dumps(entry,indent=2)+'\n')
        destination=asset_folder(eid,model);destination.parent.mkdir(exist_ok=True)
        # Replace this exercise only after all outputs pass validation.
        old=destination.with_name('.'+destination.name+'-old')
        if old.exists():shutil.rmtree(old)
        if destination.exists():destination.rename(old)
        staged.rename(destination)
        if old.exists():shutil.rmtree(old)
        rebuild_manifest()
        return entry
    finally:
        if staged.exists():shutil.rmtree(staged)

def rebuild_manifest():
    import fcntl
    dist=ROOT/'dist';dist.mkdir(exist_ok=True)
    with (dist/'.manifest.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        return _rebuild_manifest()

def _rebuild_manifest():
    from core.package_notices import package_notices
    package_notices()
    entries=[];dist=ROOT/'dist';dist.mkdir(exist_ok=True)
    for p in sorted([*dist.glob('*/asset.json'),*dist.glob('*/*/asset.json')]):
        e=read(p);eid=e['id']
        if e.get('spec_sha256')!=spec_digest(eid) or e.get('pipeline_sha256')!=pipeline_digest():continue
        if e.get('qa',{}).get('pass') is not True:continue
        try: current_asset(eid,e)
        except (OSError,ValueError,KeyError): continue
        motion=read(ROOT/'motion/specs'/(eid+'.json'));cat=read(ROOT/'catalog'/(eid+'.json'))
        from core.approvals import is_approved
        e['approved']=is_approved(eid,e,ROOT)
        entries.append(e)
    tmp=dist/'manifest.json.tmp';tmp.write_text(json.dumps(entries,indent=2)+'\n');tmp.replace(dist/'manifest.json')
    return entries

if __name__=='__main__':
    import sys
    if len(sys.argv)==2 and sys.argv[1]=='manifest':rebuild_manifest()
    else:
        eid=sys.argv[1];payload=read(sys.argv[2]);export_delivery(eid,payload['dirs'],payload['views'],model=payload.get('model'))
