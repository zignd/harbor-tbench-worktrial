import sys,json,math
from pathlib import Path
R=Path('/opt/metricq'); J=R/'journal.ndjson'; C=R/'checkpoint.json'; M=R/'metrics.prom'; L=R/'service.log'
streams={}; seen=set(); latest={}; dropped=0; journal_offset=0

def error(m): return {'ok':False,'error':{'code':'invalid_request','message':m}}
def log(event,**kw):
 with L.open('a') as f:f.write(json.dumps({'event':event,**kw},sort_keys=True,separators=(',',':'))+'\n')
def metrics():
 M.write_text('metricq_events '+str(sum(len(v) for v in streams.values()))+'\nmetricq_dropped_late '+str(dropped)+'\nmetricq_recovered_offset '+str(journal_offset)+'\n')
def num(v): return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def validate_ingest(x):
 if not isinstance(x.get('stream'),str) or not x['stream'] or not isinstance(x.get('id'),str) or not x['id']: raise ValueError('stream and id are required')
 if not num(x.get('ts')) or not num(x.get('value')): raise ValueError('ts and value must be finite numbers')
 if not isinstance(x.get('weight'),int) or isinstance(x['weight'],bool) or x['weight']<=0: raise ValueError('weight must be a positive integer')
def add(x,write=True):
 global dropped
 validate_ingest(x); key=(x['stream'],x['id'])
 if key in seen:return False
 seen.add(key); s=x['stream']; t=x['ts']; latest[s]=max(latest.get(s,-math.inf),t)
 if t<latest[s]-10:dropped+=1;return False
 streams.setdefault(s,[]).append((x['value'],t,x['weight'])); return True
def pct(a,q):
 if not a:return None
 total=sum(z[2] for z in a); target=q*(total-1); cur=0
 for value,ts,weight in sorted(a,key=lambda z:(z[0],z[1])):
  cur+=weight
  if target<cur:return value
 return sorted(a)[-1][0]
def reset():
 global streams,seen,latest,dropped,journal_offset
 streams={};seen=set();latest={};dropped=0;journal_offset=0
 for p in (J,C,M,L):
  try:p.unlink()
  except FileNotFoundError:pass
def snapshot():
 return {'offset':journal_offset,'streams':{k:[list(z) for z in v] for k,v in streams.items()},'seen':[list(z) for z in sorted(seen)],'latest':latest,'dropped':dropped}
def trim_incomplete_tail():
 if not J.exists(): return
 data=J.read_bytes()
 if not data or data.endswith(b'\n'): return
 cut=data.rfind(b'\n')+1
 J.write_bytes(data[:cut])

def checkpoint():
 C.write_text(json.dumps(snapshot(),sort_keys=True,separators=(',',':'))); log('checkpoint',offset=journal_offset); return journal_offset
def read_records():
 if not J.exists():return [],False,None
 data=J.read_bytes(); lines=data.splitlines(keepends=True); records=[];pos=0;tail=False
 for line in lines:
  if not line.endswith(b'\n'):
   tail=True;break
  try:
   obj=json.loads(line); validate_ingest(obj); records.append(obj);pos+=len(line)
  except Exception:return records,False,'malformed complete journal record'
 if tail:J.write_bytes(data[:pos])
 return records,tail,None
def recover():
 global streams,seen,latest,dropped,journal_offset
 if not C.exists():return error('no checkpoint')
 try:d=json.loads(C.read_text())
 except Exception:return error('invalid checkpoint')
 records,tail,bad=read_records()
 if bad:return error(bad)
 streams={k:[tuple(z) for z in v] for k,v in d.get('streams',{}).items()};seen={tuple(z) for z in d.get('seen',[])};latest=d.get('latest',{});dropped=d.get('dropped',0);start=int(d.get('offset',0));journal_offset=start; n=0
 for x in records[start:]: add(x,False);n+=1;journal_offset+=1
 metrics();log('recover',offset=journal_offset,recovered=n,dropped_tail=tail);return {'ok':True,'recovered':n,'offset':journal_offset}
def handle(x):
 global journal_offset
 if not isinstance(x,dict) or not isinstance(x.get('op'),str):return error('op is required')
 op=x['op']
 if op=='reset':reset();return {'ok':True,'reset':True}
 if op=='ingest':
  try:validate_ingest(x)
  except Exception as e:return error(str(e))
  key=(x['stream'],x['id'])
  if key in seen:return {'ok':True,'accepted':False}
  clean={k:x[k] for k in ('stream','id','ts','value','weight')}
  trim_incomplete_tail()
  with J.open('a') as f:f.write(json.dumps(clean,sort_keys=True,separators=(',',':'))+'\n')
  accepted=add(clean);journal_offset+=1;metrics();log('ingest',accepted=accepted,stream=clean['stream']);return {'ok':True,'accepted':accepted}
 if op=='checkpoint':return {'ok':True,'offset':checkpoint()}
 if op=='recover':return recover()
 if op=='query':
  try:
   s=x['stream'];lo=x['start'];hi=x['end'];raw=x['q'];qs=raw if isinstance(raw,list) else [raw]
   if not isinstance(s,str) or not num(lo) or not num(hi) or hi<=lo or not qs:raise ValueError('invalid query range')
   if any(not num(q) or q<0 or q>1 for q in qs):raise ValueError('invalid quantile')
   vals=[z for z in streams.get(s,[]) if lo<=z[1]<hi];out=[pct(vals,q) for q in qs]
   return {'ok':True,'values':out if isinstance(raw,list) else out[0]}
  except (KeyError,TypeError,ValueError) as e:return error(str(e))
 return error('unknown operation')
for line in sys.stdin:
 try: print(json.dumps(handle(json.loads(line)),separators=(',',':')),flush=True)
 except json.JSONDecodeError: print(json.dumps(error('invalid JSON'),separators=(',',':')),flush=True)
 except Exception as e: print(json.dumps(error(str(e)),separators=(',',':')),flush=True)
