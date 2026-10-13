-- Q1: Top flaky tests across recent commits
WITH commit_stats AS (
    SELECT
        test_name,
        commit_hash,
        MAX(CASE WHEN outcome = 'PASSED' THEN 1 ELSE 0 END) as has_pass,
        MAX(CASE WHEN outcome = 'FAILED' THEN 1 ELSE 0 END) as has_fail
    FROM test_events
    WHERE timestamp BETWEEN 1700000000000 AND 1700604800000
    GROUP BY test_name, commit_hash
)
SELECT
    test_name,
    ROUND(CAST(SUM(CASE WHEN has_pass = 1 AND has_fail = 1 THEN 1 ELSE 0 END) AS REAL) / COUNT(*), 4) as flake_rate,
    COUNT(*) as total_commits
FROM commit_stats
GROUP BY test_name
HAVING COUNT(*) >= 5
ORDER BY flake_rate DESC, test_name ASC
LIMIT 10;
