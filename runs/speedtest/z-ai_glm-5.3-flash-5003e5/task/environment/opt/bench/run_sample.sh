#!/bin/bash
set -euo pipefail
export PATH=/usr/local/go/bin:${PATH}
cd /opt/log-metricd
if [ ! -x bin/log-metricd ]; then
  go build -trimpath -o bin/log-metricd ./cmd/log-metricd
fi
exec python3 /opt/bench/sample_workload.py "${@}"
