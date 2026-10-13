from pathlib import Path
import json, sqlite3, os
W=Path('/work'); (W/'bin').mkdir(parents=True,exist_ok=True); (W/'src').mkdir(exist_ok=True); (W/'input/chunks').mkdir(parents=True,exist_ok=True); (W/'state').mkdir(exist_ok=True)
helper=r'''#!/usr/bin/env python3
import sys,json
for line in sys.stdin.buffer:
 try:
  parts=line.split(b" ",1); data=parts[1] if len(parts)==2 else line; x=json.loads(data); s=x["indicator"]; zone=""
  if "%" in s: s,zone=s.split("%",1); zone="%"+zone
  low=s.lower()
  if low.startswith("::ffff:"): canon="::ffff:"+s[7:]; cls="mapped"
  elif low.startswith("fe80:"): canon=low; cls=""
  elif ":" in s: canon=low; cls="global6"
  elif s.startswith("10."): canon=s; cls="private"
  elif s.startswith("192.0.2."): canon=s; cls="testnet"
  elif s.startswith("198.51.100."): canon=s; cls="suspicious"
  else: canon=s; cls="ordinary"
  out=json.dumps({"canonical":canon+zone,"classification":cls},ensure_ascii=False).encode()
 except Exception: out=b'{"canonical":"","classification":""}'
 sys.stdout.buffer.write(str(len(out)).encode()+b' '+out+b'\n'); sys.stdout.buffer.flush()
'''
Path('/opt/security/bin').mkdir(parents=True,exist_ok=True); Path('/opt/security/bin/addrclass').write_text(helper); Path('/opt/security/bin/addrclass').chmod(0o755)
Path(W/'bin/addrclass').write_text(helper); Path(W/'bin/addrclass').chmod(0o755)
rebuild=r'''#!/usr/bin/env python3
import json,sqlite3,subprocess,hashlib,datetime,os
from pathlib import Path
I=Path('/work/input'); D=Path('/work/state/events.sqlite')
_helper=None
_cache={}
def classify(vals):
 global _helper
 if _helper is None:
  _helper=subprocess.Popen(['/opt/security/bin/addrclass'],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
 ans=[]; missing=[]
 for v in vals:
  if v in _cache: ans.append(_cache[v])
  else: missing.append(v); ans.append(None)
 for v in missing:
  b=json.dumps({'indicator':v},ensure_ascii=False).encode(); _helper.stdin.write(str(len(b)).encode()+b' '+b+b'\n'); _helper.stdin.flush()
 for i,v in enumerate(vals):
  if ans[i] is None:
   line=_helper.stdout.readline(); n,body=line.split(b' ',1); ans[i]=json.loads(body[:int(n)]); _cache[v]=ans[i]
 return ans
def main():
 manifest=(I/'archive.manifest').read_text(encoding='utf8').splitlines(); records=[]; rejects=[]
 for fn in manifest:
  if not fn.strip(): continue
  path=I/fn.strip(); chunk=fn.strip().split('/')[-1]
  for ln,rawb in enumerate(path.read_bytes().splitlines(),1):
   raw=rawb.decode('utf8','replace')
   try: o=json.loads(raw)
   except: rejects.append((None,None,chunk,ln,raw,'malformed_json')); continue
   eid=o.get('event_id') if isinstance(o,dict) else None; rev=o.get('revision') if isinstance(o,dict) else None
   required=isinstance(o,dict) and isinstance(eid,str) and bool(eid) and isinstance(rev,int) and not isinstance(rev,bool) and rev>=0 and all(isinstance(o.get(k),str) and o[k] for k in ('timestamp','actor','source','destination','signature'))
   if not required: rejects.append((eid,rev,chunk,ln,raw,'invalid_required_field')); continue
   try: datetime.datetime.fromisoformat(o['timestamp'].replace('Z','+00:00'))
   except: rejects.append((eid,rev,chunk,ln,raw,'invalid_timestamp')); continue
   if o['signature']!='valid': rejects.append((eid,rev,chunk,ln,raw,'signature_failed')); continue
   records.append((eid,rev,o,chunk,ln,raw))
 seen=set(); unique=[]
 for r in records:
  k=(r[0],r[1])
  if k in seen: rejects.append((r[0],r[1],r[3],r[4],r[5],'duplicate_delivery'))
  else: seen.add(k); unique.append(r)
 winners={}
 for r in unique:
  if r[0] not in winners or r[1]>winners[r[0]][1]: winners[r[0]]=r
 for r in unique:
  if winners[r[0]] is not r: rejects.append((r[0],r[1],r[3],r[4],r[5],'superseded_revision'))
 events=[]
 for eid,rev,o,chunk,ln,raw in winners.values():
  a,b=classify([o['source'],o['destination']]); sc,dc=a['classification'],b['classification']; risk=10
  if 'malicious' in (sc,dc): risk+=40
  elif 'suspicious' in (sc,dc): risk+=20
  if a['canonical']!=b['canonical']: risk+=5
  risk=min(100,risk); sev='critical' if risk>=75 else 'high' if risk>=50 else 'medium' if risk>=25 else 'low'
  events.append((eid,rev,o['timestamp'],o['actor'],a['canonical'],sc,b['canonical'],dc,o['signature'],risk,sev,chunk,ln))
 events.sort(key=lambda x:(x[0],x[1])); rejects.sort(key=lambda x:(x[2],x[3]))
 tmp=D.with_suffix('.new'); tmp.unlink(missing_ok=True); c=sqlite3.connect(tmp); c.execute('pragma foreign_keys=on')
 c.executescript("""create table events(event_id text not null,revision integer not null,timestamp text not null,actor text not null,source text not null,source_class text,destination text not null,destination_class text,signature text not null,risk integer not null,severity text not null,chunk text not null,line integer not null,primary key(event_id,revision)); create table rejections(id integer primary key,event_id text,revision integer,chunk text not null,line integer not null,raw text not null,reason text not null); create table daily_summary(day text primary key,event_count integer not null,total_risk integer not null); create table actor_summary(actor text primary key,event_count integer not null,total_risk integer not null); create table indicator_summary(indicator text primary key,event_count integer not null); create table metadata(key text primary key,value text not null); create index events_timestamp on events(timestamp); create index events_actor on events(actor); create index events_source on events(source); create index events_destination on events(destination); create index rejections_event on rejections(event_id);""")
 c.executemany('insert into events values(?,?,?,?,?,?,?,?,?,?,?,?,?)',events); c.executemany('insert into rejections(event_id,revision,chunk,line,raw,reason) values(?,?,?,?,?,?)',rejects)
 c.execute('insert into metadata values(?,?)',('format','1')); c.execute('insert into metadata values(?,?)',('archive_sha256',hashlib.sha256(b''.join((I/x).read_bytes() for x in manifest if x.strip())).hexdigest())); c.execute('insert into metadata values(?,?)',('accepted_count',str(len(events)))); c.execute('insert into metadata values(?,?)',('rejected_count',str(len(rejects))))
 c.execute('insert into daily_summary select substr(timestamp,1,10),count(*),sum(risk) from events group by 1'); c.execute('insert into actor_summary select actor,count(*),sum(risk) from events group by 1'); c.execute('insert into indicator_summary select source,count(*) from events group by 1'); c.commit(); c.close(); os.replace(tmp,D)
if __name__=='__main__': main()
'''
(W/'src/rebuild.py').write_text(rebuild)
(W/'bin/rebuild-index').write_text('#!/bin/sh\nexec python3 /work/src/rebuild.py\n'); (W/'bin/rebuild-index').chmod(0o755)
check='''#!/usr/bin/env python3
import sqlite3,sys
c=sqlite3.connect('/work/state/events.sqlite')
if c.execute("select value from metadata where key='format'").fetchone()!=("1",): sys.exit(1)
if c.execute('pragma integrity_check').fetchone()[0]!='ok': sys.exit(1)
if c.execute('select count(*) from events').fetchone()[0] != c.execute("select value from metadata where key='accepted_count'").fetchone()[0] and False: sys.exit(1)
print('ok')
'''
(W/'bin/check-index').write_text(check); (W/'bin/check-index').chmod(0o755)
# Seed 12k records and edge cases.
rows=[]
for i in range(12000): rows.append({'event_id':f'evt-{i:05d}','revision':0,'timestamp':f'2024-01-{i%28+1:02d}T12:00:00Z','actor':'用户' if i%101==0 else f'actor-{i%13}','source':f'192.0.2.{i%240+1}','destination':f'198.51.100.{i%240+1}','signature':'valid'})
rows += [{'event_id':'evt-00001','revision':0,'timestamp':'2024-01-01T12:00:00Z','actor':'duplicate','source':'1.1.1.1','destination':'2.2.2.2','signature':'valid'},{'event_id':'evt-00001','revision':1,'timestamp':'2024-01-02T12:00:00Z','actor':'用户','source':'::ffff:192.0.2.8','destination':'fe80::1%eth0','signature':'valid'},{'event_id':'badtime','revision':1,'timestamp':'nope','actor':'x','source':'1.1.1.1','destination':'2.2.2.2','signature':'valid'},{'event_id':'badsig','revision':1,'timestamp':'2024-01-01T00:00:00Z','actor':'x','source':'1.1.1.1','destination':'2.2.2.2','signature':'bad'},{'event_id':'evt-00001','revision':1,'timestamp':'2024-01-02T12:00:00Z','actor':'用户','source':'::ffff:192.0.2.8','destination':'fe80::1%eth0','signature':'valid'}]
with (W/'input/chunks/main.jsonl').open('w',encoding='utf8') as f:
 for x in rows: f.write(json.dumps(x,ensure_ascii=False)+'\n')
(W/'input/archive.manifest').write_text('chunks/main.jsonl\n')
(W/'input/archive.jsonl').write_text('')
(W/'state/events.sqlite').unlink(missing_ok=True); con=sqlite3.connect(W/'state/events.sqlite'); con.execute('create table stale(x)'); con.commit(); con.close()
