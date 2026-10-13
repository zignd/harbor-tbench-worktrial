#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SAMPLE_DIR="$REPO_ROOT/sample_data"
SAMPLE_DB="/tmp/sample_catalog.db"
SAMPLE_REF="$SAMPLE_DIR/sample_reference.json"

echo "=== Testing Sample Telemetry Aggregation ==="
rm -f "$SAMPLE_DB"

SHARDS_DIR="$SAMPLE_DIR" DB_FILE="$SAMPLE_DB" "$REPO_ROOT/scripts/build_release_catalog.sh"
REFERENCE_FILE="$SAMPLE_REF" DB_FILE="$SAMPLE_DB" "$REPO_ROOT/scripts/check_release_metrics.sh"

rm -f "$SAMPLE_DB"
echo "=== Sample Verification Finished Successfully ==="
