The regional sales aggregation service at /app/service/ is producing wrong summary numbers. The service compiles and runs without errors, and individual sale records look fine, but the per-region weighted totals in the region_summaries table of /app/data/sales.db do not match hand calculations.

Find and fix whatever is broken in the source code so that every row in region_summaries has a weighted_total equal to the exact sum of (sale_amount * region_weight) for all records with that region_id, where region_weight is the value declared in /app/config/weights.ini for that region. The weights in /app/config/weights.ini are authoritative.

After fixing the source, rebuild the service from /app/service/ and rerun it against /app/data/sales.db so the database reflects the corrected results. The binary must be produced by compiling the fixed source; do not patch the database directly.

The weight stored in the weight_cache table must also match the corresponding value in /app/config/weights.ini (within floating-point precision) for every region. All regions present in sales_records must appear in region_summaries.
