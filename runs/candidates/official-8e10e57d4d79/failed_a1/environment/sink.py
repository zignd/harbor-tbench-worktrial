#!/usr/bin/env python3
import json,os,threading
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
seen=set(); events=[]; lock=threading.Lock(); total=bad=0
class H(BaseHTTPRequestHandler):
 def log_message(self,*a): pass
 def do_GET(self):
  if self.path=='/health': self.send_response(200); self.end_headers(); self.wfile.write(b'{"status":"ok"}')
  elif self.path=='/events':
   with lock: q=json.dumps(events,separators=(',',':')).encode()
   self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(q))); self.end_headers(); self.wfile.write(q)
  elif self.path=='/metrics':
   with lock: x={'accepted':len(events),'duplicates':total-len(events),'invalid':bad}
   q=json.dumps(x).encode(); self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(q))); self.end_headers(); self.wfile.write(q)
  else: self.send_error(404)
 def do_POST(self):
  global total,bad
  if self.path!='/events': self.send_error(404); return
  try:
   raw=self.rfile.read(int(self.headers.get('Content-Length','0'))); rows=[json.loads(x) for x in raw.splitlines() if x.strip()]
   with lock:
    total+=len(rows)
    for e in rows:
     if not all(k in e for k in ('identifier','sequence','timestamp','measurements','metadata')): raise ValueError()
     if e['identifier'] in seen: continue
     seen.add(e['identifier']); events.append(e)
   self.send_response(200); self.end_headers(); self.wfile.write(b'OK')
  except Exception:
   bad+=1; self.send_response(400); self.end_headers()
ThreadingHTTPServer(('0.0.0.0',9200),H).serve_forever()
