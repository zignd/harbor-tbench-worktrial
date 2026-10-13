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

-- Rollup views for release metrics within 7-day qualification window (timestamps in milliseconds)
CREATE VIEW IF NOT EXISTS v_recent_passed_runs AS
SELECT *
FROM test_events
WHERE outcome = 'PASSED' AND timestamp BETWEEN 1700000000000 AND 1700604800000;

CREATE VIEW IF NOT EXISTS v_recent_failed_runs AS
SELECT *
FROM test_events
WHERE outcome = 'FAILED' AND timestamp BETWEEN 1700000000000 AND 1700604800000;
