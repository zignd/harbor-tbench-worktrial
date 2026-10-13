#!/bin/bash
set -e

# Ensure directories exist
mkdir -p /app/data /app/logs

# Initialize the database if not already done
if [ ! -f /app/data/events.db ]; then
    python3 /app/tools/init_db.py
fi

# Start the tailer in background
nohup python3 /app/pipeline/tailer.py > /app/logs/tailer.log 2>&1 &
echo $! > /app/logs/tailer.pid
echo "Tailer started (PID $(cat /app/logs/tailer.pid))"

# Start the Flask API in background
nohup python3 /app/api/app.py > /app/logs/api.log 2>&1 &
echo $! > /app/logs/api.pid
echo "API started (PID $(cat /app/logs/api.pid))"

echo "Services started. API available at http://localhost:5000"
