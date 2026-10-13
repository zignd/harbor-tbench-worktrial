# Metrics Pipeline

This repository contains the data pipeline that ingests logs from our microservices
into a queryable time-series store, and exposes them via an HTTP query service.

## Architecture

```
/data/logs/*.jsonl
       |
       v
   ingestor.py
       |
       v
/data/processed/metrics.sqlite
       |
       v
   query_service.py   <-- HTTP API (port 7432)
       |
       v
  dashboard clients
```

### Components

**ingestor.py** — Reads JSONL log files from `/data/logs/`, normalizes records,
and writes them into the SQLite metrics database. Run manually or invoked by
the log rotator. Tracks already-processed files to avoid double-ingestion.

**log_rotator.py** — Rotates old log files and triggers the ingestor. Designed
to run as a periodic daemon (cron or systemd timer).

**logbin_engine.so** — Compiled C shared library for fast windowed aggregations.
Provides the computational core. The original source is not available; see
`engine_wrapper.py` for the Python interface. Engine quirks are fully documented
in the `engine_wrapper.py` docstrings.

**engine_wrapper.py** — Python ctypes wrapper around `logbin_engine.so`. Exposes
`load_series`, `compute_window`, and `release_handle`. See module docstring for
detailed API documentation.

**query_service.py** — HTTP service (port 7432) that answers metric queries from
dashboards. Implements the protocol described in `QUERY_PROTOCOL.md`. Not yet
implemented — see `KNOWN_ISSUES.txt`.

**schema.sql** — SQLite schema for the metrics database.

**generate_logs.py** — Deterministic log generator used during environment setup.
The generated data is already in `/data/logs/`.

### Data

Log data covers 8 microservices:
- `auth` — Authentication service
- `api-gateway` — API gateway / reverse proxy
- `worker` — Background job workers
- `cache` — Caching layer
- `db-proxy` — Database connection proxy
- `mailer` — Email delivery service
- `scheduler` — Job scheduling service
- `billing` — Billing and payments

Metrics vary by service. See `/data/logs/*.jsonl` for examples.

### Exploring the Engine

A CLI probe tool is available at `/usr/local/bin/logbin_probe` for manual
exploration of the engine's behavior:

```
logbin_probe --service auth --metric login_latency_ms \
             --start 1706400000 --end 1706403600 \
             --window 300 --agg p95
```

This calls the engine directly with data from the SQLite database and prints
results in a human-readable format. Useful for debugging query_service.py
behavior and verifying engine semantics.

### Known Issues

See `KNOWN_ISSUES.txt` for the current list of open issues.

### Database Schema

See `schema.sql`. Key table: `raw_metrics(service, metric, ts, value)`.
Timestamps are stored as float seconds since epoch.
