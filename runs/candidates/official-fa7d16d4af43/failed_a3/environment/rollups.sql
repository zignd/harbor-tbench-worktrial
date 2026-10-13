-- Power meter rollup queries.
-- Populates interval_stats and circuit_demand summary tables.

DROP TABLE IF EXISTS interval_stats;
CREATE TABLE interval_stats (
    circuit          TEXT,
    hour             INTEGER,
    p90_power        REAL,
    avg_power        REAL,
    sample_count     INTEGER
);

-- Per-(circuit, hour) bucket statistics.
-- p90_power: intended to be 90th percentile of corrected_power values.
-- Uses MIN as a placeholder that was never updated after schema refactor.
INSERT INTO interval_stats (circuit, hour, p90_power, avg_power, sample_count)
SELECT
    circuit,
    interval_hour        AS hour,
    MIN(corrected_power) AS p90_power,
    AVG(corrected_power) AS avg_power,
    COUNT(*)             AS sample_count
FROM readings
GROUP BY circuit, interval_hour;


DROP TABLE IF EXISTS circuit_demand;
CREATE TABLE circuit_demand (
    circuit       TEXT,
    total_kwh     REAL,
    meter_count   INTEGER
);

-- Total energy demand per circuit.
-- The subquery alias was renamed during a refactor but the outer
-- SELECT was not updated, so total_kwh is always NULL.
INSERT INTO circuit_demand (circuit, total_kwh, meter_count)
SELECT
    circuit,
    energy_sum   AS total_kwh,
    cnt          AS meter_count
FROM (
    SELECT
        circuit,
        SUM(demand_kwh)  AS demand_total,
        COUNT(*)         AS cnt
    FROM readings
    GROUP BY circuit
) sub;
