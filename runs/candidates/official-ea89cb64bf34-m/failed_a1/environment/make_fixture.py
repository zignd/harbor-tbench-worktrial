import os,sqlite3,struct,json,zlib
base='/var/lib/replay'; seg=base+'/segments'; os.makedirs(seg,exist_ok=True)
def f(x):
 b=json.dumps(x,ensure_ascii=False,separators=(',',':')).encode(); return b'SEG1'+struct.pack('>I',len(b))+b+struct.pack('>I',zlib.crc32(b)&0xffffffff)
rows=[
 {'tx':'1','order':1,'tenant':'tenant-a','key':'config','value':'enabled','op':'put','commit':True},
 {'tx':'2','order':2,'tenant':'tenant-a','key':'gone','value':'old','op':'put','commit':True},
 {'tx':'3','order':3,'tenant':'tenant-a','key':'gone','value':'','op':'delete','commit':True},
 {'tx':'4','order':4,'tenant':'tenant-a','key':'empty/key','value':'','op':'put','commit':True},
 {'tx':'5','order':5,'tenant':'tenant-b','key':'雪/雪','value':'välue','op':'put','commit':True},
 {'tx':'6','order':6,'tenant':'tenant-a','key':'config','value':'bad','op':'put','commit':False}]
open(seg+'/0001.seg','wb').write(b''.join(map(f,rows))+b'SEG1\x00'); open(seg+'/empty.seg','wb').close()
c=sqlite3.connect(base+'/catalog.db'); c.execute('create table if not exists seed(x)'); c.commit(); c.close()
