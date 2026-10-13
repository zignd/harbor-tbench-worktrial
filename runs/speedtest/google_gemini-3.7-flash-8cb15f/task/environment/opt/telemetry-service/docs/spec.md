# Telemetry Query Service Specification

## Overview
`telemetry-queryd` is a local HTTP daemon that matches frontend ingress access logs with backend worker execution logs, reconstructs trace sessions, and provides queryable aggregation metrics.

## Log Schemas

### Frontend Logs (`/var/log/telemetry/frontend/*.tsv`)
Text TSV files containing a header line followed by log entries:
```
timestamp_msreq_idclient_ipendpointstatusfrontend_latency_ms
```
- `timestamp_ms`: Request arrival epoch timestamp in milliseconds.
- `req_id`: Unique request identifier string.
- `client_ip`: Client IP string.
- `endpoint`: Request path (e.g. `/api/v1/checkout`).
- `status`: HTTP response status code (e.g. 200, 400, 502, 504).
- `frontend_latency_ms`: Total frontend request duration in milliseconds.
Frontend execution window is `[timestamp_ms, timestamp_ms + frontend_latency_ms]`.

### Backend Binary Logs (`/var/log/telemetry/backend/*.bpack`)
Binary files packed in little-endian format (see `legacy/bpack.h`):
- File Header (16 bytes):
  - `magic`: 4 bytes (`BPK1`)
  - `chunk_count`: uint32 (little endian)
  - `base_timestamp_ms`: uint64 (little endian)
- For each chunk:
  - `worker_id`: uint32 (little endian)
  - `record_count`: uint32 (little endian)
  - For each record in chunk:
    - `delta_start_ms`: int32 (little endian, signed offset from base_timestamp_ms; start time = `base_timestamp_ms + delta_start_ms`)
    - `duration_ms`: uint32 (little endian; end time = `start_time + duration_ms`)
    - `worker_exit_code`: uint16 (little endian, 0 = OK, >0 = error/failure)
    - `endpoint_len`: uint16 (little endian)
    - `endpoint`: UTF-8 string bytes of length `endpoint_len`
Backend execution window is `[start_time, start_time + duration_ms]`.

## Session Attribution Algorithm
Frontend request `F` and backend task `B` match if and only if:
1. Same endpoint: `F.endpoint == B.endpoint`
2. Containment: `F.timestamp_ms <= B.start_time` and `B.end_time <= (F.timestamp_ms + F.frontend_latency_ms)`
3. Status consistency:
   - If `B.worker_exit_code != 0`, `F.status >= 500`
   - If `B.worker_exit_code == 0`, `F.status < 500`

### Disambiguation and Assignment
Slack is defined as:
`slack(F, B) = F.frontend_latency_ms - B.duration_ms`

For each endpoint, candidate pairs `(F, B)` meeting all constraints are ordered by:
1. `slack` ascending
2. `F.timestamp_ms` ascending
3. `B.start_time` ascending
4. `F.req_id` ascending
5. `B.worker_id` ascending

Pairs are matched greedily in this order such that each frontend request and backend task is assigned at most once.

## HTTP API (`0.0.0.0:8085`)

### `GET /healthz`
Returns HTTP 200 with JSON:
```json
{"status": "healthy"}
```

### `GET /v1/attribution/stats`
Returns HTTP 200 with summary of current attribution across all loaded log files:
```json
{
  "total_frontend_records": 1250,
  "total_backend_records": 1100,
  "matched_records": 1050,
  "unmatched_frontend": 200,
  "unmatched_backend": 50,
  "mean_slack_ms": 14.25
}
```
- `mean_slack_ms`: Mean slack of all matched records rounded to 2 decimal places (0.0 if no matches).

### `POST /v1/query`
Request body JSON:
```json
{
  "endpoint": "/api/v1/checkout",
  "time_range": [1700000000000, 1700003600000]
}
```
Filter rule: Frontend requests for the given `endpoint` with `start_ms <= F.timestamp_ms < end_ms`.

Response HTTP 200 JSON:
```json
{
  "endpoint": "/api/v1/checkout",
  "time_range": [1700000000000, 1700003600000],
  "matched_count": 320,
  "unmatched_frontend_count": 15,
  "p50_backend_latency": 45.0,
  "p90_backend_latency": 112.0,
  "p99_backend_latency": 240.0,
  "error_rate": 0.0312
}
```
- Latency percentiles (`p50_backend_latency`, `p90_backend_latency`, `p99_backend_latency`): Computed on the backend `duration_ms` of matched pairs in the time range using the nearest-rank method:
  Given sorted backend latencies of matched records d_1 <= d_2 <= ... <= d_N (1-indexed),
  k = ceil(p * N / 100). The percentile is d_k.
  Rounded to 2 decimal places (or 0.0 if matched_count is 0).
- `error_rate`: Proportion of all frontend requests for this endpoint in the window (`matched_count + unmatched_frontend_count`) having `status >= 500`. Rounded to 4 decimal places (0.0 if total frontend count is 0).

### Dynamic Updates
The service must reflect new log files added to `/var/log/telemetry/frontend/` or `/var/log/telemetry/backend/` when responding to subsequent API queries.
