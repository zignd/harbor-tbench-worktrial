#!/usr/bin/env python3
import argparse,json,os,random
p=argparse.ArgumentParser();p.add_argument('--seed',type=int,required=True);p.add_argument('--out',required=True);a=p.parse_args()
r=random.Random(a.seed); os.makedirs(a.out,exist_ok=True)
for old in os.listdir(a.out):
 if old.endswith('.cap'): os.unlink(os.path.join(a.out,old))
devs=[f'{(0x1000000000000000+i):016X}' for i in range(1+(a.seed%4))]
rows=[]
for i in range(900 if a.seed%2 else 420):
 d=devs[i%len(devs)]; seq=(0xFFFFFF00+i*7+a.seed*3)&0xffffffff; at=1000+(i*13)%1700
 rows.append({'device':d,'at':at,'value':(i*19+a.seed)%1000,'quality':(i*7+a.seed)%101,'source_sequence':seq})
 if i%83==0: rows.append(dict(rows[-1],quality=max(0,rows[-1]['quality']-20)))
# disappearance and equal timestamps are represented naturally by alternating devices
for j in range(3):
 fn=os.path.join(a.out,f'capture-{j}.cap');
 with open(fn,'w') as f:
  for row in rows[j::3]: f.write(json.dumps(row,separators=(',',':'))+'\n')
  f.write('corrupt padding\n')
