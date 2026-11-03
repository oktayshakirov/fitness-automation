"""Restart an interrupted MVP render where it stopped; stop one on purpose.

    core/resume_mvp.py          resume if review/run_status.json says "running" but its
                                runner process is gone (shutdown, crash, killed)
    core/resume_mvp.py --stop   stop the running batch and mark it "stopped" (not resumed)

Finished deliveries are kept in dist/ and batch.py reuses every one that still matches
the pipeline and spec digests, so a resumed run only renders what is left (at most the
one delivery that was in progress is redone). The runner is wrapped in caffeinate so
the Mac does not idle-sleep mid-batch. Run it by hand after a shutdown or crash."""
import argparse, datetime, json, os, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / 'review' / 'run_status.json'


def log(message):
    print(f"{datetime.datetime.now().isoformat(timespec='seconds')} {message}", flush=True)


def runner_alive(pid):
    out = subprocess.run(['ps', '-p', str(pid), '-o', 'command='], capture_output=True, text=True).stdout
    return 'run_mvp.py' in out


def stop(status):
    if status.get('pid') and runner_alive(status['pid']):
        os.kill(status['pid'], 15)
    # the runner's children: the batch and its Blender builds/renders
    for pattern in (f'{ROOT}/core/batch.py', 'core/batch.py', f'{ROOT}/build.py', f'{ROOT}/core/render_saved.py'):
        subprocess.run(['pkill', '-f', pattern])
    status.update(state='stopped', message='Stopped by hand; run core/run_mvp.py to start again',
                  updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    STATUS.write_text(json.dumps(status, indent=2) + '\n')
    log('stopped')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--stop', action='store_true', help='stop the batch; it will not be resumed')
    args = parser.parse_args()
    status = json.loads(STATUS.read_text()) if STATUS.exists() else {}
    if args.stop:
        return stop(status)
    if status.get('state') != 'running':
        return                      # finished, failed on QA, or stopped by hand
    if runner_alive(status.get('pid', 0)):
        return
    log(f"runner {status.get('pid')} is gone at: {status.get('message')}; resuming")
    with (ROOT / 'review' / 'run_mvp.out').open('a') as out:
        subprocess.Popen(['/usr/bin/caffeinate', '-i', '-s', sys.executable, str(ROOT / 'core/run_mvp.py')],
                         cwd=ROOT, stdout=out, stderr=subprocess.STDOUT, start_new_session=True)


if __name__ == '__main__':
    main()
