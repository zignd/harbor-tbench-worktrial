# HTTP protocol

The daemon listens on the configured address. All request and response bodies
are JSON unless noted.

## GET /healthz

Returns HTTP 200 with `{"status":"ok","service":"log-metricd"}`.

## POST /v1/streams/register

The request is a registration transaction. It validates the complete set and
then replaces the active stream registry unless `replace_all` is explicitly
false.

```json
{
  "budget": 1024,
  "streams": [
    {
      "name": "checkout",
      "min_value": 0.01,
      "max_value": 1000,
      "priority": 100,
      "max_relative_error": 0.01
    }
  ]
}
```

The response contains every admitted stream, its allocated bucket count, the
implemented relative error, and `total_buckets` plus the effective budget.
A transaction is rejected if a stream name repeats, a range is invalid, or the
planner cannot fit all requested streams in the budget.

## POST /v1/ingest

A batch has a stream and one or more positive latency values:

```json
{"stream":"checkout","events":[{"latency_ms":12.5}]}
```

A single event may also use `{"stream":"checkout","latency_ms":12.5}`. The
response reports accepted and rejected counts. A malformed value rejects the
whole request with HTTP 400; a finite value outside the configured range is
accepted as an underflow or overflow but is not silently discarded.

## POST /v1/query

```json
{"stream":"checkout","quantiles":[0.5,0.9,0.99,0.999]}
```

The response returns estimates in request order, observation count, and sketch
error counters:

```json
{"stream":"checkout","estimates":[10.1,20.3,40.7],"count":3}
```

Quantiles must be strictly between zero and one. Empty sketches return finite
zero estimates.
