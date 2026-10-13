#!/usr/bin/env bash
# Deployment Orchestrator for Monte Carlo Risk Simulation Ledger Reconciler

set -eo pipefail

echo "[DEPLOY] Initializing Quantitative Reconciler Deployment..."

BASE_DIR="/opt/quant-reconcile"
CONFIG_FILE="/etc/quant-reconcile/reconcile.env"
SCHEMA_FILE="$BASE_DIR/schema.sql"
STAGING_DIR="$BASE_DIR/staging"
SERVICE_SRC="$BASE_DIR/bin/quant-reconcile-service"
SERVICE_DEST="/usr/local/bin/quant-reconcile-service"

# 1. Verify filesystem layout and permissions
echo "[DEPLOY] Step 1: Checking system directories..."
for dir in "/var/lib/quant-reconcile" "/var/spool/quant-reconcile/incoming" "/etc/quant-reconcile"; do
    if [[ ! -d "$dir" ]]; then
        echo "[DEPLOY] Creating required directory: $dir"
        mkdir -p "$dir"
    fi
done
chmod 0770 /var/lib/quant-reconcile || true

# 2. Check configuration
echo "[DEPLOY] Step 2: Validating configuration..."
if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "[DEPLOY-ERROR] Missing configuration file $CONFIG_FILE" >&2
    exit 1
fi
# shellcheck disable=SC1090
source "$CONFIG_FILE"

DB_PATH="${DB_PATH:-/var/lib/quant-reconcile/reconcile.db}"

# 3. Bootstrap database schema
echo "[DEPLOY] Step 3: Bootstrapping SQLite database schema at $DB_PATH..."
sqlite3 "$DB_PATH" < "$SCHEMA_FILE"

# Apply pragma settings from configuration
sqlite3 "$DB_PATH" << PRAGMAS
PRAGMA busy_timeout = ${SQLITE_BUSY_TIMEOUT:-0};
PRAGMA journal_mode = ${SQLITE_JOURNAL_MODE:-MEMORY};
PRAGMA synchronous = ${SQLITE_SYNCHRONOUS:-OFF};
PRAGMAS

# 4. Pre-flight staging verification
echo "[DEPLOY] Step 4: Running staging pre-flight verification on $STAGING_DIR..."
if [[ ! -d "$STAGING_DIR" ]]; then
    echo "[DEPLOY-ERROR] Staging directory not found: $STAGING_DIR" >&2
    exit 1
fi

"$BASE_DIR/bin/reconcile_all.sh" --batch-dir "$STAGING_DIR"

# 5. Database integrity validation
echo "[DEPLOY] Step 5: Running post-staging database integrity checks..."
INTEGRITY_CHECK=$(sqlite3 "$DB_PATH" "PRAGMA integrity_check;")
if [[ "$INTEGRITY_CHECK" != "ok" ]]; then
    echo "[DEPLOY-ERROR] SQLite integrity check failed: $INTEGRITY_CHECK" >&2
    exit 1
fi
echo "[DEPLOY] Database integrity verified: ok"

# 6. Service installation
echo "[DEPLOY] Step 6: Installing runner service to $SERVICE_DEST..."
install -m 755 "$SERVICE_SRC" "$SERVICE_DEST"

if [[ ! -x "$SERVICE_DEST" ]]; then
    echo "[DEPLOY-ERROR] Service binary not executable at $SERVICE_DEST" >&2
    exit 1
fi

echo "[DEPLOY] Deployment completed successfully! Service is active and ready."
exit 0
