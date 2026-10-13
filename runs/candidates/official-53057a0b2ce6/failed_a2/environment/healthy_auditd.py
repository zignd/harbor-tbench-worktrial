#!/usr/bin/env python3
import base64, hashlib, hmac, json, os, socket, sqlite3, struct, threading
DB='/opt/audit/state/audit.sqlite'
HOST='127.0.0.1'; PORT=7070

def enc(v):
    b=v if isinstance(v,bytes) else str(v).encode()
    return struct.pack('>I',len(b))+b

def key(tenant,epoch):
    return hashlib.sha256(('audit-epoch:'+tenant+':'+str(epoch)).encode()).digest()

def event_bytes(tenant,epoch,seq,payload):
    return enc(tenant)+struct.pack('>Q',int(epoch))+struct.pack('>Q',int(seq))+enc(payload)

def mac(tenant,epoch,seq,payload):
    return hmac.new(key(tenant,epoch),event_bytes(tenant,epoch,seq,payload),hashlib.sha256).digest()

def root(rows):
    r=b''
    for tenant,epoch,seq,payload,m in rows:
        mm=mac(tenant,epoch,seq,payload)
        r=hashlib.sha256(r+mm).digest()
    return r

def b64(v): return base64.b64encode(v).decode()
def unb(v): return base64.b64decode(v,validate=True)

