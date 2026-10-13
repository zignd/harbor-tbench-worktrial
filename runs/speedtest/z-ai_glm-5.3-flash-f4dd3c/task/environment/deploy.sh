#!/bin/bash
# Stage and verify the quantitative reconciliation deployment.
set -o errtrace
set -o nounset
set -o pipefail

BASE_DIR="${QUANT_BASE_DIR:-/opt/quant-reconcile}"
CONFIG_FILE="${QUANT_CONFIG:-/etc/quant-reconcile/reconcile.env}"
STATE_DIR="${QUANT_STATE_DIR:-/var/lib/quant-reconcile}"
INCOMING_DIR="${QUANT_INCOMING_DIR:-/var/spool/quant-reconcile/incoming}"
DATABASE_FILE="${STATE_DIR}/reconcile.db"
SERVICE_FILE="/usr/local/bin/quant-reconcile-service"
source "${BASE_DIR}/lib/common.sh"

[[ $(id -u) -eq 0 ]] || quant_die "deployment must run as root"
quant_require_tools sqlite3 install stat flock sha256sum
[[ -d "${BASE_DIR}/staging" ]] || quant_die "staging batch directory is missing" "${BASE_DIR}/staging"
[[ -x "${BASE_DIR}/bin/stat_accumulator" ]] || quant_die "stat accumulator is not executable"
[[ -x "${BASE_DIR}/bin/ingest_batch.sh" ]] || quant_die "ingestion script is not executable"
[[ -x "${BASE_DIR}/bin/reconcile_all.sh" ]] || quant_die "dispatcher is not executable"

install -d -m 0770 "${STATE_DIR}"
install -d -m 0755 "$(dirname "${CONFIG_FILE}")"
install -d -m 0755 "${INCOMING_DIR}"
if [[ ! -f "${CONFIG_FILE}" ]]; then
    install -m 0644 "${BASE_DIR}/config/reconcile.env" "${CONFIG_FILE}"
fi

source "${CONFIG_FILE}"
[[ "${SPOOL_HEADER_BYTES}" =~ ^[1-9][0-9]*$ ]] || quant_die "invalid spool header size"
[[ "${MAX_DRIFT}" =~ ^[+-]?[0-9]+([.][0-9]+)?$ ]] || quant_die "invalid drift tolerance"
[[ "${VAR_LIMIT}" =~ ^[+-]?[0-9]+([.][0-9]+)?$ ]] || quant_die "invalid variance tolerance"
[[ "${RECONCILE_MAX_PARALLEL}" =~ ^[1-9][0-9]*$ ]] || quant_die "invalid parallel worker limit"

quant_validate_mode "${STATE_DIR}" "770"
spool_count=$(find "${BASE_DIR}/staging" -maxdepth 1 -type f -name '*.spool' | wc -l)
(( spool_count > 0 )) || quant_die "no staged simulation batches"

if [[ ! -f "${DATABASE_FILE}" ]]; then
    sqlite3 "${DATABASE_FILE}" < "${BASE_DIR}/schema/schema.sql"
fi

quant_info "running staged pre-flight reconciliation"
if ! "${BASE_DIR}/bin/reconcile_all.sh" \
    --source "${BASE_DIR}/staging" \
    --database "${DATABASE_FILE}"; then
    quant_error "staged batch reconciliation failed"
    exit 1
fi

INTEGRITY="$(sqlite3 "${DATABASE_FILE}" 'PRAGMA integrity_check;' 2>&1)"
if [[ "${INTEGRITY}" != "ok" ]]; then
    printf 'SQLITE_CORRUPT: %s\n' "${INTEGRITY}"
    exit 1
fi

BATCH_ROWS=$(sqlite3 "${DATABASE_FILE}" 'SELECT count(*) FROM batch_reconcile;')
[[ "${BATCH_ROWS}" -gt 0 ]] || quant_die "preflight reconciliation produced no ledger rows"

install -m 0755 "${BASE_DIR}/service/quant-reconcile-service" "${SERVICE_FILE}"
chmod 0755 "${SERVICE_FILE}"
quant_info "deployment complete: ${BATCH_ROWS} staged ledger row(s)"
