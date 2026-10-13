WITH ranked_durations AS (
    SELECT
        runner_pool,
        duration_us,
        ROW_NUMBER() OVER (PARTITION BY runner_pool ORDER BY duration_us ASC) AS rnk,
        COUNT(*) OVER (PARTITION BY runner_pool) AS pool_total
    FROM test_events
    WHERE timestamp BETWEEN 1710604800000 AND 1711209600000
)
SELECT
    runner_pool,
    pool_total AS sample_count,
    duration_us AS p95_duration_us
FROM ranked_durations
WHERE rnk = CAST(0.95 * pool_total AS INT)
ORDER BY runner_pool ASC;
