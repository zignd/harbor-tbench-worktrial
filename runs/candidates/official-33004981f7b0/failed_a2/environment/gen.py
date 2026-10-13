#!/usr/bin/env python3
import csv,hashlib,hmac,json,os,random,struct,sys

def key(m): return hashlib.sha256(m['secret'].encode()+b'\0'+m['context'].encode()).digest()
def frame(p,k): return struct.pack('<I',len(p))+p+hmac.new(k,p,hashlib.sha256).digest()
def field(x): return struct.pack('<H',len(x))+x
def make_tx(ref,amount,currency,ident,desc,meta,rot):
 return ref+b'T'+struct.pack('<q',amount)+currency.encode()+field(ident)+field(desc)+field(meta)+struct.pack('<I',rot)
def make_adj(a,amount,target):
 return a+b'A'+struct.pack('<q',amount)+b'USD'+b'\0\0\0'+field(b'')+field(b'')+field(b'')+struct.pack('<I',0)+target
def main():
 if len(sys.argv)<2: raise SystemExit('usage: gen.py DIR [N] [SEED] [MODE]')
 d=sys.argv[1]; n=int(sys.argv[2]) if len(sys.argv)>2 else 8; seed=int(sys.argv[3]) if len(sys.argv)>3 else 7; mode=sys.argv[4] if len(sys.argv)>4 else 'normal'; os.makedirs(d,exist_ok=True)
 m={'secret':'secret-'+str(seed),'context':'context-'+str(seed),'rotation':1 if mode=='rotation' else 0}; k=key(m); rng=random.Random(seed); rows=[]; fs=[]
 for i in range(n):
  ref=hashlib.sha256(f'{seed}:{i}'.encode()).digest()[:16]
  ident=(f'DUP-{i%2}' if mode in ('duplicates','edges') else f'id-{i}').encode()
  desc=('München\x00record-%d'%i).encode() if mode in ('edges','binary') else f'description-{i}'.encode()
  meta=(b'' if i%3==0 else (b'Z'*65535 if mode=='edges' and i==n-1 else b'meta\0'+bytes([i & 255])))
  cur=('USD','EUR','GBP')[i%3]; amt=1000+i*17
  p=make_tx(ref,amt,cur,ident,desc,meta,m['rotation']); fs.append((ref,frame(p,k))); rows.append((ref.hex(),amt,cur))
 if mode in ('adjustments','edges','duplicates','normal','rotation'):
  for i in range(0,n,3):
   target=bytes.fromhex(rows[i][0]); ar=hashlib.sha256(b'adjustment'+target).digest()[:16]; val=-7 if i%2 else 5
   fs.append((ar,frame(make_adj(ar,val,target),k)))
 if mode=='malformed':
  target=bytes.fromhex(rows[0][0]); ar=b'X'*16; fs.append((ar,struct.pack('<I',100)+b'bad'))
 if mode=='tamper':
  target=bytes.fromhex(rows[0][0]); ar=hashlib.sha256(b'adjustment'+target).digest()[:16]; fs.append((ar,frame(make_adj(ar,3,target),k)[:-1]+b'X'))
 rng.shuffle(fs)
 with open(os.path.join(d,'spool.bin'),'wb') as f:
  for _,x in fs:f.write(x)
 with open(os.path.join(d,'bank.csv'),'w',newline='') as f:
  w=csv.writer(f);w.writerow(['reference','amount','currency']);w.writerows(rows)
 with open(os.path.join(d,'manifest.json'),'w') as f:json.dump(m,f,separators=(',',':'))
if __name__=='__main__':main()
