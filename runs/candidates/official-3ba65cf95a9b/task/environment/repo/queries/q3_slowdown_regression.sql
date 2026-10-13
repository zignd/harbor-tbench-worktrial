SELECT
    test_name,
    commit_hash,
    COUNT(*) AS execution_count,
    ROUND(AVG(duration_us), 2) AS avg_duration_us,
    MAX(duration_us) AS max_duration_us
FROM test_events
WHERE timestamp BETWEEN 1710604800000 AND 1711209600000
GROUP BY test_name, commit_hash
HAVING execution_count >= 5
ORDER BY avg_duration_us DESC, test_name ASC
LIMIT 30;
