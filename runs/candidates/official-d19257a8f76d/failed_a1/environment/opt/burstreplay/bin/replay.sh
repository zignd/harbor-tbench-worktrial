#!/bin/bash
set -euo pipefail
trace= run=
while (($#)); do
  case "$1" in
    --trace) [[ $# -ge 2 ]] || exit 2; trace=$2; shift 2;;
    --run) [[ $# -ge 2 ]] || exit 2; run=$2; shift 2;;
    *) exit 2;;
  esac
done
[[ -n "$trace" && -n "$run" && -f "$trace" ]] || exit 1
tmp=$(mktemp -d /tmp/burstreplay.XXXXXX)
trap 'rm -rf "$tmp"' EXIT
python3 - "$run" "$trace" >"$tmp/requests" <<'PY'
import json,sys
run,path=sys.argv[1:]
try: data=open(path,encoding='utf-8').read()
except Exception: raise SystemExit(1)
for x in ({'op':'reset','run':run},{'op':'ingest','run':run,'trace':data},{'op':'report','run':run}):
 print(json.dumps(x,ensure_ascii=False))
PY
/opt/burstreplay/bin/replayd <"$tmp/requests" >"$tmp/responses"
python3 - "$tmp/responses" <<'PY'
import json,sys
lines=open(sys.argv[1],encoding='utf-8').read().splitlines()
if len(lines)!=3: raise SystemExit(1)
objs=[json.loads(x) for x in lines]
if not all(x.get('ok') is True for x in objs): raise SystemExit(1)
print(json.dumps(objs[-1],ensure_ascii=False,separators=(',',':')))
PY
