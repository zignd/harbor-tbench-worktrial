#!/bin/bash
# orchestrate.sh - Pipeline orchestration script
# Drives the EMA computation engine for all configured channels
# and collects results into the final metrics summary.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"

PACKED_DIR="${APP_DIR}/data/packed"
CONFIG="${APP_DIR}/config/channels.conf"
OUTPUT_DIR="${APP_DIR}/output"
EMA_ENGINE="${APP_DIR}/src/ema_engine.py"
LOG_DIR="${APP_DIR}/logs"
PIPELINE_VERSION="3.0.1"

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

log_info()  { echo "[orchestrate] INFO  $(date -Iseconds)  $*" >&2; }
log_warn()  { echo "[orchestrate] WARN  $(date -Iseconds)  $*" >&2; }
log_error() { echo "[orchestrate] ERROR $(date -Iseconds)  $*" >&2; }

# ---------------------------------------------------------------------------
# Sanity checks
# ---------------------------------------------------------------------------

check_prerequisites() {
    log_info "Checking prerequisites (pipeline v${PIPELINE_VERSION})"

    if [[ ! -f "$CONFIG" ]]; then
        log_error "Channel config not found: $CONFIG"
        exit 1
    fi

    if [[ ! -f "$EMA_ENGINE" ]]; then
        log_error "EMA engine not found: $EMA_ENGINE"
        exit 1
    fi

    if [[ ! -d "$PACKED_DIR" ]]; then
        log_warn "Packed data directory missing: $PACKED_DIR"
        log_warn "Run ingest first to populate packed data"
    fi

    mkdir -p "$OUTPUT_DIR"
    mkdir -p "$LOG_DIR"
}

# ---------------------------------------------------------------------------
# Channel discovery
# ---------------------------------------------------------------------------

get_channels() {
    # Returns newline-separated list of channel names from config
    grep -v '^#' "$CONFIG" | grep -v '^[[:space:]]*$' | awk '{print $1}'
}

# ---------------------------------------------------------------------------
# Ingest step: compile and run the C ingest binary for each channel
# ---------------------------------------------------------------------------

run_ingest() {
    local channel="$1"
    local bin="${APP_DIR}/bin/ingest"

    if [[ ! -f "$bin" ]]; then
        log_warn "ingest binary not found at $bin, skipping ingest step"
        return 0
    fi

    local csv="${APP_DIR}/data/raw/${channel}.csv"
    if [[ ! -f "$csv" ]]; then
        log_warn "No CSV for channel '${channel}': $csv"
        return 0
    fi

    log_info "Ingesting channel '${channel}'"
    "$bin" "$channel" || {
        log_error "ingest failed for channel '${channel}'"
        return 1
    }
}

# ---------------------------------------------------------------------------
# EMA computation step
# ---------------------------------------------------------------------------

run_ema_for_channel() {
    local channel="$1"
    local tmp_output="${OUTPUT_DIR}/metrics_${channel}_$$.json"

    log_info "Computing EMA for channel '${channel}'"

    python3 "$EMA_ENGINE" \
        --channels "${channel}" \
        --packed-dir "$PACKED_DIR" \
        --output "${tmp_output}" \
        --config "$CONFIG" >&2 || {
        log_error "ema_engine failed for channel '${channel}'"
        return 1
    }

    # small stabilisation delay between channel invocations
    sleep 0.01

    echo "$tmp_output"
}

# ---------------------------------------------------------------------------
# Merge per-channel JSON files into one summary
# ---------------------------------------------------------------------------

merge_results() {
    local output_file="${OUTPUT_DIR}/metrics_summary.json"
    local tmp_files=("$@")

    log_info "Merging ${#tmp_files[@]} channel result(s) into ${output_file}"

    python3 - "${tmp_files[@]}" <<'PYMERGE'
import json, sys

files = sys.argv[1:]
merged = {}
for f in files:
    try:
        with open(f) as fh:
            data = json.load(fh)
        merged.update(data)
    except Exception as e:
        print(f"[merge] WARNING: could not read {f}: {e}", file=sys.stderr)

with open("/app/output/metrics_summary.json", "w") as fh:
    json.dump(merged, fh, indent=2)
    fh.write("\n")

print(f"[merge] wrote {len(merged)} channel(s)")
PYMERGE

    # Clean up temporary per-channel files
    for f in "${tmp_files[@]}"; do
        rm -f "$f"
    done
}

# ---------------------------------------------------------------------------
# Runtime log entry
# ---------------------------------------------------------------------------

write_run_log() {
    local channels="$1"
    local elapsed="$2"
    local logfile="${LOG_DIR}/pipeline_$(date +%Y%m%d_%H%M%S).log"

    cat >> "$logfile" <<LOGEOF
pipeline_version=${PIPELINE_VERSION}
timestamp=$(date -Iseconds)
channels=${channels}
elapsed_seconds=${elapsed}
status=complete
LOGEOF
    log_info "Run log written to ${logfile}"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

main() {
    local t_start
    t_start=$(date +%s%N 2>/dev/null || date +%s)

    check_prerequisites

    # Collect channel list
    mapfile -t CHANNELS < <(get_channels)

    if [[ ${#CHANNELS[@]} -eq 0 ]]; then
        log_error "No channels found in config: $CONFIG"
        exit 1
    fi

    log_info "Processing ${#CHANNELS[@]} channel(s): ${CHANNELS[*]}"

    # Ingest raw data for any channels whose packed file is missing
    for ch in "${CHANNELS[@]}"; do
        local packed_bin="${PACKED_DIR}/${ch}.bin"
        if [[ ! -f "$packed_bin" ]]; then
            run_ingest "$ch"
        fi
    done

    # Run EMA engine per channel (collected into array of tmp file paths)
    declare -a tmp_results=()
    for ch in "${CHANNELS[@]}"; do
        tmp_file=$(run_ema_for_channel "$ch")
        tmp_results+=("$tmp_file")
    done

    # Merge all per-channel results
    merge_results "${tmp_results[@]}"

    local t_end
    t_end=$(date +%s%N 2>/dev/null || date +%s)
    local elapsed=0
    if [[ ${#t_start} -gt 10 ]]; then
        elapsed=$(( (t_end - t_start) / 1000000 ))
        log_info "Total elapsed: ${elapsed}ms"
    fi

    write_run_log "${CHANNELS[*]}" "${elapsed}"
    log_info "Pipeline complete"
}

main "$@"
