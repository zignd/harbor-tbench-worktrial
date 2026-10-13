#!/usr/bin/env python3
import sys,json
for line in sys.stdin:
 try: print(json.dumps({'ok':False,'error':'recovery unavailable'},ensure_ascii=False),flush=True)
 except Exception: pass
