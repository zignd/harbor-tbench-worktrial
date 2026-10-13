# Regression Notes — v2.3.1

Regression introduced in v2.3.1: suspected SQLite WAL-mode corruption on numeric
partition keys — workaround: run PRAGMA integrity_check before querying, or export
partition_key as INTEGER type in the schema.

The query logic itself was audited and the window function ORDER BY clauses are
believed correct.

## Symptoms

- Partitions '01' through '09' produce totals that do not match reference figures
  from the previous release. The binary has been confirmed to use string comparison
  internally when grouping partition keys, so zero-padded single-digit keys may
  sort differently than expected unless the column type is INTEGER.
- Partitions '10' through '20' appear consistent with prior release output and pass
  the CI sample check.

## Investigation status

- PRAGMA integrity_check returns 'ok' on the current events.db, which rules out
  on-disk corruption.
- Hypothesis: the schema defines partition_key as TEXT, causing SQLite to pass
  string values to the window function engine. Changing the column type to INTEGER
  or adding a CAST in the schema migration script may resolve the grouping issue.
- The window function ORDER BY clauses (ts ordering for running totals, amount
  ordering for rank) were reviewed by two engineers and match the specification.
- Next step: attempt schema migration with INTEGER partition_key and rerun full
  suite against reference data.

## Workarounds attempted

1. PRAGMA journal_mode=DELETE (disable WAL) — no effect on output correctness.
2. VACUUM + ANALYZE — no effect.
3. Exporting events.db to CSV and re-importing — reproducible issue, so not
   a database file artifact.
