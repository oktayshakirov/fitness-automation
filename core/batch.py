"""Resume-safe MVP batch. Build/QA every catalog; failures never enter manifest."""
import subprocess,sys,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.delivery import pipeline_digest,spec_digest,read,rebuild_manifest
args=sys.argv[1:];quick='--quick' in args;pose='--pose-only' in args
chosen=[s for s in args if not s.startswith('--')]
ids=chosen or [p.stem for p in sorted((ROOT/'catalog').glob('*.json'))]
logs=ROOT/'review/batch';logs.mkdir(exist_ok=True);report=[]
for i,eid in enumerate(ids):
    asset=ROOT/'dist'/eid/'asset.json'
    if not quick and not pose and asset.exists():
        e=read(asset)
        if e.get('pipeline_sha256')==pipeline_digest() and e.get('spec_sha256')==spec_digest(eid):
            print(f'{i+1}/{len(ids)} {eid}: current, skipped',flush=True);continue
    cmd=[sys.executable,str(ROOT/'build.py'),eid]+(['--no-render'] if pose else ['--quick','--frames','1,30,54,72'] if quick else ['--delivery'])
    started=time.time()
    with (logs/(eid+'.log')).open('w') as log:
        r=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        if (pose or quick) and r.returncode==0:r=subprocess.run([sys.executable,str(ROOT/'qa/check.py'),eid],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    # Blender can return 0 after a script exception: inspect expected QA freshness.
    qpath=ROOT/'review'/(eid+'_qa.json');q=read(qpath) if qpath.exists() else {}
    valid=q.get('pass') is True and q.get('spec_sha256')==spec_digest(eid) and q.get('pipeline_sha256')==pipeline_digest()
    if not quick and not pose:valid=valid and asset.exists() and read(asset).get('pipeline_sha256')==pipeline_digest()
    status='PASS' if r.returncode==0 and valid else 'FAIL'
    entry={'id':eid,'status':status,'seconds':round(time.time()-started),'log':str(logs/(eid+'.log'))};report.append(entry)
    (logs/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'{i+1}/{len(ids)} {eid}: {status} ({entry["seconds"]}s)',flush=True)
if not quick and not pose:rebuild_manifest()
sys.exit(1 if any(e['status']=='FAIL' for e in report) else 0)
