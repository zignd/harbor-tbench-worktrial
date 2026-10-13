#!/usr/bin/env python3
import json,sqlite3
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
DB='/var/lib/funnel/events.sqlite3'

def db():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
 c.execute('CREATE TABLE IF NOT EXISTS events(event_id TEXT PRIMARY KEY,user_id TEXT,occurred_at TEXT,ingest_seq INTEGER,kind TEXT,campaign TEXT,order_id TEXT,amount_cents INTEGER)'); return c

def ts(x):
 d=datetime.fromisoformat(str(x).replace('Z','+00:00'))
 if d.tzinfo is None:d=d.replace(tzinfo=timezone.utc)
 return d.astimezone(timezone.utc).timestamp()

def calc(c,lo,hi,wanted):
 ev=list(c.execute('select * from events')); users={}
 for e in ev: users.setdefault(e['user_id'],[]).append(e)
 sessions=[]; sidof={}; bysid={}
 for u,a in users.items():
  a.sort(key=lambda e:(ts(e['occurred_at']),int(e['ingest_seq']),e['event_id']))
  sid=-1; prev=None
  for e in a:
   t=ts(e['occurred_at'])
   if prev is None or t-prev>1800:sid+=1
   sidof[e['event_id']]=(u,sid); bysid.setdefault((u,sid),[]).append(e); sessions.append((u,sid,e)); prev=t
 purchases=[]
 for (u,sid),a in bysid.items():
  for e in a:
   if e['kind']!='purchase':continue
   touches=[x for x in a if x['kind']=='touch' and x['campaign'] and ts(x['occurred_at'])<=ts(e['occurred_at'])]
   touch=max(touches,key=lambda x:(ts(x['occurred_at']),int(x['ingest_seq']),x['event_id'])) if touches else None
   purchases.append((e,u,sid,touch['campaign'] if touch else '(direct)'))
 orders={}
 for p in sorted(purchases,key=lambda p:(ts(p[0]['occurred_at']),int(p[0]['ingest_seq']),p[0]['event_id'])):orders.setdefault(p[0]['order_id'],p)
 refunds={}
 for e in ev:
  if e['kind']=='refund' and e['order_id'] in orders: refunds.setdefault(e['order_id'],[]).append(e)
 out={}
 def row(k):return out.setdefault(k,{'campaign':k,'campaign_name':k,'sessions':0,'purchases':0,'revenue_cents':0})
 active=set()
 for u,s,e in sessions:
  if lo<=ts(e['occurred_at'])<hi:active.add((u,s))
 for e,u,s,camp in purchases:
  if lo<=ts(e['occurred_at'])<hi and (wanted is None or camp in wanted):
   r=row(camp);r['purchases']+=1;r['revenue_cents']+=int(e['amount_cents'] or 0)
 for oid,(p,u,s,camp) in orders.items():
  if any(lo<=ts(r['occurred_at'])<hi for r in refunds.get(oid,[])) and (wanted is None or camp in wanted):row(camp)['revenue_cents']-=int(p['amount_cents'] or 0)
 for key in active:
  a=bysid[key]; touches=[e for e in a if e['kind']=='touch' and e['campaign']]
  camp=max(touches,key=lambda e:(ts(e['occurred_at']),int(e['ingest_seq']),e['event_id']))['campaign'] if touches else '(direct)'
  if wanted is None or camp in wanted:row(camp)['sessions']+=1
 for k in (wanted or []):row(k)
 return sorted(out.values(),key=lambda r:(-r['revenue_cents'],r['campaign']))

class H(BaseHTTPRequestHandler):
 def log_message(self,*x):pass
 def sendj(self,n,x):
  b=json.dumps(x,separators=(',',':')).encode();self.send_response(n);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):self.sendj(200,{'status':'ok'}) if self.path=='/health' else self.sendj(404,{'error':'not found'})
 def do_POST(self):
  try:
   n=int(self.headers.get('Content-Length','0')); q=json.loads(self.rfile.read(n)); c=db()
   if self.path=='/v1/reset':c.execute('delete from events');c.commit();return self.sendj(200,{'ok':True})
   if self.path=='/v1/append':
    a=q.get('events'); assert isinstance(a,list)
    for e in a:
     for k in ('event_id','user_id','occurred_at','ingest_seq','kind'):assert k in e
     assert e['kind'] in ('touch','purchase','refund');ts(e['occurred_at']);int(e['ingest_seq'])
     if e['kind']=='touch':assert e.get('campaign') is not None
     if e['kind'] in ('purchase','refund'):assert e.get('order_id') is not None
     old=c.execute('select ingest_seq from events where event_id=?',(e['event_id'],)).fetchone()
     if old is None:
      c.execute('insert or replace into events values(?,?,?,?,?,?,?,?)',(e['event_id'],e['user_id'],e['occurred_at'],int(e['ingest_seq']),e['kind'],e.get('campaign'),e.get('order_id'),e.get('amount_cents')))
    c.commit();return self.sendj(200,{'ok':True,'accepted':len(a)})
   if self.path=='/v1/report':
    assert 'since' in q and 'until' in q;lo=ts(q['since']);hi=ts(q['until']);assert hi>=lo
    w=q.get('campaigns');assert w is None or isinstance(w,list)
    return self.sendj(200,{'rows':calc(c,lo,hi,w)})
   self.sendj(404,{'error':'not found'})
  except Exception:self.sendj(400,{'error':'bad request'})
if __name__=='__main__':ThreadingHTTPServer(('0.0.0.0',8080),H).serve_forever()
