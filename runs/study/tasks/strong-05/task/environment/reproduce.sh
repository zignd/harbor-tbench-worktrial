#!/bin/bash
# Initialize DB so tables exist even if bridge fails
python3 -c "import sqlite3, os; os.makedirs('/var/lib/telemetry', exist_ok=True); conn = sqlite3.connect('/var/lib/telemetry/research.db'); conn.execute('CREATE TABLE IF NOT EXISTS telemetry (id INTEGER PRIMARY KEY, ts INTEGER, v1 REAL, v2 REAL, v3 REAL)'); conn.execute('CREATE TABLE IF NOT EXISTS system_events (id INTEGER, ts INTEGER)'); conn.commit()"

# Start bridge in background
python3 /app/ingestor/bridge.py > /var/log/bridge.log 2>&1 &
BRIDGE_PID=$!

sleep 2

# Run emitter
/usr/bin/sensor_emitter 100000

# Wait a bit for processing
sleep 10
kill $BRIDGE_PID || true
