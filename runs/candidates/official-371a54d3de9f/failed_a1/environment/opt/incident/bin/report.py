#!/usr/bin/env python3
import sqlite3,sys,itertools,hmac,hashlib,struct
P=2**127-1
def enc(e,s,p,a,x): return struct.pack('>QQ',e,s)+bytes.fromhex(p)+struct.pack('>I',len(a.encode()))+a.encode()+struct.pack('>I',len(x.encode()))+x.encode()
def mac(k,e,s,p,a,x): return hmac.new(k,enc(e,s,p,a,x),hashlib.sha256).hexdigest()
def rec(q):
 z=0
 for i,(x,y) in enumerate(q):
  n=m=1
  for j,(u,v) in enumerate(q):
   if i!=j:n=n*(-u)%P;m=m*(x-u)%P
  z=(z+y*n*pow(m,-1,P))%P
 return z
def main(db,out):
 d=sqlite3.connect(db);d.row_factory=sqlite3.Row;ans=[]
 for ep in d.execute('select * from epochs order by epoch'):
  sh=[(int(r['x']),int(r['y'])) for r in d.execute('select x,y from shares where epoch=?',(ep['epoch'],))];keys=[]
  for q in itertools.combinations(sh,int(ep['threshold'])):
   k=rec(q)
   if hashlib.sha256(str(k).encode()).hexdigest()==ep['commitment']:keys.append(k.to_bytes(32,'big'))
  if not keys:continue
  key=keys[0];rows=list(d.execute('select * from events where epoch=?',(ep['epoch'],)));valid={}
  for r in rows:
   try:
    if hmac.compare_digest(mac(key,r['epoch'],r['sequence'],r['predecessor'],r['account'],r['payload']),r['mac']):valid[r['event_id']]=r
   except Exception: pass
  ar=d.execute('select event_id from anchors where epoch=?',(ep['epoch'],)).fetchone(); children={}
  for r in valid.values():children.setdefault(r['predecessor'],[]).append(r)
  cps=list(d.execute('select * from checkpoints where epoch=?',(ep['epoch'],)));paths=[]
  def walk(r,path):
   if r['event_id'] in {x['event_id'] for x in path}:return
   p=path+[r]
   for cp in cps:
    sig=hmac.new(key,f"checkpoint|{ep['epoch']}|{r['sequence']}|{r['event_id']}".encode(),hashlib.sha256).hexdigest()
    if cp['event_id']==r['event_id'] and cp['sequence']==r['sequence'] and hmac.compare_digest(cp['signature'],sig):paths.append(p)
   for x in children.get(hashlib.sha256(r['event_id'].encode()).hexdigest(),[]):walk(x,p)
  if ar and ar[0] in valid:walk(valid[ar[0]],[])
  if paths: ans += [(int(r['epoch']),int(r['sequence']),r['event_id'],r['account']) for r in max(paths,key=len)]
 ans.sort(key=lambda x:(x[0],x[1],x[2]))
 with open(out,'w',encoding='utf-8',newline='\n') as f:
  for e,s,i,a in ans:f.write(f'{i}\t{a}\t{e}\t{s}\n')
if __name__=='__main__':main(sys.argv[1],sys.argv[2])
