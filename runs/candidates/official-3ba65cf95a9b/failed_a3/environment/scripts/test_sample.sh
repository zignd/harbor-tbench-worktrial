#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

SAMPLE_DB="/tmp/sample_catalog.db"
SAMPLE_SHARDS="${REPO_ROOT}/sample_data"
SAMPLE_REF="${REPO_ROOT}/sample_data/sample_metrics.json"

echo "=== Running Smoke Test on Sample Telemetry Shard ==="
echo "Building sample catalog..."
bash "${REPO_ROOT}/scripts/build_release_catalog.sh" "${SAMPLE_SHARDS}" "${SAMPLE_DB}"

echo "Evaluating sample analytical metrics..."
PARITY=$(python3 - "${SAMPLE_DB}" "${SAMPLE_REF}" "${REPO_ROOT}/queries" <<'PYEOF'
import sys
import os
import json
import subprocess

db_path, ref_path, queries_dir = sys.argv[1], sys.argv[2], sys.argv[3]
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
    with open(os.path.join(queries_dir, qfile)) as qf:
        sql = qf.read()
    proc = subprocess.run(["sqlite3", "-json", db_path], input=sql, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    actual[key] = json.loads(proc.stdout) if proc.stdout.strip() else []

total, matched = 0, 0
for k in expected:
    exp_rows, act_rows = expected[k], actual.get(k, [])
    if len(exp_rows) != len(act_rows):
        total += max(len(exp_rows), len(act_rows)) * 3
        continue
    for e_item, a_item in zip(exp_rows, act_rows):
        for field, exp_val in e_item.items():
            total += 1
            act_val = a_item.get(field)
            if act_val is None:
                continue
            if isinstance(exp_val, (int, float)) and isinstance(act_val, (int, float)):
                diff = abs(exp_val - act_val)
                rel = diff / (1.0 + abs(exp_val))
                if diff <= 1e-4 or rel <= 1e-4:
                    matched += 1
            elif exp_val == act_val:
                matched += 1

score = matched / total if total > 0 else 0.0
print(f"{score:.4f}")
PYEOF
)

echo "Sample parity score: ${PARITY}"
if [ "${PARITY}" = "1.0000" ]; then
    echo "[PASS] Sample smoke test passed (100% parity on legacy sample records)."
    rm -f "${SAMPLE_DB}"
    exit 0
else
    echo "[FAIL] Sample parity mismatch: ${PARITY}"
    rm -f "${SAMPLE_DB}"
    exit 1
fi
