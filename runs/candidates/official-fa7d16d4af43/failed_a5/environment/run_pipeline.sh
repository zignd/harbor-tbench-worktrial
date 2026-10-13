#!/bin/bash
set -euo pipefail

# Sensor rollup pipeline
# Reads /app/data/raw_samples.csv, normalizes, loads to DB, runs rollups

DB_DIR="/app/db"
mkdir -p "$DB_DIR"

python3 /app/normalize_and_load.py

echo "Pipeline finished." >&2
