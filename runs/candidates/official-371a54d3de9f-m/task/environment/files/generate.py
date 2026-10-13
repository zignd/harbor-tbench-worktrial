#!/usr/bin/env python3
import argparse,sqlite3,hashlib,hmac,itertools,random,os,csv
P=2305843009213693951; T=3

def hx(b): return hashlib.sha256(b).hexdigest()
def keybytes(k): return int(k).to_bytes(8,'big')
def msg(e,s,prev,a,p): return f'{e}:{s}:{prev}:{a}:{p}'.encode()
def mac(k,e,s,prev,a,p): return hmac.new(keybytes(k),msg(e,s,prev,a,p),hashlib.sha256).hexdigest()
def digest(e,s,prev,a,p): return hx(msg(e,s,prev,a,p))
def lag(x,ys):
 r=0
 for i,(xi,yi) in enumerate(zip(x,ys)):
  n=1; d=1
  for j,xj in enumerate(x):
   if i!=j: n=n*(-xj)%P; d=d*(xi-xj)%P
  r=(r+yi*n*pow(d,P-2,P))%P
 return r
def make(seed,epochs,events,out,exports):
 rng=random.Random(seed); os.makedirs(os.path.dirname(out) or '.',exist_ok=True)
 if exports: os.makedirs(exports,exist_ok=True)
 c=sqlite3.connect(out); c.executescript(open('/opt/incident/docs/schema.sql').read())
 accounts=['acct_'+chr(97+i) for i in range(max(3,epochs+1))]
 c.executemany('insert into accounts values(?,?)',[(a,'Incident account '+a) for a in accounts])
 for e in range(1,epochs+1):
  secret=rng.randrange(2,P-1); coeff=[secret,rng.randrange(1,P),rng.randrange(1,P)]
  shares=[]
  for sid in range(5+rng.randrange(3)):
   x=sid+1; y=sum(v*pow(x,i,P) for i,v in enumerate(coeff))%P; shares.append((e,sid,x,y))
  bad=rng.randrange(len(shares)); shares[bad]=(shares[bad][0],shares[bad][1],shares[bad][2],(shares[bad][3]+rng.randrange(1,1000))%P)
  rng.shuffle(shares)
  commit=hx(keybytes(secret)); anchor=hx(f'anchor:{e}:{seed}'.encode())
  c.execute('insert into epochs values(?,?,?,?,?,?)',(e,str(P),T,len(shares),commit,anchor)); c.executemany('insert into key_shares values(?,?,?,?)',shares); c.execute('insert into chain_anchors values(?,?)',(e,anchor))
  prev=anchor; good=[]
  n=events + (e-1)%3
  for s in range(n):
   a=accounts[(s+e)%len(accounts)]; p='payload-'+str(seed)+'-'+str(e)+'-'+str(s)+'-'+'x'*(s%5); d=digest(e,s,prev,a,p); m=mac(secret,e,s,prev,a,p); eid=f'E{e:02d}-{s:04d}-{seed}'
   good.append((eid,e,s,a,prev,p,m)); prev=d
  c.executemany('insert into audit_events values(?,?,?,?,?,?,?)',good)
  # authentic fork and orphan records
  if len(good)>3:
   g=good[1]; a=accounts[0]; p='fork'; fp=digest(e,2,g[4],a,p); c.execute('insert into audit_events values(?,?,?,?,?,?,?)',(f'F{e}-{seed}',e,2,a,g[4],p,mac(secret,e,2,g[4],a,p)))
  c.execute('insert into audit_events values(?,?,?,?,?,?,?)',(f'O{e}-{seed}',e,99,accounts[0],'00'*32,'orphan',mac(secret,e,99,'00'*32,accounts[0],'orphan')))
  end=good[-1]; sig=hmac.new(keybytes(secret),f'{e}:{end[2]}:{end[4] if False else digest(e,end[2],end[4],end[3],end[5])}'.encode(),hashlib.sha256).hexdigest()
  # signature covers terminal digest
  c.execute('insert into terminal_checkpoints values(?,?,?,?)',(e,end[2],digest(e,end[2],end[4],end[3],end[5]),sig))
 c.execute('insert into incident_metadata values(?,?)',('generator',str(seed))); c.commit()
 if exports:
  for t in ('epochs','key_shares','audit_events','chain_anchors','terminal_checkpoints'):
   rows=c.execute('select * from '+t); f=open(os.path.join(exports,t+'.csv'),'w',newline=''); w=csv.writer(f); w.writerows(rows); f.close()
 c.close()
if __name__=='__main__':
 q=argparse.ArgumentParser(); q.add_argument('--seed',type=int,required=True); q.add_argument('--epochs',type=int,default=2); q.add_argument('--events',type=int,default=8); q.add_argument('--out',required=True); q.add_argument('--exports'); a=q.parse_args(); make(a.seed,a.epochs,a.events,a.out,a.exports)
