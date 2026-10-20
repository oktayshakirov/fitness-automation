"""Audit the complete MVP bundle without Blender; exit nonzero on any mismatch."""
import json, sys
from pathlib import Path
from PIL import Image
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.delivery import read, digest, current_qa, spec_digest, pipeline_digest, probe
from core.approvals import is_approved

def verify():
    ids = {p.stem for p in (ROOT / 'catalog').glob('*.json')}
    entries = read(ROOT / 'dist/manifest.json')
    assert ids and len(entries) == len(ids), 'Manifest must contain every catalog exercise exactly once'
    assert {e['id'] for e in entries} == ids
    signature = pipeline_digest()
    videos = posters = 0
    largest_video = largest_poster = total = 0
    for e in entries:
        eid = e['id']; cat = read(ROOT / 'catalog' / (eid + '.json'))
        motion = read(ROOT / 'motion/specs' / (eid + '.json'))
        q = current_qa(eid)
        assert e['spec_sha256'] == spec_digest(eid) and e['pipeline_sha256'] == signature, eid
        assert e['qa']['blend_sha256'] == q['blend_sha256'], eid
        assert e['approved'] == is_approved(eid,e,ROOT), eid
        views = [v['name'] if isinstance(v, dict) else v for v in motion['views']]
        assert e['views'] == views and set(e['files']) == set(views), eid
        count = sum(motion['tempo'].values())
        assert abs(e['duration'] - count / 30) < 1e-6
        for view in views:
            for kind in ('h264', 'hevc', 'poster'):
                p = ROOT / 'dist' / e['files'][view][kind]
                assert p.resolve().is_relative_to((ROOT / 'dist' / eid).resolve())
                info = e['media'][p.name]; size = p.stat().st_size
                assert digest(p) == info['sha256'] and size == info['bytes'], str(p)
                total += size
                if kind == 'poster':
                    assert size <= 40_000 and Image.open(p).size == (720, 900)
                    posters += 1; largest_poster = max(largest_poster, size)
                else:
                    data = probe(p); streams = data['streams']
                    assert len(streams) == 1 and streams[0]['codec_type'] == 'video'
                    v = streams[0]
                    assert v['codec_name'] == kind and v['pix_fmt'] == 'yuv420p'
                    assert (v['width'], v['height']) == (720, 900)
                    assert v['r_frame_rate'] == '30/1' and int(v['nb_frames']) == count
                    assert abs(float(data['format']['duration']) - e['duration']) < .04
                    assert size <= 400_000
                    if kind == 'hevc': assert v['codec_tag_string'] == 'hvc1'
                    videos += 1; largest_video = max(largest_video, size)
        assert Image.open(ROOT / 'dist' / e['thumb']).size == (320, 320)
        for view in views:
            assert not list((ROOT / 'review' / f'{eid}_{view}').glob('[0-9][0-9][0-9][0-9].png')), f'{eid}: rendered frames not cleaned'
    assert (ROOT / 'dist/ATTRIBUTION.md').is_file()
    return dict(exercises=len(entries), videos=videos, posters=posters, thumbnails=len(entries),
                largest_video_bytes=largest_video, largest_poster_bytes=largest_poster,
                video_and_poster_bytes=total, approved=sum(e['approved'] for e in entries))

if __name__ == '__main__':
    result = verify()
    (ROOT / 'review/delivery_audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
