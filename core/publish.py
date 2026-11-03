"""Publish the app content envelope from approved, current deliveries. No approvals here.

  python3 core/publish.py v0.2.0 [--allow-partial]

Writes an immutable releases/<version>/ (content.json, H.264 loops, posters, attribution,
and the approved still sets of core/stills.py: body views from bodymap/<model>/, heroes
from heroes/<model>/, equipment icons from icons/set/ as the additive `equipmentIcons`),
verifies every file against content.json, then switches releases/current.json last.
Contract: fitness-app/src/content/types.ts (schemaVersion 1). Uploading to static hosting
is a separate, user-approved step: upload the release folder first, current.json last.
"""
import argparse,datetime,hashlib,json,os,re,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.delivery import FFPROBE,current_asset,digest,read,rebuild_manifest
from core.approvals import is_approved
from core import stills

SCHEMA=1;MIN_APP_SCHEMA=1
MUSCLES=('chest','shoulders','biceps','triceps','forearms','abs','quadriceps','hamstrings','glutes',
         'calves','lats','traps','middle_back','lower_back','adductors','abductors','neck')
MODELS=('male','female')

def muscle(name):
    m={'abdominals':'abs'}.get(name,name.replace(' ','_'))
    if m not in MUSCLES:raise ValueError('unknown muscle '+name)
    return m

def size(path):
    data=json.loads(subprocess.check_output([FFPROBE,'-v','error','-select_streams','v:0','-show_entries',
                                             'stream=width,height','-of','json',str(path)]))['streams'][0]
    return data['width'],data['height']

def asset(release,relative,w=None,h=None):
    path=release/relative
    if w is None:w,h=size(path)
    return {'path':relative,'width':w,'height':h,'bytes':path.stat().st_size,'sha256':digest(path)}

def approved_entries(allow_partial=False):
    """Current and approved model deliveries; every catalog exercise needs both unless partial."""
    ids=sorted(p.stem for p in (ROOT/'catalog').glob('*.json'))
    found={}
    for e in rebuild_manifest():
        if e.get('model') not in MODELS:continue
        current_asset(e['id'],e)
        if e.get('approved') and is_approved(e['id'],e,ROOT):found[e['id'],e['model']]=e
    missing=[f'{i}_{m}' for i in ids for m in MODELS if (i,m) not in found]
    if missing and not allow_partial:raise SystemExit('Not approved or not current: '+', '.join(missing))
    return ids,found

def copy_set(staged,kind,model,relative):
    """Copy one approved still set into the release; the copy must match what was approved."""
    source=stills.SETS[kind](model);target=staged/relative;shutil.copytree(source,target)
    if stills.fingerprint(target)!=stills.fingerprint(source):raise ValueError(f'{kind} {model} changed while copying')
    return target

def bodymap(staged,model):
    """One model's approved body views as the app's BodyView records (masks keyed by muscle id)."""
    target=copy_set(staged,'bodymap',model,f'bodymap/{model}');meta=read(target/'bodymap.json');w,h=meta['width'],meta['height']
    rel=lambda name:f'bodymap/{model}/{name}'
    return {view:{'base':asset(staged,rel(f'body_{view}.webp'),w,h),
                  'masks':{m:asset(staged,rel(f'mask_{view}_{m}.png'),w,h) for m in MUSCLES if (target/f'mask_{view}_{m}.png').is_file()},
                  'hitRegions':asset(staged,rel(f'hits_{view}.svg'),w,h)} for view in meta['views']}

def hero(staged,model):
    meta=read(copy_set(staged,'heroes',model,f'heroes/{model}')/'hero.json')
    return asset(staged,f'heroes/{model}/hero.webp',meta['width'],meta['height'])

def equipment_icons(staged):
    """{category: {icon, equipment}}: the chip icon and the catalog equipment ids it filters."""
    meta=read(copy_set(staged,'icons','all','icons')/'icons.json');n=meta['size']
    return {cat:{'icon':asset(staged,f'icons/{cat}.webp',n,n),'equipment':ids} for cat,ids in meta['categories'].items()}

