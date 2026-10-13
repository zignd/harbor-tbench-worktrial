#!/usr/bin/env python3
import argparse,json,struct,sys,zlib
from fractions import Fraction
sys.path.insert(0,'/opt/ledgerforge/lib')
from rfx import MAGIC,get

def fmt(x): return str(x.numerator) if x.denominator==1 else f'{x.numerator}/{x.denominator}'
def signed(n): return n//2 if n%2==0 else -(n//2)-1
def main():
 ap=argparse.ArgumentParser();ap.add_argument('archive');ap.add_argument('--out');a=ap.parse_args()
 try:
  raw=open(a.archive,'rb').read()
  if not raw.startswith(MAGIC):raise ValueError('invalid RFX header')
  p=4;rows=[];pars=[]
  while p<len(raw):
   n,q=get(raw,p)
   if q+n>len(raw):break
   x=raw[q:q+n];p=q+n
   if len(x)<5 or zlib.crc32(x[:-4])&0xffffffff!=struct.unpack('<I',x[-4:])[0]:continue
   r=1;k=x[0];g,r=get(x,r)
   if k==0:
    s,r=get(x,r);c,r=get(x,r);e,r=get(x,r)
    if r!=len(x)-4:continue
    rows.append((signed(s),signed(c),signed(e),g))
   elif k==1:
    count,r=get(x,r);ss=[]
    for _ in range(count):v,r=get(x,r);ss.append(signed(v))
    c,r=get(x,r);e,r=get(x,r)
    if r!=len(x)-4:continue
    pars.append((g,ss,signed(c),signed(e)))
  vals={};groups={}
  for s,c,e,g in rows:
   if s in vals and vals[s]!=(c,e):raise ValueError('conflicting duplicate')
   vals[s]=(c,e);groups.setdefault(g,[]).append(s)
  recovered=False
  for g,ss,pc,pe in pars:
   missing=[s for s in ss if s not in vals]
   if len(missing)>1:raise ValueError('observation is not recoverable')
   if len(missing)==1:
    c,e=pc,pe
    for s in groups.get(g,[]):c^=vals[s][0];e^=vals[s][1]
    vals[missing[0]]=(c,e);recovered=True
  expected={s for _,ss,_,_ in pars for s in ss}
  if expected and expected-set(vals):raise ValueError('observation is not recoverable')
  if not vals:raise ValueError('archive contains no observations')
  out=[];total=Fraction(0)
  for s,(c,e) in sorted(vals.items()):
   v=Fraction(c)*(10**e if e>=0 else Fraction(1,10**(-e)));total+=v;out.append({'seq':s,'value':fmt(v)})
  text=json.dumps({'records':out,'total':fmt(total),'status':'recovered' if recovered else 'complete'},ensure_ascii=False,separators=(',',':'))+'\n'
  if a.out:open(a.out,'w',encoding='utf-8').write(text)
  else:sys.stdout.write(text)
 except Exception as e:
  print('ERROR: '+str(e),file=sys.stderr);return 1
 return 0
if __name__=='__main__':sys.exit(main())
