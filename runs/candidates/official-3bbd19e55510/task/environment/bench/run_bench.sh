#!/bin/bash
# run_bench.sh - Throughput benchmark for the sensor metrics pipeline
# Generates synthetic sample data, runs the full pipeline, and measures
# throughput in samples per second.
#
# Writes a single integer (samples/sec) to /app/bench/throughput.txt

set -euo pipefail

APP_DIR="/app"
BENCH_DIR="${APP_DIR}/bench"
RAW_DIR="${APP_DIR}/data/raw"
PACKED_DIR="${APP_DIR}/data/packed"
CONFIG="${APP_DIR}/config/channels.conf"
OUTPUT="${APP_DIR}/output/metrics_summary.json"
THROUGHPUT_FILE="${BENCH_DIR}/throughput.txt"

BENCH_CHANNELS=("bench_a" "bench_b" "bench_c" "bench_d")
SAMPLES_PER_CHANNEL=50000
TOTAL_SAMPLES=$(( ${#BENCH_CHANNELS[@]} * SAMPLES_PER_CHANNEL ))

log() { echo "[bench] $(date -Iseconds)  $*" >&2; }

log "Benchmark starting: ${TOTAL_SAMPLES} total samples across ${#BENCH_CHANNELS[@]} channels"

# ---------------------------------------------------------------------------
# Generate synthetic CSV data
# ---------------------------------------------------------------------------

log "Generating synthetic sample data"

python3 - <<GENEOF
import os, random, math
random.seed(42)
channels = [
    ("bench_a", 0.0, 10.0),
    ("bench_b", 100.0, 110.0),
    ("bench_c", -5.0, 5.0),
    ("bench_d", 0.001, 0.01),
]
samples = $SAMPLES_PER_CHANNEL
os.makedirs("${RAW_DIR}", exist_ok=True)
for ch, lo, hi in channels:
    path = f"${RAW_DIR}/{ch}.csv"
    with open(path, "w") as f:
        for i in range(samples):
            ts = 1700000000.0 + i * 0.001
            val = lo + (hi - lo) * random.random()
            f.write(f"{ts:.3f},{val:.6f}\n")
print(f"[bench] generated data for {len(channels)} channels")
GENEOF

# ---------------------------------------------------------------------------
# Extend channels.conf with bench channels (save and restore)
# ---------------------------------------------------------------------------

CONFIG_BACKUP="${CONFIG}.bench_backup"
cp "$CONFIG" "$CONFIG_BACKUP"

trap 'cp "$CONFIG_BACKUP" "$CONFIG"; rm -f "$CONFIG_BACKUP"' EXIT

cat >> "$CONFIG" <<CONFEOF
bench_a  20
bench_b  50
bench_c  30
bench_d  100
CONFEOF

# ---------------------------------------------------------------------------
# Run ingest for bench channels
# ---------------------------------------------------------------------------

if [[ -f "${APP_DIR}/bin/ingest" ]]; then
    log "Running ingest for bench channels"
    for ch in "${BENCH_CHANNELS[@]}"; do
        "${APP_DIR}/bin/ingest" "$ch" 2>/dev/null || true
    done
fi

# ---------------------------------------------------------------------------
# Time the pipeline
# ---------------------------------------------------------------------------

log "Timing pipeline execution"

T_START=$(date +%s%N)
bash "${APP_DIR}/run_pipeline.sh" >/dev/null 2>&1
T_END=$(date +%s%N)

ELAPSED_NS=$(( T_END - T_START ))
ELAPSED_S_FRAC=$(echo "scale=6; $ELAPSED_NS / 1000000000" | bc)

if [[ $ELAPSED_NS -le 0 ]]; then
    log "ERROR: could not measure elapsed time"
    echo "0" > "$THROUGHPUT_FILE"
    exit 1
fi

THROUGHPUT=$(echo "scale=0; $TOTAL_SAMPLES * 1000000000 / $ELAPSED_NS" | bc)

log "Elapsed: ${ELAPSED_S_FRAC}s  Throughput: ${THROUGHPUT} sps"

mkdir -p "$BENCH_DIR"
echo "$THROUGHPUT" > "$THROUGHPUT_FILE"

log "Result written to ${THROUGHPUT_FILE}: ${THROUGHPUT} sps"

# Clean up bench channel packed files
for ch in "${BENCH_CHANNELS[@]}"; do
    rm -f "${PACKED_DIR}/${ch}.bin" "${PACKED_DIR}/${ch}.meta"
done

log "Benchmark complete"
