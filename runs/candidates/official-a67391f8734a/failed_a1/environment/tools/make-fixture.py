#!/usr/bin/env python3
import struct,sys

def crc(p):
 c=0xffffffff
 for b in p:
  c^=b
  for _ in range(8): c=(c>>1)^((0x82f63b78 if c&1 else 0))
 return (~c)&0xffffffff

def frame(seq,basis,eigs,x):
 m=len(eigs); n=len(x); p=struct.pack('<'+'d'*(m*n+m+n),*(sum(basis,[])+eigs+x))
 h=b'MAF2'+struct.pack('<HHIII',m,n,seq,len(p),0)
 return h+p+struct.pack('<I',crc(p))
if __name__=='__main__': sys.stdout.buffer.write(frame(1,[[1.]], [1.], [2.]))
