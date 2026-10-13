#!/usr/bin/env python3
import sys,os,json,hashlib,hmac,struct,csv,random
D=sys.argv[1];N=int(sys.argv[2]) if len(sys.argv)>2 else 8;S=int(sys.argv[3]) if len(sys.argv)>3 else 7;os.makedirs(D,exist_ok=True)
m={'secret':'secret-'+str(S),'context':'context-'+str(S),'rotation':0};k=hashlib.sha256(m['secret'].encode()+b'\0'+m['context'].encode()).digest();rows=[];fs=[]
def e(p):return struct.pack('<I',len(p))+p+hmac.new(k,p,hashlib.sha256).digest()
for i in range(N):
 r=hashlib.sha256(('%d:%d'%(S,i)).encode()).digest()[:16];c=('USD','EUR','GBP')[i%3];t=str(10000+i).encode();d=('café%d'%i).encode();z=b'\0meta' if i==1 else b'x'*(i%5);p=r+b'T'+struct.pack('<q',100+3*i)+c.encode()+struct.pack('<H',len(t))+t+struct.pack('<H',len(d))+d+struct.pack('<H',len(z))+z+struct.pack('<I',0);fs.append((r,e(p)));rows.append((r.hex(),100+3*i,c))
for i in range(0,N,3):
 r=bytes.fromhex(rows[i][0]);a=hashlib.sha256(b'adj'+r).digest()[:16];p=a+b'A'+struct.pack('<q',5 if i%2==0 else -7)+b'USD'+b'\0'*6+r;fs.append((a,e(p)))
random.Random(S).shuffle(fs);json.dump(m,open(D+'/manifest.json','w'));open(D+'/spool.bin','wb').write(b''.join(x[1] for x in fs))
with open(D+'/bank.csv','w',newline='') as f:w=csv.writer(f);w.writerow(['reference','amount','currency']);w.writerows(rows)
