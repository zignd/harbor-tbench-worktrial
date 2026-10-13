-- Metrics database schema
CREATE TABLE IF NOT EXISTS raw_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,
    metric TEXT NOT NULL,
    ts REAL NOT NULL,
    value REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_raw_metrics_service_metric_ts
    ON raw_metrics(service, metric, ts);

CREATE TABLE IF NOT EXISTS service_registry (
    service TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    first_seen REAL,
    last_seen REAL
);

CREATE TABLE IF NOT EXISTS ingest_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    ingested_at REAL NOT NULL,
    rows_inserted INTEGER NOT NULL
);
