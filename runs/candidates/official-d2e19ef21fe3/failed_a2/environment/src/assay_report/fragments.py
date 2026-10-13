import binascii,json,math
def valid(d):
    if not isinstance(d,dict) or 'crc32' not in d:return None
    body={k:v for k,v in d.items() if k!='crc32'}
    raw=json.dumps(body,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    if str(d['crc32']).lower()!=f'{binascii.crc32(raw)&0xffffffff:08x}':return None
    req=('cohort_id','analyte','well','run_id','sequence','observed_at','quality','value','unit','role')
    if any(k not in body or body[k] in (None,'') for k in req):return None
    if not isinstance(body['sequence'],int) or not isinstance(body['observed_at'],int):return None
    if not isinstance(body['value'],(int,float)) or not math.isfinite(body['value']):return None
    if not isinstance(body['quality'],(int,float)) or not math.isfinite(body['quality']):return None
    return body
def recover(conn):
    buf=b''
    for payload, in conn.execute('select payload from export_fragments order by run_id,ordinal,fragment_id'):
        buf+=bytes(payload)
        while b'\n' in buf:
            line,buf=buf.split(b'\n',1)
            try:d=valid(json.loads(line.decode()))
            except Exception:d=None
            if d is not None:yield d
    if buf:
        try:d=valid(json.loads(buf.decode()))
        except Exception:d=None
        if d is not None:yield d
