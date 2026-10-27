"""Build the unpublished model revision review from neutral and exercise previews."""
from pathlib import Path
import json, shutil
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'review/look_v21'
for model in ('male','female'):
 for part in ('head','torso','body','shoes','watch','nails'):
  for view in ('front','threeq','side','back'):
   p=OUT/f'{model}_{part}_{view}.png'
   im=Image.open(p)
   assert im.mode=='RGBA' and im.getchannel('A').getextrema()==(0,255)
   im.save(p.with_suffix('.webp'),'WEBP',lossless=True,method=6)
for part in ('head','torso'):
 sheet=Image.new('RGB',(1600,1000),'#45464b')
 for row,model in enumerate(('male','female')):
  for col,view in enumerate(('front','threeq','side','back')):
   im=Image.open(OUT/f'{model}_{part}_{view}.webp').resize((400,500))
   sheet.paste(im,(col*400,row*500),im)
   ImageDraw.Draw(sheet).text((col*400+10,row*500+10),f'{model} {view}',fill='white')
 sheet.save(OUT/(part+'s.jpg'),quality=94)
shutil.copyfile(ROOT/'review/look_oct24/sheet.png',OUT/'sheet.png')
receipts=[]
for eid in ('bodyweight_squat','dumbbell_shoulder_press'):
 for model in ('male','female'):
  name=f'{eid}_{model}';q=json.loads((ROOT/'review'/f'{name}_clothes_qa.json').read_text())
  assert q['pass'] and q['complete'] and q['model_checks']['model']==model
  motion=json.loads((ROOT/'review'/f'{name}_qa.json').read_text());assert motion['pass']
  receipts.append(f'<li>{name}: motion, garments, model and accessory attachment checks pass ({q["frames"]} frames). <a href="../{name}_sheet.png">Full sheet</a> · <a href="../{name}_clothes_qa.json">Garment/model QA</a> · <a href="../{name}_qa.json">Motion QA</a></li>')
assert (OUT/'female_squat_white.mp4').is_file(), 'Missing white H.264 review loop'
parts=['<h2>White-background H.264 sample</h2><p>Unapproved female squat loop, rendered through the current pipeline.</p><video src="female_squat_white.mp4" controls loop muted playsinline style="width:100%;max-height:650px;background:white"></video>']
for part,label in [('head','Brows, lashes, beard and hair details'),('torso','Torso silhouettes'),('body','Full models'),('shoes','Trainer close-ups'),('watch','Watch orientation close-ups'),('nails','Hand and nail close-ups')]:
 cards=''.join(f'<figure><img src="{m}_{part}_{v}.webp" alt="{m} {part} {v}"><figcaption>{m} · {v}</figcaption></figure>' for m in ('male','female') for v in ('front','threeq','side','back'))
 parts.append(f'<h2>{label}</h2><div class="grid">{cards}</div>')
(OUT/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Hair and body review</title>
<style>body{background:#fff;color:#15151a;font:16px system-ui;max-width:1600px;margin:auto;padding:24px}body.dark{background:#0A0A0C;color:#eee}p{line-height:1.5}button{padding:10px 20px;cursor:pointer}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}figure{margin:0;text-align:center}img{width:100%;height:auto}a{color:#39ac68}li{margin-bottom:10px}.note{border-left:3px solid #f90;padding-left:14px}@media(max-width:700px){.grid{grid-template-columns:repeat(2,1fr)}body{padding:12px}}</style>
<h1>Top coverage and watch fit</h1><p class="note">Unapproved review. Female top coverage repaired. Watch case seated on a continuous fitted silicone backing. White remains the default video background. Clothes stay opaque with a faint active-muscle tint. Neutral views show body shape without active-muscle colours.</p>
<button onclick="document.body.classList.add('dark')">Dark</button> <button onclick="document.body.classList.remove('dark')">White</button>
<p>Neutral stills have true transparency. Exercise loops use a white H.264 background; transparent stills remain available.</p>
''' + ''.join(parts) + '<h2>Two exercise checkpoint · both models</h2><img src="sheet.png" alt="Squat and shoulder press preview sheets"><ul>' + ''.join(receipts) + '</ul><p>Appearance still requires human approval. No new exercises have been approved or published, and the full-library rerender has not begun.</p><p>Hair source and licence: <a href="../../assets/hair/LICENSE.md">CC0 notices</a>.</p>')
