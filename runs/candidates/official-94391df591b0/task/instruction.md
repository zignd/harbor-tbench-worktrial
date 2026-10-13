Last night's incident left our log ingestion pipeline in a broken state. The service lives at /app and reads NDJSON log files from /app/logs/, validates each record against the schema at /app/schema.json, and writes accepted records to /app/output/clean.ndjson.

Two things must be true when you are done: (1) every record that satisfies the schema is present in the output and no record that violates the schema appears in the output; (2) the service must complete ingestion of a 50,000-record file in under 4 seconds on this machine. The current code fails both properties. Find and fix the defects.

Run the service with: node /app/src/index.js --input <file> --output /app/output/clean.ndjson
