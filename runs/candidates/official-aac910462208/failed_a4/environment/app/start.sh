#!/bin/bash
set -e

cd /app/framecodec

echo "Building framecodec (release)..."
cargo build --release 2>&1

echo "Starting framecodec service on port 7000..."
nohup ./target/release/framecodec > /app/service.log 2>&1 &
SVC_PID=$!
echo $SVC_PID > /app/service.pid
echo "Service started with PID $SVC_PID"
sleep 1
if kill -0 $SVC_PID 2>/dev/null; then
    echo "Service is running."
else
    echo "Service failed to start. Check /app/service.log"
    cat /app/service.log
    exit 1
fi
