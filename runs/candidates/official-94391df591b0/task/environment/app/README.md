# Log Ingestion Pipeline

This service reads newline-delimited JSON (NDJSON) log files, validates each
record against a JSON Schema, and writes accepted records to a clean output
file. Records that fail validation are silently discarded.

## Directory layout

    /app/
      src/           Node.js source modules
        index.js     Entry point
        pipeline.js  Streaming orchestration
        validator.js Schema validation logic
        schema_loader.js  Schema file loading
        config.js    CLI argument parsing
        logger.js    Structured logging
        metrics.js   Throughput and error counters
        utils.js     Shared helpers
      schema.json    JSON Schema (draft-7) for log records
      logs/          Input NDJSON log files
      output/        Accepted records written here
      tools/
        gen_corpus.js  Corpus generator (for testing)

## Schema

Each log record must be a JSON object with the following fields:

| Field      | Type                              | Required |
|------------|-----------------------------------|----------|
| timestamp  | string, ISO 8601                  | yes      |
| level      | string, one of debug/info/warn/error | yes   |
| severity   | string (non-empty)                | yes      |
| service    | string                            | yes      |
| message    | string                            | yes      |
| metadata   | object                            | no       |

## Running

    node /app/src/index.js --input <file> --output /app/output/clean.ndjson

Options:

    --input,  -i   Path to NDJSON input file (required)
    --output, -o   Path for accepted records output (default: /app/output/clean.ndjson)
    --schema, -s   Path to JSON Schema file (default: /app/schema.json)
    --batch-size   Records per write batch (default: 500)
    --log-level    Logging verbosity: debug|info|warn|error (default: info)
    --dry-run      Validate without writing output
    --verbose, -v  Print top validation error reasons after completion

## Corpus generator

    node /app/tools/gen_corpus.js --size <n> --seed <s> --output <file>

Generates a deterministic NDJSON corpus of `n` records using the given seed.
Useful for performance and regression testing.
