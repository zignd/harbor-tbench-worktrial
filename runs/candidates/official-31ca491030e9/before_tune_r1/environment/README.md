# SQL Query Executor

## Usage

    ./bin/qexec <database.db> <query.sql>

Example:

    ./bin/qexec data/events.db queries/report.sql

The executor opens the SQLite database at the first argument, reads and executes
every semicolon-delimited SQL statement from the file at the second argument, and
prints results as tab-separated rows to stdout.

## Files

- `/app/bin/qexec`            -- compiled query executor binary
- `/app/data/events.db`       -- SQLite database with partitioned event records
- `/app/queries/report.sql`   -- SQL query file (edit this to fix the report)
- `/app/expected_sample.txt`  -- reference output for a subset of partitions

## Schema

    CREATE TABLE events (
        id            INTEGER PRIMARY KEY,
        partition_key TEXT NOT NULL,
        ts            INTEGER NOT NULL,
        amount        REAL NOT NULL
    );
