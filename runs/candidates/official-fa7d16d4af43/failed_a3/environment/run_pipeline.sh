#!/bin/bash
set -euo pipefail

DB=/app/db/meters.db
SQL=/app/sql/rollups.sql
PY=/app/normalize_and_load.py

# Step 1: normalize raw counts and load into database
python3 "$PY"

# Step 2: run rollup SQL to populate summary tables
sqlite3 "$DB" < "$SQL"

echo "Pipeline complete."
