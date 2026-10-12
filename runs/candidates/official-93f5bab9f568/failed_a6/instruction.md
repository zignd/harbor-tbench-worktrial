The ETL pipeline at /app produces incorrect aggregate totals in the SQLite database. Fix it so that for every (region, product_category, date) triple present in the source data, the daily_summary table contains the correct sum of revenue and the correct count of distinct user_id values from the source records.

The pipeline is invoked as:

    python /app/run_pipeline.py <input_dir> <db_path>

where input_dir is a directory of CSV files (each with columns: event_id, user_id, region, product_category, date, revenue) and db_path is the SQLite database to write.

The daily_summary table must satisfy:
- One row per (region, product_category, date) triple — no duplicates.
- revenue_total equals the sum of all revenue values for that (region, product_category, date) triple, within 0.01 absolute tolerance.
- distinct_users equals the exact count of distinct user_id values across all source records for that (region, product_category, date) triple.
- Running the pipeline more than once on the same input must not change row counts or revenue_total values (idempotent).

The pipeline must complete without error. Sample data is available at /app/sample_data/.
