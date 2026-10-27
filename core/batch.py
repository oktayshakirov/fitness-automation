"""Resume-safe per-model production renders. Never grants human approval."""
import argparse, json, os, shutil, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.delivery import read,current_asset,current_qa,rebuild_manifest

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ids',nargs='*')
    parser.add_argument('--models',nargs='+',choices=('male','female'),default=['male','female'])
    args=parser.parse_args()
    # Blender subprocesses must use the same Python/Pillow runtime as the runner.
    os.environ['PATH']=str(Path(sys.executable).parent)+os.pathsep+os.environ.get('PATH','')
    ids=args.ids or sorted(p.stem for p in (ROOT/'catalog').glob('*.json'))
    if any(not (ROOT/'catalog'/(eid+'.json')).is_file() for eid in ids):parser.error('Unknown exercise')
    logs=ROOT/'review/batch';logs.mkdir(exist_ok=True);report=[]
    jobs=[(eid,model) for eid in ids for model in args.models]
    for i,(eid,model) in enumerate(jobs):
        prefix=f'{eid}_{model}';asset=ROOT/'dist'/eid/model/'asset.json';started=time.time();reused=False
        try:
            if asset.exists():
                try:
                    current_asset(eid,read(asset));reused=True
                except (OSError,ValueError,KeyError):
                    pass  # A stale export needs rebuilding, not a failed job.

            if not reused:
                if shutil.disk_usage(ROOT).free<8*1024**3:raise ValueError('Less than 8 GiB free; render stopped')
                try:
                    current_qa(eid,model=model)
                    cmd=[sys.executable,str(ROOT/'core/render_saved.py'),eid,model]
                except (OSError,ValueError,KeyError):
                    cmd=[sys.executable,str(ROOT/'build.py'),eid,'--model',model,'--delivery']
                with (logs/(prefix+'.log')).open('w') as log:
                    subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
                current_asset(eid,read(asset))
            # Encoding succeeded and files validated; discard interrupted-run leftovers.
            for view in read(asset)['views']:
                shutil.rmtree(ROOT/'review'/f'{prefix}_{view}',ignore_errors=True)
            (ROOT/'review'/(prefix+'.blend1')).unlink(missing_ok=True)
            result=dict(id=eid,model=model,status='PASS',reused=reused,seconds=round(time.time()-started))
        except (OSError,ValueError,KeyError,subprocess.CalledProcessError) as exc:
            result=dict(id=eid,model=model,status='FAIL',error=str(exc),seconds=round(time.time()-started))
            # Partial frames cannot ship; retry starts from the scene.
            for folder in (ROOT/'review').glob(prefix+'_*'):
                if folder.is_dir():shutil.rmtree(folder)
        report.append(result)
        (logs/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(f'{i+1}/{len(jobs)} {prefix}: {result["status"]} ({result["seconds"]}s)',flush=True)
    rebuild_manifest()
    return int(any(r['status']=='FAIL' for r in report))
if __name__=='__main__':sys.exit(main())
