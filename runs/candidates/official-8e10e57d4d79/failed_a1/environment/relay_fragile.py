#!/usr/bin/env python3
import socket,struct,urllib.request, json
from protocol import MAGIC,readvar
s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); s.bind(('0.0.0.0',9100)); s.listen(8)
while True:
 c,_=s.accept()
 while True:
  x=c.recv(65536)
  if not x: break
  if not x.startswith(MAGIC) or len(x)<12: continue
  n=struct.unpack('>I',x[4:8])[0]; b=x[8:8+n]; p=1
  try:
   def st():
    nonlocal_dummy=0
    z,p2=readvar(b,p); return b[p2:p2+z].decode(),p2+z
   ident,p=st(); seq,p=readvar(b,p); ts,p=readvar(b,p); ts=ts//2 if ts%2==0 else -(ts//2)-1
   m={}; q,p=readvar(b,p)
   for _ in range(q): k,p=st(); v,p=readvar(b,p); m[k]=v//2 if v%2==0 else -(v//2)-1
   meta={}; q,p=readvar(b,p)
   for _ in range(q): k,p=st(); v,p=st(); meta[k]=v
   body=json.dumps({'identifier':ident,'sequence':seq,'timestamp':ts,'measurements':m,'metadata':meta}).encode()+b'\n'
   req=urllib.request.Request('http://127.0.0.1:9200/events',body=body,method='POST'); urllib.request.urlopen(req,timeout=2).read()
  except Exception: pass
