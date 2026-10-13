#!/usr/bin/env python3
import sys,json
for line in sys.stdin:
 try:
  x=json.loads(line); d=x.get('device','')
  if len(d)!=16 or any(c not in '0123456789abcdefABCDEF' for c in d): raise ValueError()
  if not isinstance(x.get('at'),int) or not isinstance(x.get('source_seq'),int): raise ValueError()
  print(json.dumps({'device':d.upper(),'at':x['at'],'value':x['value'],'quality':x.get('quality','unknown'),'source_seq':x['source_seq']&0xffffffff},separators=(',',':')))
 except Exception: continue
