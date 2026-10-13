The pipeline at /app is producing incorrect rollup values. The compiled binary /app/bin/normalize (no source available) transforms raw meter counts before they reach the database, and its exact transformation must be characterized by experiment.

The pipeline is run by /app/run_pipeline.sh. It reads /app/data/raw_samples.csv, passes raw_count values through /app/bin/normalize, and loads results into /app/db/meters.db. It then executes /app/sql/rollups.sql to populate the rollup tables interval_stats and circuit_demand.

The binary reads lines of the form meter_id,raw_count from stdin and writes meter_id,corrected_power to stdout. Raw counts are floating-point values in the range 0 to 1023.

Four correctness requirements must hold when /app/run_pipeline.sh is executed on any fresh input placed at /app/data/raw_samples.csv:

1. Every row in interval_stats must have p90_power within 0.5 of the true 90th percentile of corrected_power values for that (circuit, hour) bucket.

2. Every row in circuit_demand must have total_kwh within 1.0 of the true sum of demand_kwh for all readings in that circuit.

3. The readings table in /app/db/meters.db must contain exactly one row per line of input in raw_samples.csv (excluding the header).

4. Running /app/run_pipeline.sh twice in succession on the same input must produce identical values in interval_stats and circuit_demand.

Investigate the binary's actual behavior and repair whatever in the pipeline is needed so all four requirements are met on inputs not yet seen.
