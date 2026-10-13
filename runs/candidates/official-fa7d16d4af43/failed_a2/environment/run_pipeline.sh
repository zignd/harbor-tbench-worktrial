#!/bin/bash
set -euo pipefail

DB_PATH=/app/db/sensors.db
RAW_CSV=/app/data/raw_samples.csv
NORMALIZER=/app/bin/normalize
SQL_FILE=/app/sql/rollups.sql
LOADER=/app/normalize_and_load.py

echo "[pipeline] Starting sensor rollup pipeline"
echo "[pipeline] Input:  $RAW_CSV"
echo "[pipeline] DB:     $DB_PATH"

# Ensure DB directory exists
mkdir -p "$(dirname "$DB_PATH")"

# Run Python loader: normalizes readings and populates the readings table
echo "[pipeline] Running normalizer and loader..."
python3 "$LOADER"

# Apply rollup SQL queries
echo "[pipeline] Running rollup SQL..."
sqlite3 "$DB_PATH" < "$SQL_FILE"

echo "[pipeline] Pipeline complete."

# Print summary
echo "[pipeline] hourly_stats rows: $(sqlite3 "$DB_PATH" 'SELECT COUNT(*) FROM hourly_stats')"
echo "[pipeline] zone_energy rows:  $(sqlite3 "$DB_PATH" 'SELECT COUNT(*) FROM zone_energy')"
echo "[pipeline] readings rows:     $(sqlite3 "$DB_PATH" 'SELECT COUNT(*) FROM readings')"
