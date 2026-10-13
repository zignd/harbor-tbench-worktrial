#!/usr/bin/env python3
import sys,json,os,struct,zlib,sqlite3,hashlib
BASE='/var/lib/replay'; DB=BASE+'/catalog.db'; SEG=BASE+'/segments'
def setup(c):
 c.executescript('''CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,tenant TEXT NOT NULL,key TEXT NOT NULL,value TEXT NOT NULL,op TEXT NOT NULL,tx INTEGER NOT NULL,pos INTEGER NOT NULL, UNIQUE(tx,pos,tenant,key,op)); CREATE TABLE IF NOT EXISTS live(tenant TEXT NOT NULL,key TEXT NOT NULL,value TEXT NOT NULL,PRIMARY KEY(tenant,key)); CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY,v TEXT NOT NULL);''')
def scan():
 found=[]
 for fn in sorted(os.listdir(SEG)):
  path=os.path.join(SEG,fn)
  if not os.path.isfile(path): continue
  data=open(path,'rb').read(); i=0
  while i+8<=len(data):
   n=struct.unpack('>I',data[i:i+4])[0]
   if n>64*1024*1024 or i+8+n>len(data): break
   payload=data[i+4:i+4+n]; crc=struct.unpack('>I',data[i+4+n:i+8+n])[0]
   if zlib.crc32(payload)&0xffffffff != crc: break
   try: e=json.loads(payload.decode('utf-8'))
   except Exception: break
   i += n+8
   if e.get('commit') and e.get('op') in ('put','delete') and all(k in e for k in ('tenant','key','tx','pos')): found.append(e)
 return sorted(found,key=lambda e:(int(e['tx']),int(e['pos']),str(e['tenant']),str(e['key'])))
def digest(c):
 live=c.execute('select tenant,key,value from live order by tenant,key').fetchall(); ev=c.execute('select tenant,key,value,op,tx,pos from events order by id').fetchall()
 return hashlib.sha256(json.dumps({'live':live,'events':ev},ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def recover(c):
 events=scan(); c.execute('BEGIN IMMEDIATE')
 try:
  c.execute('delete from events'); c.execute('delete from live')
  for e in events:
   value=e.get('value','')
   c.execute('insert into events(tenant,key,value,op,tx,pos) values(?,?,?,?,?,?)',(e['tenant'],e['key'],value,e['op'],int(e['tx']),int(e['pos'])))
   if e['op']=='put': c.execute('insert or replace into live values(?,?,?)',(e['tenant'],e['key'],value))
   else: c.execute('delete from live where tenant=? and key=?',(e['tenant'],e['key']))
  d=digest(c); gen=max((int(e['tx']) for e in events),default=0)
  c.execute('delete from meta'); c.executemany('insert into meta values(?,?)',[('generation',str(gen)),('checksum',d)]); c.commit()
 except: c.rollback(); raise
 return events,d
def response(q,c):
 op=q.get('op')
 if op=='recover':
  es,d=recover(c); return {'ok':True,'replayed':len(es),'generation':max((int(e['tx']) for e in es),default=0),'checksum':d}
 if op=='get':
  r=c.execute('select value from live where tenant=? and key=?',(q['tenant'],q['key'])).fetchone(); return {'ok':True,'value':r[0] if r else None}
 if op=='list':
  p=q.get('prefix',''); rows=c.execute('select key,value from live where tenant=? and key>=? and key<? order by key',(q['tenant'],p,p+chr(0x10ffff))).fetchall(); return {'ok':True,'items':[{'key':k,'value':v} for k,v in rows]}
 if op in ('put','delete'):
  c.execute('BEGIN IMMEDIATE')
  try:
   tx=c.execute('select coalesce(max(tx),0)+1 from events').fetchone()[0]; val=q.get('value',''); typ='put' if op=='put' else 'delete'
   c.execute('insert into events(tenant,key,value,op,tx,pos) values(?,?,?,?,?,?)',(q['tenant'],q['key'],val,typ,tx,tx))
   if typ=='put': c.execute('insert or replace into live values(?,?,?)',(q['tenant'],q['key'],val))
   else: c.execute('delete from live where tenant=? and key=?',(q['tenant'],q['key']))
   d=digest(c); c.execute('insert or replace into meta values(?,?)',('generation',str(tx))); c.execute('insert or replace into meta values(?,?)',('checksum',d)); c.commit(); return {'ok':True}
  except: c.rollback(); raise
 if op=='stats':
  return {'ok':True,'live':c.execute('select count(*) from live where tenant=?',(q['tenant'],)).fetchone()[0],'events':c.execute('select count(*) from events where tenant=?',(q['tenant'],)).fetchone()[0]}
 if op=='manifest':
  g=c.execute("select v from meta where k='generation'").fetchone(); d=c.execute("select v from meta where k='checksum'").fetchone(); return {'ok':True,'generation':int(g[0]) if g else 0,'checksum':d[0] if d else digest(c)}
 if op=='audit':
  rows=c.execute('select key,value,op,tx from events where tenant=? order by id',(q['tenant'],)).fetchall(); return {'ok':True,'events':[{'key':a,'value':b,'op':d,'tx':e} for a,b,d,e in rows]}
 return {'ok':False,'error':'unknown operation'}
def main():
 c=sqlite3.connect(DB); setup(c)
 for line in sys.stdin:
  try: print(json.dumps(response(json.loads(line),c),ensure_ascii=False,separators=(',',':')),flush=True)
  except Exception as e: print(json.dumps({'ok':False,'error':str(e)},separators=(',',':')),flush=True)
if __name__=='__main__': main()
