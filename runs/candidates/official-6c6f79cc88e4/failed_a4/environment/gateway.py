import sys,json,urllib.parse
from http.server import HTTPServer,BaseHTTPRequestHandler
cache={}
def classify(m,t):
    k=len(t)%16
    if k not in cache: cache[k]=urllib.parse.unquote(t)
    p=cache[k]
    return 'ALLOW' if m in ('GET','POST') and p in ('/health','/api/v1/items') else 'DENY'
def decide(x):
    try:
        if not isinstance(x,dict) or not isinstance(x.get('id'),str): raise ValueError()
        m,t=x.get('method'),x.get('target')
        if not isinstance(m,str) or not isinstance(t,str): raise ValueError()
        return {'id':x['id'],'decision':classify(m,t)}
    except Exception:return {'id':None,'decision':'DENY'}
class H(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            n=int(self.headers.get('Content-Length','-1'))
            x=json.loads(self.rfile.read(n)); b=json.dumps(decide(x),separators=(',',':')).encode()
            self.send_response(200); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
        except Exception:self.send_response(400); self.end_headers()
    def log_message(self,*a):pass
if '--http' in sys.argv: HTTPServer(('127.0.0.1',8080),H).serve_forever()
else:
    for line in sys.stdin.buffer:
        try:x=json.loads(line.decode())
        except Exception:x=None
        print(json.dumps(decide(x),separators=(',',':')),flush=True)
