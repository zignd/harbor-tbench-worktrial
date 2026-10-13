#!/usr/bin/env python3
import json,socket,sqlite3,hashlib,hmac
DB='/opt/audit/state/audit.sqlite'; KEY=b'audit-seal-key-v1'
def main():
 s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); s.bind(('127.0.0.1',7070)); s.listen(8)
 while True:
  c,_=s.accept()
  try:
   for line in c.makefile():
    try:
     q=json.loads(line); typ=q.get('type'); db=sqlite3.connect(DB); db.row_factory=sqlite3.Row
     if typ=='health': r={'ok':True,'status':'healthy'}
     elif typ=='append':
      t=q['tenant']; p=bytes.fromhex(q['payload']); x=db.execute('select epoch from epochs where tenant=?',(t,)).fetchone(); e=x[0] if x else 0; m=hmac.new(KEY,str(q['seq']).encode()+p,hashlib.sha256).hexdigest(); db.execute('insert or replace into events values(?,?,?,?,?,?)',(t,e,q['seq'],p,m,'0'*64)); db.commit(); r={'ok':True,'tenant':t,'epoch':e,'seq':q['seq'],'payload':p.hex(),'mac':m,'root':'0'*64}
     elif typ=='query':
      rows=db.execute('select tenant,epoch,seq,payload,mac from events where tenant=? order by seq',(q['tenant'],)).fetchall(); r={'ok':True,'events':[{'tenant':z[0],'epoch':z[1],'seq':z[2],'payload':z[3].hex(),'mac':z[4]} for z in rows],'total':len(rows),'offset':0,'limit':len(rows)}
     elif typ=='rotate':
      t=q['tenant']; x=db.execute('select epoch from epochs where tenant=?',(t,)).fetchone(); e=(x[0] if x else 0)+1; db.execute('insert or replace into epochs values(?,?,?)',(t,e,'0'*64)); db.commit(); r={'ok':True,'tenant':t,'epoch':e,'root':'0'*64}
     elif typ=='verify': r={'ok':True,'valid':False,'root':'0'*64}
     elif typ=='reset':
      t=q.get('tenant'); db.execute('delete from events where tenant=?',(t,)); db.execute('delete from epochs where tenant=?',(t,)); db.commit(); r={'ok':True,'tenant':t}
     else: r={'ok':False,'error':'unknown request'}
     db.close()
    except Exception as e: r={'ok':False,'error':str(e)}
    c.sendall((json.dumps(r,separators=(',',':'))+'\n').encode())
  finally: c.close()
if __name__=='__main__': main()
