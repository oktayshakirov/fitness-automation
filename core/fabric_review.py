"""Assemble the unpublished clothing-layer comparison and exercise checkpoint."""
from pathlib import Path
import json,sys,shutil
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.look_review import main as checkpoint
OUT=ROOT/'review/look_v6'
checkpoint()  # Requires complete, current motion and clothing receipts.
shutil.copyfile(ROOT/'review/look_oct24/sheet.png',OUT/'sheet.png')
sections=['<h2>Black ponytail</h2><div class=pair><figure><img src=female_head_threeq.png alt="Black ponytail, three-quarter view"></figure><figure><img src=female_head_side.png alt="Black ponytail, side view"></figure></div>']
for model in ('female','male'):
 source=Image.open(ROOT/'review'/f'bodyweight_squat_{model}_sheet.png')
 cards=[]
 for col,frame in enumerate((1,40)):
  current=source.crop((col*720,900,(col+1)*720,1800))
  current.save(OUT/f'{model}_after_{frame}.png')
  box=(220,350,500,630) if frame==1 else (350,500,670,820)
  for phase,label in (('before','Before'),('after','Solid fabric · faint tint')):
   image=Image.open(OUT/f'{model}_{phase}_{frame}.png').crop(box)
   name=f'{model}_{phase}_{frame}_detail.webp';image.save(OUT/name,'WEBP',lossless=True)
   cards.append(f'<figure><a href="{model}_{phase}_{frame}.png"><img src="{name}" alt="{model}, {label}, frame {frame}"></a><figcaption>{label} · frame {frame}</figcaption></figure>')
 sections.append(f'<h2>{model.title()} squat · before and after</h2><div class="grid">'+''.join(cards)+'</div>')
for name in ('bra_active','bra_inactive'):
 Image.open(OUT/(name+'.png')).save(OUT/(name+'.webp'),'WEBP',lossless=True)
qa=[]
for eid in ('bodyweight_squat','dumbbell_shoulder_press'):
 for model in ('male','female'):
  name=f'{eid}_{model}';q=json.loads((ROOT/'review'/f'{name}_clothes_qa.json').read_text())
  assert q['pass'] and q['complete']
  qa.append(f'<li>{name}: all {q["frames"]} frames pass. <a href="../{name}_sheet.png">Full sheet</a> · <a href="../{name}_clothes_qa.json">Clothing/model QA</a> · <a href="../{name}_qa.json">Motion QA</a></li>')
(OUT/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Solid clothes and black hair</title>
<style>body{background:#0A0A0C;color:#eee;font:16px system-ui;max-width:1440px;margin:auto;padding:24px}p{line-height:1.5;color:#bbb}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:12px}figure{margin:0}img{width:100%;height:auto}figcaption{padding:8px}a{color:#63db85}li{margin:10px 0}.note{border-left:3px solid #f90;padding-left:14px}@media(max-width:700px){.grid{grid-template-columns:1fr 1fr}body{padding:12px}}</style>
<h1>Solid clothes and black hair</h1><p class="note">Unapproved appearance review. Clothes stay solid charcoal with only a very faint colour hint over active muscles. The female ponytail is black. Tap a detail for its full frame.</p>
''' + ''.join(sections) + '''<h2>Sports top · inactive and active chest</h2><p>Material comparison only, not an exercise classification. The top remains opaque; active muscle colour is suggested beneath the fabric.</p><div class="pair"><figure><img src="bra_inactive.webp" alt="Solid inactive sports top"><figcaption>Inactive · solid fabric</figcaption></figure><figure><img src="bra_active.webp" alt="Muted chest highlight beneath fabric"><figcaption>Active · colour beneath fabric</figcaption></figure></div><h2>Two exercises · both models</h2><img src="sheet.png" alt="Full four-preview exercise sheet"><ul>''' + ''.join(qa) + '''</ul><p>No new exercise approvals or publication. The full-library rerender awaits appearance review.</p></html>''')
