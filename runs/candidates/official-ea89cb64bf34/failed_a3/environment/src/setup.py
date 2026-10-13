import os,sys,json,struct,zlib
root=sys.argv[1]; os.makedirs(root+'/segments',exist_ok=True)
def frame(x):
 b=json.dumps(x,ensure_ascii=False,separators=(',',':')).encode(); return struct.pack('<I',len(b))+b+struct.pack('<I',zlib.crc32(b)&0xffffffff)
def seg(name,items): open(root+'/segments/'+name,'wb').write(b''.join(frame(x) for x in items))
seg('0001.seg',[
 {'tenant':'tenant-a','key':'config','value':'v1','op':'put','tx':1,'pos':0,'committed':True},
 {'tenant':'tenant-a','key':'gone','value':'x','op':'put','tx':2,'pos':0,'committed':True},
 {'tenant':'tenant-a','key':'gone','value':'','op':'delete','tx':3,'pos':0,'committed':True},
 {'tenant':'tenant-b','key':'unicode/☃','value':'значение','op':'put','tx':4,'pos':0,'committed':True},
])
seg('0002.seg',[
 {'tenant':'tenant-a','key':'config','value':'v2','op':'put','tx':5,'pos':0,'committed':True},
 {'tenant':'tenant-a','key':'empty','value':'','op':'put','tx':6,'pos':0,'committed':True},
 {'tenant':'tenant-a','key':'aborted','value':'bad','op':'put','tx':7,'pos':0,'committed':False},
])
open(root+'/segments/empty.seg','wb').close()
