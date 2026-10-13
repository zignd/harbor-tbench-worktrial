#!/bin/bash
# Dispatch checkpoint spools to the ingestion worker pool.
set -o errtrace
set -o nounset
set -o pipefail

BASE_DIR="${QUANT_BASE_DIR:-/opt/quant-reconcile}"
CONFIG_FILE="${QUANT_CONFIG:-/etc/quant-reconcile/reconcile.env}"
source "${BASE_DIR}/lib/common.sh"
source "${CONFIG_FILE}"

SOURCE_DIR=""
DATABASE_FILE=""
LOG_DIR="${TMPDIR:-/tmp}/quant-reconcile-dispatch.$$"

usage() {
    printf 'usage: %s --source DIR --database FILE\n' "$0"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --source)
            [[ $# -ge 2 ]] || { usage >&2; exit 2; }
            SOURCE_DIR="$2"
            shift 2
            ;;
        --database)
            [[ $# -ge 2 ]] || { usage >&2; exit 2; }
            DATABASE_FILE="$2"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            printf 'unknown dispatcher option: %s\n' "$1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

[[ -n "${SOURCE_DIR}" && -n "${DATABASE_FILE}" ]] || { usage >&2; exit 2; }
[[ -d "${SOURCE_DIR}" ]] || quant_die "batch source directory is missing" "${SOURCE_DIR}"
[[ -d "$(dirname "${DATABASE_FILE}")" ]] || quant_die "database directory is missing" "$(dirname "${DATABASE_FILE}")"
SOURCE_DIR="$(readlink -f -- "${SOURCE_DIR}")"
DATABASE_FILE="$(readlink -f -- "${DATABASE_FILE}")"

[[ "${RECONCILE_MAX_PARALLEL}" =~ ^[1-9][0-9]*$ ]] || quant_die "invalid parallel worker limit" "${RECONCILE_MAX_PARALLEL}"
shopt -s nullglob
spools=("${SOURCE_DIR}"/*.spool)
shopt -u nullglob
[[ ${#spools[@]} -gt 0 ]] || quant_die "no checkpoint spools found" "${SOURCE_DIR}"

rm -rf -- "${LOG_DIR}"
mkdir -p -- "${LOG_DIR}"
chmod 0700 -- "${LOG_DIR}"

for spool in "${spools[@]}"; do
    label="$(basename -- "${spool}" .spool)"
    while (( $(jobs -rp | wc -l) >= RECONCILE_MAX_PARALLEL )); do
        sleep 0.02
    done
    (
        set -o errtrace
        set -o pipefail
        exec "${BASE_DIR}/bin/ingest_batch.sh" \
            --spool "${spool}" \
            --database "${DATABASE_FILE}" \
            --work-dir "${LOG_DIR}/work"
    ) > "${LOG_DIR}/${label}.out" 2> "${LOG_DIR}/${label}.err" &
done

failure=0
for pid in $(jobs -p); do
    if ! wait "${pid}"; then
        code=$?
        failure=1
        quant_error "ingestion worker returned exit code ${code}"
    fi
done

if (( failure != 0 )); then
    for log_file in "${LOG_DIR}"/*.err; do
        [[ -s "${log_file}" ]] || continue
        sed 's/^/  /' "${log_file}"
    done
    printf 'DISPATCH_STATUS=FAILED\n'
    exit 1
fi

printf 'DISPATCH_STATUS=OK\n'
rm -rf -- "${LOG_DIR}"
