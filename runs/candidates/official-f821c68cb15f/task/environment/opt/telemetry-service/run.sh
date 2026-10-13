#!/bin/bash
PIDFILE=/var/run/telemetry-queryd.pid
LOGFILE=/var/log/telemetry-queryd.log
DAEMON_DIR=/opt/telemetry-service

start() {
    if [ -f "$PIDFILE" ] && kill -0 $(cat "$PIDFILE") 2>/dev/null; then
        echo "telemetry-queryd is already running (PID $(cat $PIDFILE))"
        return 0
    fi
    echo "Starting telemetry-queryd..."
    cd "$DAEMON_DIR" || exit 1
    python3 telemetry_queryd.py >> "$LOGFILE" 2>&1 &
    PID=$!
    echo $PID > "$PIDFILE"
    for i in $(seq 1 30); do
        if kill -0 $PID 2>/dev/null; then
            if python3 -c "import socket; s = socket.socket(); s.connect(('127.0.0.1', 8085)); s.close()" 2>/dev/null; then
                echo "telemetry-queryd started successfully (PID $PID)"
                return 0
            fi
            sleep 0.1
        else
            echo "telemetry-queryd failed to start. See $LOGFILE for details."
            rm -f "$PIDFILE"
            return 1
        fi
    done
    echo "telemetry-queryd started (PID $PID), waiting for listener..."
    return 0
}

stop() {
    if [ -f "$PIDFILE" ]; then
        PID=$(cat "$PIDFILE")
        echo "Stopping telemetry-queryd (PID $PID)..."
        kill "$PID" 2>/dev/null || true
        for i in $(seq 1 20); do
            if kill -0 "$PID" 2>/dev/null; then
                sleep 0.1
            else
                break
            fi
        done
        kill -9 "$PID" 2>/dev/null || true
        rm -f "$PIDFILE"
        echo "telemetry-queryd stopped"
    else
        pkill -f telemetry_queryd.py 2>/dev/null || true
        echo "telemetry-queryd is not running"
    fi
    return 0
}

status() {
    if [ -f "$PIDFILE" ] && kill -0 $(cat "$PIDFILE") 2>/dev/null; then
        echo "telemetry-queryd is running (PID $(cat $PIDFILE))"
        return 0
    else
        echo "telemetry-queryd is not running"
        return 3
    fi
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        sleep 0.2
        start
        ;;
    status)
        status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
