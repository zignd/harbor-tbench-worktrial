# Snippet Evaluation Service

This service evaluates untrusted JavaScript snippets submitted by external API
users. It runs on port 4000 and enforces per-user CPU-time quotas using a
policy engine backed by a SQLite database.

## API Endpoints

### POST /eval

Submit a JavaScript snippet for evaluation.

Request body (JSON):
  - `user_id` (string, required): identifier for the submitting user
  - `code` (string, required): JavaScript source to evaluate

Response (200 OK, accepted):
  - `accepted`: true
  - `cpu_ms`: CPU time consumed (milliseconds)
  - `output`: captured console.log output

Response (429 Too Many Requests, budget exhausted):
  - `accepted`: false
  - `message`: human-readable reason
  - `window_total_ms`: current window total before this request

### GET /stats/:user_id

Return aggregate CPU-time statistics for a user.

Response (200 OK):
  - `user_id`: the queried user
  - `total_cpu_ms`: sum of all accepted cpu_ms across all time
  - `request_count`: number of accepted requests

### GET /health

Returns `{"status": "ok"}` when the service is running.

## Policy Invariants

The policy engine enforces two invariants that must hold under any request
sequence:

1. No single user may accumulate more than 500 CPU-milliseconds of evaluation
   time within any rolling 60-second window. Any request that would push the
   user over this budget must be rejected with HTTP 429 before evaluation begins.

2. The per-user CPU-time ledger must be consistent: the sum of CPU times
   recorded for accepted requests in any window must never exceed 500 ms, and
   the running total exposed at GET /stats/:user_id must equal the sum of the
   individual accepted-request records stored in /app/data/records.db.

## Database

Records are persisted to `/app/data/records.db` (SQLite).

Schema:
```sql
CREATE TABLE eval_records (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id  TEXT    NOT NULL,
  ts       INTEGER NOT NULL,
  cpu_ms   REAL    NOT NULL,
  accepted INTEGER NOT NULL DEFAULT 1
);
```

The `ts` column is a Unix epoch timestamp in milliseconds.
Only rows with `accepted = 1` count toward a user's quota.

## File Layout

```
/app/
  service/
    server.js   - HTTP server entry point
    routes.js   - Express route definitions
  policy/
    policy.js   - Rate-limit and budget enforcement logic
    db.js       - SQLite persistence layer
  data/
    records.db  - SQLite database (created at startup)
  start.sh      - Container entrypoint
  seed.js       - DB seeder (runs at startup)
  README.md     - This file
```
