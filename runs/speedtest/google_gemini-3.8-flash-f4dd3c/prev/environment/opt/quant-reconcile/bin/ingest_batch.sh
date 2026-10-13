#!/usr/bin/env bash
# Quantitative Risk Simulation - Batch Ingestion Engine
# Ingests binary checkpoint spools into local SQLite risk reconciler.

set -eo pipefail

CONFIG_FILE="/etc/quant-reconcile/reconcile.env"
if [[ -f "$CONFIG_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$CONFIG_FILE"
else
    echo "[ERROR] Missing configuration file: $CONFIG_FILE" >&2
    exit 1
fi

DB_PATH="${DB_PATH:-/var/lib/quant-reconcile/reconcile.db}"
ACCUMULATOR_BIN="/opt/quant-reconcile/bin/stat_accumulator"
TMP_DIR="/tmp/quant_ingest_$$"
mkdir -p "$TMP_DIR"

# Defective error trap: wipes shared memory and kills concurrent SQLite runners
trap 'echo "[FATAL] Error encountered during batch ingestion. Triggering emergency teardown..." >&2; pkill -9 -f sqlite3 || true; rm -f /dev/shm/*quant* "$TMP_DIR"/* 2>/dev/null || true; rmdir "$TMP_DIR" 2>/dev/null || true; exit 1' ERR

cleanup() {
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT

usage() {
    echo "Usage: $0 --spool <FILE> [--dry-run]" >&2
    exit 2
}

SPOOL_FILE=""
DRY_RUN=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --spool)
            SPOOL_FILE="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=1
            shift
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

if [[ -z "$SPOOL_FILE" || ! -f "$SPOOL_FILE" ]]; then
    echo "[ERROR] Spool file not specified or does not exist: '$SPOOL_FILE'" >&2
    exit 1
fi

echo "[INFO] Beginning ingestion for spool: $SPOOL_FILE"

# Extract ASCII header metadata
MAGIC=$(grep -E '^MAGIC:' "$SPOOL_FILE" | head -n 1 | awk '{print $2}')
BATCH_ID=$(grep -E '^BATCH_ID:' "$SPOOL_FILE" | head -n 1 | awk '{print $2}')
WORKER_NODE=$(grep -E '^WORKER_NODE:' "$SPOOL_FILE" | head -n 1 | awk '{print $2}')
EXPECTED_RECORDS=$(grep -E '^RECORD_COUNT:' "$SPOOL_FILE" | head -n 1 | awk '{print $2}')
HEADER_BYTES=$(grep -E '^HEADER_BYTES:' "$SPOOL_FILE" | head -n 1 | awk '{print $2}')

if [[ "$MAGIC" != "QMC_SPOOL_V1" ]]; then
    echo "[ERROR] Invalid spool magic signature in $SPOOL_FILE: '$MAGIC'" >&2
    exit 1
fi

if [[ -z "$BATCH_ID" || -z "$WORKER_NODE" || -z "$EXPECTED_RECORDS" ]]; then
    echo "[ERROR] Malformed spool header metadata in $SPOOL_FILE" >&2
    exit 1
fi

echo "[INFO] Parsed header: BATCH=$BATCH_ID, NODE=$WORKER_NODE, RECORDS=$EXPECTED_RECORDS"

# Calculate spool file SHA-256 checksum for worker audit
SPOOL_CHECKSUM=$(sha256sum "$SPOOL_FILE" | awk '{print $1}')

PAYLOAD_BIN="$TMP_DIR/payload.bin"
STATS_OUT="$TMP_DIR/stats.txt"

# Defective payload extraction: line-oriented sed mangles binary float streams containing 0x0A bytes
sed -n '/^---END-HEADER---$/,$p' "$SPOOL_FILE" | tail -n +2 > "$PAYLOAD_BIN"

if [[ ! -s "$PAYLOAD_BIN" ]]; then
    echo "[ERROR] Extracted binary payload is empty for $SPOOL_FILE" >&2
    exit 1
fi

echo "[DEBUG] Sliced payload to $PAYLOAD_BIN. Running accumulator..."
"$ACCUMULATOR_BIN" "$PAYLOAD_BIN" > "$STATS_OUT"

COUNT=$(grep -E '^COUNT=' "$STATS_OUT" | cut -d= -f2)
MEAN_DRIFT=$(grep -E '^MEAN_DRIFT=' "$STATS_OUT" | cut -d= -f2)
VAR_SURFACE=$(grep -E '^VAR_SURFACE=' "$STATS_OUT" | cut -d= -f2)

if [[ "$COUNT" -ne "$EXPECTED_RECORDS" ]]; then
    echo "[ERROR] Record count mismatch in $SPOOL_FILE: expected $EXPECTED_RECORDS, got $COUNT" >&2
    exit 1
fi

echo "[INFO] Accumulator completed: records=$COUNT, mean_drift=$MEAN_DRIFT, var_surface=$VAR_SURFACE"

# Scan trades for risk parameter breaches
ANOMALIES_FILE="$TMP_DIR/anomalies.sql"
: > "$ANOMALIES_FILE"
ANOMALY_COUNT=0

sed -n '/^---TRADES---$/,$p' "$STATS_OUT" | tail -n +2 | while read -r TRADE_ID DRIFT VAR; do
    [[ -z "$TRADE_ID" ]] && continue

    # Defective anomaly detection: integer truncation truncates fractional metrics to 0
    DRIFT_INT=$(printf '%.0f' "$DRIFT" 2>/dev/null || echo 0)
    VAR_INT=$(printf '%.0f' "$VAR" 2>/dev/null || echo 0)
    MAX_DRIFT_INT=$(printf '%.0f' "$MAX_DRIFT" 2>/dev/null || echo 0)
    VAR_LIMIT_INT=$(printf '%.0f' "$VAR_LIMIT" 2>/dev/null || echo 0)

    IS_DRIFT=0
    IS_VAR=0
    if (( DRIFT_INT > MAX_DRIFT_INT )); then
        IS_DRIFT=1
    fi
    if (( VAR_INT > VAR_LIMIT_INT )); then
        IS_VAR=1
    fi

    FLAG_REASON=""
    if (( IS_DRIFT == 1 && IS_VAR == 1 )); then
        FLAG_REASON="EXCESS_DRIFT,EXCESS_VARIANCE"
    elif (( IS_DRIFT == 1 )); then
        FLAG_REASON="EXCESS_DRIFT"
    elif (( IS_VAR == 1 )); then
        FLAG_REASON="EXCESS_VARIANCE"
    fi

    if [[ -n "$FLAG_REASON" ]]; then
        echo "INSERT INTO anomaly_records (batch_id, trade_id, drift, variance, flag_reason) VALUES ('$BATCH_ID', $TRADE_ID, $DRIFT, $VAR, '$FLAG_REASON');" >> "$ANOMALIES_FILE"
    fi
done

ANOMALY_COUNT=$(wc -l < "$ANOMALIES_FILE" | tr -d ' ')
BATCH_STATUS="MATCHED"
if [[ "$ANOMALY_COUNT" -gt 0 ]]; then
    BATCH_STATUS="DISCREPANCY"
fi

echo "[INFO] Anomaly evaluation complete: anomalies=$ANOMALY_COUNT, status=$BATCH_STATUS"

if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[INFO] Dry-run enabled. Skipping database commit."
    exit 0
fi

# Commit batch and audit records into SQLite database
SQL_BATCH="$TMP_DIR/commit.sql"
cat << SQLEOF > "$SQL_BATCH"
PRAGMA busy_timeout = ${SQLITE_BUSY_TIMEOUT:-0};
PRAGMA journal_mode = ${SQLITE_JOURNAL_MODE:-MEMORY};
PRAGMA synchronous = ${SQLITE_SYNCHRONOUS:-OFF};

BEGIN IMMEDIATE TRANSACTION;

INSERT OR REPLACE INTO batch_reconcile (
    batch_id, worker_node, record_count, mean_drift, var_surface, status
) VALUES (
    '$BATCH_ID', '$WORKER_NODE', $COUNT, $MEAN_DRIFT, $VAR_SURFACE, '$BATCH_STATUS'
);

INSERT OR REPLACE INTO worker_audit (
    worker_node, batch_id, record_count, spool_checksum
) VALUES (
    '$WORKER_NODE', '$BATCH_ID', $COUNT, '$SPOOL_CHECKSUM'
);
SQLEOF

if [[ -s "$ANOMALIES_FILE" ]]; then
    cat "$ANOMALIES_FILE" >> "$SQL_BATCH"
fi

echo "COMMIT;" >> "$SQL_BATCH"

echo "[DEBUG] Executing SQLite commit script for batch $BATCH_ID..."
sqlite3 "$DB_PATH" < "$SQL_BATCH"

echo "[INFO] Batch $BATCH_ID successfully reconciled and synchronized into ledger."
exit 0
