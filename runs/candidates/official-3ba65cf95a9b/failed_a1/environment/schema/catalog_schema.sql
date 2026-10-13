-- CI Release Telemetry Catalog Schema
-- DDL for standalone qualification database

CREATE TABLE IF NOT EXISTS test_events (
    record_id INTEGER PRIMARY KEY,
    commit_hash TEXT NOT NULL,
    test_name TEXT NOT NULL,
    runner_pool TEXT NOT NULL,
    outcome TEXT NOT NULL,
    duration_us INTEGER NOT NULL,
    timestamp INTEGER NOT NULL
);

-- Rollup views for release metrics
CREATE VIEW IF NOT EXISTS v_recent_passed_runs AS
SELECT *
FROM test_events
WHERE outcome = 'PASSED' AND timestamp >= 1700000000000;

CREATE VIEW IF NOT EXISTS v_recent_failed_runs AS
SELECT *
FROM test_events
WHERE outcome = 'FAILED' AND timestamp >= 1700000000000;
