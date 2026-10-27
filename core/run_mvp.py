"""Unattended, resumable MVP render + audit; progress appears on the review page."""
import argparse, datetime, fcntl, json, os, subprocess, sys, traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REVIEW=ROOT/'review';REVIEW.mkdir(exist_ok=True)

def status(state,message,**extra):
    data=dict(state=state,message=message,pid=os.getpid(),updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),**extra)
    temp=REVIEW/'run_status.json.tmp';temp.write_text(json.dumps(data,indent=2)+'\n');temp.replace(REVIEW/'run_status.json')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first", nargs="*", default=[], help="Render these catalog IDs before the remaining MVP exercises")
    args=parser.parse_args()
    all_ids=sorted(p.stem for p in (ROOT/"catalog").glob("*.json"))
    if any(e not in all_ids for e in args.first):parser.error("Unknown exercise in --first")
    ordered=list(dict.fromkeys(args.first+all_ids))
    with (REVIEW/'.mvp.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit('An MVP runner is already active')
        try:
            status('running',f'Preparing {len(ordered)} exercises × 2 models')
            with (REVIEW/'mvp_batch.log').open('w') as log:
                for attempt in (1,2):
                    p=subprocess.Popen([sys.executable,'core/batch.py',*ordered],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
                    for line in p.stdout:
                        log.write(line);log.flush();status('running',line.strip(),attempt=attempt)
                    if p.wait()==0:break
                    if attempt==2:raise RuntimeError('Some exercises failed after retry; see review/batch/report.json')
                status('running','Auditing codecs, dimensions, checksums, QA and file sizes')
                subprocess.run([sys.executable,'core/verify_delivery.py'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
            audit=json.loads((REVIEW/'delivery_audit.json').read_text())
            status('complete',f"{audit['model_deliveries']} model deliveries validated; awaiting human approval",audit=audit)
        except Exception as exc:
            status('failed',str(exc));traceback.print_exc();return 1
    return 0

if __name__=='__main__':sys.exit(main())
