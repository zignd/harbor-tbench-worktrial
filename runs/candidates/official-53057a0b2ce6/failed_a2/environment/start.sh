#!/bin/sh
set -eu
stop_pidfile() {
  file=$1
  target=$2
  if [ -s "$file" ]; then
    pid=$(cat "$file" 2>/dev/null || true)
    if [ -n "$pid" ] && [ -r "/proc/$pid/cmdline" ]; then
      cmd=$(tr '\000' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)
      case "$cmd" in *"$target"*) kill "$pid" 2>/dev/null || true;; esac
    fi
  fi
  rm -f "$file"
}
stop_pidfile /tmp/auditd.pid '/opt/audit/bin/auditd.py'
stop_pidfile /tmp/seal-helper.pid '/opt/audit/bin/seal-helper'
rm -f /tmp/seal-helper.sock
nohup /opt/audit/bin/seal-helper /tmp/seal-helper.sock >/tmp/seal-helper.log 2>&1 &
echo $! >/tmp/seal-helper.pid
for i in $(seq 1 100); do [ -S /tmp/seal-helper.sock ] && break; sleep .02; done
nohup python3 /opt/audit/bin/auditd.py >/tmp/auditd.log 2>&1 &
echo $! >/tmp/auditd.pid
wait "$(cat /tmp/auditd.pid)"
