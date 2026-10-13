#!/usr/bin/env python3
# Initial installation with legacy behavior.
import json,socket,sqlite3,base64,os
DB='/opt/audit/state/audit.sqlite'
def main():
 s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); s.bind(('127.0.0.1',7070)); s.listen(10)
 while True:
  c,_=s.accept(); f=c.makefile('rwb')
  for line in f:
   try:
    q=json.loads(line); typ=q.get('type'); db=sqlite3.connect(DB)
    if typ=='health': r={'ok':True,'service':'auditd'}
    elif typ=='query':
     rows=db.execute('SELECT tenant,epoch,seq,payload FROM events WHERE tenant=? ORDER BY seq LIMIT ? OFFSET ?', (q['tenant'],int(q.get('limit',100)),int(q.get('offset',0)))).fetchall(); r={'ok':True,'events':[{'tenant':a,'epoch':b,'seq':c,'payload_b64':base64.b64encode(d[:d.find(b"\\0")] if b"\\0" in d else d).decode()} for a,b,c,d in rows],'total':len(rows),'offset':q.get('offset',0),'limit':q.get('limit',100)}
    elif typ=='verify': r={'ok':True,'valid':False,'tenant':q.get('tenant'),'root_b64':''}
    elif typ in ('append','rotate','reset'): r={'ok':True}
    else: r={'ok':False,'error':'unknown request'}
    db.close()
   except Exception as e: r={'ok':False,'error':str(e)}
   f.write((json.dumps(r,separators=(',',':'))+'\n').encode()); f.flush()
if __name__=='__main__': main()
