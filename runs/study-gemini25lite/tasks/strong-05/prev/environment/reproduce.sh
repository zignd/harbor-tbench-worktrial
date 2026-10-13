#!/bin/bash
# Start bridge in background
python3 /app/ingestor/bridge.py > /var/log/bridge.log 2>&1 &
BRIDGE_PID=$!

sleep 2

# Run emitter
echo "Starting burst..."
/usr/bin/sensor_emitter 100000
echo "Burst complete."

sleep 5
kill $BRIDGE_PID
