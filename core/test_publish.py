"""Release envelope checks on temporary fixtures (no Blender, no real dist/)."""
import unittest,tempfile,json,sys,hashlib
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core import publish

class PublishTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  (self.root/'catalog').mkdir();(self.root/'dist').mkdir()
  (self.root/'dist/ATTRIBUTION.md').write_text('credits')
  (self.root/'catalog/demo.json').write_text(json.dumps({'id':'demo','name':'Demo','primary':['abdominals'],
   'secondary':['lower back'],'equipment':['mat'],'steps':['s'],'cues':['c'],'mistakes':['m'],'breathing':'b','source':'x'}))
  self.entries=[self.entry(m) for m in publish.MODELS]
  self.patches=[patch.object(publish,'ROOT',self.root),patch.object(publish,'rebuild_manifest',side_effect=lambda:self.entries),
                patch.object(publish,'current_asset',return_value={}),patch.object(publish,'is_approved',side_effect=lambda i,e,r:e['approved']),
                patch.object(publish,'size',return_value=(720,900))]
  for p in self.patches:p.start()
 def tearDown(self):
  for p in reversed(self.patches):p.stop()
  self.temp.cleanup()
 def entry(self,model):
  folder=self.root/'dist/demo'/model;folder.mkdir(parents=True);media={}
  for name in (f'{model}_loop_side.mp4',f'{model}_poster_side.webp'):
   (folder/name).write_bytes(name.encode());media[name]={'bytes':len(name),'sha256':hashlib.sha256(name.encode()).hexdigest()}
  return {'id':'demo','model':model,'approved':True,'views':['side'],'media':media,
          'files':{'side':{'h264':f'demo/{model}/{model}_loop_side.mp4','poster':f'demo/{model}/{model}_poster_side.webp'}}}
 def test_release_matches_app_contract_and_switches_pointer_last(self):
  final,content=publish.build('v0.2.0',out=self.root/'releases')
  e=content['exercises'][0]
  self.assertEqual((e['primary'],e['secondary']),(['abs'],['lower_back']))
  video=e['media']['female']['side']['video']
  self.assertEqual(set(video),{'path','width','height','bytes','sha256'})
  self.assertTrue((final/video['path']).is_file())
  pointer=json.loads((self.root/'releases/current.json').read_text())
  self.assertEqual(pointer['content']['path'],'v0.2.0/content.json')
  self.assertEqual(pointer['content']['sha256'],hashlib.sha256((final/'content.json').read_bytes()).hexdigest())
  publish.verify(final)
 def test_unapproved_model_blocks_release_unless_partial(self):
  self.entries[1]['approved']=False
  with self.assertRaises(SystemExit):publish.build('v0.2.0',out=self.root/'releases')
  self.assertFalse((self.root/'releases/current.json').exists())
  _,content=publish.build('v0.2.0',allow_partial=True,out=self.root/'releases')
  self.assertEqual(list(content['exercises'][0]['media']),['male'])
 def test_releases_are_immutable_and_failures_leave_no_release(self):
  publish.build('v0.2.0',out=self.root/'releases')
  with self.assertRaises(SystemExit):publish.build('v0.2.0',out=self.root/'releases')
  (self.root/'dist/demo/male/male_poster_side.webp').write_bytes(b'tampered')
  with self.assertRaises(ValueError):publish.build('v0.3.0',out=self.root/'releases')
  self.assertFalse((self.root/'releases/v0.3.0').exists())
  self.assertEqual(json.loads((self.root/'releases/current.json').read_text())['contentVersion'],'v0.2.0')
 def test_body_views_need_a_matching_human_approval(self):
  from core import stills
  folder=self.root/'bodymap/male';folder.mkdir(parents=True);(self.root/'approvals').mkdir()
  (folder/'bodymap.json').write_text(json.dumps({'width':800,'height':1000,'views':{'front':{}}}))
  for name in ('body_front.webp','mask_front_abs.png','hits_front.svg','LICENSE.md'):(folder/name).write_text(name)
  with patch.object(stills,'ROOT',self.root):
   _,content=publish.build('v0.2.0',out=self.root/'releases')
   self.assertEqual(content['bodymap'],{})
   stills.approve('bodymap','male','looked')
   final,content=publish.build('v0.3.0',out=self.root/'releases')
   front=content['bodymap']['male']['front']
   self.assertEqual((list(front['masks']),front['base']['height']),(['abs'],1000))
   publish.verify(final)
   (folder/'mask_front_abs.png').write_text('changed')
   self.assertFalse(stills.is_approved('bodymap','male'))
 def test_heroes_and_icons_need_a_matching_human_approval(self):
  from core import stills
  heroes=self.root/'heroes/female';heroes.mkdir(parents=True);icons=self.root/'icons/set';icons.mkdir(parents=True)
  (self.root/'approvals').mkdir()
  (heroes/'hero.json').write_text(json.dumps({'width':800,'height':1200}))
  for name in ('hero.webp','LICENSE.md'):(heroes/name).write_text(name)
  (icons/'icons.json').write_text(json.dumps({'size':256,'categories':{'barbell':['barbell','power_rack']}}))
  (icons/'barbell.webp').write_text('icon')
  with patch.object(stills,'ROOT',self.root):
   _,content=publish.build('v0.2.0',out=self.root/'releases')
   self.assertEqual((content['heroes'],'equipmentIcons' in content),({},False))
   stills.approve('heroes','female','looked');stills.approve('icons','all','looked')
   final,content=publish.build('v0.3.0',out=self.root/'releases')
   self.assertEqual((list(content['heroes']),content['heroes']['female']['height']),(['female'],1200))
   self.assertEqual(content['equipmentIcons']['barbell']['equipment'],['barbell','power_rack'])
   self.assertEqual(content['equipmentIcons']['barbell']['icon']['path'],'icons/barbell.webp')
   publish.verify(final)
   (icons/'barbell.webp').write_text('changed')
   self.assertFalse(stills.is_approved('icons','all'))
 def test_extra_file_fails_verification(self):
  final,_=publish.build('v0.2.0',out=self.root/'releases')
  (final/'stray.mp4').write_bytes(b'x')
  with self.assertRaises(AssertionError):publish.verify(final)

if __name__=='__main__':unittest.main()
