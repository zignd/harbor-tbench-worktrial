#!/usr/bin/env python3
import argparse,sqlite3,os,sys,json,hashlib,tempfile,datetime

def iso(x):
    if not x:return ''
    s=str(x).replace('Z','+00:00')
    try:return datetime.datetime.fromisoformat(s).astimezone(datetime.timezone.utc).isoformat().replace('+00:00','Z')
    except:return str(x)
def j(x):
    try:return json.loads(x or '{}')
    except:return {}
def q(c,n): return c.execute('select name from sqlite_master where type="table" and name=?',(n,)).fetchone()
def main():
 if os.environ.get('INCIDENT_REPLAY_REPAIRED') != '1': raise RuntimeError('UNREPAIRED_REPLAY')
 p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 if not os.path.exists(a.input): raise RuntimeError('input missing')
 d=a.output+'.tmp-'+str(os.getpid());
 try:
  s=sqlite3.connect(a.input);s.row_factory=sqlite3.Row
  if not q(s,'raw_events'): raise RuntimeError('raw_events missing')
  dcon=sqlite3.connect(d);dcon.execute('pragma foreign_keys=on'); c=dcon.cursor()
  c.executescript('''create table archival_events(source_id text primary key,occurred_at text,original_actor text,canonical_actor text,kind text,payload text,source text,seq integer,correlation_key text);create table incidents(incident_id text primary key,correlation_key text,owner text, state text, created_at text);create table incident_events(incident_id text,event_id text primary key,position integer,actor text,kind text);create table transitions(incident_id text,position integer,event_id text,state text,actor text,policy_version text,primary key(incident_id,position));create table sla_windows(incident_id text,position integer,event_id text,ack_minutes integer,resolve_minutes integer,primary key(incident_id,position));create table replay_audit(name text primary key,value text);''')
  aliases=[dict(x) for x in s.execute('select * from actor_aliases') ] if q(s,'actor_aliases') else []
  policies=[dict(x) for x in s.execute('select * from policy_versions')] if q(s,'policy_versions') else []
  ev=[dict(x) for x in s.execute('select * from raw_events order by id')]
  def actor(x,t):
   z=[a for a in aliases if a.get('alias')==x and (not a.get('valid_from') or iso(a['valid_from'])<=t) and (not a.get('valid_to') or t<iso(a['valid_to']))]
   return sorted(z,key=lambda y:(iso(y.get('valid_from')),str(y.get('canonical'))))[-1]['canonical'] if z else x
  rows=[]
  for e in ev:
   t=iso(e.get('occurred_at')); ca=actor(e.get('actor'),t); payload=e.get('payload') or '{}'; rows.append((str(e['id']),t,e.get('actor'),ca,e.get('kind'),payload,e.get('source'),e.get('seq'),e.get('correlation_key')))
  c.executemany('insert into archival_events values (?,?,?,?,?,?,?,?,?)',rows)
  groups={}; merges={}
  for e in ev:
   k=e.get('correlation_key') or '' ; x=j(e.get('payload')); merges.setdefault(k,set()).update([x['merge']] if x.get('merge') else [])
  for e,r in zip(ev,rows):
   k=e.get('correlation_key') or ''; groups.setdefault(k,[]).append((e,r))
  # merge components transitively
  changed=True
  while changed:
   changed=False
   for k,ms in list(merges.items()):
    for z in list(ms):
     if z in groups and z!=k: groups.setdefault(k,[]).extend(groups.pop(z)); merges[k]|=merges.pop(z,set());changed=True
  def order(es):
   by={str(e['id']):e for e,r in es}; deps={x:set(str(e.get('depends_on') or '').split(','))-{'','None','null'} for x,e in by.items()}; deps={x:{z for z in ds if z in by} for x,ds in deps.items()}; out=[]
   while by:
    ready=[x for x in by if not(deps[x]&set(by))]; x=min(ready or list(by),key=lambda z:(by[z].get('seq') is None,by[z].get('seq') if by[z].get('seq') is not None else 0,iso(by[z].get('occurred_at')),z));out.append(by.pop(x));
   return out
  for n,(k,es) in enumerate(sorted(groups.items())):
   oo=order(es); iid='inc-'+hashlib.sha256(k.encode()).hexdigest()[:16]; c.execute('insert into incidents values (?,?,?,?,?)',(iid,k, '', 'open',min(iso(e.get('occurred_at')) for e in oo)))
   survivors={str(e['id']):e for e in oo}; dead=set()
   for e in oo:
    x=j(e.get('payload')); ref=x.get('supersedes') or x.get('corrects')
    if ref in survivors: dead.add(str(ref))
    if x.get('tombstone') and x.get('tombstone') in survivors: dead.add(str(x['tombstone']))
   pos=0
   for e in oo:
    eid=str(e['id']);
    if eid in dead: continue
    pos+=1;t=iso(e.get('occurred_at')); pol=sorted([p for p in policies if (not p.get('effective_from') or iso(p['effective_from'])<=t) and (not p.get('effective_to') or t<iso(p['effective_to']))],key=lambda p:iso(p.get('effective_from')))[-1] if policies else {'version':'default','ack_minutes':0,'resolve_minutes':0}
    state='resolved' if e.get('kind') in ('resolve','resolved') else ('acknowledged' if e.get('kind') in ('ack','acknowledge') else 'open')
    c.execute('insert into incident_events values (?,?,?,?,?)',(iid,eid,pos,actor(e.get('actor'),t),e.get('kind')));c.execute('insert into transitions values (?,?,?,?,?,?)',(iid,pos,eid,state,actor(e.get('actor'),t),pol.get('version')));c.execute('insert into sla_windows values (?,?,?,?,?)',(iid,pos,eid,pol.get('ack_minutes',0),pol.get('resolve_minutes',0)))
  for table in ['archival_events','incidents','incident_events','transitions','sla_windows']:
   rows2=[tuple(x) for x in c.execute('select * from '+table+' order by rowid')]; h=hashlib.sha256(json.dumps(rows2,separators=(',',':'),default=str).encode()).hexdigest();c.execute('insert into replay_audit values (?,?)',(table,h))
  dcon.commit();dcon.close();s.close();os.replace(d,a.output)
 except Exception:
  try: os.unlink(d)
  except: pass
  raise
if __name__=='__main__':
 try:main()
 except Exception as e: print('replay failed:',e,file=sys.stderr);sys.exit(1)
