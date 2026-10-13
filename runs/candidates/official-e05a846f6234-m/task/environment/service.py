import sys,json,math
from pathlib import Path
R=Path('/opt/metricq'); J=R/'journal.ndjson'; C=R/'checkpoint.json'; M=R/'metrics.prom'; L=R/'service.log'; repaired=(R/'.repaired').exists()
streams={}; seen=set(); latest={}; dropped=0

def error(m): return {'ok':False,'error':{'code':'invalid_request','message':m}}
def log(e,**kw):
 with L.open('a') as f:f.write(json.dumps({'event':e,**kw},sort_keys=True,separators=(',',':'))+'\n')
def metrics(): M.write_text('metricq_events '+str(sum(len(v) for v in streams.values()))+'\nmetricq_dropped_late '+str(dropped)+'\n')
def check(x):
 if not isinstance(x,dict) or not isinstance(x.get('stream'),str) or not x['stream'] or not isinstance(x.get('id'),str): raise ValueError('stream and id are required')
 for k in ('ts','value'):
  if not isinstance(x.get(k),(int,float)) or isinstance(x[k],bool) or not math.isfinite(x[k]): raise ValueError(k+' must be finite')
 w=x.get('weight',1)
 if not isinstance(w,int) or isinstance(w,bool) or w<=0: raise ValueError('weight must be a positive integer')
 return x['stream'],x['id'],x['ts'],x['value'],w
def add(x):
 global dropped
 s,i,t,v,w=check(x); key=(s,i)
 if repaired:
  if key in seen:return False
 else:
  if str(i).isdigit() and int(i)<=latest.get(s,-1):return False
 if t<latest.get(s,float('-inf'))-10:dropped+=1;seen.add(key);return False
 latest[s]=max(latest.get(s,float('-inf')),t);seen.add(key);streams.setdefault(s,[]).append((v,t,w));return True
def pct(a,q):
 if not a:return None
 if not 0<=q<=1:raise ValueError('invalid quantile')
 a=sorted(a,key=lambda z:(z[0],z[1])); target=q*(sum(z[2] for z in a)-1); n=0
 for v,t,w in a:
  if target<n+w:return v
  n+=w
 return a[-1][0]
def reset():
 global streams,seen,latest,dropped
 streams={};seen=set();latest={};dropped=0
 for p in (J,C,M,L):
  try:p.unlink()
  except FileNotFoundError:pass
def checkpoint():
 d={'offset':len(J.read_text().splitlines()) if J.exists() else 0,'streams':streams,'seen':[list(x) for x in seen],'latest':latest,'dropped':dropped};C.write_text(json.dumps(d,sort_keys=True,separators=(',',':')));log('checkpoint',offset=d['offset']);return d['offset']
def recover():
 global streams,seen,latest,dropped
 if not C.exists():return error('no checkpoint')
 d=json.loads(C.read_text());streams={k:[tuple(z) for z in v] for k,v in d.get('streams',{}).items()};seen={tuple(x) for x in d.get('seen',[])};latest=d.get('latest',{});dropped=d.get('dropped',0); off=int(d['offset']); n=0
 lines=J.read_text().splitlines() if J.exists() else []
 for line in lines[off:]:
  try:add(json.loads(line));n+=1
  except Exception:
   if line is lines[-1] or lines.index(line)==len(lines)-1:break
   return error('malformed journal record')
 metrics();log('recover',offset=off,recovered=n);return {'ok':True,'recovered':n}
def handle(x):
 global dropped
 if not isinstance(x,dict) or not isinstance(x.get('op'),str):return error('op is required')
 op=x['op']
 if op=='reset':reset();return {'ok':True,'reset':True}
 if op=='ingest':
  try:check(x)
  except Exception as e:return error(str(e))
  with J.open('a') as f:f.write(json.dumps({k:x[k] for k in ('stream','id','ts','value','weight') if k in x},sort_keys=True,separators=(',',':'))+'\n')
  try:a=add(x)
  except Exception as e:return error(str(e))
  metrics();return {'ok':True,'accepted':a}
 if op=='checkpoint':return {'ok':True,'offset':checkpoint()}
 if op=='recover':return recover()
 if op=='query':
  try:
   s=x['stream'];lo=x['start'];hi=x['end'];q=x['q'];qs=q if isinstance(q,list) else [q]
   if not isinstance(s,str) or not isinstance(lo,(int,float)) or not isinstance(hi,(int,float)) or lo>=hi:raise ValueError('invalid query range')
   vals=[z for z in streams.get(s,[]) if lo<=z[1]<hi]; out=[pct(vals,float(z)) for z in qs]
   return {'ok':True,'values':out if isinstance(q,list) else out[0]}
  except (KeyError,TypeError,ValueError) as e:return error(str(e))
 return error('unknown operation')
for line in sys.stdin:
 try:r=handle(json.loads(line))
 except json.JSONDecodeError:r=error('invalid JSON')
 except Exception as e:r=error(str(e))
 print(json.dumps(r,separators=(',',':')),flush=True)
