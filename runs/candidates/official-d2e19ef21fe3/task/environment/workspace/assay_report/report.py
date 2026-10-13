import json,sqlite3
from .recover import records
from .stats import tukey,med
def make_report(db,out):
 c=sqlite3.connect(db); rec,runs,units=records(c); selected={}
 for d in rec:
  key=(d['cohort'],d['analyte'],d['run'],d['well'],d['seq'])
  if key not in selected:selected[key]=d
 vals=[]
 for d in selected.values():
  slope,inter,cu=runs[d['run']]; vals.append((d,slope*d['value']+inter,cu))
 rows=[]
 for co,a,inc in sorted(c.execute('select cohort,analyte,include from cohorts')):
  if not inc:continue
  g={'sample':[],'positive':[],'negative':[]}
  for d,v,u in vals:
   if d['cohort']==co and d['analyte']==a:g[d['role']].append(v)
  g={k:tukey(v) for k,v in g.items()};s=g['sample'];ctrl=g['positive'] or g['negative']; dif=[x-y for x in s for y in ctrl]
  unit=next((u for d,v,u in vals if d['cohort']==co and d['analyte']==a),None) if (s or ctrl) else None
  rows.append({'cohort':co,'analyte':a,'n':len(s),'control_n':len(ctrl),'median':med(s),'control_median':med(ctrl),'effect':med(dif),'unit':unit})
 c.close()
 with open(out,'w',encoding='utf-8',newline='\n') as f:json.dump(rows,f,separators=(',',':'),allow_nan=False);f.write('\n')