def build(version,allow_partial=False,out=None):
    if not re.fullmatch(r'v\d+\.\d+\.\d+',version):raise SystemExit('version must look like v0.2.0')
    out=Path(out or ROOT/'releases');final=out/version
    if final.exists():raise SystemExit(f'{final} exists; releases are immutable')
    ids,found=approved_entries(allow_partial)
    staged=out/f'.staging-{version}';shutil.rmtree(staged,ignore_errors=True);staged.mkdir(parents=True)
    try:
        exercises=[]
        for eid in ids:
            models={m:found[eid,m] for m in MODELS if (eid,m) in found}
            if not models:continue
            cat=read(ROOT/'catalog'/(eid+'.json'));media={}
            for model,e in models.items():
                media[model]={}
                for view in e['views']:
                    files=e['files'][view];pair={}
                    for kind,key in (('h264','video'),('poster','poster')):
                        relative=files[kind];target=staged/relative;target.parent.mkdir(parents=True,exist_ok=True)
                        shutil.copy2(ROOT/'dist'/relative,target)
                        pair[key]=asset(staged,relative)
                        if pair[key]['sha256']!=e['media'][Path(relative).name]['sha256']:raise ValueError(relative+' changed while copying')
                    media[model][view]=pair
            exercises.append({'id':eid,'name':cat['name'],'primary':[muscle(m) for m in cat['primary']],
                              'secondary':[muscle(m) for m in cat['secondary']],'equipment':cat['equipment'],
                              'steps':cat['steps'],'cues':cat['cues'],'mistakes':cat['mistakes'],
                              'breathing':cat['breathing'],'source':cat['source'],'media':media})
        attribution=(ROOT/'dist/ATTRIBUTION.md').read_text()
        (staged/'ATTRIBUTION.md').write_text(attribution)
        maps={m:bodymap(staged,m) for m in MODELS if stills.is_approved('bodymap',m)}
        heroes={m:hero(staged,m) for m in MODELS if stills.is_approved('heroes',m)}
        content={'schemaVersion':SCHEMA,'minAppSchema':MIN_APP_SCHEMA,'contentVersion':version,
                 'exercises':exercises,'bodymap':maps,'heroes':heroes,'attribution':attribution}
        if stills.is_approved('icons','all'):content['equipmentIcons']=equipment_icons(staged)
        (staged/'content.json').write_text(json.dumps(content,indent=1,ensure_ascii=False)+'\n')
        verify(staged)
        os.replace(staged,final)
    except BaseException:
        shutil.rmtree(staged,ignore_errors=True);raise
    pointer={'schemaVersion':SCHEMA,'minAppSchema':MIN_APP_SCHEMA,'contentVersion':version,
             'content':{'path':f'{version}/content.json','bytes':(final/'content.json').stat().st_size,
                        'sha256':digest(final/'content.json')},
             'publishedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')}
    tmp=out/'current.json.tmp';tmp.write_text(json.dumps(pointer,indent=1)+'\n');os.replace(tmp,out/'current.json')
    return final,content

def verify(release):
    """Every media file named in content.json exists with its size and hash; nothing extra."""
    release=Path(release);content=read(release/'content.json')
    assert content['schemaVersion']==SCHEMA
    named=set();assets=[]
    for e in content['exercises']:
        assert set(e['primary']+e['secondary'])<=set(MUSCLES),e['id']
        assets+=[a for views in e['media'].values() for pair in views.values() for a in pair.values()]
    for views in content['bodymap'].values():
        for v in views.values():
            assert set(v['masks'])<=set(MUSCLES)
            assets+=[v['base'],v['hitRegions'],*v['masks'].values()]
    assets+=list(content['heroes'].values())+[c['icon'] for c in content.get('equipmentIcons',{}).values()]
    for a in assets:
        path=release/a['path'];named.add(path.resolve())
        assert path.resolve().is_relative_to(release.resolve()),a['path']
        assert path.stat().st_size==a['bytes'] and digest(path)==a['sha256'],a['path']
        assert a['path'].endswith(('.mp4','.webp','.png','.svg')),a['path']
    named|={(release/'bodymap'/m/n).resolve() for m in content['bodymap'] for n in ('LICENSE.md','bodymap.json')}
    named|={(release/'heroes'/m/n).resolve() for m in content['heroes'] for n in ('LICENSE.md','hero.json')}
    if 'equipmentIcons' in content:named.add((release/'icons/icons.json').resolve())
    present={p.resolve() for p in release.rglob('*') if p.is_file() and p.name not in ('content.json','ATTRIBUTION.md')}
    assert present==named,'unlisted files in release: '+', '.join(sorted(str(p) for p in present-named))
    return content

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('version');ap.add_argument('--allow-partial',action='store_true')
    a=ap.parse_args();final,content=build(a.version,a.allow_partial)
    n=sum(len(e['media']) for e in content['exercises'])
    print(f'{final}: {len(content["exercises"])} exercises, {n} model deliveries; current.json -> {a.version}')
