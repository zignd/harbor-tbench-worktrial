import sys,json,os
for line in sys.stdin:
 try:
  req=json.loads(line); path='/opt/settlement-recon/var/last.json'; r=json.load(open(path)) if os.path.exists(path) else {'summary':{}}
  s=r.get('summary',{}) if req.get('op')=='reconciliation' else {}
  print(json.dumps({k:int(s.get(k,0)) for k in ('processed','matched','unmatched','candidate_edges')},separators=(',',':')),flush=True)
 except Exception as e: print(json.dumps({'error':str(e)},separators=(',',':')),flush=True)
