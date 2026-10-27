"""Full-frame QA-only repair preflight; no video rendering or human approvals."""
import argparse,concurrent.futures,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.delivery import current_qa,pipeline_digest

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs',type=int,choices=(1,2),default=2)
    parser.add_argument('--ids',nargs='*')
    args=parser.parse_args()
    items=json.loads((ROOT/'review/production_failures.json').read_text())
    if args.ids:items=[i for i in items if i['id'] in args.ids]
    env=dict(os.environ);env['PATH']=str(Path(sys.executable).parent)+os.pathsep+env.get('PATH','')
    signature=pipeline_digest();report=[]
    def check(item):
        eid,model=item['id'],item['model'];start=time.monotonic();prefix=f'{eid}_{model}'
        try:
            try:current_qa(eid,model=model)
            except (OSError,ValueError,KeyError):
                with (ROOT/'review'/f'fix_{prefix}.log').open('w') as log:
                    subprocess.run([sys.executable,'build.py',eid,'--model',model,'--look-preview','--no-render'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
                current_qa(eid,model=model)
            return dict(id=eid,model=model,status='PASS',seconds=round(time.monotonic()-start,1))
        except (OSError,ValueError,KeyError,subprocess.CalledProcessError) as exc:
            return dict(id=eid,model=model,status='FAIL',error=str(exc),seconds=round(time.monotonic()-start,1))
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for result in pool.map(check,items):
            if pipeline_digest()!=signature:raise RuntimeError('Sources changed during preflight; rerun to validate current scenes')
            report.append(result)
            (ROOT/'review/fix_preflight.json').write_text(json.dumps(report,indent=2)+'\n')
            print(result['id'],result['model'],result['status'],result['seconds'],flush=True)
    return int(any(i['status']=='FAIL' for i in report))
if __name__=='__main__':sys.exit(main())
