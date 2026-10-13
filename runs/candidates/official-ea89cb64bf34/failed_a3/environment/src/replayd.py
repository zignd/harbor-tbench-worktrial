#!/usr/bin/env python3
import sys,os,json,sqlite3,glob,hashlib,struct,zlib
ROOT=os.environ.get('REPLAY_ROOT','/var/lib/replay'); os.makedirs(ROOT+'/segments',exist_ok=True)
db=sqlite3.connect(ROOT+'/catalog.db',isolation_level=None); db.execute('pragma journal_mode=wal')
db.executescript('''create table if not exists objects(tenant text,key text,value text,primary key(tenant,key)); create table if not exists events(id integer primary key,tenant text,key text,value text,op text,tx integer,pos integer,unique(tx,pos,tenant,key,op)); create table if not exists meta(k text primary key,v text)''')
def frames(path):
 out=[]
 try: f=open(path,'rb')
 except OSError:return out
 with f:
  while True:
   h=f.read(4)
   if len(h)!=4: break
   n=struct.unpack('<I',h)[0]
   if n==0 or n>64*1024*1024: break
   b=f.read(n); c=f.read(4)
   if len(b)!=n or len(c)!=4 or (zlib.crc32(b)&0xffffffff)!=struct.unpack('<I',c)[0]: break
   try: x=json.loads(b.decode('utf-8'))
   except Exception: break
   if isinstance(x,dict): out.append(x)
 return out
def recover():
 files=sorted(glob.glob(ROOT+'/segments/*')); digest=hashlib.sha256(); marker=''
 for p in files:
  b=open(p,'rb').read();digest.update(b);marker+=os.path.basename(p)+':'+str(len(b))+';'
 old=db.execute("select v from meta where k='marker'").fetchone()
 if old and old[0]==marker:return
 allx=[]
 for p in files: allx += frames(p)
 groups={}
 for x in allx:
  try: groups.setdefault(int(x['tx']),[]).append(x)
  except Exception: pass
 db.execute('begin');
 try:
  db.execute('delete from objects');db.execute('delete from events')
  for tx in sorted(groups):
   es=groups[tx]
   if not any(e.get('committed') is True for e in es):continue
   for pos,e in enumerate(sorted(es,key=lambda q:int(q.get('pos',0)))):
    if e.get('op') not in ('put','delete'):continue
    t=str(e.get('tenant',''));k=str(e.get('key',''));v=str(e.get('value',''))
    db.execute('insert or ignore into events(tenant,key,value,op,tx,pos) values(?,?,?,?,?,?)',(t,k,v,e['op'],tx,int(e.get('pos',pos))))
    if e['op']=='put':db.execute('insert into objects values(?,?,?) on conflict(tenant,key) do update set value=excluded.value',(t,k,v))
    else:db.execute('delete from objects where tenant=? and key=?',(t,k))
  db.execute("insert into meta values('marker',?) on conflict(k) do update set v=excluded.v",(marker,));db.execute("insert into meta values('checksum',?) on conflict(k) do update set v=excluded.v",(digest.hexdigest(),));db.execute("insert into meta values('generation','1') on conflict(k) do update set v=excluded.v");db.commit()
 except Exception:db.rollback();raise
def mutate(q,op):
 t=str(q.get('tenant',''));k=str(q.get('key',''));v=str(q.get('value','')); row=db.execute('select coalesce(max(tx),0)+1 from events').fetchone();tx=row[0]
 db.execute('begin');
 try:
  db.execute('insert into events(tenant,key,value,op,tx,pos) values(?,?,?,?,?,0)',(t,k,v,op,tx))
  if op=='put':db.execute('insert into objects values(?,?,?) on conflict(tenant,key) do update set value=excluded.value',(t,k,v))
  else:db.execute('delete from objects where tenant=? and key=?',(t,k))
  db.commit()
 except Exception:db.rollback();raise
def answer(q):
 op=q.get('op');t=str(q.get('tenant',''));k=str(q.get('key',''))
 if op=='recover':recover();return {'ok':True}
 if op=='get':
  r=db.execute('select value from objects where tenant=? and key=?',(t,k)).fetchone();return {'ok':True,'found':r is not None,'value':r[0] if r else ''}
 if op=='list':return {'ok':True,'objects':[{'key':a,'value':b} for a,b in db.execute('select key,value from objects where tenant=? and key like ? escape "\\" order by key',(t,str(q.get('prefix',''))+'%'))]}
 if op in ('put','delete'):mutate(q,op);return {'ok':True}
 if op=='stats':return {'ok':True,'tenant':t,'live':db.execute('select count(*) from objects where tenant=?',(t,)).fetchone()[0],'events':db.execute('select count(*) from events where tenant=?',(t,)).fetchone()[0]}
 if op=='manifest':
  g=db.execute("select v from meta where k='generation'").fetchone();c=db.execute("select v from meta where k='checksum'").fetchone();return {'ok':True,'generation':int(g[0]) if g else 0,'checksum':c[0] if c else ''}
 if op=='audit':return {'ok':True,'events':[{'tenant':a,'key':b,'value':c,'op':d,'tx':e,'pos':f} for a,b,c,d,e,f in db.execute('select tenant,key,value,op,tx,pos from events where tenant=? order by tx,pos,id',(t,))]}
 return {'ok':False,'error':'unknown operation'}
for line in sys.stdin:
 try: print(json.dumps(answer(json.loads(line)),ensure_ascii=False,separators=(',',':')),flush=True)
 except Exception as e: print(json.dumps({'ok':False,'error':str(e)}),flush=True)