class Service:
  def __init__(self):
    self.lock=threading.RLock(); self.rebuild()
  def db(self):
    d=sqlite3.connect(DB,timeout=30); d.row_factory=sqlite3.Row; return d
  def rebuild(self):
    with self.lock:
      d=self.db()
      d.execute('CREATE TABLE IF NOT EXISTS events(tenant TEXT NOT NULL, epoch INTEGER NOT NULL, seq INTEGER NOT NULL, payload BLOB NOT NULL, mac BLOB NOT NULL, PRIMARY KEY(tenant,epoch,seq))')
      d.execute('CREATE TABLE IF NOT EXISTS epochs(tenant TEXT NOT NULL, epoch INTEGER NOT NULL, root BLOB NOT NULL, PRIMARY KEY(tenant,epoch))')
      rows=d.execute('SELECT tenant,epoch,seq,payload FROM events ORDER BY tenant,epoch,seq').fetchall()
      groups={}
      for x in rows: groups.setdefault((x['tenant'],x['epoch']),[]).append(x)
      for (t,e),rs in groups.items():
        rr=b''
        for x in rs:
          mm=mac(t,e,x['seq'],bytes(x['payload'])); rr=hashlib.sha256(rr+mm).digest()
          d.execute('UPDATE events SET mac=? WHERE tenant=? AND epoch=? AND seq=?',(mm,t,e,x['seq']))
        d.execute('INSERT INTO epochs(tenant,epoch,root) VALUES(?,?,?) ON CONFLICT(tenant,epoch) DO UPDATE SET root=excluded.root',(t,e,rr))
      d.commit(); d.close()
  def verify(self,t,e=None):
    d=self.db(); q='SELECT tenant,epoch,seq,payload,mac FROM events WHERE tenant=?'; args=[t]
    if e is not None: q+=' AND epoch=?'; args.append(int(e))
    q+=' ORDER BY epoch,seq'
    rows=d.execute(q,args).fetchall(); bad=False; by={}
    meta=d.execute('SELECT epoch,root FROM epochs WHERE tenant=? ORDER BY epoch',(t,)).fetchall()
    roots={str(x['epoch']):b64(bytes(x['root'])) for x in meta}
    for x in rows:
      mm=mac(x['tenant'],x['epoch'],x['seq'],bytes(x['payload'])); bad |= not hmac.compare_digest(mm,bytes(x['mac'])); by.setdefault(x['epoch'],[]).append((x['tenant'],x['epoch'],x['seq'],bytes(x['payload']),mm))
    for k,v in by.items(): roots[str(k)]=b64(root(v))
    d.close(); return not bad,roots
  def handle(self,q):
    typ=q.get('type')
    if typ=='health': return {'ok':True,'service':'auditd','port':7070}
    with self.lock:
      if typ=='append':
        t=str(q['tenant']); e=int(q.get('epoch',0)); s=int(q['seq']); p=unb(q.get('payload_b64',''))
        m=mac(t,e,s,p); d=self.db()
        try:
          d.execute('INSERT INTO events VALUES(?,?,?,?,?)',(t,e,s,p,m)); d.execute('INSERT INTO epochs(tenant,epoch,root) VALUES(?,?,?) ON CONFLICT(tenant,epoch) DO NOTHING',(t,e,b'')); d.commit()
        except Exception: d.rollback(); raise
        ok,rs=self.verify(t,e); d=self.db(); rr=base64.b64decode(rs[str(e)]); d.execute('UPDATE epochs SET root=? WHERE tenant=? AND epoch=?',(rr,t,e)); d.commit(); d.close()
        return {'ok':True,'tenant':t,'epoch':e,'seq':s,'mac_b64':b64(m),'root_b64':b64(rr)}
      if typ=='query':
        t=str(q['tenant']); sql='SELECT tenant,epoch,seq,payload,mac FROM events WHERE tenant=?'; a=[t]
        if 'epoch' in q: sql+=' AND epoch=?'; a.append(int(q['epoch']))
        if 'min_seq' in q: sql+=' AND seq>=?'; a.append(int(q['min_seq']))
        if 'max_seq' in q: sql+=' AND seq<=?'; a.append(int(q['max_seq']))
        if 'payload_prefix_b64' in q: sql+=' AND substr(payload,1,?)=?'; x=unb(q['payload_prefix_b64']); a.extend([len(x),x])
        d=self.db(); total=d.execute('SELECT COUNT(*) FROM ('+sql+')',a).fetchone()[0]; off=int(q.get('offset',0)); lim=int(q.get('limit',100)); rows=d.execute(sql+' ORDER BY epoch ASC,seq ASC LIMIT ? OFFSET ?',a+[lim,off]).fetchall(); d.close()
        ev=[{'tenant':x['tenant'],'epoch':x['epoch'],'seq':x['seq'],'payload_b64':b64(bytes(x['payload'])),'mac_b64':b64(bytes(x['mac']))} for x in rows]
        return {'ok':True,'events':ev,'total':total,'offset':off,'limit':lim}
      if typ=='verify':
        t=str(q['tenant']); ok,rs=self.verify(t,q.get('epoch')); out={'ok':True,'valid':ok,'tenant':t,'roots':rs};
        if q.get('epoch') is not None: out['root_b64']=rs.get(str(int(q['epoch'])),b64(b''))
        return out
      if typ=='rotate':
        t=str(q['tenant']); old=int(q.get('epoch',q.get('from_epoch',0))); new=int(q.get('new_epoch',old+1)); d=self.db(); d.execute('INSERT INTO epochs(tenant,epoch,root) VALUES(?,?,?) ON CONFLICT(tenant,epoch) DO NOTHING',(t,new,b'')); d.commit(); d.close(); return {'ok':True,'tenant':t,'from_epoch':old,'epoch':new,'root_b64':b64(b'')}
      if typ=='reset':
        t=str(q['tenant']); d=self.db(); d.execute('DELETE FROM events WHERE tenant=?',(t,)); d.execute('DELETE FROM epochs WHERE tenant=?',(t,)); d.commit(); d.close(); return {'ok':True,'tenant':t}
    raise ValueError('unknown request type')

def _client(c,svc):
 try:
  f=c.makefile('rwb')
  for line in f:
   try:
    out=svc.handle(json.loads(line))
   except Exception as e:
    out={'ok':False,'error':str(e)}
   try:
    f.write((json.dumps(out,separators=(',',':'))+'\n').encode()); f.flush()
   except Exception:
    break
 except Exception:
  pass
 finally:
  try: c.close()
  except Exception: pass

def serve():
 svc=Service(); s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); s.bind((HOST,PORT)); s.listen(30)
 while True:
  try:
   c,_=s.accept(); threading.Thread(target=_client,args=(c,svc),daemon=True).start()
  except Exception:
   continue
if __name__=='__main__': serve()
