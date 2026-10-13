#!/bin/bash
set -e
cd /app/src
cargo build --release --quiet
exec /app/src/target/release/sensor_pipeline /app/data/input.bin /app/db/results.db
