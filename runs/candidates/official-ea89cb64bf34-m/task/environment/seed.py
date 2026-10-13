import os,sqlite3,struct,json,zlib
root='/var/lib/replay'; os.makedirs(root+'/segments',exist_ok=True)
for f in os.listdir(root+'/segments'): os.unlink(root+'/segments/'+f)
for p in (root+'/catalog.db',):
 try: os.unlink(p)
 except FileNotFoundError: pass
def frame(x):
 b=json.dumps(x,ensure_ascii=False,separators=(',',':')).encode(); return b'RPLY'+struct.pack('>I',len(b))+b+struct.pack('>I',zlib.crc32(b)&0xffffffff)
records=[{'type':'begin','tx':1},{'type':'put','tx':1,'tenant':'tenant-a','key':'config','value':'v1'},{'type':'commit','tx':1}, {'type':'begin','tx':2},{'type':'put','tx':2,'tenant':'tenant-a','key':'empty','value':''},{'type':'commit','tx':2},{'type':'begin','tx':3},{'type':'delete','tx':3,'tenant':'tenant-a','key':'config'},{'type':'commit','tx':3},{'type':'begin','tx':4},{'type':'put','tx':4,'tenant':'tenant-b','key':'ключ/one','value':'значение'},{'type':'commit','tx':4}]
open(root+'/segments/0001.seg','wb').write(b''.join(frame(x) for x in records))
con=sqlite3.connect(root+'/catalog.db'); con.execute('create table if not exists meta(k text primary key,v text)'); con.commit(); con.close()
