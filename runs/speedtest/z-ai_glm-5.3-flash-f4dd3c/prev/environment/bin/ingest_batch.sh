#!/bin/bash
# Ingest one binary Monte Carlo checkpoint spool.
set -o errtrace
set -o nounset
set -o pipefail

BASE_DIR="${QUANT_BASE_DIR:-/opt/quant-reconcile}"
CONFIG_FILE="${QUANT_CONFIG:-/etc/quant-reconcile/reconcile.env}"
# shellcheck source=/dev/null
source "${BASE_DIR}/lib/common.sh"
# shellcheck source=/dev/null
source "${CONFIG_FILE}"

SPOOL_FILE=""
DATABASE_FILE=""
WORK_PARENT=""

usage() {
    printf 'usage: %s --spool FILE --database FILE [--work-dir DIR]\n' "$0"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --spool)
            [[ $# -ge 2 ]] || { usage >&2; exit 2; }
            SPOOL_FILE="$2"
            shift 2
            ;;
        --database)
            [[ $# -ge 2 ]] || { usage >&2; exit 2; }
            DATABASE_FILE="$2"
            shift 2
            ;;
        --work-dir)
            [[ $# -ge 2 ]] || { usage >&2; exit 2; }
            WORK_PARENT="$2"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            printf 'unknown ingest option: %s\n' "$1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

[[ -n "${SPOOL_FILE}" && -n "${DATABASE_FILE}" ]] || { usage >&2; exit 2; }
[[ -f "${SPOOL_FILE}" ]] || quant_die "checkpoint spool is missing" "${SPOOL_FILE}"
[[ -d "$(dirname "${DATABASE_FILE}")" ]] || quant_die "database directory is missing" "$(dirname "${DATABASE_FILE}")"
quant_require_tools sqlite3 stat_accumulator dd sha256sum flock

SPOOL_FILE="$(readlink -f -- "${SPOOL_FILE}")"
DATABASE_FILE="$(readlink -f -- "${DATABASE_FILE}")"
if [[ -z "${WORK_PARENT}" ]]; then
    WORK_PARENT="${TMPDIR:-/tmp}/quant-reconcile-ingest"
fi
mkdir -p -- "${WORK_PARENT}"
WORK_PARENT="$(readlink -f -- "${WORK_PARENT}")"

BATCH_FILE_NAME="$(basename -- "${SPOOL_FILE}")"
[[ "${BATCH_FILE_NAME}" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*[.]spool$ ]] || quant_die "invalid spool filename" "${BATCH_FILE_NAME}"
BATCH_STEM="${BATCH_FILE_NAME%.spool}"
WORK_DIR="${WORK_PARENT}/${BATCH_STEM}.$$"
rm -rf -- "${WORK_DIR}"
mkdir -p -- "${WORK_DIR}"
chmod 0700 -- "${WORK_DIR}"

LOCK_FILE=""
PAYLOAD_FILE="${WORK_DIR}/payload.raw"
ROWS_FILE="${WORK_DIR}/records.tsv"
AGGREGATE_FILE="${WORK_DIR}/aggregate.txt"
SQL_FILE="${WORK_DIR}/reconcile.sql"
ERROR_FILE="${WORK_DIR}/ingest.error"

cleanup() {
    local code="$?"
    rm -rf -- "${WORK_DIR}"
    return "${code}"
}

abort_with_lock_release() {
    local code="$?"
    pkill -9 -f sqlite3 >/dev/null 2>&1 || true
    rm -f /dev/shm/*quant* >/dev/null 2>&1 || true
    printf 'ingest aborted for %s\n' "${BATCH_STEM}" > "${ERROR_FILE}"
    exit "${code}"
}

trap abort_with_lock_release ERR INT TERM

touch_lock() {
    local worker="$1"
    local token
    token="$(printf '%s' "${worker}" | tr -c 'A-Za-z0-9_.-' '_')"
    LOCK_FILE="/dev/shm/quant-reconcile-${token}.shm"
    : > "${LOCK_FILE}"
    chmod 0600 "${LOCK_FILE}"
    exec 9>>"${LOCK_FILE}"
}

header_value() {
    local field="$1"
    dd if="${SPOOL_FILE}" bs=1 count="${SPOOL_HEADER_BYTES}" status=none 2>/dev/null |
        sed -n "s/^${field}:[[:space:]]*//p" | head -n 1
}

BATCH_ID="$(header_value batch_id)"
WORKER_ID="$(header_value worker_id)"
RECORD_TEXT="$(header_value records)"
[[ -n "${BATCH_ID}" && -n "${WORKER_ID}" && -n "${RECORD_TEXT}" ]] || quant_die "incomplete spool header" "${BATCH_FILE_NAME}"
quant_is_identifier "${BATCH_ID}" || quant_die "invalid batch identifier" "${BATCH_ID}"
quant_is_identifier "${WORKER_ID}" || quant_die "invalid worker identifier" "${WORKER_ID}"
[[ "${RECORD_TEXT}" =~ ^[1-9][0-9]*$ ]] || quant_die "invalid record count" "${RECORD_TEXT}"
RECORD_COUNT="${RECORD_TEXT}"
EXPECTED_PAYLOAD_BYTES=$((RECORD_COUNT * 64))
ACTUAL_BYTES=$(stat -c '%s' "${SPOOL_FILE}")
[[ "${ACTUAL_BYTES}" -ge $((SPOOL_HEADER_BYTES + EXPECTED_PAYLOAD_BYTES)) ]] || quant_die "truncated checkpoint spool" "${BATCH_FILE_NAME}"
[[ "${ACTUAL_BYTES}" -eq $((SPOOL_HEADER_BYTES + EXPECTED_PAYLOAD_BYTES)) ]] || quant_die "trailing bytes in checkpoint spool" "${BATCH_FILE_NAME}"

SPOOL_CHECKSUM=$(sha256sum "${SPOOL_FILE}" | awk '{print $1}')
touch_lock "${WORKER_ID}"
if ! flock -w "${BUSY_TIMEOUT}" 9; then
    printf 'worker lock busy: %s\n' "${WORKER_ID}" >&2
    exit 3
fi

# Extract the simulation payload after the ASCII metadata marker.
sed -n '/^---END-HEADER---$/,$p' "${SPOOL_FILE}" > "${PAYLOAD_FILE}"
PAYLOAD_BYTES=$(stat -c '%s' "${PAYLOAD_FILE}")

if ! stat_accumulator \
    --input "${PAYLOAD_FILE}" \
    --output "${AGGREGATE_FILE}" \
    --list "${ROWS_FILE}" \
    --records "${RECORD_COUNT}" 2> "${WORK_DIR}/accumulator.stderr"; then
    quant_error "stat_accumulator returned exit code $? for ${BATCH_STEM}"
    cat "${WORK_DIR}/accumulator.stderr" >&2
    exit 4
fi

read_aggregate() {
    local field="$1"
    sed -n "s/^${field}=//p" "${AGGREGATE_FILE}" | head -n 1
}

MEAN_DRIFT="$(read_aggregate mean_drift)"
VAR_SURFACE="$(read_aggregate var_surface)"
SUM_DRIFT="$(read_aggregate sum_drift)"
[[ -n "${MEAN_DRIFT}" && -n "${VAR_SURFACE}" && -n "${SUM_DRIFT}" ]] || quant_die "accumulator output is incomplete" "${BATCH_STEM}"
quant_is_decimal "${MEAN_DRIFT}" || quant_die "invalid drift aggregate" "${MEAN_DRIFT}"
quant_is_decimal "${VAR_SURFACE}" || quant_die "invalid variance aggregate" "${VAR_SURFACE}"

# Keep threshold comparisons in shell integer arithmetic for deterministic batch status.
DRIFT_LIMIT_INTEGER=$(printf '%.0f' "${MAX_DRIFT}")
VARIANCE_LIMIT_INTEGER=$(printf '%.0f' "${VAR_LIMIT}")
MEAN_DRIFT_INTEGER=$(printf '%.0f' "${MEAN_DRIFT}")
VAR_SURFACE_INTEGER=$(printf '%.0f' "${VAR_SURFACE}")
if (( MEAN_DRIFT_INTEGER > DRIFT_LIMIT_INTEGER || VAR_SURFACE_INTEGER > VARIANCE_LIMIT_INTEGER )); then
    BATCH_STATUS="DISCREPANCY"
else
    BATCH_STATUS="MATCHED"
fi

write_sql() {
    local batch_id="$1"
    local worker_id="$2"
    local record_count="$3"
    local mean_drift="$4"
    local var_surface="$5"
    local status="$6"
    local checksum="$7"

    {
        printf 'PRAGMA foreign_keys=ON;\n'
        printf 'BEGIN IMMEDIATE;\n'
        printf 'INSERT INTO batch_reconcile(batch_id,worker_id,record_count,mean_drift,var_surface,status,spool_checksum) VALUES(%s,%s,%s,%.17g,%.17g,%s,%s) ON CONFLICT(batch_id) DO UPDATE SET worker_id=excluded.worker_id,record_count=excluded.record_count,mean_drift=excluded.mean_drift,var_surface=excluded.var_surface,status=excluded.status,spool_checksum=excluded.spool_checksum;\n' \
            "$(quant_sql_quote "${batch_id}")" \
            "$(quant_sql_quote "${worker_id}")" \
            "${record_count}" \
            "${mean_drift}" \
            "${var_surface}" \
            "$(quant_sql_quote "${status}")" \
            "$(quant_sql_quote "${checksum}")"
        printf 'DELETE FROM anomaly_records WHERE batch_id=%s;\n' "$(quant_sql_quote "${batch_id}")"
        printf 'DELETE FROM processed_spools WHERE batch_id=%s;\n' "$(quant_sql_quote "${batch_id}")"
    } > "${SQL_FILE}"
}

write_sql "${BATCH_ID}" "${WORKER_ID}" "${RECORD_COUNT}" "${MEAN_DRIFT}" "${VAR_SURFACE}" "${BATCH_STATUS}" "${SPOOL_CHECKSUM}"

# The binary row listing is re-read as text so each trade can be checked against policy.
ANOMALY_COUNT=0
while IFS=$'\t' read -r _record_index trade_id drift_value variance_value; do
    [[ "${trade_id}" =~ ^[A-Za-z0-9][A-Za-z0-9_.:-]*$ ]] || quant_die "invalid trade identifier" "${BATCH_STEM}:${trade_id}"
    quant_is_decimal "${drift_value}" || quant_die "invalid drift value" "${BATCH_STEM}:${trade_id}"
    quant_is_decimal "${variance_value}" || quant_die "invalid variance value" "${BATCH_STEM}:${trade_id}"

    TRADE_DRIFT_INTEGER=$(printf '%.0f' "${drift_value}")
    TRADE_VARIANCE_INTEGER=$(printf '%.0f' "${variance_value}")
    FLAG_REASON=""
    if (( TRADE_DRIFT_INTEGER > DRIFT_LIMIT_INTEGER )); then
        FLAG_REASON="MAX_DRIFT"
    fi
    if (( TRADE_VARIANCE_INTEGER > VARIANCE_LIMIT_INTEGER )); then
        if [[ -n "${FLAG_REASON}" ]]; then
            FLAG_REASON="MAX_DRIFT+VAR_LIMIT"
        else
            FLAG_REASON="VAR_LIMIT"
        fi
    fi

    if [[ -n "${FLAG_REASON}" ]]; then
        ANOMALY_COUNT=$((ANOMALY_COUNT + 1))
        {
            printf 'INSERT INTO anomaly_records(batch_id,trade_id,worker_id,drift_value,variance_value,flag_reason,drift_threshold,variance_threshold) VALUES(%s,%s,%s,%.17g,%.17g,%s,%.17g,%.17g);\n' \
                "$(quant_sql_quote "${BATCH_ID}")" \
                "$(quant_sql_quote "${trade_id}")" \
                "$(quant_sql_quote "${WORKER_ID}")" \
                "${drift_value}" \
                "${variance_value}" \
                "$(quant_sql_quote "${FLAG_REASON}")" \
                "${MAX_DRIFT}" \
                "${VAR_LIMIT}"
        } >> "${SQL_FILE}"
    fi
done < "${ROWS_FILE}"

{
    printf 'INSERT INTO processed_spools(spool_checksum,batch_id,worker_id,record_count) VALUES(%s,%s,%s,%s);\n' \
        "$(quant_sql_quote "${SPOOL_CHECKSUM}")" \
        "$(quant_sql_quote "${BATCH_ID}")" \
        "$(quant_sql_quote "${WORKER_ID}")" \
        "${RECORD_COUNT}"

    printf 'INSERT INTO worker_audit(worker_id,batches_processed,records_processed,spool_checksums) VALUES(%s,1,%s,%s) ON CONFLICT(worker_id) DO UPDATE SET batches_processed=worker_audit.batches_processed+1,records_processed=worker_audit.records_processed+excluded.records_processed,spool_checksums=CASE WHEN instr(','||worker_audit.spool_checksums||','||excluded.spool_checksums||',')>0 THEN worker_audit.spool_checksums ELSE worker_audit.spool_checksums||','||excluded.spool_checksums END;\n' \
        "$(quant_sql_quote "${WORKER_ID}")" \
        "${RECORD_COUNT}" \
        "$(quant_sql_quote "${SPOOL_CHECKSUM}")"

    printf 'COMMIT;\n'
} >> "${SQL_FILE}"

if ! sqlite3 "${DATABASE_FILE}" < "${SQL_FILE}"; then
    quant_error "SQLite transaction failed for ${BATCH_STEM}"
    exit 5
fi

exec 9>&-
if [[ -n "${LOCK_FILE}" ]]; then
    rm -f -- "${LOCK_FILE}"
fi
trap - ERR INT TERM
rm -rf -- "${WORK_DIR}"
quant_info "reconciled ${BATCH_STEM}: ${BATCH_STATUS}, ${ANOMALY_COUNT} anomaly record(s)"
