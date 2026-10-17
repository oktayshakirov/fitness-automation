"""Integration checks for approval persistence and export gates (temporary fixtures)."""
import unittest,tempfile,json,threading,urllib.request,urllib.error,sys
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core import delivery,review_server

class ApprovalTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  for d in ('catalog','motion/specs','review','dist/demo'): (self.root/d).mkdir(parents=True,exist_ok=True)
  self.write('catalog/demo.json',{'id':'demo','name':'Demo','reviewed':False})
  self.write('motion/specs/demo.json',{'id':'demo','approved':False})
  self.write('review/demo_qa.json',{'id':'demo','pass':True,'blend_sha256':'b','pipeline_sha256':'p'})
  self.write('dist/demo/asset.json',{'spec_sha256':'s','pipeline_sha256':'p','qa':{'blend_sha256':'b'}})
  self.patches=[patch.object(review_server,'ROOT',self.root),patch.object(review_server,'current_asset',return_value={}),patch.object(review_server,'spec_digest',return_value='s'),patch.object(review_server,'rebuild_manifest',return_value=[])]
  for p in self.patches:p.start()
  self.server=review_server.ThreadingHTTPServer(('127.0.0.1',0),review_server.Handler);self.url='http://127.0.0.1:'+str(self.server.server_port)
  self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
 def tearDown(self):
  self.server.shutdown();self.server.server_close()
  for p in reversed(self.patches):p.stop()
  self.temp.cleanup()
 def write(self,p,data):(self.root/p).write_text(json.dumps(data))
 def post(self,**changes):
  data={'id':'demo','approved':True,'reviewed':True,'token':review_server.TOKEN,**changes}
  req=urllib.request.Request(self.url+'/api/approve',data=json.dumps(data).encode(),headers={'Content-Type':'application/json','Origin':self.url})
  try:return urllib.request.urlopen(req).status
  except urllib.error.HTTPError as e:return e.code
 def test_explicit_review_persists_both_flags_and_can_revoke(self):
  self.assertEqual(self.post(),200)
  self.assertTrue(json.loads((self.root/'catalog/demo.json').read_text())['reviewed'])
  self.assertTrue(json.loads((self.root/'motion/specs/demo.json').read_text())['approved'])
  self.assertEqual(self.post(approved=False,reviewed=False),200)
  self.assertFalse(json.loads((self.root/'motion/specs/demo.json').read_text())['approved'])
 def test_no_review_or_bad_token_does_not_approve(self):
  self.assertEqual(self.post(reviewed=False),400);self.assertEqual(self.post(token='bad'),400)
  self.assertFalse(json.loads((self.root/'catalog/demo.json').read_text())['reviewed'])
 def test_stale_qa_blocks_approval(self):
  with patch.object(review_server,'current_asset',side_effect=ValueError('stale QA')):self.assertEqual(self.post(),400)
 def test_cannot_serve_source_or_traverse(self):
  for path in ('/core/review_server.py','/../catalog/demo.json'):
   with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(self.url+path)

class ExportGateTests(unittest.TestCase):
 def test_failed_qa_rejected_before_encoding(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'q.json';p.write_text(json.dumps({'id':'demo','pass':False}))
   with self.assertRaisesRegex(ValueError,'failed'):delivery.current_qa('demo',p)
 def test_stale_spec_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'q.json';p.write_text(json.dumps({'id':'demo','pass':True,'spec_sha256':'old'}))
   with patch.object(delivery,'spec_digest',return_value='new'):
    with self.assertRaisesRegex(ValueError,'stale'):delivery.current_qa('demo',p)

 def test_missing_or_changed_media_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);folder=root/'dist/demo';folder.mkdir(parents=True)
   video=folder/'loop_front.mp4';video.write_bytes(b'original')
   (folder/'thumb.webp').write_bytes(b'thumb')
   entry={'spec_sha256':'s','pipeline_sha256':'p','qa':{'blend_sha256':'b'},'files':{'front':{'h264':'demo/loop_front.mp4'}},'thumb':'demo/thumb.webp','media':{'loop_front.mp4':{'bytes':8,'sha256':delivery.digest(video)}}}
   with patch.object(delivery,'ROOT',root),patch.object(delivery,'current_qa',return_value={'pipeline_sha256':'p','blend_sha256':'b'}),patch.object(delivery,'spec_digest',return_value='s'):
    delivery.current_asset('demo',entry)
    video.write_bytes(b'modified')
    with self.assertRaisesRegex(ValueError,'changed'):delivery.current_asset('demo',entry)
    video.unlink()
    with self.assertRaisesRegex(ValueError,'missing'):delivery.current_asset('demo',entry)
 def test_changed_scene_rejects_old_delivery(self):
  entry={'spec_sha256':'s','pipeline_sha256':'p','qa':{'blend_sha256':'old'}}
  with patch.object(delivery,'current_qa',return_value={'pipeline_sha256':'p','blend_sha256':'new'}),patch.object(delivery,'spec_digest',return_value='s'):
   with self.assertRaisesRegex(ValueError,'scene is stale'):delivery.current_asset('demo',entry)

if __name__=='__main__':unittest.main()
