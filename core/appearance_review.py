"""Create the unpublished appearance-v2 page with native alpha/theme comparisons."""
from pathlib import Path
import json
import shutil
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'review/look_v2'
checks=json.loads((OUT/'study_checks.json').read_text())
for name in ('transparent_male','transparent_female','bra_inactive','bra_active'):
    image=Image.open(OUT/(name+'.png'))
    assert image.mode=='RGBA' and image.getchannel('A').getextrema()==(0,255)
    image.save(OUT/(name+'.webp'),'WEBP',lossless=True,method=6)
    for theme,bg in [('light','#F4F5F7'),('dark','#0A0A0C')]:
        canvas=Image.new('RGBA',image.size,bg);canvas.alpha_composite(image)
        canvas.convert('RGB').save(OUT/(name+'_'+theme+'.webp'),'WEBP',quality=92,method=6)
shutil.copyfile(ROOT/'review/look_oct24/sheet.png',OUT/'sheet.png')
(OUT/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Short clothing and hair review</title>
<style>body{--bg:#000;--fg:#fff;--muted:#b7b8c0;--card:#0A0A0C;background:var(--bg);color:var(--fg);font:16px system-ui;max-width:1440px;margin:auto;padding:24px}
body[data-theme=light]{--bg:#f4f5f7;--fg:#111;--muted:#51525a;--card:#fff}h1{font-size:30px}p{line-height:1.55;color:var(--muted)}
button,a{color:var(--fg)}button{border:1px solid #777;background:var(--card);padding:10px 20px;border-radius:10px;cursor:pointer;margin-right:8px}a{color:#38a85a}
.row{display:grid;grid-template-columns:1fr 1fr;gap:20px}.card{background:var(--card);border-radius:16px;text-align:center;overflow:hidden}.card img{width:100%;max-height:720px;object-fit:contain}img.sheet{width:100%;height:auto}.note{border-left:3px solid #ff9f0a;padding-left:16px}h2{margin-top:32px}
@media(max-width:600px){body{padding:12px}.row{gap:8px}h1{font-size:25px}}</style>
<body data-theme="dark"><h1>Short clothing, quieter highlights, hair</h1>
<p class="note">Unapproved appearance revision. Training bottoms are shorter; the sports bra has a higher lower edge and narrower straps.
Worked muscles beneath fabric use a softer tint. Fabric over inactive muscles stays solid.</p>
<button onclick="document.body.dataset.theme='dark'">Dark</button><button onclick="document.body.dataset.theme='light'">Light</button>
<h2>Transparent stills — same images on either background</h2>
<p>These PNG/WebP previews have a genuine alpha channel. Toggle the background above.
Exercise videos retain the dark H.264 default; transparent video requires another codec/playback path and device validation.</p>
<div class="row"><div class="card"><h3>Male · short crop</h3><img src="transparent_male.webp" alt="Male with cropped hair and short training bottoms"></div>
<div class="card"><h3>Female · tied hair</h3><img src="transparent_female.webp" alt="Female with ponytail, smaller sports bra and short bottoms"></div></div>
<h2>Muscles covered by the bra</h2><p>This is a material study in a neutral pose, not an exercise classification.
The fabric stays opaque; the subdued colour suggests the worked muscle underneath.</p>
<div class="row"><div class="card"><h3>Chest inactive · solid fabric</h3><img src="bra_inactive.webp" alt="Solid dark sports bra when chest is inactive"></div>
<div class="card"><h3>Chest active · subdued tint</h3><img src="bra_active.webp" alt="Subdued chest highlight through the sports-bra material"></div></div>
<h2>Two-exercise appearance checkpoint</h2><p>Squat and dumbbell shoulder press, both models: all three views, start and peak poses.
Full motion and garment checks cover all 72 frames. Each delivery still requires human approval.</p><img class="sheet" src="sheet.png" alt="All four current appearance previews">
<p><a href="../look_oct24/index.html">Full-resolution exercise sheets and QA reports</a> · <a href="study_checks.json">Hair loop checks</a> · <a href="/bodymap/LICENSE.md">Attribution</a></p>
<p>Original procedural hair and clothing; MPFB scalp/body CC0. Anatomy-derived highlights retain Z-Anatomy / BodyParts3D attribution.
Reference screenshots informed style only; no competitor image, texture or model was imported.</p></body></html>''')
print(OUT/'index.html')
