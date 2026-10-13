#!/usr/bin/env python3
import sqlite3,sys,os,tempfile,shutil,json,hashlib

def setup(c):
 c.executescript('''CREATE TABLE archival_events(id TEXT PRIMARY KEY,ts TEXT,actor TEXT,resolved_actor TEXT,incident_key TEXT,merge_key TEXT,seq INTEGER,depends_on TEXT,kind TEXT,payload TEXT,supersedes TEXT,tombstone INTEGER); CREATE TABLE incidents(id TEXT PRIMARY KEY,incident_key TEXT,actor TEXT); CREATE TABLE incident_events(incident_id TEXT,event_id TEXT,ordinal INTEGER,PRIMARY KEY(incident_id,event_id)); CREATE TABLE transitions(incident_id TEXT,ordinal INTEGER,event_id TEXT,kind TEXT,at TEXT,policy_version TEXT); CREATE TABLE sla_windows(incident_id TEXT,transition_event_id TEXT,policy_version TEXT,response_minutes INTEGER); CREATE TABLE replay_audit(name TEXT PRIMARY KEY,value TEXT);''')

def rows(c,n):
 return c.execute('SELECT id,ts,actor,incident_key,merge_key,seq,depends_on,kind,payload,supersedes,coalesce(tombstone,0) FROM raw_events ORDER BY rowid').fetchall()
def run(src,dst):
 s=sqlite3.connect(src); outtmp=dst+'.tmp-'+str(os.getpid());
 try:
  if os.path.exists(outtmp): os.unlink(outtmp)
  d=sqlite3.connect(outtmp); setup(d); aliases=s.execute('SELECT alias,canonical,valid_from,valid_to FROM actor_aliases').fetchall(); events=rows(s)
  # Legacy path: correlation and policy are intentionally batch-oriented.
  firstpol=s.execute('SELECT version,response_minutes FROM policy_versions ORDER BY effective_from LIMIT 1').fetchone()
  groups={}
  for e in events:
   aid=e[2]
   for a,can,lo,hi in aliases:
    if aid==a and lo<=e[1] and (hi is None or e[1]<hi): aid=can; break
   d.execute('INSERT INTO archival_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(*e[:2],e[2],aid,*e[3:]))
   groups.setdefault((e[3],e[2]),[]).append(e)
  for (key,actor),es in groups.items():
   iid=hashlib.sha256((str(key)+'|'+actor).encode()).hexdigest()[:16]; d.execute('INSERT INTO incidents VALUES (?,?,?)',(iid,key,actor))
   es.sort(key=lambda x:(x[1],x[5],x[0]))
   for i,e in enumerate(es):
    d.execute('INSERT INTO incident_events VALUES (?,?,?)',(iid,e[0],i));
    if e[6] not in [None,''] and e[6] in {x[0] for x in es}: pass
    if e[7] in ('open','ack','resolve') and not e[10]:
     d.execute('INSERT INTO transitions VALUES (?,?,?,?,?,?)',(iid,i,e[0],e[7],e[1],firstpol[0] if firstpol else None)); d.execute('INSERT INTO sla_windows VALUES (?,?,?,?)',(iid,e[0],firstpol[0],firstpol[1]))
  d.execute('INSERT INTO replay_audit VALUES (?,?)',('events',str(len(events)))); d.commit(); d.close(); s.close(); os.replace(outtmp,dst)
 except Exception:
  try: os.unlink(outtmp)
  except OSError: pass
  raise
if __name__=='__main__':
 try: run(sys.argv[1],sys.argv[2])
 except Exception as e: print(str(e),file=sys.stderr); sys.exit(1)
