# Query Service Protocol Specification

Version 1.2 — Internal Draft

## Overview

The query service exposes a single HTTP endpoint for structured metric queries.
Downstream dashboards send JSON-encoded query parameters and receive time-bucketed
aggregation results. The service reads from the metrics database maintained by
the ingestor pipeline.

## Endpoint

    POST /query
    Content-Type: application/json

## Request Schema

All fields are required.

| Field        | Type   | Description                                              |
|--------------|--------|----------------------------------------------------------|
| `service`    | string | Service name (e.g. `auth`, `billing`, `api-gateway`)     |
| `metric`     | string | Metric name (e.g. `login_latency_ms`, `charge_latency_ms`)|
| `start_ts`   | number | Query window start, Unix seconds (float)                 |
| `end_ts`     | number | Query window end, Unix seconds (float); must be > start  |
| `window_secs`| number | Bucket size in seconds (positive integer or float)       |
| `agg`        | string | Aggregation type: `sum`, `mean`, `p50`, `p95`, `p99`     |

Example request:

```json
{
  "service": "auth",
  "metric": "login_latency_ms",
  "start_ts": 1706400000,
  "end_ts": 1706486400,
  "window_secs": 3600,
  "agg": "p95"
}
```

## Response Schema

HTTP 200 with body:

```json
{
  "buckets": [
    {"ts": 1706400000, "value": 142.7},
    {"ts": 1706403600, "value": 138.2},
    ...
  ]
}
```

Each element in `buckets` represents one aggregation window:

- `ts`: the start timestamp of the window interval (Unix seconds, float)
- `value`: the aggregated metric value for that window

Buckets are returned in ascending timestamp order.

Bucket timestamps are aligned to multiples of `window_secs` from the Unix epoch.
Only buckets that fall within [start_ts, end_ts) are included — no partial buckets
at either end of the query range.

If a bucket has no data, it is omitted from the response (not returned as null or zero).

## Aggregation Types

| Value | Meaning                        |
|-------|--------------------------------|
| `sum` | Sum of all values in the bucket|
| `mean`| Arithmetic mean                |
| `p50` | 50th percentile (median)       |
| `p95` | 95th percentile                |
| `p99` | 99th percentile                |

Percentile calculations use linear interpolation between adjacent ranked values.

## Error Responses

### HTTP 400 — Bad Request

Returned when the request is malformed:
- Missing required field
- `agg` is not one of the supported types
- `end_ts` <= `start_ts`
- `window_secs` <= 0

Body:
```json
{"error": "<human-readable description>"}
```

### HTTP 404 — Not Found

Returned when the service name is not known to the pipeline:

```json
{"error": "service not found"}
```

### HTTP 500 — Internal Server Error

Returned on unexpected engine or database errors. The `error` field contains
a brief description; details are logged server-side.

## Concurrency

The service must handle concurrent requests correctly. Each request operates on
an independent snapshot of the data; responses must not contain mixed or stale
results from interleaved requests.

## Live Data

The service reflects log entries written to /data/logs/ after startup. New entries
appear in query results once they have been ingested into the metrics database.
The ingestor runs periodically; the service does not need to trigger ingestion,
but it must read the current state of the database on each request rather than
caching a stale snapshot.

## Notes

- Timestamp precision: the pipeline stores timestamps as float seconds. Sub-second
  precision is preserved in the database but bucket alignment is computed at the
  resolution of `window_secs`.
- The `billing` and `scheduler` services are lower-traffic than others; some
  time windows may have sparse data.
- Service names in the protocol match the lowercase names in the service registry.
