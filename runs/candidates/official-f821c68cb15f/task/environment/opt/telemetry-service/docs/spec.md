# Telemetry Query & Trace Session Attribution Specification

## 1. Overview
During edge telemetry proxy migration, frontend edge ingress logs and backend task logs were captured into separate streams without propagated request/trace IDs.
The `telemetry-queryd` daemon is an HTTP service running on `0.0.0.0:8085` that reconstructs session attribution and serves latency aggregations.

## 2. Telemetry Log Locations & Formats

### 2.1 Frontend Edge Logs
- Location: `/var/log/telemetry/frontend/*.log` (TSV format, UTF-8 text)
- Each line represents one frontend HTTP edge request with 6 tab-separated fields:
  1. `timestamp_ms` (uint64): Request arrival Unix epoch time in milliseconds (`req_start`).
  2. `req_id` (string): Unique frontend request identifier (e.g. `req-xxxx`).
  3. `client_ip` (string): Client IP address.
  4. `endpoint` (string): Normalized request path (e.g. `/api/v1/checkout`).
  5. `status` (int): HTTP status code returned to client (e.g. 200, 502).
  6. `frontend_latency_ms` (uint32): Total elapsed frontend request duration in milliseconds.
     The frontend request window is defined as `[req_start, req_end]`, where `req_end = req_start + frontend_latency_ms`.

