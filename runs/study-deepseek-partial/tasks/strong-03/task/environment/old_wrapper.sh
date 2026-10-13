#!/bin/bash
# Old wrapper script used before the binary was moved to /usr/local/bin
# Kept for reference only; do not use in production.

INPUT_CSV="${1:-/app/sample_data.csv}"
BIN_PATH="/opt/legacy/bin/allocator"

if [ ! -f "$BIN_PATH" ]; then
    echo "Warning: legacy path not found, trying /usr/local/bin/allocator" >&2
    BIN_PATH="/usr/local/bin/allocator"
fi

if [ ! -f "$INPUT_CSV" ]; then
    echo "Error: input file not found: $INPUT_CSV" >&2
    exit 1
fi

exec "$BIN_PATH" "$INPUT_CSV"
