"""Assemble the two-exercise appearance checkpoint. Never writes approval records."""
from pathlib import Path
import json
import sys
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.delivery import pipeline_digest, spec_digest, digest

CASES = [('bodyweight_squat', 'Bodyweight squat', [1, 40]),
         ('dumbbell_shoulder_press', 'Dumbbell shoulder press', [1, 30])]


def main():
    out = ROOT/'review/look_oct24'; out.mkdir(exist_ok=True)
    font_path = '/System/Library/Fonts/Helvetica.ttc'
    title_font = ImageFont.truetype(font_path, 34)
    font = ImageFont.truetype(font_path, 22)
    small = ImageFont.truetype(font_path, 18)
    sheet = Image.new('RGB', (1440, 1550), '#FFFFFF')
    draw = ImageDraw.Draw(sheet)
    draw.text((24, 18), 'White background + training clothing', font=title_font, fill='#15151A')
    draw.text((24, 64), 'Appearance checkpoint • 2 exercises • male + female • full 72-frame QA',
              font=font, fill='#51525A')
    sections = []; checks = []; row = 0
    pipeline = pipeline_digest()
    for eid, title, frames in CASES:
        motion = json.loads((ROOT/'motion/specs'/f'{eid}.json').read_text())
        names = [v['name'] if isinstance(v, dict) else v for v in motion['views']]
        for model in ('male', 'female'):
            prefix = f'{eid}_{model}'
            qa = json.loads((ROOT/'review'/f'{prefix}_qa.json').read_text())
            cloth = json.loads((ROOT/'review'/f'{prefix}_clothes_qa.json').read_text())
            assert qa['pass'] and cloth['pass'] and cloth.get('complete'), prefix+' has failed QA'
            assert qa['model'] == model and qa['pipeline_sha256'] == pipeline
            assert qa['spec_sha256'] == spec_digest(eid)
            assert qa['blend_sha256'] == digest(ROOT/'review'/f'{prefix}.blend')
            for key in ('blend_sha256','pipeline_sha256','spec_sha256','model'):
                assert cloth[key] == qa[key], prefix+' has stale clothing QA'
            source = Image.open(ROOT/'review'/f'{prefix}_sheet.png').convert('RGB')
            assert source.size == (1440, 2700)
            # Each source is a 2-frame × 3-view grid. Flatten into a labelled row.
            y = 112 + row*350
            draw.text((24, y), f'{title} — {model.title()}', font=font, fill='#15151A')
            draw.text((1100, y), 'Motion + clothing QA passed', font=small, fill='#19733A')
            for view_index, name in enumerate(names):
                for col, frame in enumerate(frames):
                    x = (view_index*2+col)*240
                    crop = source.crop((col*720, view_index*900, (col+1)*720, (view_index+1)*900))
                    assert crop.getpixel((0, 0)) == (255, 255, 255), 'Background mismatch'
                    sheet.paste(crop.resize((240, 300), Image.Resampling.LANCZOS), (x, y+34))
                    draw.text((x+12, y+316), f'{name} · frame {frame}', font=small, fill='#51525A')
            checks.append({'id':eid, 'model':model, 'motion_qa':qa, 'clothing_qa':cloth})
            sections.append(f'<details><summary>{title} — {model.title()} · all three views</summary>'
                            f'<img src="../{prefix}_sheet.png" alt="{title}, {model}, start and peak poses">'
                            f'<p><a href="../{prefix}_qa.json">Motion QA</a> · '
                            f'<a href="../{prefix}_clothes_qa.json">Clothing QA</a></p></details>')
            row += 1
    draw.text((24, 1520), 'UNAPPROVED PREVIEWS · Appearance review does not approve exercise deliveries.',
              font=small, fill='#51525A')
    sheet.save(out/'sheet.png')
    (out/'checks.json').write_text(json.dumps(checks, indent=2)+'\n')
    (out/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Clothing appearance review</title>
<style>body{background:#fff;color:#15151a;font:16px system-ui;margin:0;padding:24px;max-width:1440px;margin:auto}
h1{font-size:30px;margin:0 0 12px}p{line-height:1.6;color:#51525a}img{width:100%;height:auto;background:#FFFFFF}
details{margin:16px 0;background:#f1f2f4;border-radius:12px;padding:16px}summary{cursor:pointer}
a{color:#63db85}.notice{border-left:3px solid #ff9f0a;padding-left:12px}</style>
<h1>White background + training clothing</h1>
<p>Two exercises, both MPFB models. Start and peak poses in front, side and three-quarter views.
Motion QA and garment-clearance checks cover every frame of each 72-frame animation.</p>
<p class="notice">Unapproved appearance previews. Please review shorts, female sports top, highlight
continuity and white-background readability. The full 30 × 2 rerender waits for your response.
Each rebuilt exercise/model will still need human approval before publishing.</p>
<img src="sheet.png" alt="Male and female squat and shoulder press clothing review">
''' + '\n'.join(sections) + '''
<p>Background: #FFFFFF. Geometry: existing MPFB CC0 body and our procedural garments.
Anatomy highlights: Z-Anatomy / BodyParts3D. <a href="/bodymap/LICENSE.md">Full attribution and licences</a>.
Garment checks allow measured existing body-fold contact, with a 2 mm limit on added penetration.
No external clothing asset was imported.</p></html>''')
    print(out/'index.html')


if __name__ == '__main__': main()
