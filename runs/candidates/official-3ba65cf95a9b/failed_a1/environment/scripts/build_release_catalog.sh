#!/bin/bash
set -euo pipefail

SHARDS_DIR="${1:-/var/lib/build_data/shards}"
OUTPUT_DB="${2:-/var/lib/build_data/release_catalog.db}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "[build] Initializing release catalog at ${OUTPUT_DB}..."
rm -f "${OUTPUT_DB}" "${OUTPUT_DB}-wal" "${OUTPUT_DB}-shm"
mkdir -p "$(dirname "${OUTPUT_DB}")"

# Initialize database schema
sqlite3 "${OUTPUT_DB}" < "${REPO_ROOT}/schema/catalog_schema.sql"

# Create staging table directly in catalog database
sqlite3 "${OUTPUT_DB}" <<'SQL'
CREATE TABLE staging_events (
    record_id INTEGER,
    commit_hash TEXT,
    test_name TEXT,
    runner_pool TEXT,
    outcome TEXT,
    duration_us INTEGER,
    flags INTEGER,
    timestamp INTEGER
);
SQL

echo "[build] Ingesting shards from ${SHARDS_DIR}..."
for shard in "${SHARDS_DIR}"/*.dat; do
    [ -f "${shard}" ] || continue
    "${REPO_ROOT}/bin/decode_shard" "${shard}" | sqlite3 "${OUTPUT_DB}" ".mode tabs" ".import /dev/stdin staging_events"
done

echo "[build] Transferring records to release catalog..."
sqlite3 "${OUTPUT_DB}" <<'SQL'
INSERT INTO test_events (
    record_id, commit_hash, test_name, runner_pool, outcome, duration_us, timestamp
)
SELECT
    record_id, commit_hash, test_name, runner_pool, outcome, duration_us, timestamp
FROM staging_events
WHERE outcome != 'SKIPPED';

DROP TABLE staging_events;
SQL

echo "[build] Release catalog built at ${OUTPUT_DB}."
