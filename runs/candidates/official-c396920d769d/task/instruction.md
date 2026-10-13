You have inherited a Rust sensor-aggregation pipeline at /app/src/. The pipeline reads batched sensor records from /app/data/input.bin, accumulates fixed-point statistics, and writes rows to /app/db/results.db. Documentation for the binary format and database schema is at /app/docs/format.md. A helper script at /app/data/generate_batch.py creates additional input files for any record count and batch ID.

When you build and run the current source against the provided sample batch, the output rows in /app/db/results.db differ from those produced by the reference binary /app/bin/accumulator_ref on the same input. Fix the pipeline source so that:

1. For every input batch, the pipeline writes rows to /app/db/results.db that are identical to those the reference binary produces on the same input — the fixed_mean, fixed_variance, and checksum columns must match exactly.
2. The pipeline processes 500,000 sensor records in under 4 seconds on a single CPU core.
3. /app/db/results.db exists after running the pipeline on /app/data/input.bin and contains exactly one row with the correct values for that batch.
4. The schema remains: batch_id INTEGER, sample_count INTEGER, fixed_mean INTEGER, fixed_variance INTEGER, checksum INTEGER.

The convenience script /app/run_pipeline.sh builds and runs the pipeline on /app/data/input.bin writing to /app/db/results.db.

Do not modify /app/bin/accumulator_ref. Do not alter the database schema. The verifier will generate fresh batches and compare your pipeline's output against the reference binary's output on those same batches.
