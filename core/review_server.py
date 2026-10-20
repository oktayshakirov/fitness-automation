"""Local review/approval server. Bind loopback only; explicit human clicks persist.
Run: python3 core/review_server.py [port=8765]. No automatic approvals.
"""
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
import json,sys,secrets,re,datetime,urllib.parse,threading
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.delivery import current_asset,read,rebuild_manifest,spec_digest
from core.approvals import is_approved,record_review
TOKEN=secrets.token_urlsafe(32);LOCK=threading.Lock()

def state():
    items=[]
    for p in sorted((ROOT/'catalog').glob('*.json')):
        cat=read(p);eid=cat['id'];motion=read(ROOT/'motion/specs'/p.name)
        qpath=ROOT/'review'/(eid+'_qa.json');q=read(qpath) if qpath.exists() else None
        asset=ROOT/'dist'/eid/'asset.json';media=read(asset) if asset.exists() else None
        ready=False;reason='No delivery yet'
        if media:
            try:
                current_asset(eid,media)
                ready=True;reason='Ready for human review'
            except (OSError,ValueError,KeyError) as e:reason=str(e)
        items.append(dict(catalog=cat,motion=motion,qa=q,media=media,ready=ready,reason=reason,approved=ready and is_approved(eid,media,ROOT)))
    return {'items':items,'token':TOKEN}

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw):super().__init__(*a,directory=str(ROOT),**kw)
    def log_message(self,*args):pass
    def send_json(self,data,status=200):
        b=json.dumps(data).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
    def do_GET(self):
        url=urllib.parse.urlsplit(self.path)
        if url.path=='/api/state':return self.send_json(state())
        if url.path=='/':self.path='/review/index.html'
        path=urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
        resolved=(ROOT/path.lstrip('/')).resolve()
        allowed=any(resolved.is_relative_to(ROOT/d) for d in ('review','dist','bodymap'))
        if not allowed or '..' in Path(path).parts or resolved.suffix not in ('.html','.svg','.webp','.png','.jpg','.mp4','.json','.md'):
            return self.send_error(404)
        return super().do_GET()
    def do_POST(self):
        if self.path!='/api/approve':return self.send_error(404)
        expected='http://'+self.headers.get('Host','')
        if self.headers.get('Origin')!=expected:return self.send_json({'error':'Origin rejected'},403)
        length=int(self.headers.get('Content-Length','0'))
        if not 0<length<4096:return self.send_error(400)
        try:
            d=json.loads(self.rfile.read(length));eid=d['id'];approved=d['approved']
            if not secrets.compare_digest(d.get('token',''),TOKEN):raise ValueError('Session token rejected')
            if not re.fullmatch(r'[a-z0-9_]+',eid) or type(approved)!=bool:raise ValueError('Invalid approval')
            with LOCK:
                item=next(i for i in state()['items'] if i['catalog']['id']==eid)
                if approved and (not item['ready'] or d.get('reviewed') is not True):raise ValueError('Review the current loop and instructions before approving')
                record_review(eid,approved,item['media'],"Human review in local approval page",ROOT)
                rebuild_manifest()
            return self.send_json({'ok':True,'approved':approved})
        except (ValueError,KeyError,OSError,StopIteration) as e:return self.send_json({'error':str(e)},400)

if __name__=='__main__':
    port=int(sys.argv[1]) if len(sys.argv)>1 else 8765
    print(f'Review: http://127.0.0.1:{port}/review/index.html',flush=True)
    ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
