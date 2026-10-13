PagerDuty: ALERT — production-log-pipeline failing
Timestamp: 2025-06-15T03:14:22Z
Severity: critical

The log aggregation pipeline has been producing garbled output since the last
deployment. Sample from /app/output/combined.log:

    ðß›_t¥?¾¢____æ_ë_
    `ÈÜê¼ë←ì▼§_§_³M_
    ...

The pipeline processes encrypted log files under /app/logs/<service>/, merges
them, and writes a sorted, deduplicated combined log to
/app/output/combined.log.

Documentation is at /app/README.md — it describes the encryption format and
key derivation. The configuration at /app/config.yaml holds the master key
and the list of services. The pipeline uses /app/bin/decrypt_tool for
decryption and maintains a state file at /app/state/processed.json.

Fix the pipeline so that running `python /app/pipeline.py` produces a correct,
human-readable combined log satisfying every requirement below. The fix must
work for any set of encrypted log files that follow the documented format, not
just the files already on disk.

Requirements:
- /app/output/combined.log must contain every log record from every .enc file
  across all services listed in config.yaml.
- Records must be sorted by timestamp in ascending order.
- Duplicate records with the same service name and sequence number must appear
  only once, keeping the first occurrence.
- All lines must be valid UTF-8 text, free of any garbled or binary characters.
