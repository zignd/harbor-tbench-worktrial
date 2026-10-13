#!/bin/sh
set -eu
D=/var/run/relay
mkdir -p "$D" /var/log/relay
stop_pid() {
  f=$1
  if [ -f "$f" ]; then
    p=$(cat "$f" 2>/dev/null || true)
    case "$p" in ''|*[!0-9]*) ;; *) kill "$p" 2>/dev/null || true; for i in 1 2 3 4 5; do kill -0 "$p" 2>/dev/null || break; sleep .05; done; kill -9 "$p" 2>/dev/null || true ;; esac
  fi
  rm -f "$f"
}
stop_pid "$D/relay.pid"
stop_pid "$D/sink.pid"
for p in $(ps -eo pid=,args= | awk '/python3 \/opt\/relay\/(sink|relay_(fragile|robust))\.py/ {print $1}'); do
  [ "$p" = "$$" ] || kill "$p" 2>/dev/null || true
done
sleep .1
python3 /opt/relay/sink.py > /var/log/relay/sink.log 2>&1 &
sink=$!
echo "$sink" > "$D/sink.pid"
ready=0
for i in $(seq 1 80); do
  if python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9200/health',timeout=.2).read()" 2>/dev/null; then ready=1; break; fi
  kill -0 "$sink" 2>/dev/null || break
  sleep .1
done
[ "$ready" = 1 ] || { echo 'sink failed readiness' >&2; exit 1; }
python3 /opt/relay/relay_robust.py > /var/log/relay/relay.log 2>&1 &
relay=$!
echo "$relay" > "$D/relay.pid"
ready=0
for i in $(seq 1 80); do
  if python3 -c "import socket; s=socket.create_connection(('127.0.0.1',9100),.2); s.close()" 2>/dev/null; then ready=1; break; fi
  kill -0 "$relay" 2>/dev/null || break
  sleep .1
done
[ "$ready" = 1 ] || { echo 'relay failed readiness' >&2; exit 1; }
