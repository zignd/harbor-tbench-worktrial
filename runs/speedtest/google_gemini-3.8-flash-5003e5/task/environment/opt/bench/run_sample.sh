#!/bin/bash
set -euo pipefail

echo "Checking log-metricd service status..."
if ! systemctl is-active log-metricd > /dev/null 2>&1; then
    echo "Warning: log-metricd is not currently active according to systemctl."
fi

python3 /opt/bench/workload.py
