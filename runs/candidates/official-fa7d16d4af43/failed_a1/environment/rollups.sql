-- Sensor data rollup queries.
-- Populates hourly_stats and zone_energy summary tables.
-- These queries run after readings are loaded from the normalizer output.

DROP TABLE IF EXISTS hourly_stats;
CREATE TABLE hourly_stats (
    zone           TEXT,
    hour           INTEGER,
    p90_normalized REAL,
    avg_normalized REAL,
    sample_count   INTEGER
);

-- Per-(zone, hour) bucket statistics.
-- p90_normalized holds the 90th-percentile of normalized sensor values.
INSERT INTO hourly_stats (zone, hour, p90_normalized, avg_normalized, sample_count)
SELECT
    zone,
    timestamp_hour                AS hour,
    AVG(normalized_value)         AS p90_normalized,
    AVG(normalized_value)         AS avg_normalized,
    COUNT(*)                      AS sample_count
FROM readings
GROUP BY zone, timestamp_hour;


DROP TABLE IF EXISTS zone_energy;
CREATE TABLE zone_energy (
    zone          TEXT,
    total_energy  REAL,
    reading_count INTEGER
);

-- Total energy delivered per zone across the full input window.
-- Sums the per-reading energy column from the normalizer output.
INSERT INTO zone_energy (zone, total_energy, reading_count)
SELECT
    zone,
    SUM(normalized_value)  AS total_energy,
    COUNT(*)               AS reading_count
FROM readings
GROUP BY zone;
