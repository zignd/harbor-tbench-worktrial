#!/usr/bin/env bash
# Quantitative Risk Simulation - Parallel Batch Reconciler
# Dispatches worker ingest jobs over a spool directory.

set -eo pipefail

CONFIG_FILE="/etc/quant-reconcile/reconcile.env"
if [[ -f "$CONFIG_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$CONFIG_FILE"
else
    echo "[ERROR] Configuration not found: $CONFIG_FILE" >&2
    exit 1
fi

MAX_WORKERS="${MAX_WORKERS:-4}"
INGEST_BIN="/opt/quant-reconcile/bin/ingest_batch.sh"
BATCH_DIR="${SPOOL_DIR:-/var/spool/quant-reconcile/incoming}"

# Defective error trap in batch orchestrator
trap 'echo "[FATAL] Error in parallel batch orchestrator. Halting SQLite runners..." >&2; pkill -9 -f sqlite3 || true; rm -f /dev/shm/*quant* 2>/dev/null || true; exit 1' ERR

usage() {
    echo "Usage: $0 [--batch-dir <DIR>] [--workers <N>]" >&2
    exit 2
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --batch-dir)
            BATCH_DIR="$2"
            shift 2
            ;;
        --workers)
            MAX_WORKERS="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "[ERROR] Unknown argument: $1" >&2
            usage
            ;;
    esac
done

if [[ ! -d "$BATCH_DIR" ]]; then
    echo "[ERROR] Batch directory does not exist: $BATCH_DIR" >&2
    exit 1
fi

echo "[INFO] Scanning for spools in $BATCH_DIR (concurrency limit: $MAX_WORKERS)..."
shopt -s nullglob
SPOOLS=("$BATCH_DIR"/*.spool)
shopt -u nullglob

TOTAL_SPOOLS=${#SPOOLS[@]}
if [[ "$TOTAL_SPOOLS" -eq 0 ]]; then
    echo "[INFO] No .spool files found in $BATCH_DIR. Reconciliation queue is empty."
    exit 0
fi

echo "[INFO] Found $TOTAL_SPOOLS spools to reconcile. Spawning worker processes..."

PID_LIST=()
EXIT_CODE=0

for spool in "${SPOOLS[@]}"; do
    # Throttle workers to MAX_WORKERS
    while [[ $(jobs -r -p | wc -l) -ge "$MAX_WORKERS" ]]; do
        sleep 0.05
    done

    echo "[INFO] Dispatching worker ingest for $spool..."
    "$INGEST_BIN" --spool "$spool" &
    PID_LIST+=($!)
done

echo "[INFO] All jobs dispatched. Awaiting worker completion..."

for pid in "${PID_LIST[@]}"; do
    if ! wait "$pid"; then
        echo "[ERROR] Ingest worker job $pid failed!" >&2
        EXIT_CODE=1
    fi
done

if [[ "$EXIT_CODE" -ne 0 ]]; then
    echo "[FATAL] One or more ingest workers encountered fatal errors." >&2
    exit "$EXIT_CODE"
fi

echo "[INFO] All $TOTAL_SPOOLS spools reconciled successfully."
exit 0
