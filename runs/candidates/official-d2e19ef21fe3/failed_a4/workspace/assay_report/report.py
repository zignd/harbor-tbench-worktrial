import sqlite3,json,statistics,math
from .recover import records

def tukey(xs):
 if len(xs)<2:return xs[:]
 a=sorted(xs); q=lambda p: a[0] if len(a)==1 else a[int((len(a)-1)*p)] + ((len(a)-1)*p-int((len(a)-1)*p))*(a[min(len(a)-1,int((len(a)-1)*p)+1)]-a[int((len(a)-1)*p)])
 q1,q3=q(.25),q(.75); lo,hi=q1-1.5*(q3-q1),q3+1.5*(q3-q1); return [x for x in xs if lo<=x<=hi]
def make_report(path,out):
 c=sqlite3.connect(path); runs={r[0]:r[1:] for r in c.execute('select run_id,slope,intercept,calibration_unit from runs')}; fac=dict(c.execute('select unit,factor from unit_factors')); eligible={r[0]:r[2] for r in c.execute('select cohort,analyte,include from cohorts')}
 # intentionally simplistic precedence and fragment handling
 rows=[]; seen=set()
 for d in records(c):
  key=(d['cohort'],d['analyte'],d['run'],d['well'],d['seq'])
  if key in seen: continue
  seen.add(key)
  if d['cohort'] not in eligible or not eligible[d['cohort']]:continue
  if d['run'] not in runs or d['unit'] not in fac:continue
  sl,inter,cu=runs[d['run']]; x=d['value']*fac[d['unit']]/fac.get(cu,1); rows.append((d,x*sl+inter,cu))
 result=[]
 for co,a,inc in sorted((x for x in eligible if eligible[x])):
  rr=[(d,x,u) for d,x,u in rows if d['cohort']==co and d['analyte']==a]; groups={k:[] for k in ('sample','positive','negative')}
  for d,x,u in rr: groups.setdefault(d.get('role','sample'),[]).append(x)
  clean={k:tukey(v) for k,v in groups.items()}; sm=clean.get('sample',[]); ct=clean.get('positive') or clean.get('negative',[])
  med=lambda x: statistics.median(x) if x else None
  effect=med([x-y for x in sm for y in ct]) if sm and ct else None
  result.append({'cohort':co,'analyte':a,'n':len(sm),'control_n':len(ct),'median':med(sm),'control_median':med(ct),'effect':effect,'unit':(rr[0][2] if rr and (sm or ct) else None)})
 with open(out,'w') as f: json.dump(result,f,separators=(',',':'),allow_nan=False); f.write('\n')
