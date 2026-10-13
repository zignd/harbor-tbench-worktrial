MODALITIES={1:'spans',2:'counters',3:'checks',4:'logs'}
def decode(s):
 try:b=bytes.fromhex(s)
 except Exception:return None
 d={};i=0
 try:
  while i<len(b):
   t=b[i];i+=1;v=0;sh=0
   while True:
    if i>=len(b) or sh>63:return None
    q=b[i];i+=1;v|=(q&127)<<sh
    if q<128:break
    sh+=7
   if t in (2,3,5,6):v=(v>>1)^-(v&1)
   if t in (1,2,3,4,5,6):d[t]=v
 except Exception:return None
 if not all(k in d for k in (1,2,3,4)) or d[1] not in MODALITIES:return None
 d['modality']=MODALITIES[d[1]];return d
