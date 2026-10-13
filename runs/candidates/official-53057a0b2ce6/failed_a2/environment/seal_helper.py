#!/usr/bin/env python3
import sys,socket,os,json,base64,hashlib,hmac,threading
path=sys.argv[1] if len(sys.argv)>1 else '/tmp/seal-helper.sock'
try: os.unlink(path)
except FileNotFoundError: pass
s=socket.socket(socket.AF_UNIX); s.bind(path); s.listen(20)
def key(t,e): return hashlib.sha256(('audit-epoch:'+t+':'+str(e)).encode()).digest()
def work(c):
    f=c.makefile('rwb')
    for line in f:
      try:
       q=json.loads(line); k=key(q['tenant'],int(q['epoch'])); data=base64.b64decode(q.get('data',''))
       out={'ok':True,'mac':base64.b64encode(hmac.new(k,data,hashlib.sha256).digest()).decode()}
      except Exception as e: out={'ok':False,'error':str(e)}
      f.write((json.dumps(out,separators=(',',':'))+'\n').encode()); f.flush()
    c.close()
while True:
 c,_=s.accept(); threading.Thread(target=work,args=(c,),daemon=True).start()
