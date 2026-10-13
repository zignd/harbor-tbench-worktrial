#!/usr/bin/env python3
import sqlite3,sys,hashlib,hmac,struct,os
P=2**127-1
def enc(e,s,p,a,x): return struct.pack('>QQ',e,s)+bytes.fromhex(p)+struct.pack('>I',len(a.encode()))+a.encode()+struct.pack('>I',len(x.encode()))+x.encode()
def mac(k,e,s,p,a,x): return hmac.new(k,enc(e,s,p,a,x),hashlib.sha256).hexdigest()
def make(path,seed=17,epochs=2,n=6):
 if os.path.exists(path): os.unlink(path)
 d=sqlite3.connect(path);c=d.cursor();c.executescript('''CREATE TABLE epochs(epoch INTEGER PRIMARY KEY,prime TEXT,threshold INTEGER,commitment TEXT);CREATE TABLE shares(epoch INTEGER,x INTEGER,y TEXT);CREATE TABLE accounts(account TEXT PRIMARY KEY,description TEXT);CREATE TABLE events(event_id TEXT PRIMARY KEY,account TEXT,epoch INTEGER,sequence INTEGER,predecessor TEXT,payload TEXT,mac TEXT);CREATE TABLE anchors(epoch INTEGER,event_id TEXT);CREATE TABLE checkpoints(epoch INTEGER,sequence INTEGER,event_id TEXT,signature TEXT);CREATE TABLE incident_metadata(name TEXT,value TEXT);''')
 for ep in range(1,epochs+1):
  scalar=int.from_bytes(hashlib.sha256(f'{seed}:key:{ep}'.encode()).digest(),'big')%P;key=scalar.to_bytes(32,'big');c.execute('insert into epochs values(?,?,?,?)',(ep,str(P),3,hashlib.sha256(str(scalar).encode()).hexdigest()));co=[scalar,(seed+ep*13)%P,(seed*7+ep*19)%P]
  for i,x in enumerate(range(1,7)): c.execute('insert into shares values(?,?,?)',(ep,x,str((sum(co[j]*x**j for j in range(3))%P)+(1234567 if i==(seed+ep)%6 else 0))))
  a=f'account-{ep}';c.execute('insert into accounts values(?,?)',(a,'incident account'));prev='';ids=[]
  for s in range(n):
   eid=f'e{ep}-{s}-main';payload=f'payload-{seed}-{ep}-{s}';c.execute('insert into events values(?,?,?,?,?,?,?)',(eid,a,ep,s,prev,payload,mac(key,ep,s,prev,a,payload)));ids.append(eid);prev=hashlib.sha256(eid.encode()).hexdigest()
  c.execute('insert into anchors values(?,?)',(ep,ids[0]));sig=hmac.new(key,f'checkpoint|{ep}|{n-1}|{ids[-1]}'.encode(),hashlib.sha256).hexdigest();c.execute('insert into checkpoints values(?,?,?,?)',(ep,n-1,ids[-1],sig))
  if n>3:
   p=hashlib.sha256(ids[1].encode()).hexdigest();c.execute('insert into events values(?,?,?,?,?,?,?)',(f'e{ep}-fork',a,ep,2,p,'fork',mac(key,ep,2,p,a,'fork')))
  c.execute('insert into events values(?,?,?,?,?,?,?)',(f'e{ep}-orphan',a,ep,1,'00'*32,'orphan',mac(key,ep,1,'00'*32,a,'orphan')))
 d.commit();d.close()
if __name__=='__main__': make(sys.argv[1],*(map(int,sys.argv[2:])) if len(sys.argv)>2 else (17,2,6))
