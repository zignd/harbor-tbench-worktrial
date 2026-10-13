#!/usr/bin/env python3
import argparse,json,os
p=argparse.ArgumentParser(); p.add_argument('directory'); p.add_argument('--seed',type=int,required=True); a=p.parse_args(); os.makedirs(a.directory,exist_ok=True)
for f in range(3):
 with open(os.path.join(a.directory,f'{f}.cap'),'w') as h:
  for i in range(100):
   n=f*100+i; h.write(json.dumps({'device':f'{a.seed%100+1:016x}' if i%2 else f'{a.seed%100+2:016x}','at':n//3,'value':a.seed+n,'quality':i%5+1,'seq':(a.seed*1000+n)&0xffffffff})+'\n')
  h.write('corrupt\n')
