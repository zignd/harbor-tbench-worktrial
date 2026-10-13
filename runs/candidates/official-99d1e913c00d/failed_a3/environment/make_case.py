#!/usr/bin/env python3
import sys,random,json,os
seed=int(sys.argv[1]) if len(sys.argv)>1 else 1; out=sys.argv[2] if len(sys.argv)>2 else '/opt/beacon/data'; random.seed(seed); os.makedirs(out,exist_ok=True)
devs=[f'{i:016X}' for i in range(1,5)]; rows=[]
for i in range(2500):
 d=random.choice(devs); rows.append({'device':d,'at':i//4,'value':round(random.random()*100,3),'quality':random.choice(['good','fair','poor']),'source_seq':(0xffffff00+i)&0xffffffff})
for j in range(3):
 with open(f'{out}/case{j}.cap','w') as f:
  for x in rows[j::3]: f.write(json.dumps(x)+'\n')
