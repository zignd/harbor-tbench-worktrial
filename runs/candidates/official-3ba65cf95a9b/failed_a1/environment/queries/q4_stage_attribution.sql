-- Q4: Failure attribution by runner pool
SELECT
    runner_pool,
    COUNT(*) as total_runs,
    SUM(CASE WHEN outcome = 'FAILED' THEN 1 ELSE 0 END) as failed_runs,
    ROUND(CAST(SUM(CASE WHEN outcome = 'FAILED' THEN 1 ELSE 0 END) AS REAL) / COUNT(*), 4) as failure_rate
FROM test_events
WHERE timestamp >= 1700000000000
GROUP BY runner_pool
ORDER BY runner_pool ASC;
