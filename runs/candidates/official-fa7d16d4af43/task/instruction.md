The release build at /app is broken. The compiled binary /app/bin/normalize transforms raw sensor readings before they reach the database. Its exact transformation must be characterized by experiment before you can trust any downstream SQL. No source is available.

The pipeline is run by /app/run_pipeline.sh, which reads /app/data/raw_samples.csv, passes readings through the normalizer, loads results into /app/db/sensors.db, and runs /app/sql/rollups.sql to populate two rollup tables: hourly_stats and zone_energy.

The binary reads lines of reading_id,raw_value from stdin and writes reading_id,normalized_value to stdout. Raw values are ADC counts in the range 0-1023.

Two correctness requirements must hold when /app/run_pipeline.sh is run on new input data placed at /app/data/raw_samples.csv:

1. Every row in hourly_stats must have p90_normalized within 0.5 of the true 90th percentile of normalized values for that (zone, hour) bucket.

2. Every row in zone_energy must have total_energy within 1.0 of the true sum of raw_energy_wh for all rows in that zone.

Repair whatever in the pipeline is needed so both thresholds are met on hidden inputs generated at verify time. The pipeline must complete successfully when /app/run_pipeline.sh is executed.
