#!/bin/bash
set -e
cd /app/framecodec
echo "Building framecodec (release)..."
cargo build --release 2>&1
echo "Build complete. Starting service..."
nohup ./target/release/framecodec > /app/service.log 2>&1 &
echo $! > /app/service.pid
echo "Service started with PID $(cat /app/service.pid)"
