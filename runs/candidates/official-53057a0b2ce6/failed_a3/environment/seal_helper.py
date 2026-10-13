#!/usr/bin/env python3
import base64,hmac,hashlib,json,os,socket,struct
SOCK='/tmp/seal-helper.sock'; MASTER=b'audit-sealing-key-v1'
def key(t,e): return hmac.new(MASTER,(str(t)+'|'+str(e)).encode(),hashlib.sha256).digest()
def main():
 try: os.unlink(SOCK)
 except FileNotFoundError: pass
 s=socket.socket(socket.AF_UNIX);s.bind(SOCK);s.listen(16)
 while True:
  c,_=s.accept()
  with c:
   f=c.makefile('r')
   for line in f:
    try:
     q=json.loads(line); t=q.get('tenant','');e=int(q.get('epoch',0)); raw=base64.b64decode(q.get('data',''))
     if q.get('op')=='mac': v=hmac.new(key(t,e),raw,hashlib.sha256).hexdigest()
     elif q.get('op')=='transition': v=hmac.new(key(t,e),b'transition'+struct.pack('>I',int(q.get('new_epoch',e+1))),hashlib.sha256).hexdigest()
     else: raise ValueError('unknown operation')
     c.sendall((json.dumps({'ok':True,'mac':v,'signature':v})+'\n').encode())
    except Exception as ex:c.sendall((json.dumps({'ok':False,'error':str(ex)})+'\n').encode())
if __name__=='__main__': main()
