You are a security engineer auditing the snippet-evaluation service running at http://localhost:4000. The service accepts POST /eval requests with a JSON body containing `user_id` and `code` fields. A policy engine at /app/policy enforces two invariants that must hold under any request sequence:

1. No single user may accumulate more than 500 CPU-milliseconds of evaluation time within any rolling 60-second window. Any request that would push the user over the budget must be rejected with HTTP 429 before evaluation begins.

2. The per-user CPU-time ledger must be consistent: the sum of CPU times recorded for accepted requests must never exceed 500 ms in any 60-second window, and the running total exposed at GET /stats/:user_id must equal the sum of the individual accepted-request records stored in /app/data/records.db for that user. This consistency must hold even after the service is restarted.

The service must also process at least 80 accepted requests per second under a 10-concurrent-user load (measured only on requests that stay within budget).

The README at /app/README.md describes the API and invariants in full. The service source is in /app/service/ and /app/policy/. The database is at /app/data/records.db.

Fix the service so all three conditions hold: the 500 ms rolling budget is never exceeded for any user under concurrent load, the stats endpoint always reflects the database contents for that user, and the throughput target is met.
