import json, os, sqlite3
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
DB='/tmp/funnel.sqlite3'
def init():
 c=sqlite3.connect(DB); c.execute('create table if not exists events(event_id text primary key,body text)'); c.commit(); c.close()
def report():
 c=sqlite3.connect(DB); es=[json.loads(x[0]) for x in c.execute('select body from events')]; c.close(); out={}
 for e in es:
  if e['kind']=='purchase':
   n=e.get('campaign','(direct)'); r=out.setdefault(n,{'campaign':n,'sessions':1,'purchases':0,'revenue_cents':0}); r['purchases']+=1;r['revenue_cents']+=int(e.get('amount_cents',0))
 return {'rows':list(out.values())}
class H(BaseHTTPRequestHandler):
 def log_message(self,*x):pass
 def x(self,n,o):
  b=json.dumps(o).encode();self.send_response(n);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path=='/health':return self.x(200,{'status':'ok'})
  if self.path.startswith('/v1/report'):return self.x(200,report())
  return self.x(404,{})
 def do_POST(self):
  try:b=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
  except:return self.x(400,{})
  if self.path=='/v1/reset':
   c=sqlite3.connect(DB);c.execute('delete from events');c.commit();c.close();return self.x(200,{'ok':True})
  if self.path=='/v1/append':
   es=b if isinstance(b,list) else b.get('events',[]);c=sqlite3.connect(DB)
   for e in es:c.execute('insert or ignore into events values(?,?)',(e['event_id'],json.dumps(e)))
   c.commit();c.close();return self.x(200,{'ok':True,'accepted':len(es)})
  return self.x(404,{})
if __name__=='__main__':init();ThreadingHTTPServer(('0.0.0.0',8080),H).serve_forever()
