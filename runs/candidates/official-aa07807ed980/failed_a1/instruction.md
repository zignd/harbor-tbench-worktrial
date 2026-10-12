The pipeline at `/app` reads a CSV, splits it into fixed-size chunks written to disk, processes each chunk through `pipeline/transform.py`, and concatenates the results into an output CSV. A recent batch run produced wrong row counts and duplicate records in the output with no exception raised.

Run the pipeline and checker to see the symptoms:

```
$ python run_pipeline.py --input data/sample.csv --output out/result.csv
Processed 12 chunks, 24000 rows written.
$ wc -l out/result.csv
24001 out/result.csv
$ python verify_output.py out/result.csv
Duplicate primary keys detected: 47
Row count mismatch: expected 20000, got 24000
```

Fix the pipeline so that all of the following hold for any valid CSV input of up to 500,000 rows with columns `record_id,name,amount,date,status`:

1. The output CSV at `/app/out/result.csv` contains exactly one row per unique `record_id` from the input (no duplicate `record_id` values, no omissions of valid rows).
2. The row count of the output equals the number of input rows that pass schema validation. Rows that fail validation must be written to `/app/out/rejected.csv` instead.
3. The pipeline produces correct output when the input row count is not evenly divisible by the chunk size; no rows may be silently dropped.
4. The pipeline handles the case where each chunk file on disk begins with a header row without treating those header rows as data or miscounting them.
5. All changes must be committed to the repository at `/app`; `git log --oneline` must show at least one commit you authored, and the working tree must be clean.

The default chunk size is 2000. The pipeline is invoked as:

```
python /app/run_pipeline.py --input <input.csv> --output /app/out/result.csv
```
