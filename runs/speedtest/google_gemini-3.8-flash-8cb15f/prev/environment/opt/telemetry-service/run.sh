#!/bin/bash
PIDFILE="/run/telemetry-queryd.pid"
APP_DIR="/opt/telemetry-service"

start() {
    if [ -f "$PIDFILE" ]; then
        PID=$(cat "$PIDFILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "telemetry-queryd already running with PID $PID"
            return 0
        fi
        rm -f "$PIDFILE"
    fi
    echo "Starting telemetry-queryd..."
    python3 "$APP_DIR/app/server.py" > /var/log/telemetry-queryd.log 2>&1 &
    PID=$!
    echo "$PID" > "$PIDFILE"
    sleep 1
    if kill -0 "$PID" 2>/dev/null; then
        echo "telemetry-queryd started (PID: $PID)"
        return 0
    else
        echo "Failed to start telemetry-queryd"
        cat /var/log/telemetry-queryd.log
        return 1
    fi
}

start_foreground() {
    echo "Starting telemetry-queryd in foreground..."
    exec python3 "$APP_DIR/app/server.py"
}

stop() {
    if [ -f "$PIDFILE" ]; then
        PID=$(cat "$PIDFILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "Stopping telemetry-queryd (PID: $PID)..."
            kill "$PID" 2>/dev/null
            for i in $(seq 1 15); do
                if ! kill -0 "$PID" 2>/dev/null; then
                    break
                fi
                sleep 0.2
            done
            if kill -0 "$PID" 2>/dev/null; then
                kill -9 "$PID" 2>/dev/null
            fi
        fi
        rm -f "$PIDFILE"
    fi
    pkill -f "$APP_DIR/app/server.py" 2>/dev/null || true
    # Wait until port 8085 is completely released
    for i in $(seq 1 15); do
        if ! ss -tlpn 2>/dev/null | grep -q ":8085 "; then
            break
        fi
        sleep 0.2
    done
    echo "telemetry-queryd stopped."
    return 0
}

restart() {
    stop
    sleep 0.5
    start
}

status() {
    if [ -f "$PIDFILE" ]; then
        PID=$(cat "$PIDFILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "telemetry-queryd is running (PID: $PID)"
            return 0
        fi
    fi
    if pgrep -f "$APP_DIR/app/server.py" > /dev/null; then
        echo "telemetry-queryd is running without pidfile"
        return 0
    fi
    echo "telemetry-queryd is not running"
    return 3
}

case "$1" in
    start)
        start
        ;;
    start-foreground)
        start_foreground
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|start-foreground}"
        exit 1
        ;;
esac
