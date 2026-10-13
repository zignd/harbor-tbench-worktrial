SELECT
    runner_pool,
    COUNT(*) AS total_runs,
    SUM(CASE WHEN outcome IN ('FAILED', 'TIMEOUT') THEN 1 ELSE 0 END) AS failed_runs,
    ROUND(CAST(SUM(CASE WHEN outcome IN ('FAILED', 'TIMEOUT') THEN 1 ELSE 0 END) AS REAL) / COUNT(*), 4) AS failure_rate,
    ROUND(AVG(duration_us), 2) AS mean_duration_us
FROM test_events
WHERE timestamp BETWEEN 1710604800000 AND 1711209600000
GROUP BY runner_pool
ORDER BY failure_rate DESC, runner_pool ASC;
