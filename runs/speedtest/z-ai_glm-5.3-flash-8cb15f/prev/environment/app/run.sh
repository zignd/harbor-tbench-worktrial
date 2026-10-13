#!/bin/bash
set -euo pipefail

APP_DIR="/opt/telemetry-service"
DAEMON="$APP_DIR/daemon.py"
PID_FILE="/run/telemetry-queryd.pid"
LOG_FILE="/var/log/telemetry-service.log"
PORT="${TELEMETRY_PORT:-8085}"

is_running() {
    [[ -f "$PID_FILE" ]] || return 1
    local pid
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    [[ "$pid" =~ ^[0-9]+$ ]] || return 1
    kill -0 "$pid" 2>/dev/null
}

wait_health() {
    local attempt
    for attempt in {1..60}; do
        if python3 - "$PORT" <<'PY'
import socket
import sys
with socket.create_connection(("127.0.0.1", int(sys.argv[1])), timeout=.25):
    pass
PY
        then
            return 0
        fi
        sleep .1
    done
    return 1
}

start() {
    if is_running; then
        echo "telemetry-queryd already running (pid $(cat "$PID_FILE"))"
        return 0
    fi
    mkdir -p "$(dirname "$LOG_FILE")"
    nohup python3 "$DAEMON" >>"$LOG_FILE" 2>&1 &
    local pid=$!
    echo "$pid" >"$PID_FILE"
    if ! wait_health; then
        echo "telemetry-queryd failed to start" >&2
        stop
        exit 1
    fi
    echo "telemetry-queryd started (pid $pid)"
}

stop() {
    if ! is_running; then
        rm -f "$PID_FILE"
        return 0
    fi
    local pid
    pid="$(cat "$PID_FILE")"
    kill "$pid" 2>/dev/null || true
    local attempt
    for attempt in {1..50}; do
        kill -0 "$pid" 2>/dev/null || break
        sleep .1
    done
    if kill -0 "$pid" 2>/dev/null; then
        kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
    echo "telemetry-queryd stopped"
}

status() {
    if is_running; then
        echo "telemetry-queryd is running (pid $(cat "$PID_FILE"))"
        return 0
    fi
    echo "telemetry-queryd is not running"
    return 3
}

case "${1:-}" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        start
        ;;
    status)
        status
        ;;
    foreground)
        echo $$ >"$PID_FILE"
        exec python3 "$DAEMON"
        ;;
    *)
        echo "usage: $0 {start|stop|restart|status|foreground}" >&2
        exit 2
        ;;
esac
