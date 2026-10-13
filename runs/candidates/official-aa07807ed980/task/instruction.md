You have inherited a Python ETL pipeline at /app. The pipeline reads a CSV file, splits it into fixed-size chunks, processes each chunk through pipeline/transform.py (which applies type coercion, schema validation, and deduplication), and concatenates the results into a final output CSV.

Run it with:

    python run_pipeline.py --input data/sample.csv --output out/result.csv

The pipeline currently produces incorrect output: the output row count does not match the input, and duplicate record_id values appear in the result.

Fix the pipeline so that:

1. The output CSV at /app/out/result.csv contains exactly one row per unique record_id from the input. No duplicate record_id values may appear in the output, and no valid input row may be omitted.

2. The output row count equals the number of input rows minus any rows that fail schema validation. Rows that fail schema validation must be written to /app/out/rejected.csv instead of the output CSV.

3. The pipeline correctly handles chunk files where each file on disk begins with a header row. The output must contain no duplicate header rows and the row count must be accurate regardless of how many chunks are produced.

4. The pipeline must produce correct output for any valid CSV input of up to 500,000 rows, including inputs whose total row count is not evenly divisible by the configured chunk size.

5. All fixes must be committed to the git repository at /app. Running git log --oneline in /app must show at least one new commit that you authored, and the working tree must be clean.

The primary key column is record_id. The schema requires columns: record_id, name, amount, date, status. A valid row has a record_id starting with "REC", a non-empty name, a non-negative numeric amount, a date in YYYY-MM-DD format, and a status that is one of: active, inactive, pending, closed.
