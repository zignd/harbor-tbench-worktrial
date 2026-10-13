import json,os,sqlite3,urllib.parse
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
DB=os.environ.get('FUNNEL_DB','/tmp/funnel.sqlite3')
def sec(v):
    if v.endswith('Z'): v=v[:-1]+'+00:00'
    d=datetime.fromisoformat(v)
    if d.tzinfo is None: d=d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).timestamp()
def load():
    c=sqlite3.connect(DB); out={k:json.loads(v) for k,v in c.execute('select event_id,body from events')}; c.close(); return out
def inside(e,a,b):
    t=sec(e['occurred_at']); return (a is None or t>=a) and (b is None or t<b)
def compute(a,since=None,until=None,filter_names=None):
    lo=sec(since) if since else None; hi=sec(until) if until else None
    users={}
    for e in a.values(): users.setdefault(e['user_id'],[]).append(e)
    sid={}; groups={}; touches={}
    for u,es in users.items():
        es.sort(key=lambda e:(sec(e['occurred_at']),int(e.get('ingest_seq',0)),e['event_id']))
        last=None; n=-1
        for e in es:
            t=sec(e['occurred_at'])
            if last is None or t-last>1800: n+=1
            last=t; sid[e['event_id']]=(u,n); groups.setdefault((u,n),[]).append(e)
            if e['kind'] in ('touch','visit','campaign_touch'): touches.setdefault((u,n),[]).append(e)
    sess_campaign={}
    for key,es in groups.items():
        z=sorted(touches.get(key,[]),key=lambda e:(sec(e['occurred_at']),int(e.get('ingest_seq',0)),e['event_id']))
        sess_campaign[key]=z[-1].get('campaign','(direct)') if z else '(direct)'
    purchases={}
    for e in a.values():
        if e['kind']!='purchase' or e.get('order_id') in purchases: continue
        key=sid[e['event_id']]; z=[x for x in touches.get(key,[]) if sec(x['occurred_at'])<=sec(e['occurred_at'])]
        z.sort(key=lambda x:(sec(x['occurred_at']),int(x.get('ingest_seq',0)),x['event_id']))
        purchases[e['order_id']]={'e':e,'campaign':z[-1].get('campaign','(direct)') if z else '(direct)','amount':int(e.get('amount_cents',0))}
    refund_events={}
    for e in a.values():
        if e['kind']=='refund' and e.get('order_id') in purchases: refund_events.setdefault(e['order_id'],[]).append(e)
    names=set(filter_names) if filter_names else set()
    for k,c in sess_campaign.items():
        if not filter_names and touches.get(k) and any(inside(e,lo,hi) for e in groups[k]): names.add(c)
    for order,p in purchases.items():
        if not filter_names and (inside(p['e'],lo,hi) or any(inside(r,lo,hi) for r in refund_events.get(order, []))): names.add(p['campaign'])
    rows={n:{'campaign':n,'sessions':0,'purchases':0,'revenue_cents':0} for n in names}
    for k,c in sess_campaign.items():
        if c in rows and any(inside(e,lo,hi) for e in groups[k]): rows[c]['sessions']+=1
    for order,p in purchases.items():
        e=p['e']; c=p['campaign']
        if c not in rows: continue
        if inside(e,lo,hi):
            rows[c]['purchases']+=1
            rows[c]['revenue_cents']+=p['amount']
        if any(inside(r,lo,hi) for r in refund_events.get(order, [])):
            rows[c]['revenue_cents']-=p['amount']
    return sorted(rows.values(),key=lambda x:(-x['revenue_cents'],x['campaign']))
def init():
    c=sqlite3.connect(DB); c.execute('create table if not exists events(event_id text primary key,body text)'); c.commit(); c.close()
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*x): pass
    def reply(self,status,obj):
        b=json.dumps(obj,separators=(',',':')).encode(); self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path=='/health': return self.reply(200,{'status':'ok'})
        if urllib.parse.urlsplit(self.path).path=='/v1/report':
            q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query); f=q.get('campaign',q.get('campaigns',[]));
            if len(f)==1 and ',' in f[0]: f=f[0].split(',')
            return self.reply(200,{'rows':compute(load(),q.get('since',[None])[0],q.get('until',[None])[0],f or None)})
        return self.reply(404,{'error':'not found'})
    def do_POST(self):
        try: body=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
        except Exception: return self.reply(400,{'error':'invalid json'})
        if self.path=='/v1/reset':
            c=sqlite3.connect(DB); c.execute('delete from events'); c.commit(); c.close(); return self.reply(200,{'ok':True})
        if self.path=='/v1/append':
            es=body if isinstance(body,list) else (body.get('events') if isinstance(body,dict) else None)
            if not isinstance(es,list) or any(not isinstance(e,dict) or 'event_id' not in e for e in es):
                return self.reply(400,{'error':'events must be a list of event objects'})
            c=sqlite3.connect(DB)
            for e in es:
                old=c.execute('select body from events where event_id=?',(e['event_id'],)).fetchone()
                if old is None or int(e.get('ingest_seq',0))>int(json.loads(old[0]).get('ingest_seq',0)):
                    c.execute('insert or replace into events values(?,?)',(e['event_id'],json.dumps(e,separators=(',',':'))))
            c.commit(); c.close(); return self.reply(200,{'ok':True,'accepted':len(es)})
        return self.reply(404,{'error':'not found'})
if __name__=='__main__': init(); ThreadingHTTPServer(('0.0.0.0',8080),Handler).serve_forever()
