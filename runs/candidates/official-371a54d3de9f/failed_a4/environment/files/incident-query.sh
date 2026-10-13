#!/bin/sh
# Legacy report retained for incident operators.
set -eu
DB=$1; OUT=$2
sqlite3 -tabs "$DB" "select event_id,account,epoch,sequence from audit_events order by epoch,sequence" > "$OUT"
