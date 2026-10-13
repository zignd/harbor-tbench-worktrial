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

The `weight` field in the output reflects the record's weight after internal sampling
adjustments. The output weight may differ from the input weight. Operators should
cross-reference the original request context when computing error rates, as the binary's
internal adjustments are tuned for reservoir sampling throughput, not error classification.

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
in the output reflects internal sampling bookkeeping and may not correspond to the
original request weight for all record types.

Weighted error rate calculation:

```
errorRate = sum(weight_i for error records) / sum(weight_i for all records)
```

where `weight_i` is the weight associated with each sample in the health window.

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
