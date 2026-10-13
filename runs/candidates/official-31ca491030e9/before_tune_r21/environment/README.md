# SQL Aggregation Engine

This environment provides a compiled SQL query executor for debugging window function and aggregation behavior.

## Files

- `/app/bin/qexec`         -- compiled query executor binary
- `/app/data/events.db`    -- SQLite database with partitioned event records
- `/app/queries/report.sql` -- SQL query file (editable)

## Usage

```
/app/bin/qexec <database.db> <query.sql>
```

The binary opens the SQLite database at the first argument, executes every semicolon-delimited statement in the SQL file at the second argument, and prints results as tab-separated rows to stdout.

### Example

```
/app/bin/qexec /app/data/events.db /app/queries/report.sql
```

Output columns: `partition_key`, `ts`, `amount`, `running_total`, `rank`

## Database Schema

```sql
CREATE TABLE events (
    id INTEGER PRIMARY KEY,
    partition_key TEXT NOT NULL,
    ts INTEGER NOT NULL,
    amount REAL NOT NULL
);
```
