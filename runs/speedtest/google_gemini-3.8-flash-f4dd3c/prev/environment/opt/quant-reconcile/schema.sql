-- Quantitative Risk Simulation Reconciliation Ledger Schema

CREATE TABLE IF NOT EXISTS batch_reconcile (
    batch_id TEXT PRIMARY KEY,
    worker_node TEXT NOT NULL,
    record_count INTEGER NOT NULL,
    mean_drift REAL NOT NULL,
    var_surface REAL NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('MATCHED', 'DISCREPANCY')),
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS anomaly_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL,
    trade_id INTEGER NOT NULL,
    drift REAL NOT NULL,
    variance REAL NOT NULL,
    flag_reason TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(batch_id) REFERENCES batch_reconcile(batch_id)
);

CREATE TABLE IF NOT EXISTS worker_audit (
    worker_node TEXT NOT NULL,
    batch_id TEXT NOT NULL PRIMARY KEY,
    record_count INTEGER NOT NULL,
    spool_checksum TEXT NOT NULL,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_anomaly_batch ON anomaly_records(batch_id);
CREATE INDEX IF NOT EXISTS idx_worker_node ON worker_audit(worker_node);
