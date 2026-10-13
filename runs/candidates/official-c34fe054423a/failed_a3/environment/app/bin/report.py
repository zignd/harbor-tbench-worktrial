#!/usr/bin/env python3
import sys, struct, zlib
from fractions import Fraction

def u(data, i):
    x=0; s=0
    while i<len(data):
        b=data[i]; i+=1; x|=(b&127)<<s
        if b<128:return x,i
        s+=7
    raise ValueError('truncated varint')
def zz(x): return (x>>1)^-(x&1)
def main():
    if len(sys.argv)!=2: print('usage: report.py ARCHIVE',file=sys.stderr); return 2
    b=open(sys.argv[1],'rb').read()
    if not b.startswith(b'RFX1'): print('ERROR: invalid archive'); return 1
    i=4; _,i=u(b,i); n,i=u(b,i); total=0; bad=None
    for frame in range(1,n+20):
        if i>=len(b): break
        typ=b[i:i+1]; i+=1
        try:
            g,i=u(b,i); seq,i=u(b,i); ln,i=u(b,i)
            if i+ln+4>len(b): raise ValueError('invalid payload length')
            p=b[i:i+ln]; i+=ln; crc=struct.unpack('<I',b[i:i+4])[0]; i+=4
            if zlib.crc32(p)&0xffffffff!=crc: raise ValueError('bad checksum')
            if typ==b'D':
                j=0; c,j=u(p,j); e,j=u(p,j)
                if j!=len(p): raise ValueError('malformed payload')
                total += c*(10**e)
        except Exception as ex:
            bad=(frame,str(ex)); break
    if bad: print('ERROR: frame %s %s'%bad)
    print('reported total:',total)
    return 0
if __name__=='__main__':sys.exit(main())
