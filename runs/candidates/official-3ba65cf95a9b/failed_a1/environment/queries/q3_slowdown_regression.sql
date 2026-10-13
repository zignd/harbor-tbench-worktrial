-- Q3: Commit execution duration regression delta vs baseline
WITH baseline AS (
    SELECT
        test_name,
        AVG(duration_us) as avg_base_us
    FROM test_events
    WHERE outcome = 'PASSED' AND timestamp >= 1700000000000
    GROUP BY test_name
),
commit_durations AS (
    SELECT
        t.test_name,
        t.commit_hash,
        AVG(t.duration_us) as avg_commit_us
    FROM test_events t
    WHERE t.outcome = 'PASSED' AND t.timestamp >= 1700000000000
    GROUP BY t.test_name, t.commit_hash
)
SELECT
    c.test_name,
    c.commit_hash,
    ROUND(c.avg_commit_us, 2) as commit_avg_us,
    ROUND(b.avg_base_us, 2) as baseline_avg_us,
    ROUND(c.avg_commit_us - b.avg_base_us, 2) as regression_delta_us
FROM commit_durations c
JOIN baseline b ON c.test_name = b.test_name
WHERE (c.avg_commit_us - b.avg_base_us) > 100000
ORDER BY regression_delta_us DESC, c.test_name ASC, c.commit_hash ASC
LIMIT 10;
