CREATE TABLE IF NOT EXISTS test_events (
    record_id INTEGER PRIMARY KEY,
    commit_hash TEXT NOT NULL,
    test_name TEXT NOT NULL,
    runner_pool TEXT NOT NULL,
    outcome TEXT NOT NULL,
    duration_us INTEGER NOT NULL,
    flags INTEGER NOT NULL,
    timestamp INTEGER NOT NULL
);

CREATE VIEW IF NOT EXISTS v_recent_qualification_events AS
SELECT *
FROM test_events
WHERE timestamp BETWEEN 1710604800000 AND 1711209600000;
