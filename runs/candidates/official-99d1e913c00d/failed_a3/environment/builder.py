#!/usr/bin/env python3
import sys,os,json,glob,subprocess,tempfile
state=sys.argv[1] if len(sys.argv)>1 else '/opt/beacon/state'; data=sys.argv[2] if len(sys.argv)>2 else '/opt/beacon/data'
os.makedirs(state,exist_ok=True); rows=[]; rejected=0
for fn in sorted(glob.glob(data+'/*.cap')):
 for line in open(fn,errors='replace'):
  p=subprocess.run(['/opt/beacon/bin/frame-decoder'],input=line,text=True,capture_output=True)
  if p.stdout:
   try: rows.append(json.loads(p.stdout))
   except: rejected+=1
  else: rejected+=1
# simple initial builder; deployment replaces this with canonical builder
rows.sort(key=lambda x:(x['device'],x['at'],x['source_seq']))
obj={'rows':rows,'rejected':rejected}; open(state+'/snapshot.json','w').write(json.dumps(obj)); open(state+'/stats.json','w').write(json.dumps({'records':len(rows),'devices':len(set(x['device'] for x in rows)),'rejected':rejected}))
