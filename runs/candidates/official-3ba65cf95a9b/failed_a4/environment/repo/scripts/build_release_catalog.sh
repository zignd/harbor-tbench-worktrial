#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_FILE="${DB_FILE:-/var/lib/build_data/release_catalog.db}"
SHARDS_DIR="${SHARDS_DIR:-/var/lib/build_data/shards}"
SCHEMA_FILE="${SCHEMA_FILE:-$REPO_ROOT/schema/catalog_schema.sql}"
DECODER="$REPO_ROOT/bin/decode_shard"

mkdir -p "$(dirname "$DB_FILE")"
rm -f "$DB_FILE"

# Initialize database schema
sqlite3 "$DB_FILE" < "$SCHEMA_FILE"

# Create staging table in catalog database
sqlite3 "$DB_FILE" "CREATE TABLE staging_events (record_id INTEGER, commit_hash TEXT, test_name TEXT, runner_pool TEXT, outcome TEXT, duration_us INTEGER, flags INTEGER, timestamp INTEGER);"

# Ingest each shard individually via subshells
for shard in "$SHARDS_DIR"/*.dat; do
    (
        "$DECODER" "$shard" | sqlite3 "$DB_FILE" ".separator \"\t\"" ".import /dev/stdin staging_events"
    )
done

# Naive staging migration: only filters skipped runs, ignoring flags and timestamps
sqlite3 "$DB_FILE" <<'SQL'
INSERT INTO test_events (record_id, commit_hash, test_name, runner_pool, outcome, duration_us, flags, timestamp)
SELECT record_id, commit_hash, test_name, runner_pool, outcome, duration_us, flags, timestamp
FROM staging_events
WHERE outcome != 'SKIPPED';

DROP TABLE staging_events;
SQL

echo "Release catalog built successfully at $DB_FILE"
