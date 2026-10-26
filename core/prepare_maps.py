"""Derive soft highlights and seam-safe shallow muscle relief from baked masks.
Run with Python + Pillow. Z-Anatomy-derived outputs remain CC BY-SA 4.0.
The faulty ecorche normal bake is retained for diagnosis, never sampled for delivery.
"""
from pathlib import Path
from PIL import Image,ImageFilter,ImageChops
ROOT=Path(__file__).resolve().parents[1];maps=ROOT/'assets/maps'
soft=maps/'soft';soft.mkdir(exist_ok=True)
height=Image.new('L',(2048,2048),0)
for i in range(6):
 source=maps/'repaired'/f'mask_{i}.png'
 if not source.exists():source=maps/f'mask_{i}.png'
 im=Image.open(source).convert('RGB')
 im.filter(ImageFilter.GaussianBlur(7.0)).save(soft/f'mask_{i}.png')
 for j,c in enumerate(im.split()):
  # Only body groups: no face, scalp, skeletal rays or neck relief.
  if i*3+j>=16:continue
  # Erode each island before blur so relief falls smoothly to zero at its border.
  relief=c.resize((512,512)).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.5)).resize((2048,2048),Image.Resampling.BICUBIC)
  height=ImageChops.lighter(height,relief)
height.save(maps/'muscle_detail_height.png')
print('Prepared six softened masks and shallow detail height map')
