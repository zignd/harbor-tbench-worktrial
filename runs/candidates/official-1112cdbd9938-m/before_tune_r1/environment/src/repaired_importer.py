#!/usr/bin/env python3
import json, os, sqlite3, subprocess, sys
from datetime import datetime
DB = '/work/state/events.sqlite'
HELPER = '/opt/security/bin/addrclass'
WEIGHT = {'private': 2, 'public': 5, 'mapped': 7, 'special': 4, 'unknown': 9}
SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE events(event_id TEXT NOT NULL, revision INTEGER NOT NULL, timestamp TEXT NOT NULL,
 actor TEXT NOT NULL, source TEXT NOT NULL, destination TEXT NOT NULL, source_canonical TEXT NOT NULL,
 destination_canonical TEXT NOT NULL, source_class TEXT NOT NULL, destination_class TEXT NOT NULL,
 signature TEXT NOT NULL, risk INTEGER NOT NULL, severity TEXT NOT NULL,
 PRIMARY KEY(event_id,revision));
CREATE TABLE rejections(id INTEGER PRIMARY KEY, source_file TEXT NOT NULL, line_no INTEGER NOT NULL,
 event_id TEXT, revision INTEGER, reason TEXT NOT NULL, raw TEXT NOT NULL);
CREATE TABLE daily_summary(day TEXT PRIMARY KEY, event_count INTEGER NOT NULL, total_risk INTEGER NOT NULL,
 low_count INTEGER NOT NULL, medium_count INTEGER NOT NULL, high_count INTEGER NOT NULL);
