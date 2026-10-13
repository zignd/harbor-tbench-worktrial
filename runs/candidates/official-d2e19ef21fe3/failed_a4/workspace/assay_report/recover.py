import json,zlib,math

def records(conn):
 out=[]
 for fid,payload in conn.execute('select fragment_id,payload from export_fragments order by fragment_id'):
  # initial implementation intentionally treats each fragment independently
  for line in bytes(payload).splitlines():
   try: d=json.loads(line)
   except Exception: continue
   if valid(d) and crc_ok(d): out.append(d)
 for r in conn.execute('select measurement_id,cohort,analyte,run_id,well,sequence,quality,timestamp,value,unit,crc32 from measurements'):
  i,co,a,run,w,s,q,t,v,u,crc=r; d={'id':i,'cohort':co,'analyte':a,'run':run,'well':w,'seq':s,'quality':q,'timestamp':t,'value':v,'unit':u,'crc32':crc,'role':'sample'}
  if valid(d) and crc_ok(d): out.append(d)
 return out

def valid(d):
 return isinstance(d,dict) and all(k in d for k in ('id','cohort','analyte','run','well','seq','quality','timestamp','value','unit','role')) and isinstance(d['value'],(int,float)) and math.isfinite(d['value'])
def crc_ok(d):
 if 'crc32' not in d:return True
 x=dict(d); got=x.pop('crc32'); raw=json.dumps(x,sort_keys=True,separators=(',',':')).encode(); return str(got).lower()==f'{zlib.crc32(raw)&0xffffffff:08x}'
