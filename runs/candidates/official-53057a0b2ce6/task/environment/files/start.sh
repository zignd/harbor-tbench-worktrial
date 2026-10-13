#!/bin/sh
set -eu
rm -f /tmp/audit.sock
exec python3 /opt/audit/bin/auditd.py
