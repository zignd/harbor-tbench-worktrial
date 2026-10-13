import struct
MAGIC=b'SWR1'
def uvarint(n):
    n=int(n); out=bytearray()
    while n>=128: out.append((n&127)|128); n>>=7
    out.append(n); return bytes(out)
def zig(n): return (int(n)<<1) if n>=0 else ((-int(n)<<1)-1)
def svarint(n): return uvarint(zig(n))
def readvar(b,p):
    v=0; s=0
    for _ in range(10):
        if p>=len(b): raise ValueError('short varint')
        x=b[p]; p+=1; v|=(x&127)<<s
        if not x&128: return v,p
        s+=7
    raise ValueError('long varint')
def crc32c(data):
    c=0xffffffff
    for x in data:
        c^=x
        for _ in range(8): c=(c>>1)^0x82f63b78 if c&1 else c>>1
    return (c^0xffffffff)&0xffffffff
def frame(identifier,sequence,timestamp,measurements,metadata,extra=b''):
    def st(x):
        x=str(x).encode(); return uvarint(len(x))+x
    b=bytearray([1]); b+=st(identifier)+uvarint(sequence)+svarint(timestamp)
    b+=uvarint(len(measurements))
    for k,v in measurements.items(): b+=st(k)+svarint(v)
    b+=uvarint(len(metadata))
    for k,v in metadata.items(): b+=st(k)+st(v)
    b+=extra
    return MAGIC+struct.pack('>I',len(b))+b+struct.pack('>I',crc32c(b))
