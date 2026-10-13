#!/usr/bin/env python3
import json, socket, struct, time, urllib.request
from protocol import MAGIC, crc32c, readvar
MAX_BODY=4*1024*1024

def event_from_body(b):
    if not b or b[0] != 1: raise ValueError('version')
    class Cursor:
        def __init__(self, data): self.data=data; self.p=1
        def var(self):
            value,self.p=readvar(self.data,self.p)
            return value
        def text(self):
            n=self.var()
            if n > len(self.data)-self.p: raise ValueError('string length')
            q=self.data[self.p:self.p+n].decode('utf-8')
            self.p += n
            return q
        def signed(self):
            value=self.var()
            return value//2 if value%2==0 else -(value//2)-1
    c=Cursor(b)
    ident=c.text(); seq=c.var(); stamp=c.signed(); measurements={}
    for _ in range(c.var()):
        key=c.text(); value=c.signed(); measurements[key]=value
    metadata={}
    for _ in range(c.var()):
        key=c.text(); value=c.text(); metadata[key]=value
    while c.p < len(b):
        c.p += 1
        n=c.var()
        if n > len(b)-c.p: raise ValueError('tlv length')
        c.p += n
    return {'identifier':ident,'sequence':seq,'timestamp':stamp,'measurements':measurements,'metadata':metadata}

def send_batch(rows):
    if not rows: return True
    payload=b''.join(json.dumps(x,separators=(',',':'),ensure_ascii=False).encode()+b'\n' for x in rows)
    req=urllib.request.Request('http://127.0.0.1:9200/events',data=payload,method='POST',headers={'Content-Type':'application/x-ndjson'})
    try:
        with urllib.request.urlopen(req,timeout=5) as r: return r.status==200
    except Exception as e:
        try:
            with open('/var/log/relay/relay-errors.log','a') as f: f.write('post '+repr(e)+'\n')
        except Exception: pass
        return False

def process(c):
    buf=bytearray(); batch=[]; local=set()
    while True:
        part=c.recv(262144)
        if not part: break
        buf.extend(part)
        while True:
            if len(buf)<8: break
            if buf[:4]!=MAGIC:
                i=buf.find(MAGIC,1)
                if i<0:
                    del buf[:-3]
                else:
                    del buf[:i]
                if len(buf)<8: break
            n=struct.unpack('>I',buf[4:8])[0]
            if n<1 or n>MAX_BODY:
                del buf[0]
                continue
            need=8+n+4
            if len(buf)<need: break
            body=bytes(buf[8:8+n])
            checksum=struct.unpack('>I',buf[8+n:need])[0]
            del buf[:need]
            if crc32c(body)!=checksum: continue
            try: row=event_from_body(body)
            except Exception as e:
                try:
                    with open('/var/log/relay/relay-errors.log','a') as f: f.write('decode '+repr(e)+'\n')
                except Exception: pass
                continue
            if row['identifier'] in local: continue
            local.add(row['identifier']); batch.append(row)
            if len(batch)>=64:
                while not send_batch(batch): time.sleep(.05)
                batch=[]
    while batch:
        if send_batch(batch): batch=[]
        else: time.sleep(.05)

def main():
    srv=socket.socket(); srv.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); srv.bind(('0.0.0.0',9100)); srv.listen(64)
    while True:
        c,_=srv.accept()
        try: process(c)
        except Exception as e:
            try:
                with open('/var/log/relay/relay-errors.log','a') as f: f.write('connection '+repr(e)+'\n')
            except Exception: pass
        finally: c.close()
if __name__=='__main__': main()
