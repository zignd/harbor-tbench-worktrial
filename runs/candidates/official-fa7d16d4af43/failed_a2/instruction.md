The release build at /app is broken. The compiled binary /app/bin/normalize (no source available) transforms raw sensor readings before they reach the database. Its exact transformation must be characterized by experiment before you can trust any downstream SQL.

The pipeline is run by /app/run_pipeline.sh. It reads /app/data/raw_samples.csv, passes readings through /app/bin/normalize, and loads results into /app/db/sensors.db. It then executes /app/sql/rollups.sql to populate the rollup tables hourly_stats and zone_energy.

The binary reads lines of the form reading_id,raw_value from stdin and writes reading_id,normalized_value to stdout. Raw values are integer ADC counts in the range 0 to 1023.

Four correctness requirements must hold when /app/run_pipeline.sh is executed on any fresh input placed at /app/data/raw_samples.csv:

1. Every row in hourly_stats must have p90_normalized within 0.5 of the true 90th percentile of normalized values for that (zone, hour) bucket.

2. Every row in zone_energy must have total_energy within 1.0 of the true sum of raw_energy_wh for all readings in that zone.

3. The readings table in /app/db/sensors.db must contain exactly one row per line of input in raw_samples.csv (excluding the header).

4. Running /app/run_pipeline.sh twice in succession on the same input must produce identical values in hourly_stats and zone_energy.

Investigate the normalizer's actual behavior and repair whatever in the pipeline is needed so all four requirements are met on inputs not yet seen.
