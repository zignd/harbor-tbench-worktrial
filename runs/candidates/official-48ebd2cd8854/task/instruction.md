Hey, the regional sales aggregation numbers coming out of `/app/service/` don't match what I calculate by hand anymore. The service compiles and runs without errors, and individual records look fine — it's only the region-level summaries that are wrong.

The final numbers end up in the `region_summaries` table in `/app/data/sales.db`. After the service runs, each row in `region_summaries` must satisfy:

    weighted_total = sum(sale_amount * region_weight)
                     for every record in sales_records with that region_id

where `region_weight` is the value declared for that region in `/app/config/weights.ini`. The weights in that file are the authoritative values.

The weight stored in the `weight_cache` table for each region must also equal the value from `/app/config/weights.ini`, within floating-point precision. All regions present in `sales_records` must appear in `region_summaries` with a correct `weighted_total`.

Fix whatever is broken in `/app/service/`, rebuild from source (the binary is at `/app/service/aggregator`), and rerun the service so the database reflects the corrected results. The fix must be in the source code; do not correct the database directly.
