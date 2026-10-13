#!/usr/bin/env bash
# Quantitative Risk Simulation - Spool Archival Utility

set -eo pipefail

CONFIG_FILE="/etc/quant-reconcile/reconcile.env"
if [[ -f "$CONFIG_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$CONFIG_FILE"
fi

TARGET_DIR="${1:-$SPOOL_DIR}"
ARCHIVE_DIR="/var/archive/quant-reconcile"

if [[ ! -d "$TARGET_DIR" ]]; then
    echo "[WARN] Spool directory does not exist: $TARGET_DIR"
    exit 0
fi

mkdir -p "$ARCHIVE_DIR"
find "$TARGET_DIR" -name '*.spool' -type f -mtime +7 -exec mv {} "$ARCHIVE_DIR" \;
echo "[INFO] Old spools archived."
