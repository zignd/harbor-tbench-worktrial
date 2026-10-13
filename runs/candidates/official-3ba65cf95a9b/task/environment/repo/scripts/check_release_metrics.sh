#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_FILE="${DB_FILE:-/var/lib/build_data/release_catalog.db}"
REFERENCE_FILE="${REFERENCE_FILE:-/var/lib/build_data/reference_metrics.json}"
QUERIES_DIR="${QUERIES_DIR:-$REPO_ROOT/queries}"

echo "=== Release Verification Gate ==="
echo "Catalog DB: $DB_FILE"

# 1. Integrity check
if [ ! -f "$DB_FILE" ]; then
    echo "FAIL: Catalog database not found at $DB_FILE"
    exit 1
fi

INTEGRITY=$(sqlite3 "$DB_FILE" "PRAGMA integrity_check;" 2>&1 || true)
if [ "$INTEGRITY" != "ok" ]; then
    echo "FAIL: SQLite integrity check failed: $INTEGRITY"
    exit 1
fi
echo "PASS: Database integrity check ok"

# 2. Database file size check (must not exceed 25.0 MB = 25,000,000 bytes)
DB_SIZE=$(stat -c%s "$DB_FILE")
MAX_SIZE=25000000
if [ "$DB_SIZE" -gt "$MAX_SIZE" ]; then
    echo "FAIL: Database file size $DB_SIZE bytes exceeds ceiling of $MAX_SIZE bytes ($(awk "BEGIN {printf \"%.2f\", $DB_SIZE/(1024*1024)}") MB > 25.0 MB)"
    exit 1
fi
echo "PASS: Database file size is $DB_SIZE bytes (<= 25.0 MB)"

# 3. Analytical Metric Parity Check
echo "Evaluating analytical query parity against reference ground truth..."
PARITY_OUTPUT=$(python3 - "$DB_FILE" "$REFERENCE_FILE" "$QUERIES_DIR" <<'PYEOF'
import sys, sqlite3, json

db_path = sys.argv[1]
ref_path = sys.argv[2]
queries_dir = sys.argv[3]

with open(ref_path, "r") as f: ref_data = json.load(f)
conn = sqlite3.connect(db_path)
total_metrics = 0
matching_metrics = 0

queries = [
    ("q1", f"{queries_dir}/q1_flaky_tests.sql"),
    ("q2", f"{queries_dir}/q2_runner_p95.sql"),
    ("q3", f"{queries_dir}/q3_slowdown_regression.sql"),
    ("q4", f"{queries_dir}/q4_stage_attribution.sql")
]

for q_name, q_path in queries:
    with open(q_path, "r") as f: sql = f.read()
    try: rows = conn.execute(sql).fetchall()
    except Exception as e: rows = []
    ref_rows = ref_data.get(q_name, [])
    dict_actual = {row[0]: row[1:] for row in rows}
    dict_ref = {row[0]: tuple(row[1:]) for row in ref_rows}
    for key, expected_vals in dict_ref.items():
        if key not in dict_actual:
            total_metrics += len(expected_vals)
            continue
        actual_vals = dict_actual[key]
        for exp, act in zip(expected_vals, actual_vals):
            total_metrics += 1
            if isinstance(exp, float) or isinstance(act, float):
                if abs(float(exp) - float(act)) <= 1e-4: matching_metrics += 1
            elif exp == act: matching_metrics += 1

parity = matching_metrics / total_metrics if total_metrics > 0 else 0.0
print(f"{parity:.6f} {matching_metrics} {total_metrics}")
PYEOF
)

PARITY_SCORE=$(echo "$PARITY_OUTPUT" | awk '{print $1}')
MATCHES=$(echo "$PARITY_OUTPUT" | awk '{print $2}')
TOTAL_CHECKS=$(echo "$PARITY_OUTPUT" | awk '{print $3}')

PARITY_OK=$(awk "BEGIN {print ($PARITY_SCORE >= 0.999) ? 1 : 0}")
if [ "$PARITY_OK" -ne 1 ]; then
    echo "FAIL: Analytical query parity score $PARITY_SCORE ($MATCHES/$TOTAL_CHECKS) is below required 0.999"
    exit 1
fi
echo "PASS: Analytical query parity score: $PARITY_SCORE ($MATCHES/$TOTAL_CHECKS)"

# 4. Latency Benchmark Check (5 warm runs across all 4 release qualification queries)
echo "Benchmarking query suite latency (5 warm iterations)..."
BENCH_TIME=$(python3 - "$DB_FILE" "$QUERIES_DIR" <<'PYEOF'
import sys, sqlite3, time
db_path, queries_dir = sys.argv[1], sys.argv[2]
conn = sqlite3.connect(db_path)
queries = [open(f"{queries_dir}/{q}").read() for q in ["q1_flaky_tests.sql", "q2_runner_p95.sql", "q3_slowdown_regression.sql", "q4_stage_attribution.sql"]]
for q in queries: conn.execute(q).fetchall()
t0 = time.perf_counter()
for _ in range(5):
    for q in queries: conn.execute(q).fetchall()
elapsed = time.perf_counter() - t0
print(f"{elapsed:.4f}")
PYEOF
)

echo "Benchmark execution time: ${BENCH_TIME}s"
LATENCY_OK=$(awk "BEGIN {print ($BENCH_TIME < 1.80) ? 1 : 0}")
if [ "$LATENCY_OK" -ne 1 ]; then
    echo "FAIL: Benchmark execution time ${BENCH_TIME}s exceeds 1.80s ceiling"
    exit 1
fi
echo "PASS: Benchmark execution time ${BENCH_TIME}s (< 1.80s ceiling)"
echo "=== ALL RELEASE GATE CHECKS PASSED ==="
exit 0
