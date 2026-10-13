#!/bin/sh
set -eu
url=${1:-http://127.0.0.1:9200/health}
tries=${2:-20}
while [ "$tries" -gt 0 ]; do
  if python3 - "$url" <<'PY'
import sys, urllib.request
try:
    with urllib.request.urlopen(sys.argv[1],timeout=.25) as r: raise SystemExit(0 if r.status == 200 else 1)
except Exception: raise SystemExit(1)
PY
  then exit 0; fi
  tries=$((tries-1)); sleep .1
done
exit 1
