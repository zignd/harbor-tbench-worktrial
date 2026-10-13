#!/usr/bin/env python3
import json,socket,sqlite3,hashlib,hmac
DB='/opt/audit/state/audit.sqlite'
KEY=b'audit-seal-key-v1'
def encode(t,e,n,p):
 b=t.encode(); return len(b).to_bytes(4,'big')+b+int(e).to_bytes(8,'big')+int(n).to_bytes(8,'big')+len(p).to_bytes(8,'big')+p
def mac(t,e,n,p): return hmac.new(KEY,encode(t,e,n,p),hashlib.sha256).hexdigest()
def root(rows):
 r=bytes(32)
 for t,e,n,p,m in rows: r=hashlib.sha256(r+bytes.fromhex(m)).digest()
 return r.hex()
def setup(db):
 db.execute('create table if not exists events(tenant text,epoch integer,seq integer,payload blob,mac text,root text,primary key(tenant,epoch,seq))')
 db.execute('create table if not exists epochs(tenant text primary key,epoch integer,root text)'); db.commit()
def handle(q):
 db=sqlite3.connect(DB); db.row_factory=sqlite3.Row; setup(db); typ=q.get('type')
 if typ=='health': out={'ok':True,'status':'healthy'}
 elif typ=='reset':
  t=q.get('tenant')
  if t is None: raise ValueError('tenant required')
  db.execute('delete from events where tenant=?',(t,)); db.execute('delete from epochs where tenant=?',(t,)); db.commit(); out={'ok':True,'tenant':t}
 elif typ=='append':
  t=q['tenant']; n=int(q['seq']); p=bytes.fromhex(q['payload']); x=db.execute('select epoch from epochs where tenant=?',(t,)).fetchone(); e=int(x[0]) if x else 0
  m=mac(t,e,n,p); rows=db.execute('select tenant,epoch,seq,payload,mac from events where tenant=?',(t,)).fetchall(); db.execute('insert or replace into events values(?,?,?,?,?,?)',(t,e,n,p,m,'0'*64)); allrows=db.execute('select tenant,epoch,seq,payload,mac from events where tenant=? order by epoch,seq',(t,)).fetchall(); rr=[(z['tenant'],z['epoch'],z['seq'],z['payload'],z['mac']) for z in allrows]; rt=root(rr); db.execute('update events set root=? where tenant=?',(rt,t)); db.execute('insert or replace into epochs values(?,?,?)',(t,e,rt)); db.commit(); out={'ok':True,'tenant':t,'epoch':e,'seq':n,'payload':p.hex(),'mac':m,'root':rt}
 elif typ=='query':
  t=q['tenant']; w=['tenant=?']; a=[t]
  if q.get('epoch') is not None: w.append('epoch=?'); a.append(int(q['epoch']))
  if q.get('seq_min') is not None: w.append('seq>=?'); a.append(int(q['seq_min']))
  if q.get('seq_max') is not None: w.append('seq<=?'); a.append(int(q['seq_max']))
  if q.get('prefix') is not None: p=bytes.fromhex(q['prefix']); w.append('substr(payload,1,?)=?'); a += [len(p),p]
  rows=db.execute('select tenant,epoch,seq,payload,mac from events where '+' and '.join(w)+' order by epoch,seq',a).fetchall(); off=int(q.get('offset',0)); lim=int(q.get('limit',len(rows))); out={'ok':True,'events':[{'tenant':z['tenant'],'epoch':z['epoch'],'seq':z['seq'],'payload':z['payload'].hex(),'mac':z['mac']} for z in rows[off:off+lim]],'total':len(rows),'offset':off,'limit':lim}
 elif typ=='rotate':
  t=q['tenant']; x=db.execute('select epoch,root from epochs where tenant=?',(t,)).fetchone(); e=int(x['epoch'])+1 if x else 1; rt=x['root'] if x else '0'*64; db.execute('insert or replace into epochs values(?,?,?)',(t,e,rt)); db.commit(); out={'ok':True,'tenant':t,'epoch':e,'root':rt}
 elif typ=='verify':
  t=q['tenant']; rows=db.execute('select tenant,epoch,seq,payload,mac from events where tenant=? order by epoch,seq',(t,)).fetchall(); good=True; rr=[]
  for z in rows:
   good=good and hmac.compare_digest(mac(z['tenant'],z['epoch'],z['seq'],z['payload']),z['mac']); rr.append((z['tenant'],z['epoch'],z['seq'],z['payload'],z['mac']))
  rt=root(rr); x=db.execute('select epoch,root from epochs where tenant=?',(t,)).fetchone(); good=good and (x is None or x['root']==rt or not rows); out={'ok':True,'valid':bool(good),'root':rt,'epoch':int(x['epoch']) if x else 0}
 else: out={'ok':False,'error':'unknown request'}
 db.close(); return out
def main():
 setup(sqlite3.connect(DB)); s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); s.bind(('127.0.0.1',7070)); s.listen(20)
 while True:
  c,_=s.accept()
  try:
   for line in c.makefile():
    try: out=handle(json.loads(line))
    except Exception as e: out={'ok':False,'error':str(e)}
    c.sendall((json.dumps(out,separators=(',',':'))+'\n').encode())
  finally: c.close()
if __name__=='__main__': main()
