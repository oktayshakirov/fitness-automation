"""Human approval of still asset sets: body views and onboarding heroes per model, one
shared equipment icon set (model "all").

  python3 core/stills.py status
  python3 core/stills.py approve bodymap male "looked at front/back, masks and taps"
  python3 core/stills.py approve icons all "looked at all eight on the chip colour"

An approval is bound to the sha256 of every file in the set's folder; any change voids it.
Only a person runs `approve`, after looking at the files; publish.py never approves.
"""
import datetime,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SETS={'bodymap':lambda model:ROOT/'bodymap'/model,
      'heroes':lambda model:ROOT/'heroes'/model,
      'icons':lambda model:ROOT/'icons/set'}
SHARED={'icons'}          # one set for both models
MODELS=('male','female')

def models(kind):return ('all',) if kind in SHARED else MODELS

def fingerprint(folder):
    files=sorted(p for p in Path(folder).rglob('*') if p.is_file())
    if not files:raise FileNotFoundError(f'{folder} is empty')
    h=hashlib.sha256()
    for p in files:h.update(str(p.relative_to(folder)).encode()+b'\0'+hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()

def record_path(kind,model):return ROOT/'approvals'/f'{kind}_{model}.json'

def is_approved(kind,model):
    try:
        record=json.loads(record_path(kind,model).read_text())
        return record.get('approved') is True and record.get('fingerprint')==fingerprint(SETS[kind](model))
    except (OSError,ValueError,KeyError):
        return False

def approve(kind,model,note):
    if kind not in SETS or model not in models(kind) or not note.strip():raise SystemExit('usage: approve <set> <model|all> "<note>"')
    record={'kind':kind,'model':model,'approved':True,'note':note,'fingerprint':fingerprint(SETS[kind](model)),
            'at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    record_path(kind,model).write_text(json.dumps(record,indent=2)+'\n')
    with (ROOT/'approvals/history.jsonl').open('a') as stream:stream.write(json.dumps(record)+'\n')
    return record

if __name__=='__main__':
    a=sys.argv[1:]
    if a[:1]==['approve'] and len(a)==4:print(approve(*a[1:]))
    elif a==['status']:
        for kind in SETS:
            for model in models(kind):print(kind,model,'approved' if is_approved(kind,model) else 'not approved')
    else:raise SystemExit(__doc__)
