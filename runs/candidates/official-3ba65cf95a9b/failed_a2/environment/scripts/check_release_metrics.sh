#!/bin/bash
set -euo pipefail

CATALOG_DB="${1:-/var/lib/build_data/release_catalog.db}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REF_METRICS="${REPO_ROOT}/metrics/reference_metrics.json"

echo "=== Release Telemetry Gate Verification ==="
echo "Target catalog: ${CATALOG_DB}"

# 1. Existence and integrity check
if [ ! -f "${CATALOG_DB}" ]; then
    echo "[FAIL] Database file not found: ${CATALOG_DB}"
    exit 1
fi

INTEGRITY=$(sqlite3 "${CATALOG_DB}" "PRAGMA integrity_check;")
if [ "${INTEGRITY}" != "ok" ]; then
    echo "[FAIL] Integrity check failed: ${INTEGRITY}"
    exit 1
fi
echo "[PASS] Database integrity check: ok"

# 2. File size ceiling check (<= 25.0 MB = 26,214,400 bytes)
DB_SIZE=$(stat -c%s "${CATALOG_DB}")
MAX_SIZE=26214400
DB_SIZE_MB=$(echo "scale=2; ${DB_SIZE} / 1048576" | bc)

if [ "${DB_SIZE}" -gt "${MAX_SIZE}" ]; then
    echo "[FAIL] Database size (${DB_SIZE} bytes / ${DB_SIZE_MB} MB) exceeds maximum allowed size (25.0 MB / ${MAX_SIZE} bytes)"
    exit 1
fi
echo "[PASS] Database size: ${DB_SIZE} bytes (${DB_SIZE_MB} MB) <= 25.0 MB limit"

# 3. Analytical query parity check
echo "[check] Computing release metrics against ground truth..."
PARITY_RESULT=$(python3 - "${CATALOG_DB}" "${REF_METRICS}" "${REPO_ROOT}/queries" <<'PYEOF'
import sys
import os
import json
import subprocess

db_path = sys.argv[1]
ref_path = sys.argv[2]
queries_dir = sys.argv[3]

if not os.path.exists(ref_path):
    print(f"FAIL|Reference metrics file not found: {ref_path}")
    sys.exit(0)

with open(ref_path) as f:
    expected = json.load(f)

queries = [
    ("q1_flaky_tests", "q1_flaky_tests.sql"),
    ("q2_runner_p95", "q2_runner_p95.sql"),
    ("q3_slowdown_regression", "q3_slowdown_regression.sql"),
    ("q4_stage_attribution", "q4_stage_attribution.sql")
]

actual = {}
for key, qfile in queries:
    qpath = os.path.join(queries_dir, qfile)
    with open(qpath) as qf:
        sql = qf.read()
    proc = subprocess.run(["sqlite3", "-json", db_path], input=sql, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        print(f"FAIL|Query {key} failed: {proc.stderr}")
        sys.exit(0)
    try:
        res = json.loads(proc.stdout) if proc.stdout.strip() else []
    except Exception as e:
        print(f"FAIL|Failed parsing json output for {key}: {e}")
        sys.exit(0)
    actual[key] = res

# Compute parity score
total_fields = 0
matched_fields = 0
tol = 1e-4

for key in ["q1_flaky_tests", "q2_runner_p95", "q3_slowdown_regression", "q4_stage_attribution"]:
    exp_rows = expected.get(key, [])
    act_rows = actual.get(key, [])
    if len(exp_rows) != len(act_rows):
        total_fields += max(len(exp_rows), len(act_rows)) * 3
        continue
    for exp_item, act_item in zip(exp_rows, act_rows):
        for field, exp_val in exp_item.items():
            total_fields += 1
            act_val = act_item.get(field)
            if act_val is None:
                continue
            if isinstance(exp_val, (int, float)) and isinstance(act_val, (int, float)):
                diff = abs(exp_val - act_val)
                rel = diff / (1.0 + abs(exp_val))
                if diff <= tol or rel <= tol:
                    matched_fields += 1
            elif exp_val == act_val:
                matched_fields += 1

score = matched_fields / total_fields if total_fields > 0 else 0.0
print(f"OK|{score:.5f}")
PYEOF
)

STATUS=$(echo "${PARITY_RESULT}" | cut -d'|' -f1)
SCORE_OR_ERR=$(echo "${PARITY_RESULT}" | cut -d'|' -f2)

if [ "${STATUS}" != "OK" ]; then
    echo "[FAIL] Query execution error: ${SCORE_OR_ERR}"
    exit 1
fi

PARITY_SCORE="${SCORE_OR_ERR}"
MIN_PARITY="0.999"

PARITY_PASS=$(echo "${PARITY_SCORE} >= ${MIN_PARITY}" | bc -l)
if [ "${PARITY_PASS}" -ne 1 ]; then
    echo "[FAIL] Analytical query parity score (${PARITY_SCORE}) is below required minimum (${MIN_PARITY})"
    exit 1
fi
echo "[PASS] Analytical query parity score: ${PARITY_SCORE} >= ${MIN_PARITY}"

# 4. Latency benchmark (warm-up + 5 iterations)
echo "[check] Running query benchmark suite (5 warm runs)..."

# Warm-up run
for q in "${REPO_ROOT}"/queries/*.sql; do
    sqlite3 "${CATALOG_DB}" < "${q}" > /dev/null
done

START_NS=$(date +%s%N)
for iter in {1..5}; do
    for q in "${REPO_ROOT}"/queries/*.sql; do
        sqlite3 "${CATALOG_DB}" < "${q}" > /dev/null
    done
done
END_NS=$(date +%s%N)

TOTAL_MS=$(( (END_NS - START_NS) / 1000000 ))
AVG_SEC=$(echo "scale=4; ${TOTAL_MS} / 5000" | bc -l)
MAX_LATENCY="1.80"

LATENCY_PASS=$(echo "${AVG_SEC} < ${MAX_LATENCY}" | bc -l)
if [ "${LATENCY_PASS}" -ne 1 ]; then
    echo "[FAIL] Average benchmark latency (${AVG_SEC}s) exceeds threshold (${MAX_LATENCY}s)"
    exit 1
fi
echo "[PASS] Benchmark query latency: average ${AVG_SEC}s per run (< 1.80s threshold, total ${TOTAL_MS}ms for 5 runs)"

echo "=== Release Verification Gate PASSED ==="
exit 0
