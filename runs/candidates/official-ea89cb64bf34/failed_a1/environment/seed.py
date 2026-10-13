import os,struct,json,zlib
D='/var/lib/replay/segments';os.makedirs(D,exist_ok=True)
def f(x):
 b=json.dumps(x,ensure_ascii=False,separators=(',',':')).encode();return struct.pack('>I',len(b))+b+struct.pack('>I',zlib.crc32(b)&0xffffffff)
e=[{'tx':1,'pos':1,'tenant':'tenant-a','key':'config','value':'enabled','op':'put','commit':1},{'tx':2,'pos':2,'tenant':'tenant-a','key':'gone','value':'x','op':'put','commit':1},{'tx':3,'pos':3,'tenant':'tenant-a','key':'gone','value':'','op':'delete','commit':1},{'tx':4,'pos':4,'tenant':'tenant-a','key':'empty/key','value':'','op':'put','commit':1},{'tx':5,'pos':5,'tenant':'tenant-b','key':'π','value':'значение','op':'put','commit':1},{'tx':6,'pos':6,'tenant':'tenant-a','key':'config','value':'later','op':'put','commit':1}]
open(D+'/001.seg','wb').write(b''.join(f(x) for x in e[:3]));open(D+'/002.seg','wb').write(b''.join(f(x) for x in e[3:]));open(D+'/empty.seg','wb').close()
