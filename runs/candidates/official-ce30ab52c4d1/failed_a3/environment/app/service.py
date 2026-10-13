import json, os, sqlite3, threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
DB='/tmp/funnel.sqlite3'; LOCK=threading.RLock()

def stamp(x):
    if not isinstance(x,str): raise ValueError('occurred_at must be ISO-8601')
    d=datetime.fromisoformat(x.replace('Z','+00:00'))
    if d.tzinfo is None: d=d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).timestamp()

def db():
    c=sqlite3.connect(DB)
    c.execute('create table if not exists events(event_id text primary key,user_id text,at real,seq integer,kind text,campaign text,order_id text,amount integer)')
    return c

def init():
    c=db(); c.commit(); c.close()

def retain(batch):
    c=db()
    for e in batch:
        for k in ('event_id','user_id','occurred_at','ingest_seq','kind'):
            if k not in e: raise ValueError('missing '+k)
        row=(str(e['event_id']),str(e['user_id']),stamp(e['occurred_at']),int(e['ingest_seq']),str(e['kind']),e.get('campaign'),e.get('order_id'),int(e.get('amount_cents',0)))
        old=c.execute('select seq from events where event_id=?',(row[0],)).fetchone()
        if old is None or row[3]>old[0]: c.execute('insert or replace into events values (?,?,?,?,?,?,?,?)',row)
    c.commit(); c.close()

def rows():
    c=db(); x=c.execute('select event_id,user_id,at,seq,kind,campaign,order_id,amount from events').fetchall(); c.close(); return x

def report(q):
    lo,hi=stamp(q['since']),stamp(q['until']); allr=rows(); users={}
    for r in allr: users.setdefault(r[1],[]).append(r)
    placed=[]; lookup={}
    for u,es in users.items():
        es.sort(key=lambda r:(r[2],r[3],r[0])); sid=-1; prev=None
        for r in es:
            if prev is None or r[2]-prev>1800: sid+=1
            z=(u,sid,r); placed.append(z); lookup[r[0]]=z; prev=r[2]
    touches={}
    for u,s,r in placed:
        if r[4] in ('touch','visit','page_view','click') and r[5]: touches.setdefault((u,s),[]).append(r)
    def attribution(u,s,r):
        a=[x for x in touches.get((u,s),[]) if (x[2],x[3],x[0])<=(r[2],r[3],r[0])]
        return max(a,key=lambda x:(x[2],x[3],x[0]))[5] if a else '(direct)'
    orders={}
    for u,s,r in placed:
        if r[4]=='purchase' and r[6] and r[6] not in orders: orders[r[6]]=(r,attribution(u,s,r))
    reversed_orders=set()
    for u,s,r in placed:
        if r[4]=='refund' and r[6] in orders and lo<=r[2]<hi: reversed_orders.add(r[6])
    requested=q.get('campaigns'); names=set(requested or []); vals={}
    for u,s,r in placed:
        if lo<=r[2]<hi:
            camp=attribution(u,s,r); names.add(camp); vals.setdefault(camp,[0,0,0]); vals[camp][0]+=1
    for oid,(r,camp) in orders.items():
        if lo<=r[2]<hi:
            names.add(camp); vals.setdefault(camp,[0,0,0]); vals[camp][1]+=1
            if oid not in reversed_orders: vals[camp][2]+=r[7]
    out=[{'campaign':n,'sessions':vals.get(n,[0,0,0])[0],'purchases':vals.get(n,[0,0,0])[1],'revenue_cents':vals.get(n,[0,0,0])[2]} for n in names]
    return {'rows':sorted(out,key=lambda x:(-x['revenue_cents'],x['campaign']))}

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def send(self,code,obj):
        b=json.dumps(obj,separators=(',',':')).encode(); self.send_response(code); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path=='/health': self.send(200,{'status':'ok'})
        else: self.send(404,{'error':'not found'})
    def do_POST(self):
        try:
            n=int(self.headers.get('Content-Length','0')); q=json.loads(self.rfile.read(n) or '{}')
            with LOCK:
                if self.path=='/v1/reset':
                    c=db(); c.execute('delete from events'); c.commit(); c.close(); return self.send(200,{'ok':True})
                if self.path=='/v1/append':
                    es=q.get('events') if isinstance(q,dict) else None
                    if not isinstance(es,list): return self.send(400,{'error':'events must be a list'})
                    retain(es); return self.send(200,{'accepted':len(es)})
                if self.path=='/v1/report': return self.send(200,report(q))
            self.send(404,{'error':'not found'})
        except (KeyError,ValueError,TypeError,sqlite3.Error) as e: self.send(400,{'error':str(e)})
init(); HTTPServer(('0.0.0.0',8080),Handler).serve_forever()
