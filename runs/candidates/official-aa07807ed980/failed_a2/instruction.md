The pipeline at `/app` reads a CSV, splits it into fixed-size chunks written to disk, processes each chunk through `pipeline/transform.py`, and concatenates the results into an output CSV. A recent batch run produced wrong row counts and duplicate records in the output without raising any exception.

Fix the pipeline so that all of the following hold for any valid CSV input of up to 500,000 rows with columns `record_id,name,amount,date,status`:

1. The output CSV at `/app/out/result.csv` contains exactly one row per unique `record_id` from the input (no duplicate `record_id` values, no omissions of valid rows).
2. The row count of the output equals the number of input rows that pass schema validation. Rows that fail validation must be written to `/app/out/rejected.csv` instead.
3. The pipeline produces correct output when the input row count is not evenly divisible by the chunk size; no input rows may be silently dropped.
4. The pipeline correctly handles chunk files that each begin with a header row; header rows must not appear as data rows in the output or be counted as valid records.
5. All changes must be committed to the repository at `/app`; `git log --oneline` must show at least one commit you authored, and the working tree must be clean.

The default chunk size is 2000. The pipeline is invoked as:

```
python /app/run_pipeline.py --input <input.csv> --output /app/out/result.csv
```
