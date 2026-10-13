Your colleague messages: "Hey, we're retiring that old allocator binary next sprint. We need a drop-in SQL replacement that behaves exactly the same for any input. The binary is at /usr/local/bin/allocator, takes a CSV like /app/sample_data.csv, and writes assignments to stdout. I've set up a SQLite table via /app/setup.sql. Can you write a SQL script /app/solution/allocate.sql that produces exactly the same rows when run? You can test with /app/tests/verify.py. Thanks!"

The allocator reads a CSV with columns (query_id, load, timestamp) and assigns each query to one of three shards (0, 1, or 2). The binary is compiled with no source available; the README at /app/README.md has usage details. Your /app/solution/allocate.sql file must produce output identical to the binary for any valid input CSV. The setup script at /app/setup.sql creates the queries table and imports the sample data. When the SQL script is run against a SQLite database with that table, it must write the same (query_id, assigned_shard) pairs to stdout.

Important points:

- The solution must work for any input CSV, not just the sample. The verifier generates random test cases including empty inputs, single queries, duplicate loads, and large values.
- The output must be strictly deterministic and match the binary's assignments exactly.
- Do not modify the binary, the setup script, or anything outside /app/solution/.
- The SQL script must be self-contained and runnable with sqlite3 -csv -header database.db < /app/solution/allocate.sql.
