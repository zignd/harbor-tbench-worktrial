-- Sensor data rollup queries
-- Populates hourly_stats and zone_energy tables for dashboard consumption

DROP TABLE IF EXISTS hourly_stats;
CREATE TABLE hourly_stats (
    zone            TEXT,
    hour            INTEGER,
    reading_count   INTEGER,
    avg_normalized  REAL,
    p90_normalized  REAL,
    min_normalized  REAL,
    max_normalized  REAL
);

-- Hourly statistics per zone
INSERT INTO hourly_stats
SELECT
    zone,
    timestamp_hour AS hour,
    COUNT(*)        AS reading_count,
    AVG(normalized_value)  AS avg_normalized,
    AVG(normalized_value)  AS p90_normalized,
    MIN(normalized_value)  AS min_normalized,
    MAX(normalized_value)  AS max_normalized
FROM readings
GROUP BY zone, timestamp_hour;


DROP TABLE IF EXISTS zone_energy;
CREATE TABLE zone_energy (
    zone            TEXT,
    total_energy    REAL,
    reading_count   INTEGER
);

-- Zone energy totals per zone
INSERT INTO zone_energy
SELECT
    r.zone          AS energy_zone,
    SUM(r.raw_energy_wh) AS total_energy,
    COUNT(*)        AS reading_count
FROM readings r
JOIN (
    SELECT energy_zone, COUNT(*) AS cnt
    FROM readings
    GROUP BY energy_zone
) sub ON r.zone = sub.energy_zone
GROUP BY r.zone;
