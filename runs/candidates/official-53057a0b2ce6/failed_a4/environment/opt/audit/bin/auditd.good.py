#!/usr/bin/env python3
import socketserver,json,sqlite3,base64,hashlib,hmac,struct
DB='/opt/audit/state/audit.sqlite'
def key(e):return hashlib.sha256(('epoch-key:'+str(e)).encode()).digest()
def mac(t,e,s,p):return hmac.new(key(e),t.encode()+struct.pack('>I',e)+struct.pack('>Q',s)+struct.pack('>I',len(p))+p,hashlib.sha256).hexdigest()
def trans(t,o,n):return hmac.new(key(o),t.encode()+struct.pack('>II',o,n),hashlib.sha256).hexdigest()
def db():
 c=sqlite3.connect(DB);c.execute('create table if not exists events(tenant text,epoch integer,seq integer,payload blob,mac text,primary key(tenant,epoch,seq))');c.execute('create table if not exists transitions(tenant text,old_epoch integer,new_epoch integer,transition text,primary key(tenant,old_epoch,new_epoch))');return c
def root(c,t,e):
 r=b'\0'*32
 for s,p,m in c.execute('select seq,payload,mac from events where tenant=? and epoch=? order by seq asc',(t,e)):
  if not hmac.compare_digest(m,mac(t,e,int(s),bytes(p))):raise ValueError('invalid MAC')
  r=hashlib.sha256(r+bytes.fromhex(m)).digest()
 return r.hex()
class H(socketserver.StreamRequestHandler):
 def handle(self):
  for line in self.rfile:
   try:
    q=json.loads(line);c=db();typ=q['type']
    if typ=='health':o={'ok':True,'service':'auditd'}
    elif typ=='append':
     t=str(q['tenant']);e=int(q['epoch']);s=int(q['seq']);p=base64.b64decode(q['payload'],validate=True);m=mac(t,e,s,p);c.execute('insert or replace into events values(?,?,?,?,?)',(t,e,s,p,m));c.commit();o={'ok':True,'tenant':t,'epoch':e,'seq':s,'payload':base64.b64encode(p).decode(),'mac':m,'root':root(c,t,e)}
    elif typ=='query':
     t=str(q['tenant']);w=['tenant=?'];a=[t]
     for k,x in [('epoch','epoch=?'),('seq_min','seq>=?'),('seq_max','seq<=?')]:
      if k in q:w.append(x);a.append(int(q[k]))
     z=c.execute('select tenant,epoch,seq,payload,mac from events where '+' and '.join(w)+' order by seq asc',a).fetchall()
     if 'prefix' in q:z=[x for x in z if bytes(x[3]).startswith(base64.b64decode(q['prefix'],validate=True))]
     total=len(z);off=max(0,int(q.get('offset',0)));lim=max(0,int(q.get('limit',100)));z=z[off:off+lim];o={'ok':True,'events':[{'tenant':x[0],'epoch':x[1],'seq':int(x[2]),'payload':base64.b64encode(bytes(x[3])).decode(),'mac':x[4]} for x in z],'total':total,'offset':off,'limit':lim}
    elif typ=='verify':
     t=str(q['tenant']);es=[x[0] for x in c.execute('select distinct epoch from events where tenant=?',(t,))];o={'ok':True,'valid':True,'tenant':t,'roots':{str(e):root(c,t,e) for e in es}}
    elif typ=='rotate':
     t=str(q['tenant']);e=int(q['epoch']);n=int(q['new_epoch']);z=trans(t,e,n);c.execute('insert or replace into transitions values(?,?,?,?)',(t,e,n,z));c.commit();o={'ok':True,'tenant':t,'old_epoch':e,'new_epoch':n,'transition':z,'root':root(c,t,e)}
    elif typ=='reset':
     if q.get('scope')=='tenant':c.execute('delete from events where tenant=?',(q['tenant'],));c.execute('delete from transitions where tenant=?',(q['tenant'],))
     else:c.execute('delete from events');c.execute('delete from transitions')
     c.commit();o={'ok':True,'roots':{}}
    self.wfile.write((json.dumps(o,separators=(',',':'))+'\n').encode());self.wfile.flush();c.close()
   except Exception as e:self.wfile.write((json.dumps({'ok':False,'error':str(e)})+'\n').encode());self.wfile.flush()
class S(socketserver.ThreadingTCPServer):allow_reuse_address=True
S(('127.0.0.1',7070),H).serve_forever()
