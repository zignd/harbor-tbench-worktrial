#!/usr/bin/env python3
import base64,hashlib,hmac,json,os,sqlite3,socket,struct
DB='/opt/audit/state/audit.sqlite';MASTER=b'audit-sealing-key-v1'
def k(t,e): return hmac.new(MASTER,(str(t)+'|'+str(e)).encode(),hashlib.sha256).digest()
def canon(t,e,s,p,prev):
 tb=str(t).encode();return struct.pack('>I',len(tb))+tb+struct.pack('>I',int(e))+struct.pack('>Q',int(s))+struct.pack('>I',len(p))+p+prev
def cmac(t,e,s,p,prev): return hmac.new(k(t,e),canon(t,e,s,p,prev),hashlib.sha256).hexdigest()
def b64(x): return base64.b64decode(x) if isinstance(x,str) else bytes(x)
def rebuild(c,t,e):
 rows=c.execute('SELECT id,seq,payload FROM events WHERE tenant=? AND epoch=? ORDER BY seq ASC',(t,e)).fetchall();prev=b'';root='0'*64
 for i,s,p in rows:
  m=cmac(t,e,s,bytes(p),prev);root=hashlib.sha256(bytes.fromhex(m)).hexdigest();c.execute('UPDATE events SET mac=?,root=? WHERE id=?',(m,root,i));prev=bytes.fromhex(m)
 c.execute('INSERT INTO epochs(tenant,epoch,root) VALUES(?,?,?) ON CONFLICT(tenant,epoch) DO UPDATE SET root=excluded.root',(t,e,root));return root
def verify(c,t,e=None):
 es=[e] if e is not None else [x[0] for x in c.execute('SELECT DISTINCT epoch FROM events WHERE tenant=? ORDER BY epoch',(t,))];out=[];good=True
 for ep in es:
  rows=c.execute('SELECT seq,payload,mac,root FROM events WHERE tenant=? AND epoch=? ORDER BY seq',(t,ep)).fetchall();prev=b'';root='0'*64;ok=True
  for s,p,m,r in rows:
   want=cmac(t,ep,s,bytes(p),prev);root=hashlib.sha256(bytes.fromhex(want)).hexdigest();ok &= hmac.compare_digest(want,m) and hmac.compare_digest(root,r);prev=bytes.fromhex(want)
  meta=c.execute('SELECT root FROM epochs WHERE tenant=? AND epoch=?',(t,ep)).fetchone();ok &= meta is None or meta[0]==root;good &= ok;out.append({'epoch':ep,'root':root,'valid':ok})
 return good,out
def handle(q,c):
 typ=q.get('type',q.get('request'))
 if typ in ('health','ping'): return {'ok':True,'healthy':True}
 if typ=='reset':
  t=q.get('tenant');
  if t is None:c.execute('DELETE FROM events');c.execute('DELETE FROM epochs')
  else:c.execute('DELETE FROM events WHERE tenant=?',(str(t),));c.execute('DELETE FROM epochs WHERE tenant=?',(str(t),))
  c.commit();return {'ok':True}
 t=str(q.get('tenant',''))
 if typ=='append':
  e=int(q['epoch']);s=int(q['seq']);p=b64(q.get('payload',''));root=rebuild(c,t,e) if False else None
  prev=c.execute('SELECT mac FROM events WHERE tenant=? AND epoch=? ORDER BY seq DESC LIMIT 1',(t,e)).fetchone();pr=bytes.fromhex(prev[0]) if prev else b'';m=cmac(t,e,s,p,pr)
  c.execute('INSERT INTO events(tenant,epoch,seq,payload,mac,root) VALUES(?,?,?,?,?,?)',(t,e,s,p,m,'0'*64));root=rebuild(c,t,e);c.commit();row=c.execute('SELECT mac FROM events WHERE tenant=? AND epoch=? AND seq=?',(t,e,s)).fetchone();return {'ok':True,'tenant':t,'epoch':e,'seq':s,'mac':row[0],'root':root}
 if typ=='query':
  sql='SELECT epoch,seq,payload,mac,root FROM events WHERE tenant=?';a=[t]
  if 'epoch' in q:sql+=' AND epoch=?';a.append(int(q['epoch']))
  if 'min_seq' in q:sql+=' AND seq>=?';a.append(int(q['min_seq']))
  if 'max_seq' in q:sql+=' AND seq<=?';a.append(int(q['max_seq']))
  rows=c.execute(sql+' ORDER BY epoch ASC,seq ASC',a).fetchall();pref=q.get('payload_prefix');z=[]
  for e,s,p,m,r in rows:
   if pref is not None and not bytes(p).startswith(b64(pref)):continue
   z.append({'tenant':t,'epoch':e,'seq':s,'payload':base64.b64encode(bytes(p)).decode(),'mac':m,'root':r})
  off=int(q.get('offset',0));total=len(z);lim=q.get('limit');items=z[off:] if lim is None else z[off:off+int(lim)];return {'ok':True,'events':items,'total':total,'offset':off,'limit':None if lim is None else int(lim)}
 if typ=='verify':
  good,es=verify(c,t,int(q['epoch']) if 'epoch' in q else None);return {'ok':True,'valid':good,'verified':good,'epochs':es,'root':es[-1]['root'] if es else '0'*64}
 if typ=='rotate':
  old=int(q.get('epoch',0));new=int(q.get('new_epoch',old+1));good,es=verify(c,t,old);sig=hmac.new(k(t,old),b'transition'+struct.pack('>I',new),hashlib.sha256).hexdigest();return {'ok':good,'tenant':t,'from_epoch':old,'epoch':new,'root':es[0]['root'] if es else '0'*64,'signature':sig,'valid':good}
 return {'ok':False,'error':'unknown request'}
def main():
 c=sqlite3.connect(DB);c.text_factory=str
 listener=socket.socket(socket.AF_INET,socket.SOCK_STREAM);listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);listener.bind(('127.0.0.1',7070));listener.listen(32)
 while True:
  x,_=listener.accept()
  with x:
   for line in x.makefile():
    try:r=handle(json.loads(line),c);x.sendall((json.dumps(r,separators=(',',':'))+'\n').encode())
    except Exception as e:x.sendall((json.dumps({'ok':False,'error':str(e)})+'\n').encode())
if __name__=='__main__':main()
