PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS batch_reconcile (
    batch_id TEXT PRIMARY KEY,
    worker_id TEXT NOT NULL,
    record_count INTEGER NOT NULL CHECK (record_count > 0),
    mean_drift REAL NOT NULL,
    var_surface REAL NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('MATCHED', 'DISCREPANCY')),
    spool_checksum TEXT NOT NULL,
    UNIQUE(worker_id, spool_checksum)
);

CREATE TABLE IF NOT EXISTS anomaly_records (
    batch_id TEXT NOT NULL,
    trade_id TEXT NOT NULL,
    worker_id TEXT NOT NULL,
    drift_value REAL NOT NULL,
    variance_value REAL NOT NULL,
    flag_reason TEXT NOT NULL CHECK (flag_reason IN (
        'MAX_DRIFT', 'VAR_LIMIT', 'MAX_DRIFT+VAR_LIMIT')),
    drift_threshold REAL NOT NULL,
    variance_threshold REAL NOT NULL,
    PRIMARY KEY (batch_id, trade_id),
    FOREIGN KEY (batch_id) REFERENCES batch_reconcile(batch_id)
);

CREATE TABLE IF NOT EXISTS worker_audit (
    worker_id TEXT PRIMARY KEY,
    batches_processed INTEGER NOT NULL CHECK (batches_processed >= 0),
    records_processed INTEGER NOT NULL CHECK (records_processed >= 0),
    spool_checksums TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS processed_spools (
    spool_checksum TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL,
    worker_id TEXT NOT NULL,
    record_count INTEGER NOT NULL,
    FOREIGN KEY (batch_id) REFERENCES batch_reconcile(batch_id)
);

CREATE INDEX IF NOT EXISTS anomaly_batch_idx
    ON anomaly_records(batch_id);
CREATE INDEX IF NOT EXISTS batch_worker_idx
    ON batch_reconcile(worker_id);
