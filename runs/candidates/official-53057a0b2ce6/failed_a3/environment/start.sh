#!/bin/sh
set -eu
rm -f /tmp/seal-helper.sock
python3 /opt/audit/bin/seal-helper >/opt/audit/state/seal-helper.log 2>&1 &
exec python3 /opt/audit/bin/auditd.py
