import struct,zlib
MAGIC=b'RFX2'
def put(n):
 if n<0: raise ValueError('unsigned varint')
 b=bytearray()
 while n>=128:b.append((n&127)|128);n>>=7
 b.append(n);return bytes(b)
def get(b,p):
 n=s=0
 while p<len(b):
  x=b[p];p+=1;n|=(x&127)<<s
  if x<128:return n,p
  s+=7
  if s>10000:raise ValueError('varint')
 raise ValueError('truncated')
def zz(n):return 2*n if n>=0 else -2*n-1
def sz(n):return zz(n)
def data(g,s,c,e):
 q=bytes([0])+put(g)+put(zz(s))+put(zz(c))+put(zz(e));return q+struct.pack('<I',zlib.crc32(q)&0xffffffff)
def parity(g,seqs,c,e):
 q=bytes([1])+put(g)+put(len(seqs))+b''.join(put(zz(x)) for x in seqs)+put(zz(c))+put(zz(e));return q+struct.pack('<I',zlib.crc32(q)&0xffffffff)
def archive(rows,group_size=3,corrupt=(),reverse=False,duplicates=0,truncate=False):
 fs=[];groups={}
 for i,(s,c,e) in enumerate(rows):
  g=i//group_size;groups.setdefault(g,[]).append(s);q=data(g,s,c,e);fs.append(put(len(q))+q)
 for g,ss in groups.items():
  c=e=0
  for s in ss:
   for _,cc,ee in [x for x in rows if x[0]==s]:c^=cc;e^=ee
  q=parity(g,ss,c,e);fs.append(put(len(q))+q)
 for i in corrupt:
  if i<len(fs):
   x=bytearray(fs[i]);x[-1]^=1;fs[i]=bytes(x)
 if duplicates:fs.extend(fs[:duplicates])
 if reverse:fs.reverse()
 out=MAGIC+b''.join(fs)
 return out[:-2] if truncate else out