### 2.2 Backend Execution Logs
- Location: `/var/log/telemetry/backend/*.bpack` (Binary packed format)
- Specified in `/opt/telemetry-service/legacy/bpack.h`:
  - Fixed 16-byte File Header:
    - `magic`: 4 bytes ASCII `"BPK1"`
    - `version`: uint16 (`1`)
    - `chunk_count`: uint16
    - `total_records`: uint32
    - `flags`: uint32 (reserved, 0)
  - Sequences of `chunk_count` chunks:
    - Fixed 16-byte Chunk Header:
      - `chunk_records`: uint32 (number of records in this chunk)
      - `chunk_bytes`: uint32 (total byte size of record payload)
      - `base_timestamp_ms`: uint64 (epoch start timestamp in milliseconds for chunk)
    - Record payload containing `chunk_records` records:
      - Fixed 18-byte Record Header:
        - `task_id`: uint32
        - `worker_id`: uint16
        - `exit_code`: int16 (0 = success, non-zero = failure)
        - `start_delta_ms`: uint32 (offset from chunk's `base_timestamp_ms`)
        - `duration_ms`: uint32 (execution duration in milliseconds)
        - `endpoint_len`: uint16 (length of endpoint string)
      - `endpoint`: UTF-8 encoded string of length `endpoint_len` (no null terminator).
  - Backend task timing:
    - `t_start = chunk.base_timestamp_ms + record.start_delta_ms`
    - `t_end = t_start + record.duration_ms`
    - Execution window is `[t_start, t_end]`.

## 3. Session Attribution Constraints & Matching Algorithm

A frontend request `F` and a backend task `B` form a valid candidate attribution pair if and only if all of the following conditions are satisfied:
1. **Endpoint Match**: `F.endpoint == B.endpoint`
2. **Temporal Containment**: The backend task must have executed entirely within the frontend request window:
   `F.req_start <= B.t_start` and `B.t_end <= F.req_end`
   (where `F.req_end = F.req_start + F.frontend_latency_ms` and `B.t_end = B.t_start + B.duration_ms`).
3. **Status Code Consistency**:
   - If backend execution failed (`B.exit_code != 0`), the frontend status must be either `502` or `504`.
   - If backend execution succeeded (`B.exit_code == 0`), the frontend status must NOT be `502` or `504`.
4. **Worker Concurrency Limit**: Tasks assigned to the same `worker_id` do not overlap concurrently. Each backend task corresponds to at most one frontend request, and each frontend request corresponds to at most one backend task.

### 3.1 Disambiguation & Slack Optimization
For any candidate pair `(F, B)`, the slack time in milliseconds is defined as:
`slack = (B.t_start - F.req_start) + (F.req_end - B.t_end) = F.frontend_latency_ms - B.duration_ms`

To resolve multi-candidate matches deterministically:
1. Identify all valid candidate pairs `(F, B)` meeting constraints 1-3.
2. Sort all candidate pairs in ascending order using the tie-breaking tuple:
   `(slack, F.req_start, F.req_id, B.task_id)`
3. Sequentially iterate through the sorted candidate list: match pair `(F, B)` if and only if neither `F` nor `B` has already been matched to another entity.

## 4. HTTP Daemon Endpoints (`telemetry-queryd`)

The daemon listens on `0.0.0.0:8085`.

### 4.1 Health Check
- `GET /healthz`
- Returns HTTP 200 OK with JSON:
  ```json
  {
    "status": "healthy"
  }
  ```

### 4.2 Query Endpoint
- `POST /v1/query`
- Request Body (JSON):
  ```json
  {
    "endpoint": "/api/v1/checkout",
    "time_range": [1700000000000, 1700000500000]
  }
  ```
  `time_range` is a half-open window `[start_ms, end_ms)`. A request belongs to the window if `start_ms <= F.req_start < end_ms` and `F.endpoint == requested_endpoint`.

- Response Body (JSON):
  ```json
  {
    "matched_count": 42,
    "unmatched_frontend_count": 3,
    "p50_backend_latency": 45.0,
    "p90_backend_latency": 85.0,
    "p99_backend_latency": 120.0,
    "error_rate": 0.05
  }
  ```
- Definitions:
  - `matched_count`: Count of frontend requests in the time window for the endpoint that are matched to a backend task.
  - `unmatched_frontend_count`: Count of frontend requests in the time window for the endpoint that could NOT be matched to any backend task.
  - `p50_backend_latency`, `p90_backend_latency`, `p99_backend_latency`: Percentiles of the backend latencies (`B.duration_ms`) of all matched requests in the window, computed using the **Nearest-Rank Method**:
    - Sort values in ascending order: v_1 <= v_2 <= ... <= v_N.
    - For percentile P in {50, 90, 99}, rank k = ceil((P / 100) * N).
    - The percentile value is v_k (in 1-based indexing, or index k - 1 in 0-based indexing), returned as a float.
    - If N == 0, return 0.0 for all percentiles.
  - `error_rate`: Count of matched requests in the window where `F.status >= 400` or `B.exit_code != 0`, divided by `matched_count` (or `0.0` if `matched_count == 0`), rounded to 4 decimal places (`round(errors / matched_count, 4)`).

### 4.3 Attribution Statistics Endpoint
- `GET /v1/attribution/stats`
- Returns global attribution metrics across all currently processed logs (HTTP 200 OK):
  ```json
  {
    "total_frontend": 1050,
    "total_backend": 1020,
    "matched_pairs": 980,
    "unmatched_frontend": 70,
    "unmatched_backend": 40,
    "total_slack_ms": 24500,
    "avg_slack_ms": 25.0
  }
  ```
- Definitions:
  - `total_frontend`: Total frontend log lines parsed.
  - `total_backend`: Total backend tasks parsed across all `.bpack` chunks.
  - `matched_pairs`: Total attributed pairs.
  - `unmatched_frontend`: `total_frontend - matched_pairs`.
  - `unmatched_backend`: `total_backend - matched_pairs`.
  - `total_slack_ms`: Sum of slack times across all matched pairs.
  - `avg_slack_ms`: `round(total_slack_ms / matched_pairs, 2)` (or `0.0` if `matched_pairs == 0`).

### 4.4 Dynamic Ingestion
When new log files are added or existing files are updated in `/var/log/telemetry/frontend/` or `/var/log/telemetry/backend/`, subsequent query or stats requests must incorporate the new data without requiring manual daemon restart.
