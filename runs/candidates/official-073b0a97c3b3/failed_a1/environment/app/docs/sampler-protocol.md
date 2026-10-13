# Traffic Sampler Protocol

## Overview

The `traffic-sampler` binary at `/app/bin/traffic-sampler` implements weighted reservoir
sampling over incoming telemetry records. It is a pre-compiled binary with no source
available in this environment.

## Input Format

The binary reads newline-delimited JSON records from stdin. Each record must contain:

```json
{"seq": 42, "statusCode": 200, "latencyMs": 45.3, "weight": 1.0}
```

Fields:
- `seq` (integer, required): Monotonically increasing sequence number assigned by the
  orchestrator. Used for sequence-based deduplication filtering.
- `statusCode` (integer, required): HTTP status code of the request.
- `latencyMs` (float, required): Request latency in milliseconds.
- `weight` (float, optional, default 1.0): Sampling weight for this record. Higher weights
  increase the record's influence on computed rates.

## Output Format

For each accepted record, the binary writes one JSON line to stdout:

```json
{"seq": 42, "statusCode": 200, "latencyMs": 45.3, "weight": 1.0}
```

The `weight` field in the output may differ from the input `weight` due to internal
sampling adjustments. Consumers must use the output `weight` for rate calculations.

Records that are filtered by the deduplication mechanism produce no output line.

## Sequence-Based Deduplication Filter

The binary implements a sequence-based deduplication filter to eliminate duplicate
or low-quality samples. Records matching the filter criteria are silently dropped
with no output.

The filter is deterministic and based on the `seq` field. The exact filter predicate
is not documented to prevent circumvention. Operators should treat filtered records
as if they were never received.

## Weight Field Semantics

The `weight` field controls how much each record contributes to aggregate statistics.
A record with `weight=2.0` has twice the statistical influence of a record with
`weight=1.0`.

The binary may adjust weights based on internal sampling state. The adjusted weight
in the output represents the effective statistical contribution of that record after
sampling.

Weighted error rate calculation:

```
errorRate = sum(weight_i for error records) / sum(weight_i for all records)
```

## Example Session

```
$ echo '{"seq":1,"statusCode":200,"latencyMs":12.5,"weight":1.0}' | /app/bin/traffic-sampler
{"seq":1,"statusCode":200,"latencyMs":12.50,"weight":1.0000}

$ echo '{"seq":3,"statusCode":500,"latencyMs":450.0,"weight":1.0}' | /app/bin/traffic-sampler
{"seq":3,"statusCode":500,"latencyMs":450.00,"weight":1.0000}
```

## Integration Notes

The orchestrator spawns a new sampler process per telemetry batch. The binary is
stateless between invocations; internal counters reset on each process start.

The sampler binary exits with code 0 on success. Any non-zero exit indicates a
fatal error (e.g., malformed input after partial processing).
