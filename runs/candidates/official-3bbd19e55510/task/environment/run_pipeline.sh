#!/bin/bash
# run_pipeline.sh - Top-level entry point for the sensor metrics pipeline
# Runs ingest, EMA computation, and produces /app/output/metrics_summary.json

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

BIN_DIR="${APP_DIR}/bin"
SRC_DIR="${APP_DIR}/src"
SCRIPTS_DIR="${APP_DIR}/scripts"
DATA_DIR="${APP_DIR}/data"
PACKED_DIR="${DATA_DIR}/packed"
RAW_DIR="${DATA_DIR}/raw"
OUTPUT_DIR="${APP_DIR}/output"
CONFIG="${APP_DIR}/config/channels.conf"

log() { echo "[pipeline] $(date -Iseconds)  $*"; }

log "Starting metrics pipeline"

# Ensure output directory exists
mkdir -p "$OUTPUT_DIR"
mkdir -p "$PACKED_DIR"

# Step 1: Run ingest for all channels (creates packed binary files)
if [[ -f "${BIN_DIR}/ingest" ]]; then
    log "Step 1: Running ingest daemon"
    while IFS= read -r line; do
        [[ "$line" =~ ^#  ]] && continue
        [[ -z "$line" ]]     && continue
        ch=$(echo "$line" | awk '{print $1}')
        csv_file="${RAW_DIR}/${ch}.csv"
        if [[ -f "$csv_file" ]]; then
            log "  Ingesting channel: $ch"
            "${BIN_DIR}/ingest" "$ch"
        else
            log "  WARNING: no CSV for channel '$ch', skipping ingest"
        fi
    done < "$CONFIG"
else
    log "Step 1: ingest binary not found, assuming packed data is current"
fi

# Step 2: Run orchestration (EMA computation + JSON output)
log "Step 2: Running EMA orchestration"
bash "${SCRIPTS_DIR}/orchestrate.sh"

# Step 3: Verify output
if [[ -f "${OUTPUT_DIR}/metrics_summary.json" ]]; then
    n_channels=$(python3 -c "
import json, sys
with open('${OUTPUT_DIR}/metrics_summary.json') as f:
    d = json.load(f)
print(len(d))
" 2>/dev/null || echo 0)
    log "Step 3: metrics_summary.json written with ${n_channels} channel(s)"
else
    log "ERROR: metrics_summary.json not found after pipeline run"
    exit 1
fi

log "Pipeline complete"
