"""Trace ID pixels to SVG boundaries (including holes), no hand-drawn anatomy.
Python + numpy + Pillow. Run after render.py. Outputs are CC BY-SA 4.0 derivatives.
"""
from pathlib import Path
import json,html,math
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parent
palette=json.loads((ROOT/'palette.json').read_text());colours=np.array(list(palette.values()),dtype=np.int32)

def simplify(points,eps=1.1):
 if len(points)<3:return points
 a=np.array(points[0],float);b=np.array(points[-1],float);p=np.array(points,float);ab=b-a
 if np.dot(ab,ab)==0:d=np.linalg.norm(p-a,axis=1)
 else:
  t=np.clip(((p-a)@ab)/np.dot(ab,ab),0,1);d=np.linalg.norm(p-(a+t[:,None]*ab),axis=1)
 k=int(np.argmax(d))
 if d[k]<=eps:return [points[0],points[-1]]
 return simplify(points[:k+1],eps)[:-1]+simplify(points[k:],eps)

def loops(mask):
 # Directed exposed pixel edges; shared borders cancel. Interior always to right.
 h,w=mask.shape;edges={}
 def add(a,b):edges.setdefault(a,[]).append(b)
 yy,xx=np.nonzero(mask)
 for y,x in zip(yy.tolist(),xx.tolist()):
  if y==0 or not mask[y-1,x]:add((x,y),(x+1,y))
  if x==w-1 or not mask[y,x+1]:add((x+1,y),(x+1,y+1))
  if y==h-1 or not mask[y+1,x]:add((x+1,y+1),(x,y+1))
  if x==0 or not mask[y,x-1]:add((x,y+1),(x,y))
 rings=[]
 while edges:
  start=next(iter(edges));a=start;ring=[start]
  for _ in range(sum(map(len,edges.values()))+1):
   choices=edges[a];b=choices.pop()
   if not choices:del edges[a]
   ring.append(b);a=b
   if a==start:break
  if ring[-1]!=start:raise ValueError('open contour')
  area=abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(ring,ring[1:]))/2)
  if area>=12:
   # Split a closed ring before RDP so endpoint distance isn't degenerate.
   mid=len(ring)//2;ring=simplify(ring[:mid+1])[:-1]+simplify(ring[mid:]);rings.append(ring)
 return rings

coverage={}
for view in ('front','back'):
 im=np.array(Image.open(ROOT/(view+'_ids.png')).convert('RGBA'));rgb=im[:,:,:3].astype(np.int32)
 d=((rgb[:,:,None,:]-colours[None,None,:,:])**2).sum(axis=-1);ids=d.argmin(axis=2)
 valid=(d.min(axis=2)<32**2)&(im[:,:,3]>200)
 paths=[];coverage[view]={}
 for i,g in enumerate(palette):
  mask=(ids==i)&valid;rings=loops(mask);coverage[view][g]=int(mask.sum())
  if not rings:continue
  data=' '.join('M'+' L'.join(f'{x},{y}' for x,y in ring)+' Z' for ring in rings)
  paths.append(f'<path id="{g.replace(" ","-")}" data-muscle="{html.escape(g)}" role="button" tabindex="0" aria-label="{html.escape(g)}" d="{data}"/>')
 svg='''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 720 900" width="720" height="900">
<title>'''+view+''' muscle selector</title>
<metadata>Traced from MPFB skin UV masks derived from Z-Anatomy / BodyParts3D. CC BY-SA 4.0. See LICENSE.md.</metadata>
<image href="'''+view+'''.webp" xlink:href="'''+view+'''.webp" width="720" height="900"/>
<g fill="#df463c" fill-opacity="0.10" stroke="#df463c" stroke-opacity="0.25" stroke-width="0.65" fill-rule="evenodd">
'''+ '\n'.join(paths)+'\n</g>\n</svg>\n'
 (ROOT/(view+'.svg')).write_text(svg)
 Image.open(ROOT/(view+'.png')).save(ROOT/(view+'.webp'),'WEBP',quality=90,method=6)
(ROOT/'coverage.json').write_text(json.dumps(coverage,indent=2)+'\n')
missing=[g for g in palette if sum(coverage[v][g] for v in coverage)<12]
if missing:raise ValueError('No tappable surface for '+str(missing))
print('Traced all 17 groups across front/back; see coverage.json')
