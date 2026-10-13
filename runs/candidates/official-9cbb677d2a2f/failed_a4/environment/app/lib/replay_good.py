import sqlite3,sys,os,json,hashlib,tempfile

def qv(x): return x if x is not None else None
def key(e): return (e['occurred_at'] or '', int(e['source_seq'] or 0), e['source'] or '', int(e['id']))
def main(src,dst):
    if not os.path.exists(src): raise RuntimeError('input does not exist')
    si=sqlite3.connect(src); si.row_factory=sqlite3.Row
    try:
        raw=[dict(x) for x in si.execute('select id,source,source_seq,occurred_at,actor,correlation,event_type,payload,depends_on,correction_of,supersedes from raw_events order by id')]
        aliases=[dict(x) for x in si.execute('select alias,canonical_actor,valid_from,valid_to from actor_aliases')]
        policies=[dict(x) for x in si.execute('select version,effective_from,effective_to,ack_minutes,resolve_minutes from policy_versions')]
    finally: si.close()
    for e in raw:
        e['resolved_actor']=e['actor']
        for a in aliases:
            if a['alias']==e['actor'] and a['valid_from']<=e['occurred_at'] and (a['valid_to'] is None or e['occurred_at']<a['valid_to']):
                e['resolved_actor']=a['canonical_actor']; break
        try: e['json']=json.loads(e['payload']) if e['payload'] else {}
        except Exception: e['json']={}
    n=len(raw); parent=list(range(n))
    def find(x):
        while parent[x]!=x: parent[x]=parent[parent[x]]; x=parent[x]
        return x
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b: parent[b]=a
    bycorr={}
    for i,e in enumerate(raw): bycorr.setdefault(e['correlation'] or '',[]).append(i)
    for xs in bycorr.values():
        for x in xs[1:]: union(xs[0],x)
    ids={e['id']:i for i,e in enumerate(raw)}
    for i,e in enumerate(raw):
        m=e['json'].get('merge_into')
        if m is not None and m in ids: union(i,ids[m])
    groups={}
    for i,e in enumerate(raw): groups.setdefault(find(i),[]).append(e)
    rows=[]
    for e in raw:
        rows.append((e['id'],e['source'],e['source_seq'],e['occurred_at'],e['actor'],e['resolved_actor'],e['correlation'],e['event_type'],e['payload'],e['depends_on'],e['correction_of'],e['supersedes']))
    outdir=os.path.dirname(os.path.abspath(dst)) or '.'
    fd,tmp=tempfile.mkstemp(prefix='.replay-',suffix='.sqlite',dir=outdir); os.close(fd)
    try:
        co=sqlite3.connect(tmp); co.execute('pragma foreign_keys=on')
        co.executescript('''create table archival_events(source_id integer primary key,source text,source_seq integer,occurred_at text,original_actor text,resolved_actor text,correlation text,event_type text,payload text,depends_on text,correction_of text,supersedes text); create table incidents(incident_id text primary key,correlation text,opened_at text,resolved_at text,final_state text); create table incident_events(incident_id text,source_id integer,ordinal integer,primary key(incident_id,source_id)); create table transitions(incident_id text,ordinal integer,source_id integer,state text,actor text,policy_version text,occurred_at text,primary key(incident_id,ordinal)); create table sla_windows(incident_id text,source_id integer,policy_version text,start_at text,end_at text,primary key(incident_id,source_id)); create table replay_audit(incident_id text primary key,event_count integer,digest text);''')
        co.executemany('insert into archival_events values (?,?,?,?,?,?,?,?,?,?,?,?)',rows)
        for root,es in sorted(groups.items(),key=lambda z:min(key(x) for x in z[1])):
            es=sorted(es,key=key); ids2={e['id']:e for e in es}; adj={e['id']:set() for e in es}; indeg={e['id']:0 for e in es}
            for e in es:
                val=e['depends_on']
                deps=[] if val is None or val=='' else [x.strip() for x in str(val).split(',') if x.strip()]
                for d in deps:
                    try: d=int(d)
                    except: continue
                    if d in ids2 and e['id'] not in adj[d]: adj[d].add(e['id']); indeg[e['id']]+=1
            remain=set(ids2); order=[]
            while remain:
                ready=sorted([x for x in remain if indeg[x]==0],key=lambda i:key(ids2[i]))
                if not ready:
                    ready=[min(remain,key=lambda i:key(ids2[i]))]
                x=ready[0]; remain.remove(x); order.append(ids2[x])
                for y in adj[x]: indeg[y]-=1
            logical={e['id']:e for e in order}; dead=set()
            for e in order:
                typ=(e['event_type'] or '').lower(); target=e['correction_of'] or e['supersedes'] or e['json'].get('target')
                try: target=int(target) if target is not None and str(target).strip() else None
                except (TypeError,ValueError): target=None
                if typ in ('tombstone','delete') and target is not None: dead.add(target)
                elif target is not None and target in logical:
                    dead.add(target); logical[target]=e
                    replacement=e['json'].get('event_type') or e['json'].get('state')
                    if replacement: e['event_type']=replacement
            effective=[e for e in order if e['id'] not in dead and (e['event_type'] or '').lower() not in ('tombstone','delete','correction','supersede')]
            inc='inc-'+hashlib.sha256(('|'.join(str(e['id']) for e in sorted(es,key=lambda x:x['id']))).encode()).hexdigest()[:16]
            corr=sorted({e['correlation'] or '' for e in es})[0]; opened=min((e['occurred_at'] for e in effective),default=min(e['occurred_at'] for e in es)); state='open'; transitions=[]; slas=[]
            for ordinal,e in enumerate(order): co.execute('insert into incident_events values (?,?,?)',(inc,e['id'],ordinal))
            for e in effective:
                typ=(e['event_type'] or '').lower()
                if typ=='ack': state='acknowledged'
                elif typ=='resolve': state='resolved'
                elif typ=='reopen': state='open'
                pol=next((p for p in policies if p['effective_from']<=e['occurred_at'] and (p['effective_to'] is None or e['occurred_at']<p['effective_to'])),None)
                pv=pol['version'] if pol else None
                transitions.append((inc,len(transitions),e['id'],state,e['resolved_actor'],pv,e['occurred_at']))
                slas.append((inc,e['id'],pv,e['occurred_at'],e['occurred_at']))
            resolved=max((e['occurred_at'] for e in effective if (e['event_type'] or '').lower()=='resolve'),default=None)
            co.execute('insert into incidents values (?,?,?,?,?)',(inc,corr,opened,resolved,state)); co.executemany('insert into transitions values (?,?,?,?,?,?,?)',transitions); co.executemany('insert into sla_windows values (?,?,?,?,?)',slas)
            digest=hashlib.sha256(json.dumps(transitions,separators=(',',':'),sort_keys=False).encode()).hexdigest(); co.execute('insert into replay_audit values (?,?,?)',(inc,len(es),digest))
        co.commit(); co.close(); os.replace(tmp,dst)
    except Exception:
        try: os.unlink(tmp)
        except OSError: pass
        raise

if __name__=='__main__':
    try: main(sys.argv[1],sys.argv[2])
    except Exception as e: print('replay failed:',e,file=sys.stderr); sys.exit(1)
