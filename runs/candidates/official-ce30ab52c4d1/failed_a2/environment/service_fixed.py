import json,sqlite3
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,HTTPServer
from urllib.parse import urlparse,parse_qs
DB='/app/events.sqlite3'
def sec(v): return datetime.fromisoformat(v.replace('Z','+00:00')).astimezone(timezone.utc).timestamp()
def canon(v): return datetime.fromtimestamp(sec(v),timezone.utc).isoformat().replace('+00:00','Z')
db=sqlite3.connect(DB,check_same_thread=False)
db.execute('create table if not exists events(event_id text primary key,user_id text,occurred_at text,ingest_seq integer,kind text,campaign text,order_id text,amount_cents integer)');db.commit()
def report(q):
 lo=sec(q.get('since',['1970-01-01T00:00:00Z'])[0]); hi=sec(q.get('until',['9999-12-31T00:00:00Z'])[0]); wanted=set(q.get('campaign',[])); groups={}; facts=[]; orders={}; refunds=[]
 allrows=db.execute('select event_id,user_id,occurred_at,ingest_seq,kind,campaign,order_id,amount_cents from events').fetchall()
 by={}
 for e in allrows: by.setdefault(e[1],[]).append(e)
 for uid,es in by.items():
  es.sort(key=lambda x:(sec(x[2]),x[3],x[0])); last=None; sid=0; touches={}
  for e in es:
   t=sec(e[2])
   if last is None or t-last>1800: sid+=1
   last=t; facts.append((uid,sid,e,t))
   if e[4]=='touch': touches.setdefault(sid,[]).append(e)
  for u,s,e,t in [x for x in facts if x[0]==uid]:
   if e[4]=='purchase':
    ts=[x for x in touches.get(s,[]) if sec(x[2])<=t]
    camp=ts[-1][5] if ts else '(direct)'
    old=orders.get(e[6])
    if old is None or (t,e[3],e[0]) < (old[3],old[2][3],old[2][0]): orders[e[6]]=(uid,s,e,t,camp)
   elif e[4]=='refund': refunds.append((e,t))
 refunded=set(e[6] for e,t in refunds if lo<=t<hi and e[6] in orders)
 def get(c): return groups.setdefault(c,{'sessions':set(),'purchases':0,'revenue_cents':0})
 for uid,s,e,t in facts:
  if lo<=t<hi and e[4]=='touch' and e[5] is not None: get(e[5])['sessions'].add((uid,s))
 for oid,(uid,s,e,t,c) in orders.items():
  if lo<=t<hi:
   x=get(c);x['sessions'].add((uid,s));x['purchases']+=1;x['revenue_cents']+=int(e[7] or 0)
   if oid in refunded:x['revenue_cents']-=int(e[7] or 0)
 names=set(groups)|wanted
 out=[]
 for c in names:
  if wanted and c not in wanted: continue
  x=groups.get(c,{'sessions':set(),'purchases':0,'revenue_cents':0})
  out.append({'campaign':c,'sessions':len(x['sessions']),'purchases':x['purchases'],'revenue_cents':x['revenue_cents']})
 out.sort(key=lambda x:(-x['revenue_cents'],x['campaign']))
 return {'rows':out}
class H(BaseHTTPRequestHandler):
 def answer(self,n,o):
  b=json.dumps(o,separators=(',',':')).encode();self.send_response(n);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path.startswith('/health'): return self.answer(200,{'status':'ok'})
  if self.path.startswith('/v1/report'): return self.answer(200,report(parse_qs(urlparse(self.path).query)))
  self.answer(404,{'error':'not found'})
 def do_POST(self):
  try: body=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))) or '{}')
  except Exception:return self.answer(400,{'error':'invalid json'})
  if self.path=='/v1/reset': db.execute('delete from events');db.commit();return self.answer(200,{'ok':True})
  if self.path=='/v1/append':
   try:
    for e in body.get('events',[]):
     v=(e['event_id'],e['user_id'],canon(e['occurred_at']),int(e['ingest_seq']),e['kind'],e.get('campaign'),e.get('order_id'),e.get('amount_cents')); old=db.execute('select ingest_seq from events where event_id=?',(v[0],)).fetchone()
     if old is None: db.execute('insert into events values(?,?,?,?,?,?,?,?)',v)
     elif v[3]>old[0]: db.execute('update events set user_id=?,occurred_at=?,ingest_seq=?,kind=?,campaign=?,order_id=?,amount_cents=? where event_id=?',v[1:]+(v[0],))
    db.commit();return self.answer(200,{'ok':True,'accepted':len(body.get('events',[]))})
   except Exception as e:return self.answer(400,{'error':str(e)})
  self.answer(404,{'error':'not found'})
 def log_message(self,*a): pass
HTTPServer(('0.0.0.0',8080),H).serve_forever()
