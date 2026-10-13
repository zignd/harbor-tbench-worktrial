WITH commit_results AS (
    SELECT
        test_name,
        commit_hash,
        MAX(CASE WHEN outcome = 'PASSED' THEN 1 ELSE 0 END) AS has_pass,
        MAX(CASE WHEN outcome IN ('FAILED', 'TIMEOUT') THEN 1 ELSE 0 END) AS has_fail
    FROM test_events
    WHERE timestamp BETWEEN 1710604800000 AND 1711209600000
    GROUP BY test_name, commit_hash
)
SELECT
    test_name,
    COUNT(*) AS total_commits,
    SUM(CASE WHEN has_pass = 1 AND has_fail = 1 THEN 1 ELSE 0 END) AS flaky_commits,
    ROUND(CAST(SUM(CASE WHEN has_pass = 1 AND has_fail = 1 THEN 1 ELSE 0 END) AS REAL) / COUNT(*), 4) AS flake_rate
FROM commit_results
GROUP BY test_name
HAVING flaky_commits > 0
ORDER BY flake_rate DESC, flaky_commits DESC, test_name ASC
LIMIT 25;
