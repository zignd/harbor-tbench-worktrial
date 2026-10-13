#!/usr/bin/env bash
# Quantitative Risk Simulation - Reconciliation Report Generator

set -eo pipefail

CONFIG_FILE="/etc/quant-reconcile/reconcile.env"
if [[ -f "$CONFIG_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$CONFIG_FILE"
fi

DB_PATH="${DB_PATH:-/var/lib/quant-reconcile/reconcile.db}"
OUTPUT_FILE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output|-o)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

if [[ ! -f "$DB_PATH" ]]; then
    echo "[ERROR] Ledger database not found: $DB_PATH" >&2
    exit 1
fi

QUERY="SELECT batch_id, worker_node, record_count, printf('%.6f', mean_drift), printf('%.6f', var_surface), status, processed_at FROM batch_reconcile ORDER BY processed_at DESC;"

if [[ -n "$OUTPUT_FILE" ]]; then
    sqlite3 -header -csv "$DB_PATH" "$QUERY" > "$OUTPUT_FILE"
    echo "[INFO] Report exported to $OUTPUT_FILE"
else
    sqlite3 -header -column "$DB_PATH" "$QUERY"
fi
