import math
from .db import connect,rows
from .recover import valid,recover
from .mathutil import median,tukey

def report(path):
 c=connect(path); runs={r['run_id']:r for r in rows(c,'runs')}; factors={r['unit']:float(r['factor']) for r in rows(c,'unit_factors')}
 raw=[x for x in rows(c,'measurements') if valid(x,False)]+list(recover(c))
 ctl=[x for x in rows(c,'controls') if valid(x,True)]
 def rank(x):
  r=runs.get(x['run_id'],{}); return (int(r.get('priority',0)),str(x['well']),int(x['sequence']),str(x['timestamp']),float(x['quality']),str(x.get('measurement_id',x.get('control_id',''))))
 def dedup(xs):
  d={}
  for x in xs:
   k=(x['cohort_id'],x['analyte'],x['well'],int(x['sequence']))
   if k not in d or rank(x)>rank(d[k]):d[k]=x
  return list(d.values())
 def calibrated(x):
  r=runs[x['run_id']]; v=float(x['value'])*factors[x['unit']]/factors[r['calibration_unit']]
  return float(r['slope'])*v+float(r['intercept'])
 bas={}
 for x in dedup(ctl): bas.setdefault((x['cohort_id'],x['analyte'],x['kind']),[]).append(calibrated(x))
 bas={k:median(v) for k,v in bas.items()}
 values={}
 for x in dedup(raw):
  if float(x['quality'])<.5:continue
  p=bas.get((x['cohort_id'],x['analyte'],'positive')); n=bas.get((x['cohort_id'],x['analyte'],'negative'))
  if p is None or n is None or p==n:continue
  values.setdefault((x['cohort_id'],x['analyte'],x['phase']),[]).append((calibrated(x)-n)/(p-n))
 keys={(x['cohort_id'],x['analyte']) for x in raw+ctl}
 out=[]
 for z,a in sorted(keys):
  pre=tukey(values.get((z,a,'pre'),[])); post=tukey(values.get((z,a,'post'),[])); pairs=[y-x for x in pre for y in post]
  out.append({'cohort_id':z,'analyte':a,'n_pre':len(pre),'n_post':len(post),'positive_control':bas.get((z,a,'positive')),'negative_control':bas.get((z,a,'negative')),'pre_median':median(pre),'post_median':median(post),'effect':median(pairs)})
 c.close();return {'records':out,'schema_version':1}
