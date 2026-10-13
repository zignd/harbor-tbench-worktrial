# Log Ingestion Pipeline

A Node.js service that reads newline-delimited JSON (NDJSON) log files, validates
each record against a JSON Schema, and writes accepted records to a clean output file.

## Structure

```
/app/
  src/
    index.js          - Entry point and orchestration
    pipeline.js       - Streaming pipeline and file I/O
    validator.js      - JSON Schema validation (Ajv)
    schema_loader.js  - Schema file loading and introspection
    config.js         - Configuration and CLI argument parsing
    utils.js          - Utility functions
    metrics.js        - Internal metrics collection
    logger.js         - Structured logging
  tools/
    gen_corpus.js     - Deterministic NDJSON corpus generator
  logs/
    sample.ndjson     - Sample log corpus from incident window
  schema.json         - JSON Schema for log record validation
  output/             - Default output directory (writable)
  package.json
```

## Usage

```bash
node /app/src/index.js --input <input.ndjson> --output /app/output/clean.ndjson
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--input <file>` | `/app/logs/sample.ndjson` | Input NDJSON file |
| `--output <file>` | `/app/output/clean.ndjson` | Output NDJSON file |
| `--schema <file>` | `/app/schema.json` | JSON Schema path |
| `--log-level <level>` | `info` | Logging level (debug/info/warn/error) |
| `--batch-size <n>` | `500` | Internal batch size hint |
| `--no-metrics` | off | Disable periodic metrics reporting |

## Schema

The schema at `/app/schema.json` is JSON Schema draft-7. Required fields:

- `timestamp` (string): ISO 8601 datetime
- `level` (string): one of `debug`, `info`, `warn`, `error`
- `severity` (string): severity label, must be a string
- `service` (string): originating service name
- `message` (string): human-readable event description

Optional fields:
- `metadata` (object): arbitrary key-value pairs

## Corpus Generator

```bash
node /app/tools/gen_corpus.js --seed 1 --count 1000 --mode mixed --output /tmp/corpus.ndjson
```

Modes: `benign` (all valid), `malicious` (all invalid), `mixed` (interleaved, default 20% invalid).
All output is deterministic for a given seed.
