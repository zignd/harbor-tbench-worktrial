The binary /app/bin/qexec runs SQL queries against a SQLite database and writes tab-separated results to stdout. Invoke it as:

    /app/bin/qexec <database.db> <query.sql>

The query file /app/queries/report.sql currently produces incorrect output when run against /app/data/events.db. Fix /app/queries/report.sql so that the output satisfies all of the following for every partition_key value in the database:

1. The running_total column contains the exact cumulative sum of amount, accumulated in ascending ts order within each partition.
2. The rank column assigns integer rank 1 to the row with the highest amount in the partition. Where two rows have equal amount, the row with the lower ts value receives the lower rank number. There must be no gaps in the rank sequence within a partition.
3. Output rows are ordered by partition_key ascending, then by ts ascending within each partition.
4. Every partition_key present in the database appears in the output exactly once per event row; no partition is dropped or duplicated.
