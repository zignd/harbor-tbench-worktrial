The binary /app/bin/qexec runs SQL queries against a SQLite database and writes tab-separated results to stdout. Invoke it as:

    /app/bin/qexec <database.db> <query.sql>

The query file /app/queries/report.sql currently produces incorrect output when run against /app/data/events.db. Fix /app/queries/report.sql so that the output satisfies all of the following for every partition_key value in the database:

1. The running_total column contains the exact cumulative sum of amount, accumulated in ascending ts order within each partition.
2. The rank column uses standard SQL RANK() semantics: rank 1 goes to the row with the highest amount in the partition. Where two rows have equal amount, the row with the lower ts value receives the lower rank number. Two rows with identical amount and identical ts share the same rank value, and the next distinct rank value equals the count of rows ranked above it plus one.
3. Partitions whose partition_key has a numeric value less than 10 (i.e., keys '01' through '09') must produce correct running totals and ranks, not be silently dropped or produce reset accumulators.
4. Partitions containing rows with negative amount values must have running_total values that reflect those negative contributions; the running_total may decrease between consecutive rows.
5. A partition consisting of exactly one row must appear in the output with running_total equal to that row's amount and rank equal to 1.
6. Output rows are ordered by partition_key ascending, then by ts ascending within each partition.
7. Every partition_key present in the database appears in the output exactly once per event row; no partition is dropped or duplicated.
8. When a partition contains rows all having the same amount, each row receives a distinct rank assigned in ascending ts order starting from 1 with no gaps.
