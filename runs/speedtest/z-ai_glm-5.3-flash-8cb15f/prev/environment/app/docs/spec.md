# Telemetry query service specification

## Runtime

The service listens on `0.0.0.0:8085`. `TELEMETRY_PORT` overrides the port only in a development process. Every successful JSON response uses HTTP 200 and `Content-Type: application/json`. Malformed input, an unknown metric, an empty endpoint, or an invalid time range produces HTTP 400 with `{"error": "..."}`. Other server failures use HTTP 500 with a JSON error object.

## Frontend TSV

Each `frontend/*.tsv` file has no header. Every nonblank line has exactly these tab-separated fields:

1. `timestamp_ms`, request arrival time
2. `req_id`, unique string
3. `client_ip`
4. `endpoint`, case-sensitive byte string
5. `status`, integer HTTP status
6. `frontend_latency_ms`, positive integer

For a frontend request `f`, its request window is `[f.timestamp_ms, f.timestamp_ms + f.frontend_latency_ms)`.

## Backend `.bpack`

A backend pack begins with a packed 16-byte header:

```c
struct bpack_file_header {
    char     magic[4];                     // "BPCK"
    uint16_t version;                      // 1
    uint16_t flags;                        // 0 in this migration
    uint32_t record_count;
    uint32_t base_timestamp_offset_ms;    // milliseconds after BPACK_EPOCH_MS
};
```

`BPACK_EPOCH_MS` is `1700000000000`. The absolute file base is therefore `BPACK_EPOCH_MS + base_timestamp_offset_ms`.

After the header, exactly `record_count` records are stored sequentially. Each starts with this packed 16-byte header:

```c
struct bpack_record_header {
    uint16_t endpoint_length;
    uint16_t flags;
    uint16_t worker_id;
    uint16_t exit_code;
    int64_t  start_delta_ms;
};
```

The endpoint is the next `endpoint_length` UTF-8 bytes with no NUL terminator. Following the endpoint is a packed signed 64-bit `execution_duration_ms`. A valid execution duration is greater than zero.

Decode execution starts as follows:

- the first record's `start_delta_ms` is relative to the file base;
- every later record's `start_delta_ms` is relative to the preceding record's decoded start in the same file;
- deltas are signed and files are not required to be sorted;
- file bases do not carry across files.

An endpoint length of zero, an unsupported magic/version, a nonpositive duration, truncated data, or trailing bytes make the pack invalid.

## Attribution

A backend record `b` is a candidate for frontend `f` only when all of the following hold:

1. `b.endpoint == f.endpoint`;
2. `b.start_ms > f.timestamp_ms` and `b.end_ms < f.timestamp_ms + f.frontend_latency_ms` (strict containment);
3. if `b.exit_code != 0`, `f.status` is either 502 or 504.

Slack is `(b.start_ms - f.timestamp_ms) + (f.timestamp_ms + f.frontend_latency_ms - b.end_ms)`. Every frontend and backend record can be used at most once.

The minimum-slack allocation is one deterministic pass over all candidates:

1. Sort candidates by slack, then `req_id`, then `worker_id`, then backend start, backend end, source filename, and record index, all ascending.
2. Accept the first candidate only when its frontend and backend are both unused.
3. Also reject it if that backend worker already has an accepted interval `p` with `p.start_ms < b.end_ms` and `b.start_ms < p.end_ms`. Equal interval boundaries do not conflict.

A candidate is otherwise accepted atomically. Records not accepted are orphans. This pass deliberately defines the service's minimum-slack constraint optimization; implementations must not substitute timestamp proximity, endpoint counts, or another objective.

Attribution is recomputed when the set of names, sizes, or modification timestamps in either log directory changes. Previously loaded files remain part of the result.

## GET /healthz

Returns HTTP 200 with exactly the JSON object `{"status":"healthy"}`.

## POST /v1/query

The body is a JSON object:

```json
{
  "endpoint": "/api/ingest",
  "time_range": [1700000000000, 1700000060000],
  "metrics": ["matched_count", "p90_backend_latency"]
}
```

`endpoint` must be a nonempty string. `time_range` must be two integers with `start_ms < end_ms`. `metrics` is optional; when omitted, every metric below is returned. An unknown metric is an error.

A session is included in query results when its frontend request start satisfies `start_ms <= frontend.timestamp_ms < end_ms`. Backend intervals are not independently filtered. The supported metrics are:

- `matched_count`: accepted sessions whose frontend starts in the window.
- `unmatched_frontend_count`: all frontend records with that endpoint and start in the window minus `matched_count`.
- `p50_backend_latency`, `p90_backend_latency`, `p99_backend_latency`: backend latency (`b.end_ms - b.start_ms`) over included accepted sessions, using nearest-rank percentiles.
- `error_rate`: backend records with nonzero `exit_code` divided by `matched_count`.

Nearest rank for `p` and `n` values is element `ceil(p * n / 100)` in ascending order (one-based). If there are no included matched sessions, all three percentiles are `null` and `error_rate` is `0.0`.

A successful response is:

```json
{
  "endpoint": "/api/ingest",
  "time_range": [1700000000000, 1700000060000],
  "metrics": {
    "matched_count": 12,
    "unmatched_frontend_count": 2,
    "p50_backend_latency": 145,
    "p90_backend_latency": 388,
    "p99_backend_latency": 491,
    "error_rate": 0.083333
  }
}
```

When a metric subset is requested, the `metrics` object contains only those metrics.

## GET /v1/attribution/stats

This summarizes all loaded records with no time filter:

```json
{
  "frontend_count": 1200,
  "backend_count": 1180,
  "matched_count": 1100,
  "unmatched_frontend_count": 100,
  "orphaned_backend_count": 80,
  "total_slack_ms": 128240,
  "slack_min_ms": 17,
  "slack_p50_ms": 112,
  "slack_p90_ms": 190,
  "slack_p99_ms": 217,
  "slack_max_ms": 229,
  "error_rate": 0.105455
}
```

Counts and slack totals are integers, slack percentile fields use nearest rank, and `error_rate` is the nonzero-exit fraction among matched backend tasks.
