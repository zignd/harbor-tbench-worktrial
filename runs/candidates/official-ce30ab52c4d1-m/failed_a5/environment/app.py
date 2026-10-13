#!/usr/bin/env python3
import json, os, sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
DB='/var/lib/funnel/events.sqlite3'
def conn():
    c=sqlite3.connect(DB)
    c.row_factory=sqlite3.Row
    c.execute('CREATE TABLE IF NOT EXISTS events(event_id TEXT PRIMARY KEY,user_id TEXT,occurred_at TEXT,ingest_seq INTEGER,kind TEXT,campaign TEXT,order_id TEXT,amount_cents INTEGER)')
    return c
def stamp(v):
    d=datetime.fromisoformat(str(v).replace('Z','+00:00'))
    if d.tzinfo is None: d=d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).timestamp()
def report(c, since, until, wanted):
    lo=stamp(since) if since is not None else float('-inf')
    hi=stamp(until) if until is not None else float('inf')
    events=list(c.execute('SELECT * FROM events'))
    byuser={}
    for e in events: byuser.setdefault(e['user_id'],[]).append(e)
    sessions=[]; event_session={}; purchases=[]
    for user,arr in byuser.items():
        arr.sort(key=lambda e:(stamp(e['occurred_at']),int(e['ingest_seq']),e['event_id']))
        sid=-1; previous=None
        for e in arr:
            t=stamp(e['occurred_at'])
            if previous is None or t-previous>1800: sid+=1
            sessions.append((user,sid,e)); event_session[e['event_id']]=(user,sid); previous=t
        for e in arr:
            if e['kind']!='purchase': continue
            t=stamp(e['occurred_at']); current_sid=event_session[e['event_id']][1]
            best=None
            for u,s,x in sessions:
                if u==user and s==current_sid and x['kind']=='touch' and stamp(x['occurred_at'])<=t:
                    key=(stamp(x['occurred_at']),int(x['ingest_seq']),x['event_id'])
                    if best is None or key>best[0]: best=(key,x)
            camp=best[1]['campaign'] if best and best[1]['campaign'] else '(direct)'
            purchases.append((e,user,current_sid,camp))
    orders={}
    for p in purchases: orders.setdefault(p[0]['order_id'],p)
    refunds={}
    for e in events:
        if e['kind']=='refund' and e['order_id'] in orders:
            t=stamp(e['occurred_at'])
            if e['order_id'] not in refunds or (t,int(e['ingest_seq']),e['event_id']) < refunds[e['order_id']][0]:
                refunds[e['order_id']]=((t,int(e['ingest_seq']),e['event_id']),e)
    out={}
    def row(camp):
        return out.setdefault(camp,{'campaign':camp,'campaign_name':camp,'sessions':0,'purchases':0,'revenue_cents':0})
    active=set()
    for user,sid,e in sessions:
        if lo<=stamp(e['occurred_at'])<hi: active.add((user,sid))
    for e,user,sid,camp in purchases:
        if lo<=stamp(e['occurred_at'])<hi and (wanted is None or camp in wanted):
            r=row(camp); r['purchases']+=1; r['revenue_cents']+=int(e['amount_cents'] or 0)
    for order,(puser,psid,pe,pcamp) in ((k,(v[1],v[2],v[0],v[3])) for k,v in orders.items()):
        if order in refunds:
            re=refunds[order][1]; rt=stamp(re['occurred_at'])
            if lo<=rt<hi and (wanted is None or pcamp in wanted): row(pcamp)['revenue_cents']-=int(pe['amount_cents'] or 0)
    for user,sid in active:
        members=[e for u,s,e in sessions if u==user and s==sid]
        touches=[e for e in members if e['kind']=='touch' and e['campaign']]
        camp='(direct)'
        if touches:
            touches.sort(key=lambda e:(stamp(e['occurred_at']),int(e['ingest_seq']),e['event_id']))
            camp=touches[-1]['campaign']
        if wanted is None or camp in wanted: row(camp)['sessions']+=1
    if wanted is not None:
        for camp in wanted: row(camp)
    return sorted(out.values(),key=lambda r:(-r['revenue_cents'],r['campaign']))

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def reply(self,status,obj):
        data=json.dumps(obj,separators=(',',':')).encode()
        self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        self.reply(200,{'status':'ok'}) if self.path=='/health' else self.reply(404,{'error':'not found'})
    def do_POST(self):
        try:
            n=int(self.headers.get('Content-Length','0')); q=json.loads(self.rfile.read(n))
            c=conn()
            if self.path=='/v1/reset': c.execute('DELETE FROM events'); c.commit(); self.reply(200,{'ok':True}); return
            if self.path=='/v1/append':
                es=q.get('events')
                if not isinstance(es,list): raise ValueError()
                repaired=os.path.exists('/opt/funnel/.repaired')
                for e in es:
                    for k in ('event_id','user_id','occurred_at','ingest_seq','kind'):
                        if k not in e: raise ValueError()
                    old=c.execute('SELECT ingest_seq FROM events WHERE event_id=?',(e['event_id'],)).fetchone()
                    if old and (not repaired or int(old[0])>=int(e['ingest_seq'])): continue
                    c.execute('INSERT OR REPLACE INTO events VALUES(?,?,?,?,?,?,?,?)',(e['event_id'],e['user_id'],e['occurred_at'],int(e['ingest_seq']),e['kind'],e.get('campaign'),e.get('order_id'),e.get('amount_cents')))
                c.commit(); self.reply(200,{'ok':True,'accepted':len(es)}); return
            if self.path=='/v1/report': self.reply(200,{'rows':report(c,q.get('since'),q.get('until'),q.get('campaigns'))}); return
            self.reply(404,{'error':'not found'})
        except Exception:
            self.reply(400,{'error':'bad request'})
if __name__=='__main__': ThreadingHTTPServer(('0.0.0.0',8080),Handler).serve_forever()
