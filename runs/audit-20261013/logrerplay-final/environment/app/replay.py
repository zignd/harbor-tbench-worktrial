import sys,os,json
if len(sys.argv)!=3: raise SystemExit(2)
for root,ds,fs in os.walk(sys.argv[1]):
 for f in fs:
  if f.endswith('.log'):
   with open(os.path.join(root,f),errors='replace') as h:
    for line in h:
     try: json.loads(line)
     except Exception: pass
