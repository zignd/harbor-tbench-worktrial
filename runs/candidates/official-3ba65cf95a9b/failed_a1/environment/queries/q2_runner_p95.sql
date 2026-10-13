-- Q2: Runner pool P95 duration for passed runs
WITH ranked_durations AS (
    SELECT
        runner_pool,
        duration_us,
        ROW_NUMBER() OVER (PARTITION BY runner_pool ORDER BY duration_us) as rk,
        COUNT(*) OVER (PARTITION BY runner_pool) as total_runs
    FROM test_events
    WHERE outcome = 'PASSED' AND timestamp >= 1700000000000
)
SELECT
    runner_pool,
    duration_us as p95_duration_us
FROM ranked_durations
WHERE rk = CAST(0.95 * total_runs AS INT)
ORDER BY runner_pool ASC;
