#!/bin/bash
PIDFILE=/var/run/telemetry-queryd.pid
LOGFILE=/var/log/telemetry-queryd.log

stop() {
    if [ -f "$PIDFILE" ]; then
        PID=$(cat "$PIDFILE")
        kill -TERM "$PID" 2>/dev/null || true
        sleep 0.5
        kill -9 "$PID" 2>/dev/null || true
        rm -f "$PIDFILE"
    fi
    pkill -f "telemetry_queryd.py" 2>/dev/null || true
}

start() {
    stop
    cd /opt/telemetry-service
    nohup python3 /opt/telemetry-service/telemetry_queryd.py > "$LOGFILE" 2>&1 &
    echo $! > "$PIDFILE"
    sleep 0.5
}

case "$1" in
    foreground)
        stop
        cd /opt/telemetry-service
        exec python3 /opt/telemetry-service/telemetry_queryd.py
        ;;
    stop)
        stop
        ;;
    restart|start|"")
        start
        ;;
    status)
        if [ -f "$PIDFILE" ] && kill -0 $(cat "$PIDFILE") 2>/dev/null; then
            echo "telemetry-queryd is running (pid $(cat "$PIDFILE"))"
            exit 0
        else
            echo "telemetry-queryd is not running"
            exit 1
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|foreground}"
        exit 1
        ;;
esac
