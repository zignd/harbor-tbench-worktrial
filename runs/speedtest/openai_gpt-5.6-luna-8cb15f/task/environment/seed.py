import os,struct
F='/var/log/telemetry/frontend'; B='/var/log/telemetry/backend'
os.makedirs(F,exist_ok=True); os.makedirs(B,exist_ok=True)
front=[(1000,'r1','10.0.0.1','/a',200,100),(2000,'r2','10.0.0.2','/a',502,200),(3000,'r3','10.0.0.3','/b',200,120),(4000,'r4','10.0.0.4','/a',200,100)]
open(F+'/access.tsv','w').write(''.join('\t'.join(map(str,x))+'\n' for x in front))
recs=[(1,'/a',0,1020,50),(1,'/a',1,2050,80),(2,'/b',0,3040,60)]
with open(B+'/pack.bpack','wb') as f:
 f.write(struct.pack('<4sBBHQ',b'BPK1',1,0,len(recs),1000)); prev=1000
 for w,e,x,s,d in recs:
  eb=e.encode(); f.write(struct.pack('<HBBiI',w,len(eb),x,s-prev,d)+eb); prev=s
