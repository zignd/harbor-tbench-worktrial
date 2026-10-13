We have an ingestion pipeline in `/app/ingestor` that processes large batches of sensor data. Our analyst says the final aggregate numbers for the 'North' and 'South' regions don't match the raw CSVs in `/app/data`. The system was recently refactored to use a custom lock-free buffer for speed.

```bash
$ cargo run --release -- --input /app/data --output /app/results.json
[INFO] Processed 1,048,576 records.
[INFO] Success.
$ python3 check_audit.py /app/results.json
AUDIT FAILED: Expected sum 52428800.0, got 52312064.0 (Delta: -116736.0)
```

Fix the pipeline so it processes every record in the input directory exactly once and produces numerically correct aggregates. The final solution must maintain a throughput of at least 500,000 records per second on this hardware.

The ingestion tool must process all CSV files in the provided input directory. The output JSON must contain the correct sum of the 'value' column for each 'region'. The pipeline must handle concurrent processing without data loss or race conditions. The processing speed must exceed 500,000 records/sec on the provided data.
