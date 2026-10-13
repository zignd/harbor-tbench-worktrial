#!/usr/bin/env python3
import sys,json
from wire import decode

def main(src,dst):
    seen=set(); groups={}
    with open(src,encoding='utf8') as f:
        for line in f:
            try:
                x=json.loads(line); d=decode(x['payload'])
                if d is None or d['modality']!='spans' or d[4]!=0: continue
                if d[2] in seen: continue
                seen.add(d[2])
                z=groups.setdefault(('spans',x['stream']),[0,0,set(),[]])
                z[0]+=1; z[2].add(d.get(6,0)); z[3].append(d.get(5,0))
            except Exception:
                continue
    with open(dst,'w',encoding='utf8',newline='') as f:
        f.write('modality\tstream\ttotal\terrors\tunique_traces\tp50_duration\tp95_duration\n')
        for (m,s),z in sorted(groups.items()):
            a=sorted(z[3]); p50=a[(len(a)-1)//2]; p95=a[(95*len(a)+99)//100-1]
            f.write(f'{m}\t{s}\t{z[0]}\t0\t{len(z[2])}\t{p50}\t{p95}\n')
if __name__=='__main__': main(sys.argv[1],sys.argv[2])
