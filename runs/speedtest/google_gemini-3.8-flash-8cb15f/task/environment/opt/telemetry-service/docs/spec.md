# Telemetry Session Attribution & Metric Query Service Specification

## Overview
The Telemetry Query Daemon (`telemetry-queryd`) provides trace attribution and windowed performance metrics by correlating edge access logs with backend worker execution logs.

Due to a legacy proxy misconfiguration, edge requests in `/var/log/telemetry/frontend/` and backend task logs in `/var/log/telemetry/backend/` lack shared trace IDs. The service dynamically ingests both log streams, solves a temporal interval constraint satisfaction problem to attribute backend tasks to frontend requests, and exposes an HTTP API on `0.0.0.0:8085`.

---

## Log Formats

### 1. Frontend Access Logs (`/var/log/telemetry/frontend/*.tsv`)
Tab-separated text files. Each non-empty line represents an incoming edge request:
```
<timestamp_ms>	<req_id>	<client_ip>	<endpoint>	<status>	<frontend_latency_ms>
```
- `timestamp_ms` (integer): Millisecond epoch timestamp when frontend received request (`req_start`).
- `req_id` (string): Unique identifier for the frontend request.
- `client_ip` (string): Client IPv4 address.
- `endpoint` (string): Request URI path (e.g. `/api/v1/checkout`).
- `status` (integer): HTTP response status code (e.g. 200, 502, 504).
- `frontend_latency_ms` (integer): Duration in milliseconds of the edge request.
- Request window interval: `[req_start, req_end]` where `req_end = req_start + frontend_latency_ms`.

### 2. Backend Binary Logs (`/var/log/telemetry/backend/*.bpack`)
Compact binary log files. A single `.bpack` file consists of one or more sequential chunks.

Each chunk begins with a 16-byte fixed header (little-endian byte order):
```
Offset  Size  Type      Field
0       4     char[4]   magic ("BPK1")
4       2     uint16    version (1)
6       2     uint16    record_count
8       8     uint64    base_timestamp_ms (epoch milliseconds)
```

Immediately following the chunk header are `record_count` variable-length records. Each record consists of:
```
Offset  Size  Type      Field
0       4     int32     delta_start_ms (signed millisecond offset from chunk base_timestamp_ms)
4       4     uint32    duration_ms (execution duration in milliseconds)
8       4     uint32    worker_id (backend worker instance identifier)
12      2     int16     exit_code (0 for success, non-zero for failure)
14      2     uint16    endpoint_len (byte length of following endpoint string)
16      N     char[]    endpoint (endpoint string of endpoint_len UTF-8 bytes)
```
- Backend task start time: `t_start = chunk.base_timestamp_ms + delta_start_ms`.
- Backend task end time: `t_end = t_start + duration_ms`.

---

## Attribution & Constraint Satisfaction Engine

To attribute a backend execution task `B` to a frontend edge request `F`, the pair `(F, B)` must satisfy the following constraints:

1. **Endpoint Match**: `F.endpoint == B.endpoint`.
2. **Temporal Containment**: Backend execution interval `[t_start, t_end]` must be strictly contained within frontend request window:
   `F.req_start <= B.t_start` AND `B.t_end <= F.req_end`.
3. **Status Code Consistency**:
   - If `B.exit_code != 0`, then `F.status` must be `502` or `504`.
   - If `B.exit_code == 0`, then `F.status` must be `200`.
4. **Cardinality & Worker Concurrency Limit**:
   - Each frontend request matches at most ONE backend task.
   - Each backend task matches at most ONE frontend request.
   - A backend worker cannot execute overlapping tasks simultaneously.
5. **Greedy Minimum-Slack Attribution**:
   Slack time represents unspent edge overhead:
   `slack = (B.t_start - F.req_start) + (F.req_end - B.t_end)`
   
   To resolve multi-candidate matches:
   - Identify all candidate pairs `(F, B)` satisfying constraints 1, 2, and 3.
   - For each candidate pair, compute `slack`.
   - Sort candidate pairs in ascending order using the tuple key:
     `(slack, F.timestamp_ms, B.t_start, F.req_id, B.worker_id)`
   - Iterate through sorted pairs in order: if neither `F` nor `B` has already been matched, assign `B` to `F`.

---

## HTTP REST API Specification

All endpoints listen on `0.0.0.0:8085`.

### 1. `GET /healthz`
Returns service health status.
**Response (200 OK)**:
```json
{
  "status": "healthy"
}
```

### 2. `GET /v1/attribution/stats`
Returns global attribution metrics across all ingested logs.
**Response (200 OK)**:
```json
{
  "total_frontend_requests": 1200,
  "total_backend_tasks": 1150,
  "matched_pairs": 1080,
  "unmatched_frontend": 120,
  "unmatched_backend": 70,
  "avg_slack_ms": 24.5
}
```
- `avg_slack_ms`: float representing the arithmetic mean of `slack` for all matched pairs (or `0.0` if `matched_pairs == 0`), rounded to 2 decimal places.

### 3. `POST /v1/query`
Computes windowed quantile and SLA metrics for a specific endpoint and time range.

**Request Body (JSON)**:
```json
{
  "endpoint": "/api/v1/checkout",
  "time_range": [1710000000000, 1710000050000]
}
```
- `time_range`: `[start_ms, end_ms]`. A frontend request is considered within the query window if `start_ms <= F.timestamp_ms <= end_ms` (inclusive of both boundaries).

**Response (200 OK)**:
```json
{
  "matched_count": 85,
  "unmatched_frontend_count": 5,
  "p50_backend_latency": 42.0,
  "p90_backend_latency": 110.0,
  "p99_backend_latency": 185.0,
  "error_rate": 0.0588
}
```
- `matched_count`: Total number of frontend requests for `endpoint` within `time_range` that have an attributed backend task.
- `unmatched_frontend_count`: Total number of frontend requests for `endpoint` within `time_range` that have NO attributed backend task.
- `p50_backend_latency`, `p90_backend_latency`, `p99_backend_latency`: Percentiles computed from the `duration_ms` of attributed backend tasks for matching requests within `time_range`.
  - **Percentile Calculation Method**: Nearest-rank method.
    Given sorted ascending values v_1, v_2, ..., v_N (1-indexed):
    For percentile P in {50, 90, 99}, calculate rank index k = ceil((P / 100) * N). In 0-indexed terms: ceil(P * N / 100) - 1.
    The percentile value is v_k, cast to float rounded to 2 decimal places.
    If `matched_count == 0`, return `0.0` for all percentiles.
- `error_rate`: `(number of matched backend tasks with exit_code != 0) / matched_count` rounded to 4 decimal places (or `0.0` if `matched_count == 0`).

---

## Dynamic Ingestion
When new log files are added or existing log files are appended in `/var/log/telemetry/frontend/` or `/var/log/telemetry/backend/`, subsequent query requests must reflect the new data.