CREATE TABLE actor_summary(actor TEXT PRIMARY KEY, event_count INTEGER NOT NULL, total_risk INTEGER NOT NULL);
CREATE TABLE indicator_summary(indicator TEXT PRIMARY KEY, event_count INTEGER NOT NULL, total_risk INTEGER NOT NULL);
CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE INDEX events_timestamp_idx ON events(timestamp);
CREATE INDEX events_actor_idx ON events(actor);
CREATE INDEX events_source_idx ON events(source_canonical);
CREATE INDEX events_destination_idx ON events(destination_canonical);
CREATE INDEX rejections_event_idx ON rejections(event_id);
'''

def helper(values):
    p = subprocess.run([HELPER], input=''.join(v+'\n' for v in values).encode('utf-8'), stdout=subprocess.PIPE, check=True)
    lines = p.stdout.decode('utf-8').splitlines()
    if len(lines) != len(values): raise ValueError('classifier_protocol')
    ans=[]
    for line in lines:
        if '\t' not in line: raise ValueError('classifier_protocol')
        kind, canonical = line.split('\t', 1)
        if not kind or canonical == '': raise ValueError('classifier_protocol')
        ans.append((kind, canonical))
    return ans

def valid_time(s):
    if not isinstance(s, str) or not s.endswith('Z'): return False
    try: datetime.fromisoformat(s[:-1] + '+00:00'); return True
    except Exception: return False

def reason_for(row):
    if not isinstance(row, dict): return 'invalid_record'
    for k in ('event_id','revision','timestamp','actor','source','destination','signature'):
        if k not in row: return 'missing_'+k
    if not isinstance(row['event_id'], str) or not row['event_id']: return 'invalid_event_id'
    if not isinstance(row['revision'], int) or isinstance(row['revision'], bool) or row['revision'] < 1: return 'invalid_revision'
    if not valid_time(row['timestamp']): return 'invalid_timestamp'
    if not isinstance(row['actor'], str): return 'invalid_actor'
    if not isinstance(row['source'], str) or not row['source']: return 'invalid_source'
    if not isinstance(row['destination'], str) or not row['destination']: return 'invalid_destination'
    if row['signature'] != 'valid': return 'signature_failed'
    return None

def main():
    os.makedirs('/work/state', exist_ok=True)
    tmp = DB + '.new'
    try: os.unlink(tmp)
    except FileNotFoundError: pass
    con = sqlite3.connect(tmp); con.executescript(SCHEMA)
    manifest = '/work/input/manifest.json'
    with open(manifest, encoding='utf-8') as f: spec=json.load(f)
    chunks = spec.get('chunks', [])
    records=[]; seen=set(); candidates={}
    for filename in chunks:
        path = os.path.join('/work/input', filename)
        with open(path, 'rb') as f:
            for line_no, rawb in enumerate(f, 1):
                raw = rawb.rstrip(b'\r\n')
                try: text=raw.decode('utf-8'); row=json.loads(text)
                except UnicodeDecodeError: records.append((filename,line_no,None,None,'invalid_utf8',raw.decode('utf8','replace'))); continue
                except Exception: records.append((filename,line_no,None,None,'malformed_json',raw.decode('utf8','replace'))); continue
                bad=reason_for(row)
                if bad: records.append((filename,line_no,row.get('event_id'),row.get('revision'),bad,text)); continue
                key=(row['event_id'],row['revision'])
                if key in seen: records.append((filename,line_no,row['event_id'],row['revision'],'duplicate_delivery',text)); continue
                seen.add(key); candidates.setdefault(row['event_id'], []).append((filename,line_no,row,text))
    accepted=[]
    for eid, vals in candidates.items():
        winner=max(vals, key=lambda z:z[2]['revision'])
        accepted.append(winner)
        for item in vals:
            if item is not winner:
                r=item[2]; records.append((item[0],item[1],eid,r['revision'],'superseded_revision',item[3]))
    accepted.sort(key=lambda z:(z[2]['event_id'], z[2]['revision']))
    for filename,line,row,text in accepted:
        try:
            (sc, scc), (dc, dcc) = helper([row['source'],row['destination']])
            risk=WEIGHT.get(sc,9)+WEIGHT.get(dc,9)+(row['revision']%3)
            sev='low' if risk<8 else ('medium' if risk<15 else 'high')
            con.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',(row['event_id'],row['revision'],row['timestamp'],row['actor'],row['source'],row['destination'],scc,dcc,sc,dc,row['signature'],risk,sev))
        except Exception:
            records.append((filename,line,row['event_id'],row['revision'],'classification_failed',text))
    for item in sorted(records, key=lambda x:(x[0],x[1],x[4])):
        con.execute('INSERT INTO rejections(source_file,line_no,event_id,revision,reason,raw) VALUES (?,?,?,?,?,?)',item)
    for r in con.execute('SELECT timestamp,risk,severity FROM events').fetchall():
        day=r[0][:10]; con.execute('INSERT INTO daily_summary VALUES (?,?,?,?,?,?) ON CONFLICT(day) DO UPDATE SET event_count=event_count+1,total_risk=total_risk+excluded.total_risk,low_count=low_count+excluded.low_count,medium_count=medium_count+excluded.medium_count,high_count=high_count+excluded.high_count',(day,1,r[1],int(r[2]=='low'),int(r[2]=='medium'),int(r[2]=='high')))
    for actor,count,risk in con.execute('SELECT actor,count(*),sum(risk) FROM events GROUP BY actor').fetchall():
        con.execute('INSERT INTO actor_summary VALUES (?,?,?)',(actor,count,risk))
    for indicator,count,risk in con.execute('SELECT indicator,count(*),sum(risk) FROM (SELECT source_canonical indicator,risk FROM events UNION ALL SELECT destination_canonical,risk FROM events) GROUP BY indicator').fetchall():
        con.execute('INSERT INTO indicator_summary VALUES (?,?,?)',(indicator,count,risk))
    con.execute("INSERT INTO metadata VALUES ('format','1')"); con.execute("INSERT INTO metadata VALUES ('accepted',?)",(str(con.execute('SELECT count(*) FROM events').fetchone()[0]),)); con.commit(); con.close(); os.replace(tmp,DB)
if __name__=='__main__': main()
