#!/usr/bin/env python3
import argparse, hashlib, json, os, shutil, sqlite3, sys, tempfile
from pathlib import Path

def ts(v):
    if v is None: return None
    s=str(v).strip()
    if s.endswith('+00:00'): s=s[:-6]+'Z'
    return s

def parse(v):
    return json.loads(v) if isinstance(v,str) and v.strip().startswith(('{','[')) else {}

def inside(t, lo, hi):
    return (lo is None or t >= ts(lo)) and (hi is None or t < ts(hi))

def fingerprint(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',',':')).encode()).hexdigest()

def replay(src, dest):
    if os.environ.get('INCIDENT_REPLAY_REPAIRED') != '1': raise RuntimeError('UNREPAIRED_REPLAY')
    if not os.path.exists(src): raise RuntimeError('input does not exist')
    check=sqlite3.connect(src)
    names={r[0] for r in check.execute("select name from sqlite_master where type='table'")}
    required={'raw_events','actor_aliases','policy_versions'}
    if not required <= names: raise RuntimeError('invalid input schema')
    raw=check.execute('select id,occurred_at,actor,kind,payload,source,seq,depends_on,correlation_key from raw_events').fetchall()
    aliases=check.execute('select alias,canonical,valid_from,valid_to from actor_aliases').fetchall()
    policies=check.execute('select version,effective_from,effective_to,ack_minutes,resolve_minutes from policy_versions').fetchall()
    check.close()
    events=[]
    for e in raw:
        eid,when,actor,kind,payload,source,seq,deps,corr=e
        when=ts(when); resolved=actor
        matches=[a for a in aliases if a[0]==actor and inside(when,a[2],a[3])]
        if matches: resolved=sorted(matches,key=lambda a:(ts(a[2]) if a[2] else '',str(a[1])))[-1][1]
        p=parse(payload)
        dep=[]
        if deps is not None and str(deps).strip(): dep += [x.strip() for x in str(deps).split(',') if x.strip()]
        if isinstance(p.get('depends_on'),str): dep += [x.strip() for x in p['depends_on'].split(',') if x.strip()]
        events.append({'id':str(eid),'at':when,'actor':actor,'resolved':resolved,'kind':kind,'payload':payload if payload is not None else '', 'source':str(source),'seq':seq,'deps':sorted(set(dep)),'corr':corr,'json':p})
    events.sort(key=lambda e:(e['source'], e['seq'] if e['seq'] is not None else 0, e['id']))
    byid={e['id']:e for e in events}
    parent={e['id']:e['id'] for e in events}
    def find(x):
        while parent[x]!=x: parent[x]=parent[parent[x]]; x=parent[x]
        return x
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b: parent[max(a,b)]=min(a,b)
    groups={}
    for e in events:
        key=str(e['corr'] or e['resolved'])
        groups.setdefault(key,[]).append(e)
        m=e['json'].get('merge')
        if m is not None: groups.setdefault(str(m),[]).append(e)
    for key, es in list(groups.items()):
        for e in es:
            if e['id'] not in parent: continue
            for f in es:
                if f['id'] != e['id']: union(e['id'],f['id'])
    comps={}
    for e in events: comps.setdefault(find(e['id']),[]).append(e)
    ordered=[]
    for root, es in sorted(comps.items(), key=lambda kv:min(x['id'] for x in kv[1])):
        ids={e['id'] for e in es}; indeg={x:0 for x in ids}; out={x:[] for x in ids}
        for e in es:
            for d in e['deps']:
                if d in ids and d != e['id']:
                    out[d].append(e['id']); indeg[e['id']]+=1
        done=[]; remaining=set(ids)
        def key(x):
            e=byid[x]; return (e['seq'] is None, e['seq'] if e['seq'] is not None else 0, e['at'] or '', x)
        while remaining:
            avail=sorted([x for x in remaining if indeg[x]==0], key=key)
            if not avail: avail=[min(remaining)]
            x=avail[0]; remaining.remove(x); done.append(x)
            for y in out[x]: indeg[y]-=1
        ordered.append((root,[byid[x] for x in done]))
    temp=dest+'.tmp-'+str(os.getpid())
    if os.path.exists(temp): os.unlink(temp)
    db=sqlite3.connect(temp); db.execute('pragma foreign_keys=on'); db.execute('begin')
    db.executescript('''create table archival_events(event_id text primary key,occurred_at text,original_actor text,resolved_actor text,payload text,source_id text,source_sequence integer,kind text,archived_at text);
create table incidents(incident_id text primary key,correlation_key text,opened_at text,resolved_at text,status text,owner text,event_count integer);
create table incident_events(incident_id text,event_id text,position integer,source_sequence integer,is_survivor integer,primary key(incident_id,event_id));
create table transitions(incident_id text,transition_no integer,event_id text,occurred_at text,from_state text,policy_version text,to_state text,actor text,details text,primary key(incident_id,transition_no));
create table sla_windows(incident_id text,window_no integer,starts_at text,ends_at text,policy_version text,target_seconds integer,elapsed_seconds integer,breached integer,primary key(incident_id,window_no));
create table replay_audit(audit_id text primary key,run_id text,incident_id text,event_count integer,input_fingerprint text,output_fingerprint text,warnings text,created_at text);''')
    for e in events: db.execute('insert into archival_events values (?,?,?,?,?,?,?,?,?)',(e['id'],e['at'],e['actor'],e['resolved'],e['payload'],e['source'],e['seq'],e['kind'],'1970-01-01T00:00:00Z'))
    allcanon=[]
    for root, es in ordered:
        iid=hashlib.sha256(('incident:'+','.join(sorted(e['id'] for e in es))).encode()).hexdigest()[:16]
        corr=sorted(str(e['corr'] or e['resolved']) for e in es)[0]
        survivors=[]; removed=set()
        for e in es:
            p=e['json']; target=p.get('supersedes') or p.get('corrects')
            if target and target in byid: removed.add(target)
            tomb=p.get('tombstone')
            if tomb and tomb in byid: removed.add(tomb)
        survivors=[e for e in es if e['id'] not in removed]
        opened=min((e['at'] for e in survivors), default=None); resolved=max((e['at'] for e in survivors), default=None)
        owner=survivors[-1]['resolved'] if survivors else None; status='resolved' if any(e['kind']=='resolve' for e in survivors) else 'open'
        db.execute('insert into incidents values (?,?,?,?,?,?,?)',(iid,corr,opened,resolved,status,owner,len(es)))
        for pos,e in enumerate(survivors): db.execute('insert into incident_events values (?,?,?,?,?)',(iid,e['id'],pos,e['seq'],1))
        state='new'; trno=0; last=None
        for e in survivors:
            pol=next((p for p in policies if inside(e['at'],p[1],p[2])),None)
            pv=pol[0] if pol else None
            new={'open':'open','ack':'ack','resolve':'resolved'}.get(e['kind'],state)
            if new != state:
                db.execute('insert into transitions values (?,?,?,?,?,?,?,?,?)',(iid,trno,e['id'],e['at'],state,pv,new,e['resolved'],e['payload'])); trno+=1; state=new
            last=e
        for i,e in enumerate(survivors):
            pol=next((p for p in policies if inside(e['at'],p[1],p[2])),None)
            if pol: db.execute('insert into sla_windows values (?,?,?,?,?,?,?,?)',(iid,i,e['at'],e['at'],pol[0],int(pol[4] or 0),0,0))
        allcanon.append((iid, len(es)))
    inp_fp=fingerprint([(e['id'],e['at'],e['payload']) for e in events])
    for iid,n in allcanon:
        outrows=list(db.execute('select * from transitions where incident_id=? order by transition_no',(iid,)))
        db.execute('insert into replay_audit values (?,?,?,?,?,?,?,?)',(hashlib.sha256(iid.encode()).hexdigest()[:16],inp_fp,iid,n,inp_fp,fingerprint(outrows),'','1970-01-01T00:00:00Z'))
    db.commit(); db.close(); os.replace(temp,dest)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--input',required=True); ap.add_argument('--output',required=True); a=ap.parse_args()
    try: replay(a.input,a.output)
    except Exception as e:
        print(str(e),file=sys.stderr); raise
if __name__=='__main__': main()
