import statistics,math
from .fragments import recover
def med(a):return statistics.median(a) if a else None
def q(a,p):
 a=sorted(a); x=(len(a)-1)*p; i=int(x); j=min(i+1,len(a)-1); return a[i]+(a[j]-a[i])*(x-i)
def filt(a):
 if not a:return []
 a=list(a); spread=q(a,.75)-q(a,.25);
 if spread==0:return a
 lo=q(a,.25)-1.5*spread; hi=q(a,.75)+1.5*spread; return [x for x in a if lo<x<hi]
def build(c):
 fac=dict(c.execute('select unit,factor from unit_factors'))
 runs={r[0]:r[1:] for r in c.execute('select run_id,calibration_unit,intercept,slope from runs')}
 active={r[0] for r in c.execute('select cohort_id from cohorts where active=1')}
 rows=[]
 for d in recover(c):
  if d['cohort_id'] not in active or d['quality']<0 or d['unit'] not in fac or d['run_id'] not in runs:continue
  _,inter,slope=runs[d['run_id']]; rows.append((d,inter+slope*d['value']*fac[d['unit']]))
 best={}
 for d,v in rows:
  k=(d['cohort_id'],d['analyte'],d['well']); rank=(d['sequence'],d['quality'],d['observed_at'],d['run_id'],d.get('source_id',''))
  if k not in best or rank>best[k][0]:best[k]=(rank,d,v)
 groups={}
 for _,d,v in best.values():groups.setdefault((d['cohort_id'],d['analyte']),{}).setdefault(d['role'],[]).append(v)
 out=[]
 for (cohort,analyte),g in sorted(groups.items()):
  pos,neg=filt(g.get('positive_control',[])),filt(g.get('negative_control',[])); pv,nv=med(pos),med(neg); den=None if pv is None or nv is None else pv-nv
  pre=filt(g.get('pre',[])); post=filt(g.get('post',[]));
  if den is None or den==0: pre2=post2=[]
  else: pre2=[(x-nv)/den for x in pre]; post2=[(x-nv)/den for x in post]
  pairs=[b-a for a in pre2 for b in post2]
  out.append({'cohort_id':cohort,'analyte':analyte,'n_pre':len(pre2),'n_post':len(post2),'positive_control':pv,'negative_control':nv,'pre_median':med(pre2),'post_median':med(post2),'effect':med(pairs)})
 return out
