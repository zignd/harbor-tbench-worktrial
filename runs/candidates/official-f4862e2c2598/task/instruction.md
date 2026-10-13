Hey, so Marcus left and the dashboard team is blocked — they need the query service running by EOD.

The pipeline ingests logs from microservices into `/data/processed/metrics.sqlite`. The engine wrapper at `/app/engine_wrapper.py` exposes a compiled shared library (`/app/logbin_engine.so`) that does fast windowed aggregations. The protocol the dashboards expect is described in `/app/QUERY_PROTOCOL.md`. There are some known issues logged in `/app/KNOWN_ISSUES.txt`.

Build the HTTP query service at `/app/query_service.py` so it listens on port 7432 and correctly implements the query protocol. The partial integration tests in `/app/tests/` are currently failing and need to pass.

The service must stay running after you start it — the dashboard team will be hitting it with fresh queries. It must reflect log entries written to `/data/logs/` after startup (the ingestor runs separately; the service just needs to read the current database state on each request).

The engine has some quirks that aren't fully captured in the documentation, so you'll probably need to run experiments against it with real data to understand how it actually behaves before you trust its output. The `logbin_probe` CLI tool at `/usr/local/bin/logbin_probe` can help with that.

Required end state:
- `/app/query_service.py` exists and runs as an HTTP service on port 7432
- `POST /query` accepts JSON `{service, metric, start_ts, end_ts, window_secs, agg}` and returns `{buckets: [{ts, value}]}`
- Supported aggregations: `sum`, `mean`, `p50`, `p95`, `p99`
- Results are numerically correct to within 0.5% for all aggregation types
- Returns HTTP 400 with `{error: <message>}` for malformed requests (missing fields, invalid agg, `end_ts <= start_ts`)
- Returns HTTP 404 with `{error: "service not found"}` for unknown service names
- Handles concurrent requests without returning stale or mixed results
- Reflects log entries written to `/data/logs/` after the service starts
