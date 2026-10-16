"""Validate MVP catalog contract without importing Blender."""
import ast, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
tree=ast.parse((ROOT/'core/look.py').read_text())
groups=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='GROUPS' for t in n.targets))
sources={e['id']:e for e in json.loads((ROOT/'catalog/sources/mvp-source-records.json').read_text())}
files=sorted((ROOT/'catalog').glob('*.json'))
assert len(files)==30, len(files)
for p in files:
 e=json.loads(p.read_text()); assert e['id']==p.stem
 assert e['reviewed'] in (True,False) and isinstance(e['reviewed'],bool)
 for k in ('name','breathing','source','level'): assert isinstance(e[k],str) and e[k].strip(), (p,k)
 for k in ('steps','cues','mistakes'): assert len(e[k])>=2 and all(isinstance(v,str) and v.strip() for v in e[k]),(p,k)
 assert isinstance(e['equipment'],list) and len(set(e['equipment']))==len(e['equipment'])
 assert e['primary'] and not set(e['primary'])&set(e['secondary'])
 assert set(e['primary']+e['secondary'])<=set(groups)
 s=sources[e['source'].split(':',1)[1]]
 assert e['primary']==s['primaryMuscles'] and e['secondary']==s['secondaryMuscles'],p
 assert (ROOT/'motion/specs'/p.name).exists(),p
print(f'PASS: {len(files)} catalog records, source fidelity, muscle groups and motion IDs')
