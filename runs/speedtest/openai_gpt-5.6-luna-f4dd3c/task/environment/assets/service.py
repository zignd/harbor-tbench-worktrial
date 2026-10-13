#!/usr/bin/env python3
import argparse,hashlib,json,os,sqlite3,struct
from pathlib import Path

def read_env():
    out={}
    for line in Path('/etc/quant-reconcile/reconcile.env').read_text().splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            k,v=line.split('=',1); out[k.strip()]=v.strip()
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--batch-dir',required=True); args=ap.parse_args()
    e=read_env(); db=Path(e.get('DB_PATH','/var/lib/quant-reconcile/reconcile.db')); db.parent.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(str(db),timeout=max(5,float(e.get('BUSY_TIMEOUT','10000'))/1000)); con.execute('PRAGMA journal_mode=WAL'); con.execute('PRAGMA synchronous=NORMAL'); con.execute('PRAGMA busy_timeout=10000')
    con.executescript('CREATE TABLE IF NOT EXISTS batch_reconcile(batch_id TEXT PRIMARY KEY,worker_node TEXT,record_count INTEGER,mean_drift REAL,var_surface REAL,status TEXT,spool_checksum TEXT); CREATE TABLE IF NOT EXISTS anomaly_records(batch_id TEXT,trade_id TEXT,drift REAL,variance REAL,reason TEXT,PRIMARY KEY(batch_id,trade_id,reason)); CREATE TABLE IF NOT EXISTS worker_audit(worker_node TEXT PRIMARY KEY,batch_count INTEGER,record_count INTEGER,spool_checksums TEXT);')
    md=float(e.get('MAX_DRIFT','0.035')); vl=float(e.get('VAR_LIMIT','0.120')); audit={}
    for f in sorted(Path(args.batch_dir).iterdir()):
        if not f.is_file(): continue
        raw=f.read_bytes()
        if len(raw)<64 or (len(raw)-64)%64: raise ValueError('invalid spool')
        try: meta=json.loads(raw[:64].rstrip(b' '))
        except Exception: meta={}
        bid=meta.get('batch_id',f.stem); node=meta.get('worker_node',f.stem.split('_')[0]); records=[]
        for off in range(64,len(raw),64):
            tid,d,v,_=struct.unpack('<32sdd16s',raw[off:off+64]); records.append((tid.split(b'\0',1)[0].decode(),d,v))
        n=len(records); mean=sum(x[1] for x in records)/n if n else 0.0; var=sum(x[2] for x in records)/n if n else 0.0; anomalies=[]
        for tid,d,v in records:
            if abs(d)>md: anomalies.append((tid,d,v,'DRIFT'))
            if v>vl: anomalies.append((tid,d,v,'VARIANCE'))
        sha=hashlib.sha256(raw).hexdigest(); status='DISCREPANCY' if anomalies else 'MATCHED'
        con.execute('INSERT OR REPLACE INTO batch_reconcile VALUES(?,?,?,?,?,?,?)',(bid,node,n,mean,var,status,sha)); con.execute('DELETE FROM anomaly_records WHERE batch_id=?',(bid,)); con.executemany('INSERT OR REPLACE INTO anomaly_records VALUES(?,?,?,?,?)',[(bid,)+x for x in anomalies])
        a=audit.setdefault(node,[0,0,[]]); a[0]+=1; a[1]+=n; a[2].append(sha)
    for node,(bc,rc,sh) in audit.items(): con.execute('INSERT OR REPLACE INTO worker_audit VALUES(?,?,?,?)',(node,bc,rc,','.join(sorted(sh))))
    con.commit(); con.execute('PRAGMA wal_checkpoint(TRUNCATE)'); con.close()
if __name__=='__main__': main()
