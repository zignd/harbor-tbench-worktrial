import json, math, zlib
REQ=('id','cohort','analyte','run','well','seq','quality','timestamp','value','unit','role')
def crc_ok(d):
    if d.get('crc32') is None:return True
    x=dict(d); got=str(x.pop('crc32')).lower()
    raw=json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    return got==f'{zlib.crc32(raw)&0xffffffff:08x}'
def valid(d,runs,units):
    if not isinstance(d,dict) or any(k not in d for k in REQ):return False
    if not all(isinstance(d[k],str) and d[k] for k in ('id','cohort','analyte','run','well','unit','role')):return False
    if d['role'] not in ('sample','positive','negative') or d['run'] not in runs or d['unit'] not in units:return False
    if isinstance(d['seq'],bool) or not isinstance(d['seq'],int) or isinstance(d['timestamp'],bool) or not isinstance(d['timestamp'],int):return False
    for k in ('quality','value'):
        if isinstance(d[k],bool) or not isinstance(d[k],(int,float)) or not math.isfinite(float(d[k])):return False
    return crc_ok(d)
def records(conn):
    runs={r[0]:r for r in conn.execute('select run_id,slope,intercept,calibration_unit from runs')}; units={r[0]:r[1] for r in conn.execute('select unit,factor from unit_factors')}
    out=[]
    for row in conn.execute('select payload from export_fragments order by fragment_id'):
        for line in bytes(row[0]).split(b'\n'):
            try:d=json.loads(line.decode())
            except Exception:continue
            if valid(d,runs,units):out.append(d)
    control={r[0]:r[3] for r in conn.execute('select measurement_id,cohort,analyte,role from controls')}
    for r in conn.execute('select measurement_id,cohort,analyte,run_id,well,sequence,quality,timestamp,value,unit,crc32 from measurements'):
        i,co,a,run,w,s,q,t,v,u,c=r; d={'id':i,'cohort':co,'analyte':a,'run':run,'well':w,'seq':s,'quality':q,'timestamp':t,'value':v,'unit':u,'role':control.get(i,'sample')}
        if c is not None:d['crc32']=c
        if valid(d,runs,units):out.append(d)
    return out,runs,units
