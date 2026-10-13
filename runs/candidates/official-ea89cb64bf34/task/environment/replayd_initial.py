#!/usr/bin/env python3
import sys,json
for line in sys.stdin:
 print(json.dumps({'ok':False,'error':'recovery unavailable'}),flush=True)
