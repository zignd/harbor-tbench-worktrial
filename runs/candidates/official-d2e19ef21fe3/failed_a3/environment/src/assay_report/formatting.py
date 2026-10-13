import json, math
def clean(x):
    if isinstance(x,float) and not math.isfinite(x): return None
    if isinstance(x,dict): return {k:clean(v) for k,v in x.items()}
    if isinstance(x,list): return [clean(v) for v in x]
    return x
def write_report(path,records):
    obj=clean({'schema_version':1,'records':sorted(records,key=lambda r:(r['cohort_id'],r['analyte']))})
    with open(path,'w',encoding='utf-8',newline='\n') as f: f.write(json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n')
